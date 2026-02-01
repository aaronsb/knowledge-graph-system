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
"""

import json
import logging
from typing import List, Dict, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)


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

        Algorithm (Polarity Axis Triangulation):
        1. Define multiple opposing pairs (SUPPORTS/CONTRADICTS, VALIDATES/REFUTES, etc.)
        2. Fetch embeddings for all pairs that exist in vocabulary
        3. Calculate difference vectors: positive_emb - negative_emb for each pair
        4. Average difference vectors to get robust polarity axis
        5. Normalize axis to unit vector
        6. For each incoming edge:
           - Project edge embedding onto polarity axis via dot product
           - Weight projection by edge confidence
        7. Calculate grounding = sum(weighted_projections) / sum(confidences)

        This approach provides nuanced grounding scores even for single edge types,
        based on how semantically aligned they are with support vs contradict axes.

        Args:
            concept_id: Target concept to calculate grounding for
            include_types: Optional list of relationship types to include
            exclude_types: Optional list of relationship types to exclude

        Returns:
            Grounding strength float in range approximately [-1.0, 1.0]:
            - Positive = Edge types align with support-like semantics
            - Zero = Edge types are neutral or balanced
            - Negative = Edge types align with contradict-like semantics

        Example:
            >>> client = AGEClient()
            >>> grounding = client.calculate_grounding_strength_semantic("concept-123")
            >>> print(f"Grounding: {grounding:.3f}")
            Grounding: 0.347  # Moderately grounded (nuanced value)

        References:
            - ADR-044: Probabilistic Truth Convergence
            - ADR-045: Unified Embedding Generation
        """
        import numpy as np

        # Define opposing pairs for polarity axis triangulation
        # Format: (positive_pole, negative_pole)
        # These pairs help triangulate the semantic direction of "support" vs "contradict"
        POLARITY_PAIRS = [
            ("SUPPORTS", "CONTRADICTS"),      # Core evidential pair
            ("VALIDATES", "REFUTES"),         # Verification semantics
            ("CONFIRMS", "DISPROVES"),        # Proof semantics
            ("REINFORCES", "OPPOSES"),        # Strength semantics
            ("ENABLES", "PREVENTS"),          # Causation semantics
        ]

        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Step 1: Fetch embeddings for all polarity pair terms that exist
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
                    emb_json = row['embedding']
                    # Parse embedding (handle various formats)
                    if isinstance(emb_json, str):
                        emb_array = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        emb_array = np.array(emb_json, dtype=float)
                    elif isinstance(emb_json, dict):
                        emb_array = np.array(list(emb_json.values()), dtype=float)
                    else:
                        try:
                            emb_array = np.array(list(emb_json), dtype=float)
                        except:
                            logger.warning(f"Could not parse embedding for {row['relationship_type']}")
                            continue

                    pair_embeddings[row['relationship_type']] = emb_array

                # Step 2: Calculate difference vectors for each pair
                difference_vectors = []
                for positive, negative in POLARITY_PAIRS:
                    if positive in pair_embeddings and negative in pair_embeddings:
                        diff_vec = pair_embeddings[positive] - pair_embeddings[negative]
                        difference_vectors.append(diff_vec)
                        logger.debug(f"Polarity pair: {positive} - {negative} (magnitude: {np.linalg.norm(diff_vec):.3f})")

                if len(difference_vectors) == 0:
                    logger.warning("No polarity pairs available for axis calculation (need embeddings)")
                    return 0.0

                # Step 3: Average difference vectors to get robust polarity axis
                polarity_axis = np.mean(difference_vectors, axis=0)

                # Step 4: Normalize to unit vector
                axis_magnitude = np.linalg.norm(polarity_axis)
                if axis_magnitude == 0:
                    logger.warning("Polarity axis has zero magnitude")
                    return 0.0

                polarity_axis = polarity_axis / axis_magnitude
                logger.debug(f"Polarity axis triangulated from {len(difference_vectors)} pairs")

                # Step 5: Get all incoming relationships to this concept
                # Use _execute_cypher() to avoid agtype parsing issues
                cypher_edges_query = f"""
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})<-[r]-(source)
                    RETURN type(r) as rel_type, r.confidence as confidence
                """

                edge_results = self._execute_cypher(cypher_edges_query)

                if not edge_results:
                    # No incoming edges = neutral grounding
                    return 0.0

                # Step 6: Get embeddings for these edge types from vocabulary
                # Build list of unique relationship types
                rel_types = set(edge['rel_type'] for edge in edge_results)

                # Apply type filters
                if include_types:
                    rel_types = rel_types & set(include_types)
                if exclude_types:
                    rel_types = rel_types - set(exclude_types)

                if not rel_types:
                    return 0.0

                # Query vocabulary for embeddings
                types_list = ','.join([f"'{t}'" for t in rel_types])
                vocab_query = f"""
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type IN ({types_list})
                      AND embedding IS NOT NULL
                """

                cur.execute(vocab_query)
                vocab_embeddings = {row['relationship_type']: row['embedding']
                                   for row in cur.fetchall()}

                # Join edge results with embeddings in Python
                edges = []
                for edge in edge_results:
                    rel_type = edge['rel_type']
                    if rel_type in vocab_embeddings:
                        # Default confidence to 1.0 if None
                        confidence = edge.get('confidence') or 1.0
                        edges.append({
                            'relationship_type': rel_type,
                            'confidence': float(confidence),
                            'embedding': vocab_embeddings[rel_type]
                        })

                if not edges:
                    # No incoming edges = neutral grounding
                    return 0.0

                # Step 7: Project each edge onto polarity axis and accumulate
                total_polarity = 0.0
                total_confidence = 0.0

                for edge in edges:
                    # Parse edge embedding from JSONB
                    emb_json = edge['embedding']
                    if isinstance(emb_json, str):
                        edge_emb = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        edge_emb = np.array(emb_json, dtype=float)
                    elif isinstance(emb_json, dict):
                        # JSONB might be returned as dict, not list
                        edge_emb = np.array(list(emb_json.values()), dtype=float)
                    else:
                        # Try to convert to list
                        try:
                            edge_emb = np.array(list(emb_json), dtype=float)
                        except:
                            logger.warning(f"Could not parse embedding for {edge.get('relationship_type')}")
                            continue

                    # Get confidence (default to 1.0 if not set)
                    confidence_str = edge.get('confidence')
                    if confidence_str:
                        # Parse agtype confidence
                        if isinstance(confidence_str, dict):
                            confidence = float(confidence_str.get('confidence', 1.0))
                        else:
                            confidence = float(confidence_str)
                    else:
                        confidence = 1.0

                    # Project edge embedding onto polarity axis using dot product
                    # Positive projection = support-like, negative = contradict-like
                    polarity_projection = np.dot(edge_emb, polarity_axis)

                    # Accumulate weighted projections
                    total_polarity += confidence * float(polarity_projection)
                    total_confidence += confidence

                    logger.debug(f"  Edge {edge.get('relationship_type')}: projection={polarity_projection:.3f}, confidence={confidence:.2f}")

                # Step 8: Calculate final grounding strength
                if total_confidence == 0:
                    return 0.0

                # Average weighted projection
                grounding_strength = total_polarity / total_confidence

                logger.debug(f"Grounding for {concept_id}: {grounding_strength:.3f} (from {len(edges)} edges)")

                return float(grounding_strength)

        except Exception as e:
            logger.error(f"Error calculating grounding strength for {concept_id}: {e}")
            return 0.0
        finally:
            self.pool.putconn(conn)

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
