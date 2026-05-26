"""
Query mixin for vector search, learned knowledge, and graph facades.

Provides vector similarity search, learned knowledge management
(human/AI-created connections), and the GraphFacade / EpochFacade
properties wired up here so callers reach them via `client.graph` and
`client.epochs`.

Grounding strength calculation + polarity-axis caching moved out to
GroundingMixin (api/app/lib/age_client/grounding.py) under #278 —
that cluster has no dependency on the rest of this file and the rest
of this file has no dependency on it, so the split keeps both modules
under the review threshold without coupling them.

Key operations:
- vector_search(): Cosine similarity search across concept embeddings
- Learned knowledge CRUD: validate, create, list, delete connections
- facade property: Lazy-loaded GraphQueryFacade for namespace-safe queries (ADR-048)
- graph property: Lazy GraphFacade (ADR-201 topology + acceleration)
- epochs property: Lazy EpochFacade (ADR-203 epoch event log)
"""

import json
import logging
from typing import List, Dict, Optional, Any
import numpy as np
from psycopg2 import extras

logger = logging.getLogger(__name__)


class QueryMixin:
    """Vector search, learned knowledge, and graph facade wiring."""

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

    @property
    def epochs(self):
        """
        Get the epoch event log facade (ADR-203).

        Lazy-loads EpochFacade on first access. Provides per-concept
        re-evidence stream queries and paginated event log access. The
        write path (`record_epoch`) lives on IngestionMixin; this property
        is the read-side surface.

        Returns:
            EpochFacade instance
        """
        if self._epoch_facade is None:
            from api.app.lib.epoch_facade import EpochFacade
            self._epoch_facade = EpochFacade(self)

        return self._epoch_facade
