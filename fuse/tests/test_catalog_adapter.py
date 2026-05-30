"""Tests for the catalog facade adapter (ADR-501).

Pure mapping logic between /catalog/children responses and the shapes the FUSE
inode layer needs. No pyfuse3 / httpx — these run anywhere.
"""

from kg_fuse import catalog_adapter as A


class TestOntologyEntries:
    def test_maps_nodes_to_descriptors(self):
        resp = {
            "nodes": [
                {"kind": "ontology", "id": "ont_1", "name": "Physics", "child_count": 3},
                {"kind": "ontology", "id": "ont_2", "name": "Bio", "child_count": 0},
            ]
        }
        out = A.ontology_entries(resp)
        assert out == [
            {"name": "Physics", "ontology_id": "ont_1", "child_count": 3},
            {"name": "Bio", "ontology_id": "ont_2", "child_count": 0},
        ]

    def test_skips_nodes_without_id(self):
        resp = {"nodes": [{"kind": "ontology", "id": None, "name": "ghost"}]}
        assert A.ontology_entries(resp) == []

    def test_falls_back_to_id_when_name_missing(self):
        resp = {"nodes": [{"kind": "ontology", "id": "ont_x"}]}
        assert A.ontology_entries(resp)[0]["name"] == "ont_x"

    def test_empty_and_none(self):
        assert A.ontology_entries({}) == []
        assert A.ontology_entries(None) == []


class TestNameToId:
    def test_builds_map(self):
        resp = {
            "nodes": [
                {"id": "ont_1", "name": "Physics"},
                {"id": "ont_2", "name": "Bio"},
            ]
        }
        assert A.ontology_name_to_id(resp) == {"Physics": "ont_1", "Bio": "ont_2"}

    def test_first_wins_on_duplicate_name(self):
        resp = {
            "nodes": [
                {"id": "ont_1", "name": "Dup"},
                {"id": "ont_2", "name": "Dup"},
            ]
        }
        assert A.ontology_name_to_id(resp) == {"Dup": "ont_1"}


class TestDocumentEntries:
    def test_maps_documents(self):
        resp = {
            "nodes": [
                {"kind": "document", "id": "sha256:abc", "name": "paper.md", "content_type": "document"},
                {"kind": "document", "id": "sha256:img", "name": "fig.png", "content_type": "image"},
            ]
        }
        out = A.document_entries(resp)
        assert out[0] == {"filename": "paper.md", "document_id": "sha256:abc", "content_type": "document"}
        assert out[1]["content_type"] == "image"

    def test_content_type_defaults_to_document(self):
        resp = {"nodes": [{"kind": "document", "id": "d1", "name": "x"}]}
        assert A.document_entries(resp)[0]["content_type"] == "document"

    def test_skips_documents_without_id(self):
        resp = {"nodes": [{"kind": "document", "id": "", "name": "x"}]}
        assert A.document_entries(resp) == []

    def test_filename_falls_back_to_id(self):
        resp = {"nodes": [{"kind": "document", "id": "sha256:zzz"}]}
        assert A.document_entries(resp)[0]["filename"] == "sha256:zzz"


class TestIsImage:
    def test_image(self):
        assert A.is_image("image") is True

    def test_non_image(self):
        assert A.is_image("document") is False
        assert A.is_image(None) is False
