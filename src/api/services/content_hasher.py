"""
Content hashing service for deduplication.

Prevents re-ingesting the same document multiple times by hashing content
and checking against previously processed jobs.

ADR-051: Now checks graph (DocumentMeta nodes) as primary source of truth,
with jobs table as fallback for in-progress jobs.
"""

import hashlib
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class ContentHasher:
    """Hash content and check for duplicates"""

    def __init__(self, job_queue, age_client=None):
        """
        Args:
            job_queue: JobQueue instance for checking existing jobs
            age_client: AGEClient instance for checking graph (ADR-051)
        """
        self.job_queue = job_queue
        self.age_client = age_client

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
        Check if content already ingested into this ontology (ADR-051).

        Checks two sources:
        1. Graph (DocumentMeta nodes) - Primary source of truth (persistent)
        2. Jobs table - Fallback for in-progress jobs (ephemeral)

        This prevents job deletion from breaking deduplication.

        Args:
            content_hash: SHA-256 hash from hash_content()
            ontology: Target ontology name

        Returns:
            None: Not seen before, safe to proceed
            Dict: Existing job/document info with status/result
                  Format depends on source:
                  - From graph: {"source": "graph", "document_id": "...", ...}
                  - From jobs: {"source": "job", "job_id": "...", "status": "...", ...}
        """
        # ADR-051: Check graph first (persistent state)
        if self.age_client:
            try:
                doc_meta = self.age_client.get_document_meta(content_hash, ontology)
                if doc_meta:
                    logger.info(
                        f"✓ Duplicate found in graph: {doc_meta.get('filename', content_hash[:16])}..."
                    )
                    # Return in job-compatible format for existing code
                    return {
                        "source": "graph",
                        "job_id": doc_meta.get("job_id", "unknown"),
                        "status": "completed",
                        "created_at": doc_meta.get("ingested_at"),
                        "completed_at": doc_meta.get("ingested_at"),
                        "result": {
                            "document_id": doc_meta.get("document_id"),
                            "filename": doc_meta.get("filename"),
                            "source_type": doc_meta.get("source_type"),
                            "source_count": doc_meta.get("source_count")
                        }
                    }
            except Exception as e:
                logger.warning(f"Failed to check graph for duplicate: {e}")
                # Fall through to jobs table check

        # Fallback: Check jobs table (for in-progress jobs or if graph check failed)
        existing_job = self.job_queue.check_duplicate(content_hash, ontology)

        if existing_job:
            # Only return if job is actually in progress (not completed)
            # Completed jobs should have created DocumentMeta in graph
            status = existing_job.get("status")
            if status in ["running", "queued", "awaiting_approval", "approved"]:
                logger.info(
                    f"✓ Duplicate found in jobs table: {existing_job['job_id']} (status: {status})"
                )
                return {**existing_job, "source": "job"}

        # No duplicate found
        return None

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

            # Ensure completed_at is timezone-aware (handle both naive and aware datetimes)
            if completed_at.tzinfo is None:
                # Assume UTC if timezone-naive
                completed_at = completed_at.replace(tzinfo=timezone.utc)

            # Use timezone-aware datetime for comparison
            age = datetime.now(timezone.utc) - completed_at

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
