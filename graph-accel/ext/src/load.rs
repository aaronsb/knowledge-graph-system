use std::time::Instant;

use graph_accel_core::Graph;
use pgrx::prelude::*;

use crate::guc;
use crate::state::{self, GraphState};

#[pg_extern]
fn graph_accel_load(
    graph_name: default!(Option<String>, "NULL"),
) -> TableIterator<
    'static,
    (
        name!(node_count, i64),
        name!(edge_count, i64),
        name!(load_time_ms, f64),
    ),
> {
    let start = Instant::now();

    // Resolve graph name: explicit argument > GUC > error
    let gname = graph_name
        .or_else(|| guc::get_string(&guc::SOURCE_GRAPH))
        .unwrap_or_else(|| {
            error!("graph_accel: source_graph not set and no graph_name argument provided");
        });

    let (node_count, edge_count) = Spi::connect(|client| {
        // Verify graph exists
        let exists = client
            .select(
                &format!(
                    "SELECT 1 FROM ag_catalog.ag_graph WHERE name = '{}'",
                    sanitize_ident(&gname)
                ),
                None,
                &[],
            )?
            .next()
            .is_some();

        if !exists {
            error!("graph_accel: AGE graph '{}' does not exist", gname);
        }

        // Get label catalog for this graph
        let labels = load_label_catalog(&client, &gname)?;

        // Parse GUC filters
        let node_label_filter = parse_filter(
            &guc::get_string(&guc::NODE_LABELS).unwrap_or_else(|| "*".to_string()),
        );
        let edge_type_filter = parse_filter(
            &guc::get_string(&guc::EDGE_TYPES).unwrap_or_else(|| "*".to_string()),
        );
        let node_id_prop = guc::get_string(&guc::NODE_ID_PROPERTY);

        let mut graph = Graph::new();

        // Load vertices
        for label in labels.iter().filter(|l| l.kind == 'v') {
            if !matches_filter(&label.name, &node_label_filter) {
                continue;
            }
            load_vertices(
                &client,
                &gname,
                &label.name,
                node_id_prop.as_deref(),
                &mut graph,
            )?;
        }

        // Load edges
        for label in labels.iter().filter(|l| l.kind == 'e') {
            if !matches_filter(&label.name, &edge_type_filter) {
                continue;
            }
            load_edges(&client, &gname, &label.name, &mut graph)?;
        }

        // Check memory limit
        let memory_mb = graph.memory_usage() / (1024 * 1024);
        let max_mb = guc::MAX_MEMORY_MB.get() as usize;
        if memory_mb > max_mb {
            error!(
                "graph_accel: loaded graph uses {}MB, exceeds graph_accel.max_memory_mb={}MB",
                memory_mb, max_mb
            );
        }

        let nc = graph.node_count() as i64;
        let ec = graph.edge_count() as i64;

        state::set_graph(GraphState {
            graph,
            source_graph: gname,
            load_time_ms: start.elapsed().as_secs_f64() * 1000.0,
            loaded_at: Instant::now(),
        });

        Ok::<_, pgrx::spi::SpiError>((nc, ec))
    })
    .unwrap_or_else(|e| {
        error!("graph_accel_load: SPI error: {}", e);
    });

    let load_time_ms = start.elapsed().as_secs_f64() * 1000.0;
    TableIterator::once((node_count, edge_count, load_time_ms))
}

// ---------------------------------------------------------------------------
// Label catalog
// ---------------------------------------------------------------------------

struct LabelInfo {
    name: String,
    kind: char,
}

fn load_label_catalog(
    client: &pgrx::spi::SpiClient<'_>,
    graph_name: &str,
) -> Result<Vec<LabelInfo>, pgrx::spi::SpiError> {
    let query = format!(
        "SELECT l.name, l.kind::text \
         FROM ag_catalog.ag_label l \
         JOIN ag_catalog.ag_graph g ON l.graph = g.graphid \
         WHERE g.name = '{}' \
           AND l.name NOT LIKE '_ag%%'",
        sanitize_ident(graph_name)
    );

    let mut labels = Vec::new();
    let table = client.select(&query, None, &[])?;
    for row in table {
        let name: String = row
            .get_by_name("name")
            .unwrap_or_else(|e| error!("graph_accel: failed to read label name: {}", e))
            .unwrap_or_default();
        let kind_str: String = row
            .get_by_name("kind")
            .unwrap_or_else(|e| error!("graph_accel: failed to read label kind: {}", e))
            .unwrap_or_default();
        let kind = kind_str.chars().next().unwrap_or('?');
        labels.push(LabelInfo { name, kind });
    }

    Ok(labels)
}

// ---------------------------------------------------------------------------
// Vertex loading
// ---------------------------------------------------------------------------

fn load_vertices(
    client: &pgrx::spi::SpiClient<'_>,
    graph_name: &str,
    label_name: &str,
    node_id_prop: Option<&str>,
    graph: &mut Graph,
) -> Result<(), pgrx::spi::SpiError> {
    let query = format!(
        "SELECT id::text, properties::text FROM {}.\"{}\"",
        sanitize_ident(graph_name),
        sanitize_ident(label_name)
    );

    let table = client.select(&query, None, &[])?;
    for row in table {
        let id_str: Option<String> = row.get_by_name("id")?;
        let props_str: Option<String> = row.get_by_name("properties")?;

        let Some(id_str) = id_str else { continue };
        let node_id: u64 = match id_str.parse() {
            Ok(id) => id,
            Err(_) => continue,
        };

        let app_id = node_id_prop.and_then(|prop| {
            props_str
                .as_deref()
                .and_then(|json| extract_json_string(json, prop))
        });

        graph.add_node(node_id, label_name.to_string(), app_id);
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Edge loading
// ---------------------------------------------------------------------------

fn load_edges(
    client: &pgrx::spi::SpiClient<'_>,
    graph_name: &str,
    label_name: &str,
    graph: &mut Graph,
) -> Result<(), pgrx::spi::SpiError> {
    let rel_type_id = graph.intern_rel_type(label_name);

    let query = format!(
        "SELECT start_id::text, end_id::text FROM {}.\"{}\"",
        sanitize_ident(graph_name),
        sanitize_ident(label_name)
    );

    let table = client.select(&query, None, &[])?;
    for row in table {
        let from_str: Option<String> = row.get_by_name("start_id")?;
        let to_str: Option<String> = row.get_by_name("end_id")?;

        let (Some(from_str), Some(to_str)) = (from_str, to_str) else {
            continue;
        };

        let from_id: u64 = match from_str.parse() {
            Ok(id) => id,
            Err(_) => continue,
        };
        let to_id: u64 = match to_str.parse() {
            Ok(id) => id,
            Err(_) => continue,
        };

        graph.add_edge(from_id, to_id, rel_type_id);
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Extract a string value from a JSON object by key.
fn extract_json_string(json: &str, key: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(json).ok()?;
    value
        .get(key)
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// Validate an identifier contains only safe characters.
fn sanitize_ident(name: &str) -> &str {
    assert!(
        !name.is_empty() && name.chars().all(|c| c.is_alphanumeric() || c == '_'),
        "graph_accel: invalid identifier: '{}'",
        name
    );
    name
}

enum Filter {
    All,
    Set(Vec<String>),
}

fn parse_filter(spec: &str) -> Filter {
    if spec.trim() == "*" {
        Filter::All
    } else {
        Filter::Set(
            spec.split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect(),
        )
    }
}

fn matches_filter(name: &str, filter: &Filter) -> bool {
    match filter {
        Filter::All => true,
        Filter::Set(names) => names.iter().any(|n| n == name),
    }
}
