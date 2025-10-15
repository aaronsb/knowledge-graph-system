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
    GenerateEmbeddingsResponse,

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

    # Get configuration from environment
    mode = os.getenv("VOCAB_PRUNING_MODE", "hitl")
    profile = os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")

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

            # Get configuration
            vocab_min = int(os.getenv("VOCAB_MIN", "30"))
            vocab_max = int(os.getenv("VOCAB_MAX", "90"))
            vocab_emergency = int(os.getenv("VOCAB_EMERGENCY", "200"))
            profile = os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")

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
                    value_score=info.get("value_score")
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
# Recommendations Endpoints (HITL Workflow)
# =============================================================================

@router.get("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations():
    """
    Generate vocabulary optimization recommendations.

    Analyzes current vocabulary state and generates recommendations
    for merging, pruning, or deprecating edge types based on the
    configured pruning mode (naive/hitl/aitl).

    Returns:
        RecommendationsResponse with auto-execute and needs-review lists

    Example:
        GET /vocabulary/recommendations
    """
    try:
        manager = get_vocabulary_manager()

        # Generate recommendations
        recommendations = await manager.generate_recommendations()

        # Get current status
        client = AGEClient()
        try:
            vocab_size = client.get_vocabulary_size()
            vocab_min = int(os.getenv("VOCAB_MIN", "30"))
            vocab_max = int(os.getenv("VOCAB_MAX", "90"))
            vocab_emergency = int(os.getenv("VOCAB_EMERGENCY", "200"))
            profile = os.getenv("VOCAB_AGGRESSIVENESS", "aggressive")

            aggressiveness, zone = calculate_aggressiveness(
                current_size=vocab_size,
                vocab_min=vocab_min,
                vocab_max=vocab_max,
                vocab_emergency=vocab_emergency,
                profile=profile
            )
        finally:
            client.close()

        # Convert to response models
        auto_execute = [
            ActionRecommendationResponse(
                action_type=ActionTypeEnum(rec.action_type.value),
                edge_type=rec.edge_type,
                target_type=rec.target_type,
                review_level=ReviewLevelEnum(rec.review_level.value),
                should_execute=rec.should_execute,
                needs_review=rec.needs_review,
                reasoning=rec.reasoning,
                metadata=rec.metadata
            )
            for rec in recommendations["auto_execute"]
        ]

        needs_review = [
            ActionRecommendationResponse(
                action_type=ActionTypeEnum(rec.action_type.value),
                edge_type=rec.edge_type,
                target_type=rec.target_type,
                review_level=ReviewLevelEnum(rec.review_level.value),
                should_execute=rec.should_execute,
                needs_review=rec.needs_review,
                reasoning=rec.reasoning,
                metadata=rec.metadata
            )
            for rec in recommendations["needs_review"]
        ]

        return RecommendationsResponse(
            vocab_size=vocab_size,
            zone=ZoneEnum(zone),
            aggressiveness=aggressiveness,
            auto_execute=auto_execute,
            needs_review=needs_review
        )

    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.post("/recommendations/execute", response_model=list[ExecutionResultResponse])
async def execute_auto_recommendations():
    """
    Execute all auto-approved recommendations.

    Only executes actions with should_execute=True (typically in naive or AITL modes).
    HITL mode actions require explicit approval via /recommendations/{id}/approve.

    Returns:
        List of ExecutionResultResponse showing results

    Example:
        POST /vocabulary/recommendations/execute
    """
    try:
        manager = get_vocabulary_manager()

        # Generate recommendations
        recommendations = await manager.generate_recommendations()

        # Execute auto-approved actions
        results = await manager.execute_auto_actions(recommendations["auto_execute"])

        # Convert to response models
        return [
            ExecutionResultResponse(
                success=result.success,
                message=result.message,
                affected_edges=result.affected_edges,
                error=result.error
            )
            for result in results
        ]

    except Exception as e:
        logger.error(f"Failed to execute recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute recommendations: {str(e)}")


# =============================================================================
# Analysis Endpoints
# =============================================================================

@router.get("/analysis", response_model=VocabularyAnalysisResponse)
async def get_vocabulary_analysis():
    """
    Get detailed vocabulary analysis including value scores and synonym candidates.

    Returns:
        VocabularyAnalysisResponse with comprehensive analysis

    Example:
        GET /vocabulary/analysis
    """
    try:
        manager = get_vocabulary_manager()

        # Perform analysis
        analysis = await manager.analyze_vocabulary()

        # Convert edge type scores
        edge_scores = [
            EdgeTypeScoreResponse(
                relationship_type=score.relationship_type,
                edge_count=score.edge_count,
                avg_traversal=score.avg_traversal,
                bridge_count=score.bridge_count,
                trend=score.trend,
                value_score=score.value_score,
                is_builtin=score.is_builtin,
                last_used=score.last_used
            )
            for score in analysis.edge_type_scores.values()
        ]

        # Convert synonym candidates
        synonym_candidates = [
            SynonymCandidateResponse(
                type1=candidate.type1,
                type2=candidate.type2,
                similarity=candidate.similarity,
                strength=candidate.strength.value,
                is_strong_match=candidate.is_strong_match,
                needs_review=candidate.needs_review,
                reasoning=candidate.reasoning
            )
            for candidate, _, _ in analysis.synonym_candidates
        ]

        # Convert low value types
        low_value = [
            EdgeTypeScoreResponse(
                relationship_type=score.relationship_type,
                edge_count=score.edge_count,
                avg_traversal=score.avg_traversal,
                bridge_count=score.bridge_count,
                trend=score.trend,
                value_score=score.value_score,
                is_builtin=score.is_builtin,
                last_used=score.last_used
            )
            for score in analysis.low_value_types
        ]

        return VocabularyAnalysisResponse(
            vocab_size=analysis.vocab_size,
            vocab_min=analysis.vocab_min,
            vocab_max=analysis.vocab_max,
            vocab_emergency=analysis.vocab_emergency,
            aggressiveness=analysis.aggressiveness,
            zone=ZoneEnum(analysis.zone),
            edge_type_scores=edge_scores,
            synonym_candidates=synonym_candidates,
            low_value_types=low_value,
            category_distribution=analysis.category_distribution
        )

    except Exception as e:
        logger.error(f"Failed to analyze vocabulary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze vocabulary: {str(e)}")


# =============================================================================
# Configuration Endpoints
# =============================================================================

@router.get("/config", response_model=VocabularyConfigResponse)
async def get_vocabulary_config():
    """
    Get current vocabulary configuration.

    Returns:
        VocabularyConfigResponse with all configuration values

    Example:
        GET /vocabulary/config
    """
    try:
        return VocabularyConfigResponse(
            vocab_min=int(os.getenv("VOCAB_MIN", "30")),
            vocab_max=int(os.getenv("VOCAB_MAX", "90")),
            vocab_emergency=int(os.getenv("VOCAB_EMERGENCY", "200")),
            pruning_mode=PruningModeEnum(os.getenv("VOCAB_PRUNING_MODE", "hitl")),
            aggressiveness_profile=os.getenv("VOCAB_AGGRESSIVENESS", "aggressive"),
            category_min=8,
            category_max=15,
            auto_expand_enabled=os.getenv("AUTO_EXPAND_ENABLED", "false").lower() == "true",
            synonym_threshold_strong=float(os.getenv("SYNONYM_THRESHOLD_STRONG", "0.90")),
            synonym_threshold_moderate=float(os.getenv("SYNONYM_THRESHOLD_MODERATE", "0.70")),
            low_value_threshold=float(os.getenv("LOW_VALUE_THRESHOLD", "1.0")),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        )

    except Exception as e:
        logger.error(f"Failed to get vocabulary config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get vocabulary config: {str(e)}")


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
        client = AGEClient()
        provider = get_provider()

        try:
            # Generate embeddings using AGEClient method
            results = client.generate_vocabulary_embeddings(
                ai_provider=provider,
                force_regenerate=request.force_regenerate,
                only_missing=request.only_missing
            )

            # Construct success message
            if request.force_regenerate:
                mode = "ALL vocabulary types (force regenerate)"
            elif request.only_missing:
                mode = "vocabulary types WITHOUT embeddings"
            else:
                mode = "active vocabulary types"

            message = f"Generated embeddings for {mode}: {results['generated']} generated, {results['skipped']} skipped, {results['failed']} failed"

            return GenerateEmbeddingsResponse(
                success=results['failed'] == 0,
                generated=results['generated'],
                skipped=results['skipped'],
                failed=results['failed'],
                message=message
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")
