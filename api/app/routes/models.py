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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional

from ..dependencies.auth import require_permission
from ..lib.age_client import AGEClient
from ..lib.model_catalog import (
    list_catalog,
    set_model_default,
    set_model_enabled,
    update_model_pricing,
    upsert_catalog_entries,
)

admin_router = APIRouter(prefix="/admin/models", tags=["admin", "models"])

# Authorization (ADR-400, internet-hardening #432): this router was entirely
# unauthenticated. Reads require extraction_config:read (admin + platform_admin);
# every mutation requires extraction_config:write (platform_admin only) — both
# pairs are seeded in migration 028. require_permission also forces an
# authenticated, non-disabled user, closing the anonymous access hole.

logger = logging.getLogger(__name__)


@admin_router.get("/catalog")
async def get_catalog(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled_only: bool = Query(False, description="Only show enabled models"),
    _: None = Depends(require_permission("extraction_config", "read")),
):
    """List model catalog entries with optional filters. Requires extraction_config:read."""
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
async def refresh_catalog(
    request: RefreshRequest,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """
    Fetch fresh model catalog from a provider's API and upsert into database.

    Supported providers: openai, anthropic, ollama, openrouter.
    Requires extraction_config:write (platform_admin).
    """
    from ..lib.ai_providers import get_provider

    provider_name = request.provider.lower()
    if provider_name not in ("openai", "anthropic", "ollama", "openrouter", "llamacpp"):
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

            # --- SKETCH: self-healing catalog reconciliation (not yet implemented) ---
            # Problem this would solve: upsert is additive. When a provider retires
            # a dated snapshot, the model vanishes from `entries` but its catalog row
            # stays enabled=TRUE — so prefer_cheapest/default resolution can still
            # select a dead model that 404s (this is exactly how claude-3-haiku-
            # 20240307 broke code-block translation; see migration 059).
            #
            # Reconcile idea: `entries` is the set the provider's API says is live.
            # After upserting, disable any *enabled* catalog row for this provider
            # whose model_id is NOT in that live set:
            #
            #   live = {e["model_id"] for e in entries}
            #   UPDATE kg_api.provider_model_catalog
            #      SET enabled = FALSE
            #    WHERE provider = %s AND enabled = TRUE AND model_id <> ALL(%s)   -- live
            #   RETURNING model_id;   -- log these as "auto-disabled (retired)"
            #
            # Resolve these BEFORE shipping it (why this is a sketch, not code):
            #   1. Trust completeness of fetch_model_catalog(). If a provider's
            #      list is paginated/filtered/partial, reconcile would wrongly
            #      disable valid models. Only reconcile when the fetch is known-
            #      complete (e.g. a flag from the provider adapter).
            #   2. Scope by category — don't let an extraction refresh disable
            #      embedding/vision rows.
            #   3. Never auto-disable the active extraction model or is_default;
            #      surface a loud warning instead so the operator re-points config.
            #   4. Distinguish operator-intent disables from auto-disables (a
            #      `disabled_reason` column) so a manual enable isn't clobbered.
            # Pairs with the deferred fail-fast work: a permanent 404 (retired
            # model) should also surface loudly rather than be silently retried.
            # --- END SKETCH ---

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
async def enable_model(
    catalog_id: int,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """Enable a model in the catalog for use. Requires extraction_config:write."""
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
async def disable_model(
    catalog_id: int,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """Disable a model in the catalog. Requires extraction_config:write."""
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
async def set_default_model(
    catalog_id: int,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """Set a model as the default for its provider+category. Requires extraction_config:write."""
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
async def update_price(
    catalog_id: int,
    request: PriceUpdateRequest,
    _: None = Depends(require_permission("extraction_config", "write")),
):
    """Manually override pricing for a catalog entry. Requires extraction_config:write."""
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
