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

    def get_all_ontology_embeddings(
        self,
        include_grounding: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch all concept embeddings across ALL ontologies.

        Each concept is tagged with its source ontology for visualization coloring.
        Used for cross-ontology projection where centering is computed globally.

        Args:
            include_grounding: Include grounding_strength for each concept

        Returns:
            List of concept dicts with ontology field included
        """
        # Query ALL concepts with their ontology (document) association
        query = """
            SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                MATCH (c:Concept)-[:APPEARS]->(s:Source)
                WHERE c.embedding IS NOT NULL
                RETURN DISTINCT
                    c.concept_id as concept_id,
                    c.label as label,
                    c.embedding as embedding,
                    c.grounding_strength as grounding_strength,
                    s.document as ontology
            $$) AS (concept_id agtype, label agtype, embedding agtype, grounding_strength agtype, ontology agtype)
        """

        concepts = []
        seen_ids = set()  # Dedupe concepts that appear in multiple ontologies
        conn = self.client.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    concept_id = str(row[0]).strip('"')

                    # Skip duplicates (concept may appear in multiple sources)
                    if concept_id in seen_ids:
                        continue
                    seen_ids.add(concept_id)

                    label = str(row[1]).strip('"')
                    ontology = str(row[4]).strip('"') if row[4] else "Unknown"

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
                        "grounding_strength": grounding,
                        "ontology": ontology
                    })

            logger.info(f"Fetched {len(concepts)} concepts with embeddings across all ontologies")

        finally:
            self.client.pool.putconn(conn)

        return concepts

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

    def get_source_embeddings(
        self,
        ontology: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch source/evidence chunk embeddings for an ontology.

        Args:
            ontology: Ontology name (document field in Source nodes)

        Returns:
            List of source chunk dicts with:
            - source_id: Source node identifier
            - chunk_index: Chunk number within source
            - label: Truncated chunk text (first 50 chars)
            - embedding: Vector embedding (numpy array)
            - full_text: Full chunk text for tooltip
        """
        import struct

        # Query source embeddings for this ontology
        query = """
            SELECT
                se.source_id,
                se.chunk_index,
                se.chunk_text,
                se.embedding,
                se.embedding_dimension
            FROM kg_api.source_embeddings se
            JOIN (
                SELECT *
                FROM cypher('knowledge_graph', $$
                    MATCH (s:Source {document: '%s'})
                    RETURN s.source_id as source_id
                $$) AS (source_id text)
            ) s ON se.source_id = s.source_id
            ORDER BY se.source_id, se.chunk_index
        """ % ontology

        sources = []
        conn = self.client.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    source_id = row[0]
                    chunk_index = row[1]
                    chunk_text = row[2]
                    embedding_bytes = row[3]
                    embedding_dim = row[4]

                    # Parse embedding from bytea (float16 or float32)
                    try:
                        if embedding_bytes:
                            # Assume float16 (2 bytes per value)
                            if len(embedding_bytes) == embedding_dim * 2:
                                embedding = np.frombuffer(embedding_bytes, dtype=np.float16).astype(np.float32)
                            # Or float32 (4 bytes per value)
                            elif len(embedding_bytes) == embedding_dim * 4:
                                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                            else:
                                logger.warning(f"Unexpected embedding size for {source_id}:{chunk_index}")
                                continue
                        else:
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to parse embedding for {source_id}:{chunk_index}: {e}")
                        continue

                    # Create label from truncated text
                    label = chunk_text[:50] + "..." if len(chunk_text) > 50 else chunk_text
                    label = label.replace("\n", " ")

                    sources.append({
                        "source_id": f"{source_id}:{chunk_index}",
                        "label": label,
                        "embedding": embedding,
                        "full_text": chunk_text,
                        "grounding_strength": None,  # Sources don't have grounding
                    })

            logger.info(f"Fetched {len(sources)} source chunks with embeddings for '{ontology}'")

        finally:
            self.client.pool.putconn(conn)

        return sources

    def get_vocabulary_embeddings(self) -> List[Dict[str, Any]]:
        """
        Fetch vocabulary/relationship type embeddings.

        Returns:
            List of vocabulary dicts with:
            - vocab_id: Relationship type name
            - label: Relationship type name
            - embedding: Vector embedding (numpy array)
            - edge_count: Number of edges using this type
            - category: Vocabulary category
        """
        # Query vocabulary embeddings
        query = """
            SELECT
                relationship_type,
                embedding,
                edge_count,
                category
            FROM kg_api.relationship_vocabulary
            WHERE embedding IS NOT NULL
              AND is_active = TRUE
            ORDER BY edge_count DESC
        """

        vocab = []
        conn = self.client.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    rel_type = row[0]
                    embedding_json = row[1]
                    edge_count = row[2]
                    category = row[3]

                    # Parse embedding from JSONB
                    try:
                        if embedding_json:
                            embedding = np.array(embedding_json, dtype=np.float32)
                        else:
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to parse embedding for {rel_type}: {e}")
                        continue

                    vocab.append({
                        "vocab_id": rel_type,
                        "label": rel_type.replace("_", " ").title(),
                        "embedding": embedding,
                        "edge_count": edge_count,
                        "category": category,
                        "grounding_strength": None,  # Could use epistemic status here
                    })

            logger.info(f"Fetched {len(vocab)} vocabulary types with embeddings")

        finally:
            self.client.pool.putconn(conn)

        return vocab

    def batch_compute_grounding(self, concept_ids: List[str]) -> Dict[str, float]:
        """
        Batch compute grounding strength for multiple concepts.

        Optimized for projection datasets - computes grounding for all concepts
        in 2-3 queries instead of N queries.

        Args:
            concept_ids: List of concept IDs to compute grounding for

        Returns:
            Dict mapping concept_id -> grounding_strength
        """
        import json
        from collections import defaultdict

        if not concept_ids:
            return {}

        groundings = {cid: 0.0 for cid in concept_ids}

        conn = self.client.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Step 1: Build polarity axis (same as single-concept version)
                POLARITY_PAIRS = [
                    ("SUPPORTS", "CONTRADICTS"),
                    ("VALIDATES", "REFUTES"),
                    ("CONFIRMS", "DISPROVES"),
                    ("REINFORCES", "OPPOSES"),
                    ("ENABLES", "PREVENTS"),
                ]

                all_pair_terms = set()
                for positive, negative in POLARITY_PAIRS:
                    all_pair_terms.add(positive)
                    all_pair_terms.add(negative)

                terms_list = ','.join([f"'{t}'" for t in all_pair_terms])
                cur.execute(f"""
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type IN ({terms_list})
                      AND embedding IS NOT NULL
                """)

                pair_embeddings = {}
                for row in cur.fetchall():
                    rel_type, emb_json = row[0], row[1]
                    if isinstance(emb_json, str):
                        emb_array = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        emb_array = np.array(emb_json, dtype=float)
                    else:
                        continue
                    pair_embeddings[rel_type] = emb_array

                # Calculate polarity axis
                difference_vectors = []
                for positive, negative in POLARITY_PAIRS:
                    if positive in pair_embeddings and negative in pair_embeddings:
                        diff_vec = pair_embeddings[positive] - pair_embeddings[negative]
                        difference_vectors.append(diff_vec)

                if len(difference_vectors) == 0:
                    logger.warning("No polarity pairs available for grounding")
                    return groundings

                polarity_axis = np.mean(difference_vectors, axis=0)
                axis_magnitude = np.linalg.norm(polarity_axis)
                if axis_magnitude == 0:
                    return groundings
                polarity_axis = polarity_axis / axis_magnitude

                logger.info(f"Polarity axis computed from {len(difference_vectors)} pairs")

                # Step 2: Batch fetch ALL incoming edges for ALL concepts
                # Build concept ID list for SQL
                concept_id_list = ','.join([f"'{cid}'" for cid in concept_ids])

                # Query all incoming edges to these concepts
                batch_edges_query = f"""
                    SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                        MATCH (c:Concept)<-[r]-(source)
                        WHERE c.concept_id IN [{concept_id_list}]
                        RETURN c.concept_id as target_concept, type(r) as rel_type, r.confidence as confidence
                    $$) AS (target_concept agtype, rel_type agtype, confidence agtype)
                """

                cur.execute(batch_edges_query)
                all_edges = cur.fetchall()

                if not all_edges:
                    logger.info("No incoming edges found for concepts")
                    return groundings

                # Group edges by target concept
                edges_by_concept = defaultdict(list)
                rel_types_needed = set()

                for row in all_edges:
                    target = str(row[0]).strip('"')
                    rel_type = str(row[1]).strip('"')
                    conf_str = str(row[2]) if row[2] else "1.0"
                    try:
                        confidence = float(conf_str.strip('"'))
                    except:
                        confidence = 1.0

                    edges_by_concept[target].append({
                        'rel_type': rel_type,
                        'confidence': confidence
                    })
                    rel_types_needed.add(rel_type)

                logger.info(f"Fetched {len(all_edges)} edges for {len(edges_by_concept)} concepts")

                # Step 3: Fetch vocabulary embeddings for all relationship types
                if rel_types_needed:
                    types_list = ','.join([f"'{t}'" for t in rel_types_needed])
                    cur.execute(f"""
                        SELECT relationship_type, embedding
                        FROM kg_api.relationship_vocabulary
                        WHERE relationship_type IN ({types_list})
                          AND embedding IS NOT NULL
                    """)

                    vocab_embeddings = {}
                    for row in cur.fetchall():
                        rel_type, emb_json = row[0], row[1]
                        if isinstance(emb_json, str):
                            emb_array = np.array(json.loads(emb_json), dtype=float)
                        elif isinstance(emb_json, list):
                            emb_array = np.array(emb_json, dtype=float)
                        else:
                            continue
                        vocab_embeddings[rel_type] = emb_array
                else:
                    vocab_embeddings = {}

                # Step 4: Compute grounding for each concept
                for concept_id in concept_ids:
                    edges = edges_by_concept.get(concept_id, [])
                    if not edges:
                        continue

                    total_polarity = 0.0
                    total_confidence = 0.0

                    for edge in edges:
                        rel_type = edge['rel_type']
                        if rel_type not in vocab_embeddings:
                            continue

                        edge_emb = vocab_embeddings[rel_type]
                        confidence = edge['confidence']

                        # Project onto polarity axis
                        polarity_projection = np.dot(edge_emb, polarity_axis)
                        total_polarity += confidence * float(polarity_projection)
                        total_confidence += confidence

                    if total_confidence > 0:
                        groundings[concept_id] = total_polarity / total_confidence

                grounded_count = sum(1 for g in groundings.values() if g != 0.0)
                logger.info(f"Computed grounding for {grounded_count}/{len(concept_ids)} concepts")

                return groundings

        except Exception as e:
            logger.error(f"Error in batch grounding: {e}", exc_info=True)
            return groundings
        finally:
            self.client.pool.putconn(conn)

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
        spread: float = 1.0,
        metric: Literal["cosine", "euclidean"] = "cosine",
        normalize_l2: bool = True,
        center: bool = True,
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
            min_dist: UMAP min_dist (cluster tightness, 0.0-1.0, lower=tighter)
            spread: UMAP spread (scale of embedding, 1.0-3.0, higher=more separation)
            metric: Distance metric - "cosine" (angular distance, best for embeddings)
                    or "euclidean" (L2 distance, spatial relationships)
            normalize_l2: Whether to L2-normalize embeddings before projection
                          (recommended for semantic embeddings)
            center: Whether to center embeddings (subtract mean) before normalization.
                    Removes the "common component" that causes anisotropy artifacts
                    (nested meatball/concentric shell problem). Recommended True.
            random_state: Random seed for reproducibility

        Returns:
            (N, n_components) array of projected coordinates
        """
        n_samples = len(embeddings)

        if n_samples < 2:
            raise ValueError(f"Need at least 2 samples, got {n_samples}")

        # Center embeddings by subtracting mean (removes common component/anisotropy)
        # This breaks apart the "nested meatball" artifact where all embeddings
        # cluster by their deviation from the average rather than by semantic content.
        # Must be done BEFORE L2 normalization.
        if center:
            mean_vector = np.mean(embeddings, axis=0)
            embeddings = embeddings - mean_vector
            logger.debug(f"Embeddings centered (mean norm: {np.linalg.norm(mean_vector):.4f})")

        # L2-normalize embeddings if requested (best practice for semantic vectors)
        # This makes cosine distance equivalent to Euclidean on the unit sphere
        if normalize_l2:
            from sklearn.preprocessing import normalize
            embeddings = normalize(embeddings, norm='l2')
            logger.debug("Embeddings L2-normalized")

        # Adjust perplexity for small datasets
        effective_perplexity = min(perplexity, (n_samples - 1) // 3)
        if effective_perplexity < 5:
            effective_perplexity = max(2, effective_perplexity)

        logger.info(
            f"Computing {algorithm.upper()} projection ({metric} metric, "
            f"{'L2-norm' if normalize_l2 else 'raw'}): "
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
                spread=spread,
                random_state=random_state,
                metric=metric
            )
            projection = reducer.fit_transform(embeddings)

        else:  # tsne
            if not TSNE_AVAILABLE:
                raise ValueError("t-SNE not available. Install scikit-learn.")

            reducer = TSNE(
                n_components=n_components,
                perplexity=effective_perplexity,
                random_state=random_state,
                metric=metric,
                init="pca" if n_samples > 50 else "random",
                max_iter=1000,
                learning_rate="auto"
            )
            projection = reducer.fit_transform(embeddings)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"{algorithm.upper()} ({metric}) projection computed in {duration:.2f}s")

        return projection.astype(np.float32)

    def generate_projection_dataset(
        self,
        ontology: str,
        algorithm: Literal["tsne", "umap"] = "tsne",
        n_components: int = 3,
        perplexity: int = 30,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        spread: float = 1.0,
        metric: Literal["cosine", "euclidean"] = "cosine",
        normalize_l2: bool = True,
        center: bool = True,
        include_grounding: bool = True,
        refresh_grounding: bool = False,
        include_diversity: bool = False,  # Off by default for performance
        embedding_source: Literal["concepts", "sources", "vocabulary", "combined"] = "concepts"
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
            min_dist: UMAP min_dist (cluster tightness, lower=tighter)
            spread: UMAP spread (embedding scale, higher=more separation)
            metric: Distance metric - "cosine" (angular) or "euclidean" (L2)
            normalize_l2: L2-normalize embeddings before projection (recommended)
            center: Center embeddings (subtract mean) before normalization.
                    Fixes "nested meatball" anisotropy artifact. Recommended True.
            include_grounding: Include grounding strength
            refresh_grounding: Compute fresh grounding (vs using stored values)
            include_diversity: Include diversity scores (slower)
            embedding_source: Which embeddings to project:
                - "concepts": Concept node embeddings (default)
                - "sources": Source/evidence chunk embeddings
                - "vocabulary": Relationship type embeddings
                - "combined": Concepts + sources together

        Returns:
            Complete projection dataset dict ready for JSON serialization
        """
        start_time = datetime.now()

        # Fetch embeddings based on source
        items = []
        item_type = "concept"  # For result field naming

        # Cross-ontology mode: project ALL concepts together
        if ontology == "__all__":
            items = self.get_all_ontology_embeddings(
                include_grounding=include_grounding
            )
            item_type = "concept"
            # Note: diversity not supported in cross-ontology mode (too slow)

        elif embedding_source == "concepts":
            items = self.get_ontology_embeddings(
                ontology,
                include_grounding=include_grounding,
                include_diversity=include_diversity
            )
            item_type = "concept"

        elif embedding_source == "sources":
            items = self.get_source_embeddings(ontology)
            item_type = "source"

        elif embedding_source == "vocabulary":
            items = self.get_vocabulary_embeddings()
            item_type = "vocabulary"

        elif embedding_source == "combined":
            # Combine concepts and sources
            concepts = self.get_ontology_embeddings(
                ontology,
                include_grounding=include_grounding,
                include_diversity=include_diversity
            )
            sources = self.get_source_embeddings(ontology)

            # Tag each item with its type
            for c in concepts:
                c["item_type"] = "concept"
            for s in sources:
                s["item_type"] = "source"
                # Normalize ID field
                s["concept_id"] = s.get("source_id", s.get("concept_id"))

            items = concepts + sources
            item_type = "mixed"

        if not items:
            return {
                "ontology": ontology,
                "embedding_source": embedding_source,
                "error": f"No {embedding_source} with embeddings found",
                "concept_count": 0
            }

        if len(items) < 2:
            return {
                "ontology": ontology,
                "embedding_source": embedding_source,
                "error": f"Need at least 2 {embedding_source} for projection",
                "concept_count": len(items)
            }

        # Stack embeddings into matrix
        embeddings = np.stack([item["embedding"] for item in items])

        # Compute projection
        projection = self.compute_projection(
            embeddings,
            algorithm=algorithm,
            n_components=n_components,
            perplexity=perplexity,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            spread=spread,
            metric=metric,
            normalize_l2=normalize_l2,
            center=center
        )

        # Batch compute fresh grounding if requested (only for concepts)
        fresh_groundings = {}
        if include_grounding and refresh_grounding and embedding_source in ("concepts", "combined"):
            concept_ids = [
                item.get("concept_id") for item in items
                if item.get("concept_id") and item.get("item_type", "concept") == "concept"
            ]
            if concept_ids:
                logger.info(f"Computing fresh grounding for {len(concept_ids)} concepts...")
                fresh_groundings = self.batch_compute_grounding(concept_ids)
                # Update items with fresh grounding values
                for item in items:
                    cid = item.get("concept_id")
                    if cid and cid in fresh_groundings:
                        item["grounding_strength"] = fresh_groundings[cid]

        # Build result dataset
        result_items = []
        grounding_values = []
        diversity_values = []

        for i, item in enumerate(items):
            coords = projection[i].tolist()

            # Use concept_id or generate from source_id/vocab_id
            item_id = item.get("concept_id") or item.get("source_id") or item.get("vocab_id")

            entry = {
                "concept_id": item_id,
                "label": item["label"],
                "x": coords[0],
                "y": coords[1],
                "z": coords[2] if n_components == 3 else 0.0
            }

            # Add item type for combined mode
            if "item_type" in item:
                entry["item_type"] = item["item_type"]

            # Add ontology for cross-ontology mode
            if "ontology" in item:
                entry["ontology"] = item["ontology"]

            if include_grounding:
                entry["grounding_strength"] = item.get("grounding_strength")
                if item.get("grounding_strength") is not None:
                    grounding_values.append(item["grounding_strength"])

            if include_diversity:
                entry["diversity_score"] = item.get("diversity_score")
                entry["diversity_related_count"] = item.get("diversity_related_count", 0)
                if item.get("diversity_score") is not None:
                    diversity_values.append(item["diversity_score"])

            # Add extra metadata for sources
            if "full_text" in item:
                entry["full_text"] = item["full_text"]
            if "category" in item:
                entry["category"] = item["category"]
            if "edge_count" in item:
                entry["edge_count"] = item["edge_count"]

            result_items.append(entry)

        # Compute statistics
        duration = (datetime.now() - start_time).total_seconds()

        stats = {
            "concept_count": len(items),
            "computation_time_ms": int(duration * 1000),
            "embedding_dims": embeddings.shape[1]
        }

        if grounding_values:
            stats["grounding_range"] = [min(grounding_values), max(grounding_values)]
        if diversity_values:
            stats["diversity_range"] = [min(diversity_values), max(diversity_values)]

        # Generate changelist ID for cache invalidation
        changelist_id = self._generate_changelist_id(f"{ontology}:{embedding_source}", len(items))

        return {
            "ontology": ontology,
            "embedding_source": embedding_source,
            "changelist_id": changelist_id,
            "algorithm": algorithm,
            "parameters": {
                "n_components": n_components,
                "perplexity": perplexity if algorithm == "tsne" else None,
                "n_neighbors": n_neighbors if algorithm == "umap" else None,
                "min_dist": min_dist if algorithm == "umap" else None,
                "spread": spread if algorithm == "umap" else None,
                "metric": metric,
                "normalize_l2": normalize_l2,
                "center": center
            },
            "computed_at": datetime.utcnow().isoformat() + "Z",
            "concepts": result_items,  # Keep "concepts" key for backward compatibility
            "statistics": stats
        }

    def _generate_changelist_id(self, ontology: str, concept_count: int) -> str:
        """Generate a changelist ID for cache invalidation."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        content = f"{ontology}:{concept_count}:{timestamp}"
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        return f"cl_{timestamp}_{short_hash}"
