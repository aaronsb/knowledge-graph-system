"""
Embedding Configuration Management

Handles loading and saving embedding configuration from/to the database.
Implements database-first configuration (ADR-039).
"""

import logging
from typing import Optional, Dict, Any
import psycopg2

logger = logging.getLogger(__name__)


def load_active_embedding_config() -> Optional[Dict[str, Any]]:
    """
    Load the active embedding configuration from the database.

    Returns:
        Dict with config parameters if found, None otherwise

    Config dict structure:
        {
            "id": 1,
            "provider": "local" | "openai",
            "model_name": "nomic-ai/nomic-embed-text-v1.5",
            "embedding_dimensions": 768,
            "precision": "float16" | "float32",
            "max_memory_mb": 512,
            "num_threads": 4,
            "device": "cpu" | "cuda" | "mps",
            "batch_size": 8,
            "max_seq_length": 8192,
            "normalize_embeddings": True,
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
                        id, provider, model_name, embedding_dimensions, precision,
                        max_memory_mb, num_threads, device, batch_size,
                        max_seq_length, normalize_embeddings,
                        created_at, updated_at, updated_by, active
                    FROM kg_api.embedding_config
                    WHERE active = TRUE
                    LIMIT 1
                """)

                row = cur.fetchone()

                if not row:
                    logger.info("📍 No active embedding config in database")
                    return None

                config = {
                    "id": row[0],
                    "provider": row[1],
                    "model_name": row[2],
                    "embedding_dimensions": row[3],
                    "precision": row[4],
                    "max_memory_mb": row[5],
                    "num_threads": row[6],
                    "device": row[7],
                    "batch_size": row[8],
                    "max_seq_length": row[9],
                    "normalize_embeddings": row[10],
                    "created_at": row[11],
                    "updated_at": row[12],
                    "updated_by": row[13],
                    "active": row[14]
                }

                logger.info(f"✅ Loaded embedding config: {config['provider']} / {config.get('model_name', 'N/A')}")
                return config

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to load embedding config from database: {e}")
        return None


def save_embedding_config(config: Dict[str, Any], updated_by: str = "api", force_change: bool = False) -> tuple[bool, str]:
    """
    Save embedding configuration to the database.

    Deactivates any existing active config and creates a new one.
    Checks change protection before allowing provider/dimension changes.

    Args:
        config: Configuration dict with keys:
            - provider: "local" or "openai" (required)
            - model_name: HuggingFace model ID (for local provider)
            - embedding_dimensions: Vector dimensions
            - precision: "float16" or "float32"
            - max_memory_mb: RAM limit
            - num_threads: CPU threads
            - device: "cpu", "cuda", or "mps"
            - batch_size: Batch size for generation
            - max_seq_length: Token limit
            - normalize_embeddings: True/False
        updated_by: User/admin who made the change
        force_change: Bypass change protection (admin override)

    Returns:
        Tuple of (success, error_message)
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN")

                # Check if active config is change-protected
                if not force_change:
                    cur.execute("""
                        SELECT id, provider, embedding_dimensions, change_protected
                        FROM kg_api.embedding_config
                        WHERE active = TRUE
                    """)

                    active_row = cur.fetchone()

                    if active_row:
                        active_id, active_provider, active_dims, change_protected = active_row

                        if change_protected:
                            # Check if provider or dimensions are changing
                            if (config['provider'] != active_provider or
                                config.get('embedding_dimensions') != active_dims):
                                cur.execute("ROLLBACK")
                                return (False,
                                    f"Active config (ID {active_id}) is change-protected. "
                                    "Changing provider or dimensions breaks vector search. "
                                    "Remove protection first with: kg admin embedding unprotect --change {active_id}")

                # Deactivate all existing configs
                cur.execute("""
                    UPDATE kg_api.embedding_config
                    SET active = FALSE
                    WHERE active = TRUE
                """)

                # Insert new config as active
                cur.execute("""
                    INSERT INTO kg_api.embedding_config (
                        provider, model_name, embedding_dimensions, precision,
                        max_memory_mb, num_threads, device, batch_size,
                        max_seq_length, normalize_embeddings, updated_by, active
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE
                    )
                """, (
                    config['provider'],
                    config.get('model_name'),
                    config.get('embedding_dimensions'),
                    config.get('precision', 'float16'),
                    config.get('max_memory_mb'),
                    config.get('num_threads'),
                    config.get('device', 'cpu'),
                    config.get('batch_size', 8),
                    config.get('max_seq_length'),
                    config.get('normalize_embeddings', True),
                    updated_by
                ))

                # Commit transaction
                cur.execute("COMMIT")

                logger.info(f"✅ Saved embedding config: {config['provider']} / {config.get('model_name', 'N/A')}")
                return (True, "")

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
        logger.error(f"Failed to save embedding config to database: {e}")
        return (False, str(e))


def get_embedding_config_summary() -> Dict[str, Any]:
    """
    Get a summary of the current embedding configuration.

    Returns dict suitable for API responses:
        {
            "provider": "local",
            "model": "nomic-ai/nomic-embed-text-v1.5",
            "dimensions": 768,
            "precision": "float16",
            "config_id": 42,
            "supports_browser": True,
            "resource_allocation": {...}
        }
    """
    config = load_active_embedding_config()

    if not config:
        return {
            "provider": "none",
            "model": None,
            "dimensions": None,
            "precision": None,
            "config_id": None,
            "supports_browser": False,
            "resource_allocation": None
        }

    # Determine if model supports browser-side embeddings
    supports_browser = False
    if config['provider'] == 'local':
        # Check if it's a transformers.js compatible model
        model = config.get('model_name', '')
        if 'nomic' in model.lower() or 'bge' in model.lower():
            supports_browser = True

    return {
        "provider": config['provider'],
        "model": config.get('model_name'),
        "dimensions": config.get('embedding_dimensions'),
        "precision": config.get('precision'),
        "config_id": config['id'],
        "supports_browser": supports_browser,
        "resource_allocation": {
            "max_memory_mb": config.get('max_memory_mb'),
            "num_threads": config.get('num_threads'),
            "device": config.get('device'),
            "batch_size": config.get('batch_size')
        } if config['provider'] == 'local' else None
    }


def list_all_embedding_configs() -> list[Dict[str, Any]]:
    """
    List all embedding configurations (active and inactive).

    Returns:
        List of config dicts with protection flags included
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, provider, model_name, embedding_dimensions, precision,
                        max_memory_mb, num_threads, device, batch_size,
                        max_seq_length, normalize_embeddings,
                        created_at, updated_at, updated_by, active,
                        delete_protected, change_protected
                    FROM kg_api.embedding_config
                    ORDER BY id DESC
                """)

                rows = cur.fetchall()

                configs = []
                for row in rows:
                    configs.append({
                        "id": row[0],
                        "provider": row[1],
                        "model_name": row[2],
                        "embedding_dimensions": row[3],
                        "precision": row[4],
                        "max_memory_mb": row[5],
                        "num_threads": row[6],
                        "device": row[7],
                        "batch_size": row[8],
                        "max_seq_length": row[9],
                        "normalize_embeddings": row[10],
                        "created_at": row[11],
                        "updated_at": row[12],
                        "updated_by": row[13],
                        "active": row[14],
                        "delete_protected": row[15] if len(row) > 15 else False,
                        "change_protected": row[16] if len(row) > 16 else False
                    })

                return configs

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to list embedding configs: {e}")
        return []


def set_embedding_config_protection(config_id: int, delete_protected: bool = None, change_protected: bool = None) -> bool:
    """
    Set or remove protection flags on an embedding configuration.

    Args:
        config_id: Database ID of the config
        delete_protected: Set delete protection (None = no change)
        change_protected: Set change protection (None = no change)

    Returns:
        True if updated successfully, False otherwise
    """
    from .age_client import AGEClient

    if delete_protected is None and change_protected is None:
        return True  # Nothing to update

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                updates = []
                params = []

                if delete_protected is not None:
                    updates.append("delete_protected = %s")
                    params.append(delete_protected)

                if change_protected is not None:
                    updates.append("change_protected = %s")
                    params.append(change_protected)

                params.append(config_id)

                cur.execute(f"""
                    UPDATE kg_api.embedding_config
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)

                conn.commit()

                logger.info(f"✅ Updated protection flags for config {config_id}")
                return True

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to update protection flags: {e}")
        return False


def check_embedding_config_protection(config_id: int) -> Dict[str, bool]:
    """
    Check protection status of an embedding configuration.

    Args:
        config_id: Database ID of the config

    Returns:
        Dict with delete_protected and change_protected flags
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT delete_protected, change_protected
                    FROM kg_api.embedding_config
                    WHERE id = %s
                """, (config_id,))

                row = cur.fetchone()

                if not row:
                    return {"delete_protected": False, "change_protected": False}

                return {
                    "delete_protected": row[0] if row[0] is not None else False,
                    "change_protected": row[1] if row[1] is not None else False
                }

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to check protection flags: {e}")
        return {"delete_protected": False, "change_protected": False}


def delete_embedding_config(config_id: int) -> tuple[bool, str]:
    """
    Delete an embedding configuration (if not protected).

    Args:
        config_id: Database ID of the config to delete

    Returns:
        Tuple of (success, error_message)
    """
    from .age_client import AGEClient

    try:
        # Check protection first
        protection = check_embedding_config_protection(config_id)

        if protection["delete_protected"]:
            return (False, "Config is delete-protected. Remove protection first with: kg admin embedding unprotect --delete")

        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.embedding_config
                    WHERE id = %s
                """, (config_id,))

                if cur.rowcount == 0:
                    return (False, f"Config {config_id} not found")

                conn.commit()

                logger.info(f"✅ Deleted embedding config {config_id}")
                return (True, "")

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to delete embedding config: {e}")
        return (False, str(e))
