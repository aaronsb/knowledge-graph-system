use std::cell::RefCell;
use std::time::Instant;

use graph_accel_core::Graph;

/// Metadata about the loaded graph state.
pub struct GraphState {
    pub graph: Graph,
    pub source_graph: String,
    pub load_time_ms: f64,
    pub loaded_at: Instant,
    /// Generation counter at time of load. 0 = loaded before any invalidation.
    pub loaded_generation: i64,
}

thread_local! {
    /// Per-backend graph state.
    ///
    /// PostgreSQL backends are single-threaded, so thread_local! + RefCell
    /// is safe. Each connection loads its own graph copy.
    /// Shared memory deferred to a future phase.
    static GRAPH_STATE: RefCell<Option<GraphState>> = const { RefCell::new(None) };
}

/// Execute a closure with a read reference to the loaded graph.
/// Returns None if no graph is loaded.
pub fn with_graph<R, F: FnOnce(&GraphState) -> R>(f: F) -> Option<R> {
    GRAPH_STATE.with(|cell| {
        let borrow = cell.borrow();
        borrow.as_ref().map(f)
    })
}

/// Replace the per-backend graph state.
pub fn set_graph(state: GraphState) {
    GRAPH_STATE.with(|cell| {
        *cell.borrow_mut() = Some(state);
    });
}

/// Resolve a node identifier: try app_id first, then parse as AGE graphid.
pub fn resolve_node(graph: &graph_accel_core::Graph, id_str: &str) -> u64 {
    graph
        .resolve_app_id(id_str)
        .or_else(|| {
            id_str
                .parse::<u64>()
                .ok()
                .filter(|id| graph.node(*id).is_some())
        })
        .unwrap_or_else(|| {
            pgrx::error!("graph_accel: node '{}' not found", id_str);
        })
}
