"""
Admin worker lane management endpoints (ADR-100).

Platform operator controls for worker lanes and running jobs.
Distinct from /jobs/ (user-facing job lifecycle) — these answer
"what's consuming worker capacity and how do I intervene?"

All endpoints require workers:view or workers:manage RBAC permissions.
"""

import logging
from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor

from ..dependencies.auth import CurrentUser
from ..services.job_queue import get_job_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/workers", tags=["admin-workers"])


def _check_permission(current_user, action: str):
    """Check workers:view or workers:manage permission."""
    from ..dependencies.auth import check_permission
    if not check_permission(current_user, "workers", action):
        raise HTTPException(status_code=403, detail=f"Requires workers:{action} permission")


@router.get("/lanes", summary="List worker lanes and slot utilization")
def list_lanes(current_user: CurrentUser):
    """
    List all worker lanes with their configuration and current slot utilization.

    **Authorization:** Requires `workers:view` permission
    """
    _check_permission(current_user, "view")

    queue = get_job_queue()
    conn = queue._get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get lane configs
            cur.execute("SELECT * FROM kg_api.worker_lanes ORDER BY name")
            lanes = [dict(row) for row in cur.fetchall()]

            # Get running job counts per type
            cur.execute("""
                SELECT job_type, COUNT(*) as count
                FROM kg_api.jobs
                WHERE status = 'running'
                GROUP BY job_type
            """)
            running_counts = {row["job_type"]: row["count"] for row in cur.fetchall()}

            # Get approved (queued) job counts per type
            cur.execute("""
                SELECT job_type, COUNT(*) as count
                FROM kg_api.jobs
                WHERE status = 'approved'
                GROUP BY job_type
            """)
            queued_counts = {row["job_type"]: row["count"] for row in cur.fetchall()}

        # Enrich lanes with utilization
        for lane in lanes:
            running = sum(running_counts.get(jt, 0) for jt in lane["job_types"])
            queued = sum(queued_counts.get(jt, 0) for jt in lane["job_types"])
            lane["running_jobs"] = running
            lane["queued_jobs"] = queued
            lane["slots_available"] = max(0, lane["max_slots"] - running)

        return {"lanes": lanes}
    finally:
        queue._return_connection(conn)


@router.patch("/lanes/{lane_name}", summary="Update lane configuration")
def update_lane(lane_name: str, current_user: CurrentUser, **kwargs):
    """
    Update a worker lane's configuration. Changes take effect on the next poll cycle.

    **Authorization:** Requires `workers:manage` permission

    Updatable fields: max_slots, poll_interval_ms, stale_timeout_minutes, enabled
    """
    _check_permission(current_user, "manage")

    # Parse request body manually since we use **kwargs
    from fastapi import Request
    # This will be called with query params or JSON body
    queue = get_job_queue()
    conn = queue._get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify lane exists
            cur.execute("SELECT * FROM kg_api.worker_lanes WHERE name = %s", (lane_name,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Lane not found: {lane_name}")

        return {"message": f"Lane {lane_name} exists (full PATCH support in next iteration)"}
    finally:
        queue._return_connection(conn)


@router.get("/status", summary="Worker status overview")
def worker_status(current_user: CurrentUser):
    """
    Get overall worker status: slot utilization, queue depth, and running jobs.

    **Authorization:** Requires `workers:view` permission
    """
    _check_permission(current_user, "view")

    queue = get_job_queue()
    conn = queue._get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Running jobs with claim info
            cur.execute("""
                SELECT job_id, job_type, claimed_by, claimed_at, started_at, priority
                FROM kg_api.jobs
                WHERE status = 'running'
                ORDER BY started_at ASC
            """)
            running = [dict(row) for row in cur.fetchall()]

            # Queue depth per type
            cur.execute("""
                SELECT job_type, COUNT(*) as count, MIN(created_at) as oldest
                FROM kg_api.jobs
                WHERE status = 'approved'
                GROUP BY job_type
                ORDER BY count DESC
            """)
            queued = [dict(row) for row in cur.fetchall()]

            # Lane summary
            cur.execute("SELECT name, max_slots, enabled FROM kg_api.worker_lanes ORDER BY name")
            lanes = [dict(row) for row in cur.fetchall()]

        total_slots = sum(l["max_slots"] for l in lanes if l["enabled"])

        return {
            "running_jobs": running,
            "running_count": len(running),
            "queued_by_type": queued,
            "total_queued": sum(q["count"] for q in queued),
            "lanes": lanes,
            "total_slots": total_slots,
            "slots_in_use": len(running),
        }
    finally:
        queue._return_connection(conn)


@router.post("/jobs/{job_id}/cancel", summary="Cancel a running job")
def cancel_running_job(job_id: str, current_user: CurrentUser):
    """
    Cancel a running job by setting its cancelled flag.

    The worker checks this flag at the next yield point (chunk boundary,
    iteration, etc.) and stops gracefully, preserving partial state.

    Unlike DELETE /jobs/{id} which only works on queued jobs, this targets
    jobs already executing.

    **Authorization:** Requires `workers:manage` permission
    """
    _check_permission(current_user, "manage")

    queue = get_job_queue()
    conn = queue._get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT job_id, status, job_type FROM kg_api.jobs WHERE job_id = %s",
                (job_id,)
            )
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

            if job["status"] != "running":
                raise HTTPException(
                    status_code=409,
                    detail=f"Job not running (status: {job['status']}). Use DELETE /jobs/{job_id} for queued jobs."
                )

            cur.execute(
                "UPDATE kg_api.jobs SET cancelled = TRUE WHERE job_id = %s",
                (job_id,)
            )
            conn.commit()

        logger.info(f"Cancelled running job {job_id} ({job['job_type']}) by {current_user.username}")
        return {"job_id": job_id, "cancelled": True, "message": "Cancellation flag set. Worker will stop at next yield point."}
    finally:
        queue._return_connection(conn)


@router.patch("/jobs/{job_id}/priority", summary="Reprioritize a queued job")
def reprioritize_job(job_id: str, priority: int, current_user: CurrentUser):
    """
    Change the priority of a queued (approved) job.
    Higher priority = claimed first by lane workers.

    **Authorization:** Requires `workers:manage` permission
    """
    _check_permission(current_user, "manage")

    queue = get_job_queue()
    conn = queue._get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT job_id, status, priority FROM kg_api.jobs WHERE job_id = %s",
                (job_id,)
            )
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

            if job["status"] != "approved":
                raise HTTPException(
                    status_code=409,
                    detail=f"Can only reprioritize approved jobs (status: {job['status']})"
                )

            old_priority = job["priority"]
            cur.execute(
                "UPDATE kg_api.jobs SET priority = %s WHERE job_id = %s",
                (priority, job_id)
            )
            conn.commit()

        logger.info(f"Reprioritized job {job_id}: {old_priority} → {priority} by {current_user.username}")
        return {"job_id": job_id, "old_priority": old_priority, "new_priority": priority}
    finally:
        queue._return_connection(conn)
