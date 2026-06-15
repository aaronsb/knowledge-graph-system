"""
Vision capability policy: which provider/model performs image → prose.

This module is the **vision capability slot policy** (ADR-802 §2), not a
provider hierarchy. The image → prose call itself runs through the single
`AIProvider.describe_image` contract in `ai_providers.py` — the parallel
`VisionProvider` classes were collapsed into it (#457). What lives here is
only the catalog-driven *selection* policy plus the research-validated literal
prompt:

- `resolve_vision_selection()` — resolve the active vision provider/model
  independently of extraction (ADR-802 §2 / #378), fail-loud at the end.
- `_resolve_vision_model()` / `_catalog_vision_model_ids()` — catalog-driven
  vision model resolution by the per-row `supports_vision` flag (ADR-800/801).
- `LITERAL_DESCRIPTION_PROMPT` — the ADR-305-validated literal transcription
  prompt the ingestion worker passes to `describe_image`.

Research Findings (ADR-305, Nov 2025):
- Primary: GPT-4o Vision (100% reliable, excellent literal descriptions)
- Alternate: Claude Sonnet Vision (similar quality to GPT-4o)
- Optional: Ollama (Granite, LLaVA) — inconsistent quality, use only when
  cloud unavailable

See docs/research/vision-testing/ for comprehensive findings.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# --- Catalog-driven vision model selection (ADR-801) -----------------------
# Vision provider/model selection comes from the dynamic model catalog's
# per-model supports_vision flag, not hardcoded lists. Resolution order:
# explicit param → catalog → VISION_MODEL env → ValueError. No literal
# fallback — a deployment without a populated catalog and no env override
# is a configuration error the operator must fix.

def _catalog_vision_models(provider: str) -> list[dict]:
    """Enabled, vision-capable catalog rows for a provider, by sort_order.

    Empty list when the catalog is unavailable or has no vision model for
    the provider (e.g. its 'Get models' has not been run yet).

    Shares the module-level cached AGEClient with ai_providers' catalog
    helpers (see ai_providers._get_catalog_age_client) so repeated calls
    don't churn fresh connection pools.
    """
    try:
        from .model_catalog import list_catalog
        from .ai_providers import _get_catalog_age_client

        client = _get_catalog_age_client()
        conn = client.pool.getconn()
        try:
            rows = list_catalog(conn, provider=provider, enabled_only=True)
            return [r for r in rows if r.get("supports_vision")]
        finally:
            client.pool.putconn(conn)
    except Exception:
        # Deliberate degradation: a catalog/DB failure must fall through to
        # env/error, never silently bind a stale model id. Log at debug so a
        # *persistent* failure is diagnosable — the resolver's raise is the
        # user-visible signal.
        logger.debug(
            f"Vision catalog lookup failed for '{provider}'; "
            f"degrading to env/error", exc_info=True)
        return []


def _catalog_vision_model_ids(provider: str) -> list[str]:
    """Vision-capable model ids for a provider from the catalog."""
    return [r["model_id"] for r in _catalog_vision_models(provider)]


def _resolve_vision_model(provider: str, model: Optional[str] = None) -> str:
    """Resolve the vision model: param → catalog → env → error.

    No hardcoded literal — the prior warned-fallback pinned stale model ids
    (e.g. claude-3-5-sonnet-20241022, retired Oct 28, 2025) and pretended to
    be functional code. Per ADR-800/801 and the no-hardcoded-models directive,
    the catalog is the source of truth; a deployment without a populated
    vision catalog and without a VISION_MODEL env override is misconfigured.
    """
    if model:
        return model
    rows = _catalog_vision_models(provider)
    if rows:
        for r in rows:
            if r.get("is_default"):
                return r["model_id"]
        return rows[0]["model_id"]
    env = os.getenv("VISION_MODEL")
    if env:
        return env
    raise ValueError(
        f"No vision model resolved for provider='{provider}'. Either populate "
        "the vision catalog via the provider's 'Get models' admin action "
        "(ADR-801), or set the VISION_MODEL environment variable."
    )


# --- Active vision provider resolution (ADR-802 §2, #378) ------------------
# Vision is a first-class provider capability resolved independently like
# embedding. The provider is no longer a hardcoded "openai" literal: it
# resolves through a defined chain, and a chosen provider with no usable
# vision model fails loud rather than silently misrouting image->prose.

def resolve_vision_selection(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Resolve which provider/model performs image->prose (ADR-802 §2).

    Resolution order, fail-loud at the end:
      1. Explicit override (per-job ``vision_provider`` / ``VISION_PROVIDER``
         env) — unchanged behaviour for callers that name a provider.
      2. The configured **active vision provider** (its own pointer in
         ``kg_api.ai_vision_config``), and its stored model if the caller
         gave none.
      3. Default: the **active extraction provider**, but only when its
         catalog has a ``supports_vision`` model — so single-provider
         deployments need zero vision config, without re-introducing a bare
         provider literal.
      4. Otherwise raise — no silent fallback to a hardcoded provider.

    Note this resolves only the provider *name* (and optionally a model). The
    caller passes the (provider, model) pair to ``get_provider(name)`` +
    ``describe_image(..., model=model)`` (ADR-802 §4 / #457). When ``model`` is
    None, ``describe_image`` resolves/validates it against the catalog, which
    is the fail-loud point when a provider has no vision-capable model.

    Returns:
        (provider_name, model_or_None)

    Raises:
        ValueError: when no vision provider can be resolved.  @verified ff971ab5
    """
    # 1. Explicit override (param or dev-mode env), parallel to AI_PROVIDER.
    explicit = provider or os.getenv("VISION_PROVIDER")
    if explicit:
        return explicit.lower(), model

    # 2. Active vision config pointer. Deliberately NO _catalog_vision_model_ids
    #    check here (unlike step 3): an operator who explicitly activated this
    #    provider chose it, and the POST /admin/vision/config guard already
    #    rejected activation without a usable model. If the catalog later loses
    #    that model, we still honour the explicit choice and fail loud at
    #    describe_image's model resolution — a named, diagnosable error —
    #    rather than silently overriding the operator's selection.
    try:
        from .ai_vision_config import load_active_vision_config
        vc = load_active_vision_config()
        if vc and vc.get("provider"):
            return vc["provider"].lower(), (model or (vc.get("model_name") or None))
    except Exception:
        logger.debug("Active vision config lookup failed; trying extraction default",
                     exc_info=True)

    # 3. Default to the active extraction provider iff it is vision-capable.
    try:
        from .ai_extraction_config import load_active_extraction_config
        ec = load_active_extraction_config()
        ep = ec.get("provider") if ec else None
        if ep and _catalog_vision_model_ids(ep):
            logger.info(
                "Vision provider unset; defaulting to active extraction "
                f"provider '{ep}' (has a supports_vision catalog model)")
            return ep.lower(), model
    except Exception:
        logger.debug("Extraction-default vision resolution failed", exc_info=True)

    # 4. Fail loud — no hardcoded provider literal (the #378 bug).
    raise ValueError(
        "No vision provider could be resolved (ADR-802 §2): no explicit "
        "override, no active vision config, and the active extraction provider "
        "has no vision-capable model in the catalog. Configure a vision "
        "provider (POST /admin/vision/config) or run the provider's 'Get "
        "models' admin action so a supports_vision model is in the catalog."
    )


# Literal description prompt (validated in research, Nov 2025).
# Passed by the ingestion worker to AIProvider.describe_image (ADR-305).
# See docs/research/vision-testing/FINDINGS.md
LITERAL_DESCRIPTION_PROMPT = """
Describe everything visible in this image literally and exhaustively.

Do NOT summarize or interpret. Do NOT provide analysis or conclusions.

Instead, describe:
- Every piece of text you see, word for word
- Every visual element (boxes, arrows, shapes, colors)
- The exact layout and positioning of elements
- Any diagrams, charts, or graphics in detail
- Relationships between elements (what connects to what, what's above/below)
- Any logos, branding, or page numbers

Be thorough and literal. If you see text, transcribe it exactly. If you see a box with an arrow pointing to another box, describe that precisely.
""".strip()
