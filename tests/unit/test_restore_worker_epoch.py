"""Unit test for the ADR-102 A13 fix: a failed restore epoch is FATAL.

Before P5, ``record_mutation`` ran AFTER the restore wrapped in a try/except that
logged-and-continued (and ignored a None return) — a restore could complete with
no epoch event, leaving restored data readable as FRESH against stale derivations
and every Instance untagged. P5 records the epoch BEFORE import and raises when
record_epoch returns None. This test pins that behavior with everything else
mocked (no DB, no real graph).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from api.app.workers import restore_worker


def _minimal_backup():
    return {"header": {"format": "kg-backup/2"}, "bulk": {}}


def test_restore_raises_when_record_epoch_returns_none(tmp_path):
    temp_file = tmp_path / "backup.json"
    temp_file.write_text(json.dumps(_minimal_backup()))

    job_queue = MagicMock()
    job_queue.is_job_cancelled.return_value = False

    client = MagicMock()
    client.record_epoch.return_value = None  # A13: the failure under test

    # Checkpoint path that does NOT exist → the except block's rollback is skipped,
    # so the original error surfaces cleanly.
    missing_checkpoint = tmp_path / "nope.json"

    with patch.object(restore_worker, "AGEClient", return_value=client), \
         patch.object(restore_worker, "freeze_lanes", return_value={"interactive": True}), \
         patch.object(restore_worker, "wait_for_quiesce", return_value=True), \
         patch.object(restore_worker, "thaw_lanes") as thaw, \
         patch.object(restore_worker, "_create_checkpoint_backup", return_value=missing_checkpoint), \
         patch.object(restore_worker, "prepare_backup", return_value=(_minimal_backup(), {})):
        with pytest.raises(Exception, match="record_epoch returned None"):
            restore_worker.run_restore_worker(
                {"temp_file": str(temp_file), "temp_file_id": "t1", "mode": "idempotent"},
                "job_test_a13",
                job_queue,
            )

    # No completed epoch was recorded (event id was None).
    client.complete_epoch.assert_not_called()
    # Lanes were still thawed in the finally despite the fatal error (A14).
    thaw.assert_called_once()


# ---------------------------------------------------------------------------
# P5-faithful eligibility gate + orchestration
# ---------------------------------------------------------------------------
from api.lib.serialization import DataExporter, DataImporter  # noqa: E402


def _valid_backup(concept_epochs=(11, 12)):
    """A spec-valid kg-backup/2 object with two carried epoch events."""
    return DataExporter.build_kg_backup_v2(
        concepts=[{"concept_id": "c1", "label": "A", "search_terms": [], "embedding": [0.1],
                   "created_at_epoch": concept_epochs[0], "last_seen_epoch": concept_epochs[1]}],
        sources=[{"source_id": "s1", "document": "D", "file_path": "/d", "paragraph": 1,
                  "full_text": "t", "content_type": "text/plain"}],
        instances=[{"instance_id": "i1", "quote": "q", "source_id": "s1", "created_at_event_id": 1}],
        evidence=[{"concept_id": "c1", "instance_id": "i1"}],
        relationships=[],
        vocabulary=[],
        embedding_profiles=[{"identity": "x", "vector_space": "x", "image_vector_space": None,
                             "name": "d", "multimodal": False}],
        epoch_kinds=[{"kind": "ingestion", "semantic_wallclock": True, "description": ""}],
        graph_epochs=[
            {"event_id": 1, "occurred_at": "2026-01-01T00:00:00Z", "kind": "ingestion",
             "actor": "system", "counter_after": 1, "metadata": {}},
            {"event_id": 2, "occurred_at": "2026-02-01T00:00:00Z", "kind": "ingestion",
             "actor": "system", "counter_after": 2, "metadata": {}},
        ],
        schema_version=76,
    )


def _run_faithful(tmp_path, mode="idempotent", target_empty=True, backup=None):
    """Drive run_restore_worker in faithful mode with all DB/lane I/O mocked."""
    backup = backup or _valid_backup()
    temp_file = tmp_path / "b.json"
    temp_file.write_text(json.dumps(backup))

    job_queue = MagicMock()
    job_queue.is_job_cancelled.return_value = False
    client = MagicMock()

    with patch.object(restore_worker, "AGEClient", return_value=client), \
         patch.object(restore_worker, "freeze_lanes", return_value={"interactive": True}), \
         patch.object(restore_worker, "wait_for_quiesce", return_value=True), \
         patch.object(restore_worker, "thaw_lanes"), \
         patch.object(restore_worker, "_create_checkpoint_backup", return_value=(tmp_path / "nope.json")), \
         patch.object(restore_worker, "_target_is_empty", return_value=target_empty), \
         patch.object(restore_worker, "prepare_backup", return_value=(backup, {})), \
         patch.object(DataImporter, "_ensure_epoch_kinds") as ensure, \
         patch.object(DataImporter, "_replay_graph_epochs", return_value={1: 101, 2: 102}) as replay, \
         patch.object(DataImporter, "_resolve_replayed_epochs") as resolve, \
         patch.object(DataImporter, "_set_ingestion_counter") as set_counter, \
         patch.object(restore_worker, "_execute_restore", return_value={"concepts": 1}) as execute:
        result = restore_worker.run_restore_worker(
            {"temp_file": str(temp_file), "temp_file_id": "t", "mode": mode, "epoch": "faithful"},
            "job_faithful", job_queue,
        )
    return result, dict(ensure=ensure, replay=replay, resolve=resolve,
                        set_counter=set_counter, execute=execute)


def test_faithful_rejects_non_idempotent_mode(tmp_path):
    with pytest.raises(Exception, match="requires --mode idempotent"):
        _run_faithful(tmp_path, mode="adjacent")


def test_faithful_rejects_non_empty_target(tmp_path):
    with pytest.raises(Exception, match="requires an EMPTY target"):
        _run_faithful(tmp_path, mode="idempotent", target_empty=False)


def test_faithful_orchestration_replays_and_resolves(tmp_path):
    result, m = _run_faithful(tmp_path)

    # Replay happened in_progress; instances stamped via the old→new map; concepts
    # NOT restamped (epoch_restamp is None for faithful).
    m["ensure"].assert_called_once()
    m["replay"].assert_called_once()
    assert m["replay"].call_args.kwargs.get("status") == "in_progress"
    _, exec_kwargs = m["execute"].call_args
    assert exec_kwargs["event_id_map"] == {1: 101, 2: 102}
    assert exec_kwargs["epoch_restamp"] is None

    # Resolved completed; counter advanced to max carried concept epoch (12).
    # _resolve_replayed_epochs(client, new_event_ids, status) — positional.
    m["resolve"].assert_called_once()
    assert sorted(m["resolve"].call_args[0][1]) == [101, 102]
    assert m["resolve"].call_args[0][2] == "completed"
    m["set_counter"].assert_called_once()
    assert m["set_counter"].call_args[0][1] == 12

    assert result["epoch_mode"] == "faithful"
    assert result["faithful_epochs_replayed"] == 2
    assert result["restore_epoch_event_id"] is None
