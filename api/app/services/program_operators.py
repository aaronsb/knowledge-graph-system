"""
GraphProgram set-algebra operators (ADR-500 Phase 3).

Pure functions implementing the 5 operators (+, -, &, ?, !) over WorkingGraph.
Each operator takes W (mutable) and R (result set), mutates W in place, and
returns (nodes_affected, links_affected).

All operators enforce the dangling link invariant after application:
links whose from_id or to_id doesn't match any node's concept_id are removed.

Zero platform dependencies. Testable from bare pytest without Docker.
"""

from typing import Set, Tuple

from api.app.models.program import WorkingGraph, RawNode, RawLink


class AssertionAbort(Exception):
    """Raised when the ! operator encounters an empty result set."""

    def __init__(self, statement: int, reason: str):
        self.statement = statement
        self.reason = reason
        super().__init__(reason)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_id_set(nodes: list[RawNode]) -> Set[str]:
    """Extract the set of concept_ids from a node list."""
    return {n.concept_id for n in nodes}


def _link_key(link: RawLink) -> Tuple[str, str, str]:
    """Compound identity key for a link: (from_id, relationship_type, to_id)."""
    return (link.from_id, link.relationship_type, link.to_id)


def _enforce_dangling_invariant(w: WorkingGraph) -> int:
    """Remove links whose from_id or to_id is not in the node set.

    Returns the number of links removed.
    """
    node_ids = _node_id_set(w.nodes)
    before = len(w.links)
    w.links = [
        link for link in w.links
        if link.from_id in node_ids and link.to_id in node_ids
    ]
    return before - len(w.links)


def _is_nonempty(r: WorkingGraph) -> bool:
    """Check if a result set contains any data."""
    return len(r.nodes) > 0 or len(r.links) > 0


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

def apply_union(w: WorkingGraph, r: WorkingGraph) -> Tuple[int, int]:
    """+ operator: merge R into W, dedup by identity. W wins on collision."""
    existing_node_ids = _node_id_set(w.nodes)
    existing_link_keys = {_link_key(l) for l in w.links}

    nodes_added = 0
    for node in r.nodes:
        if node.concept_id not in existing_node_ids:
            w.nodes.append(node)
            existing_node_ids.add(node.concept_id)
            nodes_added += 1

    links_added = 0
    for link in r.links:
        key = _link_key(link)
        if key not in existing_link_keys:
            w.links.append(link)
            existing_link_keys.add(key)
            links_added += 1

    dangling_removed = _enforce_dangling_invariant(w)
    return nodes_added, links_added - dangling_removed


def apply_difference(w: WorkingGraph, r: WorkingGraph) -> Tuple[int, int]:
    """- operator: remove R.nodes from W by concept_id. Cascade dangling links."""
    remove_ids = _node_id_set(r.nodes)
    before_nodes = len(w.nodes)
    w.nodes = [n for n in w.nodes if n.concept_id not in remove_ids]
    nodes_removed = before_nodes - len(w.nodes)

    dangling_removed = _enforce_dangling_invariant(w)
    return nodes_removed, dangling_removed


def apply_intersect(w: WorkingGraph, r: WorkingGraph) -> Tuple[int, int]:
    """& operator: keep only W nodes whose concept_id is in R.nodes."""
    keep_ids = _node_id_set(r.nodes)
    before_nodes = len(w.nodes)
    w.nodes = [n for n in w.nodes if n.concept_id in keep_ids]
    nodes_removed = before_nodes - len(w.nodes)

    dangling_removed = _enforce_dangling_invariant(w)
    return nodes_removed, dangling_removed


def apply_optional(w: WorkingGraph, r: WorkingGraph) -> Tuple[int, int]:
    """? operator: if R non-empty, apply union. Else no-op."""
    if _is_nonempty(r):
        return apply_union(w, r)
    return 0, 0


def apply_assert(
    w: WorkingGraph, r: WorkingGraph, stmt_index: int
) -> Tuple[int, int]:
    """! operator: if R non-empty, apply union. Else raise AssertionAbort."""
    if not _is_nonempty(r):
        raise AssertionAbort(
            statement=stmt_index,
            reason="assertion failed: empty result",
        )
    return apply_union(w, r)


OPERATOR_MAP = {
    '+': apply_union,
    '-': apply_difference,
    '&': apply_intersect,
    '?': apply_optional,
    '!': apply_assert,
}
"""Maps operator characters to their implementation functions."""
