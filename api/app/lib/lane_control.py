"""Worker-lane freeze / quiesce helpers (ADR-100, ADR-102 P5 / A14).

A restore wholesale rewrites the graph. If other workers keep mutating it mid
restore (ingestion in the ``interactive`` lane, projection/annealing in the
``maintenance`` lane) the import races those writes and the result is
inconsistent. So before importing we *freeze* the mutating lanes and wait for
their in-flight jobs to drain, then *thaw* them afterward.

Mechanism: lane enable/disable lives in ``kg_api.worker_lanes.enabled``, which
the LaneManager re-reads every poll cycle (ADR-100). Setting it false stops a
lane claiming NEW jobs within one poll interval; already-running jobs finish
naturally. Drain is detected by polling ``kg_api.jobs`` for running jobs whose
``job_type`` belongs to a frozen lane — a cross-process signal (the in-memory
``active_count`` on LaneManager is per-process and not visible from a worker).

The restore worker itself runs in the ``system`` lane, which is NOT frozen:
``system`` is ``max_slots=1`` (self-serializing) and also hosts the post-restore
rehydration jobs (``source_embedding``, ``vocab_consolidate``), which must run
*after* restore releases the slot.  @verified (new)
"""
import logging
import os
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

# Lanes whose work mutates (or derives from) the graph. Frozen for the duration
# of a restore. ``system`` is intentionally absent — see module docstring.
RESTORE_FREEZE_LANES: List[str] = ["interactive", "maintenance"]

# In-flight job statuses (ADR-100 claim sets 'running'; 'processing' is the
# legacy in-flight marker still honored across the queue).
_INFLIGHT_STATUSES = ("running", "processing")

# How long to wait for frozen lanes to drain before proceeding anyway
# (fail-open, ADR-102 P5 decision). Configurable for slow/long-job installs.
DEFAULT_QUIESCE_TIMEOUT_S = int(os.getenv("KG_RESTORE_QUIESCE_TIMEOUT_S", "120"))
_QUIESCE_POLL_INTERVAL_S = 2.0


def freeze_lanes(job_queue, lane_names: List[str]) -> Dict[str, bool]:
    """Disable the given lanes, returning their PRIOR enabled state.

    The prior state is what ``thaw_lanes`` restores — so a lane an operator had
    already disabled stays disabled after the restore (we never silently
    re-enable something we did not freeze).
    """
    prior: Dict[str, bool] = {}
    conn = job_queue._get_connection()
    try:
        with conn.cursor() as cur:
            # Capture prior enabled, then disable — one round-trip per lane via
            # UPDATE ... RETURNING the OLD value (a correlated subquery on the
            # same row reads its post-update state, so read prior explicitly).
            for name in lane_names:
                cur.execute("SELECT enabled FROM kg_api.worker_lanes WHERE name = %s", (name,))
                row = cur.fetchone()
                if row is None:
                    logger.warning("Cannot freeze unknown lane %r", name)
                    continue
                prior[name] = bool(row[0])
                cur.execute(
                    "UPDATE kg_api.worker_lanes SET enabled = FALSE, updated_at = NOW() WHERE name = %s",
                    (name,),
                )
        conn.commit()
        logger.info("Froze worker lanes %s (prior enabled: %s)", lane_names, prior)
    except Exception:
        conn.rollback()
        raise
    finally:
        job_queue._return_connection(conn)
    return prior


def thaw_lanes(job_queue, prior_state: Dict[str, bool]) -> None:
    """Restore lanes to their pre-freeze enabled state. Best-effort.

    Called from a ``finally`` — must never raise, or a restore failure would be
    masked by a thaw failure and leave lanes frozen with no error surfaced.
    """
    if not prior_state:
        return
    try:
        conn = job_queue._get_connection()
        try:
            with conn.cursor() as cur:
                for name, was_enabled in prior_state.items():
                    cur.execute(
                        "UPDATE kg_api.worker_lanes SET enabled = %s, updated_at = NOW() WHERE name = %s",
                        (was_enabled, name),
                    )
            conn.commit()
            logger.info("Thawed worker lanes (restored prior state: %s)", prior_state)
        except Exception:
            conn.rollback()
            raise
        finally:
            job_queue._return_connection(conn)
    except Exception as e:
        # Surface loudly — lanes left frozen is an operator-visible condition.
        logger.error("Failed to thaw worker lanes %s: %s", list(prior_state), e, exc_info=True)


def _lane_job_types(job_queue, lane_names: List[str]) -> List[str]:
    """The flattened set of job_types served by the given lanes."""
    conn = job_queue._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT unnest(job_types) FROM kg_api.worker_lanes WHERE name = ANY(%s)",
                (lane_names,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        job_queue._return_connection(conn)


def _count_inflight(job_queue, job_types: List[str]) -> int:
    """Count in-flight jobs of the given types (cross-process drain signal)."""
    if not job_types:
        return 0
    conn = job_queue._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM kg_api.jobs "
                "WHERE status = ANY(%s) AND job_type = ANY(%s)",
                (list(_INFLIGHT_STATUSES), job_types),
            )
            return int(cur.fetchone()[0])
    finally:
        job_queue._return_connection(conn)


def wait_for_quiesce(job_queue, lane_names: List[str],
                     timeout_s: int = DEFAULT_QUIESCE_TIMEOUT_S,
                     poll_interval_s: float = _QUIESCE_POLL_INTERVAL_S) -> bool:
    """Poll until the frozen lanes' in-flight jobs drain to zero.

    Fail-open (ADR-102 P5): returns True when drained, False on timeout. The
    caller proceeds with the restore either way (a timeout is logged as a
    warning) — we do NOT force-cancel in-flight jobs, because cancelling a
    worker mid graph-write risks a partial mutation the restore would then
    stomp inconsistently.
    """
    job_types = _lane_job_types(job_queue, lane_names)
    deadline = time.monotonic() + timeout_s
    while True:
        inflight = _count_inflight(job_queue, job_types)
        if inflight == 0:
            return True
        if time.monotonic() >= deadline:
            logger.warning(
                "Lane quiesce timed out after %ss with %d in-flight job(s) in %s; "
                "proceeding with restore (fail-open)",
                timeout_s, inflight, lane_names,
            )
            return False
        logger.info("Waiting for %d in-flight job(s) in %s to drain...", inflight, lane_names)
        time.sleep(poll_interval_s)
