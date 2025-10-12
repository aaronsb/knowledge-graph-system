"""
Content hashing service for deduplication.

Prevents re-ingesting the same document multiple times by hashing content
and checking against previously processed jobs.
"""

import hashlib
from typing import Optional, Dict
from datetime import datetime, timedelta


class ContentHasher:
    """Hash content and check for duplicates"""

    def __init__(self, job_queue):
        """
        Args:
            job_queue: JobQueue instance for checking existing jobs
        """
        self.job_queue = job_queue

    def hash_content(self, content: bytes) -> str:
        """
        Generate SHA-256 hash of content.

        Args:
            content: Raw document bytes

        Returns:
            Hash string in format "sha256:abc123..."
        """
        hash_hex = hashlib.sha256(content).hexdigest()
        return f"sha256:{hash_hex}"

    def check_duplicate(
        self,
        content_hash: str,
        ontology: str
    ) -> Optional[Dict]:
        """
        Check if content already ingested into this ontology.

        Args:
            content_hash: SHA-256 hash from hash_content()
            ontology: Target ontology name

        Returns:
            None: Not seen before, safe to proceed
            Dict: Existing job info with status/result
        """
        # Delegate to job queue's check_duplicate method
        # (works for both InMemory and PostgreSQL queues)
        return self.job_queue.check_duplicate(content_hash, ontology)

    def should_allow_reingestion(
        self,
        existing_job: Optional[Dict],
        force: bool = False
    ) -> tuple[bool, str]:
        """
        Determine if re-ingestion should be allowed.

        Args:
            existing_job: Result from check_duplicate()
            force: User override flag

        Returns:
            (allowed: bool, reason: str)
        """
        if not existing_job:
            return (True, "No previous ingestion found")

        if force:
            return (True, "Force flag set, allowing re-ingestion")

        status = existing_job["status"]

        if status == "failed":
            return (True, "Previous ingestion failed, allowing retry")

        if status == "processing":
            return (
                False,
                f"Already processing (job {existing_job['job_id']})"
            )

        if status == "queued":
            return (
                False,
                f"Already queued (job {existing_job['job_id']})"
            )

        if status == "completed":
            # Check age - allow re-ingestion if > 30 days old
            completed_at = datetime.fromisoformat(existing_job["completed_at"])
            age = datetime.now() - completed_at

            if age > timedelta(days=30):
                return (
                    True,
                    f"Previous ingestion from {age.days} days ago, allowing update"
                )

            return (
                False,
                f"Recently completed (job {existing_job['job_id']})"
            )

        return (False, f"Unknown status: {status}")

    def get_duplicate_info(self, existing_job: Dict) -> Dict:
        """
        Format duplicate job info for API response.

        Args:
            existing_job: Job dict from check_duplicate()

        Returns:
            Formatted response dict
        """
        return {
            "duplicate": True,
            "existing_job_id": existing_job["job_id"],
            "status": existing_job["status"],
            "created_at": existing_job["created_at"],
            "completed_at": existing_job.get("completed_at"),
            "result": existing_job.get("result"),
            "message": self._get_duplicate_message(existing_job)
        }

    def _get_duplicate_message(self, job: Dict) -> str:
        """Generate helpful message for duplicate detection"""
        status = job["status"]

        if status == "completed":
            return (
                f"This document was already ingested (job {job['job_id']}). "
                f"Use force=true to re-ingest."
            )
        elif status == "processing":
            return (
                f"This document is currently being processed (job {job['job_id']}). "
                f"Check job status for progress."
            )
        elif status == "queued":
            return (
                f"This document is queued for ingestion (job {job['job_id']}). "
                f"It will be processed soon."
            )
        else:
            return f"Document matches existing job {job['job_id']} with status: {status}"
