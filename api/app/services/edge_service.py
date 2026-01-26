"""
Edge Service - Deterministic edge CRUD (ADR-089).

Orchestrates edge (relationship) creation/editing without LLM ingestion.
Delegates to AGEClient for graph operations.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone

from ..models.edges import (
    EdgeCreate,
    EdgeUpdate,
    EdgeResponse,
    EdgeListResponse,
    EdgeSource,
    RelationshipCategory,
)
from ..lib.age_client import AGEClient

logger = logging.getLogger(__name__)


class EdgeService:
    """
    Service for deterministic edge CRUD operations.

    Handles:
    - Edge creation between concepts
    - Validation that concepts exist
    - Edge updates and deletion
    - Edge listing with filters
    """

    def __init__(self, age_client: AGEClient):
        """
        Initialize with database client.

        Args:
            age_client: AGEClient instance for graph operations
        """
        self.age_client = age_client

    async def create_edge(
        self,
        request: EdgeCreate,
        user_id: Optional[str] = None
    ) -> EdgeResponse:
        """
        Create a new edge between two concepts.

        Args:
            request: Edge creation request
            user_id: ID of user creating the edge (for audit)

        Returns:
            EdgeResponse with created edge details

        Raises:
            ValueError: If source or target concept not found
        """
        logger.info(
            f"Creating edge: {request.from_concept_id} -[{request.relationship_type}]-> "
            f"{request.to_concept_id}"
        )

        # Verify both concepts exist
        from_exists = await self._concept_exists(request.from_concept_id)
        if not from_exists:
            raise ValueError(f"Source concept not found: {request.from_concept_id}")

        to_exists = await self._concept_exists(request.to_concept_id)
        if not to_exists:
            raise ValueError(f"Target concept not found: {request.to_concept_id}")

        # Normalize relationship type to uppercase
        rel_type = request.relationship_type.upper().replace(" ", "_")

        # Create the relationship
        created_at = datetime.now(timezone.utc).isoformat()

        success = self.age_client.create_concept_relationship(
            from_id=request.from_concept_id,
            to_id=request.to_concept_id,
            rel_type=rel_type,
            category=request.category.value,
            confidence=request.confidence,
            created_by=user_id,
            source=request.source.value,
            created_at=created_at
        )

        if not success:
            raise ValueError("Failed to create edge")

        # Generate edge ID from components (since AGE doesn't provide one)
        edge_id = f"e_{request.from_concept_id}_{rel_type}_{request.to_concept_id}"

        logger.info(f"Created edge: {edge_id}")

        return EdgeResponse(
            edge_id=edge_id,
            from_concept_id=request.from_concept_id,
            to_concept_id=request.to_concept_id,
            relationship_type=rel_type,
            category=request.category.value,
            confidence=request.confidence,
            source=request.source.value,
            created_at=created_at,
            created_by=user_id
        )

    async def _concept_exists(self, concept_id: str) -> bool:
        """Check if a concept exists."""
        query = """
        MATCH (c:Concept {concept_id: $concept_id})
        RETURN c.concept_id as id
        """
        try:
            result = self.age_client._execute_cypher(
                query,
                params={"concept_id": concept_id},
                fetch_one=True
            )
            return result is not None and result.get("id") is not None
        except Exception:
            return False

    async def list_edges(
        self,
        from_concept_id: Optional[str] = None,
        to_concept_id: Optional[str] = None,
        relationship_type: Optional[str] = None,
        category: Optional[RelationshipCategory] = None,
        source: Optional[EdgeSource] = None,
        offset: int = 0,
        limit: int = 50
    ) -> EdgeListResponse:
        """
        List edges with optional filtering.

        Args:
            from_concept_id: Filter by source concept
            to_concept_id: Filter by target concept
            relationship_type: Filter by relationship type
            category: Filter by category
            source: Filter by creation source
            offset: Pagination offset
            limit: Maximum results

        Returns:
            EdgeListResponse with matching edges
        """
        # Build query with filters
        where_clauses = []
        params = {"offset": offset, "limit": limit}

        if from_concept_id:
            where_clauses.append("c1.concept_id = $from_concept_id")
            params["from_concept_id"] = from_concept_id

        if to_concept_id:
            where_clauses.append("c2.concept_id = $to_concept_id")
            params["to_concept_id"] = to_concept_id

        if category:
            where_clauses.append("r.category = $category")
            params["category"] = category.value

        if source:
            where_clauses.append("r.source = $source")
            params["source"] = source.value

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build relationship type filter (can't parameterize in AGE)
        rel_match = "-[r]->" if not relationship_type else f"-[r:{relationship_type.upper()}]->"

        # Count total
        count_query = f"""
        MATCH (c1:Concept){rel_match}(c2:Concept)
        WHERE {where_clause}
        RETURN count(r) as total
        """

        count_result = self.age_client._execute_cypher(count_query, params=params, fetch_one=True)
        total = count_result.get("total", 0) if count_result else 0

        # Fetch page
        query = f"""
        MATCH (c1:Concept){rel_match}(c2:Concept)
        WHERE {where_clause}
        RETURN c1.concept_id as from_concept_id,
               c2.concept_id as to_concept_id,
               type(r) as relationship_type,
               r.category as category,
               r.confidence as confidence,
               r.source as source,
               r.created_at as created_at,
               r.created_by as created_by
        SKIP $offset
        LIMIT $limit
        """

        results = self.age_client._execute_cypher(query, params=params)

        edges = []
        for r in (results or []):
            from_id = r.get("from_concept_id", "")
            to_id = r.get("to_concept_id", "")
            rel_type = r.get("relationship_type", "UNKNOWN")

            edges.append(EdgeResponse(
                edge_id=f"e_{from_id}_{rel_type}_{to_id}",
                from_concept_id=from_id,
                to_concept_id=to_id,
                relationship_type=rel_type,
                category=r.get("category", "structural"),
                confidence=r.get("confidence", 1.0),
                source=r.get("source", "unknown"),
                created_at=r.get("created_at"),
                created_by=r.get("created_by")
            ))

        return EdgeListResponse(
            edges=edges,
            total=total,
            offset=offset,
            limit=limit
        )

    async def update_edge(
        self,
        from_concept_id: str,
        to_concept_id: str,
        relationship_type: str,
        request: EdgeUpdate
    ) -> EdgeResponse:
        """
        Update an existing edge.

        Note: In AGE, we identify edges by (from, to, type) tuple.
        Changing relationship_type requires delete + create.

        Args:
            from_concept_id: Source concept ID
            to_concept_id: Target concept ID
            relationship_type: Current relationship type
            request: Partial update fields

        Returns:
            Updated EdgeResponse

        Raises:
            ValueError: If edge not found or update fails
        """
        rel_type = relationship_type.upper()

        # Verify edge exists
        existing = await self._get_edge(from_concept_id, to_concept_id, rel_type)
        if not existing:
            raise ValueError(
                f"Edge not found: {from_concept_id} -[{rel_type}]-> {to_concept_id}"
            )

        # Build SET clause
        set_parts = []
        params = {
            "from_id": from_concept_id,
            "to_id": to_concept_id
        }

        if request.category is not None:
            set_parts.append("r.category = $category")
            params["category"] = request.category.value

        if request.confidence is not None:
            set_parts.append("r.confidence = $confidence")
            params["confidence"] = request.confidence

        # Handle relationship type change (requires delete + create)
        if request.relationship_type is not None:
            new_rel_type = request.relationship_type.upper().replace(" ", "_")
            if new_rel_type != rel_type:
                # Delete old edge
                await self.delete_edge(from_concept_id, to_concept_id, rel_type)
                # Create new edge with updated type
                return await self.create_edge(
                    EdgeCreate(
                        from_concept_id=from_concept_id,
                        to_concept_id=to_concept_id,
                        relationship_type=new_rel_type,
                        category=request.category or RelationshipCategory(existing.get("category", "structural")),
                        confidence=request.confidence or existing.get("confidence", 1.0),
                        source=EdgeSource(existing.get("source", "api_creation"))
                    )
                )

        if not set_parts:
            # Nothing to update
            return EdgeResponse(
                edge_id=f"e_{from_concept_id}_{rel_type}_{to_concept_id}",
                from_concept_id=from_concept_id,
                to_concept_id=to_concept_id,
                relationship_type=rel_type,
                category=existing.get("category", "structural"),
                confidence=existing.get("confidence", 1.0),
                source=existing.get("source", "unknown"),
                created_at=existing.get("created_at"),
                created_by=existing.get("created_by")
            )

        # Add updated timestamp
        set_parts.append("r.updated_at = $updated_at")
        params["updated_at"] = datetime.now(timezone.utc).isoformat()

        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})-[r:{rel_type}]->(c2:Concept {{concept_id: $to_id}})
        SET {", ".join(set_parts)}
        RETURN r
        """

        try:
            self.age_client._execute_cypher(query, params=params)
        except Exception as e:
            raise ValueError(f"Failed to update edge: {e}")

        # Fetch updated edge
        updated = await self._get_edge(from_concept_id, to_concept_id, rel_type)

        return EdgeResponse(
            edge_id=f"e_{from_concept_id}_{rel_type}_{to_concept_id}",
            from_concept_id=from_concept_id,
            to_concept_id=to_concept_id,
            relationship_type=rel_type,
            category=updated.get("category", "structural"),
            confidence=updated.get("confidence", 1.0),
            source=updated.get("source", "unknown"),
            created_at=updated.get("created_at"),
            created_by=updated.get("created_by")
        )

    async def delete_edge(
        self,
        from_concept_id: str,
        to_concept_id: str,
        relationship_type: str
    ) -> bool:
        """
        Delete an edge.

        Args:
            from_concept_id: Source concept ID
            to_concept_id: Target concept ID
            relationship_type: Relationship type

        Returns:
            True if deleted

        Raises:
            ValueError: If edge not found
        """
        rel_type = relationship_type.upper()

        # Verify edge exists
        existing = await self._get_edge(from_concept_id, to_concept_id, rel_type)
        if not existing:
            raise ValueError(
                f"Edge not found: {from_concept_id} -[{rel_type}]-> {to_concept_id}"
            )

        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})-[r:{rel_type}]->(c2:Concept {{concept_id: $to_id}})
        DELETE r
        """

        try:
            self.age_client._execute_cypher(
                query,
                params={"from_id": from_concept_id, "to_id": to_concept_id}
            )
            logger.info(f"Deleted edge: {from_concept_id} -[{rel_type}]-> {to_concept_id}")
            return True
        except Exception as e:
            raise ValueError(f"Failed to delete edge: {e}")

    async def _get_edge(
        self,
        from_concept_id: str,
        to_concept_id: str,
        relationship_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get edge by (from, to, type) tuple."""
        query = f"""
        MATCH (c1:Concept {{concept_id: $from_id}})-[r:{relationship_type}]->(c2:Concept {{concept_id: $to_id}})
        RETURN r.category as category,
               r.confidence as confidence,
               r.source as source,
               r.created_at as created_at,
               r.created_by as created_by
        """
        try:
            result = self.age_client._execute_cypher(
                query,
                params={"from_id": from_concept_id, "to_id": to_concept_id},
                fetch_one=True
            )
            return result if result else None
        except Exception:
            return None


def get_edge_service(age_client: AGEClient) -> EdgeService:
    """Factory function to create EdgeService."""
    return EdgeService(age_client)
