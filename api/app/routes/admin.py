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

import re
import uuid
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime, timezone

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
from pydantic import BaseModel
from ..constants import API_KEY_PROVIDERS, LOCAL_PROVIDERS, EXTRACTION_PROVIDERS

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

        # Safety check: If a single-ontology backup targets an existing ontology,
        # require the --merge flag. The single kg-backup/2 model names the scope in
        # the header (one ontology entry == a scoped backup) — ADR-102 P3.
        with open(temp_path, 'r') as f:
            import json
            from ...lib.serialization import KgBackupV2Reader
            backup_data = json.load(f)
            _header_ontologies = [
                o.get("name") for o in KgBackupV2Reader(backup_data).header.get("ontologies", [])
                if o.get("name")
            ]
            backup_ontology = _header_ontologies[0] if len(_header_ontologies) == 1 else None

            if backup_ontology and overwrite:
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

        # Auto-approve: restore jobs don't need the analysis/approval workflow
        # (user already confirmed via CLI). Move straight to approved so the
        # ADR-100 lane manager can claim it.
        job_queue.update_job(job_id, {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": "auto"
        })

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

    # Test the key via the connector layer's single source of truth — no
    # inline per-provider SDK calls, no hardcoded model names, no key-format
    # prefix guessing. The connector authenticates model-agnostically (ADR-800).
    from ..lib.ai_providers import validate_provider_key

    is_valid, error_msg = validate_provider_key(provider, api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key validation failed: {error_msg}"
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


@router.get("/providers")
async def list_providers(
    current_user: CurrentUser,
    _: None = Depends(require_permission("api_keys", "read"))
):
    """
    Canonical list of supported AI/reasoning providers (ADR-800).

    This is the single source of truth the UI uses to render one provider
    card each — derived from EXTRACTION_PROVIDERS with per-provider metadata
    so the frontend hardcodes nothing:

    - `requires_key`: provider needs an API key (cloud)
    - `is_local`: local inference server, no key (connectivity-tested)

    Providers without a wired connector (e.g. vllm — ADR-042 Phase 4) are
    omitted so every card maps to something that actually works.

    **Authorization:** Requires `api_keys:read` permission
    """
    # vllm is in EXTRACTION_PROVIDERS as a placeholder but has no connector
    # in get_provider() yet — don't surface a card that can't function.
    unimplemented = {"vllm"}

    # ADR-802: vision is a catalog-described capability. `supports_vision` is
    # true when the provider has a supports_vision model in the catalog, so the
    # UI can data-drive a vision selector without hardcoding which providers
    # can do image->prose.
    from ..lib.vision_providers import _catalog_vision_model_ids

    providers = [
        {
            "provider": name,
            "requires_key": name in API_KEY_PROVIDERS,
            "is_local": name in LOCAL_PROVIDERS,
            "supports_vision": bool(_catalog_vision_model_ids(name)),
        }
        for name in sorted(EXTRACTION_PROVIDERS)
        if name not in unimplemented
    ]
    return {"providers": providers}


def _validate_provider_id(provider: str) -> None:
    """Reject obviously-malformed provider identifiers (ADR-800/801).

    Shared by the per-provider config GET/POST and the key DELETE so the
    contract is symmetric — a POST cannot write a row a GET would 400 on.
    """
    if not provider or not re.fullmatch(r"[a-z0-9._-]{1,50}", provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider identifier"
        )


class ProviderConfigRequest(BaseModel):
    """Per-provider config (#8) — saved without activating the provider."""
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.post("/providers/{provider}/config")
async def save_provider_config(
    provider: str,
    body: ProviderConfigRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("extraction_config", "write"))
):
    """
    Persist a provider's config (base_url, model, reasoning params) WITHOUT
    activating it (#8 — DB-backed per-provider config decoupled from the
    active pointer). Lets the UI configure an endpoint, then "Get models"
    / activate against that saved base_url.

    **Authorization:** Requires `extraction_config:write` permission
    """
    _validate_provider_id(provider)
    from ..lib.ai_extraction_config import save_extraction_config

    ok = save_extraction_config({
        "provider": provider,
        "model_name": body.model_name or "",
        "base_url": body.base_url,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "active": False,
    }, updated_by="web-admin")
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save config for provider '{provider}'"
        )
    return {"status": "success", "provider": provider}


@router.get("/providers/{provider}/config")
async def get_provider_config(
    provider: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("extraction_config", "read"))
):
    """
    Read a provider's saved config regardless of whether it is active
    (#8 — DB-backed per-provider config). Symmetric to the POST: lets the
    UI pre-populate each provider card (base_url, model, reasoning params)
    with what is actually persisted, so the database is a two-way source
    of truth rather than write-only. `config` is null when the provider
    has no saved row yet.

    **Authorization:** Requires `extraction_config:read` permission
    """
    _validate_provider_id(provider)

    from ..lib.ai_extraction_config import load_provider_config

    row = load_provider_config(provider)
    if not row:
        return {"provider": provider, "config": None}
    return {
        "provider": provider,
        "config": {
            "base_url": row.get("base_url"),
            "model_name": row.get("model_name"),
            "temperature": row.get("temperature"),
            "max_tokens": row.get("max_tokens"),
            "active": row.get("active"),
        },
    }


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

            # This endpoint lists *AI* provider keys only. A provider is an AI
            # provider if the system knows how to validate it
            # (API_KEY_PROVIDERS) or it appears in the model catalog. This
            # surfaces arbitrarily-configured AI providers (e.g. openrouter
            # via the CLI) without leaking non-AI key holders such as the
            # `garage` storage credentials, which also live in
            # system_api_keys but are not reasoning providers (ADR-800).
            configured_map = {p['provider']: p for p in configured}
            try:
                from ..lib.model_catalog import list_catalog
                catalog_providers = {row['provider'] for row in list_catalog(conn)}
            except Exception as e:
                logger.warning(f"Could not load catalog providers: {e}")
                catalog_providers = set()

            # Key-requiring AI providers only: drop local providers (ollama,
            # llamacpp — no key; they surface in the UI as local cards via
            # the catalog) and non-AI key holders (garage).
            ai_key_providers = (set(API_KEY_PROVIDERS) | catalog_providers) - set(LOCAL_PROVIDERS)
            configured_ai = {p for p in configured_map if p in ai_key_providers}
            all_providers = sorted(ai_key_providers | configured_ai)

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
    # Provider is a stored identifier, not restricted to API_KEY_PROVIDERS:
    # any provider that has a key (including ones configured via the CLI)
    # must be deletable. A non-configured provider falls through to 404
    # below. Reject only obviously malformed identifiers (ADR-800).
    _validate_provider_id(provider)

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
