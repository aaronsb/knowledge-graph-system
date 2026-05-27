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

    For the two `system_initialization_status` UPDATEs (the
    `_mark_initialization_complete` "work was done" path and the
    `_advance_vocab_cursor` "no-op cursor advance" path), the fake
    disambiguates on SQL content (presence of `metadata =` ⇒ full update;
    absence ⇒ cursor-only) and records each into a separately-named list
    so tests can assert which path fired without relying on positional
    param order. The SQL string is also captured so tests can pin the
    load-bearing fragments (`COALESCE`, `::uuid`, `GREATEST`) against
    silent regressions during a refactor.
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
        # Two named records for the two UPDATE shapes — replaces the
        # earlier single positional-unpack list.
        self.init_status_full_updates: List[Dict[str, Any]] = []
        self.init_status_cursor_advances: List[Dict[str, Any]] = []

    # Backwards-compatible alias for existing tests that read this name.
    # New tests should reach for the path-specific lists.
    @property
    def init_status_updates(self) -> List[Dict[str, Any]]:
        return self.init_status_full_updates + self.init_status_cursor_advances

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
            # Two shapes — disambiguate on what's being SET. The full
            # update touches metadata; the cursor-only advance does not.
            if "metadata" in sql:
                job_id, vocab_counter, count, provider, model, component = params
                self.init_status_full_updates.append({
                    "sql": sql,
                    "job_id": job_id,
                    "vocab_change_counter": vocab_counter,
                    "count": count,
                    "component": component,
                })
            else:
                # _advance_vocab_cursor: (vocab_change_counter, component)
                vocab_counter, component = params
                self.init_status_cursor_advances.append({
                    "sql": sql,
                    "vocab_change_counter": vocab_counter,
                    "component": component,
                })
            # Simulate the write-through so subsequent reads see it.
            # Mirrors the production GREATEST semantics: only move forward.
            if vocab_counter is not None and vocab_counter > self.last_processed:
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

        # Normal path: the full UPDATE (with metadata) fires once, the
        # cursor-only advance does not.
        assert len(db.init_status_full_updates) == 1
        assert len(db.init_status_cursor_advances) == 0
        full = db.init_status_full_updates[0]
        assert full["vocab_change_counter"] == 42
        assert full["count"] == 3
        assert full["component"] == "builtin_vocabulary_embeddings"
        # Normal path: a job_id IS provided, and _create_job_record was
        # called before _mark_initialization_complete — the FK target
        # row exists, the audit trail stays intact.
        assert full["job_id"] is not None
        assert any(
            "INSERT INTO kg_api.embedding_generation_jobs" in sql
            for sql, _ in db.queries
        )
        # SQL invariants — pin the load-bearing fragments so a future
        # "simplification" can't silently drop the UUID cast or the
        # backward-motion guard.
        assert "::uuid" in full["sql"], (
            "FK column must keep its explicit UUID cast — psycopg requires it "
            "for typed NULL via COALESCE on uuid columns"
        )
        assert "GREATEST" in full["sql"], (
            "Cursor advance must use GREATEST so two concurrent workers with "
            "stale snapshots cannot roll the cursor backward"
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

    def test_counter_advanced_but_no_types_missing_advances_cursor_only(self):
        """
        Edge case: counter advanced (e.g. a category-only change), but
        no types are actually missing embeddings. The cursor must still
        advance so the launcher doesn't keep re-checking the same delta
        every tick.

        Critically, this path must use `_advance_vocab_cursor` — the
        narrow UPDATE that only touches last_processed_vocab_change_counter.
        The full `_mark_initialization_complete` UPDATE would rewrite
        initialized_at, metadata, and initialization_job_id, decoupling
        the (when, what, by-which-job) tuple from the actual most-recent
        run. It would also smuggle a fresh UUID into the FK column with
        no matching row in embedding_generation_jobs — the FK violation
        PR #425 originally fixed.
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
        # The cursor-only UPDATE fires; the full UPDATE does not. This is
        # the load-bearing assertion: the audit-pair (initialized_at,
        # initialization_job_id, metadata) is not touched by no-op ticks.
        assert len(db.init_status_cursor_advances) == 1
        assert len(db.init_status_full_updates) == 0
        advance = db.init_status_cursor_advances[0]
        assert advance["vocab_change_counter"] == 42
        assert advance["component"] == "builtin_vocabulary_embeddings"
        # No embedding_generation_jobs INSERT in this branch — that's
        # what made the FK violation possible in the first place.
        assert not any(
            "INSERT INTO kg_api.embedding_generation_jobs" in sql
            for sql, _ in db.queries
        )
        # SQL invariant: GREATEST pins the no-backward-motion guard.
        assert "GREATEST" in advance["sql"], (
            "Cursor-only advance must use GREATEST so concurrent workers "
            "with stale snapshots cannot roll the cursor backward"
        )
        # SQL invariant: the no-op path must NOT touch the FK column or
        # the audit-pair columns. The previous design used a single
        # UPDATE for both shapes; the asymmetric COALESCE+timestamp
        # rewrite was a real audit-trail bug. Pin the column boundaries.
        assert "initialization_job_id" not in advance["sql"]
        assert "initialized_at" not in advance["sql"]
        assert "metadata" not in advance["sql"]

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
        assert db.init_status_full_updates[0]["vocab_change_counter"] == 64

    def test_advance_vocab_cursor_does_not_roll_backward_on_stale_snapshot(self):
        """
        Race: worker B already committed last_processed=43 (it processed a
        new type that arrived after worker A's snapshot). Worker A,
        carrying its older snapshot of 42, calls _advance_vocab_cursor.
        The SQL uses GREATEST, so the cursor stays at 43 — A's stale
        snapshot does not roll the cursor backward.
        """
        db = FakeDb(
            vocab_change_counter=50,
            last_processed=43,  # B already committed this
            missing_types=[],
        )
        worker = _make_worker(db)

        # A's stale snapshot — older than what's already committed
        asyncio.run(
            worker._advance_vocab_cursor(
                component="builtin_vocabulary_embeddings",
                vocab_change_counter=42,
            )
        )

        # FakeDb mirrors production GREATEST semantics — last_processed
        # stayed at 43, not regressed to 42.
        assert db.last_processed == 43
        # The UPDATE was still issued (idempotent at the SQL layer; the
        # GREATEST in production picks the higher value), and its SQL
        # contains GREATEST so the production behavior matches the test
        # fixture.
        assert len(db.init_status_cursor_advances) == 1
        assert "GREATEST" in db.init_status_cursor_advances[0]["sql"]

    def test_gate_hold_no_op_creates_no_audit_artifacts(self):
        """
        When the counter hasn't advanced (current <= last_processed), the
        early return must not generate a UUID, not insert a job row, and
        not touch system_initialization_status. The pre-PR shape allocated
        a UUID unconditionally at function top, then carried it through
        a log prefix that referenced an audit ID that was never persisted —
        actively misleading during triage.
        """
        db = FakeDb(
            vocab_change_counter=42,
            last_processed=42,  # equal — nothing to do
            missing_types=[],
        )
        worker = _make_worker(db)

        result = asyncio.run(worker.regenerate_missing_if_vocab_changed())

        # Empty result with no audit UUID (was: str(uuid4()) regardless).
        assert result.job_id == "", (
            "Gate-hold path must not allocate a UUID it never persists"
        )
        # No DB side effects at all.
        assert db.init_status_full_updates == []
        assert db.init_status_cursor_advances == []
        assert not any(
            "INSERT INTO kg_api.embedding_generation_jobs" in sql
            for sql, _ in db.queries
        )
