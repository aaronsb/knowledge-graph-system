"""
Batch Service - Bulk graph operations with transactions (ADR-089 Phase 1b).

Provides batch creation of concepts and edges in a single atomic transaction.
If any operation fails, the entire batch is rolled back.
"""

import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from datetime import datetime, timezone

from psycopg2 import extras

from ..models.graph import (
    BatchCreateRequest,
    BatchResponse,
    BatchItemResult,
    BatchConceptCreate,
    BatchEdgeCreate,
)
from ..models.concepts import MatchingMode
from ..lib.age_client import AGEClient
from .embedding_worker import get_embedding_worker
from .audit_service import log_audit, AuditAction, AuditOutcome

logger = logging.getLogger(__name__)


def _escape_cypher_string(value: str) -> str:
    """
    Escape a string for safe use in Cypher queries.

    Handles backslashes and single quotes to prevent injection.
    """
    if value is None:
        return ""
    # Escape backslashes first, then single quotes
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _normalize_relationship_type(rel_type: str) -> str:
    """
    Normalize and validate relationship type for safe use in Cypher queries.

    - Convert to uppercase
    - Replace spaces with underscores
    - Remove other special characters
    - Validate result is non-empty and starts with a letter

    Raises:
        ValueError: If relationship type is invalid after normalization
    """
    normalized = rel_type.upper().replace(" ", "_")
    # Only allow alphanumeric and underscores
    cleaned = "".join(c for c in normalized if c.isalnum() or c == "_")

    # Validate result
    if not cleaned:
        raise ValueError(f"Invalid relationship type '{rel_type}': empty after normalization")
    if not cleaned[0].isalpha():
        raise ValueError(
            f"Invalid relationship type '{rel_type}': must start with a letter"
        )
    if len(cleaned) > 100:
        raise ValueError(
            f"Invalid relationship type '{rel_type}': exceeds 100 character limit"
        )

    return cleaned


class BatchService:
    """
    Service for batch graph operations with transaction support.

    All operations in a batch are executed in a single PostgreSQL transaction.
    If any operation fails, the entire batch is rolled back.
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

    async def execute_batch(
        self,
        request: BatchCreateRequest,
        user_id: Optional[int] = None
    ) -> BatchResponse:
        """
        Execute a batch creation request.

        Args:
            request: Batch creation request with concepts and edges
            user_id: ID of user performing the operation (for audit)

        Returns:
            BatchResponse with counts and per-item results

        Raises:
            Exception: If batch execution fails (after rollback)
        """
        logger.info(
            f"Executing batch: {len(request.concepts)} concepts, "
            f"{len(request.edges)} edges, ontology={request.ontology}"
        )

        response = BatchResponse()

        # Phase 1: Generate embeddings (before transaction)
        # This is idempotent and can be done outside the transaction
        embeddings = await self._generate_embeddings(request.concepts)
        if len(embeddings) != len(request.concepts):
            response.errors.append("Failed to generate embeddings for some concepts")
            return response

        # Phase 2: Execute database operations in transaction
        conn = self.age_client.pool.getconn()
        try:
            # Setup AGE extension (must be done before transaction)
            with conn.cursor() as setup_cur:
                setup_cur.execute("LOAD 'age';")
                setup_cur.execute("SET search_path = ag_catalog, \"$user\", public;")
            conn.commit()

            # Now start the actual transaction
            conn.autocommit = False

            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                try:
                    # Create concepts and build label->ID map
                    label_to_id = await self._create_concepts_in_transaction(
                        cur, request, embeddings, response, user_id
                    )

                    # Create edges using the label->ID map
                    await self._create_edges_in_transaction(
                        cur, request, label_to_id, response
                    )

                    # Log audit entry for the batch
                    log_audit(
                        cursor=cur,
                        user_id=user_id,
                        action=AuditAction.BATCH_CREATE.value,
                        resource_type="batch",
                        resource_id=None,
                        details={
                            "ontology": request.ontology,
                            "concepts_created": response.concepts_created,
                            "concepts_matched": response.concepts_matched,
                            "edges_created": response.edges_created,
                            "errors": response.errors
                        },
                        outcome=AuditOutcome.SUCCESS.value if not response.errors else AuditOutcome.ERROR.value
                    )

                    # Commit the transaction
                    conn.commit()
                    logger.info(
                        f"Batch committed: {response.concepts_created} concepts, "
                        f"{response.edges_created} edges"
                    )

                except Exception as e:
                    # Rollback on any error
                    conn.rollback()
                    logger.error(f"Batch rolled back due to error: {e}")
                    response.errors.append(f"Transaction rolled back: {str(e)}")
                    raise

        finally:
            # Always return connection to pool
            conn.autocommit = True
            self.age_client.pool.putconn(conn)

        return response

    async def _generate_embeddings(
        self,
        concepts: List[BatchConceptCreate]
    ) -> Dict[str, List[float]]:
        """
        Generate embeddings for all concepts.

        Args:
            concepts: List of concepts to generate embeddings for

        Returns:
            Dict mapping label -> embedding
        """
        embeddings = {}
        for concept in concepts:
            result = self.embedding_worker.generate_concept_embedding(concept.label)
            if result.get("success"):
                embeddings[concept.label] = result.get("embedding", [])
            else:
                logger.error(f"Failed to generate embedding for '{concept.label}'")
        return embeddings

    async def _create_concepts_in_transaction(
        self,
        cur,
        request: BatchCreateRequest,
        embeddings: Dict[str, List[float]],
        response: BatchResponse,
        user_id: Optional[int]
    ) -> Dict[str, str]:
        """
        Create concepts within the transaction.

        Args:
            cur: Database cursor
            request: Batch request
            embeddings: Pre-generated embeddings
            response: Response to populate
            user_id: User performing the operation

        Returns:
            Dict mapping label -> concept_id
        """
        label_to_id = {}

        for concept in request.concepts:
            try:
                embedding = embeddings.get(concept.label)
                if not embedding:
                    response.errors.append(f"No embedding for concept '{concept.label}'")
                    response.concept_results.append(BatchItemResult(
                        label=concept.label,
                        status="error",
                        error="No embedding generated"
                    ))
                    continue

                # Check for matching concept if mode is auto
                matched_id = None
                if request.matching_mode == MatchingMode.AUTO:
                    matched_id = await self._find_matching_concept_in_transaction(
                        cur, embedding, request.ontology
                    )

                if matched_id:
                    label_to_id[concept.label] = matched_id
                    response.concepts_matched += 1
                    response.concept_results.append(BatchItemResult(
                        label=concept.label,
                        status="matched",
                        id=matched_id
                    ))
                    continue

                # Create new concept
                concept_id = f"c_{uuid4().hex[:12]}"

                # Create synthetic source for provenance
                source_id = await self._create_synthetic_source_in_transaction(
                    cur,
                    ontology=request.ontology,
                    concept_label=concept.label,
                    creation_method=request.creation_method.value,
                    user_id=user_id
                )

                # Create concept node
                await self._create_concept_node_in_transaction(
                    cur,
                    concept_id=concept_id,
                    label=concept.label,
                    description=concept.description or "",
                    embedding=embedding,
                    search_terms=concept.search_terms or [],
                    ontology=request.ontology,
                    creation_method=request.creation_method.value
                )

                # Link concept to source
                await self._link_concept_to_source_in_transaction(cur, concept_id, source_id)

                label_to_id[concept.label] = concept_id
                response.concepts_created += 1
                response.concept_results.append(BatchItemResult(
                    label=concept.label,
                    status="created",
                    id=concept_id
                ))

            except Exception as e:
                logger.error(f"Error creating concept '{concept.label}': {e}")
                response.errors.append(f"Concept '{concept.label}': {str(e)}")
                response.concept_results.append(BatchItemResult(
                    label=concept.label,
                    status="error",
                    error=str(e)
                ))
                raise  # Re-raise to trigger rollback

        return label_to_id

    async def _create_edges_in_transaction(
        self,
        cur,
        request: BatchCreateRequest,
        label_to_id: Dict[str, str],
        response: BatchResponse
    ) -> None:
        """
        Create edges within the transaction.

        Args:
            cur: Database cursor
            request: Batch request
            label_to_id: Map of concept labels to IDs
            response: Response to populate
        """
        for edge in request.edges:
            try:
                # Resolve labels to IDs
                from_id = label_to_id.get(edge.from_label)
                to_id = label_to_id.get(edge.to_label)

                # If not in current batch, try to find existing concept
                if not from_id:
                    from_id = await self._find_concept_by_label_in_transaction(
                        cur, edge.from_label, request.ontology
                    )
                if not to_id:
                    to_id = await self._find_concept_by_label_in_transaction(
                        cur, edge.to_label, request.ontology
                    )

                if not from_id:
                    raise ValueError(f"Source concept not found: '{edge.from_label}'")
                if not to_id:
                    raise ValueError(f"Target concept not found: '{edge.to_label}'")

                # Create edge
                edge_id = f"e_{uuid4().hex[:12]}"
                await self._create_edge_in_transaction(
                    cur,
                    edge_id=edge_id,
                    from_id=from_id,
                    to_id=to_id,
                    relationship_type=edge.relationship_type,
                    category=edge.category.value,
                    confidence=edge.confidence
                )

                response.edges_created += 1
                response.edge_results.append(BatchItemResult(
                    label=f"{edge.from_label} -> {edge.to_label}",
                    status="created",
                    id=edge_id
                ))

            except Exception as e:
                logger.error(f"Error creating edge {edge.from_label} -> {edge.to_label}: {e}")
                response.errors.append(f"Edge '{edge.from_label}' -> '{edge.to_label}': {str(e)}")
                response.edge_results.append(BatchItemResult(
                    label=f"{edge.from_label} -> {edge.to_label}",
                    status="error",
                    error=str(e)
                ))
                raise  # Re-raise to trigger rollback

    # ========================================================================
    # Low-level database operations (within transaction)
    # ========================================================================

    async def _find_matching_concept_in_transaction(
        self,
        cur,
        embedding: List[float],
        ontology: str
    ) -> Optional[str]:
        """Find matching concept by embedding similarity."""
        escaped_ontology = _escape_cypher_string(ontology)
        # Use cosine similarity to find matches
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                MATCH (c:Concept)
                WHERE c.ontology = '{escaped_ontology}'
                RETURN c.concept_id as concept_id, c.embedding as embedding
            $$) as (concept_id agtype, embedding agtype);
        """
        cur.execute(query)
        results = cur.fetchall()

        best_match = None
        best_similarity = self.MATCH_THRESHOLD

        for row in results:
            concept_id = self.age_client._parse_agtype(row['concept_id'])
            stored_embedding = self.age_client._parse_agtype(row['embedding'])
            if stored_embedding:
                similarity = self._cosine_similarity(embedding, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = concept_id

        return best_match

    async def _find_concept_by_label_in_transaction(
        self,
        cur,
        label: str,
        ontology: str
    ) -> Optional[str]:
        """Find concept by label in ontology."""
        escaped_label = _escape_cypher_string(label)
        escaped_ontology = _escape_cypher_string(ontology)
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                MATCH (c:Concept)
                WHERE c.label = '{escaped_label}' AND c.ontology = '{escaped_ontology}'
                RETURN c.concept_id as concept_id
            $$) as (concept_id agtype);
        """
        cur.execute(query)
        result = cur.fetchone()
        if result:
            return self.age_client._parse_agtype(result['concept_id'])
        return None

    async def _create_synthetic_source_in_transaction(
        self,
        cur,
        ontology: str,
        concept_label: str,
        creation_method: str,
        user_id: Optional[int]
    ) -> str:
        """Create synthetic source node for provenance."""
        source_id = f"src_{uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        escaped_label = _escape_cypher_string(concept_label)
        escaped_ontology = _escape_cypher_string(ontology)
        escaped_method = _escape_cypher_string(creation_method)
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                CREATE (s:Source {{
                    source_id: '{source_id}',
                    document_name: 'synthetic:{escaped_method}',
                    paragraph_number: 0,
                    chunk_index: 0,
                    full_text: 'Manually created concept: {escaped_label}',
                    content_type: 'synthetic',
                    ontology: '{escaped_ontology}',
                    created_at: '{timestamp}',
                    created_by: '{user_id or "system"}'
                }})
                RETURN s.source_id as source_id
            $$) as (source_id agtype);
        """
        cur.execute(query)
        return source_id

    async def _create_concept_node_in_transaction(
        self,
        cur,
        concept_id: str,
        label: str,
        description: str,
        embedding: List[float],
        search_terms: List[str],
        ontology: str,
        creation_method: str
    ) -> None:
        """Create concept node in graph."""
        escaped_label = _escape_cypher_string(label)
        escaped_desc = _escape_cypher_string(description)
        escaped_ontology = _escape_cypher_string(ontology)
        escaped_method = _escape_cypher_string(creation_method)
        embedding_str = json.dumps(embedding)
        search_terms_str = json.dumps(search_terms)
        timestamp = datetime.now(timezone.utc).isoformat()

        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                CREATE (c:Concept {{
                    concept_id: '{concept_id}',
                    label: '{escaped_label}',
                    description: '{escaped_desc}',
                    embedding: {embedding_str},
                    search_terms: {search_terms_str},
                    ontology: '{escaped_ontology}',
                    creation_method: '{escaped_method}',
                    created_at: '{timestamp}'
                }})
                RETURN c.concept_id as concept_id
            $$) as (concept_id agtype);
        """
        cur.execute(query)

    async def _link_concept_to_source_in_transaction(
        self,
        cur,
        concept_id: str,
        source_id: str
    ) -> None:
        """Link concept to source via Instance node."""
        instance_id = f"i_{uuid4().hex[:12]}"

        # Create Instance node
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                CREATE (i:Instance {{
                    instance_id: '{instance_id}',
                    concept_id: '{concept_id}',
                    source_id: '{source_id}'
                }})
                RETURN i.instance_id as instance_id
            $$) as (instance_id agtype);
        """
        cur.execute(query)

        # Create EVIDENCED_BY relationship (Concept -> Instance)
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                MATCH (c:Concept {{concept_id: '{concept_id}'}}),
                      (i:Instance {{instance_id: '{instance_id}'}})
                CREATE (c)-[:EVIDENCED_BY]->(i)
                RETURN c.concept_id as concept_id
            $$) as (concept_id agtype);
        """
        cur.execute(query)

        # Create FROM_SOURCE relationship (Instance -> Source)
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                MATCH (i:Instance {{instance_id: '{instance_id}'}}),
                      (s:Source {{source_id: '{source_id}'}})
                CREATE (i)-[:FROM_SOURCE]->(s)
                RETURN i.instance_id as instance_id
            $$) as (instance_id agtype);
        """
        cur.execute(query)

    async def _create_edge_in_transaction(
        self,
        cur,
        edge_id: str,
        from_id: str,
        to_id: str,
        relationship_type: str,
        category: str,
        confidence: float
    ) -> None:
        """Create edge between concepts."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Normalize relationship type (uppercase, no spaces, alphanumeric only)
        normalized_rel_type = _normalize_relationship_type(relationship_type)
        escaped_category = _escape_cypher_string(category)

        # Create dynamic relationship type
        query = f"""
            SELECT * FROM cypher('{self.age_client.graph_name}', $$
                MATCH (from:Concept {{concept_id: '{from_id}'}}),
                      (to:Concept {{concept_id: '{to_id}'}})
                CREATE (from)-[r:{normalized_rel_type} {{
                    edge_id: '{edge_id}',
                    category: '{escaped_category}',
                    confidence: {confidence},
                    source: 'api_creation',
                    created_at: '{timestamp}'
                }}]->(to)
                RETURN r
            $$) as (r agtype);
        """
        cur.execute(query)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)
