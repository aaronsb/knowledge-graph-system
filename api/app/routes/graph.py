"""
Graph Routes - Batch operations (ADR-089 Phase 1b).

Provides bulk graph operations with transaction support.
"""

from fastapi import APIRouter, HTTPException, Depends, status
import logging

from ..models.graph import BatchCreateRequest, BatchResponse
from ..models.auth import UserInDB
from ..dependencies.auth import require_scope
from ..services.batch_service import BatchService
from .database import get_age_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


def get_batch_service() -> BatchService:
    """Get BatchService instance."""
    age_client = get_age_client()
    return BatchService(age_client)


@router.post(
    "/batch",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch create concepts and edges"
)
async def create_batch(
    request: BatchCreateRequest,
    current_user: UserInDB = Depends(require_scope("kg:import"))
):
    """
    Create multiple concepts and edges in a single transaction.

    All operations are atomic - if any operation fails, the entire
    batch is rolled back.

    **Concepts** are created first, then **edges** are created using
    the label-to-ID mapping from the concepts.

    **Edge Label Resolution:**
    - Edges reference concepts by label, not ID
    - Labels are first matched against concepts in the same batch
    - If not found, existing concepts in the ontology are searched

    **Matching Modes:**
    - `auto`: Match existing concepts by embedding similarity, create if no match
    - `force_create`: Always create new concepts, skip matching

    **Example Request:**
    ```json
    {
      "ontology": "ai-research",
      "matching_mode": "auto",
      "concepts": [
        {"label": "Machine Learning", "description": "Learning from data"},
        {"label": "Neural Networks", "description": "Brain-inspired computation"}
      ],
      "edges": [
        {
          "from_label": "Neural Networks",
          "to_label": "Machine Learning",
          "relationship_type": "IS_TECHNIQUE_IN"
        }
      ]
    }
    ```

    Requires `kg:import` scope.
    """
    service = get_batch_service()

    try:
        response = await service.execute_batch(
            request=request,
            user_id=current_user.id if current_user else None
        )

        # If there were errors and nothing was created, return error status
        if response.errors and response.concepts_created == 0 and response.edges_created == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Batch creation failed",
                    "errors": response.errors
                }
            )

        return response

    except HTTPException:
        # Re-raise HTTPException as-is (don't convert to 500)
        raise
    except ValueError as e:
        logger.error(f"Batch validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Batch execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch execution failed: {str(e)}"
        )
