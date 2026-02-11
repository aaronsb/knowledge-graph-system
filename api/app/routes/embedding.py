"""
Embedding Profile Routes

API endpoints for embedding profile management (ADR-039 + migration 055).

Public endpoints:
- GET /embedding/config - Get embedding configuration summary

Admin endpoints:
- GET /admin/embedding/config - Get full profile details
- GET /admin/embedding/configs - List all profiles
- POST /admin/embedding/config - Create profile
- POST /admin/embedding/config/reload - Hot reload model
- GET /admin/embedding/export/{id} - Export profile as JSON
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from ..dependencies.auth import CurrentUser, require_permission
from ..models.embedding import (
    EmbeddingConfigResponse,
    EmbeddingProfileDetail,
    EmbeddingProfileCreateRequest,
    UpdateEmbeddingConfigResponse,
    ReloadEmbeddingModelResponse
)
from ..lib.embedding_config import (
    load_active_embedding_config,
    save_embedding_config,
    get_embedding_config_summary,
    list_all_embedding_configs,
    set_embedding_config_protection,
    delete_embedding_config,
    activate_embedding_config,
    export_embedding_profile
)

# Public router (no auth)
public_router = APIRouter(prefix="/embedding", tags=["embedding"])

# Admin router (requires auth in production)
admin_router = APIRouter(prefix="/admin/embedding", tags=["admin", "embedding"])

logger = logging.getLogger(__name__)


@public_router.get("/config", response_model=EmbeddingConfigResponse)
async def get_embedding_config():
    """
    Get current embedding configuration (public endpoint).

    Returns summary information suitable for clients to determine:
    - Which embedding provider is active
    - Model dimensions (for compatibility checks)
    - Whether browser-side embeddings are supported

    This endpoint does not require authentication.
    """
    try:
        summary = get_embedding_config_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding config: {str(e)}"
        )


@admin_router.get("/config", response_model=Optional[EmbeddingProfileDetail])
async def get_embedding_config_detail(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "read"))
):
    """
    Get full embedding profile details

    Returns complete profile including:
    - Text and image model configuration
    - All resource allocation settings
    - Metadata (created_at, updated_by, etc.)
    - Profile ID

    Returns null if no profile is active.

    **Authorization:** Requires `embedding_config:read` permission
    """
    try:
        config = load_active_embedding_config()
        return config
    except Exception as e:
        logger.error(f"Failed to get embedding profile details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding profile: {str(e)}"
        )


@admin_router.post("/config", response_model=UpdateEmbeddingConfigResponse)
async def create_embedding_config(
    request: EmbeddingProfileCreateRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "create"))
):
    """
    Create a new embedding profile (inactive by default)

    Supports both shorthand (provider/model) and full profile fields (text_*/image_*).

    **Workflow:**
    1. Create profile: POST /admin/embedding/config (this endpoint)
    2. Review: GET /admin/embedding/configs
    3. Activate: POST /admin/embedding/config/{id}/activate
    4. Hot reload: POST /admin/embedding/config/reload

    **Example (shorthand):**
    ```json
    {
        "provider": "local",
        "model_name": "nomic-ai/nomic-embed-text-v1.5",
        "embedding_dimensions": 768
    }
    ```

    **Example (full profile):**
    ```json
    {
        "name": "My Custom Profile",
        "vector_space": "custom-v1",
        "text_provider": "local",
        "text_model_name": "nomic-ai/nomic-embed-text-v1.5",
        "text_dimensions": 768,
        "image_provider": "local",
        "image_model_name": "nomic-ai/nomic-embed-vision-v1.5",
        "image_dimensions": 768
    }
    ```

    **Authorization:** Requires `embedding_config:create` permission
    """
    try:
        # Resolve effective provider (explicit text_provider or shorthand)
        effective_provider = request.text_provider or request.provider
        effective_model = request.text_model_name or request.model_name

        if not effective_provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify provider (or text_provider)"
            )

        if effective_provider not in ['openai', 'local']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {effective_provider}. Must be 'openai' or 'local'"
            )

        if effective_provider == 'local' and not effective_model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="provider='local' requires model_name (or text_model_name)"
            )

        # Validate multimodal consistency
        if request.multimodal and request.image_model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="multimodal=true: image fields must be absent (text model serves both roles)"
            )

        # Validate dimension match for non-multimodal with image
        if not request.multimodal and request.image_dimensions:
            text_dims = request.text_dimensions or request.embedding_dimensions
            if text_dims and text_dims != request.image_dimensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dimension mismatch: text={text_dims}, image={request.image_dimensions}. Must match for non-multimodal profiles."
                )

        # Validate precision
        text_precision = request.text_precision
        if text_precision and text_precision not in ['float16', 'float32']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid precision: {text_precision}. Must be 'float16' or 'float32'"
            )

        # Validate device
        if request.device and request.device not in ['cpu', 'cuda', 'mps']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid device: {request.device}. Must be 'cpu', 'cuda', or 'mps'"
            )

        # Create profile (inactive by default)
        config_dict = request.model_dump(exclude_none=True)
        success, error_msg, config_id = save_embedding_config(config_dict, updated_by=request.updated_by or "api")

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST if "protected" in error_msg.lower() else status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg or "Failed to create embedding profile"
            )

        logger.info(f"Embedding profile created (ID {config_id}, inactive): {effective_provider} / {effective_model or 'N/A'}")

        return UpdateEmbeddingConfigResponse(
            success=True,
            message=f"Profile created (ID {config_id}, inactive). Use 'kg admin embedding activate {config_id}' to switch.",
            config_id=config_id,
            reload_required=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create embedding profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create embedding profile: {str(e)}"
        )


@admin_router.post("/config/reload", response_model=ReloadEmbeddingModelResponse)
async def reload_embedding_model(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "reload"))
):
    """
    Hot reload embedding model without API restart

    Implements zero-downtime configuration updates:
    1. Load new config from database
    2. Initialize new model in parallel (old model still serves requests)
    3. Atomic swap to new model
    4. In-flight requests complete with old model
    5. Old model garbage collected automatically

    Note: Brief 2x memory usage during model loading (1-2 seconds for 300MB-1.3GB models).

    For provider switches:
    - local → openai: Unloads local model, switches to OpenAI API
    - openai → local: Loads local model from database config
    - local → local (different model): Hot swaps to new model

    Returns success with new provider details.

    **Authorization:** Requires `embedding_config:reload` permission

    Example response:
    ```json
    {
        "success": true,
        "message": "Embedding model reloaded successfully",
        "provider": "local",
        "model": "nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768
    }
    ```
    """
    try:
        from ..lib.embedding_model_manager import reload_embedding_model_manager
        from ..services.embedding_worker import reset_embedding_worker

        # Hot reload the model manager
        manager = await reload_embedding_model_manager()

        # Reset EmbeddingWorker singleton so it picks up the new provider
        reset_embedding_worker()
        logger.info("🔄 Reset EmbeddingWorker singleton to pick up new provider")

        # Get new configuration summary
        summary = get_embedding_config_summary()

        # Auto-protect: Re-enable change protection on the new active config
        # This prevents accidental changes after a successful reload
        config = load_active_embedding_config()
        if config:
            set_embedding_config_protection(config['id'], change_protected=True)
            logger.info(f"🔒 Auto-protected config {config['id']} after hot reload")

        logger.info(f"✅ Embedding model hot reload successful: {summary['provider']}")

        return ReloadEmbeddingModelResponse(
            success=True,
            message="Embedding model reloaded successfully (config auto-protected)",
            provider=summary['provider'],
            model=summary.get('model'),
            dimensions=summary.get('dimensions')
        )

    except Exception as e:
        logger.error(f"❌ Embedding model hot reload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hot reload failed: {str(e)}"
        )


@admin_router.get("/configs", response_model=list)
async def list_embedding_configs(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "read"))
):
    """
    List all embedding configurations

    Returns all configs (active and inactive) with protection flags.
    Use this to see all historical configurations.

    **Authorization:** Requires `embedding_config:read` permission
    """
    try:
        configs = list_all_embedding_configs()
        return configs
    except Exception as e:
        logger.error(f"Failed to list embedding configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list configs: {str(e)}"
        )


@admin_router.get("/export/{profile_id}")
async def export_embedding_profile_endpoint(
    profile_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "read")),
    profile_only: bool = False
):
    """
    Export an embedding profile as JSON

    Returns a JSON document with profile configuration and metadata.
    Can be imported via POST /admin/embedding/config with --from-json.

    **Authorization:** Requires `embedding_config:read` permission

    Query Parameters:
    - profile_only: If true, strips metadata (id, timestamps, etc.)
    """
    try:
        result = export_embedding_profile(profile_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile {profile_id} not found"
            )

        if profile_only:
            return result["profile"]

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export embedding profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export profile: {str(e)}"
        )


@admin_router.post("/config/{config_id}/protect")
async def protect_embedding_config(
    config_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "create")),
    delete_protected: Optional[bool] = None,
    change_protected: Optional[bool] = None
):
    """
    Set protection flags on an embedding configuration

    Protection flags prevent accidental breaking changes:
    - delete_protected: Prevents deletion without explicit unprotect
    - change_protected: Prevents changing provider/dimensions (breaks vector search)

    **Authorization:** Requires `embedding_config:create` permission

    Example:
    ```json
    {
        "delete_protected": true,
        "change_protected": true
    }
    ```
    """
    try:
        if delete_protected is None and change_protected is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify at least one protection flag"
            )

        success = set_embedding_config_protection(
            config_id,
            delete_protected=delete_protected,
            change_protected=change_protected
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Config {config_id} not found"
            )

        return {"success": True, "config_id": config_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set protection flags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set protection: {str(e)}"
        )


@admin_router.delete("/config/{config_id}")
async def delete_embedding_config_endpoint(
    config_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "delete"))
):
    """
    Delete an embedding configuration

    Cannot delete configs that are delete-protected.
    Remove protection first if needed.

    **Authorization:** Requires `embedding_config:delete` permission
    """
    try:
        success, error_msg = delete_embedding_config(config_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST if "protected" in error_msg.lower() else status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        return {"success": True, "config_id": config_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete config: {str(e)}"
        )


@admin_router.post("/config/{config_id}/activate")
async def activate_embedding_config_endpoint(
    config_id: int,
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "activate")),
    force: bool = False
):
    """
    Activate an embedding configuration with automatic protection management

    This provides a clean "unlock → activate → lock" workflow:
    1. Unprotects currently active config (change protection)
    2. Deactivates current config
    3. Activates target config
    4. Protects target config (both delete and change protection)

    **Safety checks:**
    - Prevents switching between configs with different embedding dimensions
    - Changing dimensions breaks vector search for all existing concepts
    - Use `?force=true` to bypass dimension check (dangerous!)

    **Example workflow:**
    ```bash
    # List available configs
    kg admin embedding list

    # Activate a preset (e.g., nomic-embed-text-v1.5)
    kg admin embedding activate 3

    # Force activation with dimension mismatch (use with caution!)
    kg admin embedding activate 3 --force

    # Hot reload to apply changes
    kg admin embedding reload
    ```

    **Authorization:** Requires `embedding_config:activate` permission

    Query Parameters:
    - force: Bypass dimension mismatch check (default: false)

    Returns:
    - success: True if activation successful
    - config_id: ID of activated config
    - message: Next steps (hot reload recommended)
    """
    try:
        success, error_msg = activate_embedding_config(config_id, updated_by="api", force_dimension_change=force)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

        # Get the activated profile details
        config = load_active_embedding_config()

        return {
            "success": True,
            "config_id": config_id,
            "message": "Profile activated successfully. Run 'kg admin embedding reload' to apply changes.",
            "provider": config.get('text_provider') if config else None,
            "model": config.get('text_model_name') if config else None,
            "dimensions": config.get('text_dimensions') if config else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate embedding config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate config: {str(e)}"
        )


@admin_router.get("/status")
async def get_embedding_status(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "read")),
    ontology: Optional[str] = None
):
    """
    Get comprehensive embedding status report for all graph text entities.

    Shows count, percentage, and compatibility status for embeddings across:
    - Concepts (AGE graph nodes)
    - Sources (source_embeddings table with stale/incompatible detection)
    - Vocabulary (relationship types)
    - Images (future - ADR-057)

    **Authorization:** Requires `embedding_config:read` permission

    Args:
        ontology: Limit to specific ontology (optional, applies to concepts/sources only)

    Returns:
        Detailed embedding status with counts, percentages, compatibility verification

    **Compatibility Check:**
    Detects embeddings that don't match the active embedding configuration:
    - Model mismatch (e.g., OpenAI vs local)
    - Dimension mismatch (e.g., 1536 vs 768)
    - Reports as "incompatible_embeddings" requiring regeneration

    **Example Usage:**

    ```bash
    # Get global embedding status
    curl http://localhost:8000/admin/embedding/status

    # Get status for specific ontology
    curl http://localhost:8000/admin/embedding/status?ontology=MyDocs
    ```
    """
    try:
        from ..workers.source_embedding_worker import get_embedding_status

        logger.info(f"Getting embedding status (ontology={ontology})")

        embedding_status = await get_embedding_status(ontology=ontology)

        return {
            "success": True,
            "ontology": ontology,
            **embedding_status
        }

    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding status: {str(e)}"
        )


@admin_router.post("/regenerate")
async def regenerate_embeddings(
    current_user: CurrentUser,
    _: None = Depends(require_permission("embedding_config", "regenerate")),
    embedding_type: str = "concept",
    only_missing: bool = False,
    only_incompatible: bool = False,
    ontology: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Unified embedding regeneration for all graph text entities (ADR-068 Phase 4).

    Regenerate embeddings for concept nodes, source text chunks, or vocabulary
    (relationship types). Useful for model migrations, fixing missing/corrupted
    embeddings, or updating incompatible embeddings.

    **Authorization:** Requires `embedding_config:regenerate` permission

    Args:
        embedding_type: Type of embeddings to regenerate: 'concept', 'source', 'vocabulary', 'all'
        only_missing: Only generate for entities without embeddings
        only_incompatible: Only regenerate embeddings with mismatched model/dimensions
        ontology: Limit to specific ontology (concept/source only)
        limit: Maximum number of entities to process (for testing/batching)

    Returns:
        Job result with statistics

    **Example Usage:**

    ```bash
    # Model migration - regenerate ALL embeddings
    curl -X POST http://localhost:8000/admin/embedding/regenerate?embedding_type=all

    # Regenerate missing source embeddings only
    curl -X POST http://localhost:8000/admin/embedding/regenerate?embedding_type=source&only_missing=true

    # Regenerate incompatible embeddings (after model switch)
    curl -X POST http://localhost:8000/admin/embedding/regenerate?embedding_type=source&only_incompatible=true
    ```
    """
    try:
        # Validate embedding_type
        valid_types = ["concept", "source", "vocabulary", "all"]
        if embedding_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid embedding_type. Must be one of: {', '.join(valid_types)}"
            )

        # Validate flag combination
        if only_missing and only_incompatible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot use both --only-missing and --only-incompatible flags together"
            )

        logger.info(
            f"Starting {embedding_type} embedding regeneration "
            f"(only_missing={only_missing}, only_incompatible={only_incompatible}, "
            f"ontology={ontology}, limit={limit})"
        )

        # Handle 'all' type - regenerate everything
        if embedding_type == "all":
            from ..services.embedding_worker import get_embedding_worker
            from ..lib.ai_providers import get_embedding_provider
            from ..workers.source_embedding_worker import regenerate_source_embeddings
            from ..lib.age_client import AGEClient

            # Get embedding worker
            worker = get_embedding_worker()
            if worker is None:
                age_client = AGEClient()
                embedding_provider = get_embedding_provider()
                worker = get_embedding_worker(age_client, embedding_provider)

                if worker is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Embedding worker not initialized"
                    )

            # Regenerate all three types
            results = {}

            # 1. Concepts
            logger.info("Regenerating concept embeddings...")
            concept_result = await worker.regenerate_concept_embeddings(
                only_missing=only_missing,
                ontology=ontology,
                limit=limit
            )
            results["concepts"] = {
                "job_id": concept_result.job_id,
                "target_count": concept_result.target_count,
                "processed_count": concept_result.processed_count,
                "failed_count": concept_result.failed_count,
                "duration_ms": concept_result.duration_ms
            }

            # 2. Sources
            logger.info("Regenerating source embeddings...")
            source_result = await regenerate_source_embeddings(
                only_missing=only_missing,
                only_incompatible=only_incompatible,
                ontology=ontology,
                limit=limit
            )
            results["sources"] = {
                "job_id": source_result["job_id"],
                "target_count": source_result["target_count"],
                "processed_count": source_result["processed_count"],
                "failed_count": source_result["failed_count"],
                "duration_ms": source_result["duration_ms"]
            }

            # 3. Vocabulary
            logger.info("Regenerating vocabulary embeddings...")
            vocab_result = await worker.regenerate_all_embeddings(
                only_missing=only_missing
            )
            results["vocabulary"] = {
                "job_id": vocab_result.job_id,
                "target_count": vocab_result.target_count,
                "processed_count": vocab_result.processed_count,
                "failed_count": vocab_result.failed_count,
                "duration_ms": vocab_result.duration_ms
            }

            # Calculate totals
            total_target = sum(r["target_count"] for r in results.values())
            total_processed = sum(r["processed_count"] for r in results.values())
            total_failed = sum(r["failed_count"] for r in results.values())
            total_duration = sum(r["duration_ms"] for r in results.values())

            return {
                "success": True,
                "embedding_type": "all",
                "results": results,
                "totals": {
                    "target_count": total_target,
                    "processed_count": total_processed,
                    "failed_count": total_failed,
                    "duration_ms": total_duration
                }
            }

        # Handle specific types
        elif embedding_type == "concept":
            from ..services.embedding_worker import get_embedding_worker
            from ..lib.ai_providers import get_embedding_provider
            from ..lib.age_client import AGEClient

            worker = get_embedding_worker()
            if worker is None:
                age_client = AGEClient()
                embedding_provider = get_embedding_provider()
                worker = get_embedding_worker(age_client, embedding_provider)

                if worker is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Embedding worker not initialized"
                    )

            result = await worker.regenerate_concept_embeddings(
                only_missing=only_missing,
                ontology=ontology,
                limit=limit
            )

            return {
                "success": True,
                "embedding_type": "concept",
                "job_id": result.job_id,
                "target_count": result.target_count,
                "processed_count": result.processed_count,
                "failed_count": result.failed_count,
                "duration_ms": result.duration_ms,
                "embedding_model": result.embedding_model,
                "embedding_provider": result.embedding_provider,
                "errors": result.errors if result.errors else []
            }

        elif embedding_type == "source":
            from ..workers.source_embedding_worker import regenerate_source_embeddings

            result = await regenerate_source_embeddings(
                only_missing=only_missing,
                only_incompatible=only_incompatible,
                ontology=ontology,
                limit=limit
            )

            return {
                "success": True,
                "embedding_type": "source",
                **result
            }

        elif embedding_type == "vocabulary":
            from ..services.embedding_worker import get_embedding_worker
            from ..lib.ai_providers import get_embedding_provider
            from ..lib.age_client import AGEClient

            worker = get_embedding_worker()
            if worker is None:
                age_client = AGEClient()
                embedding_provider = get_embedding_provider()
                worker = get_embedding_worker(age_client, embedding_provider)

                if worker is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Embedding worker not initialized"
                    )

            result = await worker.regenerate_all_embeddings(
                only_missing=only_missing
            )

            return {
                "success": True,
                "embedding_type": "vocabulary",
                "job_id": result.job_id,
                "target_count": result.target_count,
                "processed_count": result.processed_count,
                "failed_count": result.failed_count,
                "duration_ms": result.duration_ms,
                "embedding_model": result.embedding_model,
                "embedding_provider": result.embedding_provider,
                "errors": result.errors if result.errors else []
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate {embedding_type} embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate {embedding_type} embeddings: {str(e)}"
        )
