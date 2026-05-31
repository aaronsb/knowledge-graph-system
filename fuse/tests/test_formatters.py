"""Tests for markdown formatters — focused on the ontology-source fix.

Regression guard: the /documents/{id}/content response does not carry the
ontology, so format_document must use the path-derived ontology FUSE passes in
rather than rendering "unknown".
"""

from kg_fuse.config import TagsConfig
from kg_fuse.formatters import format_document


def _doc():
    return {"document_id": "sha256:abc", "filename": "doc.md", "chunks": []}


def test_ontology_arg_used_in_frontmatter_and_body():
    tags = TagsConfig(enabled=True)
    concepts = [{"name": "Convivial Tool"}]
    out = format_document(_doc(), concepts, tags, ontology="Conviviality of Knowledge Graphs")
    assert "ontology: Conviviality of Knowledge Graphs" in out
    assert "**Ontology:** Conviviality of Knowledge Graphs" in out
    assert "ontology: unknown" not in out


def test_ontology_arg_overrides_content_value():
    # Path-derived ontology wins even if the API response carried one.
    data = {**_doc(), "ontology": "stale-value"}
    out = format_document(data, [{"name": "X"}], TagsConfig(enabled=True), ontology="real-ontology")
    assert "ontology: real-ontology" in out
    assert "stale-value" not in out


def test_falls_back_to_data_then_unknown_when_no_arg():
    # No ontology arg: use data's value, else "unknown" (preserves old behavior).
    assert "ontology: from-data" in format_document(
        {**_doc(), "ontology": "from-data"}, [{"name": "X"}], TagsConfig(enabled=True)
    )
    assert "**Ontology:** unknown" in format_document(_doc(), [], TagsConfig(enabled=True))
