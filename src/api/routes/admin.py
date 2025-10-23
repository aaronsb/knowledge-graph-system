"""
Admin Routes

API endpoints for system administration:
- System status
- Database backup
- Database restore (ADR-015 Phase 2: Multipart Upload)
- Database reset
- Job scheduler management (ADR-014)
- API key management (ADR-031)
"""

import uuid
import shutil
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, BackgroundTasks
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
from ..lib.encrypted_keys import EncryptedKeyStore
from ..constants import API_KEY_PROVIDERS

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

    Supports two formats:
    - **json**: Native format (default) - includes all data, restorable
    - **gexf**: Gephi visualization format - graph structure only, NOT restorable

    JSON backup includes:
    - All concepts, sources, and instances
    - Full embeddings (1536-dim vectors)
    - All relationships
    - Metadata and statistics

    GEXF export includes:
    - Concepts as nodes (with ontology, search terms, instance count)
    - Relationships as edges (with type, category, confidence)
    - Visual properties (colors by ontology, sizes, edge thickness)
    - Compatible with Gephi for immediate visualization

    Returns streaming response with Content-Disposition header.

    Example (JSON):
    ```json
    {
        "backup_type": "full",
        "format": "json"
    }
    ```

    Example (GEXF for Gephi):
    ```json
    {
        "backup_type": "ontology",
        "ontology_name": "TBM Model",
        "format": "gexf"
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
            ontology_name=request.ontology_name,
            format=request.format
        )

        # Determine media type based on format
        media_type = "application/gexf+xml" if request.format == "gexf" else "application/json"

        # Return streaming response
        return StreamingResponse(
            stream,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Backup-Type": request.backup_type,
                "X-Ontology-Name": request.ontology_name or "all",
                "X-Export-Format": request.format
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
    background_tasks: BackgroundTasks,
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
        # Note: System jobs (restore, backup, reset) use special "_system" ontology
        # since they operate on the entire database rather than a specific ontology
        job_id = job_queue.enqueue(
            job_type="restore",
            job_data={
                "ontology": "_system",  # System-level operation
                "temp_file": str(temp_path),
                "temp_file_id": str(temp_file_id),
                "overwrite": overwrite,
                "handle_external_deps": handle_external_deps,
                "backup_stats": stats,
                "integrity_warnings": len(integrity.warnings)
            }
        )

        logger.info(f"Created restore job {job_id} for temp file {temp_path}")

        # Execute restore job immediately (authenticated operations don't need approval)
        # ADR-031: Use execute_job_async for non-blocking execution
        background_tasks.add_task(job_queue.execute_job_async, job_id)

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


# ========== API Key Management Endpoints (ADR-031) ==========

@router.post("/keys/{provider}", status_code=status.HTTP_201_CREATED)
async def set_api_key(
    provider: str,
    api_key: str = Form(..., description="API key to store")
):
    """
    Set or rotate system API key for a provider (ADR-031)

    Stores encrypted API key for this shard's LLM inference.
    Validates the key before storage by making a minimal API call.

    Supported providers:
    - `openai`: OpenAI API (GPT-4, GPT-4o, embeddings)
    - `anthropic`: Anthropic API (Claude)

    The key is:
    - Validated against the provider's API
    - Encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
    - Stored in PostgreSQL
    - Decrypted only when needed for inference

    Requires admin authentication (placeholder for now).

    Example:
    ```bash
    curl -X POST http://localhost:8000/admin/keys/openai \\
      -F "api_key=sk-..."
    ```

    Returns success message if key validated and stored.
    """
    # Validate provider
    if provider not in API_KEY_PROVIDERS:
        valid_list = ', '.join(f"'{p}'" for p in sorted(API_KEY_PROVIDERS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {valid_list}"
        )

    # Validate key format
    if provider == "anthropic":
        if not api_key.startswith("sk-ant-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Anthropic API key format (must start with 'sk-ant-')"
            )
    elif provider == "openai":
        if not api_key.startswith("sk-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OpenAI API key format (must start with 'sk-')"
            )

    # Test the key by making a minimal API call
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
        else:  # openai
            import openai
            client = openai.OpenAI(api_key=api_key)
            client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key validation failed: {str(e)}"
        )

    # Store encrypted
    try:
        age_client = AGEClient()
        conn = age_client.pool.getconn()
        try:
            key_store = EncryptedKeyStore(conn)
            key_store.store_key(provider, api_key)

            # Mark key as validated (ADR-041)
            # Key was validated above, so we can mark it as valid
            key_store.update_validation_status(provider, "valid")

            logger.info(f"API key configured and validated for provider: {provider}")

            return {
                "status": "success",
                "message": f"{provider} API key configured and validated for this shard",
                "provider": provider,
                "validation_status": "valid"
            }
        finally:
            age_client.pool.putconn(conn)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store API key: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error storing API key for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error storing API key"
        )


@router.get("/keys")
async def list_api_keys():
    """
    List configured API providers with validation status (ADR-031, ADR-041)

    Returns list of providers with status (configured/not configured),
    last update time, validation status, and masked keys.

    The validation status indicates whether the API key was successfully validated:
    - `valid`: Key validated successfully
    - `invalid`: Key validation failed
    - `untested`: Key not yet validated (newly added)
    - `unknown`: Validation tracking not available (migration pending)

    Does NOT return the actual API keys (security) - only masked versions showing
    prefix + last 6 characters (e.g., "sk-proj-...abc123").

    Example response:
    ```json
    [
        {
            "provider": "openai",
            "configured": true,
            "updated_at": "2025-10-21T10:30:00Z",
            "validation_status": "valid",
            "last_validated_at": "2025-10-21T10:30:00Z",
            "validation_error": null,
            "masked_key": "sk-proj-...abc123"
        },
        {
            "provider": "anthropic",
            "configured": false,
            "updated_at": null,
            "validation_status": null,
            "last_validated_at": null,
            "validation_error": null,
            "masked_key": null
        }
    ]
    ```
    """
    try:
        age_client = AGEClient()
        conn = age_client.pool.getconn()
        try:
            # Try to initialize key store - if encryption key not configured, return unconfigured
            try:
                key_store = EncryptedKeyStore(conn)
                # Get configured providers with validation status and masked keys
                configured = key_store.list_providers(include_masked_keys=True)
            except ValueError as e:
                # Encryption key not configured - all providers are unconfigured
                logger.info(f"Encryption key not configured: {e}")
                configured = []

            # Return all possible providers, marking which are configured
            all_providers = sorted(API_KEY_PROVIDERS)
            configured_map = {p['provider']: p for p in configured}

            return [
                {
                    "provider": provider,
                    "configured": provider in configured_map,
                    "updated_at": configured_map[provider]['updated_at'] if provider in configured_map else None,
                    "validation_status": configured_map[provider].get('validation_status') if provider in configured_map else None,
                    "last_validated_at": configured_map[provider].get('last_validated_at') if provider in configured_map else None,
                    "validation_error": configured_map[provider].get('validation_error') if provider in configured_map else None,
                    "masked_key": configured_map[provider].get('masked_key') if provider in configured_map else None
                }
                for provider in all_providers
            ]
        finally:
            age_client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error listing API keys: {str(e)}"
        )


@router.delete("/keys/{provider}")
async def delete_api_key(provider: str):
    """
    Delete system API key for a provider (ADR-031)

    Removes the encrypted API key from this shard's storage.
    After deletion, inference using this provider will not work
    until a new key is configured.

    Requires admin authentication (placeholder for now).

    Example:
    ```bash
    curl -X DELETE http://localhost:8000/admin/keys/openai
    ```

    Returns success if key was deleted, 404 if key wasn't configured.
    """
    # Validate provider
    if provider not in API_KEY_PROVIDERS:
        valid_list = ', '.join(f"'{p}'" for p in sorted(API_KEY_PROVIDERS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {valid_list}"
        )

    try:
        age_client = AGEClient()
        conn = age_client.pool.getconn()
        try:
            # Try to initialize key store - if encryption key not configured, no keys exist
            try:
                key_store = EncryptedKeyStore(conn)
            except ValueError as e:
                # Encryption key not configured - no keys can be stored
                logger.info(f"Encryption key not configured: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No {provider} API key configured (encryption key not available)"
                )

            deleted = key_store.delete_key(provider)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No {provider} API key configured"
                )

            logger.info(f"API key deleted for provider: {provider}")

            return {
                "status": "success",
                "message": f"{provider} API key removed",
                "provider": provider
            }
        finally:
            age_client.pool.putconn(conn)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting API key for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error deleting API key"
        )
