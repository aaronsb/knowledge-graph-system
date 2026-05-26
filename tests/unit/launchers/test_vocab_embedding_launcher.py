"""
VocabEmbeddingLauncher condition-check behavior (migration 069/070).

The launcher's whole job is to decide "does the worker need to run?" by
comparing vocabulary_change_counter against last_processed_vocab_change_counter
for a named component. These tests pin that decision against scripted DB
responses.

Mirrors the pattern used by EpistemicRemeasurementLauncher — same shape,
same cron, but reads a per-component cursor on system_initialization_status
instead of the global cursor on graph_metrics. The two launchers must
track progress independently; tests guard against accidentally coupling
them.
"""

from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from api.app.launchers.vocab_embedding import VocabEmbeddingLauncher


class FakeCursor:
    """Scripted cursor — returns the next pre-programmed row per execute()."""

    def __init__(self, vocab_change_counter: int, last_processed: int):
        self.vocab_change_counter = vocab_change_counter
        self.last_processed = last_processed
        self.queries: List[Tuple[str, Optional[tuple]]] = []
        self._next_row: Optional[tuple] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql: str, params: Optional[tuple] = None):
        self.queries.append((sql, params))
        if "vocabulary_change_counter" in sql:
            self._next_row = (self.vocab_change_counter,)
        elif "last_processed_vocab_change_counter" in sql:
            self._next_row = (self.last_processed,)
        else:
            self._next_row = None

    def fetchone(self):
        return self._next_row


class FakeConn:
    def __init__(self, cur: FakeCursor):
        self._cur = cur

    def cursor(self):
        return self._cur


class FakePool:
    def __init__(self, cur: FakeCursor):
        self._cur = cur

    def getconn(self):
        return FakeConn(self._cur)

    def putconn(self, conn):
        pass


def _build_launcher_with_state(
    vocab_change_counter: int, last_processed: int
) -> Tuple[VocabEmbeddingLauncher, FakeCursor]:
    """
    Build a VocabEmbeddingLauncher whose check_conditions reads from a
    scripted FakeCursor. Patches AGEClient inside the launcher module
    so we don't need a live container.
    """
    cur = FakeCursor(vocab_change_counter, last_processed)
    fake_client = MagicMock()
    fake_client.pool = FakePool(cur)

    job_queue = MagicMock()
    launcher = VocabEmbeddingLauncher(job_queue)

    return launcher, cur, fake_client


class TestVocabEmbeddingLauncherConditions:
    """Migration 069/070: per-component counter-delta gate."""

    def test_fires_when_counter_advanced_past_last_processed(self):
        """
        Standard case: vocab membership grew (counter went from 10 to 42),
        worker hasn't caught up — launcher fires.
        """
        launcher, cur, fake_client = _build_launcher_with_state(
            vocab_change_counter=42, last_processed=10
        )
        with patch("api.app.launchers.vocab_embedding.AGEClient", return_value=fake_client):
            assert launcher.check_conditions() is True

    def test_no_op_when_counter_equals_last_processed(self):
        """
        Steady state: worker already processed up to the current counter.
        Launcher does nothing — this is the path it will hit most of the
        time, when no new vocab has arrived between hourly ticks.
        """
        launcher, cur, fake_client = _build_launcher_with_state(
            vocab_change_counter=42, last_processed=42
        )
        with patch("api.app.launchers.vocab_embedding.AGEClient", return_value=fake_client):
            assert launcher.check_conditions() is False

    def test_no_op_when_counter_below_last_processed(self):
        """
        Defensive boundary: counter went backward (operator reset, or
        last_processed got desynced). Don't fire — the worker would
        no-op anyway via its own gate.
        """
        launcher, cur, fake_client = _build_launcher_with_state(
            vocab_change_counter=5, last_processed=42
        )
        with patch("api.app.launchers.vocab_embedding.AGEClient", return_value=fake_client):
            assert launcher.check_conditions() is False

    def test_threshold_is_any_positive_delta(self):
        """
        Threshold is 1, not 10 like the epistemic launcher. Embedding
        generation per-type is cheap; we don't want to delay a single
        new type by up to an hour just to batch. Delta of 1 fires.
        """
        launcher, cur, fake_client = _build_launcher_with_state(
            vocab_change_counter=11, last_processed=10
        )
        with patch("api.app.launchers.vocab_embedding.AGEClient", return_value=fake_client):
            assert launcher.check_conditions() is True

    def test_queries_per_component_not_global_cursor(self):
        """
        The launcher must read last_processed_vocab_change_counter for
        its named component — not the global mark_measurement_complete
        cursor on graph_metrics. EpistemicRemeasurementLauncher uses the
        global cursor; if we accidentally used the same one, the two
        launchers would reset each other's progress.
        """
        launcher, cur, fake_client = _build_launcher_with_state(
            vocab_change_counter=42, last_processed=10
        )
        with patch("api.app.launchers.vocab_embedding.AGEClient", return_value=fake_client):
            launcher.check_conditions()

        # Exactly one query should hit the per-component cursor
        per_component_queries = [
            sql for sql, _params in cur.queries
            if "last_processed_vocab_change_counter" in sql
        ]
        assert len(per_component_queries) == 1
        # And it should include the component name as a parameter
        component_params = [
            params for sql, params in cur.queries
            if "last_processed_vocab_change_counter" in sql
        ]
        assert component_params[0] == ("builtin_vocabulary_embeddings",)

        # The global cursor function (used by epistemic launcher) is NOT called
        assert not any("get_counter_delta" in sql for sql, _ in cur.queries)
        assert not any("mark_measurement_complete" in sql for sql, _ in cur.queries)


class TestVocabEmbeddingLauncherJobData:
    """Static parts of the launcher API."""

    def test_job_type_is_vocab_embedding(self):
        """Worker registry keys on 'vocab_embedding' — keep them in sync."""
        launcher = VocabEmbeddingLauncher(MagicMock())
        assert launcher.get_job_type() == "vocab_embedding"

    def test_prepare_job_data_includes_component(self):
        """Worker reads component from job_data to know which row to update."""
        launcher = VocabEmbeddingLauncher(MagicMock(), component="builtin_vocabulary_embeddings")
        data = launcher.prepare_job_data()
        assert data["operation"] == "regenerate_missing_vocab_embeddings"
        assert data["component"] == "builtin_vocabulary_embeddings"
        assert "description" in data

    def test_custom_component_threaded_through(self):
        """Future use: multiple components could share the same launcher."""
        launcher = VocabEmbeddingLauncher(MagicMock(), component="experimental_types")
        data = launcher.prepare_job_data()
        assert data["component"] == "experimental_types"
