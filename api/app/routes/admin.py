"""
Admin Routes

API endpoints for system administration:
- System status
- Database backup
- Database restore (ADR-015 Phase 2: Multipart Upload)
- Job scheduler management (ADR-014)
- API key management (ADR-031)

Note: Database reset removed from API (too dangerous).
      Use ./scripts/setup/initialize-platform.sh option 0 instead.
"""

import uuid
import shutil
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from typing import Optional

from ..models.admin import (
    SystemStatusResponse,
    BackupRequest,
    BackupResponse,
    ListBackupsResponse,
    RestoreRequest,
    RestoreResponse,
    # ResetRequest, ResetResponse removed - reset moved to initialize-platform.sh option 0
)
from ..dependencies.auth import CurrentUser, require_permission
from ..services.admin_service import AdminService
from ..services.job_scheduler import get_job_scheduler
from ..services.job_queue import get_job_queue
from ..lib.backup_streaming import create_backup_stream
from ..lib.backup_archive import stream_backup_archive, extract_backup_archive, cleanup_extracted_archive
from ..lib.backup_integrity import check_backup_integrity
from ..lib.age_client import AGEClient
from ..lib.encrypted_keys import EncryptedKeyStore
from ..constants import API_KEY_PROVIDERS

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: CurrentUser,
    _: None = Depends(require_permission("admin", "status"))
):
    """
    Get complete system status

    Returns status of:
    - Docker containers
    - Database connection
    - Database statistics
    - Python environment
    - Configuration

    **Authorization:** Requires `admin:status` permission
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
async def list_backups(
    current_user: CurrentUser,
    _: None = Depends(require_permission("backups", "read"))
):
    """
    List all available backup files

    Returns list of backup files with metadata (size, created date, etc.)

    **Authorization:** Requires `backups:read` permission
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
async def create_backup(
    request: BackupRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("backups", "create"))
):
    """
    Create a database backup (ADR-015 Phase 2: Streaming Download)

    **Streams backup directly to client** - no server-side storage.
    Client saves to configured backup directory (~/.local/share/kg/backups).

    Supports two modes:
    - **full**: Backup entire database (all ontologies)
    - **ontology**: Backup specific ontology (requires ontology_name)

    Supports three formats:
    - **archive** (default): tar.gz with manifest.json + original documents from Garage
    - **json**: Graph data only (legacy format) - no source documents
    - **gexf**: Gephi visualization format - graph structure only, NOT restorable

    Archive backup includes:
    - manifest.json with all graph data (concepts, sources, instances, relationships)
    - documents/ directory with original files from Garage storage
    - Full embeddings (1536-dim vectors)

    JSON backup includes (legacy, no documents):
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

    **Authorization:** Requires `backups:create` permission

    Example (Archive with documents - default):
    ```json
    {
        "backup_type": "ontology",
        "ontology_name": "Research Papers"
    }
    ```

    Example (JSON legacy):
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

        # Handle different formats
        if request.format == "archive":
            # Create tar.gz archive with documents (default)
            stream, filename = await stream_backup_archive(
                client=client,
                backup_type=request.backup_type,
                ontology_name=request.ontology_name
            )
            media_type = "application/gzip"
        else:
            # Legacy JSON or GEXF format (graph data only)
            stream, filename = await create_backup_stream(
                client=client,
                backup_type=request.backup_type,
                ontology_name=request.ontology_name,
                format=request.format
            )
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
    current_user: CurrentUser,
    _: None = Depends(require_permission("backups", "restore")),
    file: UploadFile = File(..., description="Backup file (.tar.gz archive or .json)"),
    overwrite: bool = Form(False, description="Overwrite existing data"),
    handle_external_deps: str = Form("prune", description="How to handle external dependencies: 'prune', 'stitch', or 'defer'")
):
    """
    Restore a database backup (ADR-015 Phase 2: Multipart Upload)

    ⚠️ **Potentially destructive operation** - requires admin role.

    **Multipart Upload**: Client streams backup file to server.
    Server validates, then queues restore job for background processing.

    Supports two formats:
    - **.tar.gz** (archive): Contains manifest.json + original documents from Garage
    - **.json** (legacy): Graph data only, no source documents

    Restore options:
    - **overwrite**: Whether to overwrite existing data (default: false)
    - **handle_external_deps**: How to handle external dependencies
      - `prune`: Remove dangling relationships (default)
      - `stitch`: Try to reconnect to existing concepts
      - `defer`: Leave broken (requires manual fix)

    The restore process includes:
    1. Save uploaded file to temp location
    2. For archives: extract and locate manifest.json
    3. Run integrity checks (format, references, statistics)
    4. Queue restore worker with job ID
    5. For archives: restore documents to Garage after graph restore
    6. Return job ID for progress tracking

    Returns job_id for polling restore progress via /jobs/{job_id}

    **Authorization:** Requires `backups:restore` permission

    Example (multipart/form-data):
    ```
    file: <backup_file.tar.gz>
    overwrite: false
    handle_external_deps: prune
    ```
    """

    # Validate file type
    is_archive = file.filename.endswith('.tar.gz')
    is_json = file.filename.endswith('.json')

    if not is_archive and not is_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup file must be .tar.gz archive or .json format"
        )

    # Generate temp file path
    temp_file_id = uuid.uuid4()
    archive_temp_dir = None  # Track extracted archive directory for cleanup

    if is_archive:
        # Save archive to temp, then extract
        archive_path = Path(tempfile.gettempdir()) / f"restore_{temp_file_id}.tar.gz"
    else:
        archive_path = None

    temp_path = Path(tempfile.gettempdir()) / f"restore_{temp_file_id}.json"

    try:
        if is_archive:
            # Save archive file
            logger.info(f"Saving uploaded archive to {archive_path}")
            with open(archive_path, "wb") as temp_file:
                shutil.copyfileobj(file.file, temp_file)

            # Extract archive
            logger.info(f"Extracting archive {archive_path}")
            archive_temp_dir, manifest_path = extract_backup_archive(str(archive_path))
            temp_path = Path(manifest_path)

            # Clean up archive file (keep extracted dir for document restore)
            archive_path.unlink()
        else:
            # Save JSON file directly
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

        # Safety check: If ontology backup and target ontology exists, require --merge flag
        with open(temp_path, 'r') as f:
            import json
            backup_data = json.load(f)
            backup_type = backup_data.get("type", "")
            backup_ontology = backup_data.get("ontology")

            if backup_type == "ontology_backup" and backup_ontology and overwrite:
                # Safety check: If ontology exists and user didn't specify --merge, error
                try:
                    # Use ontology list API to check existence
                    from api.app.routes.ontology import list_ontologies

                    ontologies_result = await list_ontologies()

                    existing_ontologies = [ont.ontology for ont in ontologies_result.ontologies]
                    logger.info(f"Existing ontologies: {existing_ontologies}")

                    if backup_ontology in existing_ontologies:
                        # Ontology exists - require --merge flag
                        temp_path.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Ontology '{backup_ontology}' already exists. Use --merge flag to merge into existing ontology, or delete the existing ontology first."
                        )
                except HTTPException:
                    # Re-raise HTTP exceptions (like 409)
                    raise
                except Exception as e:
                    logger.error(f"Error checking ontology existence: {e}", exc_info=True)
                    # Don't fail restore if ontology check fails - just proceed
                    logger.warning(f"Proceeding with restore despite ontology check failure")

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
                "integrity_warnings": len(integrity.warnings),
                "archive_temp_dir": archive_temp_dir,  # For document restore (None if JSON)
                "is_archive": is_archive
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
        # Cleanup on HTTP exception
        if archive_temp_dir:
            cleanup_extracted_archive(archive_temp_dir)
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Cleanup temp file and archive dir on error
        if temp_path.exists():
            temp_path.unlink()
        if archive_temp_dir:
            cleanup_extracted_archive(archive_temp_dir)

        logger.error(f"Restore upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore upload failed: {str(e)}"
        )


# ========== Database Reset REMOVED - Too Dangerous for API ==========
#
# Database reset has been moved to initialize-platform.sh option 0 for security:
# - Requires physical confirmation (hold Enter for 3 seconds)
# - AI-aware protection (10-second inactivity timeout)
# - Only accessible via direct terminal access
# - Cannot be triggered remotely via API
#
# To reset the database:
#   ./scripts/setup/initialize-platform.sh
#   Select option 0 (Database Reset)
#
# ========================================================================

# ========== Job Scheduler Endpoints (ADR-014) ==========

@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: CurrentUser,
    _: None = Depends(require_permission("admin", "status"))
):
    """
    Get job scheduler status and statistics (ADR-014)

    Returns current scheduler configuration and statistics:
    - Running status
    - Configuration (cleanup interval, retention periods)
    - Job counts by status
    - Last cleanup time
    - Next scheduled cleanup

    **Authorization:** Authenticated users (admin role)

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
async def trigger_scheduler_cleanup(
    current_user: CurrentUser,
    _: None = Depends(require_permission("admin", "status"))
):
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

    **Authorization:** Authenticated users (admin role)

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
    current_user: CurrentUser,
    _: None = Depends(require_permission("api_keys", "write")),
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

    **Authorization:** Requires `api_keys:write` permission

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
async def list_api_keys(
    current_user: CurrentUser,
    _: None = Depends(require_permission("api_keys", "read"))
):
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

    **Authorization:** Requires `api_keys:read` permission

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
async def delete_api_key(
    provider: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("api_keys", "delete"))
):
    """
    Delete system API key for a provider (ADR-031)

    Removes the encrypted API key from this shard's storage.
    After deletion, inference using this provider will not work
    until a new key is configured.

    **Authorization:** Requires `api_keys:delete` permission

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


@router.post("/regenerate-concept-embeddings")
async def regenerate_concept_embeddings(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "regenerate")),
    only_missing: bool = False,
    ontology: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Regenerate embeddings for concept nodes in the graph.

    Useful after changing embedding models to update all concept embeddings
    to the new model/dimensions.

    **Authorization:** Requires `embedding_config:regenerate` permission

    Args:
        only_missing: Only generate for concepts without embeddings
        ontology: Limit to specific ontology (optional)
        limit: Maximum number of concepts to process (for testing)

    Returns:
        Job result with statistics
    """
    try:
        from ..services.embedding_worker import get_embedding_worker
        from ..lib.ai_providers import get_embedding_provider

        # Get embedding worker (reinitialize if needed after hot reload)
        worker = get_embedding_worker()
        if worker is None:
            # Initialize with current EMBEDDING provider (not extraction provider!)
            age_client = AGEClient()
            embedding_provider = get_embedding_provider()
            worker = get_embedding_worker(age_client, embedding_provider)

            if worker is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Embedding worker not initialized"
                )

        logger.info(f"Starting concept embedding regeneration (only_missing={only_missing}, ontology={ontology}, limit={limit})")

        result = await worker.regenerate_concept_embeddings(
            only_missing=only_missing,
            ontology=ontology,
            limit=limit
        )

        return {
            "success": True,
            "job_id": result.job_id,
            "target_count": result.target_count,
            "processed_count": result.processed_count,
            "failed_count": result.failed_count,
            "duration_ms": result.duration_ms,
            "embedding_model": result.embedding_model,
            "embedding_provider": result.embedding_provider,
            "errors": result.errors if result.errors else []
        }

    except Exception as e:
        logger.error(f"Failed to regenerate concept embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate concept embeddings: {str(e)}"
        )


# ====================================================================
# Embedding Management Endpoints
# MOVED to /admin/embedding/* router (see api/routes/embedding.py)
# ====================================================================
# The following endpoints have been refactored and moved to the proper
# embedding management namespace under /admin/embedding/* (ADR-068 Phase 4):
#
# - GET  /admin/embedding-status      → GET  /admin/embedding/status
# - POST /admin/regenerate-embeddings → POST /admin/embedding/regenerate
#
# The new endpoints include:
# - Compatibility checking (model + dimension mismatch detection)
# - --only-incompatible flag for model migrations
# - Worker-based architecture for safety
# ====================================================================
