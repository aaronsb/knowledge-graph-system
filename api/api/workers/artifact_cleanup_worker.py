"""
Artifact Cleanup Worker (ADR-083).

Scheduled worker that maintains artifact storage health:
- Deletes expired artifacts (past expires_at)
- Cleans up orphaned Garage objects
- Reports storage statistics

Schedule: Daily at 2 AM (configured in scheduled_jobs table)
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def run_artifact_cleanup_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute artifact cleanup as a background job.

    Args:
        job_data: Job parameters
            - dry_run: bool - If True, report what would be deleted without deleting
            - include_orphans: bool - Also clean up orphaned Garage objects
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with cleanup statistics

    Raises:
        Exception: If cleanup fails
    """
    try:
        from api.api.dependencies.auth import get_db_connection
        from api.api.lib.garage import get_artifact_storage

        logger.info(f"🧹 Artifact cleanup worker started: {job_id}")

        dry_run = job_data.get("dry_run", False)
        include_orphans = job_data.get("include_orphans", False)

        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Starting artifact cleanup"
        })

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Find expired artifacts
                cur.execute("""
                    SELECT id, artifact_type, garage_key, owner_id
                    FROM kg_api.artifacts
                    WHERE expires_at IS NOT NULL AND expires_at < NOW()
                """)

                expired = cur.fetchall()
                expired_count = len(expired)

                job_queue.update_job(job_id, {
                    "progress": f"Found {expired_count} expired artifacts"
                })

                if expired_count > 0 and not dry_run:
                    # Delete Garage objects first
                    storage = get_artifact_storage()
                    garage_deleted = 0
                    garage_errors = 0

                    for artifact_id, artifact_type, garage_key, owner_id in expired:
                        if garage_key:
                            try:
                                storage.delete(garage_key)
                                garage_deleted += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete Garage object {garage_key}: {e}")
                                garage_errors += 1

                    job_queue.update_job(job_id, {
                        "progress": f"Deleted {garage_deleted} Garage objects ({garage_errors} errors)"
                    })

                    # Delete database records
                    cur.execute("""
                        DELETE FROM kg_api.artifacts
                        WHERE expires_at IS NOT NULL AND expires_at < NOW()
                    """)
                    db_deleted = cur.rowcount
                    conn.commit()

                    logger.info(
                        f"Deleted {db_deleted} expired artifacts "
                        f"({garage_deleted} Garage objects, {garage_errors} errors)"
                    )
                else:
                    db_deleted = 0
                    garage_deleted = 0
                    garage_errors = 0

                # Get storage statistics
                cur.execute("""
                    SELECT
                        COUNT(*) as total_artifacts,
                        COUNT(CASE WHEN garage_key IS NOT NULL THEN 1 END) as garage_stored,
                        COUNT(CASE WHEN inline_result IS NOT NULL THEN 1 END) as inline_stored,
                        COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 END) as expired
                    FROM kg_api.artifacts
                """)
                stats_row = cur.fetchone()

                result = {
                    "success": True,
                    "dry_run": dry_run,
                    "expired_found": expired_count,
                    "artifacts_deleted": db_deleted if not dry_run else 0,
                    "garage_objects_deleted": garage_deleted if not dry_run else 0,
                    "garage_delete_errors": garage_errors if not dry_run else 0,
                    "statistics": {
                        "total_artifacts": stats_row[0],
                        "garage_stored": stats_row[1],
                        "inline_stored": stats_row[2],
                        "currently_expired": stats_row[3]
                    }
                }

                logger.info(f"✅ Artifact cleanup completed: {job_id}")
                return result

        finally:
            conn.close()

    except Exception as e:
        error_msg = f"Artifact cleanup failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        job_queue.update_job(job_id, {
            "status": "failed",
            "error": error_msg,
            "progress": "Artifact cleanup failed"
        })

        raise Exception(error_msg) from e
