"""
Co-advance proof for the universal tick and its graph_accel sub-counter (ADR-207
step 4).

ADR-207 declares exactly one universal tick (the `event_id` watermark) and
enumerates `graph_accel.generation` as a sub-counter that *co-advances* with it.
The whole point of declaring it co-advancing is that the two move together by
construction — and "by construction" means one method does both. That method is
`AGEClient.record_mutation`: it records+completes an epoch event (advances the
tick) AND calls `graph.invalidate()` (advances the accelerator's generation) from
one place. These tests pin that orchestration so a refactor cannot quietly split
the two and let the in-memory accelerator drift from the SQL clock.

No DB: the epoch/accel calls are mocked; we assert the wiring, not the SQL.
"""

from unittest.mock import MagicMock

from api.app.lib.age_client.ingestion import IngestionMixin
from api.app.lib.freshness import subcounters


class _Harness(IngestionMixin):
    """Minimal IngestionMixin with the four collaborators record_mutation drives
    replaced by mocks, so we can assert the orchestration in isolation."""

    def __init__(self, event_id=42):
        self.record_epoch = MagicMock(return_value=event_id)
        self.complete_epoch = MagicMock()
        self.refresh_epoch = MagicMock()
        self.graph = MagicMock()


def test_record_mutation_coadvances_tick_and_accel():
    """One call advances BOTH the tick (record+complete epoch) and the
    graph_accel sub-counter (graph.invalidate) — the co-advance invariant."""
    h = _Harness(event_id=42)

    result = h.record_mutation("edit", actor="tester")

    assert result == 42
    # Tick advances: epoch recorded then resolved completed.
    h.record_epoch.assert_called_once_with("edit", actor="tester", metadata=None)
    h.complete_epoch.assert_called_once_with(42, "completed")
    # Sub-counter co-advances from the same call.
    h.graph.invalidate.assert_called_once()
    # graph_change_counter snapshot kept fresh for pollers (FUSE).
    h.refresh_epoch.assert_called_once()


def test_failed_epoch_still_invalidates_the_accelerator():
    """If the tick can't advance (record_epoch returns None), the accelerator is
    invalidated anyway — fail-safe (evict, never serve stale), not fail-stale.
    complete_epoch is skipped because there is no event to resolve."""
    h = _Harness(event_id=None)

    result = h.record_mutation("edit")

    assert result is None
    h.complete_epoch.assert_not_called()
    h.graph.invalidate.assert_called_once()
    h.refresh_epoch.assert_called_once()


def test_accelerator_invalidate_failure_is_non_fatal():
    """The extension may not be loaded on a given connection; a raising
    invalidate() must not break the mutation announcement or the tick advance."""
    h = _Harness(event_id=7)
    h.graph.invalidate.side_effect = RuntimeError("extension not loaded")

    result = h.record_mutation("annealing")

    assert result == 7  # tick still advanced despite the accel hiccup
    h.complete_epoch.assert_called_once_with(7, "completed")
    h.refresh_epoch.assert_called_once()


def test_graph_accel_is_the_declared_coadvancing_subcounter():
    """The counter record_mutation drives is exactly the one declared as the
    co-advancing sub-counter — declaration and mechanism agree."""
    coadvancing = [s for s in subcounters() if s.coadvances_with_tick]
    assert len(coadvancing) == 1, "exactly one counter co-advances with the tick"
    assert coadvancing[0].name == "graph_accel.generation"
