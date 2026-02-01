use graph_accel_core::{Direction, TraversalDirection};
use pgrx::prelude::*;

/// Parse a direction filter string into a TraversalDirection.
///
/// Accepts: "outgoing", "incoming", "both" (case-insensitive).
/// Raises a PostgreSQL ERROR for unrecognized values.
pub fn parse_direction(s: &str) -> TraversalDirection {
    match s.to_lowercase().as_str() {
        "outgoing" | "out" => TraversalDirection::Outgoing,
        "incoming" | "in" => TraversalDirection::Incoming,
        "both" => TraversalDirection::Both,
        other => {
            error!(
                "graph_accel: invalid direction_filter '{}' — use 'outgoing', 'incoming', or 'both'",
                other
            );
        }
    }
}

/// Convert an edge Direction to its SQL string representation.
pub fn direction_str(d: Direction) -> String {
    match d {
        Direction::Outgoing => "outgoing".to_string(),
        Direction::Incoming => "incoming".to_string(),
    }
}

/// Validate that a depth/hops parameter is non-negative.
/// Raises a PostgreSQL ERROR if negative.
pub fn check_non_negative(value: i32, param_name: &str) -> u32 {
    if value < 0 {
        error!(
            "graph_accel: {} must be non-negative, got {}",
            param_name, value
        );
    }
    value as u32
}
