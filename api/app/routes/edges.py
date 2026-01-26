"""
Edge Routes - Deterministic edge CRUD (ADR-089).

Thin HTTP layer that delegates to EdgeService.
Handles:
- Request/response formatting
- OAuth scope validation
- Error responses
"""

from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional
import logging

from ..models.edges import (
    EdgeCreate,
    EdgeUpdate,
    EdgeResponse,
    EdgeListResponse,
    EdgeSource,
    RelationshipCategory,
)
from ..models.auth import UserInDB
from ..dependencies.auth import require_scope
from ..services.edge_service import get_edge_service
from .database import get_age_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/edges", tags=["edges"])


@router.post(
    "",
    response_model=EdgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an edge"
)
async def create_edge(
    request: EdgeCreate,
    current_user: UserInDB = Depends(require_scope("kg:write"))
):
    """
    Create a new edge (relationship) between two concepts.

    The edge connects a source concept to a target concept with a
    typed relationship. Both concepts must already exist.

    **Relationship Types:**
    Common types include IMPLIES, SUPPORTS, CONTRADICTS, CAUSES,
    ENABLES, REQUIRES, etc. Type is normalized to uppercase.

    **Categories:**
    - `logical_truth`: Logical implications
    - `causal`: Cause-effect relationships
    - `structural`: Part-whole, hierarchy
    - `temporal`: Time-based relationships
    - `comparative`: Similarity, difference
    - `functional`: Purpose, capability
    - `definitional`: Definition, classification

    Requires `kg:write` scope.
    """

    age_client = get_age_client()
    service = get_edge_service(age_client)

    try:
        result = await service.create_edge(
            request=request,
            user_id=str(current_user.id) if current_user else None
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create edge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create edge"
        )


@router.get(
    "",
    response_model=EdgeListResponse,
    summary="List edges"
)
async def list_edges(
    from_concept_id: Optional[str] = Query(None, description="Filter by source concept"),
    to_concept_id: Optional[str] = Query(None, description="Filter by target concept"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    category: Optional[RelationshipCategory] = Query(None, description="Filter by category"),
    source: Optional[EdgeSource] = Query(None, description="Filter by creation source"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    current_user: UserInDB = Depends(require_scope("kg:read"))
):
    """
    List edges with optional filtering.

    **Filters:**
    - `from_concept_id`: Edges starting from this concept
    - `to_concept_id`: Edges ending at this concept
    - `relationship_type`: Edges of this type (e.g., IMPLIES)
    - `category`: Edges in this semantic category
    - `source`: Edges created by this method

    **Pagination:**
    - `offset`: Number to skip
    - `limit`: Maximum to return (1-500)

    Requires `kg:read` scope.
    """
    age_client = get_age_client()
    service = get_edge_service(age_client)

    try:
        result = await service.list_edges(
            from_concept_id=from_concept_id,
            to_concept_id=to_concept_id,
            relationship_type=relationship_type,
            category=category,
            source=source,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list edges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list edges"
        )


@router.patch(
    "/{from_concept_id}/{relationship_type}/{to_concept_id}",
    response_model=EdgeResponse,
    summary="Update an edge"
)
async def update_edge(
    from_concept_id: str,
    relationship_type: str,
    to_concept_id: str,
    request: EdgeUpdate,
    current_user: UserInDB = Depends(require_scope("kg:edit"))
):
    """
    Update an existing edge (partial update).

    Edges are identified by the (from, type, to) tuple.

    Only provided fields are updated. If `relationship_type` is changed,
    the old edge is deleted and a new one is created.

    Requires `kg:edit` scope.
    """

    age_client = get_age_client()
    service = get_edge_service(age_client)

    try:
        result = await service.update_edge(
            from_concept_id=from_concept_id,
            to_concept_id=to_concept_id,
            relationship_type=relationship_type,
            request=request
        )
        return result
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update edge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update edge"
        )


@router.delete(
    "/{from_concept_id}/{relationship_type}/{to_concept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an edge"
)
async def delete_edge(
    from_concept_id: str,
    relationship_type: str,
    to_concept_id: str,
    current_user: UserInDB = Depends(require_scope("kg:edit"))
):
    """
    Delete an edge.

    Edges are identified by the (from, type, to) tuple.

    Requires `kg:edit` scope.
    """

    age_client = get_age_client()
    service = get_edge_service(age_client)

    try:
        await service.delete_edge(
            from_concept_id=from_concept_id,
            to_concept_id=to_concept_id,
            relationship_type=relationship_type
        )
        return None  # 204 No Content
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete edge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete edge"
        )
