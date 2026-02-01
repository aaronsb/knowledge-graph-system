//! Generation-based cache invalidation for graph_accel.
//!
//! A monotonic generation counter tracks graph mutations. Query functions
//! compare the loaded generation against the current value and optionally
//! auto-reload when stale.
//!
//! Applications call `graph_accel_invalidate(graph_name)` after mutating
//! AGE data. This bumps the counter and fires `pg_notify('graph_accel', graph_name)`
//! so external listeners (monitoring, API layers) can react.
//!
//! Design: generation-based cache invalidation — standard pattern in PostgreSQL
//! internals, Linux kernel inode generations, and database caching literature.

use pgrx::prelude::*;
use pgrx::spi::quote_literal;

use crate::guc;
use crate::state;

// ---------------------------------------------------------------------------
// Bootstrap SQL: schema + generation table, created at CREATE EXTENSION time.
// ---------------------------------------------------------------------------

extension_sql!(
    r#"
CREATE SCHEMA IF NOT EXISTS graph_accel;

CREATE TABLE graph_accel.generation (
    graph_name  text PRIMARY KEY,
    generation  bigint NOT NULL DEFAULT 1,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE graph_accel.generation IS
    'Monotonic generation counter for graph_accel cache invalidation. '
    'Call graph_accel_invalidate(graph_name) after mutating AGE data.';
"#,
    name = "bootstrap",
    bootstrap
);

// ---------------------------------------------------------------------------
// Generation reads
// ---------------------------------------------------------------------------

/// Read the current generation within an existing SPI connection.
/// Returns None if the table is inaccessible; Some(0) if no row exists.
pub fn fetch_generation_spi(
    client: &pgrx::spi::SpiClient<'_>,
    graph_name: &str,
) -> Option<i64> {
    let query = format!(
        "SELECT generation FROM graph_accel.generation WHERE graph_name = {}",
        quote_literal(graph_name)
    );
    match client.select(&query, None, &[]) {
        Ok(table) => {
            for row in table {
                return row
                    .get_by_name::<i64, _>("generation")
                    .ok()
                    .flatten()
                    .or(Some(0));
            }
            Some(0) // No row = never invalidated
        }
        Err(_) => {
            warning!("graph_accel: cannot read generation table, skipping staleness check");
            None
        }
    }
}

/// Read the current generation in a standalone SPI connection.
/// Used by query functions (neighborhood, path) for staleness checks.
pub fn fetch_generation(graph_name: &str) -> Option<i64> {
    match Spi::connect(|client| {
        Ok::<_, pgrx::spi::SpiError>(fetch_generation_spi(&client, graph_name))
    }) {
        Ok(result) => result,
        Err(_) => None,
    }
}

// ---------------------------------------------------------------------------
// Invalidation
// ---------------------------------------------------------------------------

/// Bump the generation counter for a graph and notify listeners.
///
/// Returns the new generation number. Creates the row on first call.
/// Fires `pg_notify('graph_accel', graph_name)` so external tools
/// that `LISTEN graph_accel` can react.
#[pg_extern]
fn graph_accel_invalidate(graph_name: String) -> i64 {
    crate::load::validate_name(&graph_name);

    Spi::connect_mut(|client| {
        let upsert = format!(
            "INSERT INTO graph_accel.generation (graph_name, generation, updated_at) \
             VALUES ({}, 1, now()) \
             ON CONFLICT (graph_name) \
             DO UPDATE SET generation = graph_accel.generation.generation + 1, \
                           updated_at = now() \
             RETURNING generation",
            quote_literal(&graph_name)
        );

        let new_gen: i64 = client
            .update(&upsert, None, &[])?
            .first()
            .get_one::<i64>()?
            .unwrap_or(1);

        // Fire NOTIFY so external listeners can react
        client.update(
            &format!(
                "SELECT pg_notify('graph_accel', {})",
                quote_literal(&graph_name)
            ),
            None,
            &[],
        )?;

        Ok::<_, pgrx::spi::SpiError>(new_gen)
    })
    .unwrap_or_else(|e| {
        error!("graph_accel_invalidate: {}", e);
    })
}

// ---------------------------------------------------------------------------
// Staleness check + auto-reload
// ---------------------------------------------------------------------------

/// Check if the loaded graph is stale and optionally reload.
///
/// Called at the top of every query function. Cost: one SPI SELECT
/// (~0.01-0.05ms) for a single-row PK lookup.
///
/// Behavior:
/// - No graph loaded → return immediately
/// - Generation table inaccessible → skip check, serve loaded graph
/// - Fresh (loaded_generation >= current) → return immediately
/// - Stale + auto_reload=false → return (serve stale)
/// - Stale + auto_reload=true + debounce not elapsed → return (serve stale)
/// - Stale + auto_reload=true + debounce elapsed → reload inline
pub fn ensure_fresh() {
    let (graph_name, loaded_gen, loaded_at) = match state::with_graph(|gs| {
        (
            gs.source_graph.clone(),
            gs.loaded_generation,
            gs.loaded_at,
        )
    }) {
        Some(info) => info,
        None => return,
    };

    let current_gen = match fetch_generation(&graph_name) {
        Some(gen) => gen,
        None => return,
    };

    if loaded_gen >= current_gen {
        return;
    }

    // Stale. Check auto_reload.
    if !guc::AUTO_RELOAD.get() {
        return;
    }

    // Debounce: don't reload more often than reload_debounce_sec.
    let debounce_secs = guc::RELOAD_DEBOUNCE_SEC.get() as u64;
    if debounce_secs > 0 {
        let elapsed = loaded_at.elapsed().as_secs();
        if elapsed < debounce_secs {
            notice!(
                "graph_accel: stale (gen {} vs {}), debouncing ({}/{}s)",
                loaded_gen,
                current_gen,
                elapsed,
                debounce_secs
            );
            return;
        }
    }

    // Reload inline.
    notice!(
        "graph_accel: auto-reloading '{}' (gen {} -> {})",
        graph_name,
        loaded_gen,
        current_gen
    );

    crate::load::do_load(&graph_name);
}
