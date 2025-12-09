"""
AI Extraction Configuration Routes

API endpoints for AI extraction provider configuration management (ADR-041).

Public endpoints:
- GET /extraction/config - Get AI extraction configuration summary

Admin endpoints:
- GET /admin/extraction/config - Get full configuration details
- POST /admin/extraction/config - Update configuration
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from ..dependencies.auth import CurrentUser, require_role
from ..models.extraction import (
    ExtractionConfigResponse,
    ExtractionConfigDetail,
    UpdateExtractionConfigRequest,
    UpdateExtractionConfigResponse
)
from ..lib.ai_extraction_config import (
    load_active_extraction_config,
    save_extraction_config,
    get_extraction_config_summary
)

# Public router (no auth)
public_router = APIRouter(prefix="/extraction", tags=["extraction"])

# Admin router (requires auth in production)
admin_router = APIRouter(prefix="/admin/extraction", tags=["admin", "extraction"])

logger = logging.getLogger(__name__)


@public_router.get("/config", response_model=ExtractionConfigResponse)
async def get_extraction_config():
    """
    Get current AI extraction configuration (public endpoint).

    Returns summary information suitable for clients to determine:
    - Which AI provider is active (OpenAI, Anthropic)
    - Model capabilities (vision, JSON mode)
    - Token limits

    This endpoint does not require authentication.
    """
    try:
        summary = get_extraction_config_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get extraction config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get extraction config: {str(e)}"
        )


@admin_router.get("/config", response_model=Optional[ExtractionConfigDetail])
async def get_extraction_config_detail(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Get full AI extraction configuration details

    Returns complete configuration including:
    - Provider and model details
    - Capability flags (vision, JSON mode)
    - Metadata (created_at, updated_by, etc.)
    - Database config ID

    Returns null if no configuration is set.

    **Authorization:** Requires `extraction_config:read` permission
    """
    try:
        config = load_active_extraction_config()
        return config
    except Exception as e:
        logger.error(f"Failed to get extraction config details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get extraction config: {str(e)}"
        )


@admin_router.post("/config", response_model=UpdateExtractionConfigResponse)
async def update_extraction_config(
    request: UpdateExtractionConfigRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Update AI extraction configuration

    Creates a new configuration entry and deactivates the previous one.
    Configuration is stored in kg_api.ai_extraction_config table.

    **Important:** Configuration changes are applied immediately (zero-downtime).
    The next extraction request will use the new provider/model automatically.

    **DEVELOPMENT_MODE behavior:**
    - DEVELOPMENT_MODE=true: Configuration changes stored in database but .env takes precedence
    - DEVELOPMENT_MODE=false: Configuration loaded from database (hot-reloadable, recommended)

    Validation:
    - provider must be 'openai' or 'anthropic'
    - model_name is required

    **Authorization:** Requires `extraction_config:write` permission

    Example (OpenAI):
    ```json
    {
        "provider": "openai",
        "model_name": "gpt-4o",
        "supports_vision": true,
        "supports_json_mode": true,
        "max_tokens": 16384
    }
    ```

    Example (Anthropic):
    ```json
    {
        "provider": "anthropic",
        "model_name": "claude-sonnet-4-20250514",
        "supports_vision": true,
        "supports_json_mode": true,
        "max_tokens": 8192
    }
    ```
    """
    try:
        # Validate provider
        from api.api.constants import EXTRACTION_PROVIDERS

        if request.provider not in EXTRACTION_PROVIDERS:
            valid_list = ', '.join(f"'{p}'" for p in sorted(EXTRACTION_PROVIDERS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {request.provider}. Must be one of: {valid_list}"
            )

        # Validate model_name is provided
        if not request.model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="model_name is required"
            )

        # Save configuration
        config_dict = request.model_dump(exclude_none=True)
        success = save_extraction_config(config_dict, updated_by=request.updated_by)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save extraction configuration"
            )

        # Get the new config ID
        new_config = load_active_extraction_config()
        config_id = new_config['id'] if new_config else 0

        logger.info(f"✅ AI extraction config updated: {request.provider} / {request.model_name}")

        return UpdateExtractionConfigResponse(
            success=True,
            message="Configuration updated successfully. Changes applied immediately (zero-downtime).",
            config_id=config_id,
            reload_required=False  # Hot-reloadable via get_provider()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update extraction config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update extraction config: {str(e)}"
        )
