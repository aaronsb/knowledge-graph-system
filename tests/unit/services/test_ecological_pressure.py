"""
Unit tests for the ecological-pressure read-out in annealing_manager
(#249 Part 1, ADR-200 §9 + ADR-206 §Phase 3).

Pure-function tests on the module-level helpers — no AnnealingManager
construction, no DB. The DB-bound _load_phase3_controls path is covered
in test_annealing_manager via the existing manager-construction
fixtures.
"""

import pytest

from api.app.services.annealing_manager import (
    _PRESSURE_COMFORT_MAX,
    _PRESSURE_COMFORT_MIN,
    _PRESSURE_EMERGENCY,
    _build_pressure_recommendation,
    _ecological_pressure,
)


class TestEcologicalPressure:
    def test_comfort_band_returns_zero_pressure(self):
        for avg in (10.0, 30.0, 50.0, 80.0):
            score, zone = _ecological_pressure(avg)
            assert score == 0.0
            assert zone == "comfort"

    def test_empty_graph_is_comfort(self):
        score, zone = _ecological_pressure(0.0)
        assert score == 0.0
        assert zone == "comfort"

    def test_below_comfort_min_returns_pressure(self):
        score, zone = _ecological_pressure(2.0)
        assert score > 0.0
        assert zone in {"tight", "over"}

    def test_above_comfort_max_returns_pressure(self):
        score, zone = _ecological_pressure(100.0)
        assert score > 0.0
        assert zone in {"watch", "tight", "over"}

    def test_emergency_threshold_returns_one(self):
        score, zone = _ecological_pressure(_PRESSURE_EMERGENCY + 5)
        assert score == 1.0
        assert zone == "emergency"

    def test_pressure_is_monotonic_above_comfort(self):
        # As ratio grows past comfort_max, pressure should rise (until
        # we hit the emergency cap at 1.0).
        prev_score = -1.0
        for avg in (90, 100, 120, 140, 200):
            score, _zone = _ecological_pressure(float(avg))
            assert score >= prev_score
            prev_score = score


class TestBuildPressureRecommendation:
    def test_zero_pressure_recommends_baseline_values(self):
        rec = _build_pressure_recommendation(
            pressure_score=0.0,
            current_options={
                "failure_cooldown_epochs": "5",
                "max_proposals_per_cycle": "10",
                "min_activity_for_cycle": "1",
            },
        )
        assert rec["failure_cooldown_epochs"]["recommended"] == 5
        assert rec["max_proposals_per_cycle"]["recommended"] == 10
        assert rec["min_activity_for_cycle"]["recommended"] == 1
        # Delta zero across the board when current == recommended
        assert all(block["delta"] == 0 for block in rec.values())

    def test_high_pressure_raises_cooldown_and_lowers_max_proposals(self):
        rec = _build_pressure_recommendation(
            pressure_score=1.0,
            current_options={
                "failure_cooldown_epochs": "5",
                "max_proposals_per_cycle": "10",
                "min_activity_for_cycle": "1",
            },
        )
        # Cooldown grows under pressure (back off harder)
        assert rec["failure_cooldown_epochs"]["recommended"] > 5
        assert rec["failure_cooldown_epochs"]["delta"] > 0
        # Max proposals shrinks under pressure (throttle volume)
        assert rec["max_proposals_per_cycle"]["recommended"] < 10
        assert rec["max_proposals_per_cycle"]["delta"] < 0
        # Min activity ticks up
        assert rec["min_activity_for_cycle"]["recommended"] > 1

    def test_max_proposals_floors_at_two(self):
        # Even at saturation pressure, the system can still emit at least
        # a couple proposals per cycle — never reach zero.
        rec = _build_pressure_recommendation(
            pressure_score=1.0,
            current_options={"max_proposals_per_cycle": "10"},
        )
        assert rec["max_proposals_per_cycle"]["recommended"] >= 2

    def test_missing_current_values_use_defaults(self):
        # Operator never tuned the keys — defaults kick in for the
        # `current` field.
        rec = _build_pressure_recommendation(pressure_score=0.0, current_options={})
        assert rec["failure_cooldown_epochs"]["current"] == 5
        assert rec["max_proposals_per_cycle"]["current"] == 10
        assert rec["min_activity_for_cycle"]["current"] == 1

    def test_corrupt_current_values_use_defaults(self):
        rec = _build_pressure_recommendation(
            pressure_score=0.0,
            current_options={
                "failure_cooldown_epochs": "not_a_number",
                "max_proposals_per_cycle": None,
            },
        )
        assert rec["failure_cooldown_epochs"]["current"] == 5
        assert rec["max_proposals_per_cycle"]["current"] == 10
