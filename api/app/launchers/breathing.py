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
                if key == "enabled":
                    options[key] = value.lower() in ("true", "1", "yes")
                elif key in ("epoch_interval", "promotion_min_degree", "max_proposals"):
                    options[key] = int(value)
                elif key in ("demotion_threshold",):
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

    The epoch delta check in check_conditions() gates all triggers,
    so multiple trigger sources cannot cause redundant runs.

    Parameters are read from kg_api.breathing_options at launch time.
    """

    def __init__(self, job_queue, max_retries: int = 5):
        super().__init__(job_queue, max_retries=max_retries)

    def check_conditions(self) -> bool:
        """
        Check if breathing is enabled and enough epochs have passed.

        Reads configuration from kg_api.breathing_options and epoch state
        from public.graph_metrics (same table as all other epoch counters).
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

                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM public.graph_metrics "
                        "WHERE metric_name = 'last_breathing_epoch'"
                    )
                    row = cur.fetchone()
                    last_epoch = row[0] if row else 0

                epoch_interval = options["epoch_interval"]
                delta = current_epoch - last_epoch

                if delta >= epoch_interval:
                    logger.info(
                        f"BreathingLauncher: epoch delta {delta} >= {epoch_interval}, "
                        f"triggering cycle (current={current_epoch}, last={last_epoch})"
                    )
                    return True

                logger.debug(
                    f"BreathingLauncher: epoch delta {delta} < {epoch_interval}, skipping"
                )
                return False

            finally:
                client.pool.putconn(conn)

        finally:
            client.close()

    def prepare_job_data(self) -> Dict:
        """
        Prepare breathing cycle parameters from database options.

        Also stamps last_breathing_epoch in graph_metrics to prevent
        re-triggering while the cycle runs.
        """
        client = AGEClient()
        try:
            conn = client.pool.getconn()
            try:
                options = _read_options(conn)
                current_epoch = client.get_current_epoch()

                # Stamp last_breathing_epoch to claim this epoch window
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.graph_metrics "
                        "SET counter = %s, updated_at = CURRENT_TIMESTAMP "
                        "WHERE metric_name = 'last_breathing_epoch'",
                        (current_epoch,)
                    )
                conn.commit()

                return {
                    "demotion_threshold": options["demotion_threshold"],
                    "promotion_min_degree": options["promotion_min_degree"],
                    "max_proposals": options["max_proposals"],
                    "dry_run": False,
                    "triggered_at_epoch": current_epoch,
                    "description": f"Breathing cycle at epoch {current_epoch}",
                }

            finally:
                client.pool.putconn(conn)

        finally:
            client.close()

    def get_job_type(self) -> str:
        return "ontology_breathing"
