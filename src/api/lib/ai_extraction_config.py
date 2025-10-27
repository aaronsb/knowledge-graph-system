"""
AI Extraction Configuration Management

Handles loading and saving AI extraction configuration from/to the database.
Implements database-first configuration (ADR-041).
"""

import logging
from typing import Optional, Dict, Any
import psycopg2

logger = logging.getLogger(__name__)


def load_active_extraction_config() -> Optional[Dict[str, Any]]:
    """
    Load the active AI extraction configuration from the database.

    Returns:
        Dict with config parameters if found, None otherwise

    Config dict structure:
        {
            "id": 1,
            "provider": "openai" | "anthropic",
            "model_name": "gpt-4o",
            "supports_vision": True,
            "supports_json_mode": True,
            "max_tokens": 16384,
            "created_at": "...",
            "updated_at": "...",
            "updated_by": "..."
        }
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, provider, model_name, supports_vision,
                        supports_json_mode, max_tokens,
                        created_at, updated_at, updated_by, active,
                        base_url, temperature, top_p, gpu_layers, num_threads,
                        thinking_mode
                    FROM kg_api.ai_extraction_config
                    WHERE active = TRUE
                    LIMIT 1
                """)

                row = cur.fetchone()

                if not row:
                    logger.info("📍 No active AI extraction config in database")
                    return None

                config = {
                    "id": row[0],
                    "provider": row[1],
                    "model_name": row[2],
                    "supports_vision": row[3],
                    "supports_json_mode": row[4],
                    "max_tokens": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                    "updated_by": row[8],
                    "active": row[9],
                    "base_url": row[10],
                    "temperature": row[11],
                    "top_p": row[12],
                    "gpu_layers": row[13],
                    "num_threads": row[14],
                    "thinking_mode": row[15]
                }

                logger.debug(f"✅ Loaded AI extraction config: {config['provider']} / {config.get('model_name', 'N/A')}")
                logger.debug(f"🔍 Config thinking_mode from database: {config.get('thinking_mode', 'NOT_SET')}")
                return config

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to load AI extraction config from database: {e}")
        return None


def save_extraction_config(config: Dict[str, Any], updated_by: str = "api") -> bool:
    """
    Save AI extraction configuration to the database.

    Deactivates any existing active config and creates a new one.

    Args:
        config: Configuration dict with keys:
            - provider: "openai" or "anthropic" (required)
            - model_name: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-20250514")
            - supports_vision: True/False (optional)
            - supports_json_mode: True/False (optional)
            - max_tokens: Maximum token limit (optional)
        updated_by: User/admin who made the change

    Returns:
        True if saved successfully, False otherwise
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN")

                # Deactivate all existing configs
                cur.execute("""
                    UPDATE kg_api.ai_extraction_config
                    SET active = FALSE
                    WHERE active = TRUE
                """)

                # Insert new config as active
                cur.execute("""
                    INSERT INTO kg_api.ai_extraction_config (
                        provider, model_name, supports_vision, supports_json_mode,
                        max_tokens, updated_by, active,
                        base_url, temperature, top_p, gpu_layers, num_threads,
                        thinking_mode
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, TRUE,
                        %s, %s, %s, %s, %s, %s
                    )
                """, (
                    config['provider'],
                    config['model_name'],
                    config.get('supports_vision', False),
                    config.get('supports_json_mode', True),
                    config.get('max_tokens'),
                    updated_by,
                    config.get('base_url'),
                    config.get('temperature'),
                    config.get('top_p'),
                    config.get('gpu_layers'),
                    config.get('num_threads'),
                    config.get('thinking_mode', 'off')
                ))

                # Commit transaction
                cur.execute("COMMIT")

                logger.info(f"✅ Saved AI extraction config: {config['provider']} / {config.get('model_name', 'N/A')}")
                return True

        except Exception as e:
            # Rollback on error
            try:
                cur.execute("ROLLBACK")
            except:
                pass
            raise e
        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to save AI extraction config to database: {e}")
        return False


def get_extraction_config_summary() -> Dict[str, Any]:
    """
    Get a summary of the current AI extraction configuration.

    Returns dict suitable for API responses:
        {
            "provider": "openai",
            "model": "gpt-4o",
            "supports_vision": True,
            "supports_json_mode": True,
            "max_tokens": 16384,
            "config_id": 42
        }
    """
    config = load_active_extraction_config()

    if not config:
        return {
            "provider": "none",
            "model": None,
            "supports_vision": False,
            "supports_json_mode": False,
            "max_tokens": None,
            "config_id": None
        }

    return {
        "provider": config['provider'],
        "model": config.get('model_name'),
        "supports_vision": config.get('supports_vision', False),
        "supports_json_mode": config.get('supports_json_mode', True),
        "max_tokens": config.get('max_tokens'),
        "config_id": config['id'],
        "base_url": config.get('base_url'),
        "temperature": config.get('temperature'),
        "top_p": config.get('top_p'),
        "gpu_layers": config.get('gpu_layers'),
        "num_threads": config.get('num_threads'),
        "thinking_mode": config.get('thinking_mode')
    }
