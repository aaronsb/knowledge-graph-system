//! graph_accel: PostgreSQL extension for in-memory graph traversal acceleration.
//!
//! Wraps graph-accel-core to provide SQL functions for BFS neighborhood
//! traversal and shortest path queries against Apache AGE graphs.
//! Per-backend state with generation-based cache invalidation.

use pgrx::prelude::*;

mod degree;
mod generation;
mod guc;
mod load;
mod neighborhood;
mod path;
mod state;
mod status;
mod subgraph;
mod util;

pg_module_magic!();

#[allow(non_snake_case)]
#[pg_guard]
pub extern "C-unwind" fn _PG_init() {
    guc::register_gucs();
}

#[cfg(any(test, feature = "pg_test"))]
#[pg_schema]
mod tests {
    use pgrx::prelude::*;

    #[pg_test]
    fn test_status_returns_not_loaded() {
        let result = Spi::get_one::<String>("SELECT status FROM graph_accel_status()");
        assert_eq!(result, Ok(Some("not_loaded".to_string())));
    }

    #[pg_test]
    fn test_guc_defaults() {
        let max_mem =
            Spi::get_one::<String>("SHOW graph_accel.max_memory_mb");
        assert_eq!(max_mem, Ok(Some("4096".to_string())));
    }

    #[pg_test]
    fn test_invalidate_returns_generation() {
        let gen = Spi::get_one::<i64>("SELECT graph_accel_invalidate('test_graph')");
        assert_eq!(gen, Ok(Some(1)));

        let gen2 = Spi::get_one::<i64>("SELECT graph_accel_invalidate('test_graph')");
        assert_eq!(gen2, Ok(Some(2)));
    }

    #[pg_test]
    fn test_invalidate_separate_graphs() {
        let g1 = Spi::get_one::<i64>("SELECT graph_accel_invalidate('graph_a')");
        let g2 = Spi::get_one::<i64>("SELECT graph_accel_invalidate('graph_b')");
        assert_eq!(g1, Ok(Some(1)));
        assert_eq!(g2, Ok(Some(1)));

        let g1_again = Spi::get_one::<i64>("SELECT graph_accel_invalidate('graph_a')");
        assert_eq!(g1_again, Ok(Some(2)));
    }
}

#[cfg(test)]
pub mod pg_test {
    pub fn setup(_options: Vec<&str>) {}

    pub fn postgresql_conf_options() -> Vec<&'static str> {
        vec![]
    }
}
