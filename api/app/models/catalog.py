"""
Catalog Browse Models (ADR-501)

Pydantic models for the catalog browse facade — a deterministic projection of
the ontology -> document -> concept hierarchy over the graph's canonical edges
(:SCOPED_BY, :HAS_SOURCE, :APPEARS).

These models are the surface-agnostic contract shared by CLI, MCP, web (ADR-700),
and FUSE (ADR-069). They are intentionally NOT the WorkingGraph of ADR-500 —
browse returns ordered rows, not a graph.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field


# The fixed hierarchy levels. Self-describing via `kind` so a generic recursive
# client (FUSE readdir, a tree widget) needs no per-level special-casing.
CatalogKind = Literal["ontology", "document", "concept"]

# Valid sort fields per the facade contract. "name" is the default everywhere;
# "child_count" and "created" are opt-in.
CATALOG_SORT_FIELDS = ["name", "child_count", "created"]


class CatalogNode(BaseModel):
    """A single node in the catalog hierarchy.

    Neutral shape consumed identically by every client surface. `properties`
    carries kind-specific extras only when requested via `?include=`, keeping the
    default listing lean (ADR-501 §1).
    """
    kind: CatalogKind = Field(..., description="Hierarchy level: ontology | document | concept")
    id: str = Field(..., description="Stable identifier (ontology_id, document_id, or concept_id)")
    name: str = Field(..., description="Display label")
    parent_id: Optional[str] = Field(
        None,
        description="Parent node id for breadcrumb/tree assembly (null at root level)",
    )
    child_count: Optional[int] = Field(
        None,
        description="Number of direct children (documents-in-ontology, concepts-in-document)",
    )
    content_type: Optional[str] = Field(
        None,
        description="Media type for document nodes: document | image | (future) audio | video",
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Kind-specific extras, populated only when requested via include=",
    )


class CatalogChildrenResponse(BaseModel):
    """Paginated listing of a node's children (GET /catalog/children)."""
    parent_id: Optional[str] = Field(
        None, description="The parent whose children are listed (null = root)"
    )
    parent_kind: Optional[CatalogKind] = Field(
        None, description="Kind of the parent node (null at root)"
    )
    child_kind: CatalogKind = Field(
        ..., description="Kind of the returned children"
    )
    nodes: List[CatalogNode] = Field(..., description="The child nodes for this page")
    total: int = Field(..., description="Total matching children (before pagination)")
    limit: int = Field(..., description="Page size used")
    offset: int = Field(..., description="Page offset used")
    query: Optional[str] = Field(
        None, description="Fragment filter applied to this listing, if any"
    )
    stale: bool = Field(
        False,
        description="True if served from a catalog index lagging the current graph epoch",
    )


class CatalogNodeResponse(CatalogNode):
    """Single node with full properties — the stat/detail call (GET /catalog/node/{id})."""
    graph_epoch: Optional[int] = Field(
        None, description="graph_change_counter at which this node's data was indexed"
    )
    indexed_at: Optional[datetime] = Field(
        None, description="When the catalog index last refreshed this node"
    )
