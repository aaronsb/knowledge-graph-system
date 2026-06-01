"""Unit matrix for IdRemapper — adjacent-mode ID rewrite (ADR-102 P3).

One test per reference class (the LANDMINE checklist), plus the integrity guarantee
that a remapped object still validates clean (no orphaned references). Pure/DB-free.
"""
import importlib.util
from pathlib import Path

import pytest

from api.lib.serialization import DataExporter
from api.lib.id_remap import IdRemapper, _remap_storage_key

# Offline validator (standalone script) — the no-orphan oracle.
_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "lint_backup", _REPO / "scripts" / "development" / "lint" / "lint_backup.py"
)
lint_backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_backup)


def _backup(**overrides):
    lists = dict(
        concepts=[
            {"concept_id": "c1", "label": "A", "search_terms": [], "embedding": [0.1],
             "created_at_epoch": 1, "last_seen_epoch": 1},
            {"concept_id": "c2", "label": "B", "search_terms": [], "embedding": [0.2],
             "created_at_epoch": 1, "last_seen_epoch": 1},
        ],
        sources=[
            {"source_id": "s1", "document": "Doc", "file_path": "/a", "paragraph": 1,
             "full_text": "t", "content_type": "image/png",
             "garage_key": "sources/Doc/abc123sha", "storage_key": "images/Doc/s1.png"},
        ],
        instances=[
            {"instance_id": "i1", "quote": "q", "source_id": "s1", "created_at_event_id": 1},
        ],
        evidence=[{"concept_id": "c1", "instance_id": "i1"}],
        relationships=[
            {"from": "c1", "to": "c2", "type": "IMPLIES", "properties": {"learned_id": "s1"}},
        ],
        vocabulary=[{"relationship_type": "IMPLIES", "description": "", "category": "logical",
                     "embedding_model": "test:embed@1"}],
        embedding_profiles=[{"identity": "test:embed@1",
                             "vector_space": "x", "image_vector_space": None,
                             "name": "d", "multimodal": False}],
        epoch_kinds=[{"kind": "ingestion", "semantic_wallclock": True, "description": ""}],
        graph_epochs=[{"event_id": 1, "occurred_at": "2026-06-01T00:00:00Z",
                       "kind": "ingestion", "actor": "system", "counter_after": 1, "metadata": {}}],
        schema_version=76,
    )
    lists.update(overrides)
    return DataExporter.build_kg_backup_v2(**lists)


# A deterministic factory so tests can assert exact new ids.
def _fixed_factory(kind, old):
    return f"NEW_{old}"


def _remap_always():
    new, table = IdRemapper(mode="always", id_factory=_fixed_factory).remap(_backup())
    return new, table


def test_concept_id_rewritten_everywhere():
    new, table = _remap_always()
    assert table["concepts"] == {"c1": "NEW_c1", "c2": "NEW_c2"}
    assert [c["concept_id"] for c in new["bulk"]["concepts"]] == ["NEW_c1", "NEW_c2"]
    assert new["bulk"]["evidence"][0]["concept_id"] == "NEW_c1"
    rel = new["bulk"]["relationships"][0]
    assert rel["from"] == "NEW_c1" and rel["to"] == "NEW_c2"


def test_source_id_rewritten_in_sources_and_instances():
    new, table = _remap_always()
    assert table["sources"] == {"s1": "NEW_s1"}
    assert new["bulk"]["sources"][0]["source_id"] == "NEW_s1"
    assert new["bulk"]["instances"][0]["source_id"] == "NEW_s1"


def test_learned_id_edge_property_rewritten_via_source_map():
    """The load-bearing landmine: learned_id is a source_id carried on an edge."""
    new, _ = _remap_always()
    assert new["bulk"]["relationships"][0]["properties"]["learned_id"] == "NEW_s1"


def test_instance_id_rewritten_in_instances_and_evidence():
    new, table = _remap_always()
    assert table["instances"] == {"i1": "NEW_i1"}
    assert new["bulk"]["instances"][0]["instance_id"] == "NEW_i1"
    assert new["bulk"]["evidence"][0]["instance_id"] == "NEW_i1"


def test_storage_key_recomputed_from_new_source_id():
    new, _ = _remap_always()
    src = new["bulk"]["sources"][0]
    assert src["storage_key"] == "images/Doc/NEW_s1.png"


def test_garage_key_is_immune():
    """Content-addressed source-doc keys are NOT remapped."""
    new, _ = _remap_always()
    assert new["bulk"]["sources"][0]["garage_key"] == "sources/Doc/abc123sha"


def test_remapped_object_validates_clean():
    """No reference class left dangling — the integrity guarantee."""
    new, _ = _remap_always()
    result = lint_backup.validate_backup(new)
    assert result.ok, [str(i) for i in result.errors]


def test_header_carried_unchanged():
    new, _ = _remap_always()
    assert new["header"]["format_version"] == "kg-backup/2"


def test_collision_mode_only_remaps_colliding_ids():
    existing = {"concept": {"c1"}, "source": set(), "instance": set()}
    new, table = IdRemapper(mode="collision", existing_ids=existing,
                            id_factory=_fixed_factory).remap(_backup())
    assert table["concepts"]["c1"] == "NEW_c1"   # collided → remapped
    assert table["concepts"]["c2"] == "c2"        # no collision → preserved
    assert table["sources"]["s1"] == "s1"         # no collision → preserved
    # evidence/relationships follow the same map
    assert new["bulk"]["relationships"][0]["from"] == "NEW_c1"
    assert new["bulk"]["relationships"][0]["to"] == "c2"


def test_external_reference_preserved():
    """An edge endpoint absent from the backup keeps its id (points at target data)."""
    obj = _backup(relationships=[
        {"from": "c1", "to": "external_x", "type": "IMPLIES", "properties": {}},
    ])
    new, _ = IdRemapper(mode="always", id_factory=_fixed_factory).remap(obj)
    rel = new["bulk"]["relationships"][0]
    assert rel["from"] == "NEW_c1"
    assert rel["to"] == "external_x"  # untouched


def test_remap_storage_key_anchors_on_filename():
    # source_id appearing only as the filename stem is replaced exactly once.
    assert _remap_storage_key("images/Doc/s1.png", "s1", "NEW") == "images/Doc/NEW.png"


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="Unknown remap mode"):
        IdRemapper(mode="bogus")
