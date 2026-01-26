"""Job status and management routes"""

import asyncio
import json
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import timedelta
from api.app.lib.datetime_utils import utcnow, to_iso

from ..services.job_queue import get_job_queue
from ..models.job import JobStatus
from ..dependencies.auth import CurrentUser, get_current_active_user
from ..lib.job_permissions import JobPermissionContext

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    summary="Get job status"
)
async def get_job_status(
    job_id: str,
    current_user: CurrentUser
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

    **Authorization:**
    - Users can view their own jobs
    - Curators+ can view all user jobs
    - Platform admins can view system jobs
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Check permission to read this job
    with JobPermissionContext() as checker:
        if not checker.can_access_job(current_user.id, 'read', job):
            raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return JobStatus(**job)


@router.get(
    "",
    response_model=List[JobStatus],
    summary="List jobs"
)
async def list_jobs(
    current_user: CurrentUser,
    status: Optional[str] = Query(
        None,
        description="Filter by status (pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip (for pagination)")
):
    """
    List recent jobs, filtered by user's permissions.

    **Authorization:**
    - Contributors: See only their own jobs
    - Curators+: See all user jobs
    - Platform admins: See all jobs including system jobs

    Useful for:
    - Viewing jobs awaiting approval: `?status=awaiting_approval`
    - Monitoring queue backlog
    - Debugging failed jobs

    Examples:
    - `GET /jobs?status=awaiting_approval` - Jobs needing approval
    - `GET /jobs?status=completed&limit=100` - Last 100 completed jobs
    """
    queue = get_job_queue()

    # Get permission-based filter
    with JobPermissionContext() as checker:
        perm_filter = checker.get_job_list_filter(current_user.id)

    # Apply permission filter
    jobs = queue.list_jobs(
        status=status,
        user_id=perm_filter.get('user_id'),
        exclude_system=perm_filter.get('exclude_system', False),
        limit=limit,
        offset=offset
    )

    return [JobStatus(**job) for job in jobs]


@router.delete(
    "/{job_id}",
    summary="Cancel or delete a job"
)
async def cancel_or_delete_job(
    job_id: str,
    current_user: CurrentUser,
    purge: bool = Query(False, description="Permanently delete job record"),
    force: bool = Query(False, description="Force delete even if processing (dangerous)")
):
    """
    Cancel or permanently delete a job.

    **Default behavior (purge=false):** Cancel the job
    - Changes status to 'cancelled'
    - Job record remains in database

    **With purge=true:** Permanently delete job record
    - Removes job from database entirely
    - Cannot delete processing jobs unless force=true

    **Authorization:**
    - Users can cancel/delete their own jobs
    - Admins can cancel/delete any user job
    - Platform admins can cancel/delete system jobs

    **ADR-014: Can cancel jobs in these states:**
    - `pending`: Job queued, analysis running
    - `awaiting_approval`: Analysis complete, waiting for approval
    - `approved`: Approved but not yet started
    - `queued`: Legacy state

    **Cannot cancel/delete:**
    - `processing`: Job already running (unless force=true)
    - `completed`, `failed`, `cancelled`: Can delete but not cancel

    **Returns:**
    - 200: Job cancelled/deleted successfully
    - 403: Not authorized
    - 404: Job not found
    - 409: Job cannot be cancelled/deleted in current state
    """
    queue = get_job_queue()

    # Check job exists
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Check permission
    action = 'delete' if purge else 'cancel'
    with JobPermissionContext() as checker:
        if not checker.can_access_job(current_user.id, action, job):
            raise HTTPException(status_code=403, detail=f"Not authorized to {action} this job")

    if purge:
        # Permanently delete the job record
        deleted = queue.delete_job(job_id, force=force)

        if not deleted:
            if job['status'] in ('processing', 'running') and not force:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete job in status: {job['status']}. Use force=true to override."
                )
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        return {
            "job_id": job_id,
            "deleted": True,
            "message": "Job permanently deleted"
        }
    else:
        # Cancel the job (change status)
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
    current_user: CurrentUser
):
    """
    Approve a job for processing (ADR-014 approval workflow).

    **Workflow:**
    1. Job submitted → status: `pending` (analysis runs automatically)
    2. Analysis complete → status: `awaiting_approval` (check `analysis` field for costs)
    3. User approves → status: `approved` (this endpoint)
    4. Job starts → status: `processing`

    **Authorization:**
    - Users can approve their own jobs
    - Admins can approve any user job

    **Returns:**
    - 200: Job approved and queued for processing
    - 403: Not authorized
    - 404: Job not found
    - 409: Job not in awaiting_approval status
    """
    queue = get_job_queue()

    # Check job exists
    job = queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Check permission (approve maps to cancel action - manage the job)
    with JobPermissionContext() as checker:
        if not checker.can_access_job(current_user.id, 'cancel', job):
            raise HTTPException(status_code=403, detail="Not authorized to approve this job")

    # Validate state
    if job["status"] != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Job not awaiting approval (status: {job['status']})"
        )

    # Mark approved
    queue.update_job(job_id, {
        "status": "approved",
        "approved_at": to_iso(utcnow()),
        "approved_by": current_user.username
    })

    # Handle serial vs parallel processing
    processing_mode = job.get("processing_mode", "serial")
    if processing_mode == "serial":
        # Queue for serial execution (will run when no other serial job is active)
        background_tasks.add_task(queue.queue_serial_job, job_id)
    else:
        # Execute in parallel (immediate background task)
        # ADR-031: Use execute_job_async for non-blocking execution
        background_tasks.add_task(queue.execute_job_async, job_id)

    return {
        "job_id": job_id,
        "status": "approved",
        "message": f"Job approved and queued for {processing_mode} processing"
    }


@router.delete(
    "",
    summary="Delete jobs with filters"
)
async def delete_jobs(
    current_user: CurrentUser,
    confirm: bool = Query(False, description="Must set to true to confirm deletion"),
    dry_run: bool = Query(False, description="Preview what would be deleted without deleting"),
    status: Optional[str] = Query(None, description="Filter by status (pending|cancelled|completed|failed)"),
    system: bool = Query(False, description="Only delete system/scheduled jobs"),
    older_than: Optional[str] = Query(None, description="Delete jobs older than duration (1h|24h|7d|30d)"),
    job_type: Optional[str] = Query(None, description="Filter by job type")
):
    """
    Delete jobs matching filters.

    **Authorization:**
    - Admins can delete user jobs in bulk
    - Platform admins can delete system jobs
    - Requires `jobs:delete` permission with appropriate scope

    **Safety:**
    - Cannot delete jobs in `processing` or `running` status
    - Requires `confirm=true` to execute (unless dry_run=true)
    - Use `dry_run=true` to preview what would be deleted

    **Filters (all optional, combined with AND):**
    - `status`: pending, cancelled, completed, failed
    - `system=true`: Only system/scheduled jobs
    - `older_than`: 1h, 24h, 7d, 30d
    - `job_type`: ingestion, epistemic_remeasurement, etc.

    **Examples:**
    - Clean up stuck pending system jobs:
      `DELETE /jobs?status=pending&system=true&confirm=true`
    - Remove old completed jobs:
      `DELETE /jobs?status=completed&older_than=7d&confirm=true`
    - Preview before delete:
      `DELETE /jobs?status=pending&dry_run=true`
    - Delete all jobs (requires no filters + confirm):
      `DELETE /jobs?confirm=true`

    **Returns:**
    - dry_run=true: List of jobs that would be deleted
    - dry_run=false: Count of jobs deleted
    """
    # Check bulk delete permission
    with JobPermissionContext() as checker:
        if not checker.can_delete_in_bulk(current_user.id, include_system=system):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to perform bulk job deletion" +
                       (" (system jobs require platform_admin)" if system else "")
            )

    queue = get_job_queue()

    if dry_run:
        # Preview mode - show what would be deleted
        jobs = queue.preview_delete_jobs(
            status=status,
            system_only=system,
            older_than=older_than,
            job_type=job_type
        )
        return {
            "dry_run": True,
            "jobs_to_delete": len(jobs),
            "jobs": jobs,
            "message": f"Would delete {len(jobs)} job(s). Use confirm=true to execute."
        }

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete jobs (or use dry_run=true to preview)"
        )

    # Check if this is a "delete all" operation (no filters)
    has_filters = any([status, system, older_than, job_type])
    if not has_filters:
        # No filters = delete all (nuclear option, still supported)
        jobs_deleted = queue.clear_all_jobs()
        return {
            "success": True,
            "jobs_deleted": jobs_deleted,
            "message": f"Cleared {jobs_deleted} job(s) from database (all jobs)"
        }

    # Filtered deletion
    jobs_deleted = queue.delete_jobs(
        status=status,
        system_only=system,
        older_than=older_than,
        job_type=job_type
    )

    return {
        "success": True,
        "jobs_deleted": jobs_deleted,
        "filters": {
            "status": status,
            "system": system,
            "older_than": older_than,
            "job_type": job_type
        },
        "message": f"Deleted {jobs_deleted} job(s) matching filters"
    }


@router.get(
    "/{job_id}/stream",
    summary="Stream job progress (Server-Sent Events)"
)
async def stream_job_progress(
    job_id: str,
    current_user: CurrentUser
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

    **Authorization:**
    - Users can stream their own jobs
    - Curators+ can stream all user jobs
    - Platform admins can stream system jobs
    """
    queue = get_job_queue()

    # Check job exists and verify permission upfront
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

    # Check permission
    with JobPermissionContext() as checker:
        if not checker.can_access_job(current_user.id, 'read', job):
            async def forbidden_generator():
                yield f"event: error\ndata: {json.dumps({'error': 'Not authorized to view this job'})}\n\n"

            return StreamingResponse(
                forbidden_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

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
        last_keepalive = utcnow()

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
            now = utcnow()
            if (now - last_keepalive).total_seconds() >= 30:
                yield f"event: keepalive\ndata: {json.dumps({'timestamp': to_iso(now)})}\n\n"
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
