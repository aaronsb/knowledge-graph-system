---
match: regex
pattern: \bgraph.accel\b|\bgraph_accel\b|\.so\b.*pgrx|pgrx|traversal\.rs|bfs_neighborhood|graph_accel_load|graph_accel_neighborhood|graph_accel_path|graph_accel_subgraph|graph_accel_degree
files: graph-accel/
commands: cargo\s+(test|build|pgrx)
---
# graph_accel Way

Rust pgrx PostgreSQL extension for in-memory graph acceleration.

## Architecture

- **Core** (`graph-accel/core/`): Pure Rust graph algorithms (BFS, k-shortest, degree, subgraph). No pgrx dependency — testable with `cargo test`.
- **Ext** (`graph-accel/ext/`): pgrx wrapper — SPI loading, GUC handling, thread-local state. Needs `cargo pgrx test pg17`.
- **State**: Per-backend (thread_local). Each PostgreSQL connection has its own in-memory graph copy.
- **Generation**: Monotonic counter in `graph_accel.generation` table drives cache invalidation via `ensure_fresh()`.

## Build & Deploy

```bash
./graph-accel/build-in-container.sh          # Canonical build (ABI-safe)
./graph-accel/tests/deploy-option0.sh        # Copy .so into running container
```

Output: `dist/pg17/{amd64,arm64}/graph_accel.so`

## Testing

```bash
cd graph-accel && cargo test                 # Core unit tests (fast, no PG)
cd graph-accel && cargo pgrx test pg17       # Full pgrx tests (needs PG)
```

## Debugging with SQL

Always use `operator.sh query` (not docker exec):

```bash
# Check status
./operator.sh query "SELECT * FROM graph_accel_status()"

# Load with specific GUCs
./operator.sh query "
SET graph_accel.node_id_property = 'concept_id';
SET graph_accel.node_labels = 'Concept';
SET graph_accel.edge_types = 'SUBSUMES,REQUIRES';
SELECT * FROM graph_accel_load('knowledge_graph');
"
```

**Long GUC values**: Build in SQL, not shell variables. Shell interpolation
can silently truncate long strings:

```sql
-- GOOD: build in SQL
DO $$
DECLARE edge_csv text;
BEGIN
    SELECT string_agg(name, ',') INTO edge_csv FROM ag_catalog.ag_label ...;
    EXECUTE format('SET graph_accel.edge_types = %L', edge_csv);
END $$;

-- BAD: shell variable (can mangle 4000+ char strings)
./operator.sh query "SET graph_accel.edge_types = '$SHELL_VAR'"
```

## Parameter Passing Pitfalls

**NULL vs NaN for Optional parameters**: graph_accel SQL functions use
`Option<f64>` for optional thresholds (min_confidence, etc.).

| Python value | SQL wire | Rust `Option<f64>` | Behavior |
|---|---|---|---|
| `None` | `NULL` | `None` | Filter skipped (correct) |
| `float('nan')` | `'NaN'::float8` | `Some(NaN)` | `x >= NaN` is always false — **rejects all edges** |
| `0.5` | `0.5` | `Some(0.5)` | Normal threshold filter |

Never use `float('nan')` as a "no filter" sentinel. Pass `None`.

## GUCs

| GUC | Default | Purpose |
|-----|---------|---------|
| `graph_accel.source_graph` | (none) | AGE graph name |
| `graph_accel.node_labels` | `*` | Comma-separated vertex labels to load |
| `graph_accel.edge_types` | `*` | Comma-separated edge types to load |
| `graph_accel.node_id_property` | (none) | Property for app-level ID index |
| `graph_accel.auto_reload` | `on` | Auto-reload on generation mismatch |
| `graph_accel.max_memory_mb` | `4096` | Per-backend memory cap |

## Python Facade Integration

`GraphFacade` in `api/app/lib/graph_facade.py` manages graph_accel via a
dedicated pinned connection (`_accel_conn`). The load sequence:

1. `graph_accel_status()` — triggers library loading, registers GUCs
2. `_set_accel_gucs()` — sets node_labels, edge_types filters
3. `graph_accel_load()` — loads filtered graph into backend memory
4. Query functions — `ensure_fresh()` handles generation-based reload
