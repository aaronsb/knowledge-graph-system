"""
Embedding Profile Configuration Management

Handles loading and saving embedding profiles from/to the database.
Reads from kg_api.embedding_profile (migration 055).
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Column list for SELECT queries (keep in sync with embedding_profile table)
_PROFILE_COLUMNS = """
    id, name, vector_space, multimodal,
    text_provider, text_model_name, text_loader, text_revision,
    text_dimensions, text_precision, text_trust_remote_code,
    image_provider, image_model_name, image_loader, image_revision,
    image_dimensions, image_precision, image_trust_remote_code,
    device, max_memory_mb, num_threads, batch_size,
    max_seq_length, normalize_embeddings,
    active, delete_protected, change_protected,
    created_at, updated_at, updated_by
"""


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a profile row tuple to a dict."""
    return {
        "id": row[0],
        "name": row[1],
        "vector_space": row[2],
        "multimodal": row[3],
        "text_provider": row[4],
        "text_model_name": row[5],
        "text_loader": row[6],
        "text_revision": row[7],
        "text_dimensions": row[8],
        "text_precision": row[9],
        "text_trust_remote_code": row[10],
        "image_provider": row[11],
        "image_model_name": row[12],
        "image_loader": row[13],
        "image_revision": row[14],
        "image_dimensions": row[15],
        "image_precision": row[16],
        "image_trust_remote_code": row[17],
        "device": row[18],
        "max_memory_mb": row[19],
        "num_threads": row[20],
        "batch_size": row[21],
        "max_seq_length": row[22],
        "normalize_embeddings": row[23],
        "active": row[24],
        "delete_protected": row[25],
        "change_protected": row[26],
        "created_at": row[27],
        "updated_at": row[28],
        "updated_by": row[29],
        # Backward-compat aliases used by model manager and routes
        "provider": row[4],            # text_provider
        "model_name": row[5],          # text_model_name
        "embedding_dimensions": row[8], # text_dimensions
        "precision": row[9],           # text_precision
    }


def load_active_embedding_config() -> Optional[Dict[str, Any]]:
    """
    Load the active embedding profile from the database.

    Returns:
        Dict with all profile fields if found, None otherwise.
        Includes backward-compat aliases (provider, model_name, embedding_dimensions, precision).
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_PROFILE_COLUMNS}
                    FROM kg_api.embedding_profile
                    WHERE active = TRUE
                    LIMIT 1
                """)

                row = cur.fetchone()

                if not row:
                    logger.info("No active embedding profile in database")
                    return None

                config = _row_to_dict(row)
                logger.info(
                    f"Loaded embedding profile: {config['name']} "
                    f"({config['text_provider']} / {config['text_model_name']})"
                )
                return config

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to load embedding profile from database: {e}")
        return None


def save_embedding_config(config: Dict[str, Any], updated_by: str = "api", force_change: bool = False) -> tuple:
    """
    Create a new embedding profile (inactive by default).

    Accepts either new-style profile fields (text_provider, text_model_name, ...)
    or old-style shorthand (provider, model_name, embedding_dimensions).

    Returns:
        Tuple of (success, error_message, config_id)
    """
    from .age_client import AGEClient

    # Resolve shorthand → explicit profile fields
    text_provider = config.get('text_provider') or config.get('provider')
    text_model_name = config.get('text_model_name') or config.get('model_name')
    text_dimensions = config.get('text_dimensions') or config.get('embedding_dimensions')
    text_precision = config.get('text_precision') or config.get('precision', 'float16')
    text_trust_remote_code = config.get('text_trust_remote_code', False)
    multimodal = config.get('multimodal', False)

    # Auto-infer loader from provider if not specified
    text_loader = config.get('text_loader')
    if not text_loader:
        if text_provider == 'openai':
            text_loader = 'api'
        else:
            text_loader = 'sentence-transformers'

    # Auto-generate name if not provided
    name = config.get('name')
    if not name:
        name = f"{text_provider}/{text_model_name}" if text_model_name else text_provider

    # Auto-infer vector_space if not provided
    vector_space = config.get('vector_space')
    if not vector_space:
        if text_model_name:
            # Derive from model name: "nomic-ai/nomic-embed-text-v1.5" → "nomic-v1.5"
            vector_space = text_model_name.split('/')[-1].replace('nomic-embed-text-', 'nomic-').replace('text-embedding-3-', 'openai-v3-')
        else:
            vector_space = f"{text_provider}-default"

    # Image slot
    image_provider = config.get('image_provider')
    image_model_name = config.get('image_model_name')
    image_loader = config.get('image_loader')
    image_revision = config.get('image_revision')
    image_dimensions = config.get('image_dimensions')
    image_precision = config.get('image_precision', 'float16')
    image_trust_remote_code = config.get('image_trust_remote_code', False)

    # Multimodal: clear image fields
    if multimodal:
        image_provider = None
        image_model_name = None
        image_loader = None
        image_revision = None
        image_dimensions = None
        image_precision = None
        image_trust_remote_code = False

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("BEGIN")

                cur.execute("""
                    INSERT INTO kg_api.embedding_profile (
                        name, vector_space, multimodal,
                        text_provider, text_model_name, text_loader, text_revision,
                        text_dimensions, text_precision, text_trust_remote_code,
                        image_provider, image_model_name, image_loader, image_revision,
                        image_dimensions, image_precision, image_trust_remote_code,
                        device, max_memory_mb, num_threads, batch_size,
                        max_seq_length, normalize_embeddings,
                        updated_by, active
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, FALSE
                    )
                    RETURNING id
                """, (
                    name, vector_space, multimodal,
                    text_provider, text_model_name, text_loader, config.get('text_revision'),
                    text_dimensions, text_precision, text_trust_remote_code,
                    image_provider, image_model_name, image_loader, image_revision,
                    image_dimensions, image_precision, image_trust_remote_code,
                    config.get('device', 'cpu'), config.get('max_memory_mb'),
                    config.get('num_threads'), config.get('batch_size', 8),
                    config.get('max_seq_length'), config.get('normalize_embeddings', True),
                    updated_by
                ))

                new_config_id = cur.fetchone()[0]
                cur.execute("COMMIT")

                logger.info(
                    f"Created embedding profile {new_config_id} (inactive): "
                    f"{name} ({text_provider} / {text_model_name or 'N/A'})"
                )
                return (True, "", new_config_id)

        except Exception as e:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise e
        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to save embedding profile: {e}")
        return (False, str(e), 0)


def get_embedding_config_summary() -> Dict[str, Any]:
    """
    Get a summary of the current embedding configuration.

    Returns dict suitable for public API responses including both text and image info.
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
            "vector_space": None,
            "multimodal": None,
            "image_model": None,
            "image_dimensions": None,
            "resource_allocation": None
        }

    # Determine if model supports browser-side embeddings
    supports_browser = False
    if config['text_provider'] == 'local':
        model = config.get('text_model_name', '')
        if 'nomic' in model.lower() or 'bge' in model.lower():
            supports_browser = True

    # Image model info
    image_model = None
    image_dimensions = None
    if config['multimodal']:
        # Multimodal: text model serves both roles
        image_model = config['text_model_name']
        image_dimensions = config['text_dimensions']
    elif config.get('image_model_name'):
        image_model = config['image_model_name']
        image_dimensions = config.get('image_dimensions')

    return {
        "provider": config['text_provider'],
        "model": config.get('text_model_name'),
        "dimensions": config.get('text_dimensions'),
        "precision": config.get('text_precision'),
        "config_id": config['id'],
        "supports_browser": supports_browser,
        "vector_space": config.get('vector_space'),
        "multimodal": config.get('multimodal'),
        "image_model": image_model,
        "image_dimensions": image_dimensions,
        "resource_allocation": {
            "max_memory_mb": config.get('max_memory_mb'),
            "num_threads": config.get('num_threads'),
            "device": config.get('device'),
            "batch_size": config.get('batch_size')
        } if config['text_provider'] == 'local' else None
    }


def list_all_embedding_configs() -> list:
    """
    List all embedding profiles (active and inactive).

    Returns:
        List of profile dicts with all fields including protection flags.
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_PROFILE_COLUMNS}
                    FROM kg_api.embedding_profile
                    ORDER BY id DESC
                """)

                rows = cur.fetchall()
                return [_row_to_dict(row) for row in rows]

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to list embedding profiles: {e}")
        return []


def set_embedding_config_protection(config_id: int, delete_protected: bool = None, change_protected: bool = None) -> bool:
    """
    Set or remove protection flags on an embedding profile.

    Args:
        config_id: Database ID of the profile
        delete_protected: Set delete protection (None = no change)
        change_protected: Set change protection (None = no change)

    Returns:
        True if updated successfully, False otherwise
    """
    from .age_client import AGEClient

    if delete_protected is None and change_protected is None:
        return True

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
                    UPDATE kg_api.embedding_profile
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)

                conn.commit()
                return True

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to update protection flags: {e}")
        return False


def check_embedding_config_protection(config_id: int) -> Dict[str, bool]:
    """
    Check protection status of an embedding profile.

    Args:
        config_id: Database ID of the profile

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
                    FROM kg_api.embedding_profile
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


def delete_embedding_config(config_id: int) -> tuple:
    """
    Delete an embedding profile (if not protected).

    Returns:
        Tuple of (success, error_message)
    """
    from .age_client import AGEClient

    try:
        protection = check_embedding_config_protection(config_id)

        if protection["delete_protected"]:
            return (False, "Profile is delete-protected. Remove protection first with: kg admin embedding unprotect --delete")

        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.embedding_profile
                    WHERE id = %s
                """, (config_id,))

                if cur.rowcount == 0:
                    return (False, f"Profile {config_id} not found")

                conn.commit()
                logger.info(f"Deleted embedding profile {config_id}")
                return (True, "")

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to delete embedding profile: {e}")
        return (False, str(e))


def activate_embedding_config(config_id: int, updated_by: str = "api", force_dimension_change: bool = False) -> tuple:
    """
    Activate an embedding profile with automatic protection management.

    Workflow:
    1. Unprotect currently active profile (change protection)
    2. Deactivate current profile
    3. Activate new profile
    4. Protect new profile (both delete and change protection)

    Args:
        config_id: Database ID of the profile to activate
        updated_by: User/admin who made the change
        force_dimension_change: Bypass dimension mismatch check

    Returns:
        Tuple of (success, error_message)
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute("BEGIN")

                # Check if target profile exists
                cur.execute("""
                    SELECT id, text_provider, text_model_name, text_dimensions,
                           multimodal, image_dimensions
                    FROM kg_api.embedding_profile
                    WHERE id = %s
                """, (config_id,))

                target_row = cur.fetchone()

                if not target_row:
                    cur.execute("ROLLBACK")
                    return (False, f"Profile {config_id} not found")

                target_id, target_provider, target_model, target_dims, target_multimodal, target_img_dims = target_row

                # Validate image/text dimension consistency for non-multimodal profiles
                if not target_multimodal and target_img_dims is not None and target_dims != target_img_dims:
                    cur.execute("ROLLBACK")
                    return (False,
                        f"Profile {config_id} has mismatched text ({target_dims}D) and image ({target_img_dims}D) dimensions. "
                        "Text and image dimensions must match for non-multimodal profiles.")

                # Get currently active profile
                cur.execute("""
                    SELECT id, text_provider, text_dimensions, change_protected
                    FROM kg_api.embedding_profile
                    WHERE active = TRUE
                """)

                active_row = cur.fetchone()

                if active_row:
                    active_id, active_provider, active_dims, change_protected = active_row

                    # Check if dimensions are changing
                    if target_dims != active_dims and not force_dimension_change:
                        cur.execute("ROLLBACK")
                        return (False,
                            f"Cannot switch: dimension mismatch ({active_dims}D -> {target_dims}D). "
                            "Changing embedding dimensions breaks vector search for all existing concepts. "
                            "You must re-embed all concepts after switching. "
                            "Use --force to bypass this check (dangerous!). "
                            "See ADR-039 for migration procedures.")

                    # Unprotect current profile
                    if change_protected:
                        cur.execute("""
                            UPDATE kg_api.embedding_profile
                            SET change_protected = FALSE
                            WHERE id = %s
                        """, (active_id,))

                # Deactivate all profiles
                cur.execute("""
                    UPDATE kg_api.embedding_profile
                    SET active = FALSE
                    WHERE active = TRUE
                """)

                # Activate target profile
                cur.execute("""
                    UPDATE kg_api.embedding_profile
                    SET active = TRUE, updated_at = CURRENT_TIMESTAMP, updated_by = %s
                    WHERE id = %s
                """, (updated_by, config_id))

                # Protect the newly activated profile
                cur.execute("""
                    UPDATE kg_api.embedding_profile
                    SET delete_protected = TRUE, change_protected = TRUE
                    WHERE id = %s
                """, (config_id,))

                # Mark vocabulary embeddings as stale
                if active_row:
                    cur.execute("""
                        UPDATE kg_api.relationship_vocabulary
                        SET embedding_validation_status = 'stale'
                        WHERE embedding IS NOT NULL
                          AND embedding_validation_status != 'stale'
                    """)
                    stale_count = cur.rowcount
                    if stale_count > 0:
                        logger.warning(f"Marked {stale_count} vocabulary embeddings as stale")

                cur.execute("COMMIT")

                logger.info(f"Activated profile {config_id}: {target_provider} / {target_model}")

                if active_row:
                    logger.warning(
                        "EMBEDDING MODEL CHANGED - Regenerate vocabulary and concept embeddings."
                    )

                return (True, "")

        except Exception as e:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise e
        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to activate embedding profile: {e}")
        return (False, str(e))


def get_embedding_profile_by_id(profile_id: int) -> Optional[Dict[str, Any]]:
    """
    Load a specific embedding profile by ID.

    Returns:
        Dict with all profile fields, or None if not found.
    """
    from .age_client import AGEClient

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_PROFILE_COLUMNS}
                    FROM kg_api.embedding_profile
                    WHERE id = %s
                """, (profile_id,))

                row = cur.fetchone()
                if not row:
                    return None
                return _row_to_dict(row)

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"Failed to load embedding profile {profile_id}: {e}")
        return None


def export_embedding_profile(profile_id: int) -> Optional[Dict[str, Any]]:
    """
    Export a profile as a JSON-serializable dict (profile + metadata sections).

    Returns:
        Dict with 'profile' and 'metadata' keys, or None if not found.
    """
    config = get_embedding_profile_by_id(profile_id)
    if not config:
        return None

    result = {
        "profile": {
            "name": config["name"],
            "vector_space": config["vector_space"],
            "multimodal": config["multimodal"],
            "text": {
                "provider": config["text_provider"],
                "model_name": config["text_model_name"],
                "loader": config["text_loader"],
                "revision": config.get("text_revision"),
                "dimensions": config["text_dimensions"],
                "precision": config.get("text_precision"),
                "trust_remote_code": config.get("text_trust_remote_code", False),
            },
            "resources": {
                "device": config.get("device"),
                "max_memory_mb": config.get("max_memory_mb"),
                "num_threads": config.get("num_threads"),
                "batch_size": config.get("batch_size"),
                "max_seq_length": config.get("max_seq_length"),
                "normalize_embeddings": config.get("normalize_embeddings"),
            },
        },
        "metadata": {
            "id": config["id"],
            "active": config["active"],
            "delete_protected": config.get("delete_protected", False),
            "change_protected": config.get("change_protected", False),
            "created_at": config["created_at"].isoformat() if hasattr(config["created_at"], 'isoformat') else str(config["created_at"]),
            "updated_at": config["updated_at"].isoformat() if hasattr(config["updated_at"], 'isoformat') else str(config["updated_at"]),
            "updated_by": config.get("updated_by"),
        },
    }

    # Add image section for non-multimodal profiles with image config
    if not config["multimodal"] and config.get("image_model_name"):
        result["profile"]["image"] = {
            "provider": config["image_provider"],
            "model_name": config["image_model_name"],
            "loader": config["image_loader"],
            "revision": config.get("image_revision"),
            "dimensions": config["image_dimensions"],
            "precision": config.get("image_precision"),
            "trust_remote_code": config.get("image_trust_remote_code", False),
        }

    return result
