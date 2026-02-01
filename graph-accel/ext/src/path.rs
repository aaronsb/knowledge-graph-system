use pgrx::prelude::*;

use crate::state;
use crate::util::direction_str;

#[pg_extern]
fn graph_accel_path(
    from_id: String,
    to_id: String,
    max_hops: default!(i32, 10),
    direction_filter: default!(String, "'both'"),
    min_confidence: default!(Option<f64>, "NULL"),
) -> TableIterator<
    'static,
    (
        name!(step, i32),
        name!(node_id, i64),
        name!(label, String),
        name!(app_id, Option<String>),
        name!(rel_type, Option<String>),
        name!(direction, Option<String>),
    ),
> {
    crate::generation::ensure_fresh();
    let direction = crate::util::parse_direction(&direction_filter);
    let hops = crate::util::check_non_negative(max_hops, "max_hops");

    let results = state::with_graph(|gs| {
        let start = state::resolve_node(&gs.graph, &from_id);
        let target = state::resolve_node(&gs.graph, &to_id);

        match graph_accel_core::shortest_path(&gs.graph, start, target, hops, direction, min_confidence.map(|v| v as f32)) {
            Some(path) => path
                .into_iter()
                .enumerate()
                .map(|(i, s)| {
                    let dir = s.direction.map(direction_str);
                    (i as i32, s.node_id as i64, s.label, s.app_id, s.rel_type, dir)
                })
                .collect::<Vec<_>>(),
            None => Vec::new(),
        }
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}
