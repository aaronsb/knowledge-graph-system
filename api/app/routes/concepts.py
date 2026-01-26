"""
Concept Routes - Deterministic concept CRUD (ADR-089).

Thin HTTP layer that delegates to ConceptService.
Handles:
- Request/response formatting
- OAuth scope validation
- Error responses
"""

from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional
import logging

from ..models.concepts import (
    ConceptCreate,
    ConceptUpdate,
    ConceptResponse,
    ConceptListResponse,
    CreationMethod,
)
from ..models.auth import UserInDB
from ..dependencies.auth import get_current_user
from ..services.concept_service import get_concept_service
from .database import get_age_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.post(
    "",
    response_model=ConceptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a concept"
)
async def create_concept(
    request: ConceptCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a new concept or match to an existing one.

    **Matching Modes:**
    - `auto`: Match existing concepts by embedding similarity, create if no match
    - `force_create`: Always create new concept, skip matching
    - `match_only`: Only link to existing concept, fail if no match found

    **Creation Methods:**
    - `api`: Direct API call
    - `cli`: CLI tool
    - `mcp`: MCP server
    - `workstation`: Web workstation
    - `import`: Foreign graph import

    Requires `kg:write` scope.
    """
    # TODO: Check kg:write scope once OAuth scopes are implemented (Task #6)

    age_client = get_age_client()
    service = get_concept_service(age_client)

    try:
        result = await service.create_concept(
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
        logger.error(f"Failed to create concept: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create concept"
        )


@router.get(
    "",
    response_model=ConceptListResponse,
    summary="List concepts"
)
async def list_concepts(
    ontology: Optional[str] = Query(None, description="Filter by ontology"),
    label_contains: Optional[str] = Query(None, description="Filter by label substring"),
    creation_method: Optional[CreationMethod] = Query(None, description="Filter by creation method"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List concepts with optional filtering.

    **Filters:**
    - `ontology`: Filter by ontology/collection
    - `label_contains`: Filter by label substring (case-sensitive)
    - `creation_method`: Filter by how concept was created

    **Pagination:**
    - `offset`: Number to skip
    - `limit`: Maximum to return (1-500)

    Requires `kg:read` scope.
    """
    age_client = get_age_client()
    service = get_concept_service(age_client)

    try:
        result = await service.list_concepts(
            ontology=ontology,
            label_contains=label_contains,
            creation_method=creation_method,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list concepts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list concepts"
        )


@router.get(
    "/{concept_id}",
    response_model=ConceptResponse,
    summary="Get a concept"
)
async def get_concept(
    concept_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get a single concept by ID.

    Requires `kg:read` scope.
    """
    age_client = get_age_client()
    service = get_concept_service(age_client)

    try:
        result = await service._get_concept_response(concept_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get concept: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get concept"
        )


@router.patch(
    "/{concept_id}",
    response_model=ConceptResponse,
    summary="Update a concept"
)
async def update_concept(
    concept_id: str,
    request: ConceptUpdate,
    regenerate_embedding: bool = Query(
        True,
        description="Regenerate embedding if label changes"
    ),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Update an existing concept (partial update).

    Only provided fields are updated. If label changes and
    `regenerate_embedding=true`, the embedding is regenerated.

    Requires `kg:edit` scope.
    """
    # TODO: Check kg:edit scope once OAuth scopes are implemented (Task #6)

    age_client = get_age_client()
    service = get_concept_service(age_client)

    try:
        result = await service.update_concept(
            concept_id=concept_id,
            request=request,
            regenerate_embedding=regenerate_embedding
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
        logger.error(f"Failed to update concept: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update concept"
        )


@router.delete(
    "/{concept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a concept"
)
async def delete_concept(
    concept_id: str,
    cascade: bool = Query(
        False,
        description="Also delete orphaned synthetic sources"
    ),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Delete a concept and its relationships.

    If `cascade=true`, also deletes orphaned synthetic source nodes
    that were created for this concept.

    Requires `kg:edit` scope.
    """
    # TODO: Check kg:edit scope once OAuth scopes are implemented (Task #6)

    age_client = get_age_client()
    service = get_concept_service(age_client)

    try:
        await service.delete_concept(concept_id=concept_id, cascade=cascade)
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
        logger.error(f"Failed to delete concept: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete concept"
        )
