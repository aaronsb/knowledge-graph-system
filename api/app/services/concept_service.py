"""
Concept Service - Deterministic concept CRUD (ADR-089).

Orchestrates concept creation/editing without LLM ingestion pipeline.
Delegates to existing infrastructure:
- AGEClient for graph operations
- EmbeddingWorker for embedding generation

No new workers - this is a thin orchestration layer.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

from ..models.concepts import (
    ConceptCreate,
    ConceptUpdate,
    ConceptResponse,
    ConceptListResponse,
    MatchingMode,
    CreationMethod,
)
from ..lib.age_client import AGEClient
from .embedding_worker import get_embedding_worker

logger = logging.getLogger(__name__)


class ConceptService:
    """
    Service for deterministic concept CRUD operations.

    Handles:
    - Concept creation with embedding generation
    - Matching against existing concepts (when mode=auto)
    - Synthetic source creation for provenance
    - Listing and filtering concepts
    - Updating and deleting concepts
    """

    # Similarity threshold for matching existing concepts
    MATCH_THRESHOLD = 0.85

    def __init__(self, age_client: AGEClient):
        """
        Initialize with database client.

        Args:
            age_client: AGEClient instance for graph operations
        """
        self.age_client = age_client
        self._embedding_worker = None

    @property
    def embedding_worker(self):
        """Lazy-load embedding worker."""
        if self._embedding_worker is None:
            self._embedding_worker = get_embedding_worker()
        return self._embedding_worker

    async def create_concept(
        self,
        request: ConceptCreate,
        user_id: Optional[str] = None
    ) -> ConceptResponse:
        """
        Create a new concept or match to existing one.

        Args:
            request: Concept creation request
            user_id: ID of user creating the concept (for audit)

        Returns:
            ConceptResponse with created or matched concept

        Raises:
            ValueError: If match_only mode and no match found
        """
        logger.info(f"Creating concept: label='{request.label}', mode={request.matching_mode}")

        # Generate embedding for the concept label
        try:
            embedding_result = self.embedding_worker.generate_concept_embedding(request.label)
            embedding = embedding_result.get("embedding", [])
            if not embedding:
                raise ValueError("Embedding worker returned empty embedding")
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {e}")

        # Handle matching based on mode
        matched_concept = None
        if request.matching_mode in (MatchingMode.AUTO, MatchingMode.MATCH_ONLY):
            matched_concept = await self._find_matching_concept(embedding, request.ontology)

        if matched_concept:
            logger.info(f"Matched existing concept: {matched_concept['concept_id']}")
            return ConceptResponse(
                concept_id=matched_concept["concept_id"],
                label=matched_concept.get("label", request.label),
                description=matched_concept.get("description"),
                search_terms=matched_concept.get("search_terms", []),
                ontology=request.ontology,
                creation_method=matched_concept.get("creation_method"),
                has_embedding=True,
                matched_existing=True
            )

        # No match found
        if request.matching_mode == MatchingMode.MATCH_ONLY:
            raise ValueError(
                f"No matching concept found for '{request.label}' in ontology '{request.ontology}'"
            )

        # Create new concept
        concept_id = f"c_{uuid4().hex[:12]}"

        # Create synthetic source for provenance
        source_id = await self._create_synthetic_source(
            ontology=request.ontology,
            concept_label=request.label,
            creation_method=request.creation_method,
            user_id=user_id
        )

        # Create concept node (ADR-200: epoch provenance)
        current_epoch = self.age_client.get_current_epoch()
        self.age_client.create_concept_node(
            concept_id=concept_id,
            label=request.label,
            embedding=embedding,
            search_terms=request.search_terms or [],
            description=request.description or "",
            created_at_epoch=current_epoch
        )

        # Link concept to source
        self.age_client.link_concept_to_source(concept_id, source_id)

        # Store creation metadata (in concept properties)
        await self._set_concept_metadata(
            concept_id=concept_id,
            creation_method=request.creation_method.value,
            created_by=user_id,
            ontology=request.ontology
        )

        logger.info(f"Created concept: {concept_id}")

        return ConceptResponse(
            concept_id=concept_id,
            label=request.label,
            description=request.description,
            search_terms=request.search_terms or [],
            ontology=request.ontology,
            creation_method=request.creation_method.value,
            has_embedding=True,
            matched_existing=False
        )

    async def _find_matching_concept(
        self,
        embedding: List[float],
        ontology: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing concept matching the embedding.

        Uses vector similarity search with threshold.
        """
        try:
            # Use AGEClient's vector_search for similarity matching
            results = self.age_client.vector_search(
                embedding=embedding,
                threshold=self.MATCH_THRESHOLD,
                top_k=1
            )
            if results:
                return results[0]
        except Exception as e:
            logger.warning(f"Concept matching failed: {e}")
        return None

    async def _create_synthetic_source(
        self,
        ontology: str,
        concept_label: str,
        creation_method: CreationMethod,
        user_id: Optional[str] = None
    ) -> str:
        """
        Create a synthetic Source node for provenance tracking.

        Synthetic sources indicate manually/programmatically created concepts
        rather than concepts extracted from documents.
        """
        source_id = f"src_{uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build descriptive text for the synthetic source
        full_text = f"Concept '{concept_label}' created via {creation_method.value}"
        if user_id:
            full_text += f" by user {user_id}"
        full_text += f" at {timestamp}"

        self.age_client.create_source_node(
            source_id=source_id,
            document=ontology,
            paragraph=0,  # Single-paragraph synthetic source
            full_text=full_text,
            content_type="synthetic",  # Distinguish from document/image
            file_path=None
        )

        return source_id

    async def _set_concept_metadata(
        self,
        concept_id: str,
        creation_method: str,
        created_by: Optional[str],
        ontology: str
    ) -> None:
        """Set creation metadata on concept node."""
        timestamp = datetime.now(timezone.utc).isoformat()

        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        SET c.creation_method = $creation_method,
            c.created_by = $created_by,
            c.ontology = $ontology,
            c.created_at = $created_at
        RETURN c
        """

        try:
            self.age_client._execute_cypher(
                query,
                params={
                    "concept_id": concept_id,
                    "creation_method": creation_method,
                    "created_by": created_by,
                    "ontology": ontology,
                    "created_at": timestamp
                }
            )
        except Exception as e:
            logger.warning(f"Failed to set concept metadata: {e}")

    async def list_concepts(
        self,
        ontology: Optional[str] = None,
        label_contains: Optional[str] = None,
        creation_method: Optional[CreationMethod] = None,
        offset: int = 0,
        limit: int = 50
    ) -> ConceptListResponse:
        """
        List concepts with optional filtering.

        Args:
            ontology: Filter by ontology
            label_contains: Filter by label substring
            creation_method: Filter by how concept was created
            offset: Pagination offset
            limit: Maximum results to return

        Returns:
            ConceptListResponse with matching concepts
        """
        # Build query with filters
        where_clauses = []
        params = {"offset": offset, "limit": limit}

        if ontology:
            where_clauses.append("c.ontology = $ontology")
            params["ontology"] = ontology

        if label_contains:
            where_clauses.append("c.label CONTAINS $label_contains")
            params["label_contains"] = label_contains

        if creation_method:
            where_clauses.append("c.creation_method = $creation_method")
            params["creation_method"] = creation_method.value

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Count total
        count_query = f"""
        MATCH (c:Concept)
        WHERE {where_clause}
        RETURN count(c) as total
        """

        count_result = self.age_client._execute_cypher(count_query, params=params, fetch_one=True)
        total = count_result.get("total", 0) if count_result else 0

        # Fetch page
        query = f"""
        MATCH (c:Concept)
        WHERE {where_clause}
        RETURN c.concept_id as concept_id,
               c.label as label,
               c.description as description,
               c.search_terms as search_terms,
               c.ontology as ontology,
               c.creation_method as creation_method,
               c.embedding IS NOT NULL as has_embedding
        ORDER BY c.label
        SKIP $offset
        LIMIT $limit
        """

        results = self.age_client._execute_cypher(query, params=params)

        concepts = [
            ConceptResponse(
                concept_id=r.get("concept_id", ""),
                label=r.get("label", ""),
                description=r.get("description"),
                search_terms=r.get("search_terms") or [],
                ontology=r.get("ontology"),
                creation_method=r.get("creation_method"),
                has_embedding=r.get("has_embedding", True),
                matched_existing=False
            )
            for r in (results or [])
        ]

        return ConceptListResponse(
            concepts=concepts,
            total=total,
            offset=offset,
            limit=limit
        )

    async def update_concept(
        self,
        concept_id: str,
        request: ConceptUpdate,
        regenerate_embedding: bool = True
    ) -> ConceptResponse:
        """
        Update an existing concept.

        Args:
            concept_id: ID of concept to update
            request: Partial update fields
            regenerate_embedding: If True and label changed, regenerate embedding

        Returns:
            Updated ConceptResponse

        Raises:
            ValueError: If concept not found
        """
        # Verify concept exists
        existing = await self._get_concept(concept_id)
        if not existing:
            raise ValueError(f"Concept not found: {concept_id}")

        # Build SET clause
        set_parts = []
        params = {"concept_id": concept_id}

        if request.label is not None:
            set_parts.append("c.label = $label")
            params["label"] = request.label

            # Regenerate embedding if label changed
            if regenerate_embedding:
                try:
                    embedding_result = self.embedding_worker.generate_concept_embedding(request.label)
                    embedding = embedding_result.get("embedding", [])
                    if embedding:
                        set_parts.append("c.embedding = $embedding")
                        params["embedding"] = embedding
                except Exception as e:
                    logger.warning(f"Failed to regenerate embedding for concept update: {e}")

        if request.description is not None:
            set_parts.append("c.description = $description")
            params["description"] = request.description

        if request.search_terms is not None:
            set_parts.append("c.search_terms = $search_terms")
            params["search_terms"] = request.search_terms

        if not set_parts:
            # Nothing to update
            return await self._concept_to_response(existing)

        # Add updated timestamp
        set_parts.append("c.updated_at = $updated_at")
        params["updated_at"] = datetime.now(timezone.utc).isoformat()

        query = f"""
        MATCH (c:Concept {{concept_id: $concept_id}})
        SET {", ".join(set_parts)}
        RETURN c
        """

        result = self.age_client._execute_cypher(query, params=params, fetch_one=True)
        if not result:
            raise ValueError(f"Failed to update concept: {concept_id}")

        return await self.get_concept_response(concept_id)

    async def delete_concept(
        self,
        concept_id: str,
        cascade: bool = False
    ) -> bool:
        """
        Delete a concept.

        Args:
            concept_id: ID of concept to delete
            cascade: If True, also delete orphaned synthetic sources

        Returns:
            True if deleted

        Raises:
            ValueError: If concept not found
        """
        # Verify concept exists
        existing = await self._get_concept(concept_id)
        if not existing:
            raise ValueError(f"Concept not found: {concept_id}")

        # If cascade, find synthetic sources connected only to this concept
        orphaned_sources = []
        if cascade:
            orphaned_sources = await self._find_orphaned_synthetic_sources(concept_id)

        # Delete concept and its relationships
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        DETACH DELETE c
        """

        try:
            self.age_client._execute_cypher(query, params={"concept_id": concept_id})
            logger.info(f"Deleted concept: {concept_id}")

            # Delete orphaned synthetic sources if cascade
            if cascade and orphaned_sources:
                await self._delete_orphaned_sources(orphaned_sources)
                logger.info(f"Cascade deleted {len(orphaned_sources)} orphaned synthetic sources")

            return True
        except Exception as e:
            raise ValueError(f"Failed to delete concept: {e}")

    async def _find_orphaned_synthetic_sources(self, concept_id: str) -> List[str]:
        """
        Find synthetic sources that will be orphaned when this concept is deleted.

        A source is orphaned if:
        1. It has content_type = 'synthetic'
        2. All its Instance connections lead only to this concept

        Args:
            concept_id: Concept being deleted

        Returns:
            List of source_ids that will be orphaned
        """
        # Find synthetic sources connected to this concept
        # that have NO other concept connections
        query = """
        MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source)
        WHERE s.content_type = 'synthetic'
        WITH s
        OPTIONAL MATCH (other:Concept)-[:EVIDENCED_BY]->(:Instance)-[:FROM_SOURCE]->(s)
        WHERE other.concept_id <> $concept_id
        WITH s, count(other) as other_count
        WHERE other_count = 0
        RETURN s.source_id as source_id
        """

        try:
            results = self.age_client._execute_cypher(
                query,
                params={"concept_id": concept_id}
            )
            return [r.get("source_id") for r in (results or []) if r.get("source_id")]
        except Exception as e:
            logger.warning(f"Failed to find orphaned sources: {e}")
            return []

    async def _delete_orphaned_sources(self, source_ids: List[str]) -> None:
        """
        Delete orphaned source nodes and their connected instances.

        Args:
            source_ids: List of source IDs to delete
        """
        for source_id in source_ids:
            try:
                # Delete source and connected instances
                query = """
                MATCH (s:Source {source_id: $source_id})
                OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(s)
                DETACH DELETE i, s
                """
                self.age_client._execute_cypher(query, params={"source_id": source_id})
                logger.debug(f"Deleted orphaned synthetic source: {source_id}")
            except Exception as e:
                logger.warning(f"Failed to delete orphaned source {source_id}: {e}")

    async def _get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get concept by ID."""
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        RETURN c
        """
        result = self.age_client._execute_cypher(
            query,
            params={"concept_id": concept_id},
            fetch_one=True
        )
        if result and result.get("c"):
            parsed = self.age_client._parse_agtype(result.get("c"))
            return parsed.get("properties", {}) if isinstance(parsed, dict) else {}
        return None

    async def get_concept_response(self, concept_id: str) -> ConceptResponse:
        """Get concept as response model."""
        concept = await self._get_concept(concept_id)
        if not concept:
            raise ValueError(f"Concept not found: {concept_id}")
        return await self._concept_to_response(concept)

    async def _concept_to_response(self, concept: Dict[str, Any]) -> ConceptResponse:
        """Convert concept dict to response model."""
        return ConceptResponse(
            concept_id=concept.get("concept_id", ""),
            label=concept.get("label", ""),
            description=concept.get("description"),
            search_terms=concept.get("search_terms") or [],
            ontology=concept.get("ontology"),
            creation_method=concept.get("creation_method"),
            has_embedding=concept.get("embedding") is not None,
            matched_existing=False
        )


def get_concept_service(age_client: AGEClient) -> ConceptService:
    """Factory function to create ConceptService."""
    return ConceptService(age_client)
