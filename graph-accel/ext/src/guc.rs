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
    // Userset context: per-session SET. Shared memory phase will tighten
    // to Sighup/Postmaster where appropriate.
    GucRegistry::define_string_guc(
        c"graph_accel.source_graph",
        c"AGE graph name to load",
        c"Name of the Apache AGE graph to accelerate. Required for graph_accel_load().",
        &SOURCE_GRAPH,
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_int_guc(
        c"graph_accel.max_memory_mb",
        c"Maximum memory for in-memory graph (MB)",
        c"Per-backend memory cap. graph_accel_load() will error if the graph exceeds this.",
        &MAX_MEMORY_MB,
        64,
        131072, // 128 GB
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.node_id_property",
        c"Node property for application-level ID",
        c"Property name to index for app-level lookups (e.g. concept_id). Empty = AGE IDs only.",
        &NODE_ID_PROPERTY,
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.node_labels",
        c"Comma-separated node labels to load, or * for all",
        c"Filter which vertex labels to load into the in-memory graph.",
        &NODE_LABELS,
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_string_guc(
        c"graph_accel.edge_types",
        c"Comma-separated edge types to load, or * for all",
        c"Filter which relationship types to load into the in-memory graph.",
        &EDGE_TYPES,
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_bool_guc(
        c"graph_accel.auto_reload",
        c"Automatically reload when generation mismatch detected",
        c"When true, query functions check the generation table and reload inline if stale.",
        &AUTO_RELOAD,
        GucContext::Userset,
        GucFlags::default(),
    );

    GucRegistry::define_int_guc(
        c"graph_accel.reload_debounce_sec",
        c"Minimum seconds between auto-reloads",
        c"Prevents reload thrashing during bulk writes. 0 disables debouncing.",
        &RELOAD_DEBOUNCE_SEC,
        0,
        3600, // 1 hour
        GucContext::Userset,
        GucFlags::default(),
    );
}
