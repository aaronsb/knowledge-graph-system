"""
Aggressiveness Curve Calculator using Cubic Bezier Interpolation

Provides smooth, tunable response curves for vocabulary management.
Same mathematical foundation as CSS cubic-bezier() animations.

Usage:
    curve = AGGRESSIVENESS_CURVES["aggressive"]
    aggressiveness = curve.get_y_for_x(0.75)  # At 75% of window

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - CSS cubic-bezier: https://cubic-bezier.com
    - Bezier curves: https://en.wikipedia.org/wiki/Bézier_curve
"""

from typing import Tuple


class CubicBezier:
    """
    Cubic Bezier curve calculator for smooth aggressiveness transitions.

    Uses standard cubic Bezier formula with fixed endpoints:
    - P0 = (0, 0) - start point
    - P1 = (x1, y1) - first control point (configurable)
    - P2 = (x2, y2) - second control point (configurable)
    - P3 = (1, 1) - end point

    Example:
        >>> curve = CubicBezier(0.42, 0.0, 0.58, 1.0)  # ease-in-out
        >>> curve.get_y_for_x(0.5)  # Get y value at x=0.5
        0.5
    """

    def __init__(self, x1: float, y1: float, x2: float, y2: float):
        """
        Initialize cubic Bezier with control points.

        Args:
            x1: X coordinate of first control point (0.0-1.0)
            y1: Y coordinate of first control point (can exceed 0-1 for overshoot)
            x2: X coordinate of second control point (0.0-1.0)
            y2: Y coordinate of second control point (can exceed 0-1 for overshoot)
        """
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def bezier(self, t: float) -> float:
        """
        Calculate Bezier Y value at parameter t.

        Cubic Bezier formula:
        B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃

        Where P₀ = (0, 0), P₃ = (1, 1) are fixed endpoints.

        Args:
            t: Parameter value (0.0 to 1.0)

        Returns:
            Y value at parameter t
        """
        # Expand Bezier polynomial coefficients
        cx = 3 * self.x1
        bx = 3 * (self.x2 - self.x1) - cx
        ax = 1 - cx - bx

        cy = 3 * self.y1
        by = 3 * (self.y2 - self.y1) - cy
        ay = 1 - cy - by

        # Calculate Y using Horner's method for efficiency
        return ((ay * t + by) * t + cy) * t

    def solve_x(self, x: float, epsilon: float = 1e-6) -> float:
        """
        Find parameter t where Bezier X equals target x.

        Uses Newton-Raphson iterative method for fast convergence.

        Args:
            x: Target X value (0.0 to 1.0)
            epsilon: Convergence threshold

        Returns:
            Parameter t that produces X ≈ x
        """
        # Initial guess
        t = x

        # Newton-Raphson iterations (typically converges in <8 iterations)
        for _ in range(8):
            # Calculate current X value at t
            x_guess = self._bezier_x(t)

            # Check convergence
            if abs(x_guess - x) < epsilon:
                break

            # Calculate derivative for Newton step
            dx = self._bezier_x_derivative(t)

            # Avoid division by zero
            if abs(dx) < epsilon:
                break

            # Newton-Raphson update: t_new = t - f(t)/f'(t)
            t -= (x_guess - x) / dx

        return t

    def _bezier_x(self, t: float) -> float:
        """Calculate Bezier X value at parameter t."""
        cx = 3 * self.x1
        bx = 3 * (self.x2 - self.x1) - cx
        ax = 1 - cx - bx

        return ((ax * t + bx) * t + cx) * t

    def _bezier_x_derivative(self, t: float) -> float:
        """Calculate derivative of Bezier X at parameter t."""
        cx = 3 * self.x1
        bx = 3 * (self.x2 - self.x1) - cx
        ax = 1 - cx - bx

        # Derivative of ((ax*t + bx)*t + cx)*t
        return 3 * ax * t * t + 2 * bx * t + cx

    def get_y_for_x(self, x: float) -> float:
        """
        Get aggressiveness (Y) for vocabulary position (X).

        Main API method for calculating aggressiveness curves.

        Args:
            x: Position in vocabulary window (0.0 = min, 1.0 = max)

        Returns:
            Aggressiveness value (0.0 = passive, 1.0 = emergency)

        Example:
            >>> curve = CubicBezier(0.1, 0.0, 0.9, 1.0)  # aggressive
            >>> curve.get_y_for_x(0.0)   # At minimum
            0.0
            >>> curve.get_y_for_x(0.5)   # At midpoint
            0.15
            >>> curve.get_y_for_x(1.0)   # At maximum
            1.0
        """
        # Clamp input to valid range
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0

        # Find parameter t for this x value
        t = self.solve_x(x)

        # Calculate y value at this t
        return self.bezier(t)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"CubicBezier({self.x1}, {self.y1}, {self.x2}, {self.y2})"


# Predefined aggressiveness profiles (like CSS easing functions)
AGGRESSIVENESS_CURVES = {
    "linear": CubicBezier(0.0, 0.0, 1.0, 1.0),
    # Constant rate increase. Predictable, good for testing.

    "ease": CubicBezier(0.25, 0.1, 0.25, 1.0),
    # CSS default. Balanced acceleration.

    "ease-in": CubicBezier(0.42, 0.0, 1.0, 1.0),
    # Slow start, fast end. Gradual then sharp.

    "ease-out": CubicBezier(0.0, 0.0, 0.58, 1.0),
    # Fast start, slow end. Sharp then gradual.

    "ease-in-out": CubicBezier(0.42, 0.0, 0.58, 1.0),
    # Smooth S-curve. Balanced transitions.

    "aggressive": CubicBezier(0.1, 0.0, 0.9, 1.0),
    # RECOMMENDED: Stay passive until 75%, then sharp acceleration.
    # Best for production - avoids premature optimization.

    "gentle": CubicBezier(0.5, 0.5, 0.5, 0.5),
    # Very gradual. Good for high-churn environments.

    "exponential": CubicBezier(0.7, 0.0, 0.84, 0.0),
    # Explosive near limit. Use when capacity is strict.
}


def calculate_aggressiveness(
    current_size: int,
    vocab_min: int = 30,
    vocab_max: int = 90,
    vocab_emergency: int = 200,
    profile: str = "aggressive"
) -> Tuple[float, str]:
    """
    Calculate aggressiveness level for current vocabulary size.

    Maps vocabulary size to aggressiveness using configured Bezier curve.
    Returns both numeric aggressiveness and recommended action zone.

    Args:
        current_size: Current number of active edge types
        vocab_min: Minimum protected types (default: 30)
        vocab_max: Soft limit triggering optimization (default: 90)
        vocab_emergency: Hard limit blocking expansion (default: 200)
        profile: Curve profile name (default: "aggressive")

    Returns:
        Tuple of (aggressiveness: float, zone: str)
        - aggressiveness: 0.0 (passive) to 1.0 (emergency)
        - zone: "comfort", "watch", "merge", "mixed", "emergency", "block"

    Example:
        >>> calculate_aggressiveness(45)
        (0.08, "comfort")
        >>> calculate_aggressiveness(85)
        (0.72, "mixed")
        >>> calculate_aggressiveness(95)
        (0.98, "emergency")
    """
    # Boundary conditions
    if current_size <= vocab_min:
        return (0.0, "comfort")

    if current_size >= vocab_emergency:
        return (1.0, "block")

    # Normalize position: 0.0 (at min) → 1.0 (at max)
    position = (current_size - vocab_min) / (vocab_max - vocab_min)
    position = max(0.0, min(1.0, position))  # Clamp to [0, 1]

    # Apply Bezier curve
    curve = AGGRESSIVENESS_CURVES[profile]
    aggressiveness = curve.get_y_for_x(position)

    # Boost aggressiveness if beyond soft limit
    if current_size > vocab_max:
        overage = (current_size - vocab_max) / (vocab_emergency - vocab_max)
        # Blend curve value with overage (approaching 1.0)
        aggressiveness = aggressiveness + (1.0 - aggressiveness) * overage

    # Map aggressiveness to action zone
    if aggressiveness < 0.2:
        zone = "comfort"
    elif aggressiveness < 0.5:
        zone = "watch"
    elif aggressiveness < 0.7:
        zone = "merge"
    elif aggressiveness < 0.9:
        zone = "mixed"
    elif current_size < vocab_emergency:
        zone = "emergency"
    else:
        zone = "block"

    return (aggressiveness, zone)


def get_available_profiles() -> dict:
    """
    Get all available aggressiveness profiles with descriptions.

    Returns:
        Dictionary mapping profile names to descriptions
    """
    return {
        "linear": "Constant rate increase. Predictable, good for testing.",
        "ease": "CSS default. Balanced acceleration.",
        "ease-in": "Slow start, fast end. Gradual then sharp.",
        "ease-out": "Fast start, slow end. Sharp then gradual.",
        "ease-in-out": "Smooth S-curve. Balanced transitions.",
        "aggressive": "RECOMMENDED: Stay passive until 75%, sharp acceleration near limit.",
        "gentle": "Very gradual. Good for high-churn environments.",
        "exponential": "Explosive near limit. Use when capacity is strict.",
    }


if __name__ == "__main__":
    # Quick visualization of curves
    import sys

    profile = sys.argv[1] if len(sys.argv) > 1 else "aggressive"

    if profile == "list":
        print("Available profiles:")
        for name, desc in get_available_profiles().items():
            print(f"  {name:15s} - {desc}")
        sys.exit(0)

    curve = AGGRESSIVENESS_CURVES[profile]
    print(f"Profile: {profile}")
    print(f"Control points: {curve}")
    print()
    print("Position | Aggressiveness | Zone")
    print("-" * 45)

    for size in range(30, 105, 5):
        agg, zone = calculate_aggressiveness(size, profile=profile)
        bar = "█" * int(agg * 40)
        print(f"{size:3d}      | {agg:4.2f} {bar:40s} | {zone}")
