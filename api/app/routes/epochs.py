"""
Epoch Routes (ADR-203)

Read-only endpoints for the graph epoch event log. Pairs with the
concept-lifetime endpoint in routes/concepts.py — both delegate to
EpochFacade (`age_client.epochs`).
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..models.auth import UserInDB
from ..dependencies.auth import require_permission
from .database import get_age_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epochs", tags=["epochs"])


@router.get(
    "",
    summary="List graph epoch events (ADR-203)",
)
async def list_epochs(
    kind: Optional[str] = Query(
        None,
        description="Filter to a specific event kind (ingestion, reasoning, breathing, edit)",
    ),
    since: Optional[str] = Query(
        None,
        description="ISO-8601 lower bound on occurred_at (UTC)",
    ),
    until: Optional[str] = Query(
        None,
        description="ISO-8601 upper bound on occurred_at (UTC)",
    ),
    actor: Optional[str] = Query(
        None,
        description="Filter by exact actor string",
    ),
    cursor: Optional[int] = Query(
        None,
        description="Pagination cursor — return events with event_id < cursor",
    ),
    limit: int = Query(50, ge=1, le=500, description="Max events per page"),
    current_user: UserInDB = Depends(require_permission("graph", "read")),
):
    """
    Cursor-paginated read of `kg_api.graph_epochs`.

    Events are returned most-recent-first. To page back through history,
    pass the previous response's `next_cursor` as `cursor`. When the
    response's `next_cursor` is null, no further pages exist for the
    current filter set.

    Filter semantics:
      - `kind` matches exact (no wildcards). Honest about the discriminator
        in ADR-203 §Decision: only some kinds make wall-clock semantically
        meaningful.
      - `since`/`until` apply to `occurred_at` regardless of `kind`.
      - `actor` matches exact.

    Requires `graph:read` permission.
    """
    age_client = get_age_client()
    try:
        return age_client.epochs.list_epochs(
            kind=kind,
            since=since,
            until=until,
            actor=actor,
            cursor=cursor,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"list_epochs failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list epochs",
        )
