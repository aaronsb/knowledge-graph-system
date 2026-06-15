"""
AI Vision Configuration Management

Loads and saves the active vision (image->prose) provider selection from/to
the database, mirroring ai_extraction_config (ADR-805) under the ADR-802
decision that vision is a first-class provider capability resolved
independently like embedding.

This module is SELECTION-ONLY: it persists which provider/model is active for
vision and its reasoning controls. Connectivity (base_url, API keys) is reused
from the existing per-provider mechanisms (encrypted key store + env / provider
config) — a provider's endpoint is the same whether it serves extraction or
vision, so it is not duplicated here.  @verified b4106aac
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def load_active_vision_config() -> Optional[Dict[str, Any]]:
    """Load the active vision provider config row, or None if no provider is
    active for vision.

    A None result is normal, not an error: with no active vision config the
    resolver falls to the ADR-802 §2 default (the active extraction provider
    when it has a supports_vision catalog model).  @verified b4106aac
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, provider, model_name, max_tokens, temperature,
                           created_at, updated_at, updated_by, active
                    FROM kg_api.ai_vision_config
                    WHERE active = TRUE
                    LIMIT 1
                """)
                row = cur.fetchone()
                if not row:
                    logger.info("📍 No active vision config in database")
                    return None
                return _row_to_config(row)
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to load active vision config: {e}")
        return None


def load_vision_provider_config(provider: str) -> Optional[Dict[str, Any]]:
    """Load a specific provider's saved vision config row regardless of whether
    it is the active vision provider (parallel to
    ai_extraction_config.load_provider_config).  @verified b4106aac
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, provider, model_name, max_tokens, temperature,
                           created_at, updated_at, updated_by, active
                    FROM kg_api.ai_vision_config
                    WHERE provider = %s
                    LIMIT 1
                """, (provider,))
                row = cur.fetchone()
                return _row_to_config(row) if row else None
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to load vision provider config for {provider}: {e}")
        return None


def save_vision_config(config: Dict[str, Any], updated_by: str = "api") -> bool:
    """Upsert one provider's vision config (per-provider row, UNIQUE(provider)).

    Carries the ADR-801 §3 send-only-what-changed invariant: ON CONFLICT
    (provider) every optional field is COALESCEd against the stored value, so a
    partial save never nulls the rest of the row. `model_name` uses
    NULLIF(EXCLUDED.model_name,'') so the empty-string sentinel of a brand-new
    row never overwrites a real stored model.

    `config['active']` (default True) controls the active pointer only: True
    activates this provider and deactivates the others; False persists config
    without changing which vision provider is active.

    Args:
        config: dict; `provider` required. Optional: model_name, max_tokens,
            temperature, active.
        updated_by: who made the change.

    Returns:
        True on success, False otherwise.  @verified b4106aac
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            activate = config.get('active', True)
            with conn.cursor() as cur:
                cur.execute("BEGIN")

                if activate:
                    cur.execute("""
                        UPDATE kg_api.ai_vision_config
                        SET active = FALSE
                        WHERE active = TRUE AND provider <> %s
                    """, (config['provider'],))

                # Partial-save safety: absent optional fields are passed as NULL
                # and COALESCEd against the stored value (or fall to column
                # defaults on a brand-new row). model_name '' never overwrites a
                # real model (NULLIF). See ai_extraction_config.save_extraction_config.
                cur.execute("""
                    INSERT INTO kg_api.ai_vision_config (
                        provider, model_name, max_tokens, temperature,
                        updated_by, active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider) DO UPDATE SET
                        model_name = COALESCE(
                            NULLIF(EXCLUDED.model_name, ''),
                            kg_api.ai_vision_config.model_name),
                        max_tokens = COALESCE(
                            EXCLUDED.max_tokens,
                            kg_api.ai_vision_config.max_tokens),
                        temperature = COALESCE(
                            EXCLUDED.temperature,
                            kg_api.ai_vision_config.temperature),
                        updated_by = EXCLUDED.updated_by,
                        active = CASE WHEN %s THEN TRUE
                                      ELSE kg_api.ai_vision_config.active END,
                        updated_at = NOW()
                """, (
                    config['provider'],
                    config.get('model_name', ''),
                    config.get('max_tokens'),
                    config.get('temperature'),
                    updated_by,
                    activate,
                    activate,
                ))

                cur.execute("COMMIT")
                logger.info(
                    f"✅ Saved vision config: {config['provider']} / "
                    f"{config.get('model_name') or '(catalog)'} (active={activate})"
                )
                return True
        except Exception as e:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise e
        finally:
            client.pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to save vision config: {e}")
        return False


def _row_to_config(row) -> Dict[str, Any]:
    """Map an ai_vision_config row tuple to a config dict.  @verified b4106aac"""
    return {
        "id": row[0],
        "provider": row[1],
        "model_name": row[2],
        "max_tokens": row[3],
        "temperature": row[4],
        "created_at": row[5],
        "updated_at": row[6],
        "updated_by": row[7],
        "active": row[8],
    }
