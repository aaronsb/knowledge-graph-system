"""
Cold-start uses vocabulary_change_counter delta (migration 069).

The dev verification turned up this bug: cold-start ran once with an empty
vocab table, marked `initialized=TRUE` with `types_initialized=0`, and the
binary gate then permanently blocked re-runs even after later migrations
seeded 48 builtin types. The fix replaces the binary flag with a
counter-delta check against `last_processed_vocab_change_counter`.

These tests pin the new gate behavior:

1. Current counter > last_processed → work runs, processes missing types,
   updates last_processed to the snapshot at start of run.

2. Current counter == last_processed → no-op, no DB writes.

3. Counter advanced but no types missing embeddings (e.g. only a
   category change) → still update last_processed so the same delta
   doesn't keep re-triggering.

The fakes here replace `self.db` and `self.provider` so the worker's
public API is exercised against scripted DB responses without needing
a live container — matches the project's mocking way (fakes over mocks
for control flow).
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from api.app.services.embedding_worker import EmbeddingWorker


# ----------------------------------------------------------------------------
# Fake DB
# ----------------------------------------------------------------------------


class FakeDb:
    """
    Scripts execute_query responses keyed on SQL substring. Records every
    query for assertions. Lets tests simulate state transitions (counter
    increments, last_processed updates) explicitly.
    """

    def __init__(
        self,
        vocab_change_counter: int = 0,
        last_processed: int = 0,
        missing_types: Optional[List[str]] = None,
    ):
        self.vocab_change_counter = vocab_change_counter
        self.last_processed = last_processed
        self.missing_types = missing_types or []
        self.queries: List[Tuple[str, Optional[tuple]]] = []
        # Track INSERT/UPDATE side effects on system_initialization_status
        self.init_status_updates: List[Dict[str, Any]] = []

    async def execute_query(self, sql: str, params: Optional[tuple] = None):
        self.queries.append((sql.strip(), params))

        if "vocabulary_change_counter" in sql and "SELECT counter" in sql:
            return [{"counter": self.vocab_change_counter}]

        if "last_processed_vocab_change_counter" in sql and "SELECT" in sql:
            return [{"last_processed_vocab_change_counter": self.last_processed}]

        if "FROM kg_api.relationship_vocabulary" in sql and "embedding IS NULL" in sql:
            return [{"relationship_type": t} for t in self.missing_types]

        if "v_builtin_types_missing_embeddings" in sql:
            return [{"relationship_type": t} for t in self.missing_types]

        if "INSERT INTO kg_api.embedding_generation_jobs" in sql:
            return []

        if "UPDATE kg_api.embedding_generation_jobs" in sql:
            return []

        if "UPDATE kg_api.system_initialization_status" in sql:
            # Capture the snapshot the worker is committing
            job_id, vocab_counter, count, provider, model, component = params
            update = {
                "job_id": job_id,
                "vocab_change_counter": vocab_counter,
                "count": count,
                "component": component,
            }
            self.init_status_updates.append(update)
            # Simulate the write-through so subsequent reads see it
            if vocab_counter is not None:
                self.last_processed = vocab_counter
            return []

        # Unhandled queries default to empty
        return []


def _make_worker(db: FakeDb) -> EmbeddingWorker:
    """Build an EmbeddingWorker with stubbed dependencies."""
    worker = EmbeddingWorker.__new__(EmbeddingWorker)
    worker.db = db
    worker.provider = MagicMock()
    worker.provider.model_name = "test-model"
    worker.provider_name = "test-provider"
    # The actual embedding generation path isn't exercised here — these
    # tests pin the *gate* behavior. _batch_generate_embeddings would
    # require a live AI provider; we replace it with an inline stub that
    # returns a result matching the requested types.
    async def fake_batch(job_id, relationship_types, job_type):
        from api.app.services.embedding_worker import EmbeddingJobResult
        return EmbeddingJobResult(
            job_id=job_id,
            job_type=job_type,
            target_count=len(relationship_types),
            processed_count=len(relationship_types),
            failed_count=0,
            duration_ms=1,
            embedding_model="test-model",
            embedding_provider="test-provider",
        )
    worker._batch_generate_embeddings = fake_batch
    return worker


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


class TestRegenerateMissingIfVocabChanged:
    """Migration 069 counter-delta gate behavior."""

    def test_runs_work_when_counter_has_advanced(self):
        """
        Standard case: vocab counter advanced since last_processed, and
        there are types missing embeddings. The work runs, the result
        reports the count, and last_processed gets updated to the
        snapshot captured at the start of the run.
        """
        db = FakeDb(
            vocab_change_counter=42,
            last_processed=10,
            missing_types=["IMPLIES", "CAUSES", "ENABLES"],
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.regenerate_missing_if_vocab_changed())

        assert result.processed_count == 3
        assert result.target_count == 3

        # last_processed was updated to the counter snapshot at start of run
        assert len(db.init_status_updates) == 1
        assert db.init_status_updates[0]["vocab_change_counter"] == 42
        assert db.init_status_updates[0]["count"] == 3
        assert db.init_status_updates[0]["component"] == "builtin_vocabulary_embeddings"
        # Normal path: a job_id IS provided, and _create_job_record was
        # called before _mark_initialization_complete — the FK target
        # row exists, the audit trail stays intact.
        assert db.init_status_updates[0]["job_id"] is not None
        assert any(
            "INSERT INTO kg_api.embedding_generation_jobs" in sql
            for sql, _ in db.queries
        )

    def test_no_op_when_counter_unchanged(self):
        """
        Gate behavior: when current_counter == last_processed, the method
        skips all work. No INSERT/UPDATE to embedding_generation_jobs,
        no UPDATE to system_initialization_status.

        This is the steady-state path the launcher will hit when no
        new vocab has arrived.
        """
        db = FakeDb(
            vocab_change_counter=42,
            last_processed=42,
            missing_types=["IMPLIES"],  # Even if types ARE missing, gate stops us
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.regenerate_missing_if_vocab_changed())

        assert result.processed_count == 0
        assert result.target_count == 0
        # No status update — gate held
        assert db.init_status_updates == []
        # No job record was created
        assert not any(
            "embedding_generation_jobs" in sql for sql, _ in db.queries
        )

    def test_no_op_when_counter_below_last_processed(self):
        """
        Boundary: counter < last_processed (shouldn't happen in practice
        but defensive). Gate holds; no work runs.
        """
        db = FakeDb(
            vocab_change_counter=5,
            last_processed=42,
            missing_types=["IMPLIES"],
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.regenerate_missing_if_vocab_changed())

        assert result.processed_count == 0
        assert db.init_status_updates == []

    def test_counter_advanced_but_no_types_missing_updates_last_processed(self):
        """
        Edge case: counter advanced (e.g. a category-only change), but
        no types are actually missing embeddings. The method still updates
        last_processed so it doesn't keep re-checking the same delta on
        every launcher tick.

        Critically, no row was inserted into embedding_generation_jobs in
        this branch — so `initialization_job_id` must be None in the UPDATE
        params. Setting it to a tracking UUID that has no matching row in
        the FK target would violate
        system_initialization_status_initialization_job_id_fkey and roll
        back the cursor advance, producing a quietly-stuck embedding
        worker that re-fires the same warning on every startup.
        """
        db = FakeDb(
            vocab_change_counter=42,
            last_processed=10,
            missing_types=[],  # All caught up
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.regenerate_missing_if_vocab_changed())

        assert result.processed_count == 0
        assert result.target_count == 0
        # But last_processed still updated to the current counter
        assert len(db.init_status_updates) == 1
        assert db.init_status_updates[0]["vocab_change_counter"] == 42
        assert db.init_status_updates[0]["count"] == 0
        # FK-safe: job_id is None when no row was inserted into
        # embedding_generation_jobs (the SQL uses COALESCE so the column
        # keeps its prior value).
        assert db.init_status_updates[0]["job_id"] is None
        # Also: no embedding_generation_jobs INSERT in this branch.
        assert not any(
            "INSERT INTO kg_api.embedding_generation_jobs" in sql
            for sql, _ in db.queries
        )

    def test_initialize_builtin_embeddings_delegates_to_regenerate(self):
        """
        Backwards compatibility: the legacy entry point used by main.py's
        startup sequence still exists, and goes through the same gate.
        Migration 069 removed its dependence on the binary `initialized`
        flag — a fresh boot after new builtin types are seeded will
        process them, even if cold-start ran once before with count=0.
        """
        db = FakeDb(
            vocab_change_counter=64,
            last_processed=0,  # The dev-env scenario: was 0, never advanced
            missing_types=[f"BUILTIN_TYPE_{i}" for i in range(48)],
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.initialize_builtin_embeddings())

        # Pre-069 this would have short-circuited on the binary flag and
        # returned target_count=0. Post-069 it picks up the missing types.
        assert result.processed_count == 48
        assert result.target_count == 48
        assert db.init_status_updates[0]["vocab_change_counter"] == 64
