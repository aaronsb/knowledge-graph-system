use pgrx::prelude::*;

use crate::state;

#[pg_extern]
fn graph_accel_path(
    from_id: String,
    to_id: String,
    max_hops: default!(i32, 10),
) -> TableIterator<
    'static,
    (
        name!(step, i32),
        name!(node_id, i64),
        name!(label, String),
        name!(app_id, Option<String>),
        name!(rel_type, Option<String>),
    ),
> {
    crate::generation::ensure_fresh();

    let results = state::with_graph(|gs| {
        let start = state::resolve_node(&gs.graph, &from_id);
        let target = state::resolve_node(&gs.graph, &to_id);

        match graph_accel_core::shortest_path(&gs.graph, start, target, max_hops as u32) {
            Some(path) => path
                .into_iter()
                .enumerate()
                .map(|(i, s)| (i as i32, s.node_id as i64, s.label, s.app_id, s.rel_type))
                .collect::<Vec<_>>(),
            None => Vec::new(),
        }
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}
