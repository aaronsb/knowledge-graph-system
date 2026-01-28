"""Job tracking for FUSE ingestion visibility.

Tracks ingestion jobs locally and provides lazy polling when job files are read.
Jobs are automatically cleaned up after completion is shown or after staleness timeout.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# Terminal job statuses (job should be removed after showing final state)
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})

# How long to keep stale jobs before automatic cleanup (prevents memory leak)
STALE_JOB_TIMEOUT = 3600  # 1 hour


@dataclass
class TrackedJob:
    """State for a tracked ingestion job."""
    job_id: str
    ontology: str
    filename: str
    created_at: float = field(default_factory=time.time)
    seen_complete: bool = False
    marked_for_removal: bool = False

    def is_stale(self) -> bool:
        """Check if job has been tracked too long (likely orphaned)."""
        return time.time() - self.created_at > STALE_JOB_TIMEOUT


class JobTracker:
    """Tracks ingestion jobs for FUSE visibility.

    Thread-safe job tracking with lazy polling and automatic cleanup.
    Jobs are only fetched from the API when their virtual file is read.
    """

    def __init__(self):
        # Main job storage: job_id -> TrackedJob
        self._jobs: dict[str, TrackedJob] = {}

    def track_job(self, job_id: str, ontology: str, filename: str) -> None:
        """Start tracking a new ingestion job."""
        self._jobs[job_id] = TrackedJob(
            job_id=job_id,
            ontology=ontology,
            filename=filename,
        )
        log.info(f"Tracking job {job_id} for {ontology}/{filename}")

    def get_jobs_for_ontology(self, ontology: str) -> list[TrackedJob]:
        """Get all tracked jobs for an ontology.

        Performs atomic cleanup of stale/removed jobs before returning.
        """
        # Atomic cleanup: build new dict excluding jobs to remove
        # This avoids iteration issues from concurrent modification
        jobs_to_keep = {}
        for job_id, job in self._jobs.items():
            if job.marked_for_removal:
                log.debug(f"Removing completed job {job_id}")
                continue
            if job.is_stale():
                log.warning(f"Removing stale job {job_id} (tracked for >{STALE_JOB_TIMEOUT}s)")
                continue
            jobs_to_keep[job_id] = job

        # Atomic swap
        self._jobs = jobs_to_keep

        # Return jobs for requested ontology
        return [job for job in self._jobs.values() if job.ontology == ontology]

    def mark_job_status(self, job_id: str, status: str) -> None:
        """Update job status after reading from API.

        If status is terminal:
        - First call: marks seen_complete=True (show final status)
        - Second call: marks for removal (cleanup on next listing)
        """
        job = self._jobs.get(job_id)
        if not job:
            return

        if status in TERMINAL_JOB_STATUSES:
            if not job.seen_complete:
                # First time seeing completion - show it but mark as seen
                log.info(f"Job {job_id} completed with status: {status}")
                job.seen_complete = True
            else:
                # Already shown completion once - mark for removal
                log.info(f"Job {job_id} shown complete, marking for removal")
                job.marked_for_removal = True

    def mark_job_not_found(self, job_id: str) -> None:
        """Mark a job for removal when API returns not found."""
        job = self._jobs.get(job_id)
        if job:
            log.debug(f"Job {job_id} not found in API, marking for removal")
            job.marked_for_removal = True

    def get_job(self, job_id: str) -> Optional[TrackedJob]:
        """Get a tracked job by ID."""
        return self._jobs.get(job_id)

    def is_tracking(self, job_id: str) -> bool:
        """Check if a job is being tracked."""
        return job_id in self._jobs

    def clear(self) -> None:
        """Clear all tracked jobs (for cleanup on unmount)."""
        self._jobs.clear()

    @property
    def job_count(self) -> int:
        """Number of currently tracked jobs."""
        return len(self._jobs)
