"""
Breathing Cycle Launcher (ADR-200 Phase 3b).

Triggers ontology breathing cycles based on epoch interval.
Dual-trigger: runs on cron schedule AND after ingestion.
The epoch delta check prevents redundant runs regardless of trigger source.

All tunable parameters are read from kg_api.breathing_options at launch time.
Code defaults apply when a key is absent from the table.
"""

from .base import JobLauncher
from api.app.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Code defaults — overridden by kg_api.breathing_options rows
DEFAULTS = {
    "epoch_interval": 5,
    "demotion_threshold": 0.15,
    "promotion_min_degree": 10,
    "max_proposals": 5,
    "enabled": True,
}


def _read_options(conn) -> Dict:
    """Read breathing_options from database, falling back to code defaults."""
    options = dict(DEFAULTS)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM kg_api.breathing_options")
            for key, value in cur.fetchall():
                if key in ("enabled", "derive_edges"):
                    options[key] = value.lower() in ("true", "1", "yes")
                elif key in ("epoch_interval", "promotion_min_degree", "max_proposals"):
                    options[key] = int(value)
                elif key in ("demotion_threshold", "overlap_threshold", "specializes_threshold"):
                    options[key] = float(value)
                else:
                    options[key] = value
    except Exception as e:
        logger.warning(f"BreathingLauncher: could not read breathing_options, using defaults: {e}")
    return options


class BreathingLauncher(JobLauncher):
    """
    Trigger breathing cycles based on epoch interval.

    Condition: current_epoch - last_breathing_epoch >= epoch_interval
    Worker: breathing_worker (ontology_breathing)

    Triggered from:
    - Cron schedule (every 6 hours, via scheduled_jobs_manager)
    - Post-ingestion hook (ingestion_worker, after epoch increment)
    - Manual API call (POST /ontology/breathing-cycle)

    check_conditions() uses an atomic UPDATE to both verify the epoch
    delta AND claim the epoch window in one statement. This prevents
    concurrent triggers from both passing the check.

    Parameters are read from kg_api.breathing_options at launch time.
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
                    logger.info("BreathingLauncher: disabled via breathing_options")
                    return False

                current_epoch = client.get_current_epoch()
                epoch_interval = options["epoch_interval"]

                # Atomic check-and-claim: UPDATE only succeeds if delta is sufficient
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.graph_metrics "
                        "SET counter = %s, updated_at = CURRENT_TIMESTAMP "
                        "WHERE metric_name = 'last_breathing_epoch' "
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
                        f"BreathingLauncher: claimed epoch {current_epoch} "
                        f"(interval={epoch_interval}), triggering cycle"
                    )
                    return True

                logger.debug(
                    f"BreathingLauncher: epoch delta < {epoch_interval} "
                    f"or already claimed, skipping"
                )
                return False

            finally:
                client.pool.putconn(conn)

        finally:
            client.close()

    def prepare_job_data(self) -> Dict:
        """
        Prepare breathing cycle parameters.

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
            "dry_run": False,
            "triggered_at_epoch": current_epoch,
            "description": f"Breathing cycle at epoch {current_epoch}",
        }

    def get_job_type(self) -> str:
        return "ontology_breathing"
