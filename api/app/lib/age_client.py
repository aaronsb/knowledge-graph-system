"""
Apache AGE client for knowledge graph operations.

Handles all database interactions including node creation, relationship management,
and vector similarity search using PostgreSQL + Apache AGE extension.
"""

import os
import json
import logging
from datetime import datetime, timezone
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
            # ThreadedConnectionPool for thread-safe access (parallel requests, ADR-071)
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                1,  # minconn
                20,  # maxconn (supports up to 16 parallel workers + buffer)
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

        # Lazy-loaded facade for namespace-safe queries (ADR-048)
        self._facade = None

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
                    elif isinstance(value, list):
                        # Lists: JSON array syntax is Cypher-compatible
                        value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
                        query = query.replace(f"${key}", value_str)
                    elif isinstance(value, dict):
                        # Dicts: Store as JSON string (Cypher maps require unquoted keys,
                        # but JSON uses quoted keys - see GitHub issue for future improvement)
                        value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
                        query = query.replace(f"${key}", f"'{value_str}'")
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
                    error_str = str(e)

                    # Check if this is an expected race condition (parallel restore operations)
                    is_expected_race = (
                        "already exists" in error_str or
                        "Entity failed to be updated" in error_str
                    )

                    # Log at appropriate level (DEBUG for expected races, ERROR for real problems)
                    log_level = logger.debug if is_expected_race else logger.error

                    log_level("=" * 80)
                    log_level("Query execution failed" if not is_expected_race else "Expected concurrency conflict (will retry)")
                    log_level(f"Error: {e}")
                    log_level(f"Column spec: {column_spec}")
                    log_level(f"Original query length: {len(query)} chars")
                    log_level(f"First 500 chars: {query[:500]}")
                    log_level(f"Last 500 chars: {query[-500:]}")
                    if params:
                        log_level(f"Parameters:")
                        for k, v in params.items():
                            val_preview = str(v)[:200] if isinstance(v, str) else str(v)
                            log_level(f"  {k}: {val_preview}")
                    log_level("=" * 80)
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
        file_path: str = None,
        content_type: str = "document",
        storage_key: str = None,
        visual_embedding: list = None,
        embedding: list = None,
        # ADR-081: Source document lifecycle
        garage_key: str = None,
        content_hash: str = None,
        char_offset_start: int = None,
        char_offset_end: int = None,
        chunk_index: int = None
    ) -> Dict[str, Any]:
        """
        Create a Source node in the graph.

        Args:
            source_id: Unique identifier for the source
            document: Document/ontology name for logical grouping
            paragraph: Paragraph/chunk number in the document
            full_text: Full text content of the paragraph (prose for images, original text for documents)
            file_path: Path to the source file (optional)
            content_type: Type of content - "document" or "image" (ADR-057)
            storage_key: MinIO object key for image storage (images only, ADR-057)
            visual_embedding: 768-dim visual embedding from Nomic Vision (images only, ADR-057)
            embedding: Text embedding of full_text (both documents and image prose, ADR-057)
            garage_key: Garage object key for source document (ADR-081)
            content_hash: SHA-256 hash of original document content (ADR-081)
            char_offset_start: Starting character position in original document (ADR-081)
            char_offset_end: Ending character position in original document (ADR-081)
            chunk_index: Zero-based chunk index for ordering (ADR-081)

        Returns:
            Dictionary with created node properties

        Raises:
            ValueError: If offset parameters are invalid
            Exception: If node creation fails
        """
        # ADR-081: Validate offset parameters
        if char_offset_start is not None and char_offset_start < 0:
            raise ValueError(f"char_offset_start must be >= 0, got {char_offset_start}")
        if char_offset_end is not None and char_offset_end < 0:
            raise ValueError(f"char_offset_end must be >= 0, got {char_offset_end}")
        if char_offset_start is not None and char_offset_end is not None:
            if char_offset_end < char_offset_start:
                raise ValueError(f"char_offset_end ({char_offset_end}) must be >= char_offset_start ({char_offset_start})")
        if chunk_index is not None and chunk_index < 0:
            raise ValueError(f"chunk_index must be >= 0, got {chunk_index}")

        query = """
        CREATE (s:Source {
            source_id: $source_id,
            document: $document,
            paragraph: $paragraph,
            full_text: $full_text,
            file_path: $file_path,
            content_type: $content_type,
            storage_key: $storage_key,
            visual_embedding: $visual_embedding,
            embedding: $embedding,
            garage_key: $garage_key,
            content_hash: $content_hash,
            char_offset_start: $char_offset_start,
            char_offset_end: $char_offset_end,
            chunk_index: $chunk_index
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
                    "file_path": file_path if file_path else None,
                    "content_type": content_type,
                    "storage_key": storage_key,
                    "visual_embedding": visual_embedding,
                    "embedding": embedding,
                    "garage_key": garage_key,
                    "content_hash": content_hash,
                    "char_offset_start": char_offset_start,
                    "char_offset_end": char_offset_end,
                    "chunk_index": chunk_index
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
        search_terms: List[str],
        description: str = "",
        created_at_epoch: int = 0
    ) -> Dict[str, Any]:
        """
        Create a Concept node in the graph.

        Args:
            concept_id: Unique identifier for the concept
            label: Human-readable concept label
            embedding: Vector embedding for similarity search
            search_terms: Alternative terms/phrases for the concept
            description: Factual 1-2 sentence definition of the concept (optional)
            created_at_epoch: Global epoch at creation time (ADR-200 provenance)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (c:Concept {
            concept_id: $concept_id,
            label: $label,
            description: $description,
            embedding: $embedding,
            search_terms: $search_terms,
            created_at_epoch: $created_at_epoch,
            last_seen_epoch: $created_at_epoch,
            seen_count: 1
        })
        RETURN c
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "concept_id": concept_id,
                    "label": label,
                    "description": description,
                    "embedding": embedding,
                    "search_terms": search_terms,
                    "created_at_epoch": created_at_epoch
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

    def update_concept_epoch(self, concept_id: str, epoch: int) -> bool:
        """
        Update a concept's last_seen_epoch and increment seen_count.

        Called when a concept is matched (reused) during ingestion.
        ADR-200: epoch provenance for concept vitality tracking.

        Args:
            concept_id: The concept to update
            epoch: Current global epoch

        Returns:
            True if the concept was found and updated
        """
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        SET c.last_seen_epoch = $epoch,
            c.seen_count = COALESCE(c.seen_count, 0) + 1
        RETURN c.concept_id as concept_id
        """
        try:
            result = self._execute_cypher(
                query,
                params={"concept_id": concept_id, "epoch": epoch},
                fetch_one=True
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Failed to update concept epoch for {concept_id}: {e}")
            return False

    def find_instance_by_quote_and_source(
        self,
        quote: str,
        source_id: str
    ) -> Optional[str]:
        """
        Find an existing Instance node with the same quote and source.

        This prevents duplicate Instance nodes when the same quote appears
        in multiple chunks or documents that reference the same source.

        Args:
            quote: Exact quote to search for
            source_id: Source node ID to match

        Returns:
            instance_id if found, None otherwise
        """
        query = """
        MATCH (i:Instance {quote: $quote})-[:FROM_SOURCE]->(s:Source {source_id: $source_id})
        RETURN i.instance_id as instance_id
        LIMIT 1
        """

        try:
            result = self._execute_cypher(
                query,
                params={"quote": quote, "source_id": source_id},
                fetch_one=True
            )
            return result.get('instance_id') if result else None
        except Exception as e:
            logger.warning(f"Failed to find existing instance: {e}")
            return None

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
        Create APPEARS relationship from Concept to Source.

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
        MERGE (c)-[:APPEARS]->(s)
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
        confidence: float,
        # ADR-051: Edge metadata for provenance tracking
        created_by: Optional[str] = None,
        source: str = "llm_extraction",
        job_id: Optional[str] = None,
        document_id: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> bool:
        """
        Create a relationship between two concepts with category and provenance metadata.

        Args:
            from_id: Source concept ID
            to_id: Target concept ID
            rel_type: Canonical relationship type (normalized via Porter Stemmer matcher)
            category: Relationship category (logical_truth, causal, structural, etc.)
            confidence: Confidence score (0.0-1.0)
            created_by: User ID who created this relationship (optional)
            source: Origin of relationship ("llm_extraction" or "human_curation", default: "llm_extraction")
            job_id: Job ID that created this relationship (optional)
            document_id: Document hash where this relationship originated (optional)
            created_at: Timestamp (ISO format, defaults to current UTC time)

        Returns:
            True if relationship created successfully

        Raises:
            ValueError: If confidence out of range
            Exception: If relationship creation fails

        Note:
            Relationship type validation happens in ingestion layer via normalize_relationship_type().
            This method trusts that rel_type has been normalized to one of the 30 canonical types.

            ADR-051: Edge metadata enables:
            - Audit trail: "Which job created this relationship?"
            - Human vs LLM distinction: Weight human-curated relationships differently
            - Cascade delete: Delete all edges from a document
            - MCP silent storage: Metadata NOT exposed to Claude (ADR-044)
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")

        # Build properties dict (only include non-None values)
        properties = {
            "confidence": confidence,
            "category": category,
            "source": source,
            "created_at": created_at if created_at else datetime.now(timezone.utc).isoformat()
        }

        if created_by:
            properties["created_by"] = created_by
        if job_id:
            properties["job_id"] = job_id
        if document_id:
            properties["document_id"] = document_id

        # Build properties string for Cypher query
        props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])

        # Note: AGE doesn't support dynamic relationship types in parameterized queries
        # We have to use string interpolation for the relationship type
        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})
        MATCH (c2:Concept {{concept_id: $to_id}})
        MERGE (c1)-[r:{rel_type} {{{props_str}}}]->(c2)
        RETURN c1, r, c2
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "from_id": from_id,
                    "to_id": to_id,
                    **properties
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
    # Ontology Node Methods (ADR-200)
    # =========================================================================
    # Ontology nodes are first-class graph entities in the same embedding space
    # as concepts. They represent knowledge domains that organize Source nodes
    # via :SCOPED_BY edges. The s.document string on Source nodes is preserved
    # as a denormalized cache — :SCOPED_BY is the source of truth for new code.

    def create_ontology_node(
        self,
        ontology_id: str,
        name: str,
        description: str = "",
        embedding: Optional[List[float]] = None,
        search_terms: Optional[List[str]] = None,
        lifecycle_state: str = "active",
        creation_epoch: int = 0,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an Ontology node in the graph.

        Args:
            ontology_id: Unique identifier (ont_<uuid>)
            name: Ontology name (matches s.document on Source nodes)
            description: What this knowledge domain covers
            embedding: 1536-dim vector in the same space as concepts
            search_terms: Alternative names for similarity matching
            lifecycle_state: 'active' | 'pinned' | 'frozen'
            creation_epoch: Global epoch when created
            created_by: Username of the creating user (ADR-200 Phase 2)

        Returns:
            Dictionary with created node properties

        Raises:
            Exception: If node creation fails
        """
        query = """
        CREATE (o:Ontology {
            ontology_id: $ontology_id,
            name: $name,
            description: $description,
            embedding: $embedding,
            search_terms: $search_terms,
            lifecycle_state: $lifecycle_state,
            creation_epoch: $creation_epoch,
            created_by: $created_by
        })
        RETURN o
        """

        try:
            results = self._execute_cypher(
                query,
                params={
                    "ontology_id": ontology_id,
                    "name": name,
                    "description": description,
                    "embedding": embedding,
                    "search_terms": search_terms if search_terms else [],
                    "lifecycle_state": lifecycle_state,
                    "creation_epoch": creation_epoch,
                    "created_by": created_by
                },
                fetch_one=True
            )
            if results:
                agtype_result = results.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else {}
            return {}
        except Exception as e:
            raise Exception(f"Failed to create Ontology node {name}: {e}")

    def get_ontology_node(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get an Ontology node by name.

        Args:
            name: Ontology name

        Returns:
            Dictionary with node properties, or None if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except Exception as e:
            logger.error(f"Failed to get Ontology node {name}: {e}")
            return None

    def list_ontology_nodes(self) -> List[Dict[str, Any]]:
        """
        List all Ontology nodes in the graph.

        Returns:
            List of dictionaries with ontology node properties
        """
        query = """
        MATCH (o:Ontology)
        RETURN o
        ORDER BY o.name
        """

        try:
            results = self._execute_cypher(query)
            ontologies = []
            for row in results:
                agtype_result = row.get('o')
                parsed = self._parse_agtype(agtype_result)
                if isinstance(parsed, dict) and 'properties' in parsed:
                    ontologies.append(parsed['properties'])
            return ontologies
        except Exception as e:
            logger.error(f"Failed to list Ontology nodes: {e}")
            return []

    def delete_ontology_node(self, name: str) -> bool:
        """
        Delete an Ontology node and its edges (SCOPED_BY, etc).

        Does not delete Source nodes — they retain their s.document property.
        Only removes the :Ontology node and edges connected to it.

        Args:
            name: Ontology name

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        DETACH DELETE o
        RETURN count(*) as deleted
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name},
                fetch_one=True
            )
            deleted = int(str(result.get("deleted", 0))) if result else 0
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to delete Ontology node {name}: {e}")
            return False

    def rename_ontology_node(self, old_name: str, new_name: str) -> bool:
        """
        Rename an Ontology node (updates the name property).

        This is called alongside rename_ontology() which updates s.document
        on Source nodes. Both must be kept in sync.

        Args:
            old_name: Current ontology name
            new_name: New ontology name

        Returns:
            True if renamed, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $old_name})
        SET o.name = $new_name
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"old_name": old_name, "new_name": new_name},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to rename Ontology node {old_name} -> {new_name}: {e}")
            return False

    def create_scoped_by_edge(self, source_id: str, ontology_name: str) -> bool:
        """
        Create a :SCOPED_BY edge from a Source to an Ontology node.

        Uses MERGE for idempotency — safe to call multiple times.

        Args:
            source_id: Source node identifier
            ontology_name: Ontology node name

        Returns:
            True if edge exists (created or already present)
        """
        query = """
        MATCH (s:Source {source_id: $source_id})
        MATCH (o:Ontology {name: $ontology_name})
        MERGE (s)-[:SCOPED_BY]->(o)
        RETURN s.source_id as source_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "source_id": source_id,
                    "ontology_name": ontology_name
                },
                fetch_one=True
            )
            return result is not None
        except Exception as e:
            logger.warning(f"Failed to create SCOPED_BY edge {source_id} -> {ontology_name}: {e}")
            return False

    def ensure_ontology_exists(self, name: str, description: str = "", created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create an Ontology node. Used by ingestion pipeline to ensure
        the target ontology exists before creating Source nodes.

        Args:
            name: Ontology name
            description: Optional description for new ontologies
            created_by: Username of the creating user (ADR-200 Phase 2)

        Returns:
            Dictionary with ontology node properties
        """
        existing = self.get_ontology_node(name)
        if existing:
            return existing

        import uuid
        ontology_id = f"ont_{uuid.uuid4()}"

        # Get current epoch from graph_metrics
        creation_epoch = 0
        try:
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM graph_metrics WHERE metric_name = 'document_ingestion_counter'"
                    )
                    row = cur.fetchone()
                    if row:
                        creation_epoch = row[0] or 0
            finally:
                conn.commit()
                self.pool.putconn(conn)
        except Exception:
            pass  # Default to 0 if metrics unavailable

        try:
            return self.create_ontology_node(
                ontology_id=ontology_id,
                name=name,
                description=description,
                lifecycle_state="active",
                creation_epoch=creation_epoch,
                created_by=created_by
            )
        except Exception:
            # Race condition: another worker created it between our check and create.
            # Re-fetch the winner's node (same pattern as vocabulary sync races).
            existing = self.get_ontology_node(name)
            if existing:
                return existing
            raise  # Re-raise if it's a genuine failure, not a race

    def update_ontology_lifecycle(
        self,
        name: str,
        new_state: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update the lifecycle_state of an Ontology node.

        Args:
            name: Ontology name
            new_state: Target state ('active', 'pinned', or 'frozen')

        Returns:
            Dictionary with updated node properties, or None if not found

        Raises:
            ValueError: If new_state is not a valid lifecycle state
        """
        valid_states = {"active", "pinned", "frozen"}
        if new_state not in valid_states:
            raise ValueError(f"Invalid lifecycle state '{new_state}'. Must be one of: {valid_states}")

        query = """
        MATCH (o:Ontology {name: $name})
        SET o.lifecycle_state = $new_state
        RETURN o
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "new_state": new_state},
                fetch_one=True
            )
            if result:
                agtype_result = result.get('o')
                parsed = self._parse_agtype(agtype_result)
                return parsed.get('properties', {}) if isinstance(parsed, dict) else None
            return None
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update Ontology lifecycle for {name}: {e}")
            return None

    def is_ontology_frozen(self, name: str) -> bool:
        """
        Check if an ontology is in the 'frozen' lifecycle state.

        Returns False for nonexistent ontologies (they have no protection).

        Args:
            name: Ontology name

        Returns:
            True if the ontology exists and is frozen, False otherwise
        """
        node = self.get_ontology_node(name)
        if node is None:
            return False
        return node.get("lifecycle_state") == "frozen"

    def update_ontology_embedding(
        self,
        name: str,
        embedding: List[float]
    ) -> bool:
        """
        Update the embedding on an existing Ontology node.

        Args:
            name: Ontology name
            embedding: 1536-dim vector

        Returns:
            True if updated, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.embedding = $embedding
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={"name": name, "embedding": embedding},
                fetch_one=True
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to update Ontology embedding for {name}: {e}")
            return False

    # =========================================================================
    # Ontology Scoring & Breathing Controls (ADR-200 Phase 3a)
    # =========================================================================

    def get_ontology_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get raw counts for mass scoring of an ontology.

        Returns concept_count, source_count, file_count, evidence_count,
        internal_relationship_count, cross_ontology_relationship_count.

        Args:
            name: Ontology name

        Returns:
            Dictionary with counts, or None if ontology not found
        """
        # Verify ontology exists
        node = self.get_ontology_node(name)
        if not node:
            return None

        stats = {
            "ontology": name,
            "concept_count": 0,
            "source_count": 0,
            "file_count": 0,
            "evidence_count": 0,
            "internal_relationship_count": 0,
            "cross_ontology_relationship_count": 0,
        }

        try:
            # Source and file counts
            source_query = """
            MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(s) as source_count,
                   count(DISTINCT s.file_path) as file_count
            """
            result = self._execute_cypher(
                source_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["source_count"] = int(str(result.get("source_count", 0)))
                stats["file_count"] = int(str(result.get("file_count", 0)))

            # Concept count: concepts connected to sources scoped to this ontology
            concept_query = """
            MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(DISTINCT c) as concept_count
            """
            result = self._execute_cypher(
                concept_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["concept_count"] = int(str(result.get("concept_count", 0)))

            # Evidence count: instances from sources in this ontology
            evidence_query = """
            MATCH (i:Instance)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
            RETURN count(i) as evidence_count
            """
            result = self._execute_cypher(
                evidence_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["evidence_count"] = int(str(result.get("evidence_count", 0)))

            # Internal relationships: both endpoints in this ontology's sources
            internal_query = """
            MATCH (c1:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
            MATCH (c1)-[r]->(c2:Concept)
            MATCH (c2)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology {name: $name})
            RETURN count(DISTINCT r) as internal_count
            """
            result = self._execute_cypher(
                internal_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["internal_relationship_count"] = int(
                    str(result.get("internal_count", 0))
                )

            # Cross-ontology relationships: one endpoint in this ontology, other in different
            cross_query = """
            MATCH (c1:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
            MATCH (c1)-[r]->(c2:Concept)
            MATCH (c2)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology)
            WHERE o2.name <> $name
            RETURN count(DISTINCT r) as cross_count
            """
            result = self._execute_cypher(
                cross_query, params={"name": name}, fetch_one=True
            )
            if result:
                stats["cross_ontology_relationship_count"] = int(
                    str(result.get("cross_count", 0))
                )

            return stats
        except Exception as e:
            logger.error(f"Failed to get ontology stats for {name}: {e}")
            return stats  # Return partial stats rather than None

    def get_concept_degree_ranking(
        self, ontology_name: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top concepts by degree centrality within an ontology.

        Args:
            ontology_name: Ontology name
            limit: Max concepts to return (default 20)

        Returns:
            List of {concept_id, label, degree, in_degree, out_degree}
        """
        query = """
        MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        WITH DISTINCT c
        OPTIONAL MATCH (c)-[r_out]->(:Concept)
        OPTIONAL MATCH (:Concept)-[r_in]->(c)
        WITH c,
             count(DISTINCT r_out) as out_degree,
             count(DISTINCT r_in) as in_degree
        RETURN c.concept_id as concept_id,
               c.label as label,
               out_degree + in_degree as degree,
               in_degree,
               out_degree
        ORDER BY out_degree + in_degree DESC
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            concepts = []
            for row in results:
                concepts.append({
                    "concept_id": str(row.get("concept_id", "")),
                    "label": str(row.get("label", "")),
                    "degree": int(str(row.get("degree", 0))),
                    "in_degree": int(str(row.get("in_degree", 0))),
                    "out_degree": int(str(row.get("out_degree", 0))),
                })
            return concepts
        except Exception as e:
            logger.error(
                f"Failed to get concept degree ranking for {ontology_name}: {e}"
            )
            return []

    def get_cross_ontology_affinity(
        self, ontology_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get cross-ontology concept overlap (shared concept affinity).

        Finds ontologies that share concepts with the target ontology,
        ranked by affinity_score = shared_count / total_concepts_in_target.

        Args:
            ontology_name: Ontology name
            limit: Max other ontologies to return

        Returns:
            List of {other_ontology, shared_concept_count, total_concepts, affinity_score}
        """
        query = """
        MATCH (c:Concept)-->(s1:Source)-[:SCOPED_BY]->(o1:Ontology {name: $name})
        WITH collect(DISTINCT c) as my_concepts, count(DISTINCT c) as my_total
        UNWIND my_concepts as c
        MATCH (c)-->(s2:Source)-[:SCOPED_BY]->(o2:Ontology)
        WHERE o2.name <> $name
        WITH o2.name as other_ontology,
             count(DISTINCT c) as shared_count,
             my_total
        RETURN other_ontology,
               shared_count as shared_concept_count,
               my_total as total_concepts,
               toFloat(shared_count) / toFloat(my_total) as affinity_score
        ORDER BY toFloat(shared_count) / toFloat(my_total) DESC
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            affinities = []
            for row in results:
                affinities.append({
                    "other_ontology": str(row.get("other_ontology", "")),
                    "shared_concept_count": int(
                        str(row.get("shared_concept_count", 0))
                    ),
                    "total_concepts": int(str(row.get("total_concepts", 0))),
                    "affinity_score": float(str(row.get("affinity_score", 0.0))),
                })
            return affinities
        except Exception as e:
            logger.error(
                f"Failed to get cross-ontology affinity for {ontology_name}: {e}"
            )
            return []

    def get_all_ontology_scores(self) -> List[Dict[str, Any]]:
        """
        Read cached score properties from all Ontology nodes.

        Returns:
            List of {ontology, mass_score, coherence_score, raw_exposure,
                     weighted_exposure, protection_score, last_evaluated_epoch}
        """
        query = """
        MATCH (o:Ontology)
        RETURN o.name as ontology,
               o.mass_score as mass_score,
               o.coherence_score as coherence_score,
               o.raw_exposure as raw_exposure,
               o.weighted_exposure as weighted_exposure,
               o.protection_score as protection_score,
               o.last_evaluated_epoch as last_evaluated_epoch
        ORDER BY o.protection_score DESC
        """

        try:
            results = self._execute_cypher(query)
            scores = []
            for row in results:
                scores.append({
                    "ontology": str(row.get("ontology", "")),
                    "mass_score": float(str(row.get("mass_score", 0) or 0)),
                    "coherence_score": float(
                        str(row.get("coherence_score", 0) or 0)
                    ),
                    "raw_exposure": float(str(row.get("raw_exposure", 0) or 0)),
                    "weighted_exposure": float(
                        str(row.get("weighted_exposure", 0) or 0)
                    ),
                    "protection_score": float(
                        str(row.get("protection_score", 0) or 0)
                    ),
                    "last_evaluated_epoch": int(
                        str(row.get("last_evaluated_epoch", 0) or 0)
                    ),
                })
            return scores
        except Exception as e:
            logger.error(f"Failed to get all ontology scores: {e}")
            return []

    def get_current_epoch(self) -> int:
        """
        Get the current global epoch from graph_metrics.

        Returns:
            Current document_ingestion_counter value, or 0 if unavailable
        """
        try:
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM graph_metrics "
                        "WHERE metric_name = 'document_ingestion_counter'"
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0] or 0
            finally:
                conn.commit()
                self.pool.putconn(conn)
        except Exception:
            pass
        return 0

    def get_ontology_concept_embeddings(
        self, ontology_name: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get concept embeddings for concepts in an ontology.
        Used for coherence scoring (pairwise similarity).

        Args:
            ontology_name: Ontology name
            limit: Max concepts (sampling for large ontologies)

        Returns:
            List of {concept_id, label, embedding}
        """
        query = """
        MATCH (c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        WHERE c.embedding IS NOT NULL
        RETURN DISTINCT c.concept_id as concept_id,
               c.label as label,
               c.embedding as embedding
        LIMIT $limit
        """

        try:
            results = self._execute_cypher(
                query, params={"name": ontology_name, "limit": limit}
            )
            concepts = []
            for row in results:
                embedding = row.get("embedding")
                if embedding:
                    # Parse AGE embedding format
                    if isinstance(embedding, str):
                        try:
                            embedding = json.loads(embedding)
                        except (json.JSONDecodeError, TypeError):
                            continue
                    concepts.append({
                        "concept_id": str(row.get("concept_id", "")),
                        "label": str(row.get("label", "")),
                        "embedding": embedding,
                    })
            return concepts
        except Exception as e:
            logger.error(
                f"Failed to get concept embeddings for {ontology_name}: {e}"
            )
            return []

    # -------------------------------------------------------------------------
    # Ontology Breathing Write Controls (ADR-200 Phase 3a)
    # -------------------------------------------------------------------------

    def update_ontology_scores(
        self,
        name: str,
        mass: float,
        coherence: float,
        protection: float,
        raw_exposure: float = 0.0,
        weighted_exposure: float = 0.0,
        epoch: int = 0,
    ) -> bool:
        """
        Cache computed scores on the Ontology node.

        Args:
            name: Ontology name
            mass: Mass score 0.0-1.0
            coherence: Coherence score 0.0-1.0
            protection: Protection score (can be negative)
            raw_exposure: Raw exposure 0.0-1.0
            weighted_exposure: Weighted exposure 0.0-1.0
            epoch: Epoch when scores were computed

        Returns:
            True if updated, False if not found
        """
        query = """
        MATCH (o:Ontology {name: $name})
        SET o.mass_score = $mass,
            o.coherence_score = $coherence,
            o.protection_score = $protection,
            o.raw_exposure = $raw_exposure,
            o.weighted_exposure = $weighted_exposure,
            o.last_evaluated_epoch = $epoch
        RETURN o.ontology_id as ontology_id
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "name": name,
                    "mass": mass,
                    "coherence": coherence,
                    "protection": protection,
                    "raw_exposure": raw_exposure,
                    "weighted_exposure": weighted_exposure,
                    "epoch": epoch,
                },
                fetch_one=True,
            )
            return result is not None and result.get("ontology_id") is not None
        except Exception as e:
            logger.error(f"Failed to update ontology scores for {name}: {e}")
            return False

    def reassign_sources(
        self,
        source_ids: List[str],
        from_ontology: str,
        to_ontology: str,
    ) -> Dict[str, Any]:
        """
        Move sources from one ontology to another.

        Updates s.document property and SCOPED_BY edges.
        Batched in chunks of 50 source IDs.

        Args:
            source_ids: Source IDs to move
            from_ontology: Source ontology name
            to_ontology: Destination ontology name

        Returns:
            {sources_reassigned: int, success: bool, error: str|None}
        """
        # Verify both ontologies exist
        from_node = self.get_ontology_node(from_ontology)
        if not from_node:
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Source ontology '{from_ontology}' not found",
            }

        to_node = self.get_ontology_node(to_ontology)
        if not to_node:
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Target ontology '{to_ontology}' not found",
            }

        # Check frozen state — cannot move FROM frozen
        if from_node.get("lifecycle_state") == "frozen":
            return {
                "sources_reassigned": 0,
                "success": False,
                "error": f"Source ontology '{from_ontology}' is frozen",
            }

        total_reassigned = 0
        batch_size = 50

        try:
            for i in range(0, len(source_ids), batch_size):
                batch = source_ids[i : i + batch_size]

                # Update s.document on Source nodes
                update_query = """
                MATCH (s:Source)
                WHERE s.source_id IN $source_ids AND s.document = $from_name
                SET s.document = $to_name
                RETURN count(s) as updated
                """
                result = self._execute_cypher(
                    update_query,
                    params={
                        "source_ids": batch,
                        "from_name": from_ontology,
                        "to_name": to_ontology,
                    },
                    fetch_one=True,
                )
                updated = int(str(result.get("updated", 0))) if result else 0

                # Delete old SCOPED_BY edges
                delete_edge_query = """
                MATCH (s:Source)-[r:SCOPED_BY]->(o:Ontology {name: $from_name})
                WHERE s.source_id IN $source_ids
                DELETE r
                RETURN count(*) as deleted
                """
                self._execute_cypher(
                    delete_edge_query,
                    params={"source_ids": batch, "from_name": from_ontology},
                    fetch_one=True,
                )

                # Create new SCOPED_BY edges
                create_edge_query = """
                MATCH (s:Source), (o:Ontology {name: $to_name})
                WHERE s.source_id IN $source_ids AND s.document = $to_name
                MERGE (s)-[:SCOPED_BY]->(o)
                RETURN count(*) as created
                """
                self._execute_cypher(
                    create_edge_query,
                    params={"source_ids": batch, "to_name": to_ontology},
                    fetch_one=True,
                )

                total_reassigned += updated

            return {
                "sources_reassigned": total_reassigned,
                "success": True,
                "error": None,
            }
        except Exception as e:
            logger.error(
                f"Failed to reassign sources from {from_ontology} to {to_ontology}: {e}"
            )
            return {
                "sources_reassigned": total_reassigned,
                "success": False,
                "error": str(e),
            }

    def dissolve_ontology(
        self, name: str, target_ontology: str
    ) -> Dict[str, Any]:
        """
        Non-destructive ontology demotion: move all sources to target, then remove node.

        This is the key primitive for ontology demotion in the breathing cycle.
        Unlike delete_ontology (which cascade-deletes sources), dissolve preserves
        all data by moving it first.

        Args:
            name: Ontology to dissolve
            target_ontology: Default ontology to receive sources

        Returns:
            {dissolved_ontology, sources_reassigned, ontology_node_deleted,
             reassignment_targets, success, error}
        """
        node = self.get_ontology_node(name)
        if not node:
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Ontology '{name}' not found",
            }

        lifecycle = node.get("lifecycle_state", "active")
        if lifecycle in ("pinned", "frozen"):
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Ontology '{name}' is {lifecycle} — cannot dissolve",
            }

        # Get all source IDs in this ontology
        source_query = """
        MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $name})
        RETURN s.source_id as source_id
        """
        try:
            results = self._execute_cypher(
                source_query, params={"name": name}
            )
            all_source_ids = [
                str(row.get("source_id", ""))
                for row in results
                if row.get("source_id")
            ]
        except Exception as e:
            return {
                "dissolved_ontology": name,
                "sources_reassigned": 0,
                "ontology_node_deleted": False,
                "reassignment_targets": [],
                "success": False,
                "error": f"Failed to list sources: {e}",
            }

        # Reassign all sources to target
        total_reassigned = 0
        targets = set()

        if all_source_ids:
            result = self.reassign_sources(all_source_ids, name, target_ontology)
            total_reassigned = result.get("sources_reassigned", 0)
            if not result.get("success"):
                return {
                    "dissolved_ontology": name,
                    "sources_reassigned": total_reassigned,
                    "ontology_node_deleted": False,
                    "reassignment_targets": [],
                    "success": False,
                    "error": result.get("error"),
                }
            targets.add(target_ontology)

        # Remove the Ontology node (only the node + its edges, not Sources)
        node_deleted = self.delete_ontology_node(name)

        return {
            "dissolved_ontology": name,
            "sources_reassigned": total_reassigned,
            "ontology_node_deleted": node_deleted,
            "reassignment_targets": sorted(targets),
            "success": True,
            "error": None,
        }

    def batch_create_scoped_by_edges(
        self, source_ids: List[str], ontology_name: str
    ) -> int:
        """
        Batch create SCOPED_BY edges from multiple sources to an ontology.

        Args:
            source_ids: List of source IDs
            ontology_name: Ontology name

        Returns:
            Number of edges created/verified
        """
        if not source_ids:
            return 0

        query = """
        MATCH (o:Ontology {name: $ontology_name})
        WITH o
        MATCH (s:Source)
        WHERE s.source_id IN $source_ids
        MERGE (s)-[:SCOPED_BY]->(o)
        RETURN count(*) as created
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "source_ids": source_ids,
                    "ontology_name": ontology_name,
                },
                fetch_one=True,
            )
            return int(str(result.get("created", 0))) if result else 0
        except Exception as e:
            logger.error(
                f"Failed to batch create SCOPED_BY edges for {ontology_name}: {e}"
            )
            return 0

    # =========================================================================
    # Ontology-to-Ontology Edge Methods (ADR-200 Phase 5)
    # =========================================================================

    VALID_ONTOLOGY_EDGE_TYPES = ("OVERLAPS", "SPECIALIZES", "GENERALIZES")

    def upsert_ontology_edge(
        self,
        from_name: str,
        to_name: str,
        edge_type: str,
        score: float,
        shared_concept_count: int,
        epoch: int,
        source: str = "breathing_worker",
    ) -> bool:
        """
        Create or update an edge between two Ontology nodes.

        Uses MERGE to upsert — creates if absent, updates properties if exists.

        Args:
            from_name: Source ontology name
            to_name: Target ontology name
            edge_type: OVERLAPS, SPECIALIZES, or GENERALIZES
            score: Affinity strength (0.0-1.0)
            shared_concept_count: Number of shared concepts
            epoch: Global epoch when computed
            source: 'breathing_worker' or 'manual'

        Returns:
            True if edge was upserted successfully
        """
        if edge_type not in self.VALID_ONTOLOGY_EDGE_TYPES:
            raise ValueError(
                f"Invalid ontology edge type: {edge_type!r}. "
                f"Must be one of {self.VALID_ONTOLOGY_EDGE_TYPES}"
            )

        query = f"""
        MATCH (a:Ontology {{name: $from_name}})
        MATCH (b:Ontology {{name: $to_name}})
        MERGE (a)-[r:{edge_type}]->(b)
        SET r.score = $score,
            r.shared_concept_count = $shared_count,
            r.computed_at_epoch = $epoch,
            r.source = $source
        RETURN type(r) as edge_type
        """

        try:
            result = self._execute_cypher(
                query,
                params={
                    "from_name": from_name,
                    "to_name": to_name,
                    "score": score,
                    "shared_count": shared_concept_count,
                    "epoch": epoch,
                    "source": source,
                },
                fetch_one=True,
            )
            return result is not None
        except Exception as e:
            logger.error(
                f"Failed to upsert {edge_type} edge "
                f"{from_name} -> {to_name}: {e}"
            )
            return False

    def get_ontology_edges(
        self, ontology_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get all ontology-to-ontology edges for an ontology (both directions).

        Args:
            ontology_name: Ontology name

        Returns:
            List of edge dicts with: from_ontology, to_ontology, edge_type,
            score, shared_concept_count, computed_at_epoch, source, direction
        """
        query = """
        MATCH (o:Ontology {name: $name})
        OPTIONAL MATCH (o)-[out]->(other:Ontology)
        WHERE type(out) IN ['OVERLAPS', 'SPECIALIZES', 'GENERALIZES']
        WITH o, collect({
            from_ontology: $name,
            to_ontology: other.name,
            edge_type: type(out),
            score: out.score,
            shared_concept_count: out.shared_concept_count,
            computed_at_epoch: out.computed_at_epoch,
            source: out.source,
            direction: 'outgoing'
        }) as outgoing
        OPTIONAL MATCH (other2:Ontology)-[inc]->(o)
        WHERE type(inc) IN ['OVERLAPS', 'SPECIALIZES', 'GENERALIZES']
        WITH outgoing, collect({
            from_ontology: other2.name,
            to_ontology: $name,
            edge_type: type(inc),
            score: inc.score,
            shared_concept_count: inc.shared_concept_count,
            computed_at_epoch: inc.computed_at_epoch,
            source: inc.source,
            direction: 'incoming'
        }) as incoming
        RETURN outgoing + incoming as edges
        """

        try:
            result = self._execute_cypher(
                query, params={"name": ontology_name}, fetch_one=True
            )
            if not result or not result.get("edges"):
                return []
            # Filter out entries with null edge_type (from empty OPTIONAL MATCH)
            return [
                e for e in result["edges"]
                if e.get("edge_type") is not None
            ]
        except Exception as e:
            logger.error(
                f"Failed to get ontology edges for {ontology_name}: {e}"
            )
            return []

    def delete_derived_ontology_edges(
        self, ontology_name: str, edge_type: str = None
    ) -> int:
        """
        Delete derived (breathing_worker) ontology edges. Manual edges are preserved.

        Args:
            ontology_name: Ontology name
            edge_type: Optional specific type to delete (OVERLAPS, SPECIALIZES,
                       GENERALIZES). If None, deletes all derived types.

        Returns:
            Number of edges deleted
        """
        if edge_type and edge_type not in self.VALID_ONTOLOGY_EDGE_TYPES:
            raise ValueError(f"Invalid ontology edge type: {edge_type!r}")

        # Delete derived edges in both directions for this ontology
        types_to_delete = [edge_type] if edge_type else list(self.VALID_ONTOLOGY_EDGE_TYPES)
        total_deleted = 0

        for etype in types_to_delete:
            # Outgoing
            out_query = f"""
            MATCH (o:Ontology {{name: $name}})-[r:{etype}]->(other:Ontology)
            WHERE r.source = 'breathing_worker'
            DELETE r
            RETURN count(r) as deleted
            """
            # Incoming
            in_query = f"""
            MATCH (other:Ontology)-[r:{etype}]->(o:Ontology {{name: $name}})
            WHERE r.source = 'breathing_worker'
            DELETE r
            RETURN count(r) as deleted
            """

            try:
                for query in [out_query, in_query]:
                    result = self._execute_cypher(
                        query, params={"name": ontology_name}, fetch_one=True
                    )
                    if result:
                        total_deleted += int(str(result.get("deleted", 0)))
            except Exception as e:
                logger.error(
                    f"Failed to delete derived {etype} edges "
                    f"for {ontology_name}: {e}"
                )

        return total_deleted

    def delete_all_derived_ontology_edges(self) -> int:
        """
        Delete ALL derived ontology-to-ontology edges across the graph.

        Called at the start of a breathing cycle to refresh edges from scratch.

        Returns:
            Number of edges deleted
        """
        total_deleted = 0
        for etype in self.VALID_ONTOLOGY_EDGE_TYPES:
            query = f"""
            MATCH (:Ontology)-[r:{etype}]->(:Ontology)
            WHERE r.source = 'breathing_worker'
            DELETE r
            RETURN count(r) as deleted
            """
            try:
                result = self._execute_cypher(query, fetch_one=True)
                if result:
                    total_deleted += int(str(result.get("deleted", 0)))
            except Exception as e:
                logger.error(f"Failed to delete all derived {etype} edges: {e}")

        return total_deleted

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

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
        """
        try:
            query = """
            MATCH (v:VocabType)
            WHERE v.is_active = 't'
            RETURN count(v) as total
            """
            result = self._execute_cypher(query, fetch_one=True)
            if result and 'total' in result:
                return int(str(result['total']))
            return 0
        except Exception as e:
            logger.error(f"Failed to get vocabulary size from graph: {e}")
            return 0

    def get_vocab_config(self, key: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        Get vocabulary configuration value from database.

        Reads from kg_api.vocabulary_config table using helper function
        created in migration 017.

        Args:
            key: Configuration key (e.g., 'vocab_min', 'vocab_emergency')
            fallback: Value to return if key not found

        Returns:
            Configuration value as string, or fallback if not found

        Example:
            >>> client = AGEClient()
            >>> emergency = client.get_vocab_config('vocab_emergency', '200')
            >>> print(f"Emergency threshold: {emergency}")
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kg_api.get_vocab_config(%s, %s)",
                    (key, fallback)
                )
                result = cur.fetchone()
                if result and result[0] is not None:
                    return result[0]
                return fallback
        except Exception as e:
            logger.error(f"Failed to get vocab config '{key}' from database: {e}")
            return fallback
        finally:
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

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
        """
        try:
            if include_inactive:
                query = """
                MATCH (v:VocabType)
                RETURN v.name as name
                ORDER BY v.name
                """
            else:
                query = """
                MATCH (v:VocabType)
                WHERE v.is_active = 't'
                RETURN v.name as name
                ORDER BY v.name
                """

            results = self._execute_cypher(query)
            return [str(row['name']) for row in results]
        except Exception as e:
            logger.error(f"Failed to get edge types from graph: {e}")
            return []

    def sync_missing_edge_types(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Sync edge types from graph edges to vocabulary (ADR-077).

        Scans all unique relationship types used in the graph and ensures each
        has a corresponding entry in the vocabulary table and VocabType node.
        This fixes the gap where predefined types from constants.py are used
        during ingestion but never registered in the vocabulary.

        Args:
            dry_run: If True, only report missing types without creating them

        Returns:
            Dict with:
                - missing: List of types in graph but not vocabulary
                - synced: List of types that were synced (if not dry_run)
                - failed: List of types that failed to sync
                - system_types: List of system types (skipped)
                - total_graph_types: Count of unique types in graph

        Example:
            >>> result = client.sync_missing_edge_types(dry_run=True)
            >>> print(f"Missing: {len(result['missing'])}")
            >>> # If satisfied, run without dry_run
            >>> result = client.sync_missing_edge_types(dry_run=False)
        """
        from api.app.constants import RELATIONSHIP_TYPE_TO_CATEGORY

        # System relationship types - internal use only, not user-facing vocabulary
        SYSTEM_TYPES = {
            'APPEARS', 'EVIDENCED_BY', 'FROM_SOURCE', 'IN_CATEGORY',
            'SCOPED_BY', 'LOAD', 'SET',  # LOAD/SET may appear from SQL parsing artifacts
        }

        try:
            # Step 1: Get all unique edge types from the graph
            graph_types_query = """
                MATCH ()-[r]->()
                RETURN DISTINCT type(r) AS rel_type
            """
            graph_results = self._execute_cypher(graph_types_query)
            graph_types = set()
            for row in graph_results:
                rel_type = str(row['rel_type']).strip('"')
                if rel_type and rel_type.isupper():  # Only valid uppercase types
                    graph_types.add(rel_type)

            # Step 2: Get all types in vocabulary (VocabType nodes)
            vocab_types = set(self.get_all_edge_types(include_inactive=True))

            # Step 3: Find missing types
            missing_types = graph_types - vocab_types - SYSTEM_TYPES
            system_types_found = graph_types & SYSTEM_TYPES

            result = {
                'missing': sorted(list(missing_types)),
                'synced': [],
                'failed': [],
                'system_types': sorted(list(system_types_found)),
                'total_graph_types': len(graph_types),
                'total_vocab_types': len(vocab_types),
                'dry_run': dry_run
            }

            if dry_run:
                logger.info(f"Dry run: Found {len(missing_types)} missing types")
                return result

            # Step 4: Add missing types to vocabulary
            for rel_type in sorted(missing_types):
                try:
                    # Get category from constants.py if defined
                    category = RELATIONSHIP_TYPE_TO_CATEGORY.get(rel_type, 'llm_generated')
                    is_builtin = rel_type in RELATIONSHIP_TYPE_TO_CATEGORY

                    # Use add_edge_type which handles both SQL table and VocabType node
                    success = self.add_edge_type(
                        relationship_type=rel_type,
                        category=category,
                        description=f"Auto-synced from graph edges",
                        added_by="vocabulary_sync",
                        is_builtin=is_builtin
                    )

                    if success:
                        result['synced'].append(rel_type)
                        logger.info(f"✓ Synced '{rel_type}' → {category}")
                    else:
                        # add_edge_type returns False if type already exists
                        result['synced'].append(rel_type)
                        logger.debug(f"Type '{rel_type}' already exists (race condition)")

                except Exception as e:
                    logger.error(f"✗ Failed to sync '{rel_type}': {e}")
                    result['failed'].append({'type': rel_type, 'error': str(e)})

            return result

        except Exception as e:
            logger.error(f"Failed to sync missing edge types: {e}")
            raise

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

        Note:
            ADR-048 Phase 3.2: Migrated to query graph (:VocabType nodes)
            Some metadata fields (description, added_by, etc.) not yet in graph
        """
        try:
            # Query VocabType node and category via relationship (Phase 3.3)
            query = """
            MATCH (v:VocabType {name: $type_name})
            OPTIONAL MATCH (v)-[:IN_CATEGORY]->(c:VocabCategory)
            RETURN v.name as relationship_type,
                   v.is_active as is_active,
                   v.is_builtin as is_builtin,
                   v.usage_count as usage_count,
                   v.direction_semantics as direction_semantics,
                   c.name as category
            """
            result = self._execute_cypher(query, {"type_name": relationship_type}, fetch_one=True)

            if not result:
                return None

            # Build info dict from graph data
            # Note: AGE stores PostgreSQL booleans as strings 't'/'f'
            # Handle missing/None values gracefully for usage_count
            usage_count_val = result.get('usage_count', 0)
            usage_count = 0 if usage_count_val is None else int(str(usage_count_val))

            info = {
                'relationship_type': str(result['relationship_type']),
                'is_active': str(result.get('is_active', 't')) == 't',
                'is_builtin': str(result.get('is_builtin', 'f')) == 't',
                'usage_count': usage_count,
                'category': str(result['category']) if result.get('category') else None,
                'direction_semantics': str(result['direction_semantics']) if result.get('direction_semantics') else None,  # ADR-049
                # Fields not yet migrated to graph (Phase 3.3)
                'description': None,
                'added_by': None,
                'added_at': None,
                'synonyms': None,
                'deprecation_reason': None,
                'embedding_model': None,
                'embedding_generated_at': None,
            }

            # Fetch ADR-047 category scoring fields from SQL (not yet in graph)
            try:
                conn = self.pool.getconn()
                try:
                    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                        cur.execute("""
                            SELECT category_source, category_confidence,
                                   category_scores, category_ambiguous
                            FROM kg_api.relationship_vocabulary
                            WHERE relationship_type = %s
                        """, (relationship_type,))
                        sql_result = cur.fetchone()
                        if sql_result:
                            info['category_source'] = sql_result.get('category_source')
                            info['category_confidence'] = sql_result.get('category_confidence')
                            info['category_scores'] = sql_result.get('category_scores')
                            info['category_ambiguous'] = sql_result.get('category_ambiguous')
                finally:
                    self.pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Failed to fetch category scoring fields for {relationship_type}: {e}")
                info['category_source'] = None
                info['category_confidence'] = None
                info['category_scores'] = None
                info['category_ambiguous'] = None

            # ⚠️ CRITICAL: Real-time edge counting required (ADR-044)
            # This MUST count actual edges - do NOT return cached/stale usage_count!
            # Grounding calculations depend on current edge state. See ADR-044 section on caching.
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

        except Exception as e:
            logger.error(f"Failed to get edge type info from graph: {e}")
            return None

    def add_edge_type(
        self,
        relationship_type: str,
        category: str,
        description: Optional[str] = None,
        added_by: str = "system",
        is_builtin: bool = False,
        direction_semantics: Optional[str] = None,
        ai_provider = None,
        auto_categorize: bool = True
    ) -> bool:
        """
        Add a new relationship type to vocabulary with automatic embedding generation.

        Creates both:
        1. Row in kg_api.relationship_vocabulary table
        2. :VocabType node in the graph (ADR-048 Phase 3.2)

        ADR-047: If category is "llm_generated" and auto_categorize is True, will compute
        proper semantic category after generating embedding using probabilistic categorization.

        ADR-049: LLM determines direction_semantics based on frame of reference when creating
        new relationship types. Direction can be updated on first use if NULL.

        Args:
            relationship_type: Relationship type name (e.g., "AUTHORED_BY")
            category: Semantic category (or "llm_generated" for auto-categorization)
            description: Optional description
            added_by: Who added the type (username or "system")
            is_builtin: Whether this is a protected builtin type
            direction_semantics: Direction ("outward", "inward", "bidirectional", or None for LLM to decide)
            ai_provider: Optional AI provider for embedding generation (auto-generation if provided)
            auto_categorize: If True and category="llm_generated", compute proper category (ADR-047)

        Returns:
            True if added successfully, False if already exists

        Example:
            >>> success = client.add_edge_type("AUTHORED_BY", "llm_generated",
            ...                                 "LLM-generated relationship type",
            ...                                 "llm_extractor",
            ...                                 direction_semantics="outward",
            ...                                 ai_provider=provider,
            ...                                 auto_categorize=True)
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Add to vocabulary table (ADR-049: include direction_semantics)
                cur.execute("""
                    INSERT INTO kg_api.relationship_vocabulary
                        (relationship_type, description, category, added_by, is_builtin, is_active, direction_semantics)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (relationship_type) DO NOTHING
                    RETURNING relationship_type
                """, (relationship_type, description, category, added_by, is_builtin, direction_semantics))
                result = cur.fetchone()
                was_added = result is not None

                # Generate and store embedding if AI provider available and type was just added
                embedding_json = None
                model = None
                if was_added and ai_provider is not None:
                    try:
                        # Convert edge type to descriptive text (same logic as SynonymDetector)
                        descriptive_text = f"relationship: {relationship_type.lower().replace('_', ' ')}"

                        # Generate embedding
                        embedding_response = ai_provider.generate_embedding(descriptive_text)
                        embedding = embedding_response["embedding"]
                        model = embedding_response.get("model", "text-embedding-ada-002")

                        # Store embedding in table
                        embedding_json = json.dumps(embedding)
                        cur.execute("""
                            UPDATE kg_api.relationship_vocabulary
                            SET embedding = %s::jsonb,
                                embedding_model = %s,
                                embedding_generated_at = NOW()
                            WHERE relationship_type = %s
                        """, (embedding_json, model, relationship_type))

                        logger.debug(f"Generated embedding for vocabulary type '{relationship_type}' ({len(embedding)} dims)")

                        # ADR-047: Auto-categorize LLM-generated types
                        if auto_categorize and category == "llm_generated":
                            try:
                                import asyncio
                                from api.app.lib.vocabulary_categorizer import VocabularyCategorizer

                                # Create categorizer and compute category
                                categorizer = VocabularyCategorizer(self, ai_provider)

                                # Run async categorization in sync context
                                try:
                                    loop = asyncio.get_event_loop()
                                except RuntimeError:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                assignment = loop.run_until_complete(
                                    categorizer.assign_category(
                                        relationship_type,
                                        store=False,
                                        embedding=embedding  # Pass freshly-generated embedding
                                    )
                                )

                                # Update category in database
                                category = assignment.category
                                cur.execute("""
                                    UPDATE kg_api.relationship_vocabulary
                                    SET category = %s,
                                        category_source = 'computed',
                                        category_confidence = %s,
                                        category_scores = %s::jsonb,
                                        category_ambiguous = %s
                                    WHERE relationship_type = %s
                                """, (
                                    category,
                                    assignment.confidence,
                                    json.dumps(assignment.scores),
                                    assignment.ambiguous,
                                    relationship_type
                                ))

                                logger.info(
                                    f"  🎯 Auto-categorized '{relationship_type}' → {category} "
                                    f"(confidence: {assignment.confidence:.0%})"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to auto-categorize '{relationship_type}': {e}")
                                # Keep category as "llm_generated" if categorization fails

                    except Exception as e:
                        # Don't fail the entire operation if embedding generation fails
                        logger.warning(f"Failed to generate embedding for '{relationship_type}': {e}")

                # Create :VocabType node in graph (ADR-048 Phase 3.3 + ADR-049)
                # Creates both node and :IN_CATEGORY relationship
                if was_added:
                    try:
                        # Use MERGE to be idempotent (in case of partial failures)
                        # Phase 3.3: Create :IN_CATEGORY relationship to :VocabCategory node
                        # ADR-049: Add direction_semantics property
                        vocab_query = """
                            MERGE (v:VocabType {name: $name})
                            SET v.description = $description,
                                v.is_builtin = $is_builtin,
                                v.is_active = 't',
                                v.added_by = $added_by,
                                v.usage_count = 0,
                                v.direction_semantics = $direction_semantics
                            WITH v
                            MERGE (c:VocabCategory {name: $category})
                            MERGE (v)-[:IN_CATEGORY]->(c)
                            RETURN v.name as name
                        """
                        params = {
                            "name": relationship_type,
                            "category": category,
                            "description": description or "",
                            "is_builtin": 't' if is_builtin else 'f',
                            "added_by": added_by,
                            "direction_semantics": direction_semantics
                        }
                        self._execute_cypher(vocab_query, params)
                        direction_info = f", direction={direction_semantics}" if direction_semantics else ""
                        logger.debug(f"Created :VocabType node with :IN_CATEGORY->{category}{direction_info} for '{relationship_type}'")
                    except Exception as e:
                        logger.warning(f"Failed to create :VocabType node for '{relationship_type}': {e}")
                        # Don't fail the entire operation - table row was created successfully

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

        Note:
            ADR-048 Phase 3.3: Queries :IN_CATEGORY relationships to :VocabCategory nodes
        """
        try:
            # Phase 3.3: Query via :IN_CATEGORY relationships
            query = """
            MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
            WHERE v.is_active = 't'
            WITH c.name as category, count(v) as type_count
            RETURN category, type_count
            ORDER BY type_count DESC
            """
            results = self._execute_cypher(query)
            return {str(row['category']): int(str(row['type_count'])) for row in results}
        except Exception as e:
            logger.error(f"Failed to get category distribution from graph: {e}")
            return {}

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
    # DocumentMeta Operations (ADR-051: Graph-Based Provenance Tracking)
    # =========================================================================

    def get_document_meta(self, content_hash: str, ontology: str) -> Optional[Dict[str, Any]]:
        """
        Check if a document already exists in the graph (ADR-051).

        Used for deduplication: checks graph (persistent state) instead of
        jobs table (ephemeral log). This prevents job deletion from breaking
        deduplication.

        Args:
            content_hash: SHA-256 hash of document content (format: "sha256:abc123...")
            ontology: Target ontology name

        Returns:
            Document metadata dict if found, None otherwise
            {
                "document_id": "sha256:abc123...",
                "content_hash": "sha256:abc123...",
                "ontology": "My Docs",
                "filename": "chapter1.txt",
                "source_type": "file",
                "file_path": "/home/user/docs/chapter1.txt",
                "hostname": "workstation-01",
                "ingested_at": "2025-10-31T12:34:56Z",
                "ingested_by": "user_123",
                "job_id": "job_xyz",
                "source_count": 15
            }

        Example:
            >>> doc = client.get_document_meta("sha256:abc123...", "My Docs")
            >>> if doc:
            >>>     print(f"Document already ingested: {doc['filename']}")
        """
        query = """
        MATCH (d:DocumentMeta {content_hash: $hash, ontology: $ontology})
        RETURN d
        """

        try:
            results = self._execute_cypher(query, {
                "hash": content_hash,
                "ontology": ontology
            })

            if results and len(results) > 0:
                agtype_result = results[0].get('d')
                if agtype_result:
                    parsed = self._parse_agtype(agtype_result)
                    return parsed.get('properties', {}) if isinstance(parsed, dict) else None

            return None

        except Exception as e:
            logger.error(f"Failed to check DocumentMeta for hash {content_hash[:16]}...: {e}")
            return None

    def create_document_meta(
        self,
        document_id: str,
        content_hash: str,
        ontology: str,
        source_count: int,
        ingested_by: str,
        job_id: str,
        filename: Optional[str] = None,
        source_type: Optional[str] = None,
        file_path: Optional[str] = None,
        hostname: Optional[str] = None,
        ingested_at: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        # ADR-081: Source document lifecycle
        garage_key: Optional[str] = None,
        content_type: str = "document",
        storage_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a DocumentMeta node and link it to Source nodes (ADR-051, ADR-081).

        Tracks successfully ingested documents as first-class graph citizens.
        Enables deduplication via graph (persistent) instead of jobs table (ephemeral).

        Args:
            document_id: Unique identifier (typically same as content_hash)
            content_hash: SHA-256 hash for deduplication
            ontology: Target ontology name
            source_count: Number of Source nodes created from this document
            ingested_by: User ID who submitted the job
            job_id: Job ID that ingested this document
            filename: Display name (optional, best-effort)
            source_type: "file" | "stdin" | "mcp" | "api" (optional)
            file_path: Full filesystem path (optional, file ingestion only)
            hostname: Hostname where ingested (optional, CLI only)
            ingested_at: ISO timestamp (optional, defaults to now())
            source_ids: List of source_ids to link via HAS_SOURCE relationship (optional)
            garage_key: Garage object key for source document (ADR-081)
            content_type: "document" or "image" (default: "document")
            storage_key: Garage object key for image binary (ADR-057, images only)

        Returns:
            Created DocumentMeta node properties

        Raises:
            Exception: If node creation or linking fails

        Example:
            >>> client.create_document_meta(
            ...     document_id="sha256:abc123...",
            ...     content_hash="sha256:abc123...",
            ...     ontology="My Docs",
            ...     source_count=15,
            ...     ingested_by="user_123",
            ...     job_id="job_xyz",
            ...     filename="chapter1.txt",
            ...     source_type="file",
            ...     file_path="/home/user/docs/chapter1.txt",
            ...     hostname="workstation-01",
            ...     source_ids=["chapter1_txt_chunk1", "chapter1_txt_chunk2", ...],
            ...     garage_key="sources/My_Docs/a1b2c3d4...txt"
            ... )
        """
        from datetime import datetime, timezone

        # Build properties dict (only include non-None values)
        properties = {
            "document_id": document_id,
            "content_hash": content_hash,
            "ontology": ontology,
            "source_count": source_count,
            "ingested_by": ingested_by,
            "job_id": job_id
        }

        # Content type (document or image)
        if content_type != "document":
            properties["content_type"] = content_type

        # Add optional provenance metadata (best-effort)
        if filename:
            properties["filename"] = filename
        if source_type:
            properties["source_type"] = source_type
        if file_path:
            properties["file_path"] = file_path
        if hostname:
            properties["hostname"] = hostname
        # ADR-081: Link to source document in Garage
        if garage_key:
            properties["garage_key"] = garage_key
        # ADR-057: Image binary location in Garage
        if storage_key:
            properties["storage_key"] = storage_key

        # Add timestamp (default to now if not provided)
        if ingested_at:
            properties["ingested_at"] = ingested_at
        else:
            properties["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Create DocumentMeta node with explicit properties
        # Build property assignments dynamically
        prop_assignments = []
        for key, value in properties.items():
            prop_assignments.append(f"{key}: ${key}")
        props_str = ", ".join(prop_assignments)

        create_query = f"""
        CREATE (d:DocumentMeta {{{props_str}}})
        RETURN d
        """

        try:
            results = self._execute_cypher(create_query, properties)

            if not results:
                raise Exception("DocumentMeta node creation returned no results")

            # Parse created node
            agtype_result = results[0].get('d')
            parsed = self._parse_agtype(agtype_result)
            created_doc = parsed.get('properties', {}) if isinstance(parsed, dict) else {}

            # Link to Source nodes if source_ids provided
            if source_ids and len(source_ids) > 0:
                link_query = """
                MATCH (d:DocumentMeta {document_id: $doc_id})
                MATCH (s:Source)
                WHERE s.source_id IN $source_ids
                CREATE (d)-[:HAS_SOURCE {
                    created_at: $created_at
                }]->(s)
                RETURN count(s) as linked_count
                """

                link_results = self._execute_cypher(link_query, {
                    "doc_id": document_id,
                    "source_ids": source_ids,
                    "created_at": properties["ingested_at"]
                })

                if link_results:
                    linked_count = self._parse_agtype(link_results[0].get('linked_count'))
                    logger.info(
                        f"Created DocumentMeta {document_id[:16]}... and linked "
                        f"{linked_count}/{len(source_ids)} Source nodes"
                    )
                else:
                    logger.warning(
                        f"Created DocumentMeta {document_id[:16]}... but failed to link Source nodes"
                    )

            logger.info(
                f"✓ Created DocumentMeta: {properties.get('filename', document_id[:16])}... "
                f"({source_count} sources, type: {source_type or 'unknown'})"
            )

            return created_doc

        except Exception as e:
            raise Exception(f"Failed to create DocumentMeta {document_id[:16]}...: {e}")

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
