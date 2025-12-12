"""
Projection API routes (ADR-078).

Endpoints for embedding landscape visualization:
- GET /projection/{ontology} - Get cached projection dataset
- POST /projection/{ontology}/regenerate - Trigger projection recomputation
"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
import logging

from api.api.lib.age_client import AGEClient
from api.api.services.embedding_projection_service import EmbeddingProjectionService
from api.api.workers.projection_worker import (
    get_cached_projection,
    invalidate_cached_projection
)
from api.api.services.job_queue import get_job_queue
from api.api.dependencies.auth import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projection", tags=["projection"])


# Request/Response models

class ProjectionConceptResponse(BaseModel):
    """Single concept in projection response."""
    concept_id: str
    label: str
    x: float
    y: float
    z: float
    grounding_strength: Optional[float] = None
    diversity_score: Optional[float] = None
    diversity_related_count: Optional[int] = None


class ProjectionParametersResponse(BaseModel):
    """Projection algorithm parameters."""
    n_components: int = 3
    perplexity: Optional[int] = None
    n_neighbors: Optional[int] = None
    min_dist: Optional[float] = None


class ProjectionStatisticsResponse(BaseModel):
    """Projection computation statistics."""
    concept_count: int
    computation_time_ms: int
    embedding_dims: int
    grounding_range: Optional[List[float]] = None
    diversity_range: Optional[List[float]] = None


class ProjectionDatasetResponse(BaseModel):
    """Complete projection dataset response."""
    ontology: str
    changelist_id: str
    algorithm: str
    parameters: ProjectionParametersResponse
    computed_at: str
    concepts: List[ProjectionConceptResponse]
    statistics: ProjectionStatisticsResponse


class RegenerateRequest(BaseModel):
    """Request body for regenerating projection."""
    force: bool = Field(
        default=False,
        description="Force regeneration even if cache exists"
    )
    algorithm: Literal["tsne", "umap"] = Field(
        default="tsne",
        description="Projection algorithm"
    )
    n_components: int = Field(
        default=3,
        ge=2,
        le=3,
        description="Output dimensions"
    )
    perplexity: int = Field(
        default=30,
        ge=2,
        le=100,
        description="t-SNE perplexity"
    )
    n_neighbors: int = Field(
        default=15,
        ge=2,
        le=200,
        description="UMAP n_neighbors"
    )
    min_dist: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="UMAP min_dist"
    )
    include_grounding: bool = Field(
        default=True,
        description="Include grounding strength"
    )
    include_diversity: bool = Field(
        default=False,
        description="Include diversity scores (slower)"
    )


class RegenerateResponse(BaseModel):
    """Response for regenerate request."""
    status: Literal["queued", "skipped", "computed"]
    job_id: Optional[str] = None
    message: str
    changelist_id: Optional[str] = None


class AlgorithmInfoResponse(BaseModel):
    """Available projection algorithms."""
    available: List[str]
    default: str = "tsne"


@router.get("/algorithms", response_model=AlgorithmInfoResponse)
async def get_available_algorithms(
    current_user: CurrentUser
):
    """Get available projection algorithms."""
    client = AGEClient()
    service = EmbeddingProjectionService(client)
    available = service.get_available_algorithms()

    return AlgorithmInfoResponse(
        available=available,
        default="tsne" if "tsne" in available else (available[0] if available else "none")
    )


@router.get("/{ontology}", response_model=ProjectionDatasetResponse)
async def get_projection(
    ontology: str,
    request: Request,
    current_user: CurrentUser
):
    """
    Get cached projection dataset for an ontology.

    Returns pre-computed projection coordinates for visualization.
    If no cache exists, returns 404.

    Supports conditional requests:
    - If-None-Match: changelist_id → returns 304 if unchanged
    """
    # Check for cached projection
    dataset = get_cached_projection(ontology)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"No projection found for ontology '{ontology}'. "
                   f"Use POST /projection/{ontology}/regenerate to compute."
        )

    # Check conditional request (ETag/If-None-Match)
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and if_none_match == dataset.get("changelist_id"):
        return Response(status_code=304)

    # Return dataset
    return ProjectionDatasetResponse(**dataset)


@router.post("/{ontology}/regenerate", response_model=RegenerateResponse)
async def regenerate_projection(
    ontology: str,
    current_user: CurrentUser,
    body: RegenerateRequest = RegenerateRequest()
):
    """
    Trigger projection recomputation for an ontology.

    By default, queues a background job. If the ontology is small (< 100 concepts),
    computes synchronously and returns immediately.
    """
    # Check if cache exists and force=False
    if not body.force:
        cached = get_cached_projection(ontology)
        if cached is not None:
            return RegenerateResponse(
                status="skipped",
                message=f"Projection already cached (changelist: {cached.get('changelist_id')}). "
                        f"Use force=true to regenerate.",
                changelist_id=cached.get("changelist_id")
            )

    # Check ontology exists and get concept count
    client = AGEClient()
    service = EmbeddingProjectionService(client)

    concepts = service.get_ontology_embeddings(
        ontology,
        include_grounding=False,
        include_diversity=False
    )

    if not concepts:
        raise HTTPException(
            status_code=404,
            detail=f"Ontology '{ontology}' not found or has no concepts with embeddings"
        )

    concept_count = len(concepts)

    # For small/medium ontologies, compute synchronously (t-SNE is fast)
    # Only queue for very large ontologies (>500 concepts) where t-SNE takes >10s
    if concept_count < 500:
        logger.info(f"Computing projection synchronously for '{ontology}' ({concept_count} concepts)")

        dataset = service.generate_projection_dataset(
            ontology=ontology,
            algorithm=body.algorithm,
            n_components=body.n_components,
            perplexity=body.perplexity,
            n_neighbors=body.n_neighbors,
            min_dist=body.min_dist,
            include_grounding=body.include_grounding,
            include_diversity=body.include_diversity
        )

        # Store to cache
        from api.api.workers.projection_worker import _store_projection
        _store_projection(ontology, dataset)

        return RegenerateResponse(
            status="computed",
            message=f"Projection computed for {concept_count} concepts",
            changelist_id=dataset.get("changelist_id")
        )

    # For larger ontologies, queue background job
    queue = get_job_queue()
    job_id = queue.enqueue(
        job_type="projection",
        job_data={
            "operation": "compute_projection",
            "ontology": ontology,
            "algorithm": body.algorithm,
            "n_components": body.n_components,
            "perplexity": body.perplexity,
            "n_neighbors": body.n_neighbors,
            "min_dist": body.min_dist,
            "include_grounding": body.include_grounding,
            "include_diversity": body.include_diversity,
            "description": f"Regenerate projection for '{ontology}'",
            "user_id": current_user.id
        }
    )

    # Auto-approve projection jobs (no LLM costs, user-initiated)
    from datetime import datetime
    queue.update_job(job_id, {
        "status": "approved",
        "approved_at": datetime.utcnow().isoformat(),
        "approved_by": current_user.username
    })

    return RegenerateResponse(
        status="queued",
        job_id=job_id,
        message=f"Projection job queued for {concept_count} concepts"
    )


@router.delete("/{ontology}")
async def invalidate_projection(
    ontology: str,
    current_user: CurrentUser
):
    """
    Invalidate (delete) cached projection for an ontology.

    Useful when you want to force fresh computation on next request.
    """
    deleted = invalidate_cached_projection(ontology)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No cached projection found for ontology '{ontology}'"
        )

    return {"message": f"Projection cache invalidated for '{ontology}'"}
