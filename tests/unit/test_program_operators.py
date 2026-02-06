"""
GraphProgram Operator Tests (ADR-500 Phase 3).

Tests for the set-algebra operators (+, -, &, ?, !) that manipulate the
WorkingGraph during program execution. Each test exercises one operator
behavior from the specification (docs/language/specification.md Section 3).

These tests run WITHOUT Docker, database, or API server. Pure Python only.

Run:
    pytest tests/unit/test_program_operators.py -v
"""

import pytest

from api.app.models.program import WorkingGraph, RawNode, RawLink
from api.app.services.program_operators import (
    apply_union,
    apply_difference,
    apply_intersect,
    apply_optional,
    apply_assert,
    AssertionAbort,
    _enforce_dangling_invariant,
    _link_key,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _node(cid: str, label: str = "") -> RawNode:
    """Helper to create a RawNode."""
    return RawNode(concept_id=cid, label=label or cid)


def _link(from_id: str, to_id: str, rel: str = "IMPLIES") -> RawLink:
    """Helper to create a RawLink."""
    return RawLink(from_id=from_id, to_id=to_id, relationship_type=rel)


def _wg(nodes=None, links=None) -> WorkingGraph:
    """Helper to create a WorkingGraph."""
    return WorkingGraph(nodes=nodes or [], links=links or [])


# ---------------------------------------------------------------------------
# Dangling link invariant
# ---------------------------------------------------------------------------

class TestDanglingInvariant:

    def test_removes_links_with_missing_from(self):
        w = _wg(
            nodes=[_node("a")],
            links=[_link("a", "b"), _link("a", "a")],
        )
        removed = _enforce_dangling_invariant(w)
        assert removed == 1
        assert len(w.links) == 1
        assert w.links[0].to_id == "a"

    def test_removes_links_with_missing_to(self):
        w = _wg(
            nodes=[_node("a")],
            links=[_link("b", "a")],
        )
        removed = _enforce_dangling_invariant(w)
        assert removed == 1
        assert len(w.links) == 0

    def test_keeps_valid_links(self):
        w = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b"), _link("b", "a")],
        )
        removed = _enforce_dangling_invariant(w)
        assert removed == 0
        assert len(w.links) == 2

    def test_empty_graph_no_op(self):
        w = _wg()
        removed = _enforce_dangling_invariant(w)
        assert removed == 0


# ---------------------------------------------------------------------------
# + Union
# ---------------------------------------------------------------------------

class TestUnion:

    def test_into_empty_w(self):
        w = _wg()
        r = _wg(nodes=[_node("a"), _node("b")])
        n, l = apply_union(w, r)
        assert n == 2
        assert l == 0
        assert len(w.nodes) == 2

    def test_dedup_nodes_by_concept_id(self):
        w = _wg(nodes=[_node("a", "existing")])
        r = _wg(nodes=[_node("a", "new"), _node("b")])
        n, l = apply_union(w, r)
        assert n == 1  # only "b" added
        assert len(w.nodes) == 2
        # W wins on collision — label stays "existing"
        assert w.nodes[0].label == "existing"

    def test_dedup_links_by_compound_key(self):
        w = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b", "IMPLIES")],
        )
        r = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b", "IMPLIES"), _link("a", "b", "SUPPORTS")],
        )
        n, l = apply_union(w, r)
        assert l == 1  # only SUPPORTS added
        assert len(w.links) == 2

    def test_dangling_links_removed_after_union(self):
        w = _wg(nodes=[_node("a")])
        r = _wg(links=[_link("a", "missing")])
        n, l = apply_union(w, r)
        assert len(w.links) == 0


# ---------------------------------------------------------------------------
# - Difference
# ---------------------------------------------------------------------------

class TestDifference:

    def test_removes_matching_nodes(self):
        w = _wg(nodes=[_node("a"), _node("b"), _node("c")])
        r = _wg(nodes=[_node("b")])
        n, l = apply_difference(w, r)
        assert n == 1
        assert len(w.nodes) == 2
        ids = {n.concept_id for n in w.nodes}
        assert ids == {"a", "c"}

    def test_cascades_dangling_links(self):
        w = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b")],
        )
        r = _wg(nodes=[_node("b")])
        n, l = apply_difference(w, r)
        assert n == 1
        assert l == 1  # dangling link removed
        assert len(w.links) == 0

    def test_unknown_nodes_ignored(self):
        w = _wg(nodes=[_node("a")])
        r = _wg(nodes=[_node("z")])
        n, l = apply_difference(w, r)
        assert n == 0
        assert len(w.nodes) == 1

    def test_r_links_ignored(self):
        """Difference only considers R.nodes, not R.links."""
        w = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b")],
        )
        r = _wg(links=[_link("a", "b")])
        n, l = apply_difference(w, r)
        assert n == 0
        assert len(w.links) == 1  # untouched


# ---------------------------------------------------------------------------
# & Intersect
# ---------------------------------------------------------------------------

class TestIntersect:

    def test_keeps_overlap(self):
        w = _wg(nodes=[_node("a"), _node("b"), _node("c")])
        r = _wg(nodes=[_node("b"), _node("c"), _node("d")])
        n, l = apply_intersect(w, r)
        assert n == 1  # "a" removed
        ids = {n.concept_id for n in w.nodes}
        assert ids == {"b", "c"}

    def test_empty_r_clears_w(self):
        w = _wg(nodes=[_node("a"), _node("b")])
        r = _wg()
        n, l = apply_intersect(w, r)
        assert n == 2
        assert len(w.nodes) == 0

    def test_preserves_w_data(self):
        """Intersect keeps W's node data, not R's."""
        w = _wg(nodes=[_node("a", "w-label")])
        r = _wg(nodes=[_node("a", "r-label")])
        apply_intersect(w, r)
        assert w.nodes[0].label == "w-label"

    def test_dangling_links_removed(self):
        w = _wg(
            nodes=[_node("a"), _node("b")],
            links=[_link("a", "b")],
        )
        r = _wg(nodes=[_node("a")])
        n, l = apply_intersect(w, r)
        assert n == 1  # "b" removed
        assert l == 1  # dangling link removed
        assert len(w.links) == 0


# ---------------------------------------------------------------------------
# ? Optional
# ---------------------------------------------------------------------------

class TestOptional:

    def test_nonempty_applies_union(self):
        w = _wg(nodes=[_node("a")])
        r = _wg(nodes=[_node("b")])
        n, l = apply_optional(w, r)
        assert n == 1
        assert len(w.nodes) == 2

    def test_empty_is_noop(self):
        w = _wg(nodes=[_node("a")])
        r = _wg()
        n, l = apply_optional(w, r)
        assert n == 0
        assert l == 0
        assert len(w.nodes) == 1


# ---------------------------------------------------------------------------
# ! Assert
# ---------------------------------------------------------------------------

class TestAssert:

    def test_nonempty_applies_union(self):
        w = _wg(nodes=[_node("a")])
        r = _wg(nodes=[_node("b")])
        n, l = apply_assert(w, r, stmt_index=0)
        assert n == 1
        assert len(w.nodes) == 2

    def test_empty_raises_abort(self):
        w = _wg(nodes=[_node("a")])
        r = _wg()
        with pytest.raises(AssertionAbort) as exc_info:
            apply_assert(w, r, stmt_index=2)
        assert exc_info.value.statement == 2
        assert "empty result" in exc_info.value.reason


# ---------------------------------------------------------------------------
# Link key
# ---------------------------------------------------------------------------

class TestLinkKey:

    def test_compound_key(self):
        link = _link("a", "b", "IMPLIES")
        assert _link_key(link) == ("a", "IMPLIES", "b")

    def test_different_types_different_keys(self):
        l1 = _link("a", "b", "IMPLIES")
        l2 = _link("a", "b", "SUPPORTS")
        assert _link_key(l1) != _link_key(l2)
