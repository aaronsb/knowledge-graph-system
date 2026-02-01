use std::cell::RefCell;
use std::time::Instant;

use graph_accel_core::Graph;

/// Metadata about the loaded graph state.
pub struct GraphState {
    pub graph: Graph,
    pub source_graph: String,
    pub load_time_ms: f64,
    pub loaded_at: Instant,
}

thread_local! {
    /// Per-backend graph state.
    ///
    /// PostgreSQL backends are single-threaded, so thread_local! + RefCell
    /// is safe. Each connection loads its own graph copy.
    /// Shared memory deferred to Phase 3.
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
