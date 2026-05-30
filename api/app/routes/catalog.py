"""
Catalog browse endpoints (ADR-501).

A deterministic, hierarchical view of what is actually in the knowledge graph:
ontology -> document -> concept. Unlike semantic search (ADR-500 programs,
vector search), browse is structural and cheap — it answers "what's in here?"
rather than "what's similar to X?".

The hierarchy is fixed and self-describing via each node's `kind`, so a generic
recursive client (FUSE readdir, a web tree, the CLI) walks it without per-level
special-casing:

    root      -> ontology
    ontology  -> document
    document  -> concept   (leaf)

Membership is projected from the graph's canonical edges (:SCOPED_BY,
:HAS_SOURCE, :APPEARS), never from the denormalized Source.document string
(ADR-200). See CatalogFacade for the index/freshness model.
"""

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
import logging
from typing import Optional

from ..dependencies.auth import CurrentUser, require_permission
from ..models.catalog import (
    CatalogNode,
    CatalogChildrenResponse,
    CatalogNodeResponse,
    CATALOG_SORT_FIELDS,
)
from ..lib.catalog_facade import CatalogFacade
from api.app.lib.age_client import AGEClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/catalog", tags=["catalog"])

# Fixed parent-kind -> child-kind mapping. The only valid transitions.
_CHILD_OF = {None: "ontology", "ontology": "document", "document": "concept"}


def get_age_client() -> AGEClient:
    """Get an AGE client instance (per-request, closed in finally)."""
    return AGEClient()


@router.get(
    "/children",
    response_model=CatalogChildrenResponse,
    dependencies=[Depends(require_permission("catalog", "read"))],
)
async def list_children(
    current_user: CurrentUser,
    parent: Optional[str] = QueryParam(
        None, description="Parent node id. Omit (or empty) to list root ontologies."
    ),
    parent_kind: Optional[str] = QueryParam(
        None, description="Kind of the parent: ontology | document. Resolved automatically if omitted."
    ),
    q: Optional[str] = QueryParam(
        None, description="Fragment filter: case-insensitive substring match on child names."
    ),
    sort: str = QueryParam("name", description=f"Sort field: {', '.join(CATALOG_SORT_FIELDS)}"),
    limit: int = QueryParam(100, ge=1, le=1000),
    offset: int = QueryParam(0, ge=0),
):
    """
    List the children of a catalog node, or root ontologies when `parent` is omitted.

    **Authorization:** Requires `catalog:read` permission.

    Examples:
        GET /catalog/children                              -> all ontologies
        GET /catalog/children?parent=ont_abc&parent_kind=ontology   -> its documents
        GET /catalog/children?parent=sha256:...&parent_kind=document -> its concepts
        GET /catalog/children?q=neural                     -> ontologies matching "neural"
    """
    if sort not in CATALOG_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"Invalid sort field '{sort}'")

    parent = parent or None  # normalize empty string to None (root)

    client = get_age_client()
    try:
        facade = CatalogFacade(client)

        # Resolve parent_kind if a parent was given without one.
        if parent is not None and parent_kind is None:
            node = facade.get_node(parent)
            if node is None:
                raise HTTPException(status_code=404, detail=f"Catalog node '{parent}' not found")
            parent_kind = node["kind"]

        if parent_kind not in _CHILD_OF:
            # parent_kind == 'concept' (leaf) or an unknown kind.
            raise HTTPException(
                status_code=400,
                detail=f"Nodes of kind '{parent_kind}' have no children",
            )

        child_kind = _CHILD_OF[parent_kind]

        result = facade.list_children(
            parent_id=parent,
            parent_kind=parent_kind,
            child_kind=child_kind,
            q=q,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return CatalogChildrenResponse(
            parent_id=result["parent_id"],
            parent_kind=result["parent_kind"],
            child_kind=result["child_kind"],
            nodes=[CatalogNode(**n) for n in result["nodes"]],
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
            query=result["query"],
            stale=result["stale"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Catalog children listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Catalog listing failed: {str(e)}")
    finally:
        client.close()


@router.get(
    "/node/{node_id:path}",
    response_model=CatalogNodeResponse,
    dependencies=[Depends(require_permission("catalog", "read"))],
)
async def get_node(
    node_id: str,
    current_user: CurrentUser,
    kind: Optional[str] = QueryParam(
        None, description="Disambiguate kind if a node id collides across kinds."
    ),
):
    """
    Get a single catalog node's full metadata (the stat/detail call).

    **Authorization:** Requires `catalog:read` permission.

    `node_id` is a path param accepting slashes (document ids look like
    `sha256:...`). Example: GET /catalog/node/ont_abc123?kind=ontology
    """
    client = get_age_client()
    try:
        facade = CatalogFacade(client)
        node = facade.get_node(node_id, kind=kind)
        if node is None:
            raise HTTPException(status_code=404, detail=f"Catalog node '{node_id}' not found")
        return CatalogNodeResponse(**node)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Catalog node fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Catalog node fetch failed: {str(e)}")
    finally:
        client.close()
