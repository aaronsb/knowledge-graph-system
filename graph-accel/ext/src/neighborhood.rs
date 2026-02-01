use pgrx::prelude::*;

use crate::state;

#[pg_extern]
fn graph_accel_neighborhood(
    start_id: String,
    max_depth: default!(i32, 3),
) -> TableIterator<
    'static,
    (
        name!(node_id, i64),
        name!(label, String),
        name!(app_id, Option<String>),
        name!(distance, i32),
        name!(path_types, Vec<String>),
    ),
> {
    let results = state::with_graph(|gs| {
        let internal_id = resolve_node(&gs.graph, &start_id);

        let result =
            graph_accel_core::bfs_neighborhood(&gs.graph, internal_id, max_depth as u32);

        result
            .neighbors
            .into_iter()
            .map(|nr| {
                (
                    nr.node_id as i64,
                    nr.label,
                    nr.app_id,
                    nr.distance as i32,
                    nr.path_types,
                )
            })
            .collect::<Vec<_>>()
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}

/// Resolve a node identifier: try app_id first, then parse as AGE graphid.
fn resolve_node(graph: &graph_accel_core::Graph, id_str: &str) -> u64 {
    graph
        .resolve_app_id(id_str)
        .or_else(|| {
            id_str
                .parse::<u64>()
                .ok()
                .filter(|id| graph.node(*id).is_some())
        })
        .unwrap_or_else(|| {
            error!("graph_accel: node '{}' not found", id_str);
        })
}
