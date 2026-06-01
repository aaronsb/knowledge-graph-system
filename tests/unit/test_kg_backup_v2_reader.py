"""Unit tests for KgBackupV2Reader — the kg-backup/2 read/de-intern layer (ADR-102 P3).

Pure and DB-free: feeds objects built by the pure ``DataExporter.build_kg_backup_v2``
through the reader and asserts de-interning, evidence grouping, external-dependency
detection, and single-path format negotiation (no v1 fallback).
"""
import pytest

from api.lib.serialization import DataExporter, KgBackupV2Reader


def _fixture_lists():
    """Minimal representative primary-input lists for build_kg_backup_v2."""
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
            {"instance_id": "i1", "quote": "alpha", "source_id": "s1", "created_at_event_id": 1},
        ],
        evidence=[
            {"concept_id": "c1", "instance_id": "i1"},
            {"concept_id": "c2", "instance_id": "i1"},   # M:N — one instance, two concepts
        ],
        relationships=[
            {"from": "c1", "to": "c2", "type": "IMPLIES", "properties": {"learned_id": "s1"}},
        ],
        vocabulary=[
            {"relationship_type": "IMPLIES", "description": "x", "category": "logical",
             "embedding_model": "openai:text-embedding-3-small@1536"},
        ],
        embedding_profiles=[
            {"identity": "openai:text-embedding-3-small@1536", "vector_space": "openai-3-small",
             "image_vector_space": None, "name": "default", "multimodal": False},
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


def _build(**overrides):
    lists = _fixture_lists()
    lists.update(overrides)
    return DataExporter.build_kg_backup_v2(**lists)


def test_relationship_type_de_interned():
    """Bulk relationships carry an integer type index; the reader yields the label."""
    obj = _build()
    assert isinstance(obj["bulk"]["relationships"][0]["type"], int)  # interned on disk
    rels = list(KgBackupV2Reader(obj).relationships())
    assert rels[0]["type"] == "IMPLIES"
    assert rels[0]["properties"] == {"learned_id": "s1"}


def test_content_type_de_interned():
    obj = _build()
    assert isinstance(obj["bulk"]["sources"][0]["content_type"], int)
    src = list(KgBackupV2Reader(obj).sources())[0]
    assert src["content_type"] == "text/plain"


def test_evidence_grouped_by_instance():
    """The M:N evidence stream groups to {instance_id: [concept_id, ...]}."""
    grouped = KgBackupV2Reader(_build()).evidence_by_instance()
    assert grouped == {"i1": ["c1", "c2"]}


def test_instances_normalized_no_concept_id():
    inst = list(KgBackupV2Reader(_build()).instances())[0]
    assert "concept_id" not in inst
    assert inst["instance_id"] == "i1" and inst["source_id"] == "s1"
    assert inst["created_at_event_id"] == 1


def test_graph_epochs_de_interned():
    ep = list(KgBackupV2Reader(_build()).graph_epochs())[0]
    assert ep["kind"] == "ingestion"
    assert ep["actor"] == "system"


def test_counts():
    counts = KgBackupV2Reader(_build()).counts()
    assert counts == {"concepts": 2, "sources": 1, "instances": 1,
                      "evidence": 2, "relationships": 1, "vocabulary": 1}


def test_external_concept_ids_empty_when_self_contained():
    assert KgBackupV2Reader(_build()).external_concept_ids() == set()


def test_external_concept_ids_detects_dangling_endpoint():
    """An edge endpoint with no concept record is an external dependency."""
    obj = _build(relationships=[
        {"from": "c1", "to": "cX", "type": "IMPLIES", "properties": {}},  # cX not a concept
    ])
    assert KgBackupV2Reader(obj).external_concept_ids() == {"cX"}


def test_negotiate_refuses_missing_header():
    with pytest.raises(ValueError, match="missing header/bulk"):
        KgBackupV2Reader({"version": "1.0", "data": {}})  # the dead v1 shape


def test_negotiate_refuses_unknown_family():
    obj = _build()
    obj["header"]["format_version"] = "something-else/2"
    with pytest.raises(ValueError, match="Unknown backup format_version"):
        KgBackupV2Reader(obj)


def test_negotiate_refuses_higher_major():
    obj = _build()
    obj["header"]["format_version"] = "kg-backup/3"
    with pytest.raises(ValueError, match="newer than supported"):
        KgBackupV2Reader(obj)


def test_negotiate_accepts_current_major():
    obj = _build()
    assert KgBackupV2Reader(obj).format_version == "kg-backup/2"
