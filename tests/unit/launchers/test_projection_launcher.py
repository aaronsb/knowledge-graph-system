"""
ProjectionLauncher condition-check behavior.

The launcher decides "does any ontology need a projection job?" by comparing
current concept counts against cached projection metadata. A subtle failure
mode (#423): tiny ontologies with too few concepts for t-SNE used to be
enqueued, fail in the worker, leave no cache behind, and be re-enqueued on
the next tick — an infinite loop visible only in worker errors. These tests
pin the skip rule, the cache-invalidation-on-shrink rule, the manual-mode
raise, the regular stale-cache rules, and the floor-threaded-into-job_data
contract.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.app.launchers.projection import (
    DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT,
    ProjectionLauncher,
)


@pytest.fixture
def launcher_factory():
    """Build a launcher with patched mixin/cache accessors and a fake job queue."""

    def _make(counts, cached_counts, invalidate_recorder=None, **kwargs):
        launcher = ProjectionLauncher(job_queue=MagicMock(), **kwargs)
        # _get_cached_concept_count is the only DB-touching helper left on
        # the launcher; the bulk count lookup is now on the mixin and
        # patched separately via _patched_check.
        launcher._get_cached_concept_count = MagicMock(
            side_effect=lambda ont: cached_counts.get(ont)
        )
        if invalidate_recorder is not None:
            launcher._invalidate_projection_cache = MagicMock(
                side_effect=lambda ont: invalidate_recorder.append(ont)
            )
        else:
            launcher._invalidate_projection_cache = MagicMock()
        return launcher

    return _make


def _patched_check(launcher, counts, min_floor=None):
    """Run check_conditions with AGEClient + options-read mocked.

    `min_floor` overrides the value the launcher would read from
    annealing_options; pass None to let the default propagate.
    """
    with patch("api.app.launchers.projection.AGEClient") as mock_client_cls, patch(
        "api.app.launchers.projection._read_min_ontology_concept_count"
    ) as mock_read:
        mock_client = MagicMock()
        mock_client.pool.getconn.return_value = MagicMock()
        mock_client.list_ontology_concept_counts.return_value = counts
        mock_client_cls.return_value = mock_client
        mock_read.return_value = (
            min_floor if min_floor is not None else DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT
        )
        return launcher.check_conditions()


# -- skip path -------------------------------------------------------------


def test_skips_ontology_below_floor_without_cache(launcher_factory):
    """Tiny ontology with no cache: silent skip, no enqueue, no invalidation."""
    invalidations: list = []
    launcher = launcher_factory(
        counts={"tiny": 2},
        cached_counts={},
        invalidate_recorder=invalidations,
    )

    assert _patched_check(launcher, {"tiny": 2}, min_floor=5) is False
    assert launcher._stale_ontologies == []
    assert invalidations == []  # nothing to invalidate


def test_floor_is_strict_at_min_minus_one(launcher_factory):
    """count == min - 1 still skips."""
    launcher = launcher_factory(
        counts={"borderline": 4},
        cached_counts={},
    )

    assert _patched_check(launcher, {"borderline": 4}, min_floor=5) is False
    assert launcher._stale_ontologies == []


def test_enqueues_at_floor_with_missing_cache(launcher_factory):
    """count == min is allowed through; missing cache → stale."""
    launcher = launcher_factory(
        counts={"small-but-ok": 5},
        cached_counts={},
    )

    assert _patched_check(launcher, {"small-but-ok": 5}, min_floor=5) is True
    assert launcher._stale_ontologies == ["small-but-ok"]


# -- cache invalidation on shrink ------------------------------------------


def test_shrunken_ontology_below_floor_invalidates_stale_cache(launcher_factory):
    """An ontology that drops below the floor with an existing cache must
    invalidate that cache so read paths don't serve a stale landscape."""
    invalidations: list = []
    launcher = launcher_factory(
        counts={"shrunk": 2},
        cached_counts={"shrunk": 80},  # was big, lost concepts
        invalidate_recorder=invalidations,
    )

    assert _patched_check(launcher, {"shrunk": 2}, min_floor=5) is False
    assert launcher._stale_ontologies == []
    assert invalidations == ["shrunk"]


# -- manual mode (explicit ontology) ---------------------------------------


def test_explicit_ontology_below_floor_raises(launcher_factory):
    """Manual trigger for a tiny ontology should raise, not silently skip."""
    launcher = launcher_factory(
        counts={"manual-tiny": 2},
        cached_counts={},
        ontology="manual-tiny",
    )

    with pytest.raises(ValueError, match="refusing to project"):
        _patched_check(launcher, {"manual-tiny": 2}, min_floor=5)


def test_explicit_ontology_above_floor_proceeds(launcher_factory):
    """Manual mode at floor proceeds normally."""
    launcher = launcher_factory(
        counts={"manual-ok": 10},
        cached_counts={},
        ontology="manual-ok",
    )

    assert _patched_check(launcher, {"manual-ok": 10}, min_floor=5) is True
    assert launcher._stale_ontologies == ["manual-ok"]


# -- mixed ontologies and threshold ----------------------------------------


def test_mixed_ontologies_only_eligible_ones_are_staled(launcher_factory):
    """Tiny ontologies are skipped (their order in input doesn't matter);
    healthy ones with no cache are queued."""
    launcher = launcher_factory(
        counts={"tiny": 2, "healthy": 50, "also-tiny": 1},
        cached_counts={},
    )

    counts = {"tiny": 2, "healthy": 50, "also-tiny": 1}
    assert _patched_check(launcher, counts, min_floor=5) is True
    assert set(launcher._stale_ontologies) == {"healthy"}


def test_unchanged_ontology_with_warm_cache_is_skipped(launcher_factory):
    """If cached count is close to current, no job is enqueued."""
    launcher = launcher_factory(
        counts={"healthy": 50},
        cached_counts={"healthy": 49},
        change_threshold=5,
    )

    assert _patched_check(launcher, {"healthy": 50}, min_floor=5) is False
    assert launcher._stale_ontologies == []


def test_threshold_exceeded_marks_stale(launcher_factory):
    """Delta >= change_threshold flags the ontology for re-projection."""
    launcher = launcher_factory(
        counts={"healthy": 60},
        cached_counts={"healthy": 50},
        change_threshold=5,
    )

    assert _patched_check(launcher, {"healthy": 60}, min_floor=5) is True
    assert launcher._stale_ontologies == ["healthy"]


# -- config / threading ----------------------------------------------------


def test_constructor_override_wins_over_db_options(launcher_factory):
    """Explicit min_ontology_concept_count constructor arg beats annealing_options."""
    launcher = launcher_factory(
        counts={"tiny-by-override": 8},
        cached_counts={},
        min_ontology_concept_count=10,  # higher than count
    )

    # Even if the DB had a lower floor (5), the constructor override (10) wins.
    assert _patched_check(launcher, {"tiny-by-override": 8}, min_floor=5) is False
    assert launcher._stale_ontologies == []


def test_default_floor_matches_annealing_default():
    """The launcher's default code-fallback floor stays aligned with annealing's."""
    from api.app.launchers.annealing import DEFAULTS as ANNEAL_DEFAULTS

    assert (
        DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT
        == ANNEAL_DEFAULTS["min_ontology_concept_count"]
    )


def test_prepare_job_data_threads_floor(launcher_factory):
    """The floor used at check_conditions must reach the worker via job_data."""
    launcher = launcher_factory(
        counts={"healthy": 50},
        cached_counts={},
    )
    _patched_check(launcher, {"healthy": 50}, min_floor=7)

    job_data = launcher.prepare_job_data()
    assert job_data["ontology"] == "healthy"
    assert job_data["min_ontology_concept_count"] == 7
