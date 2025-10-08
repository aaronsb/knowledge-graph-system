"""
Admin Routes

API endpoints for system administration:
- System status
- Database backup
- Database restore
- Database reset
"""

from fastapi import APIRouter, HTTPException, status
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

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.post("/backup", response_model=BackupResponse)
async def create_backup(request: BackupRequest):
    """
    Create a database backup

    Supports two modes:
    - **full**: Backup entire database (all ontologies)
    - **ontology**: Backup specific ontology (requires ontology_name)

    Backups are saved to the backups/ directory and include:
    - All concepts, sources, and instances
    - Full embeddings (1536-dim vectors)
    - All relationships
    - Integrity assessment

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
    service = AdminService()
    try:
        return await service.create_backup(
            backup_type=request.backup_type,
            ontology_name=request.ontology_name,
            output_filename=request.output_filename
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


@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(request: RestoreRequest):
    """
    Restore a database backup (REQUIRES AUTHENTICATION)

    ⚠️ **Potentially destructive operation** - requires username and password.

    Restores data from a backup file. Options:
    - **overwrite**: Whether to overwrite existing data (default: false)
    - **handle_external_deps**: How to handle external dependencies
      - `prune`: Remove dangling relationships (default)
      - `stitch`: Try to reconnect to existing concepts
      - `defer`: Leave broken (requires manual fix)

    The restore process includes:
    - Validation of backup file
    - Integrity assessment
    - Conflict resolution
    - External dependency handling

    **Authentication required**: Must provide username and password.
    (Currently placeholder - will be validated in Phase 2)

    Example:
    ```json
    {
        "username": "admin",
        "password": "your_password",
        "backup_file": "backups/full_backup_20251007.json",
        "overwrite": false,
        "handle_external_deps": "prune"
    }
    ```
    """
    # TODO: Phase 2 - Validate username/password against auth system
    # For now, just check they're provided
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username and password required for restore operation"
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
        return await service.restore_backup(
            backup_file=request.backup_file,
            overwrite=request.overwrite,
            handle_external_deps=request.handle_external_deps
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}"
        )


@router.post("/reset", response_model=ResetResponse)
async def reset_database(request: ResetRequest):
    """
    Reset database (DESTRUCTIVE - requires authentication)

    ⚠️ **DANGER**: This operation:
    - Stops all containers
    - Deletes the Neo4j database
    - Removes all data volumes
    - Restarts with a clean database
    - Re-initializes schema

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
