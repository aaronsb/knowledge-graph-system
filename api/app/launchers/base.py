"""
Base class for scheduled job launchers (ADR-050).

Launchers are lightweight "sequencers" that check conditions and prepare jobs
for the existing job queue. They don't execute work themselves - they just
decide WHEN to trigger workers.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class JobLauncher(ABC):
    """
    Base class for scheduled job launchers.

    Launchers are lightweight "sequencers" that:
    1. Check if conditions are met to run a job
    2. Prepare job_data for the worker
    3. Enqueue job to existing job queue

    The existing job queue handles execution, progress, approval, etc.

    Three-Outcome Pattern:
    - Returns job_id: Job successfully enqueued (success)
    - Returns None: Conditions not met, skip (normal, not a failure)
    - Raises Exception: Actual failure (needs retry/backoff)
    """

    def __init__(self, job_queue, max_retries: int = 5):
        """
        Initialize launcher.

        Args:
            job_queue: JobQueue instance for enqueuing jobs
            max_retries: Max retries for this launcher (from schedule config)
        """
        self.job_queue = job_queue
        self.max_retries = max_retries

    @abstractmethod
    def check_conditions(self) -> bool:
        """
        Check if conditions are met to run this job.

        Returns:
            True if job should run, False to skip

        Example:
            - Check if there are llm_generated categories
            - Check if vocabulary spread exceeds threshold
            - Check if database backup is needed

        Note: This should be a cheap operation (SQL query, file check, etc.)
              The expensive work happens in the worker.
        """
        pass

    @abstractmethod
    def prepare_job_data(self) -> Dict:
        """
        Prepare job_data dict for the worker function.

        Returns:
            Dict with parameters for the worker

        Example:
            {
                "operation": "refresh_categories",
                "auto_mode": True,
                "filter": "llm_generated"
            }
        """
        pass

    @abstractmethod
    def get_job_type(self) -> str:
        """
        Return the job type for worker registry lookup.

        Returns:
            Job type string (e.g., "vocab_refresh", "vocab_consolidate")

        This job type must be registered in the worker registry:
            queue.register_worker("vocab_refresh", run_vocab_refresh_worker)
        """
        pass

    def launch(self) -> Optional[str]:
        """
        Execute the launcher: check conditions, prepare data, enqueue job.

        Returns:
            job_id if enqueued, None if conditions not met (normal skip).

        Raises:
            Exception: If condition check, data prep, or enqueueing fails.

        Important: A return value of None means "conditions not met, this is
        normal, don't treat as failure." Any actual failure should raise an
        exception so the scheduler can distinguish:
            - Success (job_id returned) → Reset retry_count
            - Skip (None returned) → Reset retry_count, advance schedule
            - Failure (exception raised) → Increment retry_count, backoff
        """
        # Let exceptions bubble up - scheduler handles them
        if not self.check_conditions():
            logger.info(f"⏭️  {self.__class__.__name__}: Conditions not met, skipping")
            return None  # Normal skip, not a failure

        logger.info(f"✓  {self.__class__.__name__}: Conditions met, preparing job")

        # Let exceptions bubble up
        job_data = self.prepare_job_data()

        # Let exceptions bubble up
        job_id = self.job_queue.enqueue(
            job_type=self.get_job_type(),
            job_data=job_data
        )

        # Mark as system job and auto-approve (ADR-050: job ownership)
        # System/scheduled jobs bypass the approval workflow since they're
        # triggered by internal conditions, not user uploads
        if job_id:
            self.job_queue.update_job(job_id, {
                "is_system_job": True,
                "job_source": "scheduled_task",
                "created_by": f"system:scheduler:{self.__class__.__name__}",
                "status": "approved",
                "approved_at": datetime.now().isoformat(),
                "approved_by": "system:scheduler"
            })

            # Trigger execution immediately (fixes #221: jobs stuck in pending)
            self.job_queue.execute_job_async(job_id)

        logger.info(f"✅ {self.__class__.__name__}: Enqueued and started job {job_id}")
        return job_id
