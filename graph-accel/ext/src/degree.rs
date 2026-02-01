use pgrx::prelude::*;

use crate::state;

#[pg_extern]
fn graph_accel_degree(
    top_n: default!(i32, 100),
) -> TableIterator<
    'static,
    (
        name!(node_id, i64),
        name!(label, String),
        name!(app_id, Option<String>),
        name!(out_degree, i32),
        name!(in_degree, i32),
        name!(total_degree, i32),
    ),
> {
    crate::generation::ensure_fresh();

    let results = state::with_graph(|gs| {
        graph_accel_core::degree_centrality(&gs.graph, top_n as usize)
            .into_iter()
            .map(|dr| {
                (
                    dr.node_id as i64,
                    dr.label,
                    dr.app_id,
                    dr.out_degree as i32,
                    dr.in_degree as i32,
                    dr.total_degree as i32,
                )
            })
            .collect::<Vec<_>>()
    })
    .unwrap_or_else(|| {
        error!("graph_accel: no graph loaded — call graph_accel_load() first");
    });

    TableIterator::new(results)
}
