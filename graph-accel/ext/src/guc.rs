use std::ffi::CString;

use pgrx::guc::*;

pub static SOURCE_GRAPH: GucSetting<Option<CString>> =
    GucSetting::<Option<CString>>::new(None);

pub static MAX_MEMORY_MB: GucSetting<i32> = GucSetting::<i32>::new(4096);

pub static NODE_ID_PROPERTY: GucSetting<Option<CString>> =
    GucSetting::<Option<CString>>::new(None);

pub static NODE_LABELS: GucSetting<Option<CString>> =
    GucSetting::<Option<CString>>::new(Some(c"*"));

pub static EDGE_TYPES: GucSetting<Option<CString>> =
    GucSetting::<Option<CString>>::new(Some(c"*"));

pub static AUTO_RELOAD: GucSetting<bool> = GucSetting::<bool>::new(true);

pub static RELOAD_DEBOUNCE_SEC: GucSetting<i32> = GucSetting::<i32>::new(5);

/// Read a string GUC, returning None if unset or empty.
pub fn get_string(setting: &GucSetting<Option<CString>>) -> Option<String> {
    setting
        .get()
        .and_then(|cs| cs.into_string().ok())
        .filter(|s| !s.is_empty())
}

pub fn register_gucs() {
    GucRegistry::define_string_guc(
        c"graph_accel.source_graph",
        c"AGE graph name to load",
        c"Name of the Apache AGE graph to accelerate. Required for graph_accel_load().",
        &SOURCE_GRAPH,
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_int_guc(
        c"graph_accel.max_memory_mb",
        c"Maximum memory for in-memory graph (MB)",
        c"Per-backend memory cap. graph_accel_load() will error if the graph exceeds this. \
          Changes to Postmaster context in Phase 3 (shared memory).",
        &MAX_MEMORY_MB,
        64,
        131072, // 128 GB
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.node_id_property",
        c"Node property for application-level ID",
        c"Property name to index for app-level lookups (e.g. concept_id). Empty = AGE IDs only.",
        &NODE_ID_PROPERTY,
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.node_labels",
        c"Comma-separated node labels to load, or * for all",
        c"Filter which vertex labels to load into the in-memory graph.",
        &NODE_LABELS,
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.edge_types",
        c"Comma-separated edge types to load, or * for all",
        c"Filter which relationship types to load into the in-memory graph.",
        &EDGE_TYPES,
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_bool_guc(
        c"graph_accel.auto_reload",
        c"Automatically reload when epoch mismatch detected",
        c"When true, stale detection triggers reload. (Phase 3 — registered but not wired.)",
        &AUTO_RELOAD,
        GucContext::Sighup,
        GucFlags::default(),
    );

    GucRegistry::define_int_guc(
        c"graph_accel.reload_debounce_sec",
        c"Minimum seconds between reloads",
        c"Prevents thrashing during bulk ingestion. (Phase 3 — registered but not wired.)",
        &RELOAD_DEBOUNCE_SEC,
        0,
        3600, // 1 hour
        GucContext::Sighup,
        GucFlags::default(),
    );
}
