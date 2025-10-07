"""Job status and management routes"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List

from ..services.job_queue import get_job_queue
from ..models.job import JobStatus
from ..middleware.auth import get_current_user, verify_job_ownership

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    summary="Get job status"
)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    Get the current status of a job.

    **Job States:**
    - `queued`: Job is waiting to be processed
    - `processing`: Job is currently running
    - `completed`: Job finished successfully (see result field)
    - `failed`: Job failed (see error field)
    - `cancelled`: Job was cancelled

    **Polling Recommendations:**
    - Poll every 2-5 seconds while status is "queued" or "processing"
    - Stop polling when status is "completed", "failed", or "cancelled"
    - Use the `progress.percent` field to show progress bar
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Verify ownership (Phase 1: no-op, Phase 2: enforced)
    await verify_job_ownership(job_id, job, current_user)

    return JobStatus(**job)


@router.get(
    "",
    response_model=List[JobStatus],
    summary="List jobs"
)
async def list_jobs(
    status: Optional[str] = Query(
        None,
        description="Filter by status (queued|processing|completed|failed|cancelled)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum jobs to return"),
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    List recent jobs, optionally filtered by status.

    Useful for:
    - Viewing job history
    - Monitoring queue backlog
    - Debugging failed jobs
    """
    queue = get_job_queue()
    jobs = queue.list_jobs(status=status, limit=limit)

    # Phase 2: Filter by current_user.client_id
    # For now, return all jobs (no filtering)

    return [JobStatus(**job) for job in jobs]


@router.delete(
    "/{job_id}",
    summary="Cancel a job"
)
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    Cancel a queued job.

    **Limitations (Phase 1):**
    - Can only cancel jobs in "queued" status
    - Cannot cancel running jobs (will be added in Phase 2)

    **Returns:**
    - 200: Job cancelled successfully
    - 404: Job not found
    - 409: Job cannot be cancelled (already processing or completed)
    """
    queue = get_job_queue()

    # Check job exists
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Verify ownership (Phase 1: no-op, Phase 2: enforced)
    await verify_job_ownership(job_id, job, current_user)

    # Attempt cancellation
    cancelled = queue.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job in status: {job['status']}"
        )

    return {
        "job_id": job_id,
        "cancelled": True,
        "message": "Job cancelled successfully"
    }
