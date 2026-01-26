"""
Projection API routes (ADR-078).

Endpoints for embedding landscape visualization:
- GET /projection/{ontology} - Get cached projection dataset
- POST /projection/{ontology}/regenerate - Trigger projection recomputation
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
import logging

from api.app.lib.age_client import AGEClient
from api.app.services.embedding_projection_service import EmbeddingProjectionService
from api.app.workers.projection_worker import (
    get_cached_projection,
    invalidate_cached_projection
)
from api.app.services.job_queue import get_job_queue
from api.app.dependencies.auth import CurrentUser

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
    ontology: Optional[str] = None  # Source ontology (for cross-ontology mode)
    item_type: Optional[str] = None  # Item type (for combined mode)


class ProjectionParametersResponse(BaseModel):
    """Projection algorithm parameters."""
    n_components: int = 3
    perplexity: Optional[int] = None
    n_neighbors: Optional[int] = None
    min_dist: Optional[float] = None
    spread: Optional[float] = None  # UMAP spread (cluster separation)
    metric: Optional[str] = None  # "cosine" or "euclidean"
    normalize_l2: Optional[bool] = None  # L2 normalization applied
    center: Optional[bool] = None  # Mean-centering applied (fixes anisotropy)


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
        description="UMAP min_dist (cluster tightness, lower=tighter)"
    )
    spread: float = Field(
        default=1.0,
        ge=0.5,
        le=5.0,
        description="UMAP spread (embedding scale, higher=more cluster separation)"
    )
    metric: Literal["cosine", "euclidean"] = Field(
        default="cosine",
        description="Distance metric: cosine (angular, best for embeddings) or euclidean (L2)"
    )
    normalize_l2: bool = Field(
        default=True,
        description="L2-normalize embeddings before projection (recommended for semantic vectors)"
    )
    center: bool = Field(
        default=True,
        description="Center embeddings (subtract mean) before normalization. Fixes 'nested meatball' anisotropy artifact where clusters form concentric shells instead of distinct islands."
    )
    include_grounding: bool = Field(
        default=True,
        description="Include grounding strength"
    )
    refresh_grounding: bool = Field(
        default=False,
        description="Compute fresh grounding values (slower but accurate)"
    )
    include_diversity: bool = Field(
        default=False,
        description="Include diversity scores (slower)"
    )
    embedding_source: Literal["concepts", "sources", "vocabulary", "combined"] = Field(
        default="concepts",
        description="Which embeddings to project: concepts (default), sources, vocabulary, or combined"
    )
    create_artifact: bool = Field(
        default=False,
        description="Save result as persistent artifact (ADR-083)"
    )


class RegenerateResponse(BaseModel):
    """Response for regenerate request."""
    status: Literal["queued", "skipped", "computed"]
    job_id: Optional[str] = None
    message: str
    changelist_id: Optional[str] = None
    artifact_id: Optional[int] = None


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
    current_user: CurrentUser,
    embedding_source: Literal["concepts", "sources", "vocabulary", "combined"] = "concepts"
):
    """
    Get cached projection dataset for an ontology.

    Returns pre-computed projection coordinates for visualization.
    If no cache exists, returns 404.

    Args:
        embedding_source: Which embeddings to retrieve (default: concepts)

    Supports conditional requests:
    - If-None-Match: changelist_id → returns 304 if unchanged
    """
    # Check for cached projection from Garage (ADR-079)
    dataset = get_cached_projection(ontology, embedding_source)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {embedding_source} projection found for ontology '{ontology}'. "
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
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    body: RegenerateRequest = RegenerateRequest()
):
    """
    Trigger projection recomputation for an ontology.

    By default, queues a background job. If the ontology is small (< 100 concepts),
    computes synchronously and returns immediately.
    """
    # Check if cache exists and force=False (ADR-079: Garage storage)
    if not body.force:
        cached = get_cached_projection(ontology, body.embedding_source)
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

    # Cross-ontology mode: fetch ALL concepts across all ontologies
    if ontology == "__all__":
        concepts = service.get_all_ontology_embeddings(
            include_grounding=False
        )
    else:
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
        logger.info(f"Computing projection synchronously for '{ontology}' ({concept_count} {body.embedding_source})")

        dataset = service.generate_projection_dataset(
            ontology=ontology,
            algorithm=body.algorithm,
            n_components=body.n_components,
            perplexity=body.perplexity,
            n_neighbors=body.n_neighbors,
            min_dist=body.min_dist,
            spread=body.spread,
            metric=body.metric,
            normalize_l2=body.normalize_l2,
            center=body.center,
            include_grounding=body.include_grounding,
            refresh_grounding=body.refresh_grounding,
            include_diversity=body.include_diversity,
            embedding_source=body.embedding_source
        )

        # Store to Garage (ADR-079)
        from api.app.workers.projection_worker import _store_projection
        _store_projection(ontology, body.embedding_source, dataset)

        # ADR-083: Optionally create artifact for persistence
        artifact_id = None
        if body.create_artifact:
            from api.app.workers.artifact_helper import create_artifact
            artifact_id = create_artifact(
                user_id=current_user.id,
                artifact_type="projection",
                representation="cli",  # CLI-initiated sync computation
                name=f"Projection: {ontology} ({body.algorithm}, {body.n_components}D)",
                parameters={
                    "ontology": ontology,
                    "algorithm": body.algorithm,
                    "n_components": body.n_components,
                    "perplexity": body.perplexity,
                    "n_neighbors": body.n_neighbors,
                    "min_dist": body.min_dist,
                    "spread": body.spread,
                    "metric": body.metric,
                    "normalize_l2": body.normalize_l2,
                    "center": body.center,
                    "include_grounding": body.include_grounding,
                    "include_diversity": body.include_diversity,
                    "embedding_source": body.embedding_source
                },
                payload=dataset,
                ontology=ontology
            )

        return RegenerateResponse(
            status="computed",
            message=f"Projection computed for {concept_count} {body.embedding_source}",
            changelist_id=dataset.get("changelist_id"),
            artifact_id=artifact_id
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
            "spread": body.spread,
            "metric": body.metric,
            "normalize_l2": body.normalize_l2,
            "center": body.center,
            "include_grounding": body.include_grounding,
            "refresh_grounding": body.refresh_grounding,
            "include_diversity": body.include_diversity,
            "embedding_source": body.embedding_source,
            "create_artifact": body.create_artifact,
            "description": f"Regenerate {body.embedding_source} projection for '{ontology}'",
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

    # Start the job in the background (serial execution)
    background_tasks.add_task(queue.queue_serial_job, job_id)

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
