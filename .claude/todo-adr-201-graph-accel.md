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
Branch: `feature/graph-accel-pgrx-shell`
- [x] Wire up pgrx 0.16.1 extension: `_PG_init`, 7 GUC parameters registered
- [x] Implement `graph_accel_status()` — returns extension state (works when unloaded)
- [x] Implement `graph_accel_load(graph_name)` — SPI reads AGE label catalog, loads per-table with filtering
- [x] Implement `graph_accel_neighborhood(start_id, max_depth)` — BFS via core engine, dual node resolution
- [x] Implement `graph_accel_path(from_id, to_id, max_hops)` — shortest path via core engine
- [x] Verified: `cargo pgrx run pg17` — extension loads, status/GUCs work in PG 17.7
- [ ] Option 0 deployment: copy .so into running `knowledge-graph-postgres` container, test against live graph

## Phase 3: Epoch Invalidation
- [ ] Create `graph_accel_epoch` table and trigger on AGE vertex/edge tables
- [ ] Implement epoch check in query functions (stale → auto-reload or error)
- [ ] Implement `graph_accel.reload_debounce_sec` logic
- [ ] Test: mutate graph via AGE, verify epoch increments, verify reload triggers

## Phase 4: Generic Configuration
- [ ] Implement `graph_accel.node_labels` filtering (load subset of node types)
- [ ] Implement `graph_accel.edge_types` filtering
- [ ] Implement `graph_accel.node_id_property` (secondary index on application-level IDs)
- [ ] Test with a non-knowledge-graph AGE schema to verify generality

## Phase 5: Integration & Deployment
- [ ] Wire API layer: route `/query/related` through graph_accel when available, fall back to AGE
- [ ] Option A deployment: volume mount in docker-compose.yml
- [ ] Option B deployment: custom Dockerfile extending apache/age
- [ ] Update `operator.sh` for graph_accel-aware Postgres image
- [ ] Benchmark: compare AGE direct vs graph_accel for depths 2-10 on real data

## Phase 6: Polish & Publish
- [ ] Implement `graph_accel_degree()` — degree centrality
- [ ] Implement `graph_accel_subgraph()` — connected component extraction
- [ ] Write extension README with install instructions, examples, benchmarks
- [ ] Set up CI: `cargo pgrx test` + standalone benchmark regression
- [ ] Publish to GitHub as standalone repo (Apache 2.0)
- [ ] Submit to PGXN (PostgreSQL Extension Network)

## Notes
- pgrx requires matching PG major version — current container is PG 17.7
- Shared memory allocated at startup, fixed size — `max_memory_mb` is a hard cap
- Threading: none inside the extension. Postgres is single-threaded per backend.
- The standalone bench binary is critical for development — most iteration happens outside Postgres
