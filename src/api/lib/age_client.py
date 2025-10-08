"""
Apache AGE client for knowledge graph operations.

Handles all database interactions including node creation, relationship management,
and vector similarity search using PostgreSQL + Apache AGE extension.
"""

import os
import json
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extensions import AsIs


class AGEClient:
    """Client for interacting with Apache AGE knowledge graph database."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize AGE client with connection details.

        Args:
            host: PostgreSQL host (defaults to POSTGRES_HOST env var)
            port: PostgreSQL port (defaults to POSTGRES_PORT env var)
            database: Database name (defaults to POSTGRES_DB env var)
            user: Database user (defaults to POSTGRES_USER env var)
            password: Database password (defaults to POSTGRES_PASSWORD env var)

        Raises:
            ValueError: If connection details are missing
            psycopg2.OperationalError: If cannot connect to PostgreSQL
        """
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = database or os.getenv("POSTGRES_DB", "knowledge_graph")
        self.user = user or os.getenv("POSTGRES_USER", "admin")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "password")
        self.graph_name = "knowledge_graph"

        if not all([self.host, self.port, self.database, self.user, self.password]):
            raise ValueError(
                "Missing PostgreSQL connection details. Provide via parameters or "
                "set POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, "
                "POSTGRES_PASSWORD environment variables."
            )

        try:
            # Create connection pool for better performance
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1,  # minconn
                10,  # maxconn
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            # Test connection and setup AGE
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
            finally:
                self.pool.putconn(conn)
        except psycopg2.OperationalError as e:
            raise psycopg2.OperationalError(
                f"Cannot connect to PostgreSQL at {self.host}:{self.port}: {e}"
            )

    def _setup_age(self, conn):
        """Load AGE extension and set search path."""
        with conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, \"$user\", public;")
        conn.commit()

    def _execute_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch_one: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query via AGE.

        Args:
            query: Cypher query string
            params: Query parameters (will be interpolated into query)
            fetch_one: If True, return only first result

        Returns:
            List of dictionaries with query results
        """
        conn = self.pool.getconn()
        try:
            self._setup_age(conn)

            # Replace parameters in query (AGE doesn't support parameterized Cypher)
            if params:
                for key, value in params.items():
                    # Convert Python types to Cypher literals
                    if isinstance(value, str):
                        # Escape single quotes in strings
                        value_str = value.replace("'", "\\'")
                        query = query.replace(f"${key}", f"'{value_str}'")
                    elif isinstance(value, (list, dict)):
                        # Convert lists/dicts to JSON strings
                        value_str = json.dumps(value).replace("'", "\\'")
                        query = query.replace(f"${key}", value_str)
                    elif isinstance(value, (int, float)):
                        query = query.replace(f"${key}", str(value))
                    elif value is None:
                        query = query.replace(f"${key}", "null")
                    else:
                        query = query.replace(f"${key}", str(value))

            # Wrap Cypher in AGE SELECT statement
            age_query = f"""
                SELECT * FROM cypher('{self.graph_name}', $$
                    {query}
                $$) as (result agtype);
            """

            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(age_query)

                if fetch_one:
                    result = cur.fetchone()
                    return [dict(result)] if result else []
                else:
                    results = cur.fetchall()
                    return [dict(row) for row in results]

        finally:
            conn.commit()
            self.pool.putconn(conn)

    def _parse_agtype(self, agtype_value: Any) -> Any:
        """
        Parse AGE's agtype values to Python types.

        AGE returns values as special agtype format that needs parsing.
        """
        if agtype_value is None:
            return None

        # Convert agtype to string and parse as JSON
        value_str = str(agtype_value)

        # AGE returns vertices as: {"id": ..., "label": ..., "properties": {...}}::vertex
        # AGE returns edges as: {"id": ..., "label": ..., "start_id": ..., "end_id": ..., "properties": {...}}::edge
        # Strip the ::vertex or ::edge suffix
        if '::vertex' in value_str or '::edge' in value_str:
            value_str = value_str.split('::')[0]

        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            # If not JSON, return as-is (might be a simple value)
            return agtype_value

    def close(self):
        """Close all database connections."""
        if hasattr(self, 'pool'):
            self.pool.closeall()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def create_source_node(
        self,
        source_id: str,
        document: str,
        paragraph: int,
        full_text: str,
        file_path: str = None
    ) -> Dict[str, Any]:
        """
        Create a Source node in the graph.

        Args:
            source_id: Unique identifier for the source
            document: Document/ontology name for logical grouping
            paragraph: Paragraph/chunk number in the document
            full_text: Full text content of the paragraph
            file_path: Path to the source file (optional)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (s:Source {
            source_id: $source_id,
            document: $document,
            paragraph: $paragraph,
            full_text: $full_text,
            file_path: $file_path
        })
        RETURN s
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "source_id": source_id,
                    "document": document,
                    "paragraph": paragraph,
                    "full_text": full_text,
                    "file_path": file_path if file_path else "null"
                },
                fetch_one=True
            )
            if results:
                agtype_result = results[0].get('result')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Source node {source_id}: {e}")

    def create_concept_node(
        self,
        concept_id: str,
        label: str,
        embedding: List[float],
        search_terms: List[str]
    ) -> Dict[str, Any]:
        """
        Create a Concept node in the graph.

        Args:
            concept_id: Unique identifier for the concept
            label: Human-readable concept label
            embedding: Vector embedding for similarity search
            search_terms: Alternative terms/phrases for the concept

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (c:Concept {
            concept_id: $concept_id,
            label: $label,
            embedding: $embedding,
            search_terms: $search_terms
        })
        RETURN c
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "concept_id": concept_id,
                    "label": label,
                    "embedding": embedding,
                    "search_terms": search_terms
                },
                fetch_one=True
            )
            if results:
                agtype_result = results[0].get('result')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Concept node {concept_id}: {e}")

    def create_instance_node(
        self,
        instance_id: str,
        quote: str
    ) -> Dict[str, Any]:
        """
        Create an Instance node in the graph.

        Args:
            instance_id: Unique identifier for the instance
            quote: Exact quote from the source text

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (i:Instance {
            instance_id: $instance_id,
            quote: $quote
        })
        RETURN i
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "instance_id": instance_id,
                    "quote": quote
                },
                fetch_one=True
            )
            if results:
                agtype_result = results[0].get('result')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Instance node {instance_id}: {e}")

    def link_concept_to_source(
        self,
        concept_id: str,
        source_id: str
    ) -> bool:
        """
        Create APPEARS_IN relationship from Concept to Source.

        Args:
            concept_id: ID of the concept node
            source_id: ID of the source node

        Returns:
            True if relationship created successfully

        Raises:
            Exception: If relationship creation fails
        """
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (s:Source {source_id: $source_id})
        MERGE (c)-[:APPEARS_IN]->(s)
        RETURN c, s
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "concept_id": concept_id,
                    "source_id": source_id
                },
                fetch_one=True
            )
            return len(results) > 0
        except Exception as e:
            raise Exception(
                f"Failed to link Concept {concept_id} to Source {source_id}: {e}"
            )

    def link_instance_to_concept_and_source(
        self,
        instance_id: str,
        concept_id: str,
        source_id: str
    ) -> bool:
        """
        Create EVIDENCED_BY (Concept->Instance) and FROM_SOURCE (Instance->Source) relationships.

        Args:
            instance_id: ID of the instance node
            concept_id: ID of the concept node
            source_id: ID of the source node

        Returns:
            True if relationships created successfully

        Raises:
            Exception: If relationship creation fails
        """
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (i:Instance {instance_id: $instance_id})
        MATCH (s:Source {source_id: $source_id})
        MERGE (c)-[:EVIDENCED_BY]->(i)
        MERGE (i)-[:FROM_SOURCE]->(s)
        RETURN c, i, s
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "instance_id": instance_id,
                    "concept_id": concept_id,
                    "source_id": source_id
                },
                fetch_one=True
            )
            return len(results) > 0
        except Exception as e:
            raise Exception(
                f"Failed to link Instance {instance_id} to Concept {concept_id} "
                f"and Source {source_id}: {e}"
            )

    def create_concept_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        confidence: float
    ) -> bool:
        """
        Create a relationship between two concepts.

        Args:
            from_id: Source concept ID
            to_id: Target concept ID
            rel_type: Relationship type (IMPLIES, CONTRADICTS, SUPPORTS, PART_OF)
            confidence: Confidence score (0.0-1.0)

        Returns:
            True if relationship created successfully

        Raises:
            ValueError: If rel_type is invalid or confidence out of range
            Exception: If relationship creation fails
        """
        valid_types = ["IMPLIES", "CONTRADICTS", "SUPPORTS", "PART_OF", "RELATES_TO"]
        if rel_type not in valid_types:
            raise ValueError(
                f"Invalid relationship type: {rel_type}. Must be one of {valid_types}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        # Note: AGE doesn't support dynamic relationship types in parameterized queries
        # We have to use string interpolation for the relationship type
        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})
        MATCH (c2:Concept {{concept_id: $to_id}})
        MERGE (c1)-[r:{rel_type} {{confidence: $confidence}}]->(c2)
        RETURN c1, r, c2
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "from_id": from_id,
                    "to_id": to_id,
                    "confidence": confidence
                },
                fetch_one=True
            )
            return len(results) > 0
        except Exception as e:
            raise Exception(
                f"Failed to create {rel_type} relationship from {from_id} to {to_id}: {e}"
            )

    def vector_search(
        self,
        embedding: List[float],
        threshold: float = 0.85,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar concepts using vector similarity.

        Note: Without pgvector, this performs a full scan with Python cosine similarity.
        Performance will degrade with large datasets. Consider adding pgvector support.

        Args:
            embedding: Query embedding vector
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results to return

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
                embedding_agtype = record.get('embedding')

                # Extract values from agtype (strip quotes)
                concept_id = str(concept_id_agtype).strip('"')
                label = str(label_agtype).strip('"')

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
                        "similarity": similarity
                    })

            # Sort by similarity and limit
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:limit]

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
            MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {{document: $document}})
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
            MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {{document: $document}})
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

            emb1_agtype = results[0].get("emb1")
            emb2_agtype = results[0].get("emb2")

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
                agtype_result = results[0].get('result')
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
                "source_deleted": int(str(results[0].get("source_deleted", 0))),
                "relationships_deleted": int(str(results[0].get("relationships_deleted", 0)))
            }
        except Exception as e:
            raise Exception(f"Failed to delete learned knowledge: {e}")
