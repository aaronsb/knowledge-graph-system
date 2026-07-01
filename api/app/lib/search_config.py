"""
Search configuration helpers (ADR-508).

Single source of truth for the runtime-configurable default similarity threshold
that every search entry point (concept search, source search, program/MCP
dispatch) inherits when a caller omits ``min_similarity``. Reads from
``kg_api.platform_config`` with a short in-process TTL cache, invalidated on write.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Config key seeded by migration 079.
SEARCH_THRESHOLD_KEY = "search_default_similarity_threshold"

# Fallback when the key is unset/unreadable. MUST match the migration 079 seed.
DEFAULT_SEARCH_THRESHOLD = 0.6

# The default changes rarely; cache it briefly to keep it off the per-search hot
# path. Writes (admin PUT) call invalidate_default_cache() for immediate effect.
_CACHE_TTL_SECONDS = 5.0
_cache: dict = {"value": None, "expires": 0.0}


def invalidate_default_cache() -> None:
    """Drop the cached default so the next read reflects a just-written value."""
    _cache["value"] = None
    _cache["expires"] = 0.0


def get_configured_default(client) -> float:
    """Return the configured default threshold (cached), or the fallback.

    ``client`` is an AGEClient (uses ``client.pool``). Never raises — logs and
    falls back to ``DEFAULT_SEARCH_THRESHOLD`` on any error.
    """
    now = time.monotonic()
    if _cache["value"] is not None and now < _cache["expires"]:
        return _cache["value"]

    value = DEFAULT_SEARCH_THRESHOLD
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT kg_api.get_platform_config(%s)", (SEARCH_THRESHOLD_KEY,))
                row = cur.fetchone()
            if row and row[0] is not None and str(row[0]).strip() != "":
                value = float(row[0])
        finally:
            client.pool.putconn(conn)
    except Exception:
        logger.warning(
            "Could not read %s; using %.2f", SEARCH_THRESHOLD_KEY,
            DEFAULT_SEARCH_THRESHOLD, exc_info=True,
        )

    _cache["value"] = value
    _cache["expires"] = now + _CACHE_TTL_SECONDS
    return value


def resolve_search_threshold(client, requested: Optional[float]) -> float:
    """Return ``requested`` if given, else the configured server default (ADR-508)."""
    if requested is not None:
        return requested
    return get_configured_default(client)
