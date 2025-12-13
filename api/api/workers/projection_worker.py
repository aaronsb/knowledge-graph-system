"""
Embedding Projection Worker (ADR-078).

Computes t-SNE/UMAP projections for ontology embeddings and stores results
for the Embedding Landscape Explorer. Triggered by ProjectionLauncher when
concept counts change significantly.
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# TEMPORARY: Ephemeral file storage for projections
# This is an accepted anti-pattern until we implement proper Garage bucket storage.
# Projections are lost on container restart but recompute quickly (~1s for 400 concepts).
# TODO: Move to Garage storage with time-series snapshots (see ADR-078 Future Considerations)
PROJECTION_CACHE_DIR = Path("/tmp/kg_projections")


def run_projection_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute projection computation as a background job.

    Args:
        job_data: Job parameters
            - operation: str - "compute_projection"
            - ontology: str - Ontology name to project
            - algorithm: str - "tsne" or "umap" (default: tsne)
            - n_components: int - Dimensions (2 or 3, default: 3)
            - perplexity: int - t-SNE perplexity (default: 30)
            - n_neighbors: int - UMAP n_neighbors (default: 15)
            - min_dist: float - UMAP min_dist (default: 0.1)
            - include_grounding: bool - Include grounding strength (default: True)
            - include_diversity: bool - Include diversity scores (default: False)
            - description: str - Job description
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with projection stats

    Raises:
        Exception: If projection fails
    """
    try:
        from api.api.lib.age_client import AGEClient
        from api.api.services.embedding_projection_service import EmbeddingProjectionService

        logger.info(f"📊 Projection worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Projection worker started"
        })

        # Extract parameters
        ontology = job_data.get("ontology")
        if not ontology:
            raise ValueError("Missing required parameter: ontology")

        algorithm = job_data.get("algorithm", "tsne")
        n_components = job_data.get("n_components", 3)
        perplexity = job_data.get("perplexity", 30)
        n_neighbors = job_data.get("n_neighbors", 15)
        min_dist = job_data.get("min_dist", 0.1)
        include_grounding = job_data.get("include_grounding", True)
        include_diversity = job_data.get("include_diversity", False)

        logger.info(
            f"Projection params: ontology={ontology}, algorithm={algorithm}, "
            f"n_components={n_components}, perplexity={perplexity}"
        )

        # Initialize service
        client = AGEClient()
        service = EmbeddingProjectionService(client)

        # Check algorithm availability
        available = service.get_available_algorithms()
        if algorithm not in available:
            raise ValueError(f"Algorithm '{algorithm}' not available. Available: {available}")

        # Update progress
        job_queue.update_job(job_id, {
            "progress": f"Fetching embeddings for '{ontology}'"
        })

        # Generate projection dataset
        dataset = service.generate_projection_dataset(
            ontology=ontology,
            algorithm=algorithm,
            n_components=n_components,
            perplexity=perplexity,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            include_grounding=include_grounding,
            include_diversity=include_diversity
        )

        # Check for errors
        if "error" in dataset:
            raise ValueError(dataset["error"])

        # Update progress
        concept_count = dataset.get("statistics", {}).get("concept_count", 0)
        job_queue.update_job(job_id, {
            "progress": f"Computed projection for {concept_count} concepts"
        })

        # Store projection to cache file
        cache_file = _store_projection(ontology, dataset)

        # Prepare result
        result = {
            "success": True,
            "ontology": ontology,
            "algorithm": algorithm,
            "concept_count": concept_count,
            "changelist_id": dataset.get("changelist_id"),
            "computation_time_ms": dataset.get("statistics", {}).get("computation_time_ms"),
            "cache_file": str(cache_file) if cache_file else None
        }

        logger.info(
            f"✅ Projection worker completed: {job_id} "
            f"({concept_count} concepts, {algorithm})"
        )
        return result

    except Exception as e:
        error_msg = f"Projection computation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        job_queue.update_job(job_id, {
            "status": "failed",
            "error": error_msg,
            "progress": "Projection computation failed"
        })

        raise Exception(error_msg) from e


def _store_projection(ontology: str, dataset: Dict[str, Any]) -> Path:
    """
    Store projection dataset to cache file.

    Args:
        ontology: Ontology name
        dataset: Projection dataset dict

    Returns:
        Path to cached file
    """
    # Ensure cache directory exists
    PROJECTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize ontology name for filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in ontology)
    cache_file = PROJECTION_CACHE_DIR / f"{safe_name}.json"

    # Write dataset
    with open(cache_file, 'w') as f:
        json.dump(dataset, f, indent=2)

    logger.info(f"Stored projection to {cache_file}")
    return cache_file


def get_cached_projection(ontology: str) -> Dict[str, Any] | None:
    """
    Retrieve cached projection for an ontology.

    Args:
        ontology: Ontology name

    Returns:
        Projection dataset dict or None if not cached
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in ontology)
    cache_file = PROJECTION_CACHE_DIR / f"{safe_name}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read cached projection for {ontology}: {e}")
        return None


def invalidate_cached_projection(ontology: str) -> bool:
    """
    Invalidate (delete) cached projection for an ontology.

    Args:
        ontology: Ontology name

    Returns:
        True if cache was deleted, False if not found
    """
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in ontology)
    cache_file = PROJECTION_CACHE_DIR / f"{safe_name}.json"

    if cache_file.exists():
        cache_file.unlink()
        logger.info(f"Invalidated projection cache for {ontology}")
        return True
    return False
