"""Unit tests for kg-backup/2 export assembly (ADR-102 P2).

Exercises the PURE ``DataExporter.build_kg_backup_v2()`` assembly — header
construction, dictionary interning, and the concept record→backup cascade —
and validates the result with the standalone offline validator
(``scripts/development/lint/lint_backup.py``). No database required.
"""
import importlib.util
from pathlib import Path

from api.lib.serialization import DataExporter, KG_BACKUP_FORMAT_VERSION

# The validator is a standalone script (not a package); import it by path.
_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "lint_backup", _REPO / "scripts" / "development" / "lint" / "lint_backup.py"
)
lint_backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_backup)


def _fixture_lists():
    """Minimal but representative primary-input lists for build_kg_backup_v2."""
    return dict(
        concepts=[
            {"concept_id": "c1", "label": "Alpha", "search_terms": ["a"],
             "embedding": [0.1, 0.2], "created_at_epoch": 1, "last_seen_epoch": 3},
            {"concept_id": "c2", "label": "Beta", "search_terms": [],
             "embedding": [0.3, 0.4], "created_at_epoch": 2, "last_seen_epoch": 2},
        ],
        sources=[
            {"source_id": "s1", "document": "Corpus", "file_path": "/a.txt",
             "paragraph": 1, "full_text": "alpha beta", "content_type": "text/plain"},
        ],
        instances=[
            {"instance_id": "i1", "quote": "alpha",
             "source_id": "s1", "created_at_event_id": 1},
        ],
        evidence=[
            {"concept_id": "c1", "instance_id": "i1"},
        ],
        relationships=[
            {"from": "c1", "to": "c2", "type": "IMPLIES",
             "properties": {"learned_id": "s1"}},
        ],
        vocabulary=[
            {"relationship_type": "IMPLIES", "description": "x", "category": "logical",
             "embedding_model": "test:embed@2"},
        ],
        embedding_profiles=[
            {"identity": "test:embed@2",
             "vector_space": "openai-3-small", "image_vector_space": None,
             "name": "default", "multimodal": False},
        ],
        epoch_kinds=[
            {"kind": "ingestion", "semantic_wallclock": True, "description": ""},
        ],
        graph_epochs=[
            {"event_id": 1, "occurred_at": "2026-06-01T00:00:00Z", "kind": "ingestion",
             "actor": "system", "counter_after": 10, "metadata": {}},
        ],
        schema_version=76,
    )


def test_build_validates_against_offline_validator():
    """A well-formed build passes lint_backup with no ERROR."""
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())
    result = lint_backup.validate_backup(obj)
    assert result.ok, [str(i) for i in result.errors]
    assert obj["header"]["format_version"] == KG_BACKUP_FORMAT_VERSION


def test_references_are_interned_by_index():
    """Repeated descriptors live in the header; bulk cites them by integer index."""
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())

    rel = obj["bulk"]["relationships"][0]
    assert isinstance(rel["type"], int)
    assert obj["header"]["relationship_vocabulary"][rel["type"]]["relationship_type"] == "IMPLIES"

    src = obj["bulk"]["sources"][0]
    assert isinstance(src["content_type"], int)
    assert obj["header"]["content_types"][src["content_type"]] == "text/plain"

    ep = obj["bulk"]["graph_epochs"][0]
    assert isinstance(ep["kind"], int)
    assert isinstance(ep["actor"], int)
    assert obj["header"]["actors"][ep["actor"]] == "system"


def test_concept_cascade_has_no_per_record_profile():
    """With one active profile, concepts inherit the backup default (no ref emitted)."""
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())
    assert obj["header"]["default_embedding_profile"] == 0
    for c in obj["bulk"]["concepts"]:
        assert "embedding_profile" not in c  # cascades to backup default


def test_epoch_fields_carried():
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())
    c = obj["bulk"]["concepts"][0]
    assert c["created_at_epoch"] == 1 and c["last_seen_epoch"] == 3
    assert obj["bulk"]["instances"][0]["created_at_event_id"] == 1


def test_instances_normalized_with_evidence_stream():
    """Instances are unique (no concept_id); Concept->Instance links are in evidence."""
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())
    inst = obj["bulk"]["instances"][0]
    assert "concept_id" not in inst
    assert inst["instance_id"] == "i1"
    ev = obj["bulk"]["evidence"][0]
    assert ev == {"concept_id": "c1", "instance_id": "i1"}


def test_dangling_evidence_link_is_flagged():
    """An evidence link to a missing concept/instance fails validation."""
    lists = _fixture_lists()
    lists["evidence"].append({"concept_id": "cX", "instance_id": "i1"})   # cX missing
    lists["evidence"].append({"concept_id": "c1", "instance_id": "iX"})   # iX missing
    result = lint_backup.validate_backup(DataExporter.build_kg_backup_v2(**lists))
    codes = {i.code for i in result.errors}
    assert "E_EVIDENCE_CONCEPT_MISSING" in codes
    assert "E_EVIDENCE_INSTANCE_MISSING" in codes


def test_no_derived_products_in_bulk():
    obj = DataExporter.build_kg_backup_v2(**_fixture_lists())
    for key in ("projections", "artifacts", "scores", "grounding", "catalog"):
        assert key not in obj["bulk"]


def test_dynamic_edge_type_missing_from_vocab_still_interns():
    """An edge type absent from the vocabulary table is appended to the header dict."""
    lists = _fixture_lists()
    lists["relationships"].append(
        {"from": "c2", "to": "c1", "type": "NOVEL_REL", "properties": {}}
    )
    obj = DataExporter.build_kg_backup_v2(**lists)
    result = lint_backup.validate_backup(obj)
    assert result.ok, [str(i) for i in result.errors]
    types = [v.get("relationship_type") for v in obj["header"]["relationship_vocabulary"]]
    assert "NOVEL_REL" in types
