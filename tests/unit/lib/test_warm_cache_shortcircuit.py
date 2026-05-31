"""
Warm-cache on-read freshness (ADR-207 #422, superseding ADR-201 #278).

History: #278 added a connection-free warm-cache short-circuit — when every
requested concept was already cached, the grounding/confidence methods returned
WITHOUT acquiring a pool connection or re-reading the graph generation. That
saved a round-trip but left staleness unbounded in wall-clock time: a hot working
set kept serving pre-mutation values until some unrelated cold-path call happened
to re-read the generation.

ADR-207 D2 forbids that: freshness must be detected ON READ. So the connection-
free short-circuit is gone. The new invariant these tests pin:

  - A warm hit (clock unchanged) still avoids the *expensive recompute* (no edge
    fetch / projection) — the cache's real value — but it DOES read the canonical
    clock every call (a cheap query) to confirm it isn't stale.
  - When the clock has advanced, the cache is evicted and the method recomputes —
    no more serving stale values to a hot working set.

The clock is the committed-epoch tick (kg_api.get_committed_epoch), read via
freshness.read_committed_epoch.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def reset_grounding_cache():
    """Empty caches between tests so warm-cache state is per-test."""
    from api.app.lib.age_client import grounding as gmod
    with gmod._grounding_cache_lock:
        gmod._grounding_cache.clear()
        gmod._grounding_cache_generation = None
    yield
    with gmod._grounding_cache_lock:
        gmod._grounding_cache.clear()
        gmod._grounding_cache_generation = None


@pytest.fixture(autouse=True)
def reset_confidence_cache():
    """Empty confidence cache between tests."""
    from api.app.services import confidence_analyzer as cmod
    with cmod._confidence_cache_lock:
        cmod._confidence_cache.clear()
        cmod._confidence_cache_generation = None
    yield
    with cmod._confidence_cache_lock:
        cmod._confidence_cache.clear()
        cmod._confidence_cache_generation = None


def _client_with_clock(tick: int):
    """A MagicMock client whose pool connection reports `tick` as the committed
    epoch (so read_committed_epoch(cur) returns it). Returns (client, cursor)."""
    cur = MagicMock()
    cur.fetchone.return_value = {"get_committed_epoch": tick}
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = ctx
    client = MagicMock()
    client.pool.getconn.return_value = conn
    return client, cur


class TestGroundingBatchOnReadFreshness:
    """The batch method reads the clock every call; a warm hit skips recompute."""

    def test_warm_hit_reads_clock_but_skips_recompute(self):
        """All 5 IDs cached at the current tick → cached values returned, the
        clock IS read (getconn), but the expensive edge query is NOT run."""
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 7
            gmod._grounding_cache.update({
                ("c_alpha", 7): 0.8, ("c_beta", 7): 0.5, ("c_gamma", 7): -0.2,
                ("c_delta", 7): 0.3, ("c_epsilon", 7): 0.9,
            })

        client, _ = _client_with_clock(7)
        client._execute_cypher = MagicMock()

        result = GroundingMixin.calculate_grounding_strength_batch(
            client,
            concept_ids=["c_alpha", "c_beta", "c_gamma", "c_delta", "c_epsilon"],
        )

        assert result == {
            "c_alpha": 0.8, "c_beta": 0.5, "c_gamma": -0.2,
            "c_delta": 0.3, "c_epsilon": 0.9,
        }
        client.pool.getconn.assert_called()          # clock WAS read (on-read freshness)
        client._execute_cypher.assert_not_called()   # but no expensive recompute

    def test_clock_advance_evicts_and_does_not_serve_stale(self):
        """The #422 fix: cache says c_alpha=0.8 at tick 7, but the clock now
        reports 8 (graph mutated). The stale 0.8 must NOT be served — the cache
        is evicted and c_alpha recomputes (to the default here, since the mock
        has no real graph data). The old connection-free short-circuit would have
        returned the stale 0.8."""
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 7
            gmod._grounding_cache[("c_alpha", 7)] = 0.8

        client, _ = _client_with_clock(8)  # graph mutated since the cache filled
        client._get_polarity_axis = MagicMock(return_value=None)  # → clean 0.0

        result = GroundingMixin.calculate_grounding_strength_batch(
            client, concept_ids=["c_alpha"]
        )

        assert result["c_alpha"] == 0.0          # stale 0.8 NOT served
        client.pool.getconn.assert_called()       # clock WAS read


class TestGroundingSemanticOnReadFreshness:
    """Per-concept method: same on-read freshness."""

    def test_warm_hit_reads_clock_but_skips_recompute(self):
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 3
            gmod._grounding_cache[("c_focus", 3)] = 0.42

        client, _ = _client_with_clock(3)
        client._execute_cypher = MagicMock()

        result = GroundingMixin.calculate_grounding_strength_semantic(
            client, concept_id="c_focus"
        )

        assert result == 0.42
        client.pool.getconn.assert_called()
        client._execute_cypher.assert_not_called()

    def test_clock_advance_does_not_serve_stale(self):
        """Cache says c_focus=0.42 at tick 3, but the clock now reports 4 → the
        stale value must not be served; it recomputes (default 0.0 here)."""
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 3
            gmod._grounding_cache[("c_focus", 3)] = 0.42

        client, _ = _client_with_clock(4)  # graph mutated since the cache filled
        client._get_polarity_axis = MagicMock(return_value=None)  # → clean 0.0

        result = GroundingMixin.calculate_grounding_strength_semantic(
            client, concept_id="c_focus"
        )

        assert result == 0.0                # stale 0.42 NOT served
        client.pool.getconn.assert_called()  # clock WAS read


class TestConfidenceBatchOnReadFreshness:
    """Same on-read freshness on the confidence-side batch method."""

    def test_warm_hit_reads_clock_and_returns_cached_levels(self):
        """All 3 IDs cached at the current tick → cached levels returned and the
        clock IS read. grounding_display is refreshed from the caller's
        grounding_map (it depends on call-time data outside the graph)."""
        from api.app.services import confidence_analyzer as cmod
        from api.app.services.confidence_analyzer import ConfidenceAnalyzer

        with cmod._confidence_cache_lock:
            cmod._confidence_cache_generation = 9
            cmod._confidence_cache.update({
                ("c_alpha", 9): {
                    "level": "high", "confidence_score": 0.92,
                    "signals": {"relationship_count": 12},
                    "interpretation": "many supporting edges",
                    "grounding_display": "Strong", "calculation_time_ms": 5,
                },
                ("c_beta", 9): {
                    "level": "medium", "confidence_score": 0.55,
                    "signals": {"relationship_count": 4},
                    "interpretation": "moderate support",
                    "grounding_display": "Moderate", "calculation_time_ms": 5,
                },
                ("c_gamma", 9): {
                    "level": "low", "confidence_score": 0.18,
                    "signals": {"relationship_count": 1},
                    "interpretation": "thin",
                    "grounding_display": "Weak", "calculation_time_ms": 5,
                },
            })

        client, _ = _client_with_clock(9)
        analyzer = ConfidenceAnalyzer(client)

        result = analyzer.calculate_confidence_batch(
            concept_ids=["c_alpha", "c_beta", "c_gamma"],
            grounding_map={"c_alpha": 0.9, "c_beta": 0.4, "c_gamma": -0.1},
        )

        assert result["c_alpha"]["level"] == "high"
        assert result["c_beta"]["level"] == "medium"
        assert result["c_gamma"]["level"] == "low"
        client.pool.getconn.assert_called()  # clock WAS read on the warm path
