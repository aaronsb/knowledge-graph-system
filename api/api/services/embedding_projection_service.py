"""
Embedding Projection Service (ADR-078).

Computes t-SNE or UMAP dimensionality reduction projections of concept embeddings
for visualization in the Embedding Landscape Explorer.

The service:
1. Fetches concept embeddings for an ontology from the graph
2. Computes 3D projections using t-SNE (sklearn) or UMAP (if available)
3. Enriches with grounding and diversity metrics
4. Returns projected coordinates for visualization
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
import numpy as np

logger = logging.getLogger(__name__)

# Algorithm availability
try:
    from sklearn.manifold import TSNE
    TSNE_AVAILABLE = True
except ImportError:
    TSNE_AVAILABLE = False
    logger.warning("sklearn.manifold.TSNE not available")

try:
    from umap import UMAP
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False
    logger.debug("umap-learn not available, using t-SNE only")


class EmbeddingProjectionService:
    """
    Service for computing and caching embedding projections.

    Projections reduce high-dimensional embeddings (768+) to 3D coordinates
    while preserving local/global structure for visualization.
    """

    def __init__(self, age_client):
        """
        Initialize with AGE client.

        Args:
            age_client: AGEClient instance for graph queries
        """
        self.client = age_client

    def get_available_algorithms(self) -> List[str]:
        """Return list of available projection algorithms."""
        algorithms = []
        if TSNE_AVAILABLE:
            algorithms.append("tsne")
        if UMAP_AVAILABLE:
            algorithms.append("umap")
        return algorithms

    def get_ontology_embeddings(
        self,
        ontology: str,
        include_grounding: bool = True,
        include_diversity: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch all concept embeddings for an ontology.

        Args:
            ontology: Ontology name (document field in Source nodes)
            include_grounding: Include grounding_strength for each concept
            include_diversity: Include diversity metrics (slower)

        Returns:
            List of concept dicts with:
            - concept_id: Unique identifier
            - label: Human-readable label
            - embedding: 768-dim vector (numpy array)
            - grounding_strength: float (-1 to 1) if include_grounding
            - diversity_score: float if include_diversity
        """
        # Query concepts with embeddings for this ontology
        query = """
            SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                MATCH (c:Concept)-[:APPEARS]->(:Source {document: '%s'})
                WHERE c.embedding IS NOT NULL
                RETURN DISTINCT
                    c.concept_id as concept_id,
                    c.label as label,
                    c.embedding as embedding,
                    c.grounding_strength as grounding_strength
            $$) AS (concept_id agtype, label agtype, embedding agtype, grounding_strength agtype)
        """ % ontology

        concepts = []
        conn = self.client.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    concept_id = str(row[0]).strip('"')
                    label = str(row[1]).strip('"')

                    # Parse embedding from agtype
                    embedding_str = str(row[2])
                    try:
                        embedding = np.array(json.loads(embedding_str), dtype=np.float32)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse embedding for {concept_id}: {e}")
                        continue

                    # Parse grounding
                    grounding = None
                    if include_grounding and row[3] is not None:
                        try:
                            grounding = float(str(row[3]))
                        except (ValueError, TypeError):
                            pass

                    concepts.append({
                        "concept_id": concept_id,
                        "label": label,
                        "embedding": embedding,
                        "grounding_strength": grounding
                    })

            logger.info(f"Fetched {len(concepts)} concepts with embeddings for '{ontology}'")

        finally:
            self.client.pool.putconn(conn)

        # Add diversity if requested (more expensive)
        if include_diversity and concepts:
            concepts = self._add_diversity_scores(concepts)

        return concepts

    def _add_diversity_scores(self, concepts: List[Dict]) -> List[Dict]:
        """
        Add diversity scores to concepts.

        Uses the existing diversity analyzer service.
        """
        try:
            from api.api.services.diversity_analyzer import DiversityAnalyzer
            analyzer = DiversityAnalyzer(self.client)

            for concept in concepts:
                try:
                    diversity = analyzer.compute_diversity(concept["concept_id"])
                    concept["diversity_score"] = diversity.get("diversity_score")
                    concept["diversity_related_count"] = diversity.get("related_count", 0)
                except Exception as e:
                    logger.debug(f"Could not compute diversity for {concept['concept_id']}: {e}")
                    concept["diversity_score"] = None
                    concept["diversity_related_count"] = 0

        except ImportError:
            logger.warning("DiversityAnalyzer not available, skipping diversity scores")
            for concept in concepts:
                concept["diversity_score"] = None
                concept["diversity_related_count"] = 0

        return concepts

    def compute_projection(
        self,
        embeddings: np.ndarray,
        algorithm: Literal["tsne", "umap"] = "tsne",
        n_components: int = 3,
        perplexity: int = 30,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        random_state: int = 42
    ) -> np.ndarray:
        """
        Compute dimensionality reduction projection.

        Args:
            embeddings: (N, D) array of embeddings
            algorithm: "tsne" or "umap"
            n_components: Output dimensions (2 or 3)
            perplexity: t-SNE perplexity (local vs global, 5-100)
            n_neighbors: UMAP n_neighbors (local structure, 5-50)
            min_dist: UMAP min_dist (point spread, 0.0-1.0)
            random_state: Random seed for reproducibility

        Returns:
            (N, n_components) array of projected coordinates
        """
        n_samples = len(embeddings)

        if n_samples < 2:
            raise ValueError(f"Need at least 2 samples, got {n_samples}")

        # Adjust perplexity for small datasets
        effective_perplexity = min(perplexity, (n_samples - 1) // 3)
        if effective_perplexity < 5:
            effective_perplexity = max(2, effective_perplexity)

        logger.info(
            f"Computing {algorithm.upper()} projection: "
            f"{n_samples} samples → {n_components}D"
        )

        start_time = datetime.now()

        if algorithm == "umap":
            if not UMAP_AVAILABLE:
                raise ValueError("UMAP not available. Install umap-learn or use tsne.")

            reducer = UMAP(
                n_components=n_components,
                n_neighbors=min(n_neighbors, n_samples - 1),
                min_dist=min_dist,
                random_state=random_state,
                metric="cosine"
            )
            projection = reducer.fit_transform(embeddings)

        else:  # tsne
            if not TSNE_AVAILABLE:
                raise ValueError("t-SNE not available. Install scikit-learn.")

            reducer = TSNE(
                n_components=n_components,
                perplexity=effective_perplexity,
                random_state=random_state,
                metric="cosine",
                init="pca" if n_samples > 50 else "random",
                max_iter=1000,
                learning_rate="auto"
            )
            projection = reducer.fit_transform(embeddings)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"{algorithm.upper()} projection computed in {duration:.2f}s")

        return projection.astype(np.float32)

    def generate_projection_dataset(
        self,
        ontology: str,
        algorithm: Literal["tsne", "umap"] = "tsne",
        n_components: int = 3,
        perplexity: int = 30,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        include_grounding: bool = True,
        include_diversity: bool = False  # Off by default for performance
    ) -> Dict[str, Any]:
        """
        Generate complete projection dataset for an ontology.

        This is the main entry point for the projection worker.

        Args:
            ontology: Ontology name
            algorithm: Projection algorithm
            n_components: Output dimensions
            perplexity: t-SNE perplexity
            n_neighbors: UMAP n_neighbors
            min_dist: UMAP min_dist
            include_grounding: Include grounding strength
            include_diversity: Include diversity scores (slower)

        Returns:
            Complete projection dataset dict ready for JSON serialization
        """
        start_time = datetime.now()

        # Fetch embeddings
        concepts = self.get_ontology_embeddings(
            ontology,
            include_grounding=include_grounding,
            include_diversity=include_diversity
        )

        if not concepts:
            return {
                "ontology": ontology,
                "error": "No concepts with embeddings found",
                "concept_count": 0
            }

        if len(concepts) < 2:
            return {
                "ontology": ontology,
                "error": "Need at least 2 concepts for projection",
                "concept_count": len(concepts)
            }

        # Stack embeddings into matrix
        embeddings = np.stack([c["embedding"] for c in concepts])

        # Compute projection
        projection = self.compute_projection(
            embeddings,
            algorithm=algorithm,
            n_components=n_components,
            perplexity=perplexity,
            n_neighbors=n_neighbors,
            min_dist=min_dist
        )

        # Build result dataset
        result_concepts = []
        grounding_values = []
        diversity_values = []

        for i, concept in enumerate(concepts):
            coords = projection[i].tolist()

            entry = {
                "concept_id": concept["concept_id"],
                "label": concept["label"],
                "x": coords[0],
                "y": coords[1],
                "z": coords[2] if n_components == 3 else 0.0
            }

            if include_grounding:
                entry["grounding_strength"] = concept.get("grounding_strength")
                if concept.get("grounding_strength") is not None:
                    grounding_values.append(concept["grounding_strength"])

            if include_diversity:
                entry["diversity_score"] = concept.get("diversity_score")
                entry["diversity_related_count"] = concept.get("diversity_related_count", 0)
                if concept.get("diversity_score") is not None:
                    diversity_values.append(concept["diversity_score"])

            result_concepts.append(entry)

        # Compute statistics
        duration = (datetime.now() - start_time).total_seconds()

        stats = {
            "concept_count": len(concepts),
            "computation_time_ms": int(duration * 1000),
            "embedding_dims": embeddings.shape[1]
        }

        if grounding_values:
            stats["grounding_range"] = [min(grounding_values), max(grounding_values)]
        if diversity_values:
            stats["diversity_range"] = [min(diversity_values), max(diversity_values)]

        # Generate changelist ID for cache invalidation
        changelist_id = self._generate_changelist_id(ontology, len(concepts))

        return {
            "ontology": ontology,
            "changelist_id": changelist_id,
            "algorithm": algorithm,
            "parameters": {
                "n_components": n_components,
                "perplexity": perplexity if algorithm == "tsne" else None,
                "n_neighbors": n_neighbors if algorithm == "umap" else None,
                "min_dist": min_dist if algorithm == "umap" else None
            },
            "computed_at": datetime.utcnow().isoformat() + "Z",
            "concepts": result_concepts,
            "statistics": stats
        }

    def _generate_changelist_id(self, ontology: str, concept_count: int) -> str:
        """Generate a changelist ID for cache invalidation."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        content = f"{ontology}:{concept_count}:{timestamp}"
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"cl_{timestamp}_{short_hash}"
