"""
Vocabulary management endpoints for ADR-032 automatic edge vocabulary expansion.

Provides REST API access to:
- Vocabulary status and statistics
- Edge type CRUD operations
- Pruning recommendations (HITL workflow)
- Configuration management
- Analysis and insights
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging
import os

from ..models.vocabulary import (
    # Status and info
    VocabularyStatusResponse,
    EdgeTypeListResponse,
    EdgeTypeInfo,
    AddEdgeTypeRequest,

    # Recommendations
    RecommendationsResponse,
    ActionRecommendationResponse,
    ApproveRecommendationRequest,
    ExecutionResultResponse,

    # Analysis
    VocabularyAnalysisResponse,
    EdgeTypeScoreResponse,
    SynonymCandidateResponse,

    # Configuration
    VocabularyConfigResponse,
    UpdateConfigRequest,

    # History
    VocabularyHistoryResponse,
    VocabularyHistoryEntry,

    # Merge/Restore
    MergeEdgeTypesRequest,
    MergeEdgeTypesResponse,
    RestoreEdgeTypeRequest,
    RestoreEdgeTypeResponse,

    # Embeddings
    GenerateEmbeddingsRequest,

    # Similarity Analysis (ADR-053)
    SimilarEdgeType,
    VocabularySimilarityResponse,
    VocabularyAnalysisDetailResponse,
    GenerateEmbeddingsResponse,

    # Category Scoring (ADR-047)
    CategoryScoresResponse,
    RefreshCategoriesRequest,
    RefreshCategoriesResponse,

    # AITL Consolidation
    ConsolidateVocabularyRequest,
    ConsolidateVocabularyResponse,
    MergeResultInfo,
    ReviewInfo,
    RejectionInfo,

    # Enums
    ZoneEnum,
    PruningModeEnum,
    ActionTypeEnum,
    ReviewLevelEnum,
)

from src.api.lib.age_client import AGEClient
from src.api.lib.ai_providers import get_provider
from src.api.services.vocabulary_manager import VocabularyManager
from src.api.lib.aggressiveness_curve import calculate_aggressiveness

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


def get_vocabulary_manager() -> VocabularyManager:
    """Get VocabularyManager instance with current configuration"""
    client = AGEClient()
    provider = get_provider()

    # Get configuration from database (with .env fallback)
    mode = client.get_vocab_config('pruning_mode') or os.getenv("VOCAB_PRUNING_MODE", "aitl")
    profile = client.get_vocab_config('aggressiveness_profile') or os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")

    return VocabularyManager(
        db_client=client,
        ai_provider=provider,
        mode=mode,
        aggressiveness_profile=profile
    )


# =============================================================================
# Status and Information Endpoints
# =============================================================================

@router.get("/status", response_model=VocabularyStatusResponse)
async def get_vocabulary_status():
    """
    Get current vocabulary status including size, zone, and aggressiveness.

    Returns:
        VocabularyStatusResponse with current state

    Example:
        GET /vocabulary/status
    """
    try:
        client = AGEClient()
        try:
            vocab_size = client.get_vocabulary_size()

            # Get configuration from database (with .env fallback)
            vocab_min = int(client.get_vocab_config('vocab_min') or os.getenv("VOCAB_MIN", "30"))
            vocab_max = int(client.get_vocab_config('vocab_max') or os.getenv("VOCAB_MAX", "90"))
            vocab_emergency = int(client.get_vocab_config('vocab_emergency') or os.getenv("VOCAB_EMERGENCY", "200"))
            profile = client.get_vocab_config('aggressiveness_profile') or os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")

            # Calculate aggressiveness
            aggressiveness, zone = calculate_aggressiveness(
                current_size=vocab_size,
                vocab_min=vocab_min,
                vocab_max=vocab_max,
                vocab_emergency=vocab_emergency,
                profile=profile
            )

            # Get type counts
            all_types = client.get_all_edge_types(include_inactive=True)
            active_types = client.get_all_edge_types(include_inactive=False)

            builtin_count = 0
            custom_count = 0
            for edge_type in active_types:
                info = client.get_edge_type_info(edge_type)
                if info and info.get("is_builtin"):
                    builtin_count += 1
                else:
                    custom_count += 1

            # Get category count
            category_dist = client.get_category_distribution()
            category_count = len(category_dist)

            return VocabularyStatusResponse(
                vocab_size=vocab_size,
                vocab_min=vocab_min,
                vocab_max=vocab_max,
                vocab_emergency=vocab_emergency,
                aggressiveness=aggressiveness,
                zone=ZoneEnum(zone),
                builtin_types=builtin_count,
                custom_types=custom_count,
                categories=category_count,
                profile=profile
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to get vocabulary status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get vocabulary status: {str(e)}")


@router.get("/types", response_model=EdgeTypeListResponse)
async def list_edge_types(
    include_inactive: bool = Query(False, description="Include inactive types"),
    include_builtin: bool = Query(True, description="Include builtin types")
):
    """
    List all edge types with statistics.

    Args:
        include_inactive: Include inactive/deprecated types
        include_builtin: Include builtin protected types

    Returns:
        EdgeTypeListResponse with list of types and counts

    Example:
        GET /vocabulary/types?include_inactive=false&include_builtin=true
    """
    try:
        client = AGEClient()
        try:
            all_types = client.get_all_edge_types(include_inactive=include_inactive)

            type_info_list = []
            builtin_count = 0
            custom_count = 0
            active_count = 0

            for edge_type in all_types:
                info = client.get_edge_type_info(edge_type)
                if not info:
                    continue

                # Skip builtin if requested
                if not include_builtin and info.get("is_builtin"):
                    continue

                # Count types
                if info.get("is_builtin"):
                    builtin_count += 1
                else:
                    custom_count += 1

                if info.get("is_active"):
                    active_count += 1

                type_info_list.append(EdgeTypeInfo(
                    relationship_type=info["relationship_type"],
                    category=info.get("category", "unknown"),
                    description=info.get("description"),
                    is_builtin=info.get("is_builtin", False),
                    is_active=info.get("is_active", True),
                    added_by=info.get("added_by", "unknown"),
                    added_at=info.get("added_at"),
                    usage_count=info.get("usage_count"),
                    edge_count=info.get("edge_count"),
                    avg_traversal=info.get("avg_traversal"),
                    last_used=info.get("last_used"),
                    value_score=info.get("value_score"),
                    # ADR-047: Category scoring fields
                    category_source=info.get("category_source"),
                    category_confidence=info.get("category_confidence"),
                    category_scores=info.get("category_scores"),
                    category_ambiguous=info.get("category_ambiguous")
                ))

            return EdgeTypeListResponse(
                total=len(type_info_list),
                active=active_count,
                builtin=builtin_count,
                custom=custom_count,
                types=type_info_list
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to list edge types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list edge types: {str(e)}")


@router.post("/types", response_model=EdgeTypeInfo)
async def add_edge_type(request: AddEdgeTypeRequest):
    """
    Manually add a new edge type (curator action).

    Args:
        request: Edge type details

    Returns:
        EdgeTypeInfo for the newly created type

    Example:
        POST /vocabulary/types
        {
            "relationship_type": "OPTIMIZES",
            "category": "functional",
            "description": "One concept optimizes another",
            "is_builtin": false
        }
    """
    try:
        client = AGEClient()
        try:
            # Add to vocabulary
            success = client.add_edge_type(
                relationship_type=request.relationship_type,
                category=request.category,
                description=request.description,
                added_by="manual_curator",
                is_builtin=request.is_builtin
            )

            if not success:
                raise HTTPException(
                    status_code=409,
                    detail=f"Edge type '{request.relationship_type}' already exists"
                )

            # Get full info
            info = client.get_edge_type_info(request.relationship_type)
            if not info:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve created edge type"
                )

            return EdgeTypeInfo(
                relationship_type=info["relationship_type"],
                category=info.get("category", "unknown"),
                description=info.get("description"),
                is_builtin=info.get("is_builtin", False),
                is_active=info.get("is_active", True),
                added_by=info.get("added_by", "unknown"),
                added_at=info.get("added_at")
            )

        finally:
            client.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add edge type: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add edge type: {str(e)}")


# =============================================================================
# Merge/Restore Endpoints
# =============================================================================

@router.post("/merge", response_model=MergeEdgeTypesResponse)
async def merge_edge_types(request: MergeEdgeTypesRequest):
    """
    Merge one edge type into another (curator action).

    Updates all edges to use the target type and marks the deprecated type as inactive.

    Args:
        request: Merge details

    Returns:
        MergeEdgeTypesResponse with results

    Example:
        POST /vocabulary/merge
        {
            "deprecated_type": "AUTHORED_BY",
            "target_type": "CREATED_BY",
            "performed_by": "curator@example.com",
            "reason": "Synonyms with 94% similarity"
        }
    """
    try:
        client = AGEClient()
        try:
            result = client.merge_edge_types(
                deprecated_type=request.deprecated_type,
                target_type=request.target_type,
                performed_by=request.performed_by
            )

            return MergeEdgeTypesResponse(
                success=True,
                deprecated_type=request.deprecated_type,
                target_type=request.target_type,
                edges_updated=result.get("edges_updated", 0),
                vocab_updated=result.get("vocab_updated", 0),
                message=f"Successfully merged {request.deprecated_type} into {request.target_type}"
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to merge edge types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to merge edge types: {str(e)}")


# =============================================================================
# AITL Consolidation Endpoint
# =============================================================================

@router.post("/consolidate", response_model=ConsolidateVocabularyResponse)
async def consolidate_vocabulary(request: ConsolidateVocabularyRequest):
    """
    Run AITL vocabulary consolidation workflow.

    Modes:
    - dry_run=True: Evaluate top candidates without executing (validation)
    - dry_run=False: Execute merges automatically based on confidence threshold

    Process:
    1. Get prioritized merge candidates (similarity-based)
    2. Evaluate each with LLM (synonym vs directional inverse)
    3. Auto-execute high confidence (≥ auto_execute_threshold)
    4. Flag medium confidence for human review
    5. Reject low confidence or inverse relationships

    Args:
        request: Consolidation parameters

    Returns:
        ConsolidateVocabularyResponse with results

    Example:
        POST /vocabulary/consolidate
        {
            "target_size": 80,
            "batch_size": 1,
            "auto_execute_threshold": 0.90,
            "dry_run": false
        }
    """
    try:
        manager = get_vocabulary_manager()
        client = AGEClient()

        try:
            # Get initial size
            initial_size = client.get_vocabulary_size()

            # Run consolidation
            results = await manager.aitl_consolidate_vocabulary(
                target_size=request.target_size,
                batch_size=request.batch_size,
                auto_execute_threshold=request.auto_execute_threshold,
                dry_run=request.dry_run
            )

            # Get size after consolidation (before pruning)
            size_after_consolidation = client.get_vocabulary_size()
            consolidation_reduction = initial_size - size_after_consolidation

            # Run pruning if requested (default: True)
            pruned_list = None
            pruned_count = 0
            if request.prune_unused and not request.dry_run:
                logger.info("Running post-consolidation pruning of unused types...")
                prune_results = await manager.prune_unused_concepts(dry_run=request.dry_run)
                pruned_list = prune_results['pruned']
                pruned_count = prune_results['pruned_count']
                logger.info(f"Pruned {pruned_count} unused types")
            elif request.prune_unused and request.dry_run:
                logger.info("Skipping pruning in dry-run mode")

            # Get final size (after consolidation + pruning)
            final_size = client.get_vocabulary_size()
            size_reduction = initial_size - final_size

            # Convert results to response models
            auto_executed = [
                MergeResultInfo(
                    deprecated=merge['deprecated'],
                    target=merge['target'],
                    similarity=merge['similarity'],
                    reasoning=merge['reasoning'],
                    blended_description=merge.get('blended_description'),
                    edges_affected=merge.get('edges_affected'),
                    edges_updated=merge.get('edges_updated'),
                    error=merge.get('error')
                )
                for merge in results['auto_executed']
            ]

            needs_review = [
                ReviewInfo(
                    type1=review['type1'],
                    type2=review['type2'],
                    suggested_term=review.get('suggested_term'),
                    suggested_description=review.get('suggested_description'),
                    similarity=review['similarity'],
                    reasoning=review['reasoning'],
                    edge_count1=review.get('edge_count1'),
                    edge_count2=review.get('edge_count2')
                )
                for review in results['needs_review']
            ]

            rejected = [
                RejectionInfo(
                    type1=reject['type1'],
                    type2=reject['type2'],
                    reasoning=reject['reasoning']
                )
                for reject in results['rejected']
            ]

            # Build message
            if request.dry_run:
                message = f"Dry run completed: Evaluated {len(auto_executed) + len(needs_review) + len(rejected)} candidates"
            else:
                if pruned_count > 0:
                    message = f"Consolidation completed: {size_reduction} types reduced ({initial_size} → {final_size}), including {pruned_count} pruned unused types"
                else:
                    message = f"Consolidation completed: {size_reduction} types reduced ({initial_size} → {final_size})"

            return ConsolidateVocabularyResponse(
                success=True,
                initial_size=initial_size,
                final_size=final_size,
                size_reduction=size_reduction,
                auto_executed=auto_executed,
                needs_review=needs_review,
                rejected=rejected,
                pruned=pruned_list,
                pruned_count=pruned_count,
                message=message
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to consolidate vocabulary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to consolidate vocabulary: {str(e)}")


# =============================================================================
# Embedding Endpoints
# =============================================================================

@router.post("/generate-embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(request: GenerateEmbeddingsRequest):
    """
    Generate embeddings for vocabulary types (bulk operation).

    Useful for:
    - Fixing missing embeddings after database issues
    - Regenerating embeddings after model changes
    - Updating embeddings after vocabulary merges

    Args:
        request: Embedding generation options

    Returns:
        GenerateEmbeddingsResponse with counts of generated/skipped/failed

    Example:
        POST /vocabulary/generate-embeddings
        {
            "force_regenerate": false,
            "only_missing": true
        }
    """
    try:
        from src.api.services.embedding_worker import get_embedding_worker
        from src.api.lib.age_client import AGEClient
        from src.api.lib.ai_providers import get_provider

        # Get embedding worker instance
        embedding_worker = get_embedding_worker(
            db_client=AGEClient(),
            ai_provider=get_provider()
        )

        if embedding_worker is None:
            raise HTTPException(
                status_code=500,
                detail="EmbeddingWorker not initialized"
            )

        # Use unified EmbeddingWorker
        # Note: We use regenerate_all_embeddings() instead of initialize_builtin_embeddings()
        # because initialize_builtin_embeddings() checks cold start status and skips if already done.
        # The user explicitly requested to generate embeddings, so we should do it.
        if request.force_regenerate:
            # Force regenerate ALL embeddings (including those that already exist)
            result = await embedding_worker.regenerate_all_embeddings(
                only_missing=False,
                only_stale=False
            )
            mode = "ALL vocabulary types (force regenerate)"
        else:
            # Default: only generate missing embeddings (no cold start check)
            result = await embedding_worker.regenerate_all_embeddings(
                only_missing=True,
                only_stale=False
            )
            mode = "vocabulary types WITHOUT embeddings"

        generated = result.processed_count
        failed = result.failed_count
        # Calculate skipped from target, processed, and failed
        skipped = result.target_count - result.processed_count - result.failed_count

        message = f"Generated embeddings for {mode}: {generated} generated, {skipped} skipped, {failed} failed"

        return GenerateEmbeddingsResponse(
            success=failed == 0,
            generated=generated,
            skipped=skipped,
            failed=failed,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")


@router.get("/category-scores/{relationship_type}", response_model=CategoryScoresResponse)
async def get_category_scores(relationship_type: str):
    """
    Get category similarity scores for a relationship type (ADR-047).

    Returns detailed breakdown of semantic similarity to all 8 categories:
    - causation, composition, logical, evidential
    - semantic, temporal, dependency, derivation

    Uses embedding similarity to 30 builtin seed types to compute scores.
    Confidence = max(similarity to any seed in category).

    Args:
        relationship_type: Edge type to analyze (e.g., "ENHANCES")

    Returns:
        CategoryScoresResponse with:
        - Primary category assignment
        - Confidence score (0.0-1.0)
        - Full score breakdown for all categories
        - Ambiguity flag if runner-up > 0.70

    Example:
        GET /vocabulary/category-scores/ENHANCES
        {
            "relationship_type": "ENHANCES",
            "category": "causation",
            "confidence": 0.85,
            "scores": {
                "causation": 0.85,
                "composition": 0.45,
                ...
            },
            "ambiguous": false
        }
    """
    try:
        from src.api.lib.age_client import AGEClient
        from src.api.lib.vocabulary_categorizer import VocabularyCategorizer

        db_client = AGEClient()
        categorizer = VocabularyCategorizer(db_client)

        # Compute category scores
        assignment = await categorizer.assign_category(relationship_type, store=False)

        return CategoryScoresResponse(
            relationship_type=assignment.relationship_type,
            category=assignment.category,
            confidence=assignment.confidence,
            scores=assignment.scores,
            ambiguous=assignment.ambiguous,
            runner_up_category=assignment.runner_up_category,
            runner_up_score=assignment.runner_up_score
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to compute category scores: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute category scores: {str(e)}")


@router.post("/refresh-categories", response_model=RefreshCategoriesResponse)
async def refresh_categories(request: RefreshCategoriesRequest):
    """
    Refresh category assignments for vocabulary types (ADR-047).

    Recomputes probabilistic category assignments based on current embeddings.
    Useful after:
    - Vocabulary merges (topology changed)
    - Embedding model changes (semantic space shifted)
    - Seed type adjustments (category definitions updated)

    Args:
        request: Configuration for refresh operation
            - only_computed: If True, only refresh types with category_source='computed'
                           If False, refresh all types (including builtins)

    Returns:
        RefreshCategoriesResponse with counts and detailed assignments

    Example:
        POST /vocabulary/refresh-categories
        {
            "only_computed": true
        }

        Response:
        {
            "success": true,
            "refreshed_count": 88,
            "skipped_count": 0,
            "failed_count": 0,
            "assignments": [
                {
                    "relationship_type": "ENHANCES",
                    "category": "causation",
                    "confidence": 0.85,
                    "scores": {...},
                    "ambiguous": false
                },
                ...
            ],
            "message": "Refreshed 88 category assignments"
        }
    """
    try:
        from src.api.lib.age_client import AGEClient
        from src.api.lib.vocabulary_categorizer import VocabularyCategorizer

        db_client = AGEClient()
        categorizer = VocabularyCategorizer(db_client)

        # Refresh categories
        assignments = await categorizer.refresh_all_categories(
            only_computed=request.only_computed
        )

        # Convert to response format
        category_responses = []
        for assignment in assignments:
            category_responses.append(
                CategoryScoresResponse(
                    relationship_type=assignment.relationship_type,
                    category=assignment.category,
                    confidence=assignment.confidence,
                    scores=assignment.scores,
                    ambiguous=assignment.ambiguous,
                    runner_up_category=assignment.runner_up_category,
                    runner_up_score=assignment.runner_up_score
                )
            )

        refreshed_count = len(assignments)
        skipped_count = 0  # Could add logic to track skipped
        failed_count = 0  # Could add logic to track failures

        message = f"Refreshed {refreshed_count} category assignment{'s' if refreshed_count != 1 else ''}"

        return RefreshCategoriesResponse(
            success=True,
            refreshed_count=refreshed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            assignments=category_responses,
            message=message
        )

    except Exception as e:
        logger.error(f"Failed to refresh categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh categories: {str(e)}")


# ========== Similarity Analysis Endpoints (ADR-053) ==========

@router.get("/similar/{relationship_type}", response_model=VocabularySimilarityResponse)
async def get_similar_types(
    relationship_type: str,
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    reverse: bool = Query(False, description="If True, return least similar (opposites)")
):
    """
    Find similar (or opposite) edge types based on embedding similarity (ADR-053).

    Uses cosine similarity between embeddings to find:
    - Similar types (high similarity): Potential synonyms for consolidation
    - Opposite types (low similarity): Semantic antonyms

    Args:
        relationship_type: Edge type to analyze
        limit: Number of results (1-100, default 10)
        reverse: If True, return least similar instead of most similar

    Returns:
        VocabularySimilarityResponse with sorted list of similar types

    Example:
        GET /vocabulary/similar/IMPLIES?limit=10

        Response:
        {
            "relationship_type": "IMPLIES",
            "category": "logical",
            "similar_types": [
                {"relationship_type": "SUGGESTS", "similarity": 0.92, "category": "logical", ...},
                {"relationship_type": "LEADS_TO", "similarity": 0.87, "category": "causation", ...}
            ],
            "total_compared": 171
        }

        GET /vocabulary/similar/IMPLIES?limit=5&reverse=true  # Get opposites
    """
    try:
        from src.api.lib.age_client import AGEClient
        from src.api.lib.vocabulary_categorizer import VocabularyCategorizer
        import numpy as np

        db_client = AGEClient()
        categorizer = VocabularyCategorizer(db_client)

        # Get target embedding
        target_embedding = await categorizer._get_embedding(relationship_type)
        if target_embedding is None:
            raise HTTPException(
                status_code=404,
                detail=f"No embedding found for relationship type: {relationship_type}"
            )

        # Get target category
        query = """
            SELECT category
            FROM kg_api.relationship_vocabulary
            WHERE relationship_type = %s
        """
        result = await db_client.execute_query(query, (relationship_type,))
        target_category = result[0]['category'] if result else "unknown"

        # Get all other types with embeddings
        query = """
            SELECT relationship_type, category, is_builtin, embedding,
                   COALESCE(usage_count, 0) as usage_count
            FROM kg_api.relationship_vocabulary
            WHERE embedding IS NOT NULL
              AND relationship_type != %s
              AND is_active = TRUE
        """
        all_types = await db_client.execute_query(query, (relationship_type,))

        # Compute similarities
        similarities = []
        for row in all_types:
            other_embedding = np.array(row['embedding'], dtype=np.float32)
            similarity = categorizer._cosine_similarity(target_embedding, other_embedding)

            # Get correct usage_count from graph (ADR-048 Phase 3)
            # Use edge_count (real-time count) not usage_count (stale property)
            type_info = db_client.get_edge_type_info(row['relationship_type'])
            actual_usage_count = type_info['edge_count'] if type_info else 0

            similarities.append(SimilarEdgeType(
                relationship_type=row['relationship_type'],
                similarity=float(similarity),
                category=row['category'],
                is_builtin=row['is_builtin'],
                usage_count=actual_usage_count
            ))

        # Sort by similarity (descending for similar, ascending for opposite)
        similarities.sort(key=lambda x: x.similarity, reverse=not reverse)

        # Return top N
        return VocabularySimilarityResponse(
            relationship_type=relationship_type,
            category=target_category,
            similar_types=similarities[:limit],
            total_compared=len(similarities)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute similarities for {relationship_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute similarities: {str(e)}")


@router.get("/analyze/{relationship_type}", response_model=VocabularyAnalysisDetailResponse)
async def analyze_vocabulary_type(relationship_type: str):
    """
    Detailed analysis of vocabulary type for quality assurance (ADR-053).

    Provides comprehensive similarity analysis:
    - Category fit (similarity to category seeds)
    - Most similar types in same category
    - Most similar types in other categories
    - Potential miscategorization detection

    Use this to:
    - Verify auto-categorization makes sense
    - Identify miscategorized types
    - Understand semantic structure
    - Find potential category changes

    Args:
        relationship_type: Edge type to analyze

    Returns:
        VocabularyAnalysisDetailResponse with detailed analysis

    Example:
        GET /vocabulary/analyze/IMPLIES

        Response:
        {
            "relationship_type": "IMPLIES",
            "category": "logical",
            "category_fit": 0.89,
            "most_similar_same_category": [
                {"relationship_type": "ENTAILS", "similarity": 0.91, ...}
            ],
            "most_similar_other_categories": [
                {"relationship_type": "CAUSES", "similarity": 0.76, "category": "causation", ...}
            ],
            "potential_miscategorization": false,
            "suggestion": null
        }
    """
    try:
        from src.api.lib.age_client import AGEClient
        from src.api.lib.vocabulary_categorizer import VocabularyCategorizer, CATEGORY_SEEDS
        import numpy as np

        db_client = AGEClient()
        categorizer = VocabularyCategorizer(db_client)

        # Get target info
        query = """
            SELECT category, category_confidence
            FROM kg_api.relationship_vocabulary
            WHERE relationship_type = %s
        """
        result = await db_client.execute_query(query, (relationship_type,))
        if not result:
            raise HTTPException(status_code=404, detail=f"Relationship type not found: {relationship_type}")

        target_category = result[0]['category']
        category_confidence = result[0].get('category_confidence', 0.0)

        # Get category fit (max similarity to any seed in assigned category)
        category_scores = await categorizer.compute_category_scores(relationship_type)
        category_fit = category_scores.get(target_category, 0.0)

        # Get all similarities
        similarity_response = await get_similar_types(relationship_type, limit=100, reverse=False)
        all_similar = similarity_response.similar_types

        # Split by category
        same_category = [s for s in all_similar if s.category == target_category][:5]
        other_categories = [s for s in all_similar if s.category != target_category][:5]

        # Detect potential miscategorization
        # If most similar type is in different category with high similarity
        potential_misc = False
        suggestion = None

        if other_categories and other_categories[0].similarity > category_fit:
            potential_misc = True
            top_other = other_categories[0]
            suggestion = (
                f"Consider reclassifying to '{top_other.category}' category "
                f"(more similar to {top_other.relationship_type}: {top_other.similarity:.2f} "
                f"vs category fit: {category_fit:.2f})"
            )

        return VocabularyAnalysisDetailResponse(
            relationship_type=relationship_type,
            category=target_category,
            category_fit=category_fit,
            most_similar_same_category=same_category,
            most_similar_other_categories=other_categories,
            potential_miscategorization=potential_misc,
            suggestion=suggestion
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze {relationship_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze vocabulary type: {str(e)}")
