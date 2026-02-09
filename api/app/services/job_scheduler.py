"""
Job lifecycle scheduler.

Runs periodic maintenance tasks:
- Cancel expired unapproved jobs (24h timeout)
- Delete old completed/cancelled jobs (48h retention)
- Delete old failed jobs (7 days retention for debugging)
- Expire stale annealing proposals past their TTL (7 days)

Based on ADR-014: Job Approval Workflow
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import logging
import os

logger = logging.getLogger(__name__)


class JobScheduler:
    """Background scheduler for job lifecycle management."""

    def __init__(
        self,
        cleanup_interval: int = 3600,      # 1 hour
        approval_timeout: int = 24,        # 24 hours
        completed_retention: int = 48,     # 48 hours
        failed_retention: int = 168        # 7 days
    ):
        """
        Initialize job scheduler.

        Args:
            cleanup_interval: Seconds between cleanup runs (default: 3600 = 1 hour)
            approval_timeout: Hours before cancelling unapproved jobs (default: 24)
            completed_retention: Hours to keep completed/cancelled jobs (default: 48)
            failed_retention: Hours to keep failed jobs (default: 168 = 7 days)
        """
        self.cleanup_interval = cleanup_interval
        self.approval_timeout = timedelta(hours=approval_timeout)
        self.completed_retention = timedelta(hours=completed_retention)
        self.failed_retention = timedelta(hours=failed_retention)
        self.running = False
        self.task: Optional[asyncio.Task] = None

    def start(self):
        """Start the scheduler background task."""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info(
            f"Job scheduler started (interval: {self.cleanup_interval}s, "
            f"approval_timeout: {self.approval_timeout.total_seconds() / 3600:.0f}h, "
            f"completed_retention: {self.completed_retention.total_seconds() / 3600:.0f}h, "
            f"failed_retention: {self.failed_retention.total_seconds() / 3600:.0f}h)"
        )

    async def stop(self):
        """Stop the scheduler gracefully."""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Job scheduler stopped")

    async def _run(self):
        """Main scheduler loop - runs cleanup and job processing periodically."""
        # On startup, immediately check for stuck approved jobs
        try:
            await self.process_approved_jobs()
        except Exception as e:
            logger.error(f"Error processing approved jobs on startup: {e}", exc_info=True)

        while self.running:
            try:
                await self.cleanup_jobs()
                # Also check for stuck approved jobs each cycle
                await self.process_approved_jobs()
            except Exception as e:
                logger.error(f"Error in job scheduler: {e}", exc_info=True)

            # Sleep until next run
            await asyncio.sleep(self.cleanup_interval)

    async def process_approved_jobs(self):
        """
        Process approved jobs that may be stuck in queue.

        This handles the case where:
        - API restarted while jobs were in 'approved' status
        - Jobs were approved but never started due to race conditions
        - Serial queue processing was interrupted

        Uses database-backed queue (see job_queue.py) for safe concurrent access.
        """
        from .job_queue import get_job_queue

        queue = get_job_queue()

        # Check if any serial job is currently running
        running_jobs = queue.list_jobs(status="running", limit=1)
        running_serial = any(j.get("processing_mode") == "serial" for j in running_jobs)

        if running_serial:
            # A serial job is already running - don't start another
            return

        # Get oldest approved serial job
        approved_jobs = queue.list_jobs(status="approved", limit=10)
        serial_jobs = [j for j in approved_jobs if j.get("processing_mode", "serial") == "serial"]

        if serial_jobs:
            # Sort by created_at and take oldest
            serial_jobs.sort(key=lambda j: j.get("created_at", ""))
            oldest_job = serial_jobs[0]

            logger.info(f"Found stuck approved job, starting: {oldest_job['job_id']}")
            # Use queue_serial_job which handles database state atomically
            queue.queue_serial_job(oldest_job["job_id"])

    async def cleanup_jobs(self):
        """
        Run all cleanup tasks.

        - Cancel unapproved jobs older than approval_timeout
        - Delete completed/cancelled jobs older than completed_retention
        - Delete failed jobs older than failed_retention
        """
        from .job_queue import get_job_queue

        queue = get_job_queue()
        now = datetime.now(timezone.utc)

        # Task 1: Cancel expired unapproved jobs
        expired_count = 0
        for job in queue.list_jobs(status="awaiting_approval", limit=1000):
            created = datetime.fromisoformat(job["created_at"])
            # Make timezone-aware if naive
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = now - created

            if age > self.approval_timeout:
                queue.update_job(job["job_id"], {
                    "status": "cancelled",
                    "error": f"Expired - not approved within {self.approval_timeout.total_seconds() / 3600:.0f} hours"
                })
                expired_count += 1

        if expired_count > 0:
            logger.info(f"Cancelled {expired_count} expired unapproved jobs")

        # Task 2: Delete old completed/cancelled jobs
        deleted_completed = 0
        for status in ["completed", "cancelled"]:
            for job in queue.list_jobs(status=status, limit=1000):
                if job.get("completed_at"):
                    completed = datetime.fromisoformat(job["completed_at"])
                    # Make timezone-aware if naive
                    if completed.tzinfo is None:
                        completed = completed.replace(tzinfo=timezone.utc)
                    age = now - completed

                    if age > self.completed_retention:
                        queue.delete_job(job["job_id"])
                        deleted_completed += 1

        if deleted_completed > 0:
            logger.info(f"Deleted {deleted_completed} old completed/cancelled jobs")

        # Task 3: Delete old failed jobs (longer retention)
        deleted_failed = 0
        for job in queue.list_jobs(status="failed", limit=1000):
            if job.get("completed_at"):
                completed = datetime.fromisoformat(job["completed_at"])
                # Make timezone-aware if naive
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                age = now - completed

                if age > self.failed_retention:
                    queue.delete_job(job["job_id"])
                    deleted_failed += 1

        if deleted_failed > 0:
            logger.info(f"Deleted {deleted_failed} old failed jobs")

        # Task 4: Expire stale annealing proposals past their TTL
        try:
            conn = queue._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE kg_api.annealing_proposals
                        SET status = 'expired'
                        WHERE status = 'pending'
                          AND expires_at IS NOT NULL
                          AND expires_at < NOW()
                    """)
                    expired_proposals = cur.rowcount
                conn.commit()
                if expired_proposals > 0:
                    logger.info(f"Expired {expired_proposals} stale annealing proposals")
            finally:
                queue._return_connection(conn)
        except Exception as e:
            logger.debug(f"Proposal expiry check skipped: {e}")

    async def manual_cleanup(self) -> Dict[str, int]:
        """
        Trigger cleanup manually (for CLI/API endpoint).

        Returns:
            Statistics about cleanup operations:
            {
                "expired_cancelled": int,
                "completed_deleted": int,
                "failed_deleted": int
            }
        """
        from .job_queue import get_job_queue

        queue = get_job_queue()
        now = datetime.now(timezone.utc)

        stats = {
            "expired_cancelled": 0,
            "completed_deleted": 0,
            "failed_deleted": 0
        }

        # Cancel expired unapproved jobs
        for job in queue.list_jobs(status="awaiting_approval", limit=1000):
            created = datetime.fromisoformat(job["created_at"])
            age = now - created

            if age > self.approval_timeout:
                queue.update_job(job["job_id"], {
                    "status": "cancelled",
                    "error": f"Expired - not approved within {self.approval_timeout.total_seconds() / 3600:.0f} hours"
                })
                stats["expired_cancelled"] += 1

        # Delete old completed/cancelled jobs
        for status in ["completed", "cancelled"]:
            for job in queue.list_jobs(status=status, limit=1000):
                if job.get("completed_at"):
                    completed = datetime.fromisoformat(job["completed_at"])
                    age = now - completed

                    if age > self.completed_retention:
                        queue.delete_job(job["job_id"])
                        stats["completed_deleted"] += 1

        # Delete old failed jobs
        for job in queue.list_jobs(status="failed", limit=1000):
            if job.get("completed_at"):
                completed = datetime.fromisoformat(job["completed_at"])
                age = now - completed

                if age > self.failed_retention:
                    queue.delete_job(job["job_id"])
                    stats["failed_deleted"] += 1

        logger.info(
            f"Manual cleanup: cancelled {stats['expired_cancelled']}, "
            f"deleted {stats['completed_deleted']} completed/cancelled, "
            f"deleted {stats['failed_deleted']} failed"
        )

        return stats

    def get_stats(self) -> Dict[str, any]:
        """
        Get current scheduler statistics.

        Returns:
            Dictionary with job counts by status and cleanup info:
            {
                "jobs_by_status": {"pending": 2, "completed": 100, ...},
                "last_cleanup": None,  # Could track this with instance variable
                "next_cleanup": None   # Could calculate from cleanup_interval
            }
        """
        from .job_queue import get_job_queue

        queue = get_job_queue()

        # Get job counts by status
        jobs_by_status = {}
        for status in ["pending", "awaiting_approval", "approved", "queued", "processing", "completed", "failed", "cancelled"]:
            jobs = queue.list_jobs(status=status, limit=10000)
            count = len(jobs)
            if count > 0:
                jobs_by_status[status] = count

        return {
            "jobs_by_status": jobs_by_status,
            "last_cleanup": None,  # Future: track last cleanup timestamp
            "next_cleanup": None   # Future: calculate from cleanup_interval and last_cleanup
        }


# Singleton instance
_scheduler_instance: Optional[JobScheduler] = None


def init_job_scheduler(**kwargs) -> JobScheduler:
    """
    Initialize job scheduler with environment config.

    Environment variables:
        JOB_CLEANUP_INTERVAL - Seconds between cleanup runs (default: 3600)
        JOB_APPROVAL_TIMEOUT - Hours before cancelling unapproved (default: 24)
        JOB_COMPLETED_RETENTION - Hours to keep completed/cancelled (default: 48)
        JOB_FAILED_RETENTION - Hours to keep failed jobs (default: 168)

    Args:
        **kwargs: Override environment config with explicit values

    Returns:
        JobScheduler instance
    """
    global _scheduler_instance

    config = {
        "cleanup_interval": int(os.getenv("JOB_CLEANUP_INTERVAL", "3600")),
        "approval_timeout": int(os.getenv("JOB_APPROVAL_TIMEOUT", "24")),
        "completed_retention": int(os.getenv("JOB_COMPLETED_RETENTION", "48")),
        "failed_retention": int(os.getenv("JOB_FAILED_RETENTION", "168")),
    }
    config.update(kwargs)

    _scheduler_instance = JobScheduler(**config)
    return _scheduler_instance


def get_job_scheduler() -> JobScheduler:
    """
    Get the scheduler instance.

    Raises:
        RuntimeError: If scheduler not initialized
    """
    if _scheduler_instance is None:
        raise RuntimeError("Scheduler not initialized. Call init_job_scheduler() first.")
    return _scheduler_instance
