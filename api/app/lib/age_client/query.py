"""
Query mixin for search, learned knowledge, and grounding operations.

Provides vector similarity search, learned knowledge management
(human/AI-created connections), and grounding strength calculation
using polarity axis projection (ADR-044).

Key operations:
- vector_search(): Cosine similarity search across concept embeddings
- Learned knowledge CRUD: validate, create, list, delete connections
- calculate_grounding_strength_semantic(): Polarity axis projection
- facade property: Lazy-loaded GraphQueryFacade for namespace-safe queries (ADR-048)

Caching (ADR-201 Phase 5f):
  The polarity axis used for grounding is vocabulary-level data — it depends only
  on relationship type embeddings, not on any individual concept. It's cached
  against graph_metrics.vocabulary_change_counter and reused across all concepts.
  Vocabulary mutations (synonym collapse, embedding regeneration) bump the counter,
  invalidating the cache. Each concept's grounding is then independently cached
  against the graph generation counter (graph_accel.generation).
"""

import json
import logging
import threading
from collections import defaultdict
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
from psycopg2 import extras

logger = logging.getLogger(__name__)

# ---- Two-tier grounding cache (ADR-201 Phase 5f) ----
#
# Tier 1: Polarity axis — derived from vocabulary embeddings, shared across all
# concepts. Invalidates when vocabulary_change_counter changes (synonym collapse,
# embedding regeneration). One axis computation replaces N identical DB queries.
#
# Tier 2: Per-concept grounding — cached against graph generation. Each concept's
# grounding depends only on its own incoming edges (no cross-concept dependency),
# making independent caching safe. Invalidates when graph_accel_invalidate() bumps
# the generation after ingestion, edits, or vocabulary merges.
#
# Analogy: like GI probe caching in real-time rendering — only recompute when the
# "frame" (generation) changes, and each "probe" (concept) is independent.

_polarity_axis_cache_lock = threading.Lock()
_polarity_axis_cache: Optional[Tuple[int, np.ndarray]] = None  # (vocab_generation, axis_vector)

_grounding_cache_lock = threading.Lock()
_grounding_cache: Dict[Tuple[str, int], Tuple[float, Dict]] = {}  # (concept_id, graph_gen) → (grounding, confidence)
_grounding_cache_generation: Optional[int] = None  # tracks which graph generation the cache covers

from api.app.constants import BATCH_CHUNK_SIZE


def _parse_embedding(emb_json) -> Optional[np.ndarray]:
    """Parse embedding from various storage formats (JSONB, list, str)."""
    if isinstance(emb_json, str):
        return np.array(json.loads(emb_json), dtype=float)
    elif isinstance(emb_json, list):
        return np.array(emb_json, dtype=float)
    elif isinstance(emb_json, dict):
        return np.array(list(emb_json.values()), dtype=float)
    else:
        try:
            return np.array(list(emb_json), dtype=float)
        except Exception:
            return None


def _parse_confidence(value) -> float:
    """Parse edge confidence from AGE result (may be float, str, dict, or None)."""
    if value is None:
        return 1.0
    if isinstance(value, dict):
        return float(value.get('confidence', 1.0))
    return float(value)


class QueryMixin:
    """Vector search, learned knowledge, grounding strength, and query facade."""

    def vector_search(
        self,
        embedding: List[float],
        threshold: float = 0.85,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar concepts using vector similarity.

        Note: Without pgvector, this performs a full scan with Python cosine similarity.
        Performance will degrade with large datasets. Consider adding pgvector support.

        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity threshold (0.0-1.0)
            top_k: Maximum number of results to return

        Returns:
            List of dictionaries with concept_id, label, and similarity score

        Raises:
            ValueError: If threshold is out of range
            Exception: If search fails
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        # Get all concepts with embeddings
        query = """
        MATCH (c:Concept)
        WHERE c.embedding IS NOT NULL
        RETURN c.concept_id AS concept_id,
               c.label AS label,
               c.description AS description,
               c.embedding AS embedding
        """

        try:
            results = self._execute_cypher(query)

            # Calculate cosine similarity in Python
            import numpy as np

            query_emb = np.array(embedding, dtype=float)
            similarities = []

            for record in results:
                # Parse agtype result
                concept_id_agtype = record.get('concept_id')
                label_agtype = record.get('label')
                description_agtype = record.get('description')
                embedding_agtype = record.get('embedding')

                # Extract values from agtype (strip quotes)
                concept_id = str(concept_id_agtype).strip('"')
                label = str(label_agtype).strip('"')
                description = str(description_agtype).strip('"') if description_agtype else ""

                # Parse embedding from agtype (it's stored as JSON array)
                embedding_str = str(embedding_agtype)
                try:
                    concept_emb = np.array(json.loads(embedding_str), dtype=float)
                except (json.JSONDecodeError, ValueError):
                    continue

                # Calculate cosine similarity
                similarity = float(
                    np.dot(query_emb, concept_emb) /
                    (np.linalg.norm(query_emb) * np.linalg.norm(concept_emb))
                )

                if similarity >= threshold:
                    similarities.append({
                        "concept_id": concept_id,
                        "label": label,
                        "description": description,
                        "similarity": similarity
                    })

            # Sort by similarity and limit
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            raise Exception(f"Vector search failed: {e}")

    def get_document_concepts(
        self,
        document_name: str,
        limit: int = 50,
        recent_chunks_only: Optional[int] = None,
        warn_on_empty: bool = False
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        Retrieve concepts from a specific document for context awareness.

        Args:
            document_name: Name of the document
            limit: Maximum number of concepts to return
            recent_chunks_only: If set, only get concepts from last N chunks/paragraphs
            warn_on_empty: If True, returns flag indicating empty database warnings

        Returns:
            Tuple of (list of concept dicts, has_empty_db_warnings)

        Raises:
            Exception: If query fails
        """
        if recent_chunks_only:
            # Get concepts from recent chunks only
            query = f"""
            MATCH (c:Concept)-[:APPEARS]->(s:Source {{document: $document}})
            WITH c, s
            ORDER BY s.paragraph DESC
            LIMIT {recent_chunks_only * 10}
            WITH DISTINCT c
            RETURN c.concept_id AS concept_id, c.label AS label
            LIMIT {limit}
            """
        else:
            # Get all concepts from document
            query = f"""
            MATCH (c:Concept)-[:APPEARS]->(s:Source {{document: $document}})
            RETURN DISTINCT c.concept_id AS concept_id, c.label AS label
            LIMIT {limit}
            """

        try:
            results = self._execute_cypher(
                query,
                params={"document": document_name}
            )

            concepts = []
            for record in results:
                concept_id = str(record.get('concept_id', '')).strip('"')
                label = str(record.get('label', '')).strip('"')
                concepts.append({
                    "concept_id": concept_id,
                    "label": label
                })

            # AGE doesn't have notifications like Neo4j, so we check if results are empty
            has_empty_warnings = warn_on_empty and len(concepts) == 0

            return concepts, has_empty_warnings
        except Exception as e:
            raise Exception(f"Failed to get document concepts: {e}")

    def validate_learned_connection(
        self,
        evidence_embedding: List[float],
        concept_id_1: str,
        concept_id_2: str
    ) -> Dict[str, Any]:
        """
        Validate a learned connection using semantic similarity (smell test).

        Calculates similarity between evidence and both concepts to determine
        cognitive leap required for the connection.

        Args:
            evidence_embedding: Embedding vector for the evidence/rationale text
            concept_id_1: First concept ID
            concept_id_2: Second concept ID

        Returns:
            Dictionary with similarity scores and cognitive leap rating:
            {
                "similarity_to_concept1": float,
                "similarity_to_concept2": float,
                "avg_similarity": float,
                "cognitive_leap": "LOW" | "MEDIUM" | "HIGH",
                "valid": bool
            }
        """
        query = """
        MATCH (c1:Concept {concept_id: $concept_id_1})
        MATCH (c2:Concept {concept_id: $concept_id_2})
        RETURN c1.embedding as emb1, c2.embedding as emb2
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "concept_id_1": concept_id_1,
                    "concept_id_2": concept_id_2
                },
                fetch_one=True
            )

            if not results:
                raise ValueError(f"One or both concepts not found: {concept_id_1}, {concept_id_2}")

            emb1_agtype = results.get("emb1")
            emb2_agtype = results.get("emb2")

            # Parse embeddings from agtype
            try:
                emb1 = json.loads(str(emb1_agtype))
                emb2 = json.loads(str(emb2_agtype))
            except (json.JSONDecodeError, ValueError):
                raise ValueError(f"One or both concepts do not have valid embeddings")

            if emb1 is None or emb2 is None:
                raise ValueError(f"One or both concepts do not have embeddings")

            # Calculate cosine similarity
            import numpy as np

            # Convert embeddings to numpy arrays
            evidence_emb = np.array(evidence_embedding, dtype=float)
            emb1_arr = np.array(emb1, dtype=float)
            emb2_arr = np.array(emb2, dtype=float)

            def cosine_similarity(a, b):
                return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

            sim1 = cosine_similarity(evidence_emb, emb1_arr)
            sim2 = cosine_similarity(evidence_emb, emb2_arr)
            avg_sim = (sim1 + sim2) / 2

            # Determine cognitive leap
            if avg_sim >= 0.85:
                cognitive_leap = "LOW"  # Obvious connection
            elif avg_sim >= 0.70:
                cognitive_leap = "MEDIUM"  # Reasonable leap
            else:
                cognitive_leap = "HIGH"  # Unusual connection

            return {
                "similarity_to_concept1": sim1,
                "similarity_to_concept2": sim2,
                "avg_similarity": avg_sim,
                "cognitive_leap": cognitive_leap,
                "valid": True
            }

        except Exception as e:
            raise Exception(f"Failed to validate connection: {e}")

    def create_learned_source(
        self,
        source_id: str,
        evidence: str,
        created_by: str,
        similarity_score: float,
        cognitive_leap: str
    ) -> Dict[str, Any]:
        """
        Create a learned Source node with provenance metadata.

        Args:
            source_id: Unique identifier (e.g., "learned_2025-10-06_001")
            evidence: Rationale/evidence text
            created_by: Creator identifier ("username", "claude-mcp", etc.)
            similarity_score: Average similarity from validation
            cognitive_leap: "LOW", "MEDIUM", or "HIGH"

        Returns:
            Dictionary with created node properties
        """
        from datetime import datetime, timezone

        document = "AI synthesis" if created_by.startswith("claude") else "User synthesis"
        created_at = datetime.now(timezone.utc).isoformat()

        query = """
        CREATE (s:Source {
            source_id: $source_id,
            document: $document,
            paragraph: 0,
            full_text: $evidence,
            type: 'LEARNED',
            created_by: $created_by,
            created_at: $created_at,
            similarity_score: $similarity_score,
            cognitive_leap: $cognitive_leap
        })
        RETURN s
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "source_id": source_id,
                    "document": document,
                    "evidence": evidence,
                    "created_by": created_by,
                    "created_at": created_at,
                    "similarity_score": similarity_score,
                    "cognitive_leap": cognitive_leap
                },
                fetch_one=True
            )
            if results:
                agtype_result = results.get('s')  # 's' from RETURN s
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create learned Source node: {e}")

    def create_learned_relationship(
        self,
        from_concept_id: str,
        to_concept_id: str,
        relationship_type: str,
        learned_source_id: str
    ) -> bool:
        """
        Create a relationship between concepts with learned source provenance.

        Args:
            from_concept_id: Starting concept ID
            to_concept_id: Target concept ID
            relationship_type: Type of relationship (BRIDGES, LEARNED_CONNECTION, etc.)
            learned_source_id: ID of the learned Source node for provenance

        Returns:
            True if relationship created successfully
        """
        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})
        MATCH (c2:Concept {{concept_id: $to_id}})
        MATCH (s:Source {{source_id: $source_id, type: 'LEARNED'}})
        CREATE (c1)-[r:{relationship_type} {{learned_id: $source_id}}]->(c2)
        RETURN r
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "from_id": from_concept_id,
                    "to_id": to_concept_id,
                    "source_id": learned_source_id
                },
                fetch_one=True
            )
            return len(results) > 0
        except Exception as e:
            raise Exception(f"Failed to create learned relationship: {e}")

    def list_learned_knowledge(
        self,
        creator: Optional[str] = None,
        min_similarity: Optional[float] = None,
        cognitive_leap: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query learned knowledge with optional filters.

        Args:
            creator: Filter by creator username/identifier
            min_similarity: Minimum similarity score threshold
            cognitive_leap: Filter by "LOW", "MEDIUM", or "HIGH"
            limit: Maximum results to return
            offset: Number of results to skip (pagination)

        Returns:
            List of learned knowledge records with metadata
        """
        conditions = ["s.type = 'LEARNED'"]
        if creator:
            conditions.append(f"s.created_by = '{creator}'")
        if min_similarity is not None:
            conditions.append(f"s.similarity_score >= {min_similarity}")
        if cognitive_leap:
            conditions.append(f"s.cognitive_leap = '{cognitive_leap}'")

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (s:Source)
        WHERE {where_clause}
        RETURN s.source_id as learned_id,
               s.full_text as evidence,
               s.created_by as creator,
               s.created_at as created_at,
               s.similarity_score as similarity,
               s.cognitive_leap as cognitive_leap
        ORDER BY s.created_at DESC
        SKIP {offset}
        LIMIT {limit}
        """

        try:
            results = self._execute_cypher(query)

            learned_records = []
            for record in results:
                learned_records.append({
                    "learned_id": str(record.get('learned_id', '')).strip('"'),
                    "evidence": str(record.get('evidence', '')).strip('"'),
                    "creator": str(record.get('creator', '')).strip('"'),
                    "created_at": str(record.get('created_at', '')).strip('"'),
                    "similarity": float(str(record.get('similarity', 0)).strip('"')),
                    "cognitive_leap": str(record.get('cognitive_leap', '')).strip('"')
                })

            return learned_records
        except Exception as e:
            raise Exception(f"Failed to list learned knowledge: {e}")

    def delete_learned_knowledge(
        self,
        learned_id: str
    ) -> Dict[str, int]:
        """
        Delete a learned Source node and its relationships.

        Only deletes nodes with type='LEARNED' to prevent accidental deletion
        of document-extracted knowledge.

        Args:
            learned_id: Source ID of the learned knowledge to delete

        Returns:
            Dictionary with counts: {"source_deleted": 1, "relationships_deleted": N}
        """
        query = """
        MATCH (s:Source {source_id: $learned_id, type: 'LEARNED'})
        OPTIONAL MATCH ()-[r {learned_id: $learned_id}]-()
        WITH s, collect(r) as rels
        FOREACH (rel in rels | DELETE rel)
        DELETE s
        RETURN 1 as source_deleted, size(rels) as relationships_deleted
        """

        try:
            results = self._execute_cypher(
                query,
                params={"learned_id": learned_id},
                fetch_one=True
            )
            if not results:
                return {"source_deleted": 0, "relationships_deleted": 0}

            return {
                "source_deleted": int(str(results.get("source_deleted", 0))),
                "relationships_deleted": int(str(results.get("relationships_deleted", 0)))
            }
        except Exception as e:
            raise Exception(f"Failed to delete learned knowledge: {e}")

    # =========================================================================
    # Grounding Strength Calculation (ADR-044)
    # =========================================================================

    def _get_vocab_generation(self, cur) -> int:
        """Read vocabulary_change_counter from graph_metrics (single-row query)."""
        try:
            cur.execute(
                "SELECT counter FROM graph_metrics "
                "WHERE metric_name = 'vocabulary_change_counter'"
            )
            row = cur.fetchone()
            return int(row['counter']) if row else 0
        except Exception:
            return 0

    def _get_polarity_axis(self, cur) -> Optional[np.ndarray]:
        """Get cached polarity axis, recomputing if vocabulary has changed.

        The polarity axis is derived from vocabulary embeddings for opposing
        relationship pairs (SUPPORTS/CONTRADICTS, etc.). It's shared across
        all concepts — only the per-concept edge projections differ.

        Cached against graph_metrics.vocabulary_change_counter. Invalidates
        when synonym collapse, embedding regeneration, or any vocabulary
        mutation bumps the counter via refresh_graph_metrics().
        """
        global _polarity_axis_cache

        vocab_gen = self._get_vocab_generation(cur)

        with _polarity_axis_cache_lock:
            if _polarity_axis_cache is not None:
                cached_gen, cached_axis = _polarity_axis_cache
                if cached_gen == vocab_gen:
                    return cached_axis

        # Cache miss — recompute from vocabulary embeddings
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
            emb_array = _parse_embedding(row['embedding'])
            if emb_array is not None:
                pair_embeddings[row['relationship_type']] = emb_array

        difference_vectors = []
        for positive, negative in POLARITY_PAIRS:
            if positive in pair_embeddings and negative in pair_embeddings:
                difference_vectors.append(
                    pair_embeddings[positive] - pair_embeddings[negative]
                )

        if not difference_vectors:
            logger.warning("No polarity pairs available for axis calculation (need embeddings)")
            return None

        polarity_axis = np.mean(difference_vectors, axis=0)
        axis_magnitude = np.linalg.norm(polarity_axis)
        if axis_magnitude == 0:
            logger.warning("Polarity axis has zero magnitude")
            return None

        polarity_axis = polarity_axis / axis_magnitude
        logger.info(
            f"Polarity axis computed from {len(difference_vectors)} pairs "
            f"(vocab generation {vocab_gen})"
        )

        with _polarity_axis_cache_lock:
            _polarity_axis_cache = (vocab_gen, polarity_axis)

        return polarity_axis

    def calculate_grounding_strength_semantic(
        self,
        concept_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> float:
        """
        Calculate grounding strength using polarity axis projection (ADR-044).

        Uses multiple opposing relationship pairs to triangulate a robust semantic
        polarity axis (support ↔ contradict). Edge embeddings are projected onto
        this axis via dot product to determine their grounding contribution.

        Two-tier caching (ADR-201 Phase 5f):
          Tier 1 — Polarity axis: Vocabulary-level, shared across all concepts.
          Cached against graph_metrics.vocabulary_change_counter. Recomputed only
          when vocabulary mutates (synonym collapse, embedding regeneration).

          Tier 2 — Per-concept grounding: Cached against graph generation
          (graph_accel.generation). Each concept's grounding depends only on its
          own incoming edges — no cross-concept dependency — so per-concept
          caching is safe. Recomputed only when the graph mutates.

        Args:
            concept_id: Target concept to calculate grounding for
            include_types: Optional list of relationship types to include
            exclude_types: Optional list of relationship types to exclude

        Returns:
            Grounding strength float in range approximately [-1.0, 1.0]:
            - Positive = Edge types align with support-like semantics
            - Zero = Edge types are neutral or balanced
            - Negative = Edge types align with contradict-like semantics

        References:
            - ADR-044: Probabilistic Truth Convergence
            - ADR-045: Unified Embedding Generation
        """
        global _grounding_cache, _grounding_cache_generation

        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # ---- Tier 2 cache check: per-concept grounding ----
                # Read graph generation from graph_accel if available,
                # otherwise fall back to a simple counter.
                graph_gen = self._get_graph_generation(cur)

                # Evict entire cache if graph generation changed
                with _grounding_cache_lock:
                    if _grounding_cache_generation != graph_gen:
                        if _grounding_cache:
                            logger.info(
                                f"Grounding cache invalidated: generation "
                                f"{_grounding_cache_generation} → {graph_gen} "
                                f"({len(_grounding_cache)} entries evicted)"
                            )
                        _grounding_cache.clear()
                        _grounding_cache_generation = graph_gen

                    cache_key = (concept_id, graph_gen)
                    if cache_key in _grounding_cache:
                        return _grounding_cache[cache_key]

                # ---- Tier 1: get or compute polarity axis ----
                polarity_axis = self._get_polarity_axis(cur)
                if polarity_axis is None:
                    return 0.0

                # ---- Per-concept: fetch incoming edges ----
                cypher_edges_query = f"""
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})<-[r]-(source)
                    RETURN type(r) as rel_type, r.confidence as confidence
                """
                edge_results = self._execute_cypher(cypher_edges_query)

                if not edge_results:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                # Filter relationship types
                rel_types = set(edge['rel_type'] for edge in edge_results)
                if include_types:
                    rel_types = rel_types & set(include_types)
                if exclude_types:
                    rel_types = rel_types - set(exclude_types)
                if not rel_types:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                # Fetch vocabulary embeddings for these edge types
                types_list = ','.join([f"'{t}'" for t in rel_types])
                cur.execute(f"""
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type IN ({types_list})
                      AND embedding IS NOT NULL
                """)
                vocab_embeddings = {
                    row['relationship_type']: row['embedding']
                    for row in cur.fetchall()
                }

                # Project each edge onto polarity axis
                total_polarity = 0.0
                total_confidence = 0.0
                edge_count = 0

                for edge in edge_results:
                    rel_type = edge['rel_type']
                    if rel_type not in vocab_embeddings:
                        continue

                    edge_emb = _parse_embedding(vocab_embeddings[rel_type])
                    if edge_emb is None:
                        continue

                    confidence = _parse_confidence(edge.get('confidence'))
                    polarity_projection = np.dot(edge_emb, polarity_axis)
                    total_polarity += confidence * float(polarity_projection)
                    total_confidence += confidence
                    edge_count += 1

                if total_confidence == 0:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                grounding_strength = float(total_polarity / total_confidence)
                logger.debug(
                    f"Grounding for {concept_id}: {grounding_strength:.3f} "
                    f"(from {edge_count} edges)"
                )

                with _grounding_cache_lock:
                    _grounding_cache[cache_key] = grounding_strength

                return grounding_strength

        except Exception as e:
            logger.error(f"Error calculating grounding strength for {concept_id}: {e}")
            return 0.0
        finally:
            self.pool.putconn(conn)

    def calculate_grounding_strength_batch(
        self,
        concept_ids: List[str],
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Batch-compute grounding strength for multiple concepts (ADR-201 Phase 5f).

        Amortized version of calculate_grounding_strength_semantic(). On cache
        miss, replaces 2N DB round-trips (N Cypher edge queries + N SQL vocab
        queries) with 2 queries per chunk of BATCH_CHUNK_SIZE concepts:
          1. One batch Cypher: incoming edges for chunk concepts
          2. One SQL: vocabulary embeddings for all unique relationship types

        The per-concept computation (dot product against polarity axis) then
        runs in pure Python with no further DB access.

        Cache interaction:
            Uses the same _grounding_cache global as the per-concept method.
            For each concept_id: if (concept_id, graph_gen) is in cache, the
            cached value is used (no DB hit). Only cache misses trigger the
            batch queries. Each computed result is written back to the cache,
            so subsequent per-concept calls for any concept in this batch
            will return instantly from cache.

        Connection management:
            Misses are processed in chunks of BATCH_CHUNK_SIZE. Each chunk
            gets its own pool connection, runs 2 queries, and returns it.
            This keeps IN-clause lists small for AGE's query planner and
            releases connections between chunks so concurrent requests
            aren't starved.

        Args:
            concept_ids: Concept IDs to compute grounding for.
            include_types: Optional whitelist of relationship types.
            exclude_types: Optional blacklist of relationship types.

        Returns:
            Dict mapping concept_id -> grounding_strength float.
            Missing or failed concepts default to 0.0.
        """
        global _grounding_cache, _grounding_cache_generation

        if not concept_ids:
            return {}

        result = {cid: 0.0 for cid in concept_ids}

        # --- Phase 1: cache check + polarity axis (one connection) ---
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                graph_gen = self._get_graph_generation(cur)

                misses = []
                with _grounding_cache_lock:
                    if _grounding_cache_generation != graph_gen:
                        if _grounding_cache:
                            logger.info(
                                f"Grounding cache invalidated: generation "
                                f"{_grounding_cache_generation} → {graph_gen} "
                                f"({len(_grounding_cache)} entries evicted)"
                            )
                        _grounding_cache.clear()
                        _grounding_cache_generation = graph_gen

                    for cid in concept_ids:
                        cache_key = (cid, graph_gen)
                        if cache_key in _grounding_cache:
                            result[cid] = _grounding_cache[cache_key]
                        else:
                            misses.append(cid)

                if not misses:
                    logger.debug(
                        f"Grounding batch: all {len(concept_ids)} concepts "
                        f"served from cache"
                    )
                    return result

                polarity_axis = self._get_polarity_axis(cur)
                if polarity_axis is None:
                    with _grounding_cache_lock:
                        for cid in misses:
                            _grounding_cache[(cid, graph_gen)] = 0.0
                    return result
        finally:
            self.pool.putconn(conn)

        # --- Phase 2: process misses in chunks ---
        # Each chunk gets its own connection, keeping IN-clause lists
        # small and releasing connections between chunks.
        total_edges = 0
        for i in range(0, len(misses), BATCH_CHUNK_SIZE):
            chunk = misses[i:i + BATCH_CHUNK_SIZE]
            conn = self.pool.getconn()
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    # Batch Cypher: incoming edges for this chunk
                    ids_str = ','.join([f"'{cid}'" for cid in chunk])
                    batch_edges_sql = f"""
                        SELECT * FROM ag_catalog.cypher(
                            '{self.graph_name}', $$
                            MATCH (c:Concept)<-[r]-(source)
                            WHERE c.concept_id IN [{ids_str}]
                            RETURN c.concept_id as concept_id,
                                   type(r) as rel_type,
                                   r.confidence as confidence
                        $$) AS (concept_id agtype, rel_type agtype,
                                confidence agtype)
                    """
                    cur.execute(batch_edges_sql)
                    chunk_edges = cur.fetchall()
                    total_edges += len(chunk_edges)

                    # Group edges by concept, collect unique rel types
                    edges_by_concept = defaultdict(list)
                    rel_types_needed = set()
                    for row in chunk_edges:
                        cid = str(row['concept_id']).strip('"')
                        rel_type = str(row['rel_type']).strip('"')
                        conf_str = (
                            str(row['confidence'])
                            if row['confidence'] else "1.0"
                        )
                        try:
                            confidence = float(conf_str.strip('"'))
                        except (ValueError, AttributeError):
                            confidence = 1.0
                        edges_by_concept[cid].append({
                            'rel_type': rel_type,
                            'confidence': confidence
                        })
                        rel_types_needed.add(rel_type)

                    # Apply type filters
                    if include_types:
                        rel_types_needed &= set(include_types)
                    if exclude_types:
                        rel_types_needed -= set(exclude_types)

                    # Batch SQL: vocabulary embeddings for this chunk's
                    # rel types
                    vocab_embeddings = {}
                    if rel_types_needed:
                        types_list = ','.join(
                            [f"'{t}'" for t in rel_types_needed]
                        )
                        cur.execute(f"""
                            SELECT relationship_type, embedding
                            FROM kg_api.relationship_vocabulary
                            WHERE relationship_type IN ({types_list})
                              AND embedding IS NOT NULL
                        """)
                        vocab_embeddings = {
                            row['relationship_type']: _parse_embedding(
                                row['embedding']
                            )
                            for row in cur.fetchall()
                        }
                        vocab_embeddings = {
                            k: v for k, v in vocab_embeddings.items()
                            if v is not None
                        }

                    # Per-concept dot products (pure CPU, no DB)
                    for cid in chunk:
                        edges = edges_by_concept.get(cid, [])
                        if not edges:
                            grounding = 0.0
                        else:
                            total_polarity = 0.0
                            total_confidence = 0.0
                            for edge in edges:
                                rel_type = edge['rel_type']
                                if (include_types
                                        and rel_type not in include_types):
                                    continue
                                if (exclude_types
                                        and rel_type in exclude_types):
                                    continue
                                emb = vocab_embeddings.get(rel_type)
                                if emb is None:
                                    continue
                                confidence = edge['confidence']
                                proj = np.dot(emb, polarity_axis)
                                total_polarity += confidence * float(proj)
                                total_confidence += confidence

                            grounding = (
                                float(total_polarity / total_confidence)
                                if total_confidence > 0
                                else 0.0
                            )

                        result[cid] = grounding
                        with _grounding_cache_lock:
                            _grounding_cache[(cid, graph_gen)] = grounding

            except Exception as e:
                logger.error(
                    f"Batch grounding chunk failed: {e}"
                )
                raise
            finally:
                self.pool.putconn(conn)

        logger.debug(
            f"Grounding batch: {len(concept_ids)} concepts, "
            f"{len(concept_ids) - len(misses)} cached, "
            f"{len(misses)} computed in "
            f"{(len(misses) + BATCH_CHUNK_SIZE - 1) // BATCH_CHUNK_SIZE} "
            f"chunks ({total_edges} edges total)"
        )

        return result

    def _get_graph_generation(self, cur) -> int:
        """Read current graph generation for cache invalidation.

        Uses graph_accel.generation table if available (bumped by
        graph_accel_invalidate after mutations), falls back to
        vocabulary_change_counter from graph_metrics.

        Uses SAVEPOINT to safely probe for graph_accel.generation —
        if the extension isn't loaded on this pool connection, the
        query fails without aborting the outer transaction.
        """
        try:
            cur.execute("SAVEPOINT gen_check")
            cur.execute(
                "SELECT current_generation FROM graph_accel.generation "
                "WHERE graph_name = 'knowledge_graph'"
            )
            row = cur.fetchone()
            cur.execute("RELEASE SAVEPOINT gen_check")
            if row:
                return int(row['current_generation'])
        except Exception:
            try:
                cur.execute("ROLLBACK TO SAVEPOINT gen_check")
            except Exception:
                pass
        # Fallback: use vocabulary_change_counter
        return self._get_vocab_generation(cur)

    async def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute a raw PostgreSQL query and return results as list of dicts.

        This method is used by VocabularyScorer and other modules that need
        to query statistics tables directly with SQL (not Cypher).

        Args:
            query: Raw PostgreSQL query string (use %s for parameters)
            params: Optional tuple of parameters for query placeholders

        Returns:
            List of row dictionaries

        Example:
            >>> # Simple query
            >>> results = await client.execute_query(
            ...     "SELECT * FROM kg_api.relationship_vocabulary LIMIT 5"
            ... )
            >>>
            >>> # Parameterized query
            >>> results = await client.execute_query(
            ...     "SELECT * FROM kg_api.relationship_vocabulary WHERE relationship_type = %s",
            ...     ("IMPLIES",)
            ... )
            >>> for row in results:
            ...     print(row['relationship_type'])
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)

                # Check if query returns results (SELECT, RETURNING) or not (INSERT, UPDATE without RETURNING)
                if cur.description is not None:
                    results = cur.fetchall()
                    # Convert RealDictRow to regular dict
                    return [dict(row) for row in results]
                else:
                    # Query doesn't return results (INSERT, UPDATE, DELETE without RETURNING)
                    return []
        finally:
            conn.commit()
            self.pool.putconn(conn)


    # =========================================================================
    # Query Facade (ADR-048)
    # =========================================================================

    @property
    def facade(self):
        """
        Get namespace-safe query facade (ADR-048).

        Lazy-loads GraphQueryFacade on first access.

        Returns:
            GraphQueryFacade instance

        Example:
            # Namespace-safe concept query
            concepts = client.facade.match_concepts(
                where="c.label =~ '(?i).*recursive.*'",
                limit=10
            )

            # Namespace-safe vocabulary query
            vocab_types = client.facade.match_vocab_types(
                where="v.is_active = true"
            )

            # Get audit stats
            stats = client.facade.get_audit_stats()
            logger.info(f"Safety ratio: {stats['safety_ratio']:.1%}")
        """
        if self._facade is None:
            from api.app.lib.query_facade import GraphQueryFacade
            self._facade = GraphQueryFacade(self)

        return self._facade

    @property
    def graph(self):
        """
        Get unified graph facade with graph_accel acceleration (ADR-201).

        Lazy-loads GraphFacade on first access. Provides accelerated
        neighborhood, pathfinding, degree, and subgraph operations with
        automatic Cypher fallback when graph_accel is not available.

        Returns:
            GraphFacade instance
        """
        if self._graph_facade is None:
            from api.app.lib.graph_facade import GraphFacade
            self._graph_facade = GraphFacade(self)

        return self._graph_facade
