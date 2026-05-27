"""
ProjectionLauncher condition-check behavior.

The launcher decides "does any ontology need a projection job?" by comparing
current concept counts against cached projection metadata. A subtle failure
mode (#fix/projection-tiny-ontology-loop): tiny ontologies with too few
concepts for t-SNE used to be enqueued, fail in the worker, leave no cache
behind, and be re-enqueued on the next tick — an infinite loop visible only
in worker errors. These tests pin the skip rule plus the regular stale-cache
rules.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.app.launchers.projection import ProjectionLauncher


@pytest.fixture
def launcher_factory():
    """Build a launcher with patched DB/cache accessors and a fake job queue."""

    def _make(counts, cached_counts, **kwargs):
        launcher = ProjectionLauncher(job_queue=MagicMock(), **kwargs)
        launcher._get_ontology_concept_counts = MagicMock(return_value=counts)
        launcher._get_cached_concept_count = MagicMock(
            side_effect=lambda ont: cached_counts.get(ont)
        )
        return launcher

    return _make


def _check(launcher):
    """Run check_conditions with AGEClient mocked at the import site."""
    with patch("api.app.launchers.projection.AGEClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.pool.getconn.return_value = MagicMock()
        mock_client_cls.return_value = mock_client
        return launcher.check_conditions()


def test_skips_ontology_below_min_concepts(launcher_factory):
    """An ontology with fewer concepts than min_concepts is silently skipped."""
    launcher = launcher_factory(
        counts={"tiny": 2},
        cached_counts={},  # No cache — would normally enqueue
        min_concepts=5,
    )

    assert _check(launcher) is False
    assert launcher._stale_ontologies == []


def test_skips_at_exact_min_minus_one(launcher_factory):
    """The floor is strict: count == min_concepts - 1 still skips."""
    launcher = launcher_factory(
        counts={"borderline": 4},
        cached_counts={},
        min_concepts=5,
    )

    assert _check(launcher) is False
    assert launcher._stale_ontologies == []


def test_enqueues_at_min_concepts_with_missing_cache(launcher_factory):
    """count == min_concepts is allowed through; missing cache → stale."""
    launcher = launcher_factory(
        counts={"small-but-ok": 5},
        cached_counts={},
        min_concepts=5,
    )

    assert _check(launcher) is True
    assert launcher._stale_ontologies == ["small-but-ok"]


def test_mixed_ontologies_only_eligible_ones_are_staled(launcher_factory):
    """Tiny ontologies are skipped; healthy ones with no cache are queued."""
    launcher = launcher_factory(
        counts={"tiny": 2, "healthy": 50, "also-tiny": 1},
        cached_counts={},
        min_concepts=5,
    )

    assert _check(launcher) is True
    assert launcher._stale_ontologies == ["healthy"]


def test_unchanged_ontology_with_warm_cache_is_skipped(launcher_factory):
    """If cached count is close to current, no job is enqueued."""
    launcher = launcher_factory(
        counts={"healthy": 50},
        cached_counts={"healthy": 49},
        min_concepts=5,
        change_threshold=5,
    )

    assert _check(launcher) is False
    assert launcher._stale_ontologies == []


def test_threshold_exceeded_marks_stale(launcher_factory):
    """Delta >= change_threshold flags the ontology for re-projection."""
    launcher = launcher_factory(
        counts={"healthy": 60},
        cached_counts={"healthy": 50},
        min_concepts=5,
        change_threshold=5,
    )

    assert _check(launcher) is True
    assert launcher._stale_ontologies == ["healthy"]


def test_min_concepts_default_is_five():
    """Default floor matches the t-SNE perplexity practical lower bound."""
    launcher = ProjectionLauncher(job_queue=MagicMock())
    assert launcher.min_concepts == 5
