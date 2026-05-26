"""
Counter bump + polarity-axis cache key behavior (migration 069).

The bug the dev verification turned up: the polarity-axis cache in
GroundingMixin keyed against vocabulary_change_counter, which only moves
on row membership changes — not on embedding-content changes. Running
`kg admin embedding regenerate --type vocabulary` populated 48 embeddings
without bumping the counter, so the in-process cache held a stale
(vocab_gen=N, axis=None) entry until process restart.

Migration 069 introduces vocabulary_embedding_generation_counter. These
tests pin two behaviors:

1. The polarity-axis cache now reads the new counter, so any bump
   invalidates the cache on the next call.

2. The cache miss path computes a fresh axis from the now-embedded vocab
   rows. (We don't exercise the full vocab embedding pipeline here —
   that lives in integration tests; the unit-level invariant is "key
   moves, cache rebuilds.")
"""

import numpy as np
import pytest

from api.app.lib.age_client.grounding import GroundingMixin


class FakeAgeClient(GroundingMixin):
    """Concrete GroundingMixin subclass — exercises real method dispatch.

    Using a real class instead of MagicMock so `self._get_vocab_embedding_generation`
    inside `_get_polarity_axis` calls the actual method, not a stub.
    """

    def __init__(self):
        pass


@pytest.fixture(autouse=True)
def reset_polarity_cache():
    """Each test starts with empty polarity cache."""
    from api.app.lib.age_client import grounding as gmod
    with gmod._polarity_axis_cache_lock:
        original = gmod._polarity_axis_cache
        gmod._polarity_axis_cache = None
    yield
    with gmod._polarity_axis_cache_lock:
        gmod._polarity_axis_cache = original


class FakeCursor:
    """Tiny cursor that scripts responses keyed on SQL substring."""

    def __init__(self):
        self.queries = []
        # Counter value returned for the embedding-generation counter query
        self.embedding_gen_counter = 0
        # Whether the embedding pair query returns rows that yield a valid axis
        self.pairs_available = True

    def execute(self, sql, params=None):
        self.queries.append(sql)
        if "vocabulary_embedding_generation_counter" in sql:
            self._next = [{"counter": self.embedding_gen_counter}]
        elif "relationship_vocabulary" in sql and "embedding" in sql:
            if self.pairs_available:
                # Two opposing-pair embeddings — SUPPORTS at [1,0,0,0] and
                # CONTRADICTS at [-1,0,0,0] yield axis [1,0,0,0] (normalized).
                self._next = [
                    {"relationship_type": "SUPPORTS",
                     "embedding": [1.0, 0.0, 0.0, 0.0]},
                    {"relationship_type": "CONTRADICTS",
                     "embedding": [-1.0, 0.0, 0.0, 0.0]},
                    {"relationship_type": "ENABLES",
                     "embedding": [0.5, 0.5, 0.0, 0.0]},
                    {"relationship_type": "PREVENTS",
                     "embedding": [-0.5, -0.5, 0.0, 0.0]},
                ]
            else:
                self._next = []
        else:
            self._next = []

    def fetchone(self):
        return self._next[0] if self._next else None

    def fetchall(self):
        return list(self._next)


class TestPolarityAxisCacheKey:
    """Migration 069: polarity cache keys on vocabulary_embedding_generation_counter."""

    def test_get_vocab_embedding_generation_reads_new_counter(self):
        """
        _get_vocab_embedding_generation queries the
        vocabulary_embedding_generation_counter row, not the legacy
        vocabulary_change_counter. Pre-069 the cache keyed on the wrong
        counter, so an embedding regen didn't move the key.
        """
        from api.app.lib.age_client.grounding import GroundingMixin

        cur = FakeCursor()
        cur.embedding_gen_counter = 42

        client = FakeAgeClient()
        result = GroundingMixin._get_vocab_embedding_generation(client, cur)

        assert result == 42
        # The query mentions the new counter by name
        assert any(
            "vocabulary_embedding_generation_counter" in q
            for q in cur.queries
        )
        # And does NOT query the old key
        assert not any(
            "vocabulary_change_counter" in q for q in cur.queries
        )

    def test_axis_cache_hit_when_counter_unchanged(self):
        """
        Standard cache behavior: when the embedding-generation counter
        hasn't moved, _get_polarity_axis returns the cached axis without
        re-querying the vocab embeddings table.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as gmod

        # Seed cache at counter=5 with a known axis
        with gmod._polarity_axis_cache_lock:
            gmod._polarity_axis_cache = (
                5, np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
            )

        cur = FakeCursor()
        cur.embedding_gen_counter = 5  # Same counter

        client = FakeAgeClient()
        axis = GroundingMixin._get_polarity_axis(client, cur)

        # Got the cached axis back
        assert axis is not None
        np.testing.assert_array_equal(axis, np.array([1.0, 0.0, 0.0, 0.0]))
        # Only the counter probe ran, not the embeddings query
        assert not any(
            "FROM kg_api.relationship_vocabulary" in q for q in cur.queries
        )

    def test_axis_cache_invalidates_when_counter_advances(self):
        """
        The bug 069 fixes: when embeddings get regenerated, the
        counter bumps and the cached axis must be discarded.

        Pre-069: cache keyed on vocabulary_change_counter, which didn't
        move on embedding updates → stale cache served indefinitely.

        Post-069: cache keyed on vocabulary_embedding_generation_counter
        which the regen path now bumps → cache miss → axis recomputed.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as gmod

        # Seed cache at counter=5
        stale_axis = np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float64)
        with gmod._polarity_axis_cache_lock:
            gmod._polarity_axis_cache = (5, stale_axis)

        # Simulate: regen bumped counter to 6
        cur = FakeCursor()
        cur.embedding_gen_counter = 6

        client = FakeAgeClient()
        axis = GroundingMixin._get_polarity_axis(client, cur)

        # Cache missed (counter changed) and rebuilt from vocab embeddings
        assert axis is not None
        # The new axis is recomputed from the FakeCursor's seeded pair
        # embeddings, not the stale value we put in
        assert not np.array_equal(axis, stale_axis)
        # The vocab embeddings query DID run (cache rebuild)
        assert any(
            "relationship_vocabulary" in q and "embedding" in q
            for q in cur.queries
        )

    def test_axis_returns_none_when_no_complete_pairs(self):
        """
        Boundary: counter advances but the vocab table has no embedded
        polarity pairs yet (e.g. mid-regen, only one half of each pair
        has been processed). _get_polarity_axis returns None and the
        cache is NOT updated — the next call will retry.
        """
        from api.app.lib.age_client.grounding import GroundingMixin
        from api.app.lib.age_client import grounding as gmod

        # No prior cache
        with gmod._polarity_axis_cache_lock:
            gmod._polarity_axis_cache = None

        cur = FakeCursor()
        cur.embedding_gen_counter = 1
        cur.pairs_available = False  # No embedded pairs in vocab table yet

        client = FakeAgeClient()
        axis = GroundingMixin._get_polarity_axis(client, cur)

        assert axis is None
        # Cache should still be None — don't poison subsequent reads
        with gmod._polarity_axis_cache_lock:
            assert gmod._polarity_axis_cache is None
