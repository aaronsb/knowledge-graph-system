use graph_accel_core::Direction;
use pgrx::prelude::*;

use crate::state;

fn direction_str(d: Direction) -> String {
    match d {
        Direction::Outgoing => "outgoing".to_string(),
        Direction::Incoming => "incoming".to_string(),
    }
}

#[pg_extern]
fn graph_accel_neighborhood(
    start_id: String,
    max_depth: default!(i32, 3),
    direction_filter: default!(String, "'both'"),
    min_confidence: default!(Option<f64>, "NULL"),
) -> TableIterator<
    'static,
    (
        name!(node_id, i64),
        name!(label, String),
        name!(app_id, Option<String>),
        name!(distance, i32),
        name!(path_types, Vec<String>),
        name!(path_directions, Vec<String>),
    ),
> {
    crate::generation::ensure_fresh();
    let direction = crate::util::parse_direction(&direction_filter);

    let results = state::with_graph(|gs| {
        let internal_id = state::resolve_node(&gs.graph, &start_id);

        let result =
            graph_accel_core::bfs_neighborhood(&gs.graph, internal_id, max_depth as u32, direction, min_confidence.map(|v| v as f32));

        result
            .neighbors
            .into_iter()
            .map(|nr| {
                let dirs = nr.path_directions.into_iter().map(direction_str).collect();
                (
                    nr.node_id as i64,
                    nr.label,
                    nr.app_id,
                    nr.distance as i32,
                    nr.path_types,
                    dirs,
                )
            })
            .collect::<Vec<_>>()
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}
