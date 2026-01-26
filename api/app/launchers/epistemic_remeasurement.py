"""
Epistemic Re-measurement Launcher (ADR-065 Phase 2).

Automatically re-measure epistemic status when vocabulary changes exceed threshold.
Checks every 1 hour (configured in kg_api.scheduled_jobs) but only runs when
vocabulary_change_counter delta >= threshold.
"""

from .base import JobLauncher
from api.app.services.vocabulary_metrics_service import VocabularyMetricsService
from api.app.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class EpistemicRemeasurementLauncher(JobLauncher):
    """
    Automatically re-measure epistemic status when vocabulary changes accumulate.

    Schedule: Every 1 hour (cron: "0 * * * *")
    Condition: vocabulary_change_counter delta >= threshold (default: 10)
    Worker: epistemic_remeasurement_worker
    Pattern: Polling (checks hourly, runs when threshold met)

    Example flow:
    1. Scheduler fires every hour
    2. check_conditions() queries vocabulary_change_counter delta
    3. If delta >= 10: enqueue epistemic_remeasurement job
    4. If delta < 10: skip (return False, not a failure)
    5. Worker runs measurement and resets delta to 0
    """

    def __init__(self, job_queue, max_retries: int = 5, threshold: int = 10):
        """
        Initialize launcher with vocabulary change threshold.

        Args:
            job_queue: JobQueue instance
            max_retries: Maximum retry attempts for failed jobs
            threshold: Minimum vocabulary changes to trigger re-measurement (default: 10)
        """
        super().__init__(job_queue, max_retries)
        self.threshold = threshold

    def check_conditions(self) -> bool:
        """
        Check if vocabulary changes have exceeded threshold.

        Returns:
            True if vocabulary_change_counter delta >= threshold, False otherwise
        """
        try:
            client = AGEClient()
            conn = client.pool.getconn()
            try:
                metrics_service = VocabularyMetricsService(conn)

                # Get vocabulary change counter delta
                delta = metrics_service.get_counter_delta('vocabulary_change_counter')

                if delta >= self.threshold:
                    logger.info(
                        f"✓ EpistemicRemeasurementLauncher: Vocabulary change delta ({delta}) "
                        f">= threshold ({self.threshold})"
                    )
                    return True

                logger.debug(
                    f"EpistemicRemeasurementLauncher: Delta ({delta}) below threshold ({self.threshold})"
                )
                return False

            finally:
                client.pool.putconn(conn)

        except Exception as e:
            # Let exceptions bubble up so scheduler can retry
            logger.error(f"EpistemicRemeasurementLauncher condition check failed: {e}")
            raise

    def prepare_job_data(self) -> Dict:
        """
        Prepare data for epistemic re-measurement worker.

        Returns:
            Dict with measurement parameters
        """
        return {
            "operation": "remeasure_epistemic_status",
            "sample_size": 100,  # Default sample size
            "store": True,  # Store results to VocabType nodes
            "description": f"Scheduled epistemic re-measurement (delta >= {self.threshold})"
        }

    def get_job_type(self) -> str:
        """
        Return job type for worker registry.

        Returns:
            "epistemic_remeasurement" (must be registered as worker)
        """
        return "epistemic_remeasurement"
