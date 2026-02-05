"""
Ingestion mixin for graph node and edge creation.

Handles CRUD operations for the core graph entities created during
document ingestion: Source, Concept, and Instance nodes, plus the
edges that link them (APPEARS, EVIDENCED_BY, FROM_SOURCE).

Also includes DocumentMeta operations (ADR-051/081) for tracking
document-level metadata and deduplication.

Entity flow during ingestion:
    Document -> Source nodes (chunks)
    Source -> Concept nodes (extracted via LLM)
    Source -> Instance nodes (evidence quotes)
    Concept -[APPEARS]-> Source
    Concept -[EVIDENCED_BY]-> Instance -[FROM_SOURCE]-> Source
    Concept -[rel_type]-> Concept (inter-concept relationships)
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class IngestionMixin:
    """Source, Concept, and Instance node CRUD with graph linking."""

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

    # =========================================================================
    # Document Metadata (ADR-051/081)
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

        # MERGE DocumentMeta on document_id to prevent duplicate nodes on re-ingest.
        # SET remaining properties so metadata updates on force re-ingest.
        merge_key_props = f"document_id: $document_id"
        set_assignments = []
        for key, value in properties.items():
            if key != "document_id":
                set_assignments.append(f"d.{key} = ${key}")
        set_str = ", ".join(set_assignments)

        create_query = f"""
        MERGE (d:DocumentMeta {{{merge_key_props}}})
        SET {set_str}
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
            # MERGE prevents duplicate edges on re-ingest
            if source_ids and len(source_ids) > 0:
                link_query = """
                MATCH (d:DocumentMeta {document_id: $doc_id})
                MATCH (s:Source)
                WHERE s.source_id IN $source_ids
                MERGE (d)-[:HAS_SOURCE]->(s)
                RETURN count(s) as linked_count
                """

                link_results = self._execute_cypher(link_query, {
                    "doc_id": document_id,
                    "source_ids": source_ids,
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
