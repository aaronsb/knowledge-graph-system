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
    get_embedding_config_summary
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
async def update_embedding_config(request: UpdateEmbeddingConfigRequest):
    """
    Update embedding configuration (admin endpoint).

    Creates a new configuration entry and deactivates the previous one.
    Configuration is stored in kg_api.embedding_config table.

    **Important:** In Phase 1, changing configuration requires API restart.
    Use: ./scripts/stop-api.sh && ./scripts/start-api.sh

    **Phase 2:** Will support hot reload via POST /admin/embedding/config/reload

    Validation:
    - provider='local' requires model_name
    - embedding_dimensions auto-detected from model (can be specified for validation)
    - precision must be 'float16' or 'float32'
    - device must be 'cpu', 'cuda', or 'mps'

    Example (OpenAI):
    ```json
    {
        "provider": "openai"
    }
    ```

    Example (Local):
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

        # Save configuration
        config_dict = request.model_dump(exclude_none=True)
        success = save_embedding_config(config_dict, updated_by=request.updated_by)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save embedding configuration"
            )

        # Get the new config ID
        new_config = load_active_embedding_config()
        config_id = new_config['id'] if new_config else 0

        logger.info(f"✅ Embedding config updated: {request.provider} / {request.model_name or 'N/A'}")

        return UpdateEmbeddingConfigResponse(
            success=True,
            message="Configuration updated successfully. API restart required to apply changes.",
            config_id=config_id,
            reload_required=True  # Phase 1: manual restart required
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
    Hot reload embedding model without API restart (Phase 2 - Not Yet Implemented).

    This endpoint will be implemented in Phase 2 to support zero-downtime
    configuration updates. Currently returns 501 Not Implemented.

    Phase 2 implementation:
    1. Load new config from database
    2. Initialize new model in parallel (brief 2x memory usage)
    3. Atomic swap to new model
    4. Finish in-flight requests with old model
    5. Garbage collect old model

    See ADR-039 "Configuration Update Strategy" for details.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Hot reload not yet implemented (ADR-039 Phase 2). "
               "Please restart API: ./scripts/stop-api.sh && ./scripts/start-api.sh"
    )
