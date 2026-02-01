use pgrx::prelude::*;

use crate::generation;
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
        name!(loaded_generation, i64),
        name!(current_generation, i64),
        name!(is_stale, bool),
    ),
> {
    let row = if let Some(result) = state::with_graph(|gs| {
        let current_gen = generation::fetch_generation(&gs.source_graph).unwrap_or(0);
        let is_stale = gs.loaded_generation < current_gen;
        let status_str = if is_stale { "stale" } else { "loaded" };

        (
            Some(gs.source_graph.clone()),
            status_str.to_string(),
            gs.graph.node_count() as i64,
            gs.graph.edge_count() as i64,
            gs.graph.memory_usage() as i64,
            gs.graph.rel_type_count() as i32,
            gs.loaded_generation,
            current_gen,
            is_stale,
        )
    }) {
        result
    } else {
        let configured = guc::get_string(&guc::SOURCE_GRAPH);
        let current_gen = configured
            .as_ref()
            .and_then(|name| generation::fetch_generation(name))
            .unwrap_or(0);

        (
            configured,
            "not_loaded".to_string(),
            0,
            0,
            0,
            0,
            0,
            current_gen,
            false,
        )
    };

    TableIterator::once(row)
}
