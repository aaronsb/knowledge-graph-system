# ADR-201 Implementation: In-Memory Graph Acceleration Extension

ADR: [ADR-201](docs/architecture/database-schema/ADR-201-in-memory-graph-acceleration-extension.md)

## Phase 1: Scaffold & Proof of Concept ✓
Merged: PR #263 → `main`
- [x] Initialize Rust workspace (`graph-accel/` with `core` and `bench` crates)
- [x] Set up dual build: `graph-accel-core` lib (no Postgres deps) + `graph-accel-bench` binary
- [x] Implement core adjacency structure (`HashMap<NodeId, Vec<Edge>>`) in `graph-accel-core`
- [x] Implement BFS neighborhood traversal with visited-set pruning (parent pointers, lazy path reconstruction)
- [x] Implement shortest path (BFS, unweighted, parent backtracking)
- [x] Write standalone benchmark with 6 topology generators (L-system, scale-free, small-world, Erdos-Renyi, barbell, DLA)
- [x] Validate at target scale: 5M nodes / 50M edges — bounded-depth queries in ms, full-graph traversal in seconds
- [x] 26 unit tests (chains, stars, cycles, self-loops, parallel edges, depth limits, undirected, app IDs, bounds checks)
- [x] Code review: EdgeRecord struct, parent-pointer BFS, u16 bounds check, memory_usage accuracy, VecDeque DLA

## Phase 2: PostgreSQL Extension Shell ✓
Merged: PR #265 → `main`
- [x] Wire up pgrx 0.16.1 extension: `_PG_init`, 7 GUC parameters registered
- [x] Implement `graph_accel_status()` — returns extension state (works when unloaded)
- [x] Implement `graph_accel_load(graph_name)` — SPI reads AGE label catalog, loads per-table with filtering
- [x] Implement `graph_accel_neighborhood(start_id, max_depth)` — BFS via core engine, dual node resolution
- [x] Implement `graph_accel_path(from_id, to_id, max_hops)` — shortest path via core engine
- [x] Verified: `cargo pgrx run pg17` — extension loads, status/GUCs work in PG 17.7
- [x] Option 0 deployment: copy .so into running container, tested against live graph
  - Fixed: `ag_label.name` type cast (Postgres `name` → `text`), GUC contexts (Sighup → Userset for Phase 2)
  - 788 nodes / 2,159 edges loaded in 22ms from live AGE graph
  - Depth 5 neighborhood: 0.378ms vs AGE 92,474ms (244,600x speedup)
  - Depth 6+: sub-ms vs AGE hangs — infinite speedup
  - Data validation: depth-1 exact match (11/11), depth-2 strict superset (45/45 + 4 via cross-type paths)
  - See: `graph-accel/docs/benchmark-findings.md`

## Phase 3: Cache Invalidation ✓
Merged: PR #267 → `main`
- [x] Generation-based cache invalidation (terminology: generation counter, not "epoch")
- [x] `graph_accel.generation` table — monotonic counter per graph, bootstrap SQL via `extension_sql!`
- [x] `graph_accel_invalidate(graph_name)` — bumps generation + `pg_notify('graph_accel', graph_name)`
- [x] Staleness check in query functions (`ensure_fresh()` — ~0.01ms SPI overhead per query)
- [x] `auto_reload` + `reload_debounce_sec` GUCs now wired
- [x] `graph_accel_status()` enhanced: `loaded_generation`, `current_generation`, `is_stale`
- [x] Graceful degradation: reload failures caught via `PgTryBuilder`, serves stale with warning
- [x] Validated: all 4 invalidation tests pass in benchmark-comparison.sh
- [x] Extension version: 0.1.0 → 0.2.0

## Phase 3.5: Documentation ✓
Merged: PR #266 → `main`
- [x] `graph-accel/README.md` — external-facing for pgrx community / AGE users
- [x] `graph-accel/docs/DESIGN.md` — technical deep dive for contributors
- [x] `graph-accel/tests/deploy-option0.sh` — scripted Option 0 deployment
- [x] Update README + DESIGN.md with `graph_accel_invalidate()` and cache invalidation section

## Phase 3.7: Direction Tracking ✓
Merged: PR #268 → `main`
- [x] `Direction` enum (Outgoing/Incoming) stored per edge traversal
- [x] `path_directions` column on `graph_accel_neighborhood()`
- [x] `direction` column on `graph_accel_path()`
- [x] Direction correctness validated in benchmark-comparison.sh (symmetry, depth-1, path)
- [x] Extension version: 0.2.0 → 0.3.0

## Phase 4: Integration Enablers ✓
Merged: PR #269 → `main`
- [x] `TraversalDirection` enum (Outgoing/Incoming/Both) — `direction_filter` param on neighborhood, path, subgraph
- [x] `iter_neighbors()` helper with boolean flags (zero-cost directed filtering)
- [x] `graph_accel_degree(top_n)` — degree centrality, nodes ranked by total degree
- [x] `graph_accel_subgraph(start_id, max_depth)` — BFS discovery + outgoing-only edge emission
- [x] Edge confidence filtering — `f32::NAN` sentinel, `min_confidence` param on neighborhood/path/subgraph
- [x] SPI loader reads confidence from AGE edge properties (JSON extraction)
- [x] Bounds checking for negative max_depth/max_hops/top_n at SQL boundary
- [x] `direction_str()` consolidated in util.rs
- [x] 56 core unit tests, benchmark-comparison.sh validates all features against live AGE
- [x] Extension version: 0.3.0 → 0.4.0

## Phase 4.5: Generic Configuration (partially complete)
- [x] `graph_accel.node_labels` filtering — implemented and tested (Concept-only load works)
- [x] `graph_accel.edge_types` filtering — implemented (GUC + filter logic in load.rs)
- [x] `graph_accel.node_id_property` — implemented and tested (concept_id resolution works)
- [ ] Edge filtering: skip edges where source/target not in loaded node set
- [ ] Test with a non-knowledge-graph AGE schema to verify generality

## Phase 5: API Integration

### 5a: age_client.py refactor (prerequisite — issue #243) ✓
Merged: PR #270 → `main`
- [x] Extract into domain mixin package: base, ingestion, query, ontology, ontology_scoring, ontology_edges, vocabulary
- [x] AGEClient composed via multiple inheritance, import interface unchanged

### 5b: Unified GraphFacade with two-phase query pattern ✓
Merged: PR #274 → `main`
- [x] `api/app/lib/graph_facade.py` — unified GraphFacade class
  - graph_accel availability detection (lazy, cached per-request)
  - `neighborhood()` — graph_accel_neighborhood fast path + Cypher fallback
  - `find_path()` / `find_paths()` — graph_accel_path + bidirectional BFS fallback
  - `degree()` — graph_accel_degree + Cypher OPTIONAL MATCH fallback
  - `subgraph()` — graph_accel_subgraph + Cypher edge list fallback
  - `match_sources()` / `match_concepts_for_sources_batch()` — carried from QueryFacade
  - `invalidate()` / `status()` / `is_accelerated()` — cache management
  - `_hydrate_concepts()` — batch property fetch for topology IDs
  - `_execute_sql()` — sync SQL helper for graph_accel function calls
- [x] `client.graph` lazy property wired on AGEClient (QueryMixin + BaseMixin)
- [x] Route migration — 4 routes use `client.graph.*`:
  - POST /query/related → `client.graph.neighborhood()`
  - POST /query/connect → `client.graph.find_paths()`
  - POST /query/connect-by-search → `client.graph.find_paths()`
  - POST /query/sources/search → `client.graph.match_sources()` + `match_concepts_for_sources_batch()`
- [x] `_build_connection_paths()` shared helper extracted (deduplicated from /connect and /connect-by-search)
- [x] Cache invalidation wired at mutation sites:
  - `ingestion_worker.py` — after batch completion
  - `routes/graph.py` — after batch create
  - `routes/ontology.py` — after reassign and dissolve
- [x] 32 unit tests (test_graph_facade.py): availability, neighborhood (accel + fallback),
      pathfinding, degree, invalidation, hydration, match_sources
- [x] Full suite: 975 passed, 0 failed

### 5c: Deployment
- [ ] Option A deployment: volume mount in docker-compose.yml
- [ ] Option B deployment: custom Dockerfile extending apache/age
- [ ] Update `operator.sh` for graph_accel-aware Postgres image
- [x] Call `graph_accel_invalidate()` after batch ingestion + graph mutations
- [x] Benchmark: compare AGE direct vs graph_accel for depths 1-5 on real data (see benchmark-findings.md)

### 5d: Multi-path acceleration (Yen's k-shortest-paths) ✓
Merged: PR #275 → `main`
- [x] Implement `k_shortest_paths()` in `graph-accel/core/src/traversal.rs` (Yen's algorithm)
- [x] Expose `graph_accel_paths(from_id, to_id, max_hops, max_paths, direction, confidence)` via pgrx
- [x] Extension version: 0.4.0 → 0.5.0
- [x] Deploy to container, validate with live data (5 paths in 0.128ms)
- [x] Wire `_find_paths_accel()` into GraphFacade, remove single-path-only guard
- [x] Benchmark: re-run baseline query (Graph Structure → Property Graph Databases, max_hops=4)
- [x] 14 new Rust unit tests + 3 new Python unit tests (70 Rust / 35 Python total)
- [x] Add standalone bench tests for k-shortest across 6 topologies
- [x] Add multi-path tests to `graph-accel/tests/benchmark-comparison.sh`
- [x] Fix empty middle node in APPEARS→APPEARS path chains (use AGE label as fallback)
- [x] Pinned dedicated connection for graph_accel — graph loads once, stays in memory
  - /query/related: 280ms → 14ms (20x improvement)
  - Eliminated 265ms graph reload on every request

### 5e: Cleanup
- [ ] Remove old facades: `query_facade.py`, `pathfinding_facade.py`, `query_service.py`
- [ ] Migrate remaining consumers (if any) to `client.graph.*`

## Phase 6: Polish & Publish
- [x] Implement `graph_accel_degree()` — degree centrality
- [x] Implement `graph_accel_subgraph()` — subgraph extraction
- [ ] Set up CI: `cargo pgrx test` + standalone benchmark regression
- [ ] Publish to GitHub as standalone repo (Apache 2.0)
- [ ] Submit to PGXN (PostgreSQL Extension Network)

### 5f: Generation-aware grounding cache (hydration optimization)
Branch: `feature/grounding-cache`

The topology phase (graph_accel) is sub-ms. The remaining 3-4s per connect query
is grounding hydration: `calculate_grounding_strength_semantic()` runs sequentially
per concept, each needing 2-3 Cypher round-trips.

Naive thread-pool parallelization doesn't work because `calculate_grounding_strength_semantic`
holds one pool connection while internally calling `_execute_cypher` (second connection).
10 threads × 2 connections = pool exhaustion. Confirmed: parallel version was 5.1s vs
sequential 3.7s due to ThreadedConnectionPool lock contention.

**Architecture: generation-aware cached hydration**

Polarity axis and per-concept grounding are both cacheable against the graph generation
counter. The key property: each concept's grounding is computed from its own incoming
edges — no cross-concept dependency. This makes per-concept caching safe.

- [ ] Cache polarity axis (vocabulary-level) — shared across all concepts
  - Invalidation key: `graph_metrics.vocabulary_change_counter` (already bumped by
    `refresh_graph_metrics()` after synonym consolidation in vocab_consolidate_worker.py:118)
  - Synonym collapse (CONCEDES→CONCEDE) triggers `merge_edge_types()` → worker calls
    `refresh_graph_metrics()` → counter bumps → polarity axis cache invalidates
  - No new wiring needed at the mutation site — existing signal suffices
  - This eliminates the polarity pair embedding query (runs once per vocab change, not per concept)
- [ ] Cache per-concept grounding against graph generation
  - Store: `{concept_id: (generation, grounding_strength, confidence_result)}`
  - On query: check `cached_generation == current_generation` → cache hit
  - On invalidation: generation bumps, all caches stale, recompute on next access
  - Storage: module-level dict (in-process), or pg table for cross-process
- [ ] Batch incoming-edges query — `WHERE c.concept_id IN [...]` for all path concepts
  - One Cypher round-trip instead of N
  - Same for confidence signals (`_gather_signals`)
- [ ] After batching: parallel computation in Python (dot products, thresholds — no DB)
  - Pure CPU work, no pool contention, ThreadPoolExecutor works correctly

- [ ] Docstrings: document the two-tier cache invalidation model
  - `calculate_grounding_strength_semantic()` — explain polarity axis caching, vocab generation check
  - `_build_connection_paths()` — explain per-concept grounding cache, graph generation check
  - `GraphFacade._execute_sql()` — explain pinned connection, generation-based ensure_fresh
  - `graph_facade.py` module docstring — explain the full pipeline: topology (sub-ms) → cached hydration

Expected improvement: 3.7s → ~0.5-1s for connect queries (warm cache hit: ~0.1s).

Two-tier invalidation (both signals already exist):
  | Cache layer        | Generation source                          | Signal origin                    |
  |--------------------|--------------------------------------------|----------------------------------|
  | Polarity axis      | graph_metrics.vocabulary_change_counter     | refresh_graph_metrics() after consolidation |
  | Per-concept ground | graph_accel.generation                      | graph_accel_invalidate() after mutations    |
  merge_edge_types() both deletes/recreates edges (graph mutation) AND triggers
  refresh_graph_metrics() (vocab mutation), so both caches invalidate correctly.

Analogy: id Tech GI probe caching — only update volumes where the player looks.
Graph generation is the "frame number"; if it hasn't changed, every cached value is valid.
Each concept's grounding is an independent "probe" — no mutual influence.

## Live API Benchmarks (2026-02-02, 1393 nodes / 412K edges)

Baseline query for multi-path comparison:
```
POST /query/connect
from: sha256:bd065_chunk4_c51b1769 (Graph Structure)
to:   sha256:bd065_chunk8_78c1711d (Property Graph Databases)
max_hops: 4, include_grounding: true
```

| Scenario | Time | Result |
|----------|------|--------|
| Cypher BFS only (no graph_accel) | >187s → terminated by restarting postgres | 500, 5 postgres workers at 95% CPU |
| graph_accel single path (cold, first load) | 2.3s | 200, 1 path / 2 hops |
| graph_accel multi-path Yen's k=5 (raw SQL, warm) | 0.128ms | 5 paths, 16 rows |
| graph_accel multi-path via API (cold, first load) | ~3s | 200, 5 paths (1/2/2/3/3 hops), includes grounding+evidence hydration |

Multi-path speedup vs Cypher: >1,400,000x (0.128ms vs >187,000ms).

## Notes
- pgrx 0.16.1 (latest stable), PostgreSQL 13-18, container is PG 17.7
- Per-backend state (thread_local + RefCell). Shared memory deferred.
- `Spi::connect` for reads, `Spi::connect_mut` for writes (pgrx 0.13+ API split)
- The standalone bench binary is critical for development — most iteration happens outside Postgres
- Deploy script: `./graph-accel/tests/deploy-option0.sh` (build + copy into container)
