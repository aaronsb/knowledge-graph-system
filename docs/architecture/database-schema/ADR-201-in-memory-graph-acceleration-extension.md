---
status: Draft
date: 2026-01-31
deciders:
  - aaronsb
  - claude
related:
  - ADR-016  # openCypher compatibility
  - ADR-048  # Query safety & GraphQueryFacade
---

# ADR-201: In-Memory Graph Acceleration Extension

## Context

Apache AGE provides graph storage and openCypher query support as a PostgreSQL extension, but its traversal performance is fundamentally limited by PostgreSQL's relational query planner. AGE translates Cypher path matches into nested SQL joins on internal edge/vertex tables. For multi-hop traversals (depth 3+), this creates combinatorial intermediate result sets that the planner cannot optimize — it doesn't understand graph topology.

### Benchmarks

Testing on a ~200 node, ~1000 edge graph (16 cores / 32 threads, 128GB RAM).

**Traversal performance (iterative fixed-depth chain queries, PR #262):**

| Depth | Concepts Found | Sequential | Parallel (asyncio.to_thread) | Speedup |
|-------|---------------|------------|------------------------------|---------|
| 2     | 5             | 0.202s     | 0.113s                       | 1.8x    |
| 3     | 7             | 0.340s     | 0.162s                       | 2.1x    |
| 4     | 14            | 0.529s     | 0.204s                       | 2.6x    |
| 5     | 20            | 0.871s     | 0.378s                       | 2.3x    |
| 6     | —             | Hangs indefinitely | —                      | —       |

Parallel execution dispatches each depth level to a separate thread via `asyncio.to_thread`, each getting its own connection from AGE's `ThreadedConnectionPool`. Real parallelism on the Postgres side (GIL releases during I/O). Consistent ~2-2.5x speedup.

**Postgres tuning attempted (did not resolve depth-6):**

| Setting | Default | Tuned | Effect |
|---------|---------|-------|--------|
| `work_mem` | 4MB | 64MB | No improvement at depth 6; 256MB caused plan regression (planner chose hash joins over nested loops, slower for small result sets) |
| `shared_buffers` | 128MB | 8GB | Cold cache penalty: ~3.5s overhead on first queries after restart. Once warm, no measurable difference at depth 5 |
| `max_parallel_workers_per_gather` | 2 | 4 | More cores active (visible in CPU monitoring) but depth-6 still hung. Parallel workers bail out when the join is too large |
| `max_parallel_workers` | 8 | 16 | Allowed more concurrent intra-query parallelism but didn't help the fundamental join explosion |

**Key observation:** At depth 6, CPU activity starts with broad parallelism (workers engaging) then drops to 1-2 cores grinding — the deep join exceeds what Postgres can parallelize. The wall is not memory or CPU count, it's the relational execution model.

**Prior issue (PR #261):** The `/query/cypher` endpoint was returning 384-float embedding vectors (~3KB JSON per concept) in responses. A depth-2 neighborhood query returning 200 concepts would send ~600KB of useless embedding data. Stripped in PR #261.

**Prior issue (PR #262):** The original `/query/related` endpoint used `MATCH path = (start)-[*1..N]-(related)` with `collect(path)`, which enumerates ALL paths (combinatorial in cyclic graphs). Replaced with iterative fixed-depth chain queries merged in Python. This made depth 5 practical but depth 6+ remains infeasible via AGE.

The depth-6 query generates a 12-table SQL join. Even returning ~20 distinct concepts, the intermediate row count is O(degree^depth) before DISTINCT collapses it. Postgres tuning does not fix this — the problem is architectural.

A native graph engine stores adjacency lists directly on nodes. Traversing an edge is a pointer chase (O(1) per hop). The same depth-6 query on an adjacency list completes in microseconds regardless of graph size.

### Prior Art

This is a well-established architectural pattern that combines CQRS (Command Query Responsibility Segregation), materialized graph views, and epoch-based invalidation. There is no single canonical name — LinkedIn calls it a "graph serving layer," Meta calls it a "graph-aware cache."

**Production systems using this pattern:**

| System | Company | Write Path | Read Path | Invalidation | Scale |
|--------|---------|------------|-----------|--------------|-------|
| **TAO** | Meta/Facebook | MySQL (ACID, source of truth) | Graph-aware distributed cache | Version numbers in invalidation messages | 1B reads/sec, 96.4% cache hit rate |
| **LIquid** | LinkedIn | Relational model | In-memory graph serving (Datalog) | Replica-based | 270B+ entities, ~15TB in-memory, 2M queries/sec |
| **A1** | Microsoft/Bing | FaRM-based storage | In-memory graph (distributed) | TTL-based staleness checks | 10B+ vertices, 350M+ reads/sec |
| **FlockDB** | Twitter | MySQL + Kestrel write queue | MySQL with full memory cache | Journal-based | 13B+ edges, 100K reads/sec |

**Key lessons from production:**
- **Meta's TAO** discovered a subtle off-by-one bug in version comparison (strict `<` instead of `<=`) that caused indefinite staleness. They built a dedicated consistency monitor (Polaris) to detect it, improving from six nines to ten nines of consistency.
- **LinkedIn's LIquid** describes the critical distinction: "the difference between a cache and an index is that the index is complete — it has some consistency properties that you can state, whereas the cache is just whatever the application put in there." The in-memory graph is an index, not a cache.
- **Full reload vs incremental:** Meta's earlier Memcache approach had this problem: "A key-value cache is not good for fetching a large list of edges. A change will require reloading the entire list." TAO solved this by making the cache graph-aware. Our extension follows the same principle — graph-structured, not key-value.

**Academic foundations:**
- Martin Fowler's CQRS pattern: separate models for reads and writes, where the read model can be a specialized structure (graph, search index, OLAP cube).
- Materialized graph views: "a physical data object containing the results of executing Q over G" that can answer queries without accessing the original data store.
- Polyglot persistence: using different storage technologies for different access patterns — relational for writes/integrity, in-memory graph for traversal.

**Open source components in this space:**
- **pgrx** (Rust PostgreSQL extension framework) — proven by VectorChord, ParadeDB, pgvectorscale
- **VectorChord's `vchordg`** — demonstrates a graph-based index as a Postgres extension via pgrx with custom access methods
- **Debezium** — CDC from PostgreSQL that could drive incremental updates (future optimization)
- **Grand** — Python library providing NetworkX-compatible interface with pluggable backends (demonstrates the dual-interface concept)

## Decision

Build a PostgreSQL extension in Rust (via pgrx) that maintains an in-memory adjacency structure alongside AGE and exposes fast traversal functions via SQL.

### Architecture

```
Writes: Application → AGE (Cypher) → PostgreSQL tables → epoch++
                                                            │
                                                            ▼
Reads:  Application → graph_accel_*() ← in-memory adjacency structure
            │                                (Rust HashMap in shmem)
            │
            └─ shallow queries (depth ≤ 3) can still go directly to AGE
```

**AGE remains the source of truth.** It handles all writes, schema integrity, ACID transactions, and the openCypher interface. The acceleration extension is a read-only materialized view of AGE's edge graph.

### Generic Design

The extension is **not hardcoded to a specific schema**. It works with any AGE graph — any node labels, any relationship types, any property names. This makes it useful to anyone using AGE, not just this project.

**How it discovers the graph:** On load, the extension reads AGE's internal edge and vertex tables directly (via SPI on `ag_catalog` tables), or executes a user-provided Cypher query. By default it loads all edges:

```cypher
-- Default: load everything
MATCH (a)-[r]->(b) RETURN id(a), id(b), type(r), label(a), label(b)
```

Users can narrow the scope via configuration:

```
# Only load edges between Concept nodes (our use case)
graph_accel.node_labels = 'Concept'

# Load all node types (someone else's use case)
graph_accel.node_labels = '*'

# Only load specific relationship types
graph_accel.edge_types = 'IMPLIES,SUPPORTS,CONTRADICTS'
```

**Node identity:** The extension uses AGE's internal graph IDs (`id(node)`) as the primary key in the adjacency structure. It also indexes a configurable property (default: `concept_id` for our use case, but configurable to `name`, `uuid`, or any string property) so callers can look up nodes by their application-level identifier.

```
# Our project: nodes identified by concept_id property
graph_accel.node_id_property = 'concept_id'

# Another project: nodes identified by 'name' property
graph_accel.node_id_property = 'name'
```

### Core Design

**Data structure:** `HashMap<NodeId, Vec<(TargetId, RelType)>>` stored in PostgreSQL shared memory. Bidirectional — both outgoing and incoming edges indexed. A secondary index maps application-level IDs (string property values) to internal node IDs.

**Epoch invalidation:** A monotonic counter in a dedicated table (`graph_accel_epoch`), incremented in the same transaction as any graph mutation (node/edge create, update, delete). The extension checks `current_epoch == loaded_epoch` before serving any query. If stale, it reloads.

The epoch trigger is installed automatically on `CREATE EXTENSION` for the configured AGE graph. It hooks into AGE's internal vertex and edge tables — any INSERT, UPDATE, or DELETE increments the counter.

**Reload strategy:**
- Full reload: single flat query on AGE's internal tables — loads entire edge list
- At target scale (50M edges), full reload takes seconds, not minutes
- Incremental reload (delta application) is a future optimization if write-heavy workloads make full reload impractical

**SQL interface:**
```sql
-- Load/reload the graph (or automatic via epoch check)
SELECT graph_accel_load('knowledge_graph');

-- Neighborhood traversal (BFS, any depth)
SELECT * FROM graph_accel_neighborhood('node_id_value', max_depth := 10);
-- Returns: node_id, label, distance, path_types[]

-- Shortest path between two nodes
SELECT * FROM graph_accel_path('from_id', 'to_id', max_hops := 20);
-- Returns: step, node_id, label, rel_type (one row per hop)

-- Connected components / subgraph extraction
SELECT * FROM graph_accel_subgraph('node_id_value', max_depth := 5);
-- Returns: node_id, label, component_id

-- Degree centrality (useful for graph analysis)
SELECT * FROM graph_accel_degree(top_n := 100);
-- Returns: node_id, label, in_degree, out_degree, total_degree

-- Status and diagnostics
SELECT * FROM graph_accel_status();
-- Returns: loaded_epoch, current_epoch, node_count, edge_count,
--          memory_bytes, load_time_ms, source_graph, status
```

All functions accept the application-level node identifier (the string property configured via `graph_accel.node_id_property`), not AGE's internal integer IDs. This keeps the interface natural for application code.

### Dual Build Target

The core traversal engine is a pure Rust library (`graph-accel-core`) with no Postgres dependencies. It compiles into two targets:

1. **`graph_accel.so`** — pgrx PostgreSQL extension (production use)
2. **`graph-accel-bench`** — standalone CLI binary for benchmarking with synthetic graphs (development/testing)

This enables:
- Testing traversal performance at target scale without a running Postgres instance
- CI benchmarking with synthetic graphs of known topology
- Profiling and optimization outside the Postgres process model
- Validating correctness against a reference BFS implementation

### Benchmark Topologies

The standalone benchmark binary includes six synthetic graph generators. Different topologies stress different traversal behaviors — a graph engine that performs well on one shape may degrade on another.

| Generator | Topology | What it tests | Edges/node | Generation |
|-----------|----------|---------------|------------|------------|
| **L-system tree** | Fractal branching (ternary tree) | Deep BFS (depth 12+ to reach full graph), path reconstruction on long chains | 1 | O(n), recursive frontier expansion |
| **Scale-free** | Power-law degree distribution (Barabási-Albert) | High fan-out hubs, realistic knowledge graph structure. Depth 3 covers ~99% of nodes. | 10 | O(edges), edge-list endpoint sampling for preferential attachment |
| **Small-world** | Ring lattice + random rewiring (Watts-Strogatz) | High clustering with short global paths. Tests that shortcuts are discovered. | 10 | O(n × k), p=0.05 rewire rate |
| **Erdős-Rényi** | Uniform random edges | Baseline control — no structural bias. Gradual BFS expansion. | 10 | O(edges), random endpoint pairs |
| **Barbell** | Two dense cliques + thin bridge chain | Bottleneck pathfinding. BFS at depth 5 covers only one clique. Must cross bridge to reach the other half. | ~20 (clique), 1 (bridge) | O(n) |
| **DLA** | Diffusion-limited aggregation | Organic branching, winding paths, tree-like with occasional shortcuts. Mimics natural growth. | ~1.1 | O(n), surface-limited attachment |

**Why these matter:** A real knowledge graph is closest to scale-free (power-law hubs from popular concepts) with small-world properties (ontology cross-references create shortcuts). But edge cases like barbell (two isolated knowledge domains connected by a single bridging concept) and DLA (incrementally grown knowledge with no global structure) exercise failure modes that scale-free alone would miss.

**Generation performance constraint:** At target scale (5M nodes), all generators must complete in under 30 seconds. The original naive preferential attachment (O(n²) cumulative degree scan) took 4+ minutes at 5M nodes. The edge-list sampling approach achieves the same degree distribution in O(edges) time.

### Target Scale Envelope

| Dimension | Target | Memory Estimate |
|-----------|--------|-----------------|
| Ontologies | ~500 | negligible |
| Documents/Files | ~500,000 | not loaded (metadata stays in AGE) |
| Concepts | ~5,000,000 | ~500MB |
| Edges | ~50,000,000 | ~2.5GB |
| **Total in-memory** | | **~3GB** |

At 50M edges with average degree 10, BFS to depth 10 touches at most 10^10 candidate paths — but with visited-set pruning, it touches at most 5M nodes (the entire graph). Wall time: milliseconds for bounded-depth queries, seconds for full-graph traversal.

### Standalone Benchmark Results (5M nodes)

Measured with `graph-accel-bench` on the same hardware (16 cores / 32 threads, 128GB RAM). Six synthetic topologies at target scale. All generation + traversal runs single-threaded.

**Generation performance:**

| Topology | Nodes | Edges | Memory | Gen Time |
|----------|-------|-------|--------|----------|
| L-system tree | 5M | 5M | 992MB | 2.9s |
| Scale-free (edge sampling) | 5M | 50M | 2.4GB | 20.6s |
| Small-world (Watts-Strogatz) | 5M | 50M | 2.4GB | 6.8s |
| Erdős-Rényi random | 5M | 50M | 2.4GB | 21.2s |
| Barbell (clique-bridge-clique) | 5M | 100M | 3.9GB | 33.0s |
| DLA (organic branching) | 5M | 5.5M | 1.0GB | 5.3s |

**BFS neighborhood traversal (from hub/root node):**

| Topology | Depth 1 | Depth 5 | Depth 10 | Full graph | Depth to 100% |
|----------|---------|---------|----------|------------|---------------|
| L-system | 0.0ms (3) | 0.3ms (363) | 79ms (89K) | 6.6s (5M) | 20 |
| Scale-free | 6.3ms (11K) | 15.0s (5M) | — | 15.0s (5M) | 5 |
| Small-world | 0.1ms (21) | 20ms (18K) | 9.5s (5M) | 11.1s (5M) | ~20 |
| Random | 80ms (15) | 2.9s (2.5M) | 15.6s (5M) | 15.6s (5M) | 10 |
| Barbell | 0.1ms (33) | 7.1s (2.5M) | 11.7s (2.5M) | 25.2s (5M) | 50 |
| DLA | 0.0ms (12) | 3.2ms (4.5K) | 140ms (146K) | 8.3s (5M) | 50 |

Values in parentheses are nodes found at that depth.

**Shortest path (node 0 → last node):**

| Topology | Hops | Time |
|----------|------|------|
| L-system | 14 | 1.9s |
| Scale-free | 3 | 2.0s |
| Small-world | 1 | 1.7ms |
| Random | 5 | 344ms |
| Barbell | 21 | 8.8s |
| DLA | 17 | 1.3s |

### Projected Speedup vs AGE on Real Data

A real knowledge graph is structurally closest to scale-free (power-law hubs from popular concepts like "Machine Learning" or "Climate Change") with small-world shortcuts (ontology cross-references). The current system has ~200 concepts / ~1000 edges. Projections based on benchmark data:

**Current graph size (~200 nodes, ~1000 edges):**

| Query | AGE (measured) | graph_accel (projected) | Speedup |
|-------|---------------|------------------------|---------|
| Depth 2 neighborhood | 113ms | <0.1ms | ~1,000x |
| Depth 3 neighborhood | 162ms | <0.1ms | ~1,600x |
| Depth 5 neighborhood | 378ms | <0.1ms | ~3,800x |
| Depth 6 neighborhood | ∞ (hangs) | <0.1ms | ∞ |
| Depth 10 neighborhood | impossible | <0.1ms | — |

At 200 nodes the entire graph fits in a few cache lines. Every query is sub-millisecond.

**Projected at medium scale (~50K nodes, ~500K edges):**

| Query | AGE (estimated) | graph_accel (projected) | Speedup |
|-------|----------------|------------------------|---------|
| Depth 3 neighborhood | ~2-5s | ~1-5ms | ~500x |
| Depth 5 neighborhood | hangs | ~50-200ms | ∞ |
| Depth 10 neighborhood | impossible | ~500ms-2s | — |
| Shortest path | impossible beyond depth 5 | ~10-50ms | — |

**Projected at target scale (~5M nodes, ~50M edges):**

| Query | AGE (estimated) | graph_accel (measured) | Speedup |
|-------|----------------|----------------------|---------|
| Depth 3 neighborhood | impossible | ~500ms-5s | — |
| Depth 5 neighborhood | impossible | ~3s-15s (full graph reached on scale-free) | — |
| Bounded depth 5 (typical API query) | impossible | ~20ms-3s depending on topology | — |
| Shortest path (short) | impossible | ~2ms-2s | — |

**Key insight from benchmarks:** The bottleneck at scale is not the graph engine — it's touching millions of nodes. A depth-5 BFS on a scale-free graph with 5M nodes visits the entire graph because hub nodes fan out so broadly. In production, most queries will have `max_depth=5` on a graph where depth 5 reaches thousands to tens of thousands of nodes, not millions. The realistic query profile is:

- Depth 3-5, returning 100-10,000 nodes: **sub-100ms**
- Depth 10+, returning 50K+ nodes: **under 1 second**
- Full graph traversal (analysis/export): **5-15 seconds**

AGE cannot do any of these beyond depth 5 at any graph size.

### Configuration (GUC Parameters)

The extension uses PostgreSQL's standard GUC (Grand Unified Configuration) system. Parameters are namespaced under `graph_accel.*` and set in `postgresql.conf`, via `ALTER SYSTEM SET`, or per-session with `SET`.

| Parameter | Type | Default | Restart Required | Purpose |
|-----------|------|---------|------------------|---------|
| `graph_accel.source_graph` | string | `''` (none) | reload | AGE graph name to load. Required. |
| `graph_accel.node_labels` | string | `'*'` | reload | Comma-separated node labels to load, or `'*'` for all |
| `graph_accel.edge_types` | string | `'*'` | reload | Comma-separated edge types to load, or `'*'` for all |
| `graph_accel.node_id_property` | string | `''` (AGE ID) | reload | Node property to use as application-level identifier. Empty = AGE internal IDs only. |
| `graph_accel.max_memory_mb` | int | 4096 | postmaster | Shared memory allocation cap. Set based on expected graph size. |
| `graph_accel.preload` | bool | `off` | postmaster | Load graph into shared memory at Postgres startup. When `off`, loads lazily on first query. |
| `graph_accel.auto_reload` | bool | `on` | reload | Automatically reload when epoch mismatch detected |
| `graph_accel.reload_debounce_sec` | int | 5 | reload | Minimum seconds between reloads. Prevents thrashing during bulk ingestion. |
| `graph_accel.log_level` | enum | `warning` | reload | Extension logging verbosity (`debug`, `info`, `warning`, `error`) |

**Postmaster vs reload:** Parameters that control shared memory allocation (`max_memory_mb`, `preload`) require a Postgres restart because shared memory is allocated at startup. All other parameters take effect on `SELECT pg_reload_conf()`.

**Preload behavior:** When `graph_accel.preload = on`, add `graph_accel` to `shared_preload_libraries` in `postgresql.conf`. The extension loads the full edge list during Postgres startup before accepting connections. This adds startup time but eliminates cold-start latency on the first query.

### Deployment into the Postgres + AGE Container

The platform uses the `apache/age` Docker image (Debian Trixie, PostgreSQL 17.7). AGE is pre-installed at:
- `/usr/lib/postgresql/17/lib/age.so`
- `/usr/share/postgresql/17/extension/age.control` + `age--1.6.0.sql`

The graph_accel extension follows the same pattern. Four deployment options, from simplest to most integrated:

**Option 0: Manual copy (bootstrapping / first build)**

Build on the host, copy directly into the running container:

```bash
# Build with pgrx
cargo pgrx package --pg-config $(docker exec knowledge-graph-postgres pg_config --bindir)/pg_config

# Copy artifacts into running container
docker cp target/release/graph_accel-pg17/usr/lib/postgresql/17/lib/graph_accel.so \
  knowledge-graph-postgres:/usr/lib/postgresql/17/lib/
docker cp target/release/graph_accel-pg17/usr/share/postgresql/17/extension/graph_accel.control \
  knowledge-graph-postgres:/usr/share/postgresql/17/extension/
docker cp target/release/graph_accel-pg17/usr/share/postgresql/17/extension/graph_accel--0.1.0.sql \
  knowledge-graph-postgres:/usr/share/postgresql/17/extension/

# Activate
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -c "CREATE EXTENSION graph_accel;"
```

Pros: Zero infrastructure changes. Works right now with the existing container.
Cons: Lost on container restart. Manual and not reproducible. Good for "does this work at all" testing.

**Option A: Volume mount (development / quick testing)**

Build the extension on the host, mount the artifacts into the container:

```yaml
# docker-compose.yml
postgres:
  image: apache/age
  volumes:
    - ./extensions/graph_accel.so:/usr/lib/postgresql/17/lib/graph_accel.so:ro
    - ./extensions/graph_accel.control:/usr/share/postgresql/17/extension/graph_accel.control:ro
    - ./extensions/graph_accel--0.1.0.sql:/usr/share/postgresql/17/extension/graph_accel--0.1.0.sql:ro
```

Then activate:
```sql
CREATE EXTENSION graph_accel;
SELECT graph_accel_load();
```

Pros: No custom image needed. Fast iteration during development.
Cons: Requires host Rust toolchain with pgrx. Extension must be compiled for the exact PG version in the container.

**Option B: Custom Dockerfile extending apache/age (recommended for production)**

```dockerfile
FROM apache/age AS base

# Build stage: compile extension
FROM rust:latest AS builder
RUN cargo install cargo-pgrx && cargo pgrx init --pg17 /usr/bin/pg_config
COPY graph-accel/ /build/
WORKDIR /build
RUN cargo pgrx package --pg-config /usr/bin/pg_config

# Final stage: copy extension into AGE image
FROM base
COPY --from=builder /build/target/release/graph_accel-pg17/ /usr/share/postgresql/17/
COPY --from=builder /build/target/release/graph_accel-pg17/ /usr/lib/postgresql/17/
```

This produces a single image with both AGE and graph_accel. The operator's `upgrade` command would pull this image the same way it pulls the current `apache/age` image.

Pros: Self-contained, reproducible. Works with `operator.sh upgrade`.
Cons: Custom image to maintain. Must rebuild when AGE or PG version changes.

**Option C: Init container / sidecar (Kubernetes-style)**

An init container compiles or copies the extension into a shared volume before Postgres starts. Overkill for Docker Compose but natural in Kubernetes deployments.

**Recommended path:** Start with Option A during development. Move to Option B once the extension is stable. The compose file change is minimal — swap `image: apache/age` for `build: ./docker/postgres/` pointing at the custom Dockerfile.

**Activation after deployment:**

```sql
-- One-time setup (in schema init script)
CREATE EXTENSION IF NOT EXISTS graph_accel;

-- Verify
SELECT graph_accel_status();
-- → loaded_epoch: 0, current_epoch: 42, status: 'not_loaded'

-- Manual load (or automatic if preload = on)
SELECT graph_accel_load();
-- → loaded 5000000 concepts, 50000000 edges in 2.3s

SELECT graph_accel_status();
-- → loaded_epoch: 42, current_epoch: 42, status: 'ready', memory_mb: 2847
```

The `CREATE EXTENSION` line would be added to `schema/00_baseline.sql` alongside the existing `CREATE EXTENSION IF NOT EXISTS age;`.

### Safety and Correctness

The extension must be a well-behaved Postgres citizen. Key constraints:

**Memory management:**
- All Postgres-facing allocations use `PgMemoryContexts`, not raw Rust allocators. Postgres frees context-allocated memory automatically on transaction abort or backend exit.
- The adjacency structure lives in shared memory, allocated at startup via `pg_shmem_init!()` with a fixed cap (`graph_accel.max_memory_mb`). Cannot grow beyond the cap — reload fails gracefully with an `ERROR` if the graph exceeds it.
- Use `PgBox<T>` for Postgres heap objects to handle drop semantics correctly across `elog(ERROR)` longjmp boundaries.

**Error handling:**
- Every function callable from Postgres is marked `#[pg_guard]`, converting Rust panics into Postgres `ERROR` (transaction abort + clean recovery). Without this, a panic unwinds through C frames and crashes the backend.
- The extension never emits `FATAL` (kills connection) or `PANIC` (crashes cluster). All errors are `ERROR` level — Postgres aborts the transaction and the backend continues.
- `PgTryBuilder` (pgrx's `PG_TRY`/`PG_CATCH`) wraps SPI calls during reload for safe recovery if AGE queries fail.

**Threading:**
- None. Postgres is single-process, single-threaded per connection. The extension never spawns threads. All traversal runs synchronously in the calling backend's thread, on the pre-built shared memory structure.

**Read-only guarantee:**
- The extension never writes to AGE's internal tables. It reads via SPI during reload and serves from shared memory during queries. This eliminates any risk of data corruption.
- The epoch counter table is the only table the extension writes to, and only via a trigger on AGE mutations (not from extension code directly).

**Atomic reload:**
- Reload builds a new adjacency structure in a staging buffer, then atomically swaps the pointer. No query ever sees a partially-loaded graph. If reload fails mid-way, the old structure remains active.

**Failure modes:**
- Extension crash → Postgres kills that backend process, other connections unaffected. On next connection, the shared memory structure is still intact (it's in shared memory, not per-backend memory).
- OOM during reload → `ERROR` returned to caller, old graph remains loaded. The `max_memory_mb` cap prevents unbounded growth.
- AGE unavailable during reload → SPI query fails, `PgTryBuilder` catches it, `ERROR` returned, old graph remains loaded.

### Licensing

Apache License 2.0. The extension is a standalone project that reads from AGE's data but does not fork or modify AGE code.

## Consequences

### Positive

- Traversal queries at any depth complete in milliseconds, not seconds
- Removes the hard depth-5 ceiling on neighborhood exploration
- Enables analysis patterns currently impossible: large connected components, graph diameter, centrality metrics
- No changes to AGE or the existing write path
- Standalone benchmark binary enables performance testing at target scale without infrastructure
- Rust + pgrx provides memory safety — no segfault risk to Postgres
- Apache 2.0 license allows broad adoption and contribution

### Negative

- Adds ~3GB memory footprint at target scale (acceptable on 128GB+ machines)
- Cold start after Postgres restart requires full graph reload before traversal queries are available
- Epoch-based full reload under rapid write workloads (bulk ingestion) may cause repeated reloads; may need write-batching or reload-debounce logic
- New technology in the stack (Rust, pgrx) — different skills from the Python/TypeScript codebase
- Extension must be recompiled for each major PostgreSQL version

### Neutral

- AGE continues to handle all writes and simple queries — no migration needed
- The API layer's query routing logic needs to decide when to use AGE vs the extension (depth threshold, or always prefer extension when loaded)
- The existing Python-side parallel query optimization (asyncio.gather for per-depth queries) remains as a fallback when the extension is not installed
- Document/Source/Instance nodes are NOT loaded by default in our configuration — the extension only covers Concept-to-Concept edges. Other users can configure `node_labels = '*'` to load their full graph.
- The generic design (configurable labels, properties, edge types) adds some complexity over a hardcoded solution, but makes the extension useful to the broader AGE community — anyone hitting the same traversal wall benefits

## Alternatives Considered

### Keep AGE, optimize with Python-side BFS

Load the edge list via a flat Cypher query into a Python dict, traverse in Python. This works and is what we'd do as a stopgap. Rejected as the long-term solution because:
- Adds latency from the Python→Postgres round-trip for the edge dump
- Python dict-based BFS is slower than Rust at scale (50M edges)
- No shared memory — each API worker process would need its own copy
- Not reusable by other Postgres clients (CLI, MCP server)

### Switch to a native graph database (Neo4j, Memgraph, KuzuDB)

Would solve the traversal problem but:
- Neo4j: encumbered license (SSPL/commercial for enterprise features)
- Memgraph: BSL license, requires separate server process
- KuzuDB: MIT, embedded, compelling — but adds a second data store to sync
- All options lose the single-Postgres advantage (one backup, one connection, one transaction scope)
- The extension approach gets native-graph performance without leaving Postgres

### Contribute traversal improvements to Apache AGE

AGE's `age_global_graph` already attempts in-memory caching for VLE queries, but it has known memory leaks and is not designed for general traversal acceleration. Contributing upstream is possible but:
- AGE's C codebase is large and complex
- The Apache Foundation contribution process is slow
- Our needs are specific (read-only traversal acceleration, not general Cypher optimization)
- A standalone extension can ship independently and faster

### PuppyGraph or similar overlay engine

PuppyGraph queries existing relational stores directly as a graph. Interesting but:
- Not open source (proprietary, free tier only)
- External service dependency
- Our graph is simple enough that an adjacency list solves it
