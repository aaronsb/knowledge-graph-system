"""
Embedding Projection Worker (ADR-078, ADR-079).

Computes t-SNE/UMAP projections for ontology embeddings and stores results
for the Embedding Landscape Explorer. Triggered by ProjectionLauncher when
concept counts change significantly.

Storage:
    Projections are stored in Garage (S3-compatible object storage) with both
    latest version and timestamped historical snapshots for tracking semantic
    landscape evolution over time.

    Key format: projections/{ontology}/{embedding_source}/latest.json
                projections/{ontology}/{embedding_source}/{timestamp}.json
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


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
        spread = job_data.get("spread", 1.0)
        metric = job_data.get("metric", "cosine")
        normalize_l2 = job_data.get("normalize_l2", True)
        center = job_data.get("center", True)
        include_grounding = job_data.get("include_grounding", True)
        refresh_grounding = job_data.get("refresh_grounding", False)
        include_diversity = job_data.get("include_diversity", False)
        embedding_source = job_data.get("embedding_source", "concepts")

        logger.info(
            f"Projection params: ontology={ontology}, algorithm={algorithm}, "
            f"n_components={n_components}, perplexity={perplexity}, metric={metric}, "
            f"spread={spread}, normalize_l2={normalize_l2}, center={center}, "
            f"refresh_grounding={refresh_grounding}, embedding_source={embedding_source}"
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
            "progress": f"Fetching {embedding_source} embeddings for '{ontology}'"
        })

        # Generate projection dataset
        dataset = service.generate_projection_dataset(
            ontology=ontology,
            algorithm=algorithm,
            n_components=n_components,
            perplexity=perplexity,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            spread=spread,
            metric=metric,
            normalize_l2=normalize_l2,
            center=center,
            include_grounding=include_grounding,
            refresh_grounding=refresh_grounding,
            include_diversity=include_diversity,
            embedding_source=embedding_source
        )

        # Check for errors
        if "error" in dataset:
            raise ValueError(dataset["error"])

        # Update progress
        concept_count = dataset.get("statistics", {}).get("concept_count", 0)
        job_queue.update_job(job_id, {
            "progress": f"Computed projection for {concept_count} {embedding_source}"
        })

        # Store projection to Garage (ADR-079)
        storage_key = _store_projection(ontology, embedding_source, dataset)

        # Prepare result - include warning if storage failed (ADR-079 review feedback)
        result = {
            "success": True,
            "ontology": ontology,
            "embedding_source": embedding_source,
            "algorithm": algorithm,
            "concept_count": concept_count,
            "changelist_id": dataset.get("changelist_id"),
            "computation_time_ms": dataset.get("statistics", {}).get("computation_time_ms"),
            "storage_key": storage_key,
            "storage_warning": None if storage_key else "Projection computed but cache storage failed - will recompute on next request"
        }

        if storage_key:
            logger.info(
                f"✅ Projection worker completed: {job_id} "
                f"({concept_count} {embedding_source}, {algorithm})"
            )
        else:
            logger.warning(
                f"⚠️ Projection worker completed but storage failed: {job_id} "
                f"({concept_count} {embedding_source}, {algorithm})"
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


def _store_projection(ontology: str, embedding_source: str, dataset: Dict[str, Any]) -> Optional[str]:
    """
    Store projection dataset to Garage (ADR-079).

    Stores both latest version and timestamped historical snapshot.

    Args:
        ontology: Ontology name
        embedding_source: Source type (concepts, sources, vocabulary, combined)
        dataset: Projection dataset dict

    Returns:
        Object key of stored projection, or None if storage failed
    """
    try:
        from api.api.lib.garage_client import get_garage_client

        garage = get_garage_client()
        storage_key = garage.store_projection(
            ontology=ontology,
            embedding_source=embedding_source,
            projection_data=dataset,
            keep_history=True  # Store timestamped snapshot for historical analysis
        )

        logger.info(f"Stored projection to Garage: {storage_key}")
        return storage_key

    except Exception as e:
        logger.error(f"Failed to store projection to Garage: {e}")
        # Return None instead of raising - worker continues with result
        return None


def get_cached_projection(ontology: str, embedding_source: str = "concepts") -> Optional[Dict[str, Any]]:
    """
    Retrieve cached projection for an ontology from Garage.

    Args:
        ontology: Ontology name
        embedding_source: Source type (default: concepts)

    Returns:
        Projection dataset dict or None if not cached
    """
    try:
        from api.api.lib.garage_client import get_garage_client

        garage = get_garage_client()
        return garage.get_projection(ontology, embedding_source)

    except Exception as e:
        logger.warning(f"Failed to get cached projection from Garage for {ontology}: {e}")
        return None


def invalidate_cached_projection(ontology: str, embedding_source: str = "concepts") -> bool:
    """
    Invalidate (delete) cached projection for an ontology.

    Note: Does not delete historical snapshots, only the latest version.

    Args:
        ontology: Ontology name
        embedding_source: Source type (default: concepts)

    Returns:
        True if cache was deleted, False if not found
    """
    try:
        from api.api.lib.garage_client import get_garage_client

        garage = get_garage_client()
        return garage.delete_projection(ontology, embedding_source)

    except Exception as e:
        logger.warning(f"Failed to invalidate projection cache for {ontology}: {e}")
        return False


def get_projection_history(ontology: str, embedding_source: str = "concepts", limit: int = 10) -> list:
    """
    List historical projection snapshots for an ontology.

    Args:
        ontology: Ontology name
        embedding_source: Source type (default: concepts)
        limit: Maximum snapshots to return (default: 10)

    Returns:
        List of snapshot metadata dicts (sorted newest first)
    """
    try:
        from api.api.lib.garage_client import get_garage_client

        garage = get_garage_client()
        return garage.get_projection_history(ontology, embedding_source, limit)

    except Exception as e:
        logger.warning(f"Failed to get projection history from Garage for {ontology}: {e}")
        return []
