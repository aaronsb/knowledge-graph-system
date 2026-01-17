"""Tests for QueryStore."""

import pytest
from pathlib import Path
import tempfile

from kg_fuse.query_store import Query, QueryStore


class TestQuery:
    """Tests for Query dataclass."""

    def test_default_values(self):
        """Query should initialize with correct defaults."""
        q = Query(query_text="test")
        assert q.query_text == "test"
        assert q.threshold == 0.7
        assert q.limit == 50
        assert q.exclude == []
        assert q.union == []
        assert q.symlinks == []

    def test_mutable_defaults_not_shared(self):
        """Each Query instance should have its own lists."""
        q1 = Query(query_text="test1")
        q2 = Query(query_text="test2")
        q1.exclude.append("term")
        assert "term" in q1.exclude
        assert "term" not in q2.exclude

    def test_to_dict(self):
        """Query should serialize to dict correctly."""
        q = Query(query_text="test", threshold=0.8, limit=100)
        d = q.to_dict()
        assert d["query_text"] == "test"
        assert d["threshold"] == 0.8
        assert d["limit"] == 100


class TestQueryStore:
    """Tests for QueryStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a QueryStore with a temporary file."""
        return QueryStore(data_path=tmp_path / "queries.toml")

    def test_add_query(self, store):
        """Should add a query and retrieve it."""
        query = store.add_query("ontology1", "leadership")
        assert query.query_text == "leadership"
        assert store.is_query_dir("ontology1", "leadership")

    def test_add_query_custom_text(self, store):
        """Should use custom query text when provided."""
        query = store.add_query("ontology1", "dir", query_text="custom search")
        assert query.query_text == "custom search"

    def test_add_global_query(self, store):
        """Should handle global queries (ontology=None)."""
        query = store.add_query(None, "global-search")
        assert query.query_text == "global-search"
        assert store.is_query_dir(None, "global-search")
        # Should not match as ontology query
        assert not store.is_query_dir("global-search", "")

    def test_remove_query(self, store):
        """Should remove a query."""
        store.add_query("ont", "query1")
        store.add_query("ont", "query2")
        assert store.is_query_dir("ont", "query1")
        store.remove_query("ont", "query1")
        assert not store.is_query_dir("ont", "query1")
        assert store.is_query_dir("ont", "query2")

    def test_remove_query_removes_children(self, store):
        """Should remove nested children when removing parent."""
        store.add_query("ont", "parent")
        store.add_query("ont", "parent/child1")
        store.add_query("ont", "parent/child1/grandchild")
        store.add_query("ont", "parent/child2")
        store.remove_query("ont", "parent")
        assert not store.is_query_dir("ont", "parent")
        assert not store.is_query_dir("ont", "parent/child1")
        assert not store.is_query_dir("ont", "parent/child1/grandchild")
        assert not store.is_query_dir("ont", "parent/child2")

    def test_list_queries_under(self, store):
        """Should list immediate children only."""
        store.add_query("ont", "a")
        store.add_query("ont", "b")
        store.add_query("ont", "a/nested")
        store.add_query("ont", "a/nested/deep")

        children = store.list_queries_under("ont", "")
        assert sorted(children) == ["a", "b"]

        nested = store.list_queries_under("ont", "a")
        assert nested == ["nested"]

    def test_list_global_queries(self, store):
        """Should list global queries separately."""
        store.add_query(None, "global1")
        store.add_query(None, "global2")
        store.add_query("ont", "scoped")

        global_queries = store.list_queries_under(None, "")
        assert sorted(global_queries) == ["global1", "global2"]

    def test_get_query_chain(self, store):
        """Should return queries in hierarchy order."""
        store.add_query("ont", "leadership")
        store.add_query("ont", "leadership/communication")
        store.add_query("ont", "leadership/communication/feedback")

        chain = store.get_query_chain("ont", "leadership/communication/feedback")
        assert len(chain) == 3
        assert chain[0].query_text == "leadership"
        assert chain[1].query_text == "communication"
        assert chain[2].query_text == "feedback"

    def test_get_query_chain_partial(self, store):
        """Should handle missing intermediate queries."""
        store.add_query("ont", "a")
        store.add_query("ont", "a/b/c")  # b is missing

        chain = store.get_query_chain("ont", "a/b/c")
        assert len(chain) == 2
        assert chain[0].query_text == "a"
        assert chain[1].query_text == "c"

    def test_update_limit(self, store):
        """Should update limit within bounds."""
        store.add_query("ont", "test")
        store.update_limit("ont", "test", 200)
        assert store.get_query("ont", "test").limit == 200

        # Test clamping
        store.update_limit("ont", "test", 5000)
        assert store.get_query("ont", "test").limit == 1000

        store.update_limit("ont", "test", -5)
        assert store.get_query("ont", "test").limit == 1

    def test_update_threshold(self, store):
        """Should update threshold within 0.0-1.0."""
        store.add_query("ont", "test")
        store.update_threshold("ont", "test", 0.85)
        assert store.get_query("ont", "test").threshold == 0.85

        # Test clamping
        store.update_threshold("ont", "test", 1.5)
        assert store.get_query("ont", "test").threshold == 1.0

        store.update_threshold("ont", "test", -0.5)
        assert store.get_query("ont", "test").threshold == 0.0

    def test_add_exclude(self, store):
        """Should add unique exclude terms."""
        store.add_query("ont", "test")
        store.add_exclude("ont", "test", "noise")
        store.add_exclude("ont", "test", "spam")
        store.add_exclude("ont", "test", "noise")  # Duplicate

        excludes = store.get_query("ont", "test").exclude
        assert excludes == ["noise", "spam"]

    def test_add_union(self, store):
        """Should add unique union terms."""
        store.add_query("ont", "test")
        store.add_union("ont", "test", "related")
        store.add_union("ont", "test", "similar")

        unions = store.get_query("ont", "test").union
        assert unions == ["related", "similar"]

    def test_clear_exclude(self, store):
        """Should clear all exclude terms."""
        store.add_query("ont", "test")
        store.add_exclude("ont", "test", "a")
        store.add_exclude("ont", "test", "b")
        store.clear_exclude("ont", "test")
        assert store.get_query("ont", "test").exclude == []

    def test_clear_union(self, store):
        """Should clear all union terms."""
        store.add_query("ont", "test")
        store.add_union("ont", "test", "a")
        store.add_union("ont", "test", "b")
        store.clear_union("ont", "test")
        assert store.get_query("ont", "test").union == []

    def test_add_remove_symlink(self, store):
        """Should manage symlinks."""
        store.add_query(None, "test")
        store.add_symlink(None, "test", "ontology1")
        store.add_symlink(None, "test", "ontology2")

        symlinks = store.get_symlinks(None, "test")
        assert symlinks == ["ontology1", "ontology2"]

        store.remove_symlink(None, "test", "ontology1")
        symlinks = store.get_symlinks(None, "test")
        assert symlinks == ["ontology2"]

    def test_persistence(self, tmp_path):
        """Should persist and reload queries."""
        path = tmp_path / "queries.toml"

        # Create and populate
        store1 = QueryStore(data_path=path)
        store1.add_query("ont", "search1")
        store1.add_query("ont", "search1/nested")
        store1.update_limit("ont", "search1", 100)
        store1.add_exclude("ont", "search1", "noise")

        # Reload
        store2 = QueryStore(data_path=path)
        assert store2.is_query_dir("ont", "search1")
        assert store2.is_query_dir("ont", "search1/nested")
        q = store2.get_query("ont", "search1")
        assert q.limit == 100
        assert q.exclude == ["noise"]

    def test_nonexistent_query_returns_none(self, store):
        """Should return None for nonexistent queries."""
        assert store.get_query("ont", "missing") is None
        assert not store.is_query_dir("ont", "missing")

    def test_operations_on_nonexistent_return_false(self, store):
        """Operations on nonexistent queries should return False."""
        assert store.update_limit("ont", "missing", 100) is False
        assert store.update_threshold("ont", "missing", 0.5) is False
        assert store.add_exclude("ont", "missing", "term") is False
        assert store.add_union("ont", "missing", "term") is False
