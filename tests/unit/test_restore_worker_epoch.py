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
