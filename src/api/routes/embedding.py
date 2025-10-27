"""
Embedding Configuration Routes

API endpoints for embedding configuration management (ADR-039).

Public endpoints:
- GET /embedding/config - Get embedding configuration summary

Admin endpoints:
- GET /admin/embedding/config - Get full configuration details
- POST /admin/embedding/config - Update configuration
- POST /admin/embedding/config/reload - Hot reload model (Phase 2)
"""

import logging
from fastapi import APIRouter, HTTPException, status
from typing import Optional

from ..models.embedding import (
    EmbeddingConfigResponse,
    EmbeddingConfigDetail,
    UpdateEmbeddingConfigRequest,
    UpdateEmbeddingConfigResponse,
    ReloadEmbeddingModelResponse
)
from ..lib.embedding_config import (
    load_active_embedding_config,
    save_embedding_config,
    get_embedding_config_summary,
    list_all_embedding_configs,
    set_embedding_config_protection,
    delete_embedding_config,
    activate_embedding_config
)

# Public router (no auth)
public_router = APIRouter(prefix="/embedding", tags=["embedding"])

# Admin router (requires auth in production)
admin_router = APIRouter(prefix="/admin/embedding", tags=["admin", "embedding"])

logger = logging.getLogger(__name__)


@public_router.get("/config", response_model=EmbeddingConfigResponse)
async def get_embedding_config():
    """
    Get current embedding configuration (public endpoint).

    Returns summary information suitable for clients to determine:
    - Which embedding provider is active
    - Model dimensions (for compatibility checks)
    - Whether browser-side embeddings are supported

    This endpoint does not require authentication.
    """
    try:
        summary = get_embedding_config_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding config: {str(e)}"
        )


@admin_router.get("/config", response_model=Optional[EmbeddingConfigDetail])
async def get_embedding_config_detail():
    """
    Get full embedding configuration details (admin endpoint).

    Returns complete configuration including:
    - All resource allocation settings
    - Metadata (created_at, updated_by, etc.)
    - Database config ID

    Returns null if no configuration is set.
    """
    try:
        config = load_active_embedding_config()
        return config
    except Exception as e:
        logger.error(f"Failed to get embedding config details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding config: {str(e)}"
        )


@admin_router.post("/config", response_model=UpdateEmbeddingConfigResponse)
async def create_embedding_config(request: UpdateEmbeddingConfigRequest):
    """
    Create a new embedding configuration (admin endpoint).

    Creates a new INACTIVE configuration entry. Use the activate endpoint to switch to it.

    **Workflow:**
    1. Create config: POST /admin/embedding/config (this endpoint)
    2. Review configs: GET /admin/embedding/configs
    3. Activate: POST /admin/embedding/config/{id}/activate
    4. Hot reload: POST /admin/embedding/config/reload

    **Validation:**
    - provider='local' requires model_name
    - embedding_dimensions auto-detected from model (can be specified for validation)
    - precision must be 'float16' or 'float32'
    - device must be 'cpu', 'cuda', or 'mps'

    **Example (OpenAI):**
    ```json
    {
        "provider": "openai"
    }
    ```

    **Example (Local):**
    ```json
    {
        "provider": "local",
        "model_name": "nomic-ai/nomic-embed-text-v1.5",
        "precision": "float16",
        "max_memory_mb": 512,
        "num_threads": 4,
        "device": "cpu",
        "batch_size": 8
    }
    ```
    """
    try:
        # Validate provider
        if request.provider not in ['openai', 'local']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {request.provider}. Must be 'openai' or 'local'"
            )

        # Validate local provider has model_name
        if request.provider == 'local' and not request.model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="provider='local' requires model_name parameter"
            )

        # Validate precision
        if request.precision and request.precision not in ['float16', 'float32']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid precision: {request.precision}. Must be 'float16' or 'float32'"
            )

        # Validate device
        if request.device and request.device not in ['cpu', 'cuda', 'mps']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid device: {request.device}. Must be 'cpu', 'cuda', or 'mps'"
            )

        # Create configuration (inactive by default)
        config_dict = request.model_dump(exclude_none=True)
        success, error_msg, config_id = save_embedding_config(config_dict, updated_by=request.updated_by)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST if "protected" in error_msg.lower() else status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg or "Failed to create embedding configuration"
            )

        logger.info(f"✅ Embedding config created (ID {config_id}, inactive): {request.provider} / {request.model_name or 'N/A'}")

        return UpdateEmbeddingConfigResponse(
            success=True,
            message=f"Configuration created (ID {config_id}, inactive). Use 'kg admin embedding activate {config_id}' to switch to this config.",
            config_id=config_id,
            reload_required=False  # Not active yet, so no reload needed
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update embedding config: {str(e)}"
        )


@admin_router.post("/config/reload", response_model=ReloadEmbeddingModelResponse)
async def reload_embedding_model():
    """
    Hot reload embedding model without API restart (zero-downtime updates).

    Implements zero-downtime configuration updates:
    1. Load new config from database
    2. Initialize new model in parallel (old model still serves requests)
    3. Atomic swap to new model
    4. In-flight requests complete with old model
    5. Old model garbage collected automatically

    Note: Brief 2x memory usage during model loading (1-2 seconds for 300MB-1.3GB models).

    For provider switches:
    - local → openai: Unloads local model, switches to OpenAI API
    - openai → local: Loads local model from database config
    - local → local (different model): Hot swaps to new model

    Returns success with new provider details.

    Example response:
    ```json
    {
        "success": true,
        "message": "Embedding model reloaded successfully",
        "provider": "local",
        "model": "nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768
    }
    ```
    """
    try:
        from ..lib.embedding_model_manager import reload_embedding_model_manager
        from ..services.embedding_worker import reset_embedding_worker

        # Hot reload the model manager
        manager = await reload_embedding_model_manager()

        # Reset EmbeddingWorker singleton so it picks up the new provider
        reset_embedding_worker()
        logger.info("🔄 Reset EmbeddingWorker singleton to pick up new provider")

        # Get new configuration summary
        summary = get_embedding_config_summary()

        # Auto-protect: Re-enable change protection on the new active config
        # This prevents accidental changes after a successful reload
        config = load_active_embedding_config()
        if config:
            set_embedding_config_protection(config['id'], change_protected=True)
            logger.info(f"🔒 Auto-protected config {config['id']} after hot reload")

        logger.info(f"✅ Embedding model hot reload successful: {summary['provider']}")

        return ReloadEmbeddingModelResponse(
            success=True,
            message="Embedding model reloaded successfully (config auto-protected)",
            provider=summary['provider'],
            model=summary.get('model'),
            dimensions=summary.get('dimensions')
        )

    except Exception as e:
        logger.error(f"❌ Embedding model hot reload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hot reload failed: {str(e)}"
        )


@admin_router.get("/configs", response_model=list)
async def list_embedding_configs():
    """
    List all embedding configurations (admin endpoint).

    Returns all configs (active and inactive) with protection flags.
    Use this to see all historical configurations.
    """
    try:
        configs = list_all_embedding_configs()
        return configs
    except Exception as e:
        logger.error(f"Failed to list embedding configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list configs: {str(e)}"
        )


@admin_router.post("/config/{config_id}/protect")
async def protect_embedding_config(
    config_id: int,
    delete_protected: Optional[bool] = None,
    change_protected: Optional[bool] = None
):
    """
    Set protection flags on an embedding configuration (admin endpoint).

    Protection flags prevent accidental breaking changes:
    - delete_protected: Prevents deletion without explicit unprotect
    - change_protected: Prevents changing provider/dimensions (breaks vector search)

    Example:
    ```json
    {
        "delete_protected": true,
        "change_protected": true
    }
    ```
    """
    try:
        if delete_protected is None and change_protected is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify at least one protection flag"
            )

        success = set_embedding_config_protection(
            config_id,
            delete_protected=delete_protected,
            change_protected=change_protected
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Config {config_id} not found"
            )

        return {"success": True, "config_id": config_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set protection flags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set protection: {str(e)}"
        )


@admin_router.delete("/config/{config_id}")
async def delete_embedding_config_endpoint(config_id: int):
    """
    Delete an embedding configuration (admin endpoint).

    Cannot delete configs that are delete-protected.
    Remove protection first if needed.
    """
    try:
        success, error_msg = delete_embedding_config(config_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST if "protected" in error_msg.lower() else status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        return {"success": True, "config_id": config_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete config: {str(e)}"
        )


@admin_router.post("/config/{config_id}/activate")
async def activate_embedding_config_endpoint(config_id: int, force: bool = False):
    """
    Activate an embedding configuration with automatic protection management.

    This provides a clean "unlock → activate → lock" workflow:
    1. Unprotects currently active config (change protection)
    2. Deactivates current config
    3. Activates target config
    4. Protects target config (both delete and change protection)

    **Safety checks:**
    - Prevents switching between configs with different embedding dimensions
    - Changing dimensions breaks vector search for all existing concepts
    - Use `?force=true` to bypass dimension check (dangerous!)

    **Example workflow:**
    ```bash
    # List available configs
    kg admin embedding list

    # Activate a preset (e.g., nomic-embed-text-v1.5)
    kg admin embedding activate 3

    # Force activation with dimension mismatch (use with caution!)
    kg admin embedding activate 3 --force

    # Hot reload to apply changes
    kg admin embedding reload
    ```

    Query Parameters:
    - force: Bypass dimension mismatch check (default: false)

    Returns:
    - success: True if activation successful
    - config_id: ID of activated config
    - message: Next steps (hot reload recommended)
    """
    try:
        success, error_msg = activate_embedding_config(config_id, updated_by="api", force_dimension_change=force)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Get the activated config details
        config = load_active_embedding_config()

        return {
            "success": True,
            "config_id": config_id,
            "message": "Configuration activated successfully. Run 'kg admin embedding reload' to apply changes.",
            "provider": config.get('provider') if config else None,
            "model": config.get('model_name') if config else None,
            "dimensions": config.get('embedding_dimensions') if config else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate config: {str(e)}"
        )
