"""
Warm-cache pool connection short-circuit (ADR-201 Phase 5f #278).

Pre-fix: every call to calculate_grounding_strength_semantic /
calculate_grounding_strength_batch / calculate_confidence_batch acquired
a pool connection just to read the graph generation counter — even when
all the requested concepts were already in the in-process cache. The
review note on PR #276 (finding #7) called this out: "warm cache should
not pay a round-trip."

These tests prove the short-circuit: when all requested concepts have
entries at `_grounding_cache_generation` / `_confidence_cache_generation`,
the method returns without calling `pool.getconn`. This is a legitimate
"method-call count IS the behavior" case — the optimization's whole
point is to skip the connection acquisition.

Soundness reminder: skipping the generation probe means the method can
serve up-to-one-call-stale data right after a graph mutation. The next
non-warm call reads the new generation and evicts. The tests below
exercise the warm path; the cold path is already covered by the existing
batch tests.
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


class TestGroundingBatchWarmCacheShortcircuit:
    """100% warm batch skips pool.getconn() entirely."""

    def test_all_concepts_cached_no_pool_connection_acquired(self):
        """
        Pre-populate _grounding_cache for 5 IDs at generation=7. Set
        _grounding_cache_generation=7. Call the batch method. Assert
        pool.getconn is never called — the entire response comes from
        the in-process cache without touching the DB.
        """
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        # Seed cache: 5 concepts at generation 7
        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 7
            gmod._grounding_cache.update({
                ("c_alpha", 7): 0.8,
                ("c_beta", 7): 0.5,
                ("c_gamma", 7): -0.2,
                ("c_delta", 7): 0.3,
                ("c_epsilon", 7): 0.9,
            })

        # Build a client with a pool that explodes if accessed
        client = MagicMock()
        client.pool = MagicMock()

        result = GroundingMixin.calculate_grounding_strength_batch(
            client,
            concept_ids=["c_alpha", "c_beta", "c_gamma", "c_delta", "c_epsilon"],
        )

        # Cached values returned correctly
        assert result == {
            "c_alpha": 0.8,
            "c_beta": 0.5,
            "c_gamma": -0.2,
            "c_delta": 0.3,
            "c_epsilon": 0.9,
        }
        # Pool was NEVER touched
        client.pool.getconn.assert_not_called()
        client.pool.putconn.assert_not_called()

    def test_partial_warm_falls_through_to_normal_path(self):
        """
        3 of 5 IDs cached. The short-circuit only fires on 100% warm, so
        the partially-warm case still acquires a pool connection (to hydrate
        the 2 misses). This proves the optimization doesn't accidentally
        skip work it's supposed to do.
        """
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 7
            gmod._grounding_cache.update({
                ("c_alpha", 7): 0.8,
                ("c_beta", 7): 0.5,
                ("c_gamma", 7): -0.2,
                # c_delta, c_epsilon NOT cached
            })

        # Pool must be reachable now so the cold path can run. We just
        # raise after the first getconn to short-circuit the rest of the
        # path — proves only that getconn WAS called, which is the
        # invariant the test guards.
        client = MagicMock()
        client.pool.getconn.side_effect = RuntimeError("pool reached on partial warm")

        with pytest.raises(RuntimeError, match="pool reached on partial warm"):
            GroundingMixin.calculate_grounding_strength_batch(
                client,
                concept_ids=["c_alpha", "c_beta", "c_gamma", "c_delta", "c_epsilon"],
            )

        client.pool.getconn.assert_called()

    def test_no_cached_generation_skips_shortcircuit(self):
        """
        Fresh process: _grounding_cache_generation is None (nothing has
        been cached yet). The short-circuit must NOT fire — there's
        nothing valid to serve from.
        """
        from api.app.lib.age_client.grounding import GroundingMixin

        client = MagicMock()
        client.pool.getconn.side_effect = RuntimeError("cold-path reached")

        with pytest.raises(RuntimeError, match="cold-path reached"):
            GroundingMixin.calculate_grounding_strength_batch(
                client, concept_ids=["c_alpha"]
            )

        client.pool.getconn.assert_called()


class TestGroundingSemanticWarmCacheShortcircuit:
    """Per-concept method skips pool.getconn() on a cache hit."""

    def test_cache_hit_returns_without_acquiring_connection(self):
        """The hot path through the per-concept method (search-render-render
        cycles). One cached concept at the current generation → no DB touch."""
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 3
            gmod._grounding_cache[("c_focus", 3)] = 0.42

        client = MagicMock()
        result = GroundingMixin.calculate_grounding_strength_semantic(
            client, concept_id="c_focus"
        )

        assert result == 0.42
        client.pool.getconn.assert_not_called()

    def test_cache_miss_falls_through_to_cold_path(self):
        """Different concept than what's cached → cold path acquires a conn."""
        from api.app.lib.age_client import grounding as gmod
        from api.app.lib.age_client.grounding import GroundingMixin

        with gmod._grounding_cache_lock:
            gmod._grounding_cache_generation = 3
            gmod._grounding_cache[("c_other", 3)] = 0.1

        client = MagicMock()
        client.pool.getconn.side_effect = RuntimeError("cold-path reached")

        with pytest.raises(RuntimeError):
            GroundingMixin.calculate_grounding_strength_semantic(
                client, concept_id="c_focus"
            )


class TestConfidenceBatchWarmCacheShortcircuit:
    """Same short-circuit on the confidence-side batch method."""

    def test_all_concepts_cached_no_pool_connection_acquired(self):
        """
        All 3 IDs cached at the current generation. grounding_display gets
        recomputed from the caller's grounding_map (a deliberate exception
        to the cache-key invariant — display depends on call-time data
        outside the graph). But level, score, signals, interpretation
        all come from cache. No pool touch.
        """
        from api.app.services import confidence_analyzer as cmod
        from api.app.services.confidence_analyzer import ConfidenceAnalyzer

        # Seed confidence cache for 3 concepts at generation 9
        with cmod._confidence_cache_lock:
            cmod._confidence_cache_generation = 9
            cmod._confidence_cache.update({
                ("c_alpha", 9): {
                    "level": "high",
                    "confidence_score": 0.92,
                    "signals": {"relationship_count": 12},
                    "interpretation": "many supporting edges",
                    "grounding_display": "Strong",  # will be overwritten
                    "calculation_time_ms": 5,
                },
                ("c_beta", 9): {
                    "level": "medium",
                    "confidence_score": 0.55,
                    "signals": {"relationship_count": 4},
                    "interpretation": "moderate support",
                    "grounding_display": "Moderate",
                    "calculation_time_ms": 5,
                },
                ("c_gamma", 9): {
                    "level": "low",
                    "confidence_score": 0.18,
                    "signals": {"relationship_count": 1},
                    "interpretation": "thin",
                    "grounding_display": "Weak",
                    "calculation_time_ms": 5,
                },
            })

        client = MagicMock()
        client.pool = MagicMock()
        analyzer = ConfidenceAnalyzer(client)

        result = analyzer.calculate_confidence_batch(
            concept_ids=["c_alpha", "c_beta", "c_gamma"],
            grounding_map={"c_alpha": 0.9, "c_beta": 0.4, "c_gamma": -0.1},
        )

        # Cached values came back
        assert result["c_alpha"]["level"] == "high"
        assert result["c_beta"]["level"] == "medium"
        assert result["c_gamma"]["level"] == "low"
        # And no pool acquisition
        client.pool.getconn.assert_not_called()
