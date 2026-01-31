"""
Breathing Cycle Launcher (ADR-200 Phase 3b).

Triggers ontology breathing cycles based on epoch interval.
Called after ingestion completes — checks if enough epochs have
passed since the last breathing cycle.
"""

from .base import JobLauncher
from api.app.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class BreathingLauncher(JobLauncher):
    """
    Trigger breathing cycles based on ingestion epoch interval.

    Condition: current_epoch - last_breathing_epoch >= epoch_interval
    Worker: breathing_worker (ontology_breathing)
    Pattern: Event-driven (checked after each ingestion)

    Default: breathe every 5 epochs (configurable).
    """

    def __init__(self, job_queue, epoch_interval: int = 5, **kwargs):
        super().__init__(job_queue, **kwargs)
        self.epoch_interval = epoch_interval

    def check_conditions(self) -> bool:
        """
        Check if enough epochs have passed since last breathing cycle.

        Uses the 'last_breathing_epoch' counter in kg_api.counters.
        If it doesn't exist, creates it at 0 (first run always triggers).
        """
        client = AGEClient()
        try:
            current_epoch = client.get_current_epoch()

            # Get last breathing epoch from counters table
            conn = client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT value FROM kg_api.counters
                        WHERE name = 'last_breathing_epoch'
                    """)
                    row = cur.fetchone()
                    last_epoch = row[0] if row else 0
            finally:
                client.pool.putconn(conn)

            delta = current_epoch - last_epoch

            if delta >= self.epoch_interval:
                logger.info(
                    f"BreathingLauncher: epoch delta {delta} >= {self.epoch_interval}, "
                    f"triggering cycle (current={current_epoch}, last={last_epoch})"
                )
                return True

            logger.debug(
                f"BreathingLauncher: epoch delta {delta} < {self.epoch_interval}, skipping"
            )
            return False

        finally:
            client.close()

    def prepare_job_data(self) -> Dict:
        """
        Prepare breathing cycle parameters.

        Also updates last_breathing_epoch to current epoch to prevent
        re-triggering while the cycle runs.
        """
        client = AGEClient()
        try:
            current_epoch = client.get_current_epoch()

            # Update last_breathing_epoch so we don't re-trigger
            conn = client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO kg_api.counters (name, value)
                        VALUES ('last_breathing_epoch', %s)
                        ON CONFLICT (name) DO UPDATE SET value = %s
                    """, (current_epoch, current_epoch))
                conn.commit()
            finally:
                client.pool.putconn(conn)

            return {
                "demotion_threshold": 0.15,
                "promotion_min_degree": 10,
                "max_proposals": 5,
                "dry_run": False,
                "triggered_at_epoch": current_epoch,
                "description": f"Scheduled breathing cycle at epoch {current_epoch}",
            }

        finally:
            client.close()

    def get_job_type(self) -> str:
        return "ontology_breathing"
