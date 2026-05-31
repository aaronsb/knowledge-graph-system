"""
Per-chunk failure isolation in batch grounding (ADR-201 Phase 5f, #281).

PR #276's review caught the original behavior: any chunk's Cypher failure
raised straight through `calculate_grounding_strength_batch`, discarding
already-computed results from earlier chunks. The fallback in
`_hydrate_grounding_batch` would then recompute everything per-concept —
hitting cache for the earlier chunks but paying the iteration cost.

These tests pin the fixed behavior: per-chunk failures are isolated.
Earlier and later successful chunks survive in both the returned dict
and the module-level `_grounding_cache`. The failing chunk's concept IDs
log as a WARNING with the IDs included so operators can drill in.

The fakes here implement the small subset of psycopg2 we need (cursor
execute/fetchone/fetchall, pool getconn/putconn) so the real control flow
runs against scripted DB responses — per the project mocking way.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import patch

import numpy as np
import pytest


# ---------- Fakes ----------


class FakeCursor:
    """
    Minimal cursor that returns scripted responses keyed on substrings of
    the SQL it sees. `raise_on_match` lets a test simulate "this exact
    Cypher fails" without affecting any other SQL.
    """

    def __init__(
        self,
        edges_by_chunk_signature: Dict[str, List[Dict]],
        vocab_embeddings: Dict[str, List[float]],
        raise_on_match: Optional[str] = None,
    ):
        self._edges = edges_by_chunk_signature
        self._vocab = vocab_embeddings
        self._raise_on_match = raise_on_match
        self._last_query = ""
        self._next_rows: List[Dict[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self._last_query = sql

        # Simulate a chunk-specific Cypher failure
        if self._raise_on_match and self._raise_on_match in sql:
            raise RuntimeError(f"simulated chunk failure on: {self._raise_on_match}")

        # Savepoints / rollbacks / releases are silent
        if any(token in sql for token in ("SAVEPOINT", "RELEASE", "ROLLBACK")):
            self._next_rows = []
            return

        # ADR-207 canonical freshness clock (committed-epoch tick). The cache
        # keys on this now; the test asserts entries at generation 1.
        if "get_committed_epoch" in sql:
            self._next_rows = [{"get_committed_epoch": 1}]
            return

        # Tier-1 graph generation probe (graph_accel.generation)
        if "graph_accel.generation" in sql:
            self._next_rows = [{"current_generation": 1}]
            return

        # Tier-2 fallback / vocab generation probe
        if "vocabulary_change_counter" in sql:
            self._next_rows = [{"counter": 1}]
            return

        # The polarity axis bootstrap query — return empty so the test
        # path injects a non-None axis via _get_polarity_axis patch.
        if "polarity_axis" in sql or "polarity_concepts" in sql:
            self._next_rows = []
            return

        # Batch edges Cypher — key on the IDs the SQL string mentions
        if "ag_catalog.cypher" in sql and "MATCH (c:Concept)<-[r]-" in sql:
            for sig, rows in self._edges.items():
                if sig in sql:
                    self._next_rows = rows
                    return
            self._next_rows = []
            return

        # Vocabulary embeddings query
        if "relationship_vocabulary" in sql:
            rows = []
            for rel_type, emb in self._vocab.items():
                if f"'{rel_type}'" in sql:
                    rows.append({"relationship_type": rel_type, "embedding": emb})
            self._next_rows = rows
            return

        # Anything else returns empty.
        self._next_rows = []

    def fetchone(self):
        return self._next_rows[0] if self._next_rows else None

    def fetchall(self):
        return list(self._next_rows)


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self, cursor_factory=None):
        return self._cursor


class FakePool:
    """
    Records getconn calls so tests can assert connection acquisition
    patterns. Returns the same FakeConnection each time — chunk boundaries
    are observable through the cursor's call log rather than separate
    connection identities.
    """

    def __init__(self, cursor: FakeCursor):
        self.cursor = cursor
        self.getconn_calls = 0
        self.putconn_calls = 0

    def getconn(self):
        self.getconn_calls += 1
        return FakeConnection(self.cursor)

    def putconn(self, conn):
        self.putconn_calls += 1


# ---------- Tests ----------


@pytest.fixture(autouse=True)
def reset_grounding_cache():
    """Each test starts with empty grounding caches so writes are observable."""
    from api.app.lib.age_client import grounding as query_mod
    with query_mod._grounding_cache_lock:
        query_mod._grounding_cache.clear()
        query_mod._grounding_cache_generation = None
    yield
    with query_mod._grounding_cache_lock:
        query_mod._grounding_cache.clear()
        query_mod._grounding_cache_generation = None


class FakeAgeClient:
    """Just enough of the AGEClient surface for the batch method to drive."""

    graph_name = "knowledge_graph"

    def __init__(self, pool: FakePool):
        self.pool = pool

    def _get_polarity_axis(self, cur):
        # 4D unit vector — any non-None axis works for the dot-product path.
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


class TestGroundingBatchPerChunkRecovery:
    """ADR-201 Phase 5f #281: chunk N failure must not wipe earlier/later chunks."""

    def test_middle_chunk_failure_leaves_earlier_and_later_chunks_intact(
        self, caplog
    ):
        """
        Three chunks of one concept each (BATCH_CHUNK_SIZE patched to 1).
        Chunk 2's Cypher raises. The returned dict still contains the
        computed values for chunks 1 and 3, and the cache holds them too.
        The failing chunk's concept defaults to 0.0 in the result (matching
        the per-concept method's behavior on error). A WARNING is logged
        with the failed chunk's concept_ids so operators can drill in.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as query_mod

        # 4D embeddings — projection onto axis [1,0,0,0] gives the first
        # component. Chunks 1 and 3 should produce non-zero grounding;
        # chunk 2 raises before it can compute.
        cursor = FakeCursor(
            edges_by_chunk_signature={
                "'c_alpha'": [
                    {"concept_id": '"c_alpha"', "rel_type": '"SUPPORTS"',
                     "confidence": '"1.0"'}
                ],
                # 'c_beta' Cypher will raise via raise_on_match below
                "'c_gamma'": [
                    {"concept_id": '"c_gamma"', "rel_type": '"IMPLIES"',
                     "confidence": '"1.0"'}
                ],
            },
            vocab_embeddings={
                "SUPPORTS": [0.7, 0.0, 0.0, 0.0],
                "IMPLIES": [0.5, 0.0, 0.0, 0.0],
            },
            raise_on_match="'c_beta'",
        )
        pool = FakePool(cursor)
        client = FakeAgeClient(pool)

        # Patch BATCH_CHUNK_SIZE to 1 so each concept is its own chunk —
        # makes "chunk 2 fails" observable as a per-concept failure.
        with patch.object(query_mod, "BATCH_CHUNK_SIZE", 1), \
             caplog.at_level("WARNING"):
            result = GroundingMixin.calculate_grounding_strength_batch(
                client,
                concept_ids=["c_alpha", "c_beta", "c_gamma"],
            )

        # Chunk 1: computed correctly
        assert result["c_alpha"] == pytest.approx(0.7)
        # Chunk 2: failed, defaults to 0.0 (matches per-concept failure)
        assert result["c_beta"] == 0.0
        # Chunk 3: computed correctly — the prior failure didn't wipe it
        assert result["c_gamma"] == pytest.approx(0.5)

        # Cache holds the successful computations for the warm path
        assert query_mod._grounding_cache.get(("c_alpha", 1)) == pytest.approx(0.7)
        assert query_mod._grounding_cache.get(("c_gamma", 1)) == pytest.approx(0.5)
        # Failed chunk's concept is NOT cached — leaves room for retry
        # next call (when whatever broke might be fixed)
        assert ("c_beta", 1) not in query_mod._grounding_cache

        # WARNING was emitted with the failed concept ID, so operators
        # can grep logs to find which concepts hit transient errors
        warnings = [
            r.message for r in caplog.records
            if r.levelname == "WARNING" and "chunk failed" in r.message
        ]
        assert len(warnings) == 1
        assert "c_beta" in warnings[0]
        assert "c_alpha" not in warnings[0]  # not part of the failing chunk
        assert "c_gamma" not in warnings[0]

    def test_no_chunk_failures_returns_clean_dict(self, caplog):
        """
        Sanity: when no chunks fail, the behavior matches the pre-#281
        code — no WARNING, all concepts computed, all cached.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as query_mod

        cursor = FakeCursor(
            edges_by_chunk_signature={
                "'c_alpha'": [
                    {"concept_id": '"c_alpha"', "rel_type": '"SUPPORTS"',
                     "confidence": '"1.0"'}
                ],
                "'c_beta'": [
                    {"concept_id": '"c_beta"', "rel_type": '"SUPPORTS"',
                     "confidence": '"1.0"'}
                ],
            },
            vocab_embeddings={"SUPPORTS": [0.7, 0.0, 0.0, 0.0]},
        )
        pool = FakePool(cursor)
        client = FakeAgeClient(pool)

        with patch.object(query_mod, "BATCH_CHUNK_SIZE", 1), \
             caplog.at_level("WARNING"):
            result = GroundingMixin.calculate_grounding_strength_batch(
                client,
                concept_ids=["c_alpha", "c_beta"],
            )

        assert result["c_alpha"] == pytest.approx(0.7)
        assert result["c_beta"] == pytest.approx(0.7)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == [], "no chunk failed — no WARNING expected"

    def test_first_chunk_failure_still_processes_remaining(self, caplog):
        """
        Pre-#281 bug specifically: the FIRST chunk fails. Pre-fix this would
        raise and the caller's fallback would recompute everything. Post-fix:
        chunks 2 and 3 still process and their values land in the dict + cache.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as query_mod

        cursor = FakeCursor(
            edges_by_chunk_signature={
                "'c_beta'": [
                    {"concept_id": '"c_beta"', "rel_type": '"SUPPORTS"',
                     "confidence": '"1.0"'}
                ],
                "'c_gamma'": [
                    {"concept_id": '"c_gamma"', "rel_type": '"SUPPORTS"',
                     "confidence": '"1.0"'}
                ],
            },
            vocab_embeddings={"SUPPORTS": [0.4, 0.0, 0.0, 0.0]},
            raise_on_match="'c_alpha'",
        )
        pool = FakePool(cursor)
        client = FakeAgeClient(pool)

        with patch.object(query_mod, "BATCH_CHUNK_SIZE", 1), \
             caplog.at_level("WARNING"):
            result = GroundingMixin.calculate_grounding_strength_batch(
                client,
                concept_ids=["c_alpha", "c_beta", "c_gamma"],
            )

        assert result["c_alpha"] == 0.0  # failed
        assert result["c_beta"] == pytest.approx(0.4)
        assert result["c_gamma"] == pytest.approx(0.4)

    def test_chunk_failure_does_not_leak_connections(self):
        """
        Every getconn must have a matching putconn — even on the failing
        chunk. Otherwise the pool drains under repeated batch failures.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as query_mod

        cursor = FakeCursor(
            edges_by_chunk_signature={
                "'c_ok'": [{"concept_id": '"c_ok"', "rel_type": '"SUPPORTS"',
                           "confidence": '"1.0"'}],
            },
            vocab_embeddings={"SUPPORTS": [0.3, 0.0, 0.0, 0.0]},
            raise_on_match="'c_bad'",
        )
        pool = FakePool(cursor)
        client = FakeAgeClient(pool)

        with patch.object(query_mod, "BATCH_CHUNK_SIZE", 1):
            GroundingMixin.calculate_grounding_strength_batch(
                client,
                concept_ids=["c_ok", "c_bad"],
            )

        assert pool.getconn_calls == pool.putconn_calls
        assert pool.getconn_calls >= 3  # phase-1 + chunk-1 + chunk-2 (failing)
