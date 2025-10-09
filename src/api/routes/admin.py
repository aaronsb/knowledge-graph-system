"""
Admin Routes

API endpoints for system administration:
- System status
- Database backup
- Database restore (ADR-015 Phase 2: Multipart Upload)
- Database reset
- Job scheduler management (ADR-014)
"""

import uuid
import shutil
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional

from ..models.admin import (
    SystemStatusResponse,
    BackupRequest,
    BackupResponse,
    ListBackupsResponse,
    RestoreRequest,
    RestoreResponse,
    ResetRequest,
    ResetResponse,
)
from ..services.admin_service import AdminService
from ..services.job_scheduler import get_job_scheduler
from ..services.job_queue import get_job_queue
from ..lib.backup_streaming import create_backup_stream
from ..lib.backup_integrity import check_backup_integrity
from ..lib.age_client import AGEClient

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """
    Get complete system status

    Returns status of:
    - Docker containers
    - Database connection
    - Database statistics
    - Python environment
    - Configuration
    """
    service = AdminService()
    try:
        return await service.get_system_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/backups", response_model=ListBackupsResponse)
async def list_backups():
    """
    List all available backup files

    Returns list of backup files with metadata (size, created date, etc.)
    """
    service = AdminService()
    try:
        return await service.list_backups()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}"
        )


@router.post("/backup")
async def create_backup(request: BackupRequest):
    """
    Create a database backup (ADR-015 Phase 2: Streaming Download)

    **Streams backup directly to client** - no server-side storage.
    Client saves to configured backup directory (~/.local/share/kg/backups).

    Supports two modes:
    - **full**: Backup entire database (all ontologies)
    - **ontology**: Backup specific ontology (requires ontology_name)

    Backup includes:
    - All concepts, sources, and instances
    - Full embeddings (1536-dim vectors)
    - All relationships
    - Metadata and statistics

    Returns streaming JSON response with Content-Disposition header.

    Example:
    ```json
    {
        "backup_type": "full"
    }
    ```

    Or for ontology-specific:
    ```json
    {
        "backup_type": "ontology",
        "ontology_name": "My Ontology"
    }
    ```
    """
    try:
        # Get AGE client
        client = AGEClient()

        # Create streaming backup
        stream, filename = await create_backup_stream(
            client=client,
            backup_type=request.backup_type,
            ontology_name=request.ontology_name
        )

        # Return streaming response
        return StreamingResponse(
            stream,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Backup-Type": request.backup_type,
                "X-Ontology-Name": request.ontology_name or "all"
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup failed: {str(e)}"
        )


@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(..., description="Backup JSON file to restore"),
    username: str = Form(..., description="Username for authentication"),
    password: str = Form(..., description="Password for authentication"),
    overwrite: bool = Form(False, description="Overwrite existing data"),
    handle_external_deps: str = Form("prune", description="How to handle external dependencies: 'prune', 'stitch', or 'defer'")
):
    """
    Restore a database backup (ADR-015 Phase 2: Multipart Upload)

    ⚠️ **Potentially destructive operation** - requires username and password.

    **Multipart Upload**: Client streams backup file to server.
    Server validates, then queues restore job for background processing.

    Restore options:
    - **overwrite**: Whether to overwrite existing data (default: false)
    - **handle_external_deps**: How to handle external dependencies
      - `prune`: Remove dangling relationships (default)
      - `stitch`: Try to reconnect to existing concepts
      - `defer`: Leave broken (requires manual fix)

    The restore process includes:
    1. Save uploaded file to temp location
    2. Run integrity checks (format, references, statistics)
    3. Queue restore worker with job ID
    4. Return job ID for progress tracking

    **Authentication required**: Must provide username and password.
    (Currently placeholder - will be validated in production)

    Returns job_id for polling restore progress via /jobs/{job_id}

    Example (multipart/form-data):
    ```
    file: <backup_file.json>
    username: admin
    password: your_password
    overwrite: false
    handle_external_deps: prune
    ```
    """
    # Validate authentication
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username and password required for restore operation"
        )

    # Placeholder auth check (will be replaced with real auth in production)
    if len(password) < 4:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Validate file type
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup file must be JSON format (.json extension)"
        )

    # Generate temp file path
    temp_file_id = uuid.uuid4()
    temp_path = Path(tempfile.gettempdir()) / f"restore_{temp_file_id}.json"

    try:
        # Save uploaded file to temp location
        logger.info(f"Saving uploaded backup to {temp_path}")
        with open(temp_path, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Run integrity checks
        logger.info(f"Running integrity checks on {temp_path}")
        integrity = check_backup_integrity(str(temp_path))

        if not integrity.valid:
            # Cleanup temp file
            temp_path.unlink()

            # Collect error details
            error_details = [f"{e.category}: {e.message}" for e in integrity.errors]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Backup integrity check failed: {'; '.join(error_details)}"
            )

        # Log warnings if present
        if integrity.warnings:
            for warning in integrity.warnings:
                logger.warning(f"Backup validation warning - {warning.category}: {warning.message}")

        # Log successful validation
        stats = integrity.statistics or {}
        logger.info(
            f"Backup validated successfully - "
            f"Concepts: {stats.get('concepts', 0)}, "
            f"Sources: {stats.get('sources', 0)}, "
            f"Instances: {stats.get('instances', 0)}, "
            f"Relationships: {stats.get('relationships', 0)}"
        )

        # Queue restore job
        job_queue = get_job_queue()
        if job_queue is None:
            # Cleanup temp file
            temp_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job queue not available"
            )

        # Create restore job
        job_id = job_queue.create_job(
            job_type="restore",
            job_data={
                "temp_file": str(temp_path),
                "temp_file_id": str(temp_file_id),
                "overwrite": overwrite,
                "handle_external_deps": handle_external_deps,
                "backup_stats": stats,
                "integrity_warnings": len(integrity.warnings)
            }
        )

        logger.info(f"Created restore job {job_id} for temp file {temp_path}")

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Restore job queued for processing",
            "backup_stats": stats,
            "integrity_warnings": len(integrity.warnings)
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Cleanup temp file on error
        if temp_path.exists():
            temp_path.unlink()

        logger.error(f"Restore upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore upload failed: {str(e)}"
        )


@router.post("/reset", response_model=ResetResponse)
async def reset_database(request: ResetRequest):
    """
    Reset database (DESTRUCTIVE - requires authentication)

    ⚠️ **DANGER**: This operation:
    - Stops all containers
    - Deletes the PostgreSQL database
    - Removes all data volumes
    - Restarts with a clean database
    - Re-initializes AGE schema

    **Authentication required**: Must provide username and password.
    (Currently placeholder - will be validated in Phase 2)

    Must set `confirm: true` to proceed.

    Optional:
    - `clear_logs`: Clear log files (default: true)
    - `clear_checkpoints`: Clear checkpoint files (default: true)

    Example:
    ```json
    {
        "username": "admin",
        "password": "your_password",
        "confirm": true,
        "clear_logs": true,
        "clear_checkpoints": true
    }
    ```

    Returns schema validation results after reset.
    """
    # Validate confirmation
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must set 'confirm: true' to reset database"
        )

    # TODO: Phase 2 - Validate username/password against auth system
    # For now, just check they're provided
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username and password required for reset operation"
        )

    # Placeholder auth check
    # In Phase 2, this will validate against real auth system
    if len(request.password) < 4:  # Minimal validation
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    service = AdminService()
    try:
        return await service.reset_database(
            clear_logs=request.clear_logs,
            clear_checkpoints=request.clear_checkpoints
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset failed: {str(e)}"
        )


# ========== Job Scheduler Endpoints (ADR-014) ==========

@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get job scheduler status and statistics (ADR-014)

    Returns current scheduler configuration and statistics:
    - Running status
    - Configuration (cleanup interval, retention periods)
    - Job counts by status
    - Last cleanup time
    - Next scheduled cleanup

    Example response:
    ```json
    {
        "running": true,
        "config": {
            "cleanup_interval": 3600,
            "approval_timeout": 24,
            "completed_retention": 48,
            "failed_retention": 168
        },
        "stats": {
            "jobs_by_status": {
                "pending": 2,
                "awaiting_approval": 5,
                "approved": 1,
                "completed": 100
            },
            "last_cleanup": "2025-10-07T10:30:00",
            "next_cleanup": "2025-10-07T11:30:00"
        }
    }
    ```
    """
    scheduler = get_job_scheduler()

    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job scheduler not initialized"
        )

    stats = scheduler.get_stats()

    return {
        "running": scheduler.running,
        "config": {
            "cleanup_interval": scheduler.cleanup_interval,
            "approval_timeout": scheduler.approval_timeout,
            "completed_retention": scheduler.completed_retention,
            "failed_retention": scheduler.failed_retention,
        },
        "stats": stats
    }


@router.post("/scheduler/cleanup")
async def trigger_scheduler_cleanup():
    """
    Manually trigger job scheduler cleanup (ADR-014)

    Forces an immediate cleanup cycle:
    - Cancels unapproved jobs older than approval_timeout
    - Deletes old completed/cancelled jobs
    - Deletes old failed jobs

    Useful for:
    - Testing scheduler behavior
    - Emergency cleanup
    - Manual intervention

    Returns cleanup results showing what was processed.

    Example response:
    ```json
    {
        "success": true,
        "message": "Cleanup completed",
        "processed": {
            "expired_jobs_cancelled": 3,
            "completed_jobs_deleted": 15,
            "failed_jobs_deleted": 2
        }
    }
    ```
    """
    scheduler = get_job_scheduler()

    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job scheduler not initialized"
        )

    if not scheduler.running:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job scheduler not running"
        )

    try:
        # Manually trigger cleanup
        await scheduler.cleanup_jobs()

        return {
            "success": True,
            "message": "Cleanup completed successfully",
            "note": "Check scheduler stats for detailed counts"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}"
        )
