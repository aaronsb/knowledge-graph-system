"""Integration test for the kg-backup/2 clone writer (ADR-102 P3).

Imports a small, TEST-NAMESPACED synthetic backup into the live dev graph via
``DataImporter.import_backup`` and asserts the reconstructed graph shape — the
normalized instance + M:N evidence reconstruction (EVIDENCED_BY / FROM_SOURCE /
derived APPEARS), the dynamic relationship label, the load-bearing ``learned_id``
edge property, and the carried epoch stamps.

Honors "messy data finds bugs": it does NOT reset the working graph. All nodes use
a ``p3rt_`` id prefix so they can't collide with real data, and the test removes
them in a finally block.
"""
from unittest.mock import MagicMock

import pytest

from api.app.lib.age_client import AGEClient
from api.lib.serialization import DataExporter, DataImporter
from api.lib.id_remap import IdRemapper

NS = "p3rt_"  # test namespace prefix


def _namespaced_backup():
    """A self-contained kg-backup/2 object with namespaced ids (built via the pure builder)."""
    return DataExporter.build_kg_backup_v2(
        concepts=[
            {"concept_id": f"{NS}c1", "label": "P3 Alpha", "search_terms": ["a"],
             "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 11, "last_seen_epoch": 12},
            {"concept_id": f"{NS}c2", "label": "P3 Beta", "search_terms": ["b"],
             "embedding": [0.4, 0.5, 0.6], "created_at_epoch": 11, "last_seen_epoch": 11},
        ],
        sources=[
            {"source_id": f"{NS}s1", "document": "P3 RoundTrip Corpus", "file_path": "/p3.txt",
             "paragraph": 1, "full_text": "alpha implies beta", "content_type": "text/plain"},
        ],
        instances=[
            {"instance_id": f"{NS}i1", "quote": "alpha implies beta",
             "source_id": f"{NS}s1", "created_at_event_id": 11},
        ],
        # One instance evidenced by BOTH concepts (M:N) — exercises the evidence fan-out.
        evidence=[
            {"concept_id": f"{NS}c1", "instance_id": f"{NS}i1"},
            {"concept_id": f"{NS}c2", "instance_id": f"{NS}i1"},
        ],
        relationships=[
            {"from": f"{NS}c1", "to": f"{NS}c2", "type": "IMPLIES",
             "properties": {"learned_id": f"{NS}s1", "confidence": 0.9}},
        ],
        vocabulary=[],          # skip vocab writes; IMPLIES is created as a dynamic edge label
        embedding_profiles=[
            {"identity": "openai:text-embedding-3-small@1536", "vector_space": "openai-3-small",
             "image_vector_space": None, "name": "default", "multimodal": False},
        ],
        epoch_kinds=[],
        graph_epochs=[],        # epoch-log replay is P5; clone carries only the stamps
        schema_version=76,
    )


def _scalar(client, query, key="n"):
    row = client._execute_cypher(query, fetch_one=True)
    return int(str(row.get(key, 0)).strip('"')) if row else 0


@pytest.fixture()
def client_with_cleanup():
    client = AGEClient()
    try:
        yield client
    finally:
        # Remove only the namespaced test nodes (DETACH DELETE drops their edges too).
        for label, idfield in (("Concept", "concept_id"), ("Source", "source_id"), ("Instance", "instance_id")):
            try:
                client._execute_cypher(
                    f"MATCH (n:{label}) WHERE n.{idfield} STARTS WITH '{NS}' DETACH DELETE n"
                )
            except Exception:
                pass


def test_merge_relationship_rejects_unsafe_edge_label():
    """A crafted edge label (untrusted backup) is skipped, never interpolated into Cypher."""
    client = MagicMock()
    n = DataImporter._merge_relationship(
        client, {"from": "a", "to": "b", "type": "IMPLIES]->() DETACH DELETE n //", "properties": {}}
    )
    assert n == 0
    client._execute_cypher.assert_not_called()


def test_clone_writer_reconstructs_graph(client_with_cleanup):
    client = client_with_cleanup
    backup = _namespaced_backup()

    stats = DataImporter.import_backup(client, backup, overwrite_existing=True)

    assert stats["concepts_created"] == 2
    assert stats["sources_created"] == 1
    assert stats["instances_created"] == 1
    assert stats["relationships_created"] == 1

    # Nodes exist with preserved ids + carried epoch stamps.
    assert _scalar(client,
        f"MATCH (c:Concept {{concept_id:'{NS}c1'}}) WHERE c.created_at_epoch = 11 RETURN count(c) AS n") == 1
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}i1'}}) WHERE i.created_at_event_id = 11 RETURN count(i) AS n") == 1

    # Instance is normalized: one FROM_SOURCE edge to its source.
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}i1'}})-[:FROM_SOURCE]->(s:Source {{source_id:'{NS}s1'}}) RETURN count(*) AS n") == 1

    # M:N EVIDENCED_BY reconstructed from the evidence stream — both concepts.
    assert _scalar(client,
        f"MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance {{instance_id:'{NS}i1'}}) WHERE c.concept_id STARTS WITH '{NS}' RETURN count(c) AS n") == 2

    # Derived APPEARS edges (concept -> instance's source) for both concepts.
    assert _scalar(client,
        f"MATCH (c:Concept)-[:APPEARS]->(s:Source {{source_id:'{NS}s1'}}) WHERE c.concept_id STARTS WITH '{NS}' RETURN count(c) AS n") == 2

    # Dynamic relationship with the load-bearing learned_id edge property preserved.
    assert _scalar(client,
        f"MATCH (:Concept {{concept_id:'{NS}c1'}})-[r:IMPLIES]->(:Concept {{concept_id:'{NS}c2'}}) "
        f"WHERE r.learned_id = '{NS}s1' RETURN count(r) AS n") == 1


def test_reimport_is_idempotent(client_with_cleanup):
    """Re-importing the same backup must not duplicate edges (MERGE-by-id)."""
    client = client_with_cleanup
    backup = _namespaced_backup()

    DataImporter.import_backup(client, backup, overwrite_existing=True)
    DataImporter.import_backup(client, backup, overwrite_existing=True)

    # Still exactly one IMPLIES edge and two EVIDENCED_BY edges after a second pass.
    assert _scalar(client,
        f"MATCH (:Concept {{concept_id:'{NS}c1'}})-[r:IMPLIES]->(:Concept {{concept_id:'{NS}c2'}}) RETURN count(r) AS n") == 1
    assert _scalar(client,
        f"MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance {{instance_id:'{NS}i1'}}) WHERE c.concept_id STARTS WITH '{NS}' RETURN count(c) AS n") == 2


def test_adjacent_remap_round_trips_through_clone_writer(client_with_cleanup):
    """Adjacent mode: remap all ids, then clone — edges survive under the NEW ids."""
    client = client_with_cleanup
    backup = _namespaced_backup()

    # New ids stay under the test namespace so cleanup catches them too.
    remapper = IdRemapper(mode="always", id_factory=lambda kind, old: f"{NS}rm_{old}")
    new_obj, table = remapper.remap(backup)

    # Mapping table records the transposition.
    assert table["concepts"][f"{NS}c1"] == f"{NS}rm_{NS}c1"
    assert table["sources"][f"{NS}s1"] == f"{NS}rm_{NS}s1"

    DataImporter.import_backup(client, new_obj, overwrite_existing=True)

    rm_c1, rm_c2 = f"{NS}rm_{NS}c1", f"{NS}rm_{NS}c2"
    rm_s1, rm_i1 = f"{NS}rm_{NS}s1", f"{NS}rm_{NS}i1"

    # The relationship exists under remapped concept ids, with learned_id rewritten
    # through the SOURCE map (the landmine).
    assert _scalar(client,
        f"MATCH (:Concept {{concept_id:'{rm_c1}'}})-[r:IMPLIES]->(:Concept {{concept_id:'{rm_c2}'}}) "
        f"WHERE r.learned_id = '{rm_s1}' RETURN count(r) AS n") == 1

    # Evidence + FROM_SOURCE reconstructed under the remapped instance/source ids.
    assert _scalar(client,
        f"MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance {{instance_id:'{rm_i1}'}})-[:FROM_SOURCE]->(:Source {{source_id:'{rm_s1}'}}) "
        f"RETURN count(c) AS n") == 2
