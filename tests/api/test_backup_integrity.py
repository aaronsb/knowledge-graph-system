"""
Tests for the Backup Integrity Check Module (ADR-015 Phase 2; retargeted to
kg-backup/2 in ADR-102 P3).

The runtime checker now validates the single backup model (declarative header +
bulk record streams). Tests build objects with the pure
``DataExporter.build_kg_backup_v2`` and assert structural, reference, and
external-dependency checks.
"""
import json
import tempfile
from pathlib import Path

import pytest

from api.lib.serialization import DataExporter
from api.app.lib.backup_integrity import (
    BackupIntegrityChecker,
    BackupIntegrity,
    check_backup_integrity,
    check_backup_data,
)


# ========== Fixtures ==========

def _lists(**overrides):
    base = dict(
        concepts=[
            {"concept_id": "c1", "label": "Alpha", "search_terms": ["a"],
             "embedding": [0.1, 0.2], "created_at_epoch": 1, "last_seen_epoch": 1},
            {"concept_id": "c2", "label": "Beta", "search_terms": [],
             "embedding": [0.3, 0.4], "created_at_epoch": 1, "last_seen_epoch": 1},
        ],
        sources=[
            {"source_id": "s1", "document": "Corpus", "file_path": "/a.txt",
             "paragraph": 1, "full_text": "alpha", "content_type": "text/plain"},
        ],
        instances=[
            {"instance_id": "i1", "quote": "alpha", "source_id": "s1", "created_at_event_id": 1},
        ],
        evidence=[{"concept_id": "c1", "instance_id": "i1"}],
        relationships=[
            {"from": "c1", "to": "c2", "type": "IMPLIES", "properties": {}},
        ],
        vocabulary=[
            {"relationship_type": "IMPLIES", "description": "x", "category": "logical",
             "embedding_model": "openai:text-embedding-3-small@1536"},
        ],
        embedding_profiles=[
            {"identity": "openai:text-embedding-3-small@1536", "vector_space": "openai-3-small",
             "image_vector_space": None, "name": "default", "multimodal": False},
        ],
        epoch_kinds=[{"kind": "ingestion", "semantic_wallclock": True, "description": ""}],
        graph_epochs=[],
        schema_version=76,
    )
    base.update(overrides)
    return base


@pytest.fixture
def valid_full_backup():
    return DataExporter.build_kg_backup_v2(**_lists())


@pytest.fixture
def valid_scoped_backup():
    return DataExporter.build_kg_backup_v2(ontology="Corpus", **_lists())


# ========== Structural format ==========

def test_valid_full_backup_passes(valid_full_backup):
    result = BackupIntegrityChecker().check_data(valid_full_backup)
    assert result.valid, [e.message for e in result.errors]
    assert result.statistics["concepts"] == 2


def test_valid_scoped_backup_passes(valid_scoped_backup):
    result = check_backup_data(valid_scoped_backup)
    assert result.valid, [e.message for e in result.errors]


def test_missing_header_bulk_fails():
    result = check_backup_data({"version": "1.0", "data": {}})  # the dead v1 shape
    assert not result.valid
    assert any("header" in e.message.lower() or "bulk" in e.message.lower() for e in result.errors)


def test_unknown_format_version_fails(valid_full_backup):
    valid_full_backup["header"]["format_version"] = "kg-backup/99"
    result = check_backup_data(valid_full_backup)
    assert not result.valid


def test_missing_bulk_section_fails(valid_full_backup):
    del valid_full_backup["bulk"]["sources"]
    result = check_backup_data(valid_full_backup)
    assert not result.valid
    assert any("sources" in e.message for e in result.errors)


def test_non_list_bulk_section_fails(valid_full_backup):
    valid_full_backup["bulk"]["concepts"] = {"not": "a list"}
    result = check_backup_data(valid_full_backup)
    assert not result.valid


# ========== Reference integrity ==========

def test_instance_with_missing_source_fails(valid_full_backup):
    valid_full_backup["bulk"]["instances"][0]["source_id"] = "nonexistent_source"
    result = check_backup_data(valid_full_backup)
    assert not result.valid
    assert any("source_id" in e.message for e in result.errors)


def test_evidence_with_missing_instance_fails(valid_full_backup):
    valid_full_backup["bulk"]["evidence"].append({"concept_id": "c1", "instance_id": "iX"})
    result = check_backup_data(valid_full_backup)
    assert not result.valid
    assert any("instance_id" in e.message for e in result.errors)


def test_relationship_missing_endpoint_fails(valid_full_backup):
    valid_full_backup["bulk"]["relationships"][0]["from"] = None
    result = check_backup_data(valid_full_backup)
    assert not result.valid


# ========== External dependencies ==========

def test_external_concept_reference_is_warning_not_error():
    """An edge to a concept absent from the backup is an external dep (warning)."""
    lists = _lists(relationships=[
        {"from": "c1", "to": "external_concept", "type": "IMPLIES", "properties": {}},
    ])
    result = check_backup_data(DataExporter.build_kg_backup_v2(**lists))
    assert result.valid  # external refs do not fail validation
    assert result.has_external_deps
    assert result.external_deps == 1


# ========== Statistics + file path ==========

def test_statistics_surface_counts(valid_full_backup):
    result = check_backup_data(valid_full_backup)
    assert result.statistics == {
        "concepts": 2, "sources": 1, "instances": 1, "relationships": 1, "vocabulary": 1,
    }


def test_check_file_round_trips(valid_full_backup):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "backup.json"
        p.write_text(json.dumps(valid_full_backup))
        result = check_backup_integrity(str(p))
        assert result.valid, [e.message for e in result.errors]


def test_check_file_missing_path_fails():
    result = check_backup_integrity("/no/such/backup.json")
    assert not result.valid


def test_check_file_invalid_json_fails():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.json"
        p.write_text("{not valid json")
        result = check_backup_integrity(str(p))
        assert not result.valid
