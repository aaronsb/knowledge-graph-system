"""Job status and management routes"""

import asyncio
import json
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime, timedelta

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

    **Job States (ADR-014):**
    - `pending`: Job queued, analysis running (fast)
    - `awaiting_approval`: Analysis complete, needs user approval
    - `approved`: User approved, waiting for processor
    - `queued`: Legacy state (same as approved)
    - `processing`: Job is currently running
    - `completed`: Job finished successfully (see result field)
    - `failed`: Job failed (see error field)
    - `cancelled`: Job was cancelled or expired

    **Polling Recommendations:**
    - Poll every 2-5 seconds while status is "pending", "approved", "queued", or "processing"
    - Check `analysis` field when status is "awaiting_approval" to see cost estimates
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
        description="Filter by status (pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled)"
    ),
    client_id: Optional[str] = Query(
        None,
        description="Filter by client ID (ADR-014: view specific user's jobs)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum jobs to return"),
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    List recent jobs, optionally filtered by status and/or client_id.

    Useful for:
    - Viewing jobs awaiting approval: `?status=awaiting_approval`
    - Viewing your own jobs: `?client_id=your-client-id`
    - Viewing another user's jobs: `?client_id=other-user`
    - Monitoring queue backlog
    - Debugging failed jobs

    Examples:
    - `GET /jobs?status=awaiting_approval` - Jobs needing approval
    - `GET /jobs?client_id=alice&status=awaiting_approval` - Alice's pending jobs
    - `GET /jobs?status=completed&limit=100` - Last 100 completed jobs
    """
    queue = get_job_queue()
    jobs = queue.list_jobs(status=status, client_id=client_id, limit=limit)

    # Phase 2: Enforce ownership filtering based on current_user.client_id
    # For now, allow viewing all jobs (no filtering enforcement)

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
    Cancel a job before it starts processing.

    **ADR-014: Can cancel jobs in these states:**
    - `pending`: Job queued, analysis running
    - `awaiting_approval`: Analysis complete, waiting for approval
    - `approved`: Approved but not yet started
    - `queued`: Legacy state

    **Cannot cancel:**
    - `processing`: Job already running
    - `completed`, `failed`, `cancelled`: Already finished

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


@router.post(
    "/{job_id}/approve",
    summary="Approve a job for processing"
)
async def approve_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    Approve a job for processing (ADR-014 approval workflow).

    **Workflow:**
    1. Job submitted → status: `pending` (analysis runs automatically)
    2. Analysis complete → status: `awaiting_approval` (check `analysis` field for costs)
    3. User approves → status: `approved` (this endpoint)
    4. Job starts → status: `processing`

    **Requirements:**
    - Job must be in `awaiting_approval` status
    - User must have permission (Phase 2: enforced, Phase 1: placeholder)

    **Returns:**
    - 200: Job approved and queued for processing
    - 404: Job not found
    - 409: Job not in awaiting_approval status
    """
    queue = get_job_queue()

    # Check job exists
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Verify ownership (Phase 1: no-op, Phase 2: enforced)
    await verify_job_ownership(job_id, job, current_user)

    # Validate state
    if job["status"] != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Job not awaiting approval (status: {job['status']})"
        )

    # Mark approved
    queue.update_job(job_id, {
        "status": "approved",
        "approved_at": datetime.now().isoformat(),
        "approved_by": current_user.get("user_id", "anonymous")  # Phase 2: real user ID
    })

    # Add to processing queue
    background_tasks.add_task(queue.execute_job, job_id)

    return {
        "job_id": job_id,
        "status": "approved",
        "message": "Job approved and queued for processing"
    }


@router.get(
    "/{job_id}/stream",
    summary="Stream job progress (Server-Sent Events)"
)
async def stream_job_progress(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Stream real-time job progress updates via Server-Sent Events (ADR-018).

    **Events sent:**
    - `progress`: Job progress updates (stage, percent, items)
    - `completed`: Job completed successfully
    - `failed`: Job failed with error
    - `error`: Job not found or access denied
    - `keepalive`: Connection keepalive (every 30s)

    **SSE Format:**
    ```
    event: progress
    data: {"stage": "restoring_concepts", "percent": 45, "items_processed": 512}

    event: completed
    data: {"restore_stats": {...}}
    ```

    **Auto-closes stream** when job reaches terminal state (completed/failed/cancelled).

    **Polling Fallback**: If SSE fails, client should fall back to `GET /jobs/{job_id}`

    **Connection:** Uses HTTP/1.1 chunked transfer encoding. Works through most proxies.
    """
    queue = get_job_queue()

    # Check job exists and verify ownership upfront
    job = queue.get_job(job_id)
    if not job:
        # Send error event and close
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Verify ownership (Phase 1: no-op, Phase 2: enforced)
    await verify_job_ownership(job_id, job, current_user)

    async def event_generator():
        """
        Generator that streams job progress events.

        Implements ADR-018 Phase 1: Core SSE Infrastructure
        - Polls job queue every 500ms
        - Sends progress events when state changes
        - Sends terminal events (completed/failed)
        - Auto-closes on terminal state
        """
        last_progress = None
        last_keepalive = datetime.now()

        while True:
            job = queue.get_job(job_id)

            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job disappeared'})}\n\n"
                break

            # Send progress if changed
            current_progress = job.get('progress')
            if current_progress and current_progress != last_progress:
                yield f"event: progress\ndata: {json.dumps(current_progress)}\n\n"
                last_progress = current_progress

            # Send terminal events
            if job['status'] == 'completed':
                result = job.get('result', {})
                yield f"event: completed\ndata: {json.dumps(result)}\n\n"
                break
            elif job['status'] == 'failed':
                error = job.get('error', 'Unknown error')
                yield f"event: failed\ndata: {json.dumps({'error': error})}\n\n"
                break
            elif job['status'] == 'cancelled':
                yield f"event: cancelled\ndata: {json.dumps({'message': 'Job was cancelled'})}\n\n"
                break

            # Send keepalive every 30 seconds to prevent timeout
            now = datetime.now()
            if (now - last_keepalive).total_seconds() >= 30:
                yield f"event: keepalive\ndata: {json.dumps({'timestamp': now.isoformat()})}\n\n"
                last_keepalive = now

            # Poll interval: 500ms for sub-second updates
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
