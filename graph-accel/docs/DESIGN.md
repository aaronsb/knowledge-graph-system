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

The extension is a thin wrapper that handles SPI loading, GUC registration, node ID resolution, and SQL function bindings. The core engine owns all data structures and algorithms.

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
    estimated_avg_degree: usize,             // hint for Vec pre-allocation
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

### Edge Confidence

Edges carry an optional `confidence` field (`f32`). To avoid the memory cost of `Option<f32>` (which adds alignment padding + discriminant, bloating each Edge from 8 to 12+ bytes across 50M+ edges), the extension uses `f32::NAN` as a sentinel for "not loaded." This is safe because:

- `Edge::has_confidence()` uses `is_nan()` — the only `f32` value that returns true.
- The confidence filter passes NAN through: edges without loaded confidence are never silently dropped.
- Confidence values are only compared, never arithmetically composed, so NAN propagation is not a risk.

Confidence is loaded from AGE edge properties during SPI load (parsed from the `properties::text` JSON column). Edges without a `confidence` key receive `NAN`.

### Memory Accounting

`Graph::memory_usage()` approximates total heap usage by accounting for:

- HashMap bucket arrays (capacity, not just len)
- Vec capacity for edge lists
- String heap allocations (label, app_id, rel_type names)
- NodeInfo structs

This estimate is checked against `max_memory_mb` after loading. It's approximate -- Rust's allocator may use more due to alignment and fragmentation -- but tracks actual usage within ~10%.

## Algorithms

### Neighbor Iteration

`iter_neighbors(graph, node, direction, min_confidence)`

All traversal functions share this helper for directed and confidence-filtered neighbor iteration. It uses boolean flags to select which adjacency lists to iterate:

```rust
let (use_out, use_inc) = match direction {
    Outgoing => (true, false),
    Incoming => (false, true),
    Both => (true, true),
};
```

The compiler eliminates dead branches via constant propagation, making directed traversal zero-cost compared to undirected.

When `min_confidence` is set, edges are filtered inline: skip edges where `has_confidence() && confidence < threshold`. Edges without loaded confidence (NAN) always pass.

### BFS Neighborhood

`bfs_neighborhood(graph, start, max_depth, direction, min_confidence) -> TraversalResult`

Standard BFS with two enhancements:

1. **Visited-set pruning.** Each node is visited at most once, at its minimum distance from start. This bounds the traversal to O(V + E) regardless of graph cycles.

2. **Parent pointer tracking.** Instead of storing the full path to each discovered node (which would be O(V * D) memory), we store only the parent pointer and the edge type used to reach each node. Path types are reconstructed lazily by walking pointers backward from the target to the start.

```
BFS queue: [(start, 0)]
visited: {start → (parent=None, rel_type=None, direction=None)}

while queue not empty:
    (node, depth) = dequeue
    if depth >= max_depth: skip
    for (target, rel_type, direction) in iter_neighbors(node, direction, min_confidence):
        if target not in visited:
            visited[target] = (parent=node, rel_type, direction)
            enqueue (target, depth+1)
```

**Direction-aware traversal:** `iter_neighbors()` selects from outgoing, incoming, or both adjacency lists, tagging each edge with its traversal direction (`Outgoing` if followed from → to, `Incoming` if followed against the stored direction). This preserves edge semantics -- the caller can distinguish "A SUPPORTS B" from "B SUPPORTS A" -- while controlling the traversal direction.

**Path reconstruction:** For each discovered node, walk the parent pointers from node back to start, collecting relationship type names and directions. This produces the types and directions along one shortest path -- not all shortest paths. The lazy reconstruction avoids allocating path data for nodes that may never be returned (e.g., if the caller filters by label).

### Shortest Path

`shortest_path(graph, start, target, max_hops, direction, min_confidence) -> Option<Vec<PathStep>>`

BFS with early termination: stop as soon as `target` is dequeued. Reconstruct the full path (both endpoints + intermediate nodes) by walking parent pointers. Respects `direction` and `min_confidence` via `iter_neighbors`.

Returns `None` if target is unreachable within `max_hops`. Returns a single-node path if `start == target`.

### Degree Centrality

`degree_centrality(graph, top_n) -> Vec<DegreeResult>`

Iterates all nodes via `graph.nodes_iter()`, counting outgoing and incoming neighbor counts directly from the adjacency lists. Results are sorted descending by total degree (with node ID as tiebreaker for determinism), then truncated to `top_n`. Passing `top_n = 0` returns all nodes.

This replaces per-concept `OPTIONAL MATCH` counting in Cypher, which requires a round-trip per concept. A single `graph_accel_degree(100)` call returns the top hubs in one pass.

### Subgraph Extraction

`extract_subgraph(graph, start, max_depth, direction, min_confidence) -> SubgraphResult`

Two-phase approach:

1. **Discovery:** BFS from `start` using `iter_neighbors` (respects direction + confidence filtering) to collect all reachable nodes into a `HashSet`.
2. **Edge collection:** For each discovered node, iterate `neighbors_out()` only. If the target is also in the discovered set, emit the edge. Iterating outgoing-only avoids emitting each edge twice.

Returns `SubgraphResult { node_count, edges: Vec<SubgraphEdge> }` where each edge carries from/to IDs, labels, app_ids, and relationship type.

**Note on directed mode:** The `direction` parameter controls Phase 1 (discovery). Phase 2 always emits outgoing edges between discovered nodes, regardless of direction. This means the output is "the subgraph induced by nodes reachable via the specified direction," not "only edges in the specified direction." This distinction matters when `direction = 'incoming'` -- the emitted edges may include outgoing edges between the discovered nodes.

## PostgreSQL Integration

### SPI Loading

The extension loads AGE's graph data via SPI (Server Programming Interface), reading AGE's internal tables directly rather than executing Cypher queries. This is faster and avoids the query planner overhead that makes AGE slow in the first place.

**Loading sequence:**

1. Verify graph exists: `SELECT 1 FROM ag_catalog.ag_graph WHERE name = $name`
2. Load label catalog:
   ```sql
   SELECT l.name::text, l.kind::text
   FROM ag_catalog.ag_label l
   JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
   WHERE g.name = $name AND l.name NOT LIKE '_ag%'
   ```
   The `_ag%` exclusion skips AGE's internal labels (e.g., `_ag_label_vertex`, `_ag_label_edge`).
3. For each vertex label (filtered by `node_labels` GUC):
   `SELECT id::text, properties::text FROM {graph}.{label}`
4. For each edge label (filtered by `edge_types` GUC):
   `SELECT start_id::text, end_id::text, properties::text FROM {graph}.{label}`
   Edge properties are parsed as JSON to extract `confidence` (float). Edges without a confidence property receive `Edge::NO_CONFIDENCE` (NAN).

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

The extension never writes to AGE's internal tables. It reads via SPI during load and serves from in-memory state during queries. The only table the extension writes to is `graph_accel.generation` (its own cache invalidation counter), managed via `graph_accel_invalidate()`.

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
- **No weighted paths.** Shortest path is unweighted (hop count only). Dijkstra using edge confidence as weights is a future enhancement.
- **Subgraph direction semantics.** `graph_accel_subgraph` with `direction_filter = 'incoming'` discovers nodes via incoming edges but emits outgoing edges between them. The direction controls discovery scope, not output edge direction.
- **u16 relationship type limit.** Max 65,535 distinct relationship types. Sufficient for any practical graph but panics (caught by pg_guard) if exceeded.
- **No incremental updates.** The entire graph is reloaded on each `graph_accel_load()` call. Incremental edge insertion/deletion is a future enhancement.

## Cache Invalidation

Generation-based cooperative invalidation. AGE bypasses PostgreSQL row-level triggers (its C functions directly manipulate vertex/edge tables), so transparent invalidation is impossible. Applications cooperate by calling `graph_accel_invalidate(graph_name)` after mutations.

**Schema** (created at `CREATE EXTENSION` via `extension_sql!` bootstrap):

```sql
CREATE TABLE graph_accel.generation (
    graph_name  text PRIMARY KEY,
    generation  bigint NOT NULL DEFAULT 1,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
```

**Invalidation function:**

```sql
SELECT graph_accel_invalidate('my_graph');  -- returns new generation (monotonic)
```

Atomically bumps the generation counter and fires `pg_notify('graph_accel', graph_name)` for external listeners.

**Staleness check:** Every query function calls `ensure_fresh()` as its first instruction — a single-row PK lookup (~0.01ms). If `loaded_generation < current_generation` and `auto_reload = true` (with debounce), the graph reloads inline. If reload fails, `PgTryBuilder` catches the error and serves stale data with a warning.

**Status:** `graph_accel_status()` returns `loaded_generation`, `current_generation`, and `is_stale`. Status string is `"loaded"`, `"stale"`, or `"not_loaded"`.

**Graceful degradation:**
- Generation table missing → skip staleness check, serve loaded graph
- No row for this graph → generation 0 → always fresh
- Auto-reload fails → warning, serve stale
- Never invalidated → everything fresh forever

## Integration Pattern: Two-Phase Queries

graph_accel stores topology — node IDs, labels, application-level identifiers, and edges with relationship types. It does **not** store node properties (descriptions, scores, embeddings, or any domain-specific data). This keeps the extension generic and lightweight.

Applications that need full node properties alongside fast traversal use a two-phase pattern:

```
Phase 1: Topology (graph_accel, sub-ms)
  graph_accel_neighborhood('node_id', 5, 'outgoing', 0.5)
  → node_id, label, app_id, distance, path_types[], path_directions[]

Phase 2: Property Hydration (application-side, parallel)
  SELECT * FROM {graph}.{label} WHERE id IN (...)
  → full node properties for the IDs returned by Phase 1
```

Beyond neighborhood queries, the extension supports several topology operations:

```
-- Hub detection for ontology scoring
graph_accel_degree(100) → node_id, out_degree, in_degree, total_degree

-- Edge list for relationship counting and affinity analysis
graph_accel_subgraph('node_id', 3) → from_id, to_id, rel_type, ...

-- Shortest path between two concepts
graph_accel_path('from', 'to', 10, 'both', 0.5) → step, node_id, rel_type, direction
```

**Why this works:** AGE's `MATCH (a)-[*1..N]-(b)` translates to nested SQL joins with O(degree^depth) intermediate rows. The two-phase pattern eliminates that — Phase 1 is O(V+E) BFS with visited-set pruning, Phase 2 is flat index lookups at O(result_count).

**Application-side orchestration:** Because Phase 1 returns the complete set of node IDs before any property fetching begins, the application controls how hydration executes — batch sizing, priority ordering (shallow results first), cancellation, selective hydration (skip properties for topology-only views), and parallel dispatch across multiple connections. Each hydration worker gets a disjoint ID set with no overlap.

This pattern applies to any AGE graph where traversal performance matters but full property data is needed in the response. The extension stays topology-only; property handling is the application's concern.

## Future Work

- **Weighted shortest path.** Dijkstra's algorithm using edge confidence as weights. The confidence data is already loaded; this adds a weighted traversal mode. No current endpoint needs weighted paths, but it would enable "highest-confidence path" queries.
- **Shared memory.** Cross-backend graph sharing via `pg_shmem_init!()`. Requires redesigning the core data structure to use a flat buffer layout (CSR) in fixed-size pre-allocated shared memory. Justified when per-backend copies exceed available RAM.
- **Relationship type filtering.** A `rel_types` parameter on traversal functions to restrict which edge types are followed. Currently achievable via `edge_types` GUC at load time, but per-query filtering would be more flexible.
