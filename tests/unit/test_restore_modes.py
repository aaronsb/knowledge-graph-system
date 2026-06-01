"""Unit tests for restore merge modes (ADR-102 P4).

idempotent / adjacent are pure (no DB). integration is exercised with a patched
ConceptMatcher so the match-or-mint + attach-and-drop behavior is asserted without
a database.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.lib.serialization import DataExporter
from api.app.lib.restore_modes import RestoreMode, prepare_backup

# Offline validator — adjacent output must stay self-contained (no orphans).
_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "lint_backup", _REPO / "scripts" / "development" / "lint" / "lint_backup.py"
)
lint_backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_backup)


def _backup():
    return DataExporter.build_kg_backup_v2(
        concepts=[
            {"concept_id": "c1", "label": "Alpha", "search_terms": [], "embedding": [0.1, 0.2],
             "created_at_epoch": 1, "last_seen_epoch": 1},
            {"concept_id": "c2", "label": "Beta", "search_terms": [], "embedding": [0.3, 0.4],
             "created_at_epoch": 1, "last_seen_epoch": 1},
        ],
        sources=[{"source_id": "s1", "document": "Doc", "file_path": "/a", "paragraph": 1,
                  "full_text": "t", "content_type": "text/plain"}],
        instances=[{"instance_id": "i1", "quote": "q", "source_id": "s1", "created_at_event_id": 1}],
        evidence=[{"concept_id": "c1", "instance_id": "i1"}, {"concept_id": "c2", "instance_id": "i1"}],
        relationships=[{"from": "c1", "to": "c2", "type": "IMPLIES", "properties": {"learned_id": "s1"}}],
        vocabulary=[{"relationship_type": "IMPLIES", "description": "", "category": "logical",
                     "embedding_model": "openai:text-embedding-3-small@1536"}],
        embedding_profiles=[{"identity": "openai:text-embedding-3-small@1536", "vector_space": "x",
                             "image_vector_space": None, "name": "d", "multimodal": False}],
        epoch_kinds=[{"kind": "ingestion", "semantic_wallclock": True, "description": ""}],
        graph_epochs=[{"event_id": 1, "occurred_at": "2026-06-01T00:00:00Z", "kind": "ingestion",
                       "actor": "system", "counter_after": 1, "metadata": {}}],
        schema_version=76,
    )


class _FakeMatcher:
    """ConceptMatcher stand-in: 'Alpha' matches an existing target; others don't."""
    def __init__(self, client, **kw):
        self.client = client

    def match_concept_in_database(self, external_concept, top_k=5):
        assert "embedding" in external_concept  # integration passes the vector
        if external_concept.get("label") == "Alpha":
            return {"concept_id": "TARGET_c1", "label": "Alpha", "similarity": 0.95}
        return None


# ---- idempotent ----

def test_idempotent_passthrough():
    obj = _backup()
    prepared, maps = prepare_backup(obj, RestoreMode.IDEMPOTENT)
    assert prepared is obj  # no transformation
    assert maps == {"concepts": {}, "sources": {}, "instances": {}}


# ---- adjacent ----

def test_adjacent_mints_all_ids_and_stays_self_contained():
    obj = _backup()
    prepared, maps = prepare_backup(obj, RestoreMode.ADJACENT)
    # every id remapped to something new
    assert set(maps["concepts"]) == {"c1", "c2"}
    assert all(new != old for old, new in maps["concepts"].items())
    assert maps["sources"]["s1"] != "s1"
    # self-contained → validates clean (the no-orphan guarantee)
    assert lint_backup.validate_backup(prepared).ok, \
        [str(i) for i in lint_backup.validate_backup(prepared).errors]


# ---- integration ----

def test_integration_attaches_match_and_mints_rest():
    obj = _backup()
    with patch("api.app.lib.restore_modes.ConceptMatcher", _FakeMatcher):
        prepared, maps = prepare_backup(obj, RestoreMode.INTEGRATION, client=MagicMock())

    # c1 (Alpha) attached to the existing target; c2 minted new.
    assert maps["concepts"]["c1"] == "TARGET_c1"
    assert maps["concepts"]["c2"] not in ("c2", "TARGET_c1")

    # The matched concept's RECORD is dropped (target node left untouched);
    # only the new concept is emitted.
    emitted = [c["concept_id"] for c in prepared["bulk"]["concepts"]]
    assert emitted == [maps["concepts"]["c2"]]
    assert "TARGET_c1" not in emitted

    # References to c1 rewired to the existing target.
    assert any(e["concept_id"] == "TARGET_c1" for e in prepared["bulk"]["evidence"])
    rel = prepared["bulk"]["relationships"][0]
    assert rel["from"] == "TARGET_c1"
    assert rel["to"] == maps["concepts"]["c2"]
    assert rel["properties"]["learned_id"] == maps["sources"]["s1"]  # source remapped too

    # sources/instances always minted fresh
    assert maps["sources"]["s1"] != "s1"
    assert maps["instances"]["i1"] != "i1"


def test_integration_requires_client():
    with pytest.raises(ValueError, match="requires a client"):
        prepare_backup(_backup(), RestoreMode.INTEGRATION, client=None)


# ---- validation ----

def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="Unknown restore mode"):
        prepare_backup(_backup(), "bogus")


def test_restore_mode_validate():
    assert RestoreMode.validate("adjacent") == "adjacent"
    with pytest.raises(ValueError):
        RestoreMode.validate("nope")
