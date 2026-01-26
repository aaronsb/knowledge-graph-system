"""
Unit tests for aggressiveness_curve.py module.

Tests Cubic Bezier implementation and aggressiveness calculation for
automatic edge vocabulary expansion (ADR-032).

Test Coverage:
- CubicBezier class: bezier(), solve_x(), get_y_for_x()
- All 8 predefined curve profiles
- Boundary conditions (x=0, x=0.5, x=1)
- Edge cases (negative x, x > 1)
- calculate_aggressiveness(): all zones and boundary transitions
- Newton-Raphson convergence
"""

import pytest
import math
from api.app.lib.aggressiveness_curve import (
    CubicBezier,
    AGGRESSIVENESS_CURVES,
    calculate_aggressiveness,
    get_available_profiles,
)


# ============================================================================
# CubicBezier Class Tests
# ============================================================================


class TestCubicBezier:
    """Test suite for CubicBezier class"""

    def test_linear_curve(self):
        """Linear curve (0, 0, 1, 1) should produce y = x"""
        curve = CubicBezier(0.0, 0.0, 1.0, 1.0)

        # Test several points along linear curve
        test_points = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        for x in test_points:
            y = curve.get_y_for_x(x)
            assert abs(y - x) < 0.01, f"Linear curve at x={x} should be y={x}, got y={y}"

    def test_boundary_conditions(self):
        """Test boundary conditions for all curves"""
        for profile_name, curve in AGGRESSIVENESS_CURVES.items():
            # x=0 should always give y=0
            assert curve.get_y_for_x(0.0) == 0.0, f"{profile_name}: x=0 should return y=0"

            # x=1 should always give y=1
            assert curve.get_y_for_x(1.0) == 1.0, f"{profile_name}: x=1 should return y=1"

    def test_negative_x_clamping(self):
        """Negative x should clamp to 0.0"""
        curve = AGGRESSIVENESS_CURVES["linear"]
        assert curve.get_y_for_x(-0.5) == 0.0
        assert curve.get_y_for_x(-100) == 0.0

    def test_x_greater_than_one_clamping(self):
        """x > 1 should clamp to 1.0"""
        curve = AGGRESSIVENESS_CURVES["linear"]
        assert curve.get_y_for_x(1.5) == 1.0
        assert curve.get_y_for_x(100) == 1.0

    def test_monotonic_increasing(self):
        """All curves should be monotonically increasing (y2 >= y1 when x2 > x1)"""
        for profile_name, curve in AGGRESSIVENESS_CURVES.items():
            x_values = [i/100.0 for i in range(101)]  # 0.00, 0.01, ..., 1.00
            y_values = [curve.get_y_for_x(x) for x in x_values]

            for i in range(len(y_values) - 1):
                assert y_values[i+1] >= y_values[i] - 0.001, (
                    f"{profile_name}: Not monotonic at x={x_values[i]}, "
                    f"y1={y_values[i]}, y2={y_values[i+1]}"
                )

    def test_midpoint_behavior(self):
        """Test expected behavior at x=0.5 for known curves"""
        # Linear at x=0.5 should be ~0.5
        linear = AGGRESSIVENESS_CURVES["linear"]
        assert abs(linear.get_y_for_x(0.5) - 0.5) < 0.05

        # Ease-in at x=0.5 should be < 0.5 (slow start)
        ease_in = AGGRESSIVENESS_CURVES["ease-in"]
        assert ease_in.get_y_for_x(0.5) < 0.5

        # Ease-out at x=0.5 should be > 0.5 (fast start)
        ease_out = AGGRESSIVENESS_CURVES["ease-out"]
        assert ease_out.get_y_for_x(0.5) > 0.5

    def test_aggressive_profile_characteristics(self):
        """
        Test that 'aggressive' profile stays low until 75%, then accelerates.

        This is the RECOMMENDED profile per ADR-032.
        CubicBezier(0.1, 0.0, 0.9, 1.0)
        """
        curve = AGGRESSIVENESS_CURVES["aggressive"]

        # Should stay relatively passive until 75%
        assert curve.get_y_for_x(0.25) < 0.3, "Should be passive at 25%"
        assert curve.get_y_for_x(0.50) <= 0.5, "Should be moderate at 50%"
        assert curve.get_y_for_x(0.75) < 0.8, "Should still be moderate at 75%"

        # Should accelerate sharply after 75%
        assert curve.get_y_for_x(0.85) > 0.7, "Should accelerate at 85%"
        assert curve.get_y_for_x(0.95) > 0.9, "Should be high at 95%"

    def test_gentle_profile_characteristics(self):
        """
        Test that 'gentle' profile is very gradual.

        CubicBezier(0.5, 0.5, 0.5, 0.5)
        """
        curve = AGGRESSIVENESS_CURVES["gentle"]

        # Should be close to linear but smoother
        assert abs(curve.get_y_for_x(0.25) - 0.25) < 0.1
        assert abs(curve.get_y_for_x(0.50) - 0.50) < 0.1
        assert abs(curve.get_y_for_x(0.75) - 0.75) < 0.1

    def test_exponential_profile_characteristics(self):
        """
        Test that 'exponential' profile explodes near limit.

        CubicBezier(0.7, 0.0, 0.84, 0.0)
        """
        curve = AGGRESSIVENESS_CURVES["exponential"]

        # Should stay very low until very close to limit
        assert curve.get_y_for_x(0.5) < 0.4, "Should be low at 50%"
        assert curve.get_y_for_x(0.75) < 0.6, "Should be low at 75%"

        # Then accelerate near the end (less dramatic than originally expected)
        assert curve.get_y_for_x(0.9) > 0.5, "Should accelerate at 90%"
        assert curve.get_y_for_x(0.95) > 0.7, "Should be high at 95%"

    def test_newton_raphson_convergence(self):
        """Test that Newton-Raphson solver converges within tolerance"""
        curve = AGGRESSIVENESS_CURVES["aggressive"]

        # Test that internal solve_x() produces consistent results
        for x_target in [0.1, 0.25, 0.5, 0.75, 0.9]:
            t = curve.solve_x(x_target)
            x_actual = curve._bezier_x(t)

            # Should converge within epsilon (1e-6)
            assert abs(x_actual - x_target) < 1e-5, (
                f"Newton-Raphson failed to converge for x={x_target}, "
                f"got x={x_actual} after solving"
            )

    def test_repr(self):
        """Test string representation"""
        curve = CubicBezier(0.1, 0.0, 0.9, 1.0)
        assert repr(curve) == "CubicBezier(0.1, 0.0, 0.9, 1.0)"


# ============================================================================
# Predefined Profiles Tests
# ============================================================================


class TestPredefinedProfiles:
    """Test suite for predefined curve profiles"""

    def test_all_profiles_exist(self):
        """Test that all documented profiles exist"""
        expected_profiles = [
            "linear",
            "ease",
            "ease-in",
            "ease-out",
            "ease-in-out",
            "aggressive",
            "gentle",
            "exponential",
        ]

        for profile in expected_profiles:
            assert profile in AGGRESSIVENESS_CURVES, f"Missing profile: {profile}"

    def test_profile_types(self):
        """Test that all profiles are CubicBezier instances"""
        for profile_name, curve in AGGRESSIVENESS_CURVES.items():
            assert isinstance(curve, CubicBezier), (
                f"{profile_name} should be CubicBezier instance"
            )

    def test_get_available_profiles(self):
        """Test that get_available_profiles() returns descriptions"""
        profiles = get_available_profiles()

        # Should return a dict
        assert isinstance(profiles, dict)

        # Should have all profile names
        assert "aggressive" in profiles
        assert "gentle" in profiles

        # Should have descriptions
        assert "RECOMMENDED" in profiles["aggressive"]
        assert len(profiles["linear"]) > 10  # Non-empty description


# ============================================================================
# calculate_aggressiveness() Tests
# ============================================================================


class TestCalculateAggressiveness:
    """Test suite for calculate_aggressiveness() function"""

    def test_at_minimum_boundary(self):
        """At vocab_min (30), should return (0.0, 'comfort')"""
        agg, zone = calculate_aggressiveness(30)
        assert agg == 0.0
        assert zone == "comfort"

    def test_below_minimum(self):
        """Below vocab_min, should return (0.0, 'comfort')"""
        agg, zone = calculate_aggressiveness(20)
        assert agg == 0.0
        assert zone == "comfort"

    def test_at_emergency_limit(self):
        """At vocab_emergency (200), should return (1.0, 'block')"""
        agg, zone = calculate_aggressiveness(200)
        assert agg == 1.0
        assert zone == "block"

    def test_above_emergency_limit(self):
        """Above vocab_emergency, should return (1.0, 'block')"""
        agg, zone = calculate_aggressiveness(250)
        assert agg == 1.0
        assert zone == "block"

    def test_at_soft_limit(self):
        """
        At vocab_max (90), should be in upper zones.

        With aggressive profile, should be transitioning to emergency.
        """
        agg, zone = calculate_aggressiveness(90)
        assert agg > 0.8, "Should be high aggressiveness at soft limit"
        assert zone in ["mixed", "emergency"], f"Unexpected zone at limit: {zone}"

    def test_comfort_zone(self):
        """
        At 35-40 types (slightly above min), should be in comfort zone.

        Aggressiveness < 0.2 → "comfort"
        """
        agg, zone = calculate_aggressiveness(35)
        assert zone == "comfort"
        assert agg < 0.2

    def test_watch_zone(self):
        """
        At ~50 types, should be in watch zone.

        Aggressiveness 0.2-0.5 → "watch"
        """
        agg, zone = calculate_aggressiveness(50)
        assert zone == "watch"
        assert 0.2 <= agg < 0.5

    def test_merge_zone(self):
        """
        At ~65 types, should be in merge zone.

        Aggressiveness 0.5-0.7 → "merge"
        """
        agg, zone = calculate_aggressiveness(65)
        assert zone == "merge"
        assert 0.5 <= agg < 0.7

    def test_mixed_zone(self):
        """
        At ~80 types, should be in mixed zone.

        Aggressiveness 0.7-0.9 → "mixed"
        """
        agg, zone = calculate_aggressiveness(80)
        assert zone == "mixed"
        assert 0.7 <= agg < 0.9

    def test_emergency_zone(self):
        """
        At ~95 types (above soft limit but below emergency), should be emergency.

        Aggressiveness >= 0.9 → "emergency"
        """
        agg, zone = calculate_aggressiveness(95)
        assert zone == "emergency"
        assert agg >= 0.9

    def test_overage_boost(self):
        """
        Test that aggressiveness increases when beyond soft limit.

        At size > vocab_max, aggressiveness should get boosted toward 1.0.
        """
        # Just below limit (where curve hasn't maxed out yet)
        agg_at_85, _ = calculate_aggressiveness(85)

        # Just beyond limit
        agg_at_95, _ = calculate_aggressiveness(95)

        # Should be higher when beyond limit
        assert agg_at_95 > agg_at_85, "Aggressiveness should boost beyond soft limit"

        # Should approach 1.0 as we go further beyond
        agg_at_100, _ = calculate_aggressiveness(100)
        assert agg_at_100 >= agg_at_95, "Should continue increasing toward 1.0"

    def test_different_profiles(self):
        """Test that different profiles produce different aggressiveness values"""
        size = 70  # Mid-range size

        agg_aggressive, _ = calculate_aggressiveness(size, profile="aggressive")
        agg_gentle, _ = calculate_aggressiveness(size, profile="gentle")
        agg_exponential, _ = calculate_aggressiveness(size, profile="exponential")

        # All should be different (profiles have different curves)
        assert agg_aggressive != agg_gentle
        assert agg_aggressive != agg_exponential
        assert agg_gentle != agg_exponential

    def test_custom_window_parameters(self):
        """Test with custom vocab_min, vocab_max, vocab_emergency values"""
        # Custom window: 10-50-100
        agg_min, zone_min = calculate_aggressiveness(
            10, vocab_min=10, vocab_max=50, vocab_emergency=100
        )
        agg_max, zone_max = calculate_aggressiveness(
            50, vocab_min=10, vocab_max=50, vocab_emergency=100
        )
        agg_emerg, zone_emerg = calculate_aggressiveness(
            100, vocab_min=10, vocab_max=50, vocab_emergency=100
        )

        assert agg_min == 0.0
        assert zone_min == "comfort"

        assert agg_max > 0.8

        assert agg_emerg == 1.0
        assert zone_emerg == "block"

    def test_position_normalization(self):
        """
        Test that position is correctly normalized to 0-1 range.

        Position = (current_size - vocab_min) / (vocab_max - vocab_min)
        """
        # At 30 types (min), position = 0
        agg_0, _ = calculate_aggressiveness(30, vocab_min=30, vocab_max=90)

        # At 60 types (midpoint), position = 0.5
        agg_50, _ = calculate_aggressiveness(60, vocab_min=30, vocab_max=90)

        # At 90 types (max), position = 1
        agg_100, _ = calculate_aggressiveness(90, vocab_min=30, vocab_max=90)

        # Verify monotonic increase
        assert agg_0 < agg_50 < agg_100

    def test_zone_boundaries(self):
        """
        Test zone transitions at exact boundary values.

        Zones:
        - comfort:   0.0 <= agg < 0.2
        - watch:     0.2 <= agg < 0.5
        - merge:     0.5 <= agg < 0.7
        - mixed:     0.7 <= agg < 0.9
        - emergency: 0.9 <= agg < 1.0
        - block:     agg == 1.0 (at emergency limit)
        """
        # Use linear profile for predictable aggressiveness values

        # Find sizes that produce specific aggressiveness values
        # For linear profile: position ≈ aggressiveness

        # Test comfort/watch boundary (agg ≈ 0.2)
        # position = 0.2 → size = 30 + 0.2 * (90-30) = 30 + 12 = 42
        agg_42, zone_42 = calculate_aggressiveness(42, profile="linear")
        assert zone_42 == "watch", f"Expected 'watch' at size 42, got '{zone_42}'"

        # Test watch/merge boundary (agg ≈ 0.5)
        # position = 0.5 → size = 30 + 0.5 * 60 = 60
        agg_60, zone_60 = calculate_aggressiveness(60, profile="linear")
        assert zone_60 == "merge", f"Expected 'merge' at size 60, got '{zone_60}'"

    def test_returns_tuple(self):
        """Test that function returns (float, str) tuple"""
        result = calculate_aggressiveness(50)
        assert isinstance(result, tuple)
        assert len(result) == 2

        agg, zone = result
        assert isinstance(agg, float)
        assert isinstance(zone, str)

    def test_aggressiveness_range(self):
        """Test that aggressiveness is always in [0.0, 1.0] range"""
        # Test many sizes across full range
        for size in range(0, 250, 5):
            agg, _ = calculate_aggressiveness(size)
            assert 0.0 <= agg <= 1.0, (
                f"Aggressiveness {agg} out of range [0, 1] at size {size}"
            )

    def test_zone_values(self):
        """Test that zone is always one of the valid values"""
        valid_zones = {"comfort", "watch", "merge", "mixed", "emergency", "block"}

        for size in range(20, 250, 10):
            _, zone = calculate_aggressiveness(size)
            assert zone in valid_zones, f"Invalid zone '{zone}' at size {size}"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test suite for edge cases and error conditions"""

    def test_zero_size(self):
        """Test with vocabulary size of 0"""
        agg, zone = calculate_aggressiveness(0)
        assert agg == 0.0
        assert zone == "comfort"

    def test_very_large_size(self):
        """Test with extremely large vocabulary size"""
        agg, zone = calculate_aggressiveness(10000)
        assert agg == 1.0
        assert zone == "block"

    def test_min_equals_max(self):
        """Test edge case where vocab_min == vocab_max"""
        # This shouldn't happen in practice, but test graceful handling
        # Position calculation would divide by zero, should handle
        agg, zone = calculate_aggressiveness(50, vocab_min=50, vocab_max=50)

        # Should return some reasonable value (either 0 or 1)
        assert agg in [0.0, 1.0]

    def test_inverted_window(self):
        """Test edge case where vocab_max < vocab_min"""
        # This is a configuration error, but test it doesn't crash
        # Position calculation would be negative
        try:
            agg, zone = calculate_aggressiveness(50, vocab_min=90, vocab_max=30)
            # If it doesn't raise, verify result is clamped
            assert 0.0 <= agg <= 1.0
        except (ValueError, ZeroDivisionError):
            # It's also acceptable to raise an error
            pass

    def test_invalid_profile_name(self):
        """Test with non-existent profile name"""
        with pytest.raises(KeyError):
            calculate_aggressiveness(50, profile="nonexistent")

    def test_float_vocabulary_size(self):
        """Test that float sizes work (should be acceptable)"""
        agg, zone = calculate_aggressiveness(45.5)
        assert isinstance(agg, float)
        assert isinstance(zone, str)


# ============================================================================
# Integration Tests
# ============================================================================


class TestCurveIntegration:
    """Integration tests for complete aggressiveness curve workflow"""

    def test_full_vocabulary_lifecycle(self):
        """
        Simulate vocabulary growing from 30 to 200 types.

        Verify zones transition in expected order.
        """
        zones_seen = []

        for size in range(30, 201, 10):
            _, zone = calculate_aggressiveness(size)
            if not zones_seen or zones_seen[-1] != zone:
                zones_seen.append(zone)

        # Should see zones in this order (may skip some)
        expected_order = ["comfort", "watch", "merge", "mixed", "emergency", "block"]

        # Verify zones appear in order (but may skip some)
        zone_indices = [expected_order.index(z) for z in zones_seen]
        assert zone_indices == sorted(zone_indices), (
            f"Zones should appear in order: {expected_order}, got {zones_seen}"
        )

    def test_batching_scenario(self):
        """
        Test scenario from ADR-032: batching with buffer.

        At 91 types, prune to 85 (excess + buffer) to avoid immediate re-trigger.
        """
        # At 91, should be emergency
        agg_91, zone_91 = calculate_aggressiveness(91)
        assert zone_91 in ["emergency", "block"]
        assert agg_91 > 0.9

        # After pruning to 85, should drop to mixed zone
        agg_85, zone_85 = calculate_aggressiveness(85)
        assert zone_85 in ["mixed", "emergency"]
        assert agg_85 < agg_91

        # After pruning to 80, should be in mixed
        agg_80, zone_80 = calculate_aggressiveness(80)
        assert zone_80 == "mixed"

    def test_aggressive_vs_gentle_comparison(self):
        """
        Compare aggressive and gentle profiles across vocabulary range.

        Aggressive should stay lower longer, then spike.
        Gentle should be more gradual throughout.
        """
        aggressive_values = []
        gentle_values = []

        for size in range(30, 91, 5):
            agg_aggr, _ = calculate_aggressiveness(size, profile="aggressive")
            agg_gent, _ = calculate_aggressiveness(size, profile="gentle")
            aggressive_values.append(agg_aggr)
            gentle_values.append(agg_gent)

        # Early in window, aggressive should be lower
        assert aggressive_values[0] <= gentle_values[0]
        assert aggressive_values[1] <= gentle_values[1]

        # Later in window, aggressive should be higher (sharp acceleration)
        assert aggressive_values[-1] >= gentle_values[-1]


if __name__ == "__main__":
    # Allow running tests directly: python test_aggressiveness_curve.py
    pytest.main([__file__, "-v"])
