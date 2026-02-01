use pgrx::prelude::*;

use crate::guc;
use crate::state;

#[pg_extern]
fn graph_accel_status() -> TableIterator<
    'static,
    (
        name!(source_graph, Option<String>),
        name!(status, String),
        name!(node_count, i64),
        name!(edge_count, i64),
        name!(memory_bytes, i64),
        name!(rel_type_count, i32),
    ),
> {
    let row = if let Some(result) = state::with_graph(|gs| {
        (
            Some(gs.source_graph.clone()),
            "loaded".to_string(),
            gs.graph.node_count() as i64,
            gs.graph.edge_count() as i64,
            gs.graph.memory_usage() as i64,
            gs.graph.rel_type_count() as i32,
        )
    }) {
        result
    } else {
        let configured = guc::get_string(&guc::SOURCE_GRAPH);
        (configured, "not_loaded".to_string(), 0, 0, 0, 0)
    };

    TableIterator::once(row)
}
