"""
Vision Provider Configuration Routes (ADR-802 / #378)

Vision is a first-class provider capability resolved independently like
embedding. These endpoints expose the active vision-provider selection that
backs the ADR-802 §2 resolution chain (explicit override → active vision
config → active extraction provider if vision-capable → fail loud).

Public endpoints:
- GET  /vision/config        - active vision provider/model summary

Admin endpoints:
- GET  /admin/vision/config  - active vision config detail (or null)
- POST /admin/vision/config  - set/activate the vision provider
- GET  /admin/vision/providers - which providers are vision-capable (catalog)

Authorization reuses the `extraction_config` RBAC resource: configuring the
vision provider is the same class of admin operation as configuring the
extraction provider, so no new RBAC resource/migration is introduced.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..dependencies.auth import CurrentUser, require_permission
from ..constants import EXTRACTION_PROVIDERS
from ..lib.ai_vision_config import (
    load_active_vision_config,
    load_vision_provider_config,
    save_vision_config,
)
from ..lib.vision_providers import (
    _catalog_vision_model_ids,
    _resolve_vision_model,
    resolve_vision_selection,
)

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/vision", tags=["vision"])
admin_router = APIRouter(prefix="/admin/vision", tags=["admin", "vision"])

# vllm is an EXTRACTION_PROVIDERS placeholder with no connector — never a card.
_UNIMPLEMENTED = {"vllm"}


class UpdateVisionConfigRequest(BaseModel):
    """Set/activate the vision provider. Only `provider` is required; an empty
    `model_name` resolves from the catalog's supports_vision rows."""
    provider: str
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    active: bool = True
    updated_by: str = "api"


def _vision_summary() -> dict:
    """Resolve the effective vision provider/model for client display.

    Mirrors the resolution the worker uses, so clients see what an image
    ingest would actually use — including the extraction-provider default —
    rather than only an explicitly-saved row. Returns provider=None when
    nothing resolves (a misconfiguration the operator must fix).  @verified b4106aac
    """
    try:
        provider, model = resolve_vision_selection()
    except Exception:
        return {"provider": None, "model": None, "source": "unresolved"}
    # Resolve the effective model (catalog → env) so the summary shows what an
    # ingest would actually use; None if the provider has no usable model.
    try:
        model = _resolve_vision_model(provider, model)
    except Exception:
        model = None
    active = load_active_vision_config()
    source = "vision_config" if (active and active.get("provider") == provider) else "extraction_default"
    return {"provider": provider, "model": model, "source": source}


@public_router.get("/config")
async def get_vision_config():
    """Effective vision provider/model summary (public, no auth)."""
    return _vision_summary()


@admin_router.get("/config")
async def get_vision_config_detail(
    current_user: CurrentUser,
    _: None = Depends(require_permission("extraction_config", "read")),
):
    """Active vision config row (or null), plus the effective resolution.

    `config` is null when no vision provider has been explicitly activated —
    in that case `effective` shows the ADR-802 §2 default (the active
    extraction provider when vision-capable).

    **Authorization:** Requires `extraction_config:read` permission
    """
    return {"config": load_active_vision_config(), "effective": _vision_summary()}


@admin_router.post("/config")
async def update_vision_config(
    request: UpdateVisionConfigRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """Set/activate the vision provider (ADR-802 §2).

    Validates the provider against the supported set and, when activating,
    that the provider has a vision-capable catalog model (or an explicit
    model is supplied) — so we never activate a provider that would fail
    loud at the first image. Partial saves preserve other fields (COALESCE).

    **Authorization:** Requires `extraction_config:write` permission
    """
    provider = request.provider.lower()
    if provider in _UNIMPLEMENTED or provider not in EXTRACTION_PROVIDERS:
        valid = ", ".join(f"'{p}'" for p in sorted(EXTRACTION_PROVIDERS - _UNIMPLEMENTED))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid vision provider: {request.provider}. Must be one of: {valid}",
        )

    # Don't activate a provider that has no usable vision model: that would
    # only surface as a fail-loud error on the next image ingest.
    if request.active and not request.model_name and not _catalog_vision_model_ids(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider '{provider}' has no vision-capable model in the catalog. "
                "Run the provider's 'Get models' admin action first, or pass an "
                "explicit model_name."
            ),
        )

    ok = save_vision_config(
        {
            "provider": provider,
            "model_name": request.model_name or "",
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "active": request.active,
        },
        updated_by=request.updated_by,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save vision configuration",
        )
    logger.info(f"✅ Vision config updated: {provider} (active={request.active})")
    return {"status": "success", "provider": provider, "effective": _vision_summary()}


@admin_router.get("/providers")
async def list_vision_providers(
    current_user: CurrentUser,
    _: None = Depends(require_permission("api_keys", "read")),
):
    """Vision-capability metadata per provider (data-driven UI, ADR-801 style).

    `supports_vision` is true when the provider has at least one
    `supports_vision` model in the catalog — i.e. it can be activated for
    vision without an explicit model. `vision_models` lists those ids.

    **Authorization:** Requires `api_keys:read` permission
    """
    providers = []
    for name in sorted(EXTRACTION_PROVIDERS - _UNIMPLEMENTED):
        model_ids = _catalog_vision_model_ids(name)
        providers.append(
            {
                "provider": name,
                "supports_vision": bool(model_ids),
                "vision_models": model_ids,
            }
        )
    return {"providers": providers}
