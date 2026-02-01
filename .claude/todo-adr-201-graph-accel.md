# ADR-201 Implementation: In-Memory Graph Acceleration Extension

Branch: `feature/graph-accel-extension`
ADR: [ADR-201](docs/architecture/database-schema/ADR-201-in-memory-graph-acceleration-extension.md)

## Phase 1: Scaffold & Proof of Concept
- [ ] Initialize Rust workspace with pgrx (`cargo pgrx new graph_accel`)
- [ ] Set up dual build: `graph-accel-core` lib (no Postgres deps) + `graph-accel-pg` extension crate
- [ ] Implement core adjacency structure (`HashMap<NodeId, Vec<(TargetId, RelType)>>`) in `graph-accel-core`
- [ ] Implement BFS neighborhood traversal in `graph-accel-core`
- [ ] Implement shortest path in `graph-accel-core`
- [ ] Write standalone benchmark binary that generates synthetic graphs and traverses them
- [ ] Validate: benchmark at target scale (5M nodes, 50M edges) — confirm microsecond traversal

## Phase 2: PostgreSQL Extension Shell
- [ ] Wire up pgrx extension: `_PG_init`, GUC parameter registration
- [ ] Implement `graph_accel_status()` — returns extension state
- [ ] Implement `graph_accel_load(graph_name)` — SPI query to read AGE edge table, populate shared memory structure
- [ ] Implement `graph_accel_neighborhood(node_id, max_depth)` — BFS from shared memory, returns set
- [ ] Implement `graph_accel_path(from_id, to_id, max_hops)` — shortest path from shared memory
- [ ] Option 0 deployment: manually copy .so into running `knowledge-graph-postgres` container, test

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
