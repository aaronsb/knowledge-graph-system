use graph_accel_core::TraversalDirection;
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
