# graph_accel Design

Technical design document for contributors and reviewers.

## Architecture

graph_accel uses a dual build target: the core traversal engine is a pure Rust library with no PostgreSQL dependencies, compiled into both a pgrx extension and a standalone benchmark binary.

```
                          graph-accel-core (pure Rust, zero deps)
                         /                    \
           graph-accel-ext                graph-accel-bench
           (pgrx cdylib)                 (standalone binary)
                |                              |
         graph_accel.so                 graph_accel_bench
         (PostgreSQL extension)         (6-topology benchmark)
```

This separation enables:

- **Testing at scale without Postgres.** The benchmark binary generates 5M-node graphs and profiles traversal in isolation. Most development iteration happens here.
- **Profiling outside the Postgres process model.** Standard Rust profiling tools (perf, flamegraph) work directly on the binary without the overhead of Postgres startup and SPI.
- **CI without infrastructure.** Unit tests and benchmark regressions run against the core library, no database required.

The extension is a thin wrapper: 602 lines of Rust that handles SPI loading, GUC registration, node ID resolution, and SQL function bindings. The core engine (771 lines) owns all data structures and algorithms.

## Data Structures

### Graph

The central structure is a bidirectional adjacency list backed by `HashMap`:

```rust
pub struct Graph {
    outgoing: HashMap<NodeId, Vec<Edge>>,    // node → [outgoing edges]
    incoming: HashMap<NodeId, Vec<Edge>>,    // node → [incoming edges]
    nodes: HashMap<NodeId, NodeInfo>,        // node → metadata
    app_id_index: HashMap<String, NodeId>,   // app-level ID → node
    rel_types: Vec<String>,                  // interned type names
    rel_type_map: HashMap<String, RelTypeId>,// type name → index
}
```

**Why HashMap, not CSR:** Compressed Sparse Row (CSR) is more cache-friendly and compact, but requires knowing the full graph before construction (two-pass: count edges, then fill). HashMap allows incremental loading during the SPI scan -- each vertex and edge is inserted as it's read. CSR would be the right choice for shared memory (Phase 4) where the structure lives in a fixed-size pre-allocated region.

**Why bidirectional:** The primary use case (neighborhood exploration) is undirected -- "show me everything connected to this concept." Storing both `outgoing` and `incoming` edges doubles memory but makes undirected BFS a simple concatenation of two slices instead of scanning the entire edge set.

### Node Identity

Nodes have two identifiers:

- **NodeId** (`u64`): AGE's internal graph ID, the primary key in all internal structures.
- **app_id** (`Option<String>`): An application-level identifier extracted from a configurable node property (e.g., `concept_id`). Indexed in `app_id_index` for O(1) lookup.

The `resolve_node()` function tries app_id first, then falls back to parsing the input as a raw u64. This lets callers use either human-readable IDs (`"linear-scanning-system"`) or AGE internal IDs (`"2251799813685388"`).

### Relationship Type Interning

Edge relationship types are interned into a `u16` index (max 65,535 distinct types). This saves ~40 bytes per edge compared to storing the type name as a `String` on each edge. The interning table is populated during the SPI load -- each edge label table name is interned once.

**Why u16:** The Apache AGE label catalog typically has tens to low hundreds of relationship types. u16 handles up to 65,535 -- more than sufficient. Using u16 instead of u32 saves 2 bytes per edge, which matters at 50M edges (100MB savings).

### Memory Accounting

`Graph::memory_usage()` approximates total heap usage by accounting for:

- HashMap bucket arrays (capacity, not just len)
- Vec capacity for edge lists
- String heap allocations (label, app_id, rel_type names)
- NodeInfo structs

This estimate is checked against `max_memory_mb` after loading. It's approximate -- Rust's allocator may use more due to alignment and fragmentation -- but tracks actual usage within ~10%.

## Algorithms

### BFS Neighborhood

`bfs_neighborhood(graph, start, max_depth) -> TraversalResult`

Standard BFS with two enhancements:

1. **Visited-set pruning.** Each node is visited at most once, at its minimum distance from start. This bounds the traversal to O(V + E) regardless of graph cycles.

2. **Parent pointer tracking.** Instead of storing the full path to each discovered node (which would be O(V * D) memory), we store only the parent pointer and the edge type used to reach each node. Path types are reconstructed lazily by walking pointers backward from the target to the start.

```
BFS queue: [(start, 0)]
visited: {start → (parent=None, rel_type=None)}

while queue not empty:
    (node, depth) = dequeue
    if depth >= max_depth: skip
    for (target, rel_type) in neighbors_all(node):
        if target not in visited:
            visited[target] = (parent=node, rel_type)
            enqueue (target, depth+1)
```

**Undirected traversal:** `neighbors_all()` concatenates outgoing and incoming edges, treating the graph as undirected. This matches the AGE query pattern `(a)-[r]-(b)` which traverses in both directions.

**Path type reconstruction:** For each discovered node, walk the parent pointers from node back to start, collecting relationship type names. This produces the relationship types along one shortest path -- not all shortest paths. The lazy reconstruction avoids allocating path data for nodes that may never be returned (e.g., if the caller filters by label).

### Shortest Path

`shortest_path(graph, start, target, max_hops) -> Option<Vec<PathStep>>`

BFS with early termination: stop as soon as `target` is dequeued. Reconstruct the full path (both endpoints + intermediate nodes) by walking parent pointers.

Returns `None` if target is unreachable within `max_hops`. Returns a single-node path if `start == target`.

## PostgreSQL Integration

### SPI Loading

The extension loads AGE's graph data via SPI (Server Programming Interface), reading AGE's internal tables directly rather than executing Cypher queries. This is faster and avoids the query planner overhead that makes AGE slow in the first place.

**Loading sequence:**

1. Verify graph exists: `SELECT 1 FROM ag_catalog.ag_graph WHERE name = $name`
2. Load label catalog: `SELECT name::text, kind::text FROM ag_catalog.ag_label WHERE graph = $graphid`
3. For each vertex label (filtered by `node_labels` GUC):
   `SELECT id::text, properties::text FROM {graph}.{label}`
4. For each edge label (filtered by `edge_types` GUC):
   `SELECT start_id::text, end_id::text FROM {graph}.{label}`

**Why per-label-table, not a single Cypher query:**

- Each edge label table gives us the relationship type for free (it's the table name).
- Filtered labels are skipped entirely -- no wasted I/O.
- No query planner involvement -- these are simple sequential scans.
- AGE's Cypher-to-SQL translation is the bottleneck we're trying to avoid.

**SQL injection prevention:** `pgrx::spi::quote_identifier()` for schema/table names in FROM clauses, `pgrx::spi::quote_literal()` for values in WHERE clauses. Graph names are additionally validated (alphanumeric + underscore only) before any SPI call.

### GUC Registration

Configuration uses PostgreSQL's Grand Unified Configuration system. pgrx 0.16.1 requires `GucSetting<Option<CString>>` for string parameters with `c"..."` C string literals for defaults.

All GUCs currently use `GucContext::Userset` (settable per-session via `SET`). This will tighten to `Sighup` or `Postmaster` when shared memory is added, since changes would affect all backends.

### Per-Backend State

```rust
thread_local! {
    static GRAPH_STATE: RefCell<Option<GraphState>> = const { RefCell::new(None) };
}
```

PostgreSQL backends are single-threaded, so `thread_local! + RefCell` is safe and idiomatic. Each connection gets its own graph copy. This is simpler than shared memory and more robust -- one backend crash cannot corrupt another's state.

**Access patterns:**

- `with_graph(|gs| ...)` -- Execute a closure with a read reference to the loaded graph. Returns `None` if no graph is loaded.
- `set_graph(state)` -- Replace the per-backend graph. Called by `graph_accel_load()`.

### Error Handling

All functions callable from PostgreSQL are marked `#[pg_guard]`, which converts Rust panics into PostgreSQL `ERROR` (transaction abort + clean recovery). Without this, a panic would unwind through C frames and crash the backend.

The extension uses `pgrx::error!()` instead of `assert!()` or `panic!()` for expected error conditions. This produces proper PostgreSQL ERROR messages that the client can handle.

## Memory Model

### Per-Backend (Current)

Each backend connection loads its own copy of the graph. Memory cost scales linearly with connections:

| Graph Size | Memory/Backend | 10 Connections |
|------------|---------------|----------------|
| ~800 nodes | 312 KB | 3 MB |
| ~50K nodes | ~50 MB | ~500 MB |
| ~5M nodes | ~3 GB | ~30 GB |

This works well when:
- The graph fits comfortably in RAM alongside other processes
- A connection pool (PgBouncer) keeps backend count low
- Backends are long-lived (load once, query many times)

Load time scales with graph size: 22ms for ~800 nodes, estimated 5-20s for 50M edges.

### Shared Memory (Future)

Shared memory eliminates per-backend duplication: one copy serves all connections. This requires:

- **Fixed-size allocation at startup** via `pg_shmem_init!()` -- the HashMap-based structure would need to be replaced with a flat layout (CSR or arena-allocated) that fits in pre-allocated shared memory.
- **Background worker** for reloading -- a pgrx `BackgroundWorker` handles all reloads, building new structures in a staging buffer and atomically swapping the pointer.
- **`shared_preload_libraries`** -- the extension must load at Postgres startup.
- **GUC context tightening** -- `max_memory_mb` becomes `Postmaster` (restart required), most others become `Sighup`.

The per-backend approach may be sufficient indefinitely if connection pools keep backend counts low and load times stay acceptable.

## Safety

### Read-Only Guarantee

The extension never writes to AGE's internal tables. It reads via SPI during load and serves from in-memory state during queries. The only table the extension will eventually write to is its own epoch counter (Phase 3), and only via triggers on AGE mutations -- not from extension code directly.

### Memory Bounds

`max_memory_mb` is checked after loading. If the graph exceeds the cap, the load fails with an ERROR and no graph is stored. The previous graph (if any) remains available.

### Panic Safety

Every `#[pg_extern]` function is protected by `#[pg_guard]`. The extension never emits `FATAL` (kills connection) or `PANIC` (crashes cluster). All errors are `ERROR` level -- PostgreSQL aborts the transaction and the backend continues.

### No Threading

PostgreSQL is single-threaded per backend. The extension never spawns threads. All traversal runs synchronously in the calling backend's thread.

## Benchmark Methodology

### Synthetic Topologies

Six generators produce graphs with different structural properties. A real knowledge graph is closest to scale-free (power-law hubs) with small-world shortcuts, but edge cases like barbell (bottleneck paths) and DLA (organic growth) exercise failure modes that scale-free alone misses.

All generators are deterministic (seeded RNG) and O(n + edges). At 5M nodes, all complete in under 30 seconds.

### Live Graph Comparison

The benchmark comparison script (`tests/benchmark-comparison.sh`) runs the same neighborhood query against both AGE (via Cypher) and graph_accel (via SQL function) on the live graph. It validates:

1. **Timing** at depths 1-5 with psql `\timing`
2. **Data correctness** -- depth-1 concept sets must be identical
3. **Superset property** -- at depth 2+, graph_accel must find all concepts AGE finds (it may find more due to traversal through non-Concept intermediate nodes)

See [benchmark-findings.md](benchmark-findings.md) for detailed results and reproduction SQL.

## Known Limitations

- **Cross-type traversal.** BFS traverses all edges regardless of node type. Loading all node types means neighborhoods include Instance/Source nodes, which broadens results compared to AGE's Concept-only Cypher patterns. Mitigate with `node_labels` filtering or post-query label filtering.
- **Per-backend memory.** Each connection loads its own copy. At 5M nodes with 10 connections, that's ~30GB. Connection pooling mitigates this.
- **No weighted paths.** Shortest path is unweighted (hop count only). Dijkstra or A* for weighted edges is a future enhancement.
- **u16 relationship type limit.** Max 65,535 distinct relationship types. Sufficient for any practical graph but panics (caught by pg_guard) if exceeded.
- **No incremental updates.** The entire graph is reloaded on each `graph_accel_load()` call. Incremental edge insertion/deletion is a future enhancement.

## Future Work

- **Epoch invalidation (Phase 3).** A monotonic counter in a dedicated table, incremented by triggers on AGE mutations. Query functions check the epoch before serving -- if stale, trigger a reload.
- **Shared memory (Phase 4).** Cross-backend graph sharing via `pg_shmem_init!()`. Requires redesigning the core data structure to use a flat buffer layout (CSR) in fixed-size pre-allocated shared memory.
- **Directed traversal.** Option to follow only outgoing or only incoming edges, matching AGE's `(a)-[r]->(b)` vs `(a)-[r]-(b)` patterns.
- **Edge property filtering.** Load and index edge properties (e.g., `grounding_strength`) to support filtered traversals.
- **Weighted shortest path.** Dijkstra's algorithm using edge properties as weights.
- **Degree centrality function.** `graph_accel_degree(top_n)` returning nodes ranked by in/out/total degree.
- **Connected component extraction.** `graph_accel_subgraph(start_id, max_depth)` for subgraph analysis.
