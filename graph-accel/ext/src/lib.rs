//! graph_accel: PostgreSQL extension for in-memory graph traversal acceleration.
//!
//! Wraps graph-accel-core to provide SQL functions for BFS neighborhood
//! traversal and shortest path queries against Apache AGE graphs.
//! Phase 2: per-backend state, no shared memory.

use pgrx::prelude::*;

mod guc;
mod load;
mod neighborhood;
mod path;
mod state;
mod status;

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
}

#[cfg(test)]
pub mod pg_test {
    pub fn setup(_options: Vec<&str>) {}

    pub fn postgresql_conf_options() -> Vec<&'static str> {
        vec![]
    }
}
