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
from unittest.mock import MagicMock, patch

import pytest

from api.app.lib.age_client import AGEClient
from api.lib.serialization import DataExporter, DataImporter, KgBackupV2Reader
from api.lib.id_remap import IdRemapper
from api.app.lib.restore_modes import prepare_backup, RestoreMode

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
        for label, idfield in (("Concept", "concept_id"), ("Source", "source_id"),
                               ("Instance", "instance_id"), ("Ontology", "ontology_id")):
            try:
                client._execute_cypher(
                    f"MATCH (n:{label}) WHERE n.{idfield} STARTS WITH '{NS}' DETACH DELETE n"
                )
            except Exception:
                pass


def test_ontology_nodes_and_edges_round_trip(client_with_cleanup):
    """Faithful clone restores the :Ontology layer that the format previously dropped.

    Exports an ontology node (with a non-default ``lifecycle_state``), a source
    scoped to it, and a concept it anchors, then imports into the live graph and
    asserts the node + SCOPED_BY + ANCHORED_BY all reconstruct. ``lifecycle_state``
    is the tell that a *lossy* reconstruction (name-only) would have lost.
    """
    client = client_with_cleanup
    backup = DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": f"{NS}oc1", "label": "Anchor", "search_terms": [],
                   "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 1, "last_seen_epoch": 1}],
        sources=[{"source_id": f"{NS}os1", "document": f"{NS}Onto", "file_path": "/o",
                  "paragraph": 1, "full_text": "t", "content_type": "text/plain"}],
        instances=[], evidence=[], relationships=[], vocabulary=[],
        embedding_profiles=[{"identity": "openai:text-embedding-3-small@1536", "vector_space": "x",
                             "image_vector_space": None, "name": "d", "multimodal": False}],
        epoch_kinds=[], graph_epochs=[],
        ontologies=[{"ontology_id": f"{NS}ont1", "name": f"{NS}Onto",
                     "description": "round-trip", "embedding": [0.4, 0.5, 0.6],
                     "search_terms": ["o"], "lifecycle_state": "frozen",
                     "creation_epoch": 2, "created_by": "tester"}],
        scoped_by=[{"source_id": f"{NS}os1", "ontology": f"{NS}Onto"}],
        anchored_by=[{"ontology": f"{NS}Onto", "concept_id": f"{NS}oc1"}],
        schema_version=76,
    )
    DataImporter.import_backup(client, backup, overwrite_existing=True)

    # :Ontology node restored WITH lifecycle_state intact (a name-only fix loses this).
    assert _scalar(client,
        f"MATCH (o:Ontology {{name:'{NS}Onto'}}) WHERE o.lifecycle_state = 'frozen' "
        f"RETURN count(o) AS n") == 1
    # SCOPED_BY membership + ANCHORED_BY provenance edges reconstructed.
    assert _scalar(client,
        f"MATCH (:Source {{source_id:'{NS}os1'}})-[:SCOPED_BY]->(:Ontology {{name:'{NS}Onto'}}) "
        f"RETURN count(*) AS n") == 1
    assert _scalar(client,
        f"MATCH (:Ontology {{name:'{NS}Onto'}})-[:ANCHORED_BY]->(:Concept {{concept_id:'{NS}oc1'}}) "
        f"RETURN count(*) AS n") == 1


def test_ontology_merges_on_name_not_id(client_with_cleanup):
    """Merge safety: an incoming ontology with the same NAME but a different
    ontology_id converges onto the one node (keyed by name), not a duplicate.

    The rest of the system keys ontologies by name; MERGE-on-name keeps a single
    node and lets the SCOPED_BY/ANCHORED_BY MATCHes (which bind by name) resolve
    unambiguously. Regression guard for the adjacent/integration collision case.
    """
    client = client_with_cleanup
    # Pre-existing ontology in the target: same name, DIFFERENT id.
    client._execute_cypher(
        "CREATE (o:Ontology {name: $name, ontology_id: $oid, lifecycle_state: 'active'})",
        params={"name": f"{NS}Onto", "oid": f"{NS}ontA"})

    backup = DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": f"{NS}oc1", "label": "Anchor", "search_terms": [],
                   "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 1, "last_seen_epoch": 1}],
        sources=[{"source_id": f"{NS}os1", "document": f"{NS}Onto", "file_path": "/o",
                  "paragraph": 1, "full_text": "t", "content_type": "text/plain"}],
        instances=[], evidence=[], relationships=[], vocabulary=[],
        embedding_profiles=[{"identity": "openai:text-embedding-3-small@1536", "vector_space": "x",
                             "image_vector_space": None, "name": "d", "multimodal": False}],
        epoch_kinds=[], graph_epochs=[],
        ontologies=[{"ontology_id": f"{NS}ontB", "name": f"{NS}Onto",  # SAME name, different id
                     "description": "", "embedding": [0.4, 0.5, 0.6], "search_terms": [],
                     "lifecycle_state": "frozen", "creation_epoch": 2, "created_by": None}],
        scoped_by=[{"source_id": f"{NS}os1", "ontology": f"{NS}Onto"}],
        anchored_by=[{"ontology": f"{NS}Onto", "concept_id": f"{NS}oc1"}],
        schema_version=76,
    )
    DataImporter.import_backup(client, backup, overwrite_existing=True)

    # Exactly ONE node with that name — the id mismatch did NOT spawn a duplicate.
    assert _scalar(client,
        f"MATCH (o:Ontology {{name:'{NS}Onto'}}) RETURN count(o) AS n") == 1
    # Edges attach unambiguously to that single node.
    assert _scalar(client,
        f"MATCH (:Source {{source_id:'{NS}os1'}})-[:SCOPED_BY]->(:Ontology {{name:'{NS}Onto'}}) "
        f"RETURN count(*) AS n") == 1
    assert _scalar(client,
        f"MATCH (:Ontology {{name:'{NS}Onto'}})-[:ANCHORED_BY]->(:Concept {{concept_id:'{NS}oc1'}}) "
        f"RETURN count(*) AS n") == 1


def test_integration_mode_attaches_to_existing_concept(client_with_cleanup):
    """integration: a matched incoming concept's instance/edges attach to the
    EXISTING target concept (not in this backup); the target node is untouched."""
    client = client_with_cleanup

    # Pre-insert the existing target concept (namespaced; caught by prefix cleanup).
    target = DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": f"{NS}tgt", "label": "Shared", "search_terms": [],
                   "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 1, "last_seen_epoch": 1}],
        sources=[], instances=[], evidence=[], relationships=[], vocabulary=[],
        embedding_profiles=[{"identity": "openai:text-embedding-3-small@1536", "vector_space": "x",
                             "image_vector_space": None, "name": "d", "multimodal": False}],
        epoch_kinds=[], graph_epochs=[], schema_version=76,
    )
    DataImporter.import_backup(client, target, overwrite_existing=True)

    incoming = _namespaced_backup()  # p3rt_c1 (label "P3 Alpha") will be matched

    class _M:
        def __init__(self, *a, **k):
            pass
        def match_concept_in_database(self, ext, top_k=5):
            return ({"concept_id": f"{NS}tgt", "label": "Shared", "similarity": 0.95}
                    if ext.get("label") == "P3 Alpha" else None)

    # Stub the embedding-space gate (ADR-102 §6) so the test is independent of the
    # dev graph's configured profile; the matcher is already patched.
    with patch("api.app.lib.restore_modes.ConceptMatcher", _M), \
         patch("api.app.lib.restore_modes._target_active_identity",
               return_value="openai:text-embedding-3-small@1536"):
        prepared, maps = prepare_backup(incoming, RestoreMode.INTEGRATION, client)

    minted = [v for m in maps.values() for v in m.values() if not v.startswith(NS)]
    try:
        DataImporter.import_backup(client, prepared, overwrite_existing=True)

        new_i1 = maps["instances"][f"{NS}i1"]
        new_c2 = maps["concepts"][f"{NS}c2"]
        # p3rt_c1's instance attached to the EXISTING target via EVIDENCED_BY.
        assert _scalar(client,
            f"MATCH (:Concept {{concept_id:'{NS}tgt'}})-[:EVIDENCED_BY]->(:Instance {{instance_id:'{new_i1}'}}) "
            f"RETURN count(*) AS n") == 1
        # the IMPLIES edge now runs target -> new c2 (from rewired to the match).
        assert _scalar(client,
            f"MATCH (:Concept {{concept_id:'{NS}tgt'}})-[r:IMPLIES]->(:Concept {{concept_id:'{new_c2}'}}) "
            f"RETURN count(r) AS n") == 1
    finally:
        # Minted ids are uuid-based (outside the NS prefix) — delete them explicitly.
        for _id in minted:
            for label in ("Concept", "Source", "Instance"):
                try:
                    client._execute_cypher(
                        f"MATCH (n:{label}) WHERE n.concept_id = $i OR n.source_id = $i "
                        f"OR n.instance_id = $i DETACH DELETE n", params={"i": _id})
                except Exception:
                    pass


def test_faithful_replay_mints_ordered_ids_and_maps_instances(client_with_cleanup):
    """P5-faithful primitives against the live DB: _replay_graph_epochs mints fresh
    ordered event_ids carrying occurred_at/kind, and import with event_id_map stamps
    the restored instance through old→new. Inserts as 'completed' (watermark-safe)
    and deletes the test epoch rows in a finally."""
    client = client_with_cleanup
    backup = DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": f"{NS}fc1", "label": "F", "search_terms": [],
                   "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 5, "last_seen_epoch": 7}],
        sources=[{"source_id": f"{NS}fs1", "document": "F", "file_path": "/f", "paragraph": 1,
                  "full_text": "t", "content_type": "text/plain"}],
        instances=[{"instance_id": f"{NS}fi1", "quote": "q", "source_id": f"{NS}fs1",
                    "created_at_event_id": 41}],   # carried id → must remap to a new local id
        evidence=[{"concept_id": f"{NS}fc1", "instance_id": f"{NS}fi1"}],
        relationships=[], vocabulary=[],
        embedding_profiles=[{"identity": "x", "vector_space": "x", "image_vector_space": None,
                             "name": "d", "multimodal": False}],
        epoch_kinds=[{"kind": "ingestion", "semantic_wallclock": True, "description": ""}],
        graph_epochs=[
            {"event_id": 40, "occurred_at": "2026-01-01T00:00:00Z", "kind": "ingestion",
             "actor": "system", "counter_after": 40, "metadata": {"k": "v"}},
            {"event_id": 41, "occurred_at": "2026-02-01T00:00:00Z", "kind": "ingestion",
             "actor": "system", "counter_after": 41, "metadata": {}},
        ],
        schema_version=76,
    )
    reader = KgBackupV2Reader(backup)

    DataImporter._ensure_epoch_kinds(client, reader)
    event_id_map = DataImporter._replay_graph_epochs(client, reader, status="completed")
    new_ids = sorted(event_id_map.values())
    try:
        # Two events minted, fresh + ordered (preserve original 40<41 order).
        assert set(event_id_map.keys()) == {40, 41}
        assert new_ids[0] < new_ids[1]
        assert event_id_map[40] < event_id_map[41]
        # Rows exist carrying the original kind + wallclock.
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT kind, occurred_at FROM kg_api.graph_epochs WHERE event_id = %s",
                    (event_id_map[40],))
                row = cur.fetchone()
                assert row[0] == "ingestion"
                assert row[1].year == 2026 and row[1].month == 1
        finally:
            conn.commit(); client.pool.putconn(conn)

        # Import with the map: the instance's carried event_id 41 → the new local id.
        DataImporter.import_backup(client, backup, overwrite_existing=True, event_id_map=event_id_map)
        assert _scalar(client,
            f"MATCH (i:Instance {{instance_id:'{NS}fi1'}}) "
            f"WHERE i.created_at_event_id = {event_id_map[41]} RETURN count(i) AS n") == 1
        assert _scalar(client,
            f"MATCH (i:Instance {{instance_id:'{NS}fi1'}}) "
            f"WHERE i.created_at_event_id = 41 RETURN count(i) AS n") == 0
    finally:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kg_api.graph_epochs WHERE event_id = ANY(%s)", (new_ids,))
            conn.commit()
        finally:
            client.pool.putconn(conn)


def test_faithful_unmapped_event_id_is_unstamped_not_dangling(client_with_cleanup):
    """P5-faithful safety (review M2): an instance referencing an event_id absent
    from the backup's graph_epochs must be stamped NULL, not passed through to a
    foreign id that would dangle against the target's fresh epoch sequence."""
    client = client_with_cleanup
    backup = DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": f"{NS}uc1", "label": "U", "search_terms": [],
                   "embedding": [0.1, 0.2, 0.3], "created_at_epoch": 1, "last_seen_epoch": 1}],
        sources=[{"source_id": f"{NS}us1", "document": "U", "file_path": "/u", "paragraph": 1,
                  "full_text": "t", "content_type": "text/plain"}],
        # Instance references event 999 — NOT present in graph_epochs below.
        instances=[{"instance_id": f"{NS}ui1", "quote": "q", "source_id": f"{NS}us1",
                    "created_at_event_id": 999}],
        evidence=[{"concept_id": f"{NS}uc1", "instance_id": f"{NS}ui1"}],
        relationships=[], vocabulary=[],
        embedding_profiles=[{"identity": "x", "vector_space": "x", "image_vector_space": None,
                             "name": "d", "multimodal": False}],
        epoch_kinds=[], graph_epochs=[], schema_version=76,
    )
    # event_id_map is empty (no carried epochs) → 999 is unmapped.
    DataImporter.import_backup(client, backup, overwrite_existing=True, event_id_map={})

    # Stamped NULL (unstamped), NOT the dangling foreign id 999.
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}ui1'}}) "
        f"WHERE i.created_at_event_id = 999 RETURN count(i) AS n") == 0
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}ui1'}}) "
        f"WHERE i.created_at_event_id IS NULL RETURN count(i) AS n") == 1


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


def test_epoch_simple_restamp_overrides_carried_stamps(client_with_cleanup):
    """ADR-102 P5 epoch-simple: ``epoch_restamp`` overrides the carried per-record
    epoch stamps with LOCAL clocks — every instance gets the one restore event_id,
    every concept gets the target's current concept epoch. The backup's own
    stamps (event_id 11, epochs 11/12) must NOT survive."""
    client = client_with_cleanup
    backup = _namespaced_backup()  # carries created_at_event_id=11, epochs 11/12

    RESTORE_EVENT = 770077   # the single restore graph_epochs.event_id
    CONCEPT_EPOCH = 880088   # target's current document_ingestion_counter

    DataImporter.import_backup(
        client, backup, overwrite_existing=True,
        epoch_restamp={"event_id": RESTORE_EVENT, "concept_epoch": CONCEPT_EPOCH},
    )

    # Instance event_id restamped to the restore event (carried 11 is gone).
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}i1'}}) WHERE i.created_at_event_id = {RESTORE_EVENT} RETURN count(i) AS n") == 1
    assert _scalar(client,
        f"MATCH (i:Instance {{instance_id:'{NS}i1'}}) WHERE i.created_at_event_id = 11 RETURN count(i) AS n") == 0

    # Both concepts restamped to the local concept epoch (carried 11/12 gone).
    assert _scalar(client,
        f"MATCH (c:Concept) WHERE c.concept_id STARTS WITH '{NS}' "
        f"AND c.created_at_epoch = {CONCEPT_EPOCH} AND c.last_seen_epoch = {CONCEPT_EPOCH} RETURN count(c) AS n") == 2
    assert _scalar(client,
        f"MATCH (c:Concept) WHERE c.concept_id STARTS WITH '{NS}' AND c.created_at_epoch = 11 RETURN count(c) AS n") == 0


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
