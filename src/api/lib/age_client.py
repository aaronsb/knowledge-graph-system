"""
Apache AGE client for knowledge graph operations.

Handles all database interactions including node creation, relationship management,
and vector similarity search using PostgreSQL + Apache AGE extension.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extensions import AsIs

logger = logging.getLogger(__name__)


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

            # Extract column names from RETURN clause BEFORE parameter substitution
            # (otherwise document content can interfere with regex parsing)
            column_spec = self._extract_column_spec(query)

            # Replace parameters in query (AGE doesn't support parameterized Cypher)
            if params:
                for key, value in params.items():
                    # Convert Python types to Cypher literals
                    if isinstance(value, str):
                        # Escape backslashes FIRST (critical for docs with code examples)
                        value_str = value.replace("\\", "\\\\")
                        # Then escape single quotes
                        value_str = value_str.replace("'", "\\'")
                        query = query.replace(f"${key}", f"'{value_str}'")
                    elif isinstance(value, (list, dict)):
                        # Convert lists/dicts to JSON strings
                        value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
                        query = query.replace(f"${key}", value_str)
                    elif isinstance(value, (int, float)):
                        query = query.replace(f"${key}", str(value))
                    elif value is None:
                        query = query.replace(f"${key}", "null")
                    else:
                        query = query.replace(f"${key}", str(value))

            # Wrap Cypher in AGE SELECT statement with dynamic column specification
            age_query = f"""
                SELECT * FROM cypher('{self.graph_name}', $$
                    {query}
                $$) as ({column_spec});
            """

            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                try:
                    cur.execute(age_query)
                except Exception as e:
                    # Log detailed error information
                    logger.error("=" * 80)
                    logger.error("Query execution failed")
                    logger.error(f"Error: {e}")
                    logger.error(f"Column spec: {column_spec}")
                    logger.error(f"Original query length: {len(query)} chars")
                    logger.error(f"First 500 chars: {query[:500]}")
                    logger.error(f"Last 500 chars: {query[-500:]}")
                    if params:
                        logger.error(f"Parameters:")
                        for k, v in params.items():
                            val_preview = str(v)[:200] if isinstance(v, str) else str(v)
                            logger.error(f"  {k}: {val_preview}")
                    logger.error("=" * 80)
                    raise

                if fetch_one:
                    result = cur.fetchone()
                    if result:
                        # Parse all agtype values in the result dict
                        return {k: self._parse_agtype(v) for k, v in result.items()}
                    return None
                else:
                    results = cur.fetchall()
                    # Parse all agtype values in each result dict
                    return [
                        {k: self._parse_agtype(v) for k, v in row.items()}
                        for row in results
                    ]

        finally:
            conn.commit()
            self.pool.putconn(conn)

    def _extract_column_spec(self, query: str) -> str:
        """
        Extract column names from Cypher RETURN clause to build AGE column specification.

        Parses patterns like:
        - RETURN count(n) as node_count -> "node_count agtype"
        - RETURN n.id, n.label -> "id agtype, label agtype"
        - RETURN n -> "n agtype"

        Args:
            query: Cypher query string

        Returns:
            Column specification string for AGE query (e.g., "col1 agtype, col2 agtype")
        """
        import re

        # Find the RETURN clause (case-insensitive)
        # Match everything after RETURN until ORDER BY, LIMIT, or end of string
        return_match = re.search(r'\bRETURN\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', query, re.IGNORECASE | re.DOTALL)

        if not return_match:
            # No RETURN clause found, default to single result column
            return "result agtype"

        return_clause = return_match.group(1).strip()

        # Extract column names/aliases
        # Pattern: matches "expr as alias" or just "expr"
        columns = []
        for part in return_clause.split(','):
            part = part.strip()

            # Check for "as alias" pattern
            as_match = re.search(r'\s+as\s+(\w+)', part, re.IGNORECASE)
            if as_match:
                # Use the alias
                columns.append(as_match.group(1))
            else:
                # Extract last identifier (e.g., "n.label" -> "label", "count(n)" -> "count")
                # This is a simplified heuristic
                # For complex expressions, use a generic name
                tokens = re.findall(r'\w+', part)
                if tokens:
                    # Use the last token as column name
                    col_name = tokens[-1]
                    columns.append(col_name)
                else:
                    columns.append(f"col{len(columns)}")

        # Build column specification
        if not columns:
            return "result agtype"

        # De-duplicate column names by adding suffix if needed
        seen = {}
        unique_columns = []
        for col in columns:
            if col in seen:
                seen[col] += 1
                unique_columns.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_columns.append(col)

        return ", ".join(f"{col} agtype" for col in unique_columns)

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
        # AGE returns lists with type annotations: [{...}::vertex, {...}::vertex]
        # Strip ALL ::vertex and ::edge suffixes (not just the first one)
        if '::vertex' in value_str or '::edge' in value_str:
            import re
            # Remove all ::vertex and ::edge type annotations
            value_str = re.sub(r'::(vertex|edge|path)', '', value_str)

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
                agtype_result = results.get('s')  # 's' from RETURN s
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
                agtype_result = results.get('c')  # 'c' from RETURN c
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
                agtype_result = results.get('i')  # 'i' from RETURN i
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
        category: str,
        confidence: float
    ) -> bool:
        """
        Create a relationship between two concepts with category metadata.

        Args:
            from_id: Source concept ID
            to_id: Target concept ID
            rel_type: Canonical relationship type (normalized via Porter Stemmer matcher)
            category: Relationship category (logical_truth, causal, structural, etc.)
            confidence: Confidence score (0.0-1.0)

        Returns:
            True if relationship created successfully

        Raises:
            ValueError: If confidence out of range
            Exception: If relationship creation fails

        Note:
            Relationship type validation happens in ingestion layer via normalize_relationship_type().
            This method trusts that rel_type has been normalized to one of the 30 canonical types.
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        # Note: AGE doesn't support dynamic relationship types in parameterized queries
        # We have to use string interpolation for the relationship type
        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})
        MATCH (c2:Concept {{concept_id: $to_id}})
        MERGE (c1)-[r:{rel_type} {{
            confidence: $confidence,
            category: $category
        }}]->(c2)
        RETURN c1, r, c2
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "from_id": from_id,
                    "to_id": to_id,
                    "confidence": confidence,
                    "category": category
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

    def rename_ontology(
        self,
        old_name: str,
        new_name: str
    ) -> Dict[str, int]:
        """
        Rename an ontology by updating all Source nodes' document property.

        Ontologies are logical groupings defined by the 'document' property on Source nodes.
        This method updates all Source nodes from old_name to new_name.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            Dictionary with count: {"sources_updated": N}

        Raises:
            ValueError: If old ontology doesn't exist or new ontology already exists
            Exception: If rename operation fails
        """
        # Check if old ontology exists
        check_old = """
        MATCH (s:Source {document: $old_name})
        RETURN count(s) as source_count
        """

        try:
            old_result = self._execute_cypher(
                check_old,
                params={"old_name": old_name},
                fetch_one=True
            )
            old_count = int(str(old_result.get("source_count", 0)))

            if old_count == 0:
                raise ValueError(f"Ontology '{old_name}' does not exist")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check old ontology existence: {e}")

        # Check if new ontology already exists
        check_new = """
        MATCH (s:Source {document: $new_name})
        RETURN count(s) as source_count
        """

        try:
            new_result = self._execute_cypher(
                check_new,
                params={"new_name": new_name},
                fetch_one=True
            )
            new_count = int(str(new_result.get("source_count", 0)))

            if new_count > 0:
                raise ValueError(f"Ontology '{new_name}' already exists")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to check new ontology existence: {e}")

        # Rename ontology by updating all Source nodes
        rename_query = """
        MATCH (s:Source {document: $old_name})
        SET s.document = $new_name
        RETURN count(s) as updated_count
        """

        try:
            result = self._execute_cypher(
                rename_query,
                params={
                    "old_name": old_name,
                    "new_name": new_name
                },
                fetch_one=True
            )

            updated_count = int(str(result.get("updated_count", 0)))

            return {"sources_updated": updated_count}
        except Exception as e:
            raise Exception(f"Failed to rename ontology: {e}")

    # =========================================================================
    # Vocabulary Management Methods (ADR-032)
    # =========================================================================

    def get_vocabulary_size(self) -> int:
        """
        Get count of active relationship types in vocabulary.

        Returns:
            Count of active (non-deprecated) relationship types

        Example:
            >>> client = AGEClient()
            >>> size = client.get_vocabulary_size()
            >>> print(f"Vocabulary size: {size}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM kg_api.relationship_vocabulary 
                    WHERE is_active = TRUE
                """)
                result = cur.fetchone()
                return result[0] if result else 0
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_all_edge_types(self, include_inactive: bool = False) -> List[str]:
        """
        Get list of all relationship types in vocabulary.

        Args:
            include_inactive: Include deprecated types (default: False)

        Returns:
            List of relationship type names

        Example:
            >>> client = AGEClient()
            >>> types = client.get_all_edge_types()
            >>> print(f"Active types: {len(types)}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                if include_inactive:
                    cur.execute("""
                        SELECT relationship_type 
                        FROM kg_api.relationship_vocabulary 
                        ORDER BY relationship_type
                    """)
                else:
                    cur.execute("""
                        SELECT relationship_type 
                        FROM kg_api.relationship_vocabulary 
                        WHERE is_active = TRUE
                        ORDER BY relationship_type
                    """)
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_edge_type_info(self, relationship_type: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a relationship type.

        Args:
            relationship_type: Relationship type name

        Returns:
            Dict with type details, or None if not found

        Example:
            >>> info = client.get_edge_type_info("IMPLIES")
            >>> print(f"Category: {info['category']}, Builtin: {info['is_builtin']}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT relationship_type, description, category, added_by,
                           added_at, usage_count, is_active, is_builtin,
                           synonyms, deprecation_reason, embedding_model,
                           embedding_generated_at
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type = %s
                """, (relationship_type,))
                result = cur.fetchone()

                if not result:
                    return None

                # Convert to dict
                info = dict(result)

                # Query graph for actual edge count
                try:
                    count_query = f"""
                    MATCH ()-[r:{relationship_type}]->()
                    RETURN count(r) as edge_count
                    """
                    edge_result = self._execute_cypher(count_query, fetch_one=True)
                    if edge_result:
                        info['edge_count'] = int(str(edge_result.get('edge_count', 0)))
                    else:
                        info['edge_count'] = 0
                except Exception as e:
                    logger.warning(f"Failed to count edges for {relationship_type}: {e}")
                    info['edge_count'] = 0

                return info
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def add_edge_type(
        self,
        relationship_type: str,
        category: str,
        description: Optional[str] = None,
        added_by: str = "system",
        is_builtin: bool = False,
        ai_provider = None
    ) -> bool:
        """
        Add a new relationship type to vocabulary with automatic embedding generation.

        Args:
            relationship_type: Relationship type name (e.g., "AUTHORED_BY")
            category: Semantic category
            description: Optional description
            added_by: Who added the type (username or "system")
            is_builtin: Whether this is a protected builtin type
            ai_provider: Optional AI provider for embedding generation (auto-generation if provided)

        Returns:
            True if added successfully, False if already exists

        Example:
            >>> success = client.add_edge_type("AUTHORED_BY", "authorship",
            ...                                 "Indicates authorship", "admin",
            ...                                 ai_provider=provider)
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO kg_api.relationship_vocabulary
                        (relationship_type, description, category, added_by, is_builtin, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (relationship_type) DO NOTHING
                    RETURNING relationship_type
                """, (relationship_type, description, category, added_by, is_builtin))
                result = cur.fetchone()
                was_added = result is not None

                # Generate and store embedding if AI provider available and type was just added
                if was_added and ai_provider is not None:
                    try:
                        # Convert edge type to descriptive text (same logic as SynonymDetector)
                        descriptive_text = f"relationship: {relationship_type.lower().replace('_', ' ')}"

                        # Generate embedding
                        embedding_response = ai_provider.generate_embedding(descriptive_text)
                        embedding = embedding_response["embedding"]
                        model = embedding_response.get("model", "text-embedding-ada-002")

                        # Store embedding
                        embedding_json = json.dumps(embedding)
                        cur.execute("""
                            UPDATE kg_api.relationship_vocabulary
                            SET embedding = %s::jsonb,
                                embedding_model = %s,
                                embedding_generated_at = NOW()
                            WHERE relationship_type = %s
                        """, (embedding_json, model, relationship_type))

                        logger.debug(f"Generated embedding for vocabulary type '{relationship_type}' ({len(embedding)} dims)")
                    except Exception as e:
                        # Don't fail the entire operation if embedding generation fails
                        logger.warning(f"Failed to generate embedding for '{relationship_type}': {e}")

                return was_added
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def update_edge_type(
        self,
        relationship_type: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        deprecation_reason: Optional[str] = None
    ) -> bool:
        """
        Update relationship type properties.

        Args:
            relationship_type: Type to update
            description: New description (optional)
            category: New category (optional)
            is_active: Active status (optional)
            deprecation_reason: Reason for deprecation (optional)

        Returns:
            True if updated successfully

        Example:
            >>> client.update_edge_type("OLD_TYPE", is_active=False, 
            ...                          deprecation_reason="Merged into NEW_TYPE")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Build dynamic UPDATE
                updates = []
                params = []
                
                if description is not None:
                    updates.append("description = %s")
                    params.append(description)
                
                if category is not None:
                    updates.append("category = %s")
                    params.append(category)
                
                if is_active is not None:
                    updates.append("is_active = %s")
                    params.append(is_active)
                
                if deprecation_reason is not None:
                    updates.append("deprecation_reason = %s")
                    params.append(deprecation_reason)
                
                if not updates:
                    return False
                
                params.append(relationship_type)
                
                cur.execute(f"""
                    UPDATE kg_api.relationship_vocabulary
                    SET {', '.join(updates)}
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, params)
                result = cur.fetchone()
                return result is not None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def merge_edge_types(
        self,
        deprecated_type: str,
        target_type: str,
        performed_by: str = "system"
    ) -> Dict[str, int]:
        """
        Merge one relationship type into another.

        This updates all edges using deprecated_type to use target_type instead,
        marks deprecated_type as inactive, and records the change in history.

        Args:
            deprecated_type: Type to deprecate and merge
            target_type: Type to preserve
            performed_by: Who performed the merge

        Returns:
            Dict with counts: {"edges_updated": N, "vocab_updated": 1}

        Example:
            >>> result = client.merge_edge_types("VERIFIES", "VALIDATES", "admin")
            >>> print(f"Updated {result['edges_updated']} edges")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # First, update all edges in the graph from deprecated_type to target_type
                # Note: AGE doesn't support dynamic relationship types in parameterized queries
                # We must use string interpolation for relationship types
                try:
                    # Delete existing edges of deprecated type and recreate with target type
                    # This is a two-step process since AGE doesn't support SET on relationship labels
                    merge_query = f"""
                    MATCH (c1)-[r:{deprecated_type}]->(c2)
                    CREATE (c1)-[new_r:{target_type}]->(c2)
                    SET new_r = properties(r)
                    DELETE r
                    RETURN count(new_r) as edges_updated
                    """

                    result = self._execute_cypher(merge_query, fetch_one=True)
                    edges_updated = int(str(result.get('edges_updated', 0))) if result else 0

                    logger.info(f"Merged {edges_updated} edges from {deprecated_type} to {target_type}")
                except Exception as e:
                    logger.error(f"Failed to update graph edges during merge: {e}")
                    # Continue with vocabulary update even if graph update fails
                    edges_updated = 0

                # Mark deprecated type as inactive in vocabulary
                cur.execute("""
                    UPDATE kg_api.relationship_vocabulary
                    SET is_active = FALSE,
                        deprecation_reason = %s
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, (f"Merged into {target_type}", deprecated_type))

                vocab_updated = 1 if cur.fetchone() else 0

                # Record in history
                cur.execute("""
                    INSERT INTO kg_api.vocabulary_history
                        (relationship_type, action, performed_by, target_type, reason)
                    VALUES (%s, 'merged', %s, %s, %s)
                """, (deprecated_type, performed_by, target_type, f"Merged into {target_type}"))

                return {
                    "edges_updated": edges_updated,
                    "vocab_updated": vocab_updated
                }
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_category_distribution(self) -> Dict[str, int]:
        """
        Get count of types per category.

        Returns:
            Dict mapping category name -> count

        Example:
            >>> distribution = client.get_category_distribution()
            >>> for category, count in distribution.items():
            ...     print(f"{category}: {count}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT category, COUNT(*) as count
                    FROM kg_api.relationship_vocabulary
                    WHERE is_active = TRUE
                    GROUP BY category
                    ORDER BY count DESC, category
                """)
                return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def store_embedding(
        self,
        relationship_type: str,
        embedding: List[float],
        model: str = "text-embedding-ada-002"
    ) -> bool:
        """
        Store embedding vector for relationship type.

        Args:
            relationship_type: Type to store embedding for
            embedding: Embedding vector
            model: Model used to generate embedding

        Returns:
            True if stored successfully

        Example:
            >>> embedding = [0.123, 0.456, ...]  # 1536 dimensions
            >>> client.store_embedding("VALIDATES", embedding)
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Store as JSONB array
                import json
                embedding_json = json.dumps(embedding)
                
                cur.execute("""
                    UPDATE kg_api.relationship_vocabulary
                    SET embedding = %s::jsonb,
                        embedding_model = %s,
                        embedding_generated_at = NOW()
                    WHERE relationship_type = %s
                    RETURNING relationship_type
                """, (embedding_json, model, relationship_type))
                result = cur.fetchone()
                return result is not None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_embedding(self, relationship_type: str) -> Optional[List[float]]:
        """
        Get stored embedding for relationship type.

        Args:
            relationship_type: Type to get embedding for

        Returns:
            Embedding vector as list of floats, or None if not found

        Example:
            >>> embedding = client.get_embedding("VALIDATES")
            >>> if embedding:
            ...     print(f"Embedding dimension: {len(embedding)}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type = %s
                """, (relationship_type,))
                result = cur.fetchone()
                if result and result[0]:
                    import json
                    return json.loads(result[0])
                return None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def get_vocabulary_embedding(self, relationship_type: str) -> Optional[Dict[str, Any]]:
        """
        Get embedding with metadata for vocabulary type from database.

        Args:
            relationship_type: The edge type to get embedding for

        Returns:
            Dict with 'embedding' (list of floats) and 'embedding_model' (str),
            or None if not found or no embedding

        Example:
            >>> client = AGEClient()
            >>> data = client.get_vocabulary_embedding("VALIDATES")
            >>> if data:
            ...     print(f"Embedding dimensions: {len(data['embedding'])}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding, embedding_model
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type = %s
                      AND embedding IS NOT NULL
                """, (relationship_type,))
                result = cur.fetchone()

                if result and result[0]:
                    return {
                        'embedding': result[0],  # Already a Python list from JSONB
                        'embedding_model': result[1]
                    }
                return None
        finally:
            conn.commit()
            self.pool.putconn(conn)

    def update_vocabulary_embedding(
        self,
        relationship_type: str,
        embedding: List[float],
        embedding_model: str
    ) -> bool:
        """
        Update embedding for a vocabulary type in database.

        Wrapper around store_embedding() for consistency with get_vocabulary_embedding().

        Args:
            relationship_type: The edge type to update
            embedding: Embedding vector as list of floats
            embedding_model: Name of the model used (e.g., "text-embedding-ada-002")

        Returns:
            True if updated, False if type not found

        Example:
            >>> client = AGEClient()
            >>> success = client.update_vocabulary_embedding(
            ...     "VALIDATES",
            ...     embedding_vector,
            ...     "text-embedding-ada-002"
            ... )
        """
        return self.store_embedding(relationship_type, embedding, embedding_model)

    def generate_vocabulary_embeddings(
        self,
        ai_provider,
        force_regenerate: bool = False,
        only_missing: bool = True
    ) -> Dict[str, int]:
        """
        Bulk generate/regenerate embeddings for vocabulary types.

        Useful for:
        - Fixing missing embeddings after database issues
        - Regenerating embeddings after model changes
        - Updating embeddings after vocabulary merges

        Args:
            ai_provider: AI provider instance for embedding generation
            force_regenerate: Regenerate all embeddings (default: False)
            only_missing: Only generate for types without embeddings (default: True, ignored if force_regenerate=True)

        Returns:
            Dict with counts: {"generated": N, "skipped": M, "failed": K}

        Example:
            >>> from src.api.lib.ai_providers import get_provider
            >>> provider = get_provider()
            >>> result = client.generate_vocabulary_embeddings(provider, only_missing=True)
            >>> print(f"Generated {result['generated']} embeddings")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Get vocabulary types to process
                if force_regenerate:
                    # Regenerate ALL embeddings
                    cur.execute("""
                        SELECT relationship_type
                        FROM kg_api.relationship_vocabulary
                        WHERE is_active = TRUE
                        ORDER BY relationship_type
                    """)
                    logger.info("Generating embeddings for ALL vocabulary types (force_regenerate=True)")
                elif only_missing:
                    # Only types without embeddings
                    cur.execute("""
                        SELECT relationship_type
                        FROM kg_api.relationship_vocabulary
                        WHERE is_active = TRUE AND embedding IS NULL
                        ORDER BY relationship_type
                    """)
                    logger.info("Generating embeddings for vocabulary types WITHOUT embeddings")
                else:
                    # All active types (might skip some if they already have embeddings)
                    cur.execute("""
                        SELECT relationship_type
                        FROM kg_api.relationship_vocabulary
                        WHERE is_active = TRUE
                        ORDER BY relationship_type
                    """)
                    logger.info("Generating embeddings for active vocabulary types")

                types_to_process = [row['relationship_type'] for row in cur.fetchall()]
                total = len(types_to_process)

                if total == 0:
                    logger.info("No vocabulary types to process")
                    return {"generated": 0, "skipped": 0, "failed": 0}

                logger.info(f"Processing {total} vocabulary types...")

                generated = 0
                skipped = 0
                failed = 0

                for idx, rel_type in enumerate(types_to_process, 1):
                    try:
                        # Convert edge type to descriptive text (same logic as add_edge_type and SynonymDetector)
                        descriptive_text = f"relationship: {rel_type.lower().replace('_', ' ')}"

                        # Generate embedding
                        embedding_response = ai_provider.generate_embedding(descriptive_text)
                        embedding = embedding_response["embedding"]
                        model = embedding_response.get("model", "text-embedding-ada-002")

                        # Store embedding
                        embedding_json = json.dumps(embedding)
                        cur.execute("""
                            UPDATE kg_api.relationship_vocabulary
                            SET embedding = %s::jsonb,
                                embedding_model = %s,
                                embedding_generated_at = NOW()
                            WHERE relationship_type = %s
                        """, (embedding_json, model, rel_type))

                        generated += 1

                        # Log progress every 10 types
                        if idx % 10 == 0:
                            logger.info(f"  Progress: {idx}/{total} ({(idx/total)*100:.0f}%)")

                    except Exception as e:
                        failed += 1
                        logger.error(f"Failed to generate embedding for '{rel_type}': {e}")

                # Commit all changes
                conn.commit()

                logger.info(f"Bulk embedding generation complete: {generated} generated, {skipped} skipped, {failed} failed")
                return {
                    "generated": generated,
                    "skipped": skipped,
                    "failed": failed
                }

        except Exception as e:
            conn.rollback()
            raise Exception(f"Bulk embedding generation failed: {e}")
        finally:
            self.pool.putconn(conn)

    def calculate_grounding_strength_semantic(
        self,
        concept_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> float:
        """
        Calculate grounding strength using embedding-based edge semantics (ADR-044).

        Uses semantic similarity to prototypical edge types (SUPPORTS, CONTRADICTS)
        instead of hard-coded polarity. This scales to dynamic vocabulary without
        manual classification.

        Algorithm:
        1. Get embeddings for SUPPORTS and CONTRADICTS prototypes
        2. For each incoming edge to concept:
           - Get edge type embedding
           - Calculate similarity to both prototypes
           - Classify as supporting (higher SUPPORTS similarity) or contradicting
           - Weight by edge confidence and semantic similarity
        3. Calculate grounding_strength = (support - contradict) / (support + contradict)

        Args:
            concept_id: Target concept to calculate grounding for
            include_types: Optional list of relationship types to include
            exclude_types: Optional list of relationship types to exclude

        Returns:
            Grounding strength float in range [-1.0, 1.0]:
            - 1.0 = Maximally grounded (strong support, no contradiction)
            - 0.0 = Neutral (balanced support/contradiction or no edges)
            - -1.0 = Maximally ungrounded (strong contradiction, no support)

        Example:
            >>> client = AGEClient()
            >>> grounding = client.calculate_grounding_strength_semantic("concept-123")
            >>> print(f"Grounding: {grounding:.2f}")
            Grounding: 0.75  # Strongly grounded

        References:
            - ADR-044: Probabilistic Truth Convergence
            - ADR-045: Unified Embedding Generation
        """
        import numpy as np

        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Step 1: Get prototype embeddings for SUPPORTS and CONTRADICTS
                cur.execute("""
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type IN ('SUPPORTS', 'CONTRADICTS')
                      AND embedding IS NOT NULL
                """)
                prototypes = cur.fetchall()

                if len(prototypes) < 2:
                    logger.warning(f"Missing prototype embeddings (need SUPPORTS and CONTRADICTS)")
                    return 0.0

                # Parse prototype embeddings
                supports_emb = None
                contradicts_emb = None

                for proto in prototypes:
                    emb_json = proto['embedding']
                    if isinstance(emb_json, str):
                        emb_array = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        emb_array = np.array(emb_json, dtype=float)
                    elif isinstance(emb_json, dict):
                        # JSONB might be returned as dict
                        emb_array = np.array(list(emb_json.values()), dtype=float)
                    else:
                        try:
                            emb_array = np.array(list(emb_json), dtype=float)
                        except:
                            logger.warning(f"Could not parse prototype embedding for {proto['relationship_type']}")
                            continue

                    if proto['relationship_type'] == 'SUPPORTS':
                        supports_emb = emb_array
                    elif proto['relationship_type'] == 'CONTRADICTS':
                        contradicts_emb = emb_array

                if supports_emb is None or contradicts_emb is None:
                    logger.warning("Failed to parse prototype embeddings")
                    return 0.0

                # Step 2: Get all incoming relationships to this concept
                # Use _execute_cypher() to avoid agtype parsing issues
                cypher_edges_query = f"""
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})<-[r]-(source)
                    RETURN type(r) as rel_type, r.confidence as confidence
                """

                edge_results = self._execute_cypher(cypher_edges_query)

                if not edge_results:
                    # No incoming edges = neutral grounding
                    return 0.0

                # Step 2b: Get embeddings for these edge types from vocabulary
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

                # Step 3: Calculate weighted support and contradiction scores
                support_weight = 0.0
                contradict_weight = 0.0

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

                    # Calculate semantic similarity to prototypes (cosine similarity)
                    support_sim = np.dot(edge_emb, supports_emb) / (
                        np.linalg.norm(edge_emb) * np.linalg.norm(supports_emb)
                    )
                    contradict_sim = np.dot(edge_emb, contradicts_emb) / (
                        np.linalg.norm(edge_emb) * np.linalg.norm(contradicts_emb)
                    )

                    # Classify edge as supporting or contradicting based on higher similarity
                    if support_sim > contradict_sim:
                        # Edge is more semantically similar to SUPPORTS
                        support_weight += confidence * float(support_sim)
                    else:
                        # Edge is more semantically similar to CONTRADICTS
                        contradict_weight += confidence * float(contradict_sim)

                # Step 4: Calculate final grounding strength
                total_weight = support_weight + contradict_weight

                if total_weight == 0:
                    return 0.0

                # Normalize to [-1.0, 1.0] range
                grounding_strength = (support_weight - contradict_weight) / total_weight

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
