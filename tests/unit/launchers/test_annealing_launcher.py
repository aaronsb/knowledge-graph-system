"""
AnnealingLauncher refractory gate (ADR-200, Approach A).

The launcher used to fire purely on epoch cadence (current_epoch -
last_annealing_epoch >= epoch_interval). During a large ingest every mutation
bumps the epoch, so the interval was crossed constantly and annealing ran hot
("panic mode") while documents were still flooding in — reorganizing a graph
that the next chunk invalidates. The ecological-pressure curve was computed but
observational-only; it never gated the trigger.

These tests pin the in-flight defer policy: defer while ingestion is active,
but force a cycle once max_defer_epochs of epoch delta accumulate so a
continuous stream can't starve annealing.
"""

import pytest

from api.app.launchers.annealing import _should_defer_for_inflight


class TestShouldDeferForInflight:
    def test_no_inflight_never_defers(self):
        # System at rest — annealing should run regardless of epoch delta.
        assert _should_defer_for_inflight(0, 3, 50) is False
        assert _should_defer_for_inflight(0, 999, 50) is False

    def test_inflight_under_cap_defers(self):
        # Ingestion actively flooding and we haven't waited too long yet — defer.
        assert _should_defer_for_inflight(1, 3, 50) is True
        assert _should_defer_for_inflight(8, 49, 50) is True

    def test_inflight_at_or_past_cap_forces(self):
        # Continuous stream: once the cap is reached, force a cycle (no starvation).
        assert _should_defer_for_inflight(8, 50, 50) is False
        assert _should_defer_for_inflight(8, 120, 50) is False

    def test_negative_inflight_treated_as_none(self):
        assert _should_defer_for_inflight(-1, 3, 50) is False

    @pytest.mark.parametrize("max_defer", [0, 5, 50, 200])
    def test_cap_boundary_is_strict_less_than(self, max_defer):
        # epoch_delta < max_defer defers; epoch_delta == max_defer forces.
        assert _should_defer_for_inflight(1, max_defer - 1, max_defer) is (max_defer - 1 < max_defer)
        assert _should_defer_for_inflight(1, max_defer, max_defer) is False
