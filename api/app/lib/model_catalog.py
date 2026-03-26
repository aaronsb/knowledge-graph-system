"""
Provider model catalog management (ADR-800).

Handles fetching, upserting, and querying the provider_model_catalog table.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def upsert_catalog_entries(conn, entries: List[Dict[str, Any]]) -> int:
    """
    Upsert model catalog entries into provider_model_catalog.

    Args:
        conn: psycopg2 connection
        entries: List of dicts with catalog column values from fetch_model_catalog()

    Returns:
        Number of rows upserted
    """
    if not entries:
        return 0

    now = datetime.now(timezone.utc)
    count = 0

    with conn.cursor() as cur:
        for entry in entries:
            raw = entry.get("raw_metadata")
            raw_json = json.dumps(raw) if raw is not None else None

            cur.execute(
                """INSERT INTO kg_api.provider_model_catalog
                   (provider, model_id, display_name, category, context_length,
                    max_completion_tokens, supports_vision, supports_json_mode,
                    supports_tool_use, supports_streaming,
                    price_prompt_per_m, price_completion_per_m, price_cache_read_per_m,
                    upstream_provider, raw_metadata, fetched_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (provider, model_id, category) DO UPDATE SET
                     display_name = EXCLUDED.display_name,
                     context_length = COALESCE(EXCLUDED.context_length, kg_api.provider_model_catalog.context_length),
                     max_completion_tokens = COALESCE(EXCLUDED.max_completion_tokens, kg_api.provider_model_catalog.max_completion_tokens),
                     supports_vision = EXCLUDED.supports_vision,
                     supports_json_mode = EXCLUDED.supports_json_mode,
                     supports_tool_use = EXCLUDED.supports_tool_use,
                     supports_streaming = EXCLUDED.supports_streaming,
                     price_prompt_per_m = COALESCE(EXCLUDED.price_prompt_per_m, kg_api.provider_model_catalog.price_prompt_per_m),
                     price_completion_per_m = COALESCE(EXCLUDED.price_completion_per_m, kg_api.provider_model_catalog.price_completion_per_m),
                     price_cache_read_per_m = COALESCE(EXCLUDED.price_cache_read_per_m, kg_api.provider_model_catalog.price_cache_read_per_m),
                     upstream_provider = EXCLUDED.upstream_provider,
                     raw_metadata = EXCLUDED.raw_metadata,
                     fetched_at = EXCLUDED.fetched_at,
                     updated_at = EXCLUDED.updated_at
                """,
                (
                    entry["provider"],
                    entry["model_id"],
                    entry.get("display_name"),
                    entry["category"],
                    entry.get("context_length"),
                    entry.get("max_completion_tokens"),
                    entry.get("supports_vision", False),
                    entry.get("supports_json_mode", False),
                    entry.get("supports_tool_use", False),
                    entry.get("supports_streaming", True),
                    entry.get("price_prompt_per_m"),
                    entry.get("price_completion_per_m"),
                    entry.get("price_cache_read_per_m"),
                    entry.get("upstream_provider"),
                    raw_json,
                    now,
                    now,
                ),
            )
            count += 1

    conn.commit()
    logger.info(f"Upserted {count} catalog entries")
    return count


def list_catalog(
    conn,
    provider: Optional[str] = None,
    category: Optional[str] = None,
    enabled_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Query provider_model_catalog with optional filters.

    Returns list of dicts with all catalog columns.
    """
    conditions = []
    params = []

    if provider:
        conditions.append("provider = %s")
        params.append(provider)
    if category:
        conditions.append("category = %s")
        params.append(category)
    if enabled_only:
        conditions.append("enabled = TRUE")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, provider, model_id, display_name, category,
                       context_length, max_completion_tokens,
                       supports_vision, supports_json_mode, supports_tool_use,
                       supports_streaming,
                       price_prompt_per_m, price_completion_per_m, price_cache_read_per_m,
                       enabled, is_default, sort_order,
                       upstream_provider, fetched_at, created_at, updated_at
                FROM kg_api.provider_model_catalog
                {where}
                ORDER BY provider, sort_order, model_id""",
            params,
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def set_model_enabled(conn, catalog_id: int, enabled: bool) -> bool:
    """Enable or disable a model in the catalog."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE kg_api.provider_model_catalog
               SET enabled = %s, updated_at = NOW()
               WHERE id = %s""",
            (enabled, catalog_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_model_default(conn, catalog_id: int) -> bool:
    """
    Set a model as the default for its provider+category.

    Clears existing default for that provider+category first.
    """
    with conn.cursor() as cur:
        # Get the provider and category for this model
        cur.execute(
            "SELECT provider, category FROM kg_api.provider_model_catalog WHERE id = %s",
            (catalog_id,),
        )
        row = cur.fetchone()
        if not row:
            return False

        provider, category = row

        # Clear existing default
        cur.execute(
            """UPDATE kg_api.provider_model_catalog
               SET is_default = FALSE, updated_at = NOW()
               WHERE provider = %s AND category = %s AND is_default = TRUE""",
            (provider, category),
        )

        # Set new default (also ensures enabled)
        cur.execute(
            """UPDATE kg_api.provider_model_catalog
               SET is_default = TRUE, enabled = TRUE, updated_at = NOW()
               WHERE id = %s""",
            (catalog_id,),
        )
        conn.commit()
        return True


def update_model_pricing(
    conn,
    catalog_id: int,
    price_prompt_per_m: Optional[float] = None,
    price_completion_per_m: Optional[float] = None,
) -> bool:
    """Manually override pricing for a catalog entry."""
    updates = []
    params = []

    if price_prompt_per_m is not None:
        updates.append("price_prompt_per_m = %s")
        params.append(price_prompt_per_m)
    if price_completion_per_m is not None:
        updates.append("price_completion_per_m = %s")
        params.append(price_completion_per_m)

    if not updates:
        return False

    updates.append("updated_at = NOW()")
    params.append(catalog_id)

    with conn.cursor() as cur:
        cur.execute(
            f"""UPDATE kg_api.provider_model_catalog
                SET {', '.join(updates)}
                WHERE id = %s""",
            params,
        )
        conn.commit()
        return cur.rowcount > 0


def get_model_pricing(conn, provider: str, model_id: str) -> Optional[Dict[str, Any]]:
    """
    Look up pricing for a specific model from the catalog.

    Returns dict with price_prompt_per_m and price_completion_per_m, or None.
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT price_prompt_per_m, price_completion_per_m, price_cache_read_per_m
               FROM kg_api.provider_model_catalog
               WHERE provider = %s AND model_id = %s AND enabled = TRUE
               LIMIT 1""",
            (provider, model_id),
        )
        row = cur.fetchone()
        if row:
            return {
                "price_prompt_per_m": float(row[0]) if row[0] is not None else None,
                "price_completion_per_m": float(row[1]) if row[1] is not None else None,
                "price_cache_read_per_m": float(row[2]) if row[2] is not None else None,
            }
    return None
