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

## Phase 5: API Integration ← NEXT

### 5a: age_client.py refactor (prerequisite — issue #243)
- [ ] Extract `age_query.py` — search, pathfinding, concept details, neighborhood
- [ ] Extract `age_ingestion.py` — concept/source/instance CRUD, matching
- [ ] Extract `age_ontology.py` — ontology nodes, lifecycle, scoring
- [ ] Extract `age_vocabulary.py` — vocab types, consolidation
- [ ] Shared base: connection pool + `_execute_cypher` helper

### 5b: Two-phase query pattern
graph_accel knows topology (IDs, labels, edges) but not properties (embeddings,
grounding_strength, descriptions). Integration pattern:
1. graph_accel → fast traversal (sub-ms): "which concept IDs within N hops?"
2. Direct SQL → targeted property hydration: "fetch properties for these IDs"

See `graph-accel/tests/benchmark-comparison.sh` header for the API integration
rosetta stone — maps each graph_accel function to its API worker replacement.

- [ ] Identify which `age_query.py` methods can use accelerated traversal
- [ ] Build hydration layer: given a set of node IDs from graph_accel, fetch full properties via SQL
- [ ] Wire `/query/related` through graph_accel + hydration, fall back to AGE if not loaded
- [ ] Ensure response shape is identical to current AGE-only path

### 5c: Deployment
- [ ] Option A deployment: volume mount in docker-compose.yml
- [ ] Option B deployment: custom Dockerfile extending apache/age
- [ ] Update `operator.sh` for graph_accel-aware Postgres image
- [ ] Call `graph_accel_invalidate()` after batch ingestion in `batch_service.py`
- [x] Benchmark: compare AGE direct vs graph_accel for depths 1-5 on real data (see benchmark-findings.md)

## Phase 6: Polish & Publish
- [x] Implement `graph_accel_degree()` — degree centrality
- [x] Implement `graph_accel_subgraph()` — subgraph extraction
- [ ] Set up CI: `cargo pgrx test` + standalone benchmark regression
- [ ] Publish to GitHub as standalone repo (Apache 2.0)
- [ ] Submit to PGXN (PostgreSQL Extension Network)

## Notes
- pgrx 0.16.1 (latest stable), PostgreSQL 13-18, container is PG 17.7
- Per-backend state (thread_local + RefCell). Shared memory deferred.
- `Spi::connect` for reads, `Spi::connect_mut` for writes (pgrx 0.13+ API split)
- The standalone bench binary is critical for development — most iteration happens outside Postgres
- Deploy script: `./graph-accel/tests/deploy-option0.sh` (build + copy into container)
