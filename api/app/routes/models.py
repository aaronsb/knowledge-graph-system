"""
Model Catalog Routes (ADR-800).

Admin endpoints for managing the provider model catalog:
- GET /admin/models/catalog - List catalog entries
- POST /admin/models/catalog/refresh - Fetch fresh catalog from provider API
- PUT /admin/models/catalog/{id}/enable - Enable a model
- PUT /admin/models/catalog/{id}/disable - Disable a model
- PUT /admin/models/catalog/{id}/default - Set as default
- PUT /admin/models/catalog/{id}/price - Update pricing
"""

import logging
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional

from ..lib.age_client import AGEClient
from ..lib.model_catalog import (
    list_catalog,
    set_model_default,
    set_model_enabled,
    update_model_pricing,
    upsert_catalog_entries,
)

admin_router = APIRouter(prefix="/admin/models", tags=["admin", "models"])

logger = logging.getLogger(__name__)


@admin_router.get("/catalog")
async def get_catalog(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled_only: bool = Query(False, description="Only show enabled models"),
):
    """List model catalog entries with optional filters."""
    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            results = list_catalog(conn, provider=provider, category=category, enabled_only=enabled_only)
            return {"models": results, "count": len(results)}
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to list catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RefreshRequest(BaseModel):
    provider: str


@admin_router.post("/catalog/refresh")
async def refresh_catalog(request: RefreshRequest):
    """
    Fetch fresh model catalog from a provider's API and upsert into database.

    Supported providers: openai, anthropic, ollama, openrouter.
    """
    from ..lib.ai_providers import get_provider

    provider_name = request.provider.lower()
    if provider_name not in ("openai", "anthropic", "ollama", "openrouter"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider_name}",
        )

    try:
        provider = get_provider(provider_name)
        entries = provider.fetch_model_catalog()

        if not entries:
            return {
                "provider": provider_name,
                "message": "No models returned from provider API",
                "upserted": 0,
            }

        client = AGEClient()
        conn = client.pool.getconn()
        try:
            count = upsert_catalog_entries(conn, entries)
            return {
                "provider": provider_name,
                "message": f"Refreshed {count} models",
                "upserted": count,
            }
        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to refresh catalog for {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put("/catalog/{catalog_id}/enable")
async def enable_model(catalog_id: int):
    """Enable a model in the catalog for use."""
    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            if set_model_enabled(conn, catalog_id, True):
                return {"id": catalog_id, "enabled": True}
            raise HTTPException(status_code=404, detail="Model not found")
        finally:
            client.pool.putconn(conn)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put("/catalog/{catalog_id}/disable")
async def disable_model(catalog_id: int):
    """Disable a model in the catalog."""
    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            if set_model_enabled(conn, catalog_id, False):
                return {"id": catalog_id, "enabled": False}
            raise HTTPException(status_code=404, detail="Model not found")
        finally:
            client.pool.putconn(conn)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put("/catalog/{catalog_id}/default")
async def set_default_model(catalog_id: int):
    """Set a model as the default for its provider+category."""
    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            if set_model_default(conn, catalog_id):
                return {"id": catalog_id, "is_default": True}
            raise HTTPException(status_code=404, detail="Model not found")
        finally:
            client.pool.putconn(conn)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PriceUpdateRequest(BaseModel):
    price_prompt_per_m: Optional[float] = None
    price_completion_per_m: Optional[float] = None


@admin_router.put("/catalog/{catalog_id}/price")
async def update_price(catalog_id: int, request: PriceUpdateRequest):
    """Manually override pricing for a catalog entry."""
    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            if update_model_pricing(
                conn,
                catalog_id,
                price_prompt_per_m=request.price_prompt_per_m,
                price_completion_per_m=request.price_completion_per_m,
            ):
                return {"id": catalog_id, "updated": True}
            raise HTTPException(status_code=404, detail="Model not found or no changes")
        finally:
            client.pool.putconn(conn)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
