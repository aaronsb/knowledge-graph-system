"""
Tests for the catalog browse facade (ADR-501).

Covers:
- Pydantic models (CatalogNode / responses) and kind validation
- The pure DAG projection (_project): canonical-edge membership, multi-parent
  concepts, child_count derivation, sourceless/orphan accounting
- Row -> node mapping (JSON property parsing)
- Sort-field whitelist
- RBAC gating (no auth -> 401/403)

The projection tests are the important correctness coverage: they pin the DAG
invariant that a concept appearing in N documents produces N membership edges,
and that membership derives only from the canonical-edge fetch results (never
the Source.document string).
"""

import pytest
from fastapi.testclient import TestClient

from api.app.lib.catalog_facade import CatalogFacade, _SORT_SQL
from api.app.models.catalog import (
    CatalogNode,
    CatalogChildrenResponse,
    CatalogNodeResponse,
    CATALOG_SORT_FIELDS,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    from api.app.main import app
    return TestClient(app)


# ============================================================
# Models
# ============================================================

class TestCatalogModels:
    def test_catalog_node_minimal(self):
        node = CatalogNode(kind="ontology", id="ont_1", name="Philosophy")
        assert node.kind == "ontology"
        assert node.parent_id is None
        assert node.properties == {}

    def test_catalog_node_rejects_bad_kind(self):
        with pytest.raises(Exception):
            CatalogNode(kind="galaxy", id="x", name="x")

    def test_children_response_shape(self):
        resp = CatalogChildrenResponse(
            parent_id="ont_1",
            parent_kind="ontology",
            child_kind="document",
            nodes=[CatalogNode(kind="document", id="d1", name="paper.pdf",
                               parent_id="ont_1", child_count=12,
                               content_type="document")],
            total=1, limit=100, offset=0, query=None, stale=False,
        )
        assert resp.child_kind == "document"
        assert resp.nodes[0].content_type == "document"

    def test_node_response_carries_freshness(self):
        resp = CatalogNodeResponse(
            kind="concept", id="c1", name="Entropy", graph_epoch=42,
        )
        assert resp.graph_epoch == 42


# ============================================================
# Pure DAG projection
# ============================================================

class TestProjection:
    def test_ontology_child_count_is_doc_count(self):
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[{"id": "ont_1", "name": "Physics", "doc_count": 3}],
            documents=[], concepts=[], epoch=5,
        )
        onto = [n for n in nodes if n[0] == "ontology"][0]
        assert onto[1] == "ont_1"
        assert onto[4] == 3  # child_count slot
        assert onto[7] == 5  # epoch slot
        assert edges == []

    def test_document_links_to_parent_ontology(self):
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[{"id": "ont_1", "name": "Physics", "doc_count": 1}],
            documents=[{
                "id": "sha256:doc1", "name": "relativity.pdf",
                "content_type": "document", "concept_count": 7,
                "parent_ontology_ids": ["ont_1"],
            }],
            concepts=[], epoch=1,
        )
        doc = [n for n in nodes if n[0] == "document"][0]
        assert doc[4] == 7              # concept_count -> child_count
        assert doc[5] == "document"     # content_type
        assert ("ontology", "ont_1", "document", "sha256:doc1", 1) in edges
        assert stats["sourceless_docs"] == 0

    def test_concept_with_multiple_parents_yields_multiple_edges(self):
        """The DAG invariant: one concept, two documents -> two edges."""
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[],
            documents=[],
            concepts=[{
                "id": "c_entropy", "name": "Entropy",
                "parent_document_ids": ["sha256:docA", "sha256:docB"],
            }],
            epoch=9,
        )
        concept = [n for n in nodes if n[0] == "concept"][0]
        assert concept[4] == 0  # leaf: child_count 0
        concept_edges = [e for e in edges if e[3] == "c_entropy"]
        assert len(concept_edges) == 2
        assert ("document", "sha256:docA", "concept", "c_entropy", 9) in edges
        assert ("document", "sha256:docB", "concept", "c_entropy", 9) in edges

    def test_sourceless_document_counted_not_dropped(self):
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[],
            documents=[{"id": "d_orphan", "name": "loose.pdf",
                        "parent_ontology_ids": []}],
            concepts=[], epoch=1,
        )
        # Node still present (searchable) but no membership edge.
        assert any(n[1] == "d_orphan" for n in nodes)
        assert edges == []
        assert stats["sourceless_docs"] == 1

    def test_orphan_concept_counted_not_dropped(self):
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[], documents=[],
            concepts=[{"id": "c_loose", "name": "Floaty",
                       "parent_document_ids": []}],
            epoch=1,
        )
        assert any(n[1] == "c_loose" for n in nodes)
        assert edges == []
        assert stats["orphan_concepts"] == 1

    def test_rows_without_ids_skipped(self):
        nodes, edges, stats = CatalogFacade._project(
            ontologies=[{"id": None, "name": "ghost"}],
            documents=[{"id": "", "name": "ghost"}],
            concepts=[{"name": "ghost"}],
            epoch=1,
        )
        assert nodes == []
        assert edges == []

    def test_name_lower_is_populated(self):
        nodes, _, _ = CatalogFacade._project(
            ontologies=[{"id": "o1", "name": "MixedCase", "doc_count": 0}],
            documents=[], concepts=[], epoch=1,
        )
        assert nodes[0][3] == "mixedcase"  # name_lower slot


# ============================================================
# Mapping + whitelists
# ============================================================

class TestHelpers:
    def test_row_to_node_parses_json_string_properties(self):
        node = CatalogFacade._row_to_node(
            {"kind": "ontology", "node_id": "o1", "name": "X",
             "child_count": 2, "content_type": None,
             "properties": '{"lifecycle_state": "active"}'},
            parent_id=None,
        )
        assert node["properties"]["lifecycle_state"] == "active"
        assert node["id"] == "o1"

    def test_row_to_node_handles_dict_properties(self):
        node = CatalogFacade._row_to_node(
            {"kind": "concept", "node_id": "c1", "name": "Y",
             "child_count": 0, "content_type": None,
             "properties": {"a": 1}},
            parent_id="d1",
        )
        assert node["properties"] == {"a": 1}
        assert node["parent_id"] == "d1"

    def test_sort_whitelist_matches_documented_fields(self):
        # Every documented sort field must have a safe ORDER BY clause.
        for field in CATALOG_SORT_FIELDS:
            assert field in _SORT_SQL


# ============================================================
# RBAC gating
# ============================================================

class TestCatalogAuth:
    def test_children_requires_auth(self, client):
        resp = client.get("/catalog/children")
        assert resp.status_code in (401, 403)

    def test_node_requires_auth(self, client):
        resp = client.get("/catalog/node/ont_1")
        assert resp.status_code in (401, 403)
