use pgrx::prelude::*;

use crate::state;

#[pg_extern]
fn graph_accel_subgraph(
    start_id: String,
    max_depth: default!(i32, 3),
    direction_filter: default!(String, "'both'"),
    min_confidence: default!(Option<f64>, "NULL"),
) -> TableIterator<
    'static,
    (
        name!(from_id, i64),
        name!(from_label, String),
        name!(from_app_id, Option<String>),
        name!(to_id, i64),
        name!(to_label, String),
        name!(to_app_id, Option<String>),
        name!(rel_type, String),
    ),
> {
    crate::generation::ensure_fresh();
    let direction = crate::util::parse_direction(&direction_filter);

    let results = state::with_graph(|gs| {
        let internal_id = state::resolve_node(&gs.graph, &start_id);

        let sub = graph_accel_core::extract_subgraph(&gs.graph, internal_id, max_depth as u32, direction, min_confidence.map(|v| v as f32));

        sub.edges
            .into_iter()
            .map(|e| {
                (
                    e.from_id as i64,
                    e.from_label,
                    e.from_app_id,
                    e.to_id as i64,
                    e.to_label,
                    e.to_app_id,
                    e.rel_type,
                )
            })
            .collect::<Vec<_>>()
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}
