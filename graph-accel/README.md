# graph_accel

In-memory graph traversal acceleration for [Apache AGE](https://age.apache.org/).

**License:** Apache-2.0 | **pgrx:** 0.16.1 | **PostgreSQL:** 13-18

## The Problem

Apache AGE stores graphs in PostgreSQL and translates Cypher path matches into nested SQL joins. For multi-hop traversals, this creates O(degree^depth) intermediate rows that the relational planner cannot optimize. On a 236-node graph with ~120 edge types:

| Depth | AGE (SQL) | graph_accel | Speedup |
|-------|-----------|-------------|---------|
| 1 | 3,644ms | 0.101ms | 36,000x |
| 2 | 471ms | 0.066ms | 7,100x |
| 3 | 1,790ms | 0.122ms | 14,700x |
| 4 | 11,460ms | 0.267ms | 42,900x |
| 5 | 92,474ms | 0.378ms | **244,600x** |
| 6 | Hangs | 0.377ms | --- |

AGE hits a hard wall at depth 6. graph_accel handles arbitrary depth in sub-millisecond time.

## The Solution

A PostgreSQL extension (built with [pgrx](https://github.com/pgcentralfoundation/pgrx)) that loads AGE's edge graph into an in-memory adjacency list and exposes fast traversal functions via SQL.

- **Pure Rust core** with zero external dependencies
- **BFS via pointer chases** instead of SQL joins
- **Generic** -- works with any AGE graph, any node labels, any edge types
- **Read-only** -- AGE remains the source of truth for all writes

## Quick Start

```sql
-- Load the extension
CREATE EXTENSION graph_accel;

-- Configure (optional -- can also pass graph name directly)
SET graph_accel.source_graph = 'my_graph';
SET graph_accel.node_id_property = 'concept_id';

-- Load the graph into memory (22ms for ~800 nodes)
SELECT * FROM graph_accel_load('my_graph');
--  node_count | edge_count | load_time_ms
-- ------------+------------+--------------
--         788 |       2159 |    22.285593

-- Neighborhood: all nodes within 5 hops
SELECT * FROM graph_accel_neighborhood('my_node_id', 5);

-- Shortest path between two nodes
SELECT * FROM graph_accel_path('node_a', 'node_b');

-- Check status
SELECT * FROM graph_accel_status();

-- Signal cache invalidation after mutations
SELECT graph_accel_invalidate('my_graph');
```

## SQL Reference

### graph_accel_load

```sql
graph_accel_load(graph_name TEXT DEFAULT NULL)
  RETURNS TABLE(node_count BIGINT, edge_count BIGINT, load_time_ms FLOAT8)
```

Loads an AGE graph into memory via SPI. Reads AGE's internal label catalog, then bulk-loads vertices and edges from per-label tables. Filters by `node_labels` and `edge_types` GUCs. Checks memory against `max_memory_mb`.

If `graph_name` is NULL, uses the `graph_accel.source_graph` GUC.

### graph_accel_neighborhood

```sql
graph_accel_neighborhood(
    start_id TEXT,
    max_depth INT DEFAULT 3,
    direction_filter TEXT DEFAULT 'both',
    min_confidence FLOAT8 DEFAULT NULL
)
  RETURNS TABLE(
    node_id         BIGINT,
    label           TEXT,
    app_id          TEXT,       -- NULL if node_id_property not configured
    distance        INT,
    path_types      TEXT[],     -- relationship types along one shortest path
    path_directions TEXT[]      -- 'outgoing' or 'incoming', parallel to path_types
  )
```

BFS from `start_id` up to `max_depth` hops. Returns all reachable nodes with their minimum distance, the relationship types along one shortest path, and the direction each edge was traversed.

`direction_filter`: `'both'` (default, undirected), `'outgoing'` (forward edges only), or `'incoming'` (reverse edges only). `min_confidence`: when set, skips edges with loaded confidence below this threshold. Edges without confidence data always pass.

Node resolution: tries `node_id_property` lookup first, then falls back to parsing as an AGE internal graph ID.

### graph_accel_path

```sql
graph_accel_path(
    from_id TEXT,
    to_id TEXT,
    max_hops INT DEFAULT 10,
    direction_filter TEXT DEFAULT 'both',
    min_confidence FLOAT8 DEFAULT NULL
)
  RETURNS TABLE(
    step      INT,
    node_id   BIGINT,
    label     TEXT,
    app_id    TEXT,
    rel_type  TEXT,         -- relationship type on the edge TO this node (NULL for start)
    direction TEXT           -- 'outgoing', 'incoming', or NULL for start node
  )
```

Finds the unweighted shortest path between two nodes. Returns the full path as ordered steps (0-indexed). Empty result set if no path exists within `max_hops` -- not an error. `direction_filter` and `min_confidence` work the same as in `graph_accel_neighborhood`.

### graph_accel_degree

```sql
graph_accel_degree(top_n INT DEFAULT 100)
  RETURNS TABLE(
    node_id      BIGINT,
    label        TEXT,
    app_id       TEXT,
    out_degree   INT,
    in_degree    INT,
    total_degree INT
  )
```

Returns nodes ranked by total degree (descending). `top_n = 0` returns all nodes. Useful for hub detection, ontology scoring, and annealing candidate ranking.

### graph_accel_subgraph

```sql
graph_accel_subgraph(
    start_id TEXT,
    max_depth INT DEFAULT 3,
    direction_filter TEXT DEFAULT 'both',
    min_confidence FLOAT8 DEFAULT NULL
)
  RETURNS TABLE(
    from_id     BIGINT,
    from_label  TEXT,
    from_app_id TEXT,
    to_id       BIGINT,
    to_label    TEXT,
    to_app_id   TEXT,
    rel_type    TEXT
  )
```

Extracts the edge list within the subgraph reachable from `start_id`. Phase 1 discovers nodes via BFS, Phase 2 emits edges between discovered nodes. Useful for relationship counting, cross-ontology edge analysis, and component extraction.

### graph_accel_invalidate

```sql
graph_accel_invalidate(graph_name TEXT)
  RETURNS BIGINT  -- new generation number
```

Bumps the generation counter for `graph_name` and fires `pg_notify('graph_accel', graph_name)`. Call this after modifying the graph (AGE bypasses PostgreSQL triggers, so invalidation must be cooperative). The returned generation is monotonically increasing.

If `auto_reload` is enabled, the next query function call detects the generation mismatch and reloads automatically (subject to `reload_debounce_sec`).

### graph_accel_status

```sql
graph_accel_status()
  RETURNS TABLE(
    source_graph       TEXT,
    status             TEXT,     -- 'loaded', 'stale', or 'not_loaded'
    node_count         BIGINT,
    edge_count         BIGINT,
    memory_bytes       BIGINT,
    rel_type_count     INT,
    loaded_generation  BIGINT,   -- generation at time of last load
    current_generation BIGINT,   -- current generation from table
    is_stale           BOOL      -- loaded_generation < current_generation
  )
```

Always works, even when no graph is loaded. Returns the current state of the per-backend graph including cache freshness.

## Configuration

All parameters are set via PostgreSQL GUCs (`SET`, `ALTER SYSTEM SET`, or `postgresql.conf`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `graph_accel.source_graph` | text | *(none)* | AGE graph name. Required for `graph_accel_load()` when no argument given. |
| `graph_accel.max_memory_mb` | int | 4096 | Memory cap per backend. Load fails if graph exceeds this. Range: 64--131,072. |
| `graph_accel.node_id_property` | text | *(none)* | Node property to index for app-level lookups (e.g., `concept_id`). Empty = AGE internal IDs only. |
| `graph_accel.node_labels` | text | `*` | Comma-separated vertex labels to load, or `*` for all. |
| `graph_accel.edge_types` | text | `*` | Comma-separated edge types to load, or `*` for all. |
| `graph_accel.auto_reload` | bool | true | Automatically reload when generation mismatch detected. |
| `graph_accel.reload_debounce_sec` | int | 5 | Minimum seconds between reloads. Prevents thrashing during bulk writes. |

## Building

### Prerequisites

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install pgrx
cargo install cargo-pgrx --version 0.16.1 --locked

# Initialize pgrx for your PostgreSQL version
cargo pgrx init --pg17=download    # or point to your pg_config
```

### Build the extension

```bash
cd graph-accel

# Development (runs a temporary Postgres instance)
cargo pgrx run pg17

# Package for deployment
cargo pgrx package --pg-config $(which pg_config)
```

### Build the standalone benchmark

```bash
cd graph-accel

# Release build (recommended -- uses LTO for best performance)
cargo build --release -p graph-accel-bench

# Run at default scale (5M nodes)
./target/release/graph_accel_bench

# Run a specific topology at custom scale
./target/release/graph_accel_bench scalefree 1000000
```

## Installation

### Pre-built artifacts (recommended)

Pre-built artifacts for `apache/age` (PostgreSQL 17, Debian trixie) are in `dist/pg17/`, organized by architecture:

```
dist/pg17/
├── amd64/
│   ├── graph_accel.so          # Shared library (x86-64)
│   ├── graph_accel.control     # Extension metadata
│   └── graph_accel--0.5.0.sql  # Function definitions
└── arm64/
    ├── graph_accel.so          # Shared library (aarch64)
    ├── graph_accel.control
    └── graph_accel--0.5.0.sql
```

Copy the three files matching your container's architecture into any `apache/age` container:

```bash
# Use amd64/ or arm64/ to match your container architecture
docker cp dist/pg17/amd64/graph_accel.so \
  my-container:/usr/lib/postgresql/17/lib/
docker cp dist/pg17/amd64/graph_accel.control \
  my-container:/usr/share/postgresql/17/extension/
docker cp dist/pg17/amd64/graph_accel--0.5.0.sql \
  my-container:/usr/share/postgresql/17/extension/

docker exec my-container psql -U postgres -d mydb \
  -c "CREATE EXTENSION graph_accel;"
```

**Compatibility:** The `.so` is built inside the official `apache/age` Docker image, so it is ABI-compatible with that exact image. If you use a different PostgreSQL build, rebuild from source (see Building below).

### Building the artifacts

To rebuild for the current `apache/age` image (guarantees ABI compatibility):

```bash
./build-in-container.sh              # host arch only (fast)
./build-in-container.sh --all        # amd64 + arm64
./build-in-container.sh --platform linux/arm64  # specific arch
# → produces dist/pg17/<arch>/{graph_accel.so, .control, .sql}
```

This spins up a temporary Docker container with the `apache/age` base, installs the Rust toolchain + pgrx, compiles the extension, and extracts the artifacts. Docker layer caching makes rebuilds fast.

### Dockerfile (bake into a custom image)

```dockerfile
FROM apache/age
ARG TARGETARCH
COPY dist/pg17/${TARGETARCH}/graph_accel.so /usr/lib/postgresql/17/lib/
COPY dist/pg17/${TARGETARCH}/graph_accel.control /usr/share/postgresql/17/extension/
COPY dist/pg17/${TARGETARCH}/graph_accel--*.sql /usr/share/postgresql/17/extension/
```

### Development deployment

For rapid iteration with a host Rust toolchain:

```bash
# Build on host + deploy into running container
./tests/deploy-option0.sh

# Or build in container + deploy
./build-in-container.sh
./tests/deploy-option0.sh --skip-build
```

## Project Structure

```
graph-accel/
├── Cargo.toml          # Workspace: core, bench, ext
├── build-in-container.sh  # Build inside apache/age for ABI compatibility
├── Dockerfile.build    # Multi-stage Dockerfile for container builds
├── dist/pg17/{amd64,arm64}/  # Pre-built artifacts for apache/age (PG 17)
├── core/               # Pure Rust traversal engine
│   └── src/
│       ├── graph.rs    #   Adjacency list, node index, rel-type interning
│       ├── traversal.rs#   BFS neighborhood, shortest path
│       └── lib.rs      #   Public API
├── bench/              # Standalone benchmark binary
│   └── src/
│       └── main.rs     #   6 topology generators, benchmark harness
├── ext/                # pgrx PostgreSQL extension
│   ├── graph_accel.control
│   └── src/
│       ├── lib.rs      #   _PG_init, module declarations
│       ├── guc.rs      #   7 GUC parameters
│       ├── state.rs    #   Per-backend graph state (thread_local)
│       ├── load.rs     #   SPI bulk load from AGE tables
│       ├── generation.rs #  Cache invalidation, staleness check
│       ├── status.rs   #   graph_accel_status()
│       ├── neighborhood.rs  # graph_accel_neighborhood()
│       ├── path.rs     #   graph_accel_path()
│       ├── degree.rs   #   graph_accel_degree()
│       ├── subgraph.rs #   graph_accel_subgraph()
│       └── util.rs     #   Shared helpers (direction parsing)
├── docs/               # Design docs, benchmark data
│   ├── DESIGN.md       #   Technical deep dive
│   └── benchmark-findings.md  # Measured performance data
└── tests/              # Integration tests
    ├── benchmark-comparison.sh  # AGE vs graph_accel automated comparison
    └── deploy-option0.sh        # Scripted Option 0 deployment
```

**Core:** Pure Rust traversal engine with unit tests. No PostgreSQL dependencies.
**Extension:** pgrx wrapper — SPI loading, GUCs, SQL function bindings.
**Bench:** Standalone binary for profiling outside Postgres.

## Standalone Benchmark

The benchmark binary generates synthetic graphs at configurable scale and measures traversal performance. Six topologies test different graph characteristics:

| Topology | Structure | What it stresses |
|----------|-----------|-----------------|
| L-system | Fractal tree (ternary branching) | Deep BFS, path reconstruction on long chains |
| Scale-free | Power-law hubs (Barabasi-Albert) | High fan-out, realistic knowledge graph structure |
| Small-world | Ring lattice + rewiring (Watts-Strogatz) | Clustering with short global paths |
| Erdos-Renyi | Uniform random edges | Baseline with no structural bias |
| Barbell | Two cliques + thin bridge | Bottleneck pathfinding |
| DLA | Diffusion-limited aggregation | Organic branching, tree-like with shortcuts |

At 5M nodes / 50M edges on the scale-free topology, BFS reaches the entire graph at depth 5 in 15 seconds. Bounded-depth queries (the typical API pattern) complete in single-digit milliseconds.

```bash
$ ./target/release/graph_accel_bench scalefree 5000000
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Core engine | Done | Adjacency list, BFS, shortest path, 6-topology benchmark |
| 2. pgrx extension | Done | SQL functions, SPI loading, GUCs, per-backend state |
| 3. Cache invalidation | Done | Generation-based staleness, auto-reload, debouncing |
| 4. Integration enablers | Done | Directed traversal, degree centrality, subgraph extraction, confidence filtering |
| 5. API integration | Done | GraphFacade with accel fast path + Cypher fallback, container deployment |
| 6. Shared memory | Deferred | Cross-backend graph sharing, background worker reload |
| 7. Publish | Planned | Standalone repo, PGXN submission |

See [docs/DESIGN.md](docs/DESIGN.md) for architectural details and design rationale.

## License

Apache License 2.0. See [LICENSE](../LICENSE) for details.
