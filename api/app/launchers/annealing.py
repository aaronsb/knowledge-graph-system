"""
Annealing Cycle Launcher (ADR-200).

Triggers ontology annealing cycles based on epoch interval.
Dual-trigger: runs on cron schedule AND after ingestion.
The epoch delta check prevents redundant runs regardless of trigger source.

All tunable parameters are read from kg_api.annealing_options at launch time.
Code defaults apply when a key is absent from the table.
"""

from .base import JobLauncher
from api.app.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Code defaults — overridden by kg_api.annealing_options rows.
# Per-ontology cadence floors (min_ontology_age_epochs, min_ontology_concept_count)
# are added by migration 065 for #402 Defect C.
DEFAULTS = {
    "epoch_interval": 5,
    "demotion_threshold": 0.15,
    "promotion_min_degree": 10,
    "max_proposals": 5,
    "enabled": True,
    "automation_level": "autonomous",
    "min_ontology_age_epochs": 3,
    "min_ontology_concept_count": 5,
    # Refractory gate (ADR-200): defer annealing while ingestion is in-flight,
    # but force a cycle once this many epochs have accumulated so a continuous
    # ingestion stream can't starve annealing entirely. ~10x epoch_interval.
    "inflight_defer_max_epochs": 50,
}


def _read_options(conn) -> Dict:
    """Read annealing_options from database, falling back to code defaults."""
    options = dict(DEFAULTS)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM kg_api.annealing_options")
            for key, value in cur.fetchall():
                if key in ("enabled", "derive_edges"):
                    options[key] = value.lower() in ("true", "1", "yes")
                elif key in (
                    "epoch_interval",
                    "promotion_min_degree",
                    "max_proposals",
                    "min_ontology_age_epochs",
                    "min_ontology_concept_count",
                    "inflight_defer_max_epochs",
                ):
                    options[key] = int(value)
                elif key in ("demotion_threshold", "overlap_threshold", "specializes_threshold"):
                    options[key] = float(value)
                else:
                    options[key] = value
    except Exception as e:
        logger.warning(f"AnnealingLauncher: could not read annealing_options, using defaults: {e}")
    return options


def _should_defer_for_inflight(
    inflight_count: int, epoch_delta: int, max_defer_epochs: int
) -> bool:
    """Decide whether to defer an annealing cycle because ingestion is in-flight.

    Refractory gate (ADR-200, Approach A): annealing reorganizes the graph, so
    running it while documents are still being ingested churns work that the
    next chunk invalidates — the "panic mode" observed when a large ingest
    bumps the epoch faster than the epoch_interval cadence. Defer while
    ingestion is active, but only up to `max_defer_epochs` of accumulated epoch
    delta, after which we force a cycle so a continuous ingestion stream can't
    starve annealing entirely.

    Pure function (no I/O) so the policy is unit-testable in isolation.
    """
    if inflight_count <= 0:
        return False
    return epoch_delta < max_defer_epochs


class AnnealingLauncher(JobLauncher):
    """
    Trigger annealing cycles based on epoch interval.

    Condition: current_epoch - last_annealing_epoch >= epoch_interval
    Worker: annealing_worker (ontology_annealing)

    Triggered from:
    - Cron schedule (every 6 hours, via scheduled_jobs_manager)
    - Post-ingestion hook (ingestion_worker, after epoch increment)
    - Manual API call (POST /ontology/annealing-cycle)

    check_conditions() uses an atomic UPDATE to both verify the epoch
    delta AND claim the epoch window in one statement. This prevents
    concurrent triggers from both passing the check.

    Parameters are read from kg_api.annealing_options at launch time.
    """

    def __init__(self, job_queue, max_retries: int = 5):
        super().__init__(job_queue, max_retries=max_retries)
        self._cached_options = None
        self._cached_epoch = None

    def check_conditions(self) -> bool:
        """
        Atomically check epoch delta and claim the window.

        Uses UPDATE ... WHERE to combine the condition check and epoch
        stamp into a single statement, preventing TOCTOU races when
        multiple triggers fire concurrently.
        """
        client = AGEClient()
        try:
            conn = client.pool.getconn()
            try:
                options = _read_options(conn)

                if not options["enabled"]:
                    logger.info("AnnealingLauncher: disabled via annealing_options")
                    return False

                current_epoch = client.get_current_epoch()
                epoch_interval = options["epoch_interval"]

                # Refractory gate (Approach A): defer while ingestion is actively
                # in-flight so we don't anneal a graph that's still being flooded
                # with concepts. Bounded by inflight_defer_max_epochs so a
                # continuous stream can't starve annealing. (Graded pressure-curve
                # response is the Approach B follow-up — see GitHub issue.)
                inflight = self._count_inflight_ingestion(conn)
                if inflight > 0:
                    max_defer = options["inflight_defer_max_epochs"]
                    epoch_delta = current_epoch - self._read_last_annealing_epoch(conn)
                    if _should_defer_for_inflight(inflight, epoch_delta, max_defer):
                        logger.info(
                            f"AnnealingLauncher: deferring — {inflight} ingestion "
                            f"job(s) in-flight (epoch_delta={epoch_delta} < "
                            f"max_defer={max_defer}); waiting for the influx to settle"
                        )
                        conn.rollback()
                        return False
                    logger.info(
                        f"AnnealingLauncher: {inflight} ingestion job(s) in-flight "
                        f"but epoch_delta={epoch_delta} >= max_defer={max_defer}; "
                        f"forcing a cycle to avoid starvation"
                    )

                # Atomic check-and-claim: UPDATE only succeeds if delta is sufficient
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.graph_metrics "
                        "SET counter = %s, updated_at = CURRENT_TIMESTAMP "
                        "WHERE metric_name = 'last_annealing_epoch' "
                        "AND %s - counter >= %s "
                        "RETURNING counter",
                        (current_epoch, current_epoch, epoch_interval)
                    )
                    row = cur.fetchone()
                conn.commit()

                if row:
                    self._cached_options = options
                    self._cached_epoch = current_epoch
                    logger.info(
                        f"AnnealingLauncher: claimed epoch {current_epoch} "
                        f"(interval={epoch_interval}), triggering cycle"
                    )
                    return True

                logger.debug(
                    f"AnnealingLauncher: epoch delta < {epoch_interval} "
                    f"or already claimed, skipping"
                )
                return False

            finally:
                client.pool.putconn(conn)

        finally:
            client.close()

    @staticmethod
    def _count_inflight_ingestion(conn) -> int:
        """Count ingestion jobs that are queued or actively running (the influx).

        Counts pending/queued/approved/running ingestion + image-ingestion jobs.
        Excludes terminal states (completed/failed/cancelled) and
        awaiting_approval (not yet committed to run — could sit indefinitely and
        would otherwise defer annealing forever). Fails open (returns 0) so an
        error here never blocks annealing.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM kg_api.jobs "
                    "WHERE job_type IN ('ingestion', 'ingest_image') "
                    "AND status IN ('pending', 'queued', 'approved', 'running')"
                )
                return int(cur.fetchone()[0])
        except Exception as e:
            logger.warning(f"AnnealingLauncher: in-flight ingestion check failed: {e}")
            return 0

    @staticmethod
    def _read_last_annealing_epoch(conn) -> int:
        """Read the last claimed annealing epoch (0 if the metric is absent)."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT counter FROM public.graph_metrics "
                "WHERE metric_name = 'last_annealing_epoch'"
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def prepare_job_data(self) -> Dict:
        """
        Prepare annealing cycle parameters.

        Uses values cached by check_conditions() to avoid a second
        database round-trip and stay within the same atomic window.
        """
        options = self._cached_options or DEFAULTS
        current_epoch = self._cached_epoch or 0

        return {
            "demotion_threshold": options["demotion_threshold"],
            "promotion_min_degree": options["promotion_min_degree"],
            "max_proposals": options["max_proposals"],
            "derive_edges": options.get("derive_edges", True),
            "overlap_threshold": options.get("overlap_threshold", 0.1),
            "specializes_threshold": options.get("specializes_threshold", 0.3),
            "automation_level": options.get("automation_level", "autonomous"),
            "min_ontology_age_epochs": options.get("min_ontology_age_epochs", 3),
            "min_ontology_concept_count": options.get("min_ontology_concept_count", 5),
            "dry_run": False,
            "triggered_at_epoch": current_epoch,
            "description": f"Annealing cycle at epoch {current_epoch}",
        }

    def get_job_type(self) -> str:
        return "ontology_annealing"
