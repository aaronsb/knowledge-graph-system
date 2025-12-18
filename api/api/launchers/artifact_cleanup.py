"""
Artifact Cleanup Launcher (ADR-083).

Scheduled launcher that triggers cleanup of expired artifacts.
Runs daily to maintain storage health.
"""

import logging
from typing import Optional
from datetime import datetime

from .base import JobLauncher

logger = logging.getLogger(__name__)


class ArtifactCleanupLauncher(JobLauncher):
    """
    Launcher for artifact cleanup jobs.

    Checks if there are expired artifacts and triggers cleanup.
    Runs daily at 2 AM by default (configured in scheduled_jobs table).
    """

    def check_conditions(self) -> bool:
        """
        Check if there are expired artifacts to clean up.

        Returns True if any artifacts have passed their expires_at date.
        """
        from api.api.dependencies.auth import get_db_connection

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM kg_api.artifacts
                    WHERE expires_at IS NOT NULL AND expires_at < NOW()
                """)
                expired_count = cur.fetchone()[0]

                if expired_count > 0:
                    logger.info(f"Artifact cleanup: {expired_count} expired artifacts to clean")
                    return True
                else:
                    logger.debug("Artifact cleanup: No expired artifacts")
                    return False
        finally:
            conn.close()

    def prepare_job_data(self) -> dict:
        """
        Prepare job data for the cleanup worker.
        """
        return {
            "dry_run": False,
            "include_orphans": False,  # Future enhancement
            "description": f"Scheduled artifact cleanup ({datetime.utcnow().isoformat()})"
        }

    def launch(self) -> Optional[str]:
        """
        Check conditions and enqueue cleanup job if needed.

        Returns:
            job_id if job enqueued, None if skipped
        """
        if not self.check_conditions():
            return None

        job_data = self.prepare_job_data()

        job_id = self.job_queue.enqueue(
            job_type="artifact_cleanup",
            job_data=job_data
        )

        # Auto-approve (no cost, maintenance job)
        self.job_queue.update_job(job_id, {
            "status": "approved",
            "approved_at": datetime.utcnow().isoformat(),
            "approved_by": "system"
        })

        logger.info(f"Artifact cleanup job enqueued: {job_id}")
        return job_id
