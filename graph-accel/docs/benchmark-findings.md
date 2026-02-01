# ADR-201 Benchmark Findings: AGE vs graph_accel

Companion to [ADR-201](../../docs/architecture/database-schema/ADR-201-in-memory-graph-acceleration-extension.md).

## Motivating Query

The performance investigation started with a **neighborhood search for "Way"** through the web workstation's block builder (NeighborhoodBlock). The query explored the highest-degree concept matching "way" at increasing depths, which became impractical beyond depth 4-5 via AGE.

### Test Environment

- **Hardware:** 16 cores / 32 threads, 128GB RAM
- **Database:** PostgreSQL 17.7, Apache AGE 1.6.0 (Debian container)
- **Graph:** ~236 concepts, ~339 instances, ~68 sources, ~120 edge types
- **Target concept:** "Way" (`sha256:990a8_chunk1_d7639f13`), degree 36 (2nd highest in graph)

### Top concepts by degree

| Rank | Concept | Degree |
|------|---------|--------|
| 1 | Homomorphism | 38 |
| 2 | **Way** | **36** |
| 3 | Domain | 34 |
| 4 | Business Capabilities | 31 |
| 5 | Graph Structure | 29 |

## Query Chain: Web UI → API → Cypher

### 1. Web Component

`web/src/components/blocks/NeighborhoodBlock.tsx` — block builder component with depth (1-5), direction (outgoing/incoming/both), and epistemic status filters.

### 2. Block Compiler

`web/src/lib/blockCompiler.ts` — compiles visual blocks into Cypher patterns. Generates variable-length paths like `(input)-[*1..N]->(neighbor:Concept)`.

### 3. API Client

`web/src/api/client.ts` — calls `POST /query/related` with `concept_id`, `max_depth`, optional `relationship_types`.

### 4. API Endpoint

`api/app/routes/queries.py` — `/query/related` route. Resolves epistemic filters, builds per-depth queries, executes in parallel via `asyncio.gather()`.

### 5. Query Builder

`api/app/services/query_service.py:113-175` — `build_related_concepts_query()`. Generates **fixed-depth chain queries** (not `[*1..N]` variable-length paths) to avoid combinatorial explosion.

### 6. Generated Cypher (per depth)

**Depth 1:**
```cypher
MATCH (start:Concept {concept_id: $concept_id})-[r0]-(target:Concept)
WHERE start <> target
WITH DISTINCT target.concept_id as concept_id,
    target.label as label,
    [type(r0)] as path_types
RETURN concept_id, label, 1 as distance, path_types
```

**Depth 2:**
```cypher
MATCH (start:Concept {concept_id: $concept_id})-[r0]-(h1:Concept)-[r1]-(target:Concept)
WHERE start <> target
WITH DISTINCT target.concept_id as concept_id,
    target.label as label,
    [type(r0), type(r1)] as path_types
RETURN concept_id, label, 2 as distance, path_types
```

**Depth N (general pattern):**
```cypher
MATCH (start:Concept {concept_id: $concept_id})
    -[r0]-(h1:Concept)
    -[r1]-(h2:Concept)
    ...
    -[r{N-1}]-(target:Concept)
WHERE start <> target
WITH DISTINCT target.concept_id as concept_id,
    target.label as label,
    [type(r0), type(r1), ..., type(r{N-1})] as path_types
RETURN concept_id, label, {N} as distance, path_types
```

Each depth runs as a separate query. Results merged in Python keeping minimum distance per concept.

### 7. Execution

All depth queries dispatched in parallel via `asyncio.to_thread()`, each getting its own connection from AGE's `ThreadedConnectionPool`.

## AGE Baseline Timing

Measured with `\timing` inside psql (pure SQL execution time, no client overhead).

Concept: "Way" (`sha256:990a8_chunk1_d7639f13`), degree 36.

| Depth | Concepts Found | SQL Time | Notes |
|-------|---------------|----------|-------|
| 1 | 11 | 3,644ms | Consistent across runs; ~120 edge table scan overhead |
| 2 | 45 | 471ms | Different query plan — AGE uses index joins |
| 3 | 73 | 1,790ms | |
| 4 | 105 | 11,460ms | ~12 table join |
| 5 | 124 | 92,474ms | 1.5 minutes for 124 concepts |
| 6 | — | Hangs | Expected based on prior testing |

### Observations

**Depth 1 anomaly:** Depth 1 is consistently ~3.6s even on warm cache — slower than depth 2. AGE generates a plan that scans all ~120 edge label tables (UNION ALL) for a single-hop untyped traversal. The plan is structurally expensive regardless of result count.

**Depth 2 is faster than depth 1:** AGE appears to use a different plan for multi-hop chains (explicit hop variables force index-based joins instead of a brute-force UNION across all edge tables).

**Exponential growth:** From depth 2 onward, timing grows roughly exponentially:
- Depth 2→3: 3.8x
- Depth 3→4: 6.4x
- Depth 4→5: 8.1x

**Depth 5 wall:** 92 seconds to find 124 concepts in a 236-node graph. At this rate, depth 6 generates a 12-table SQL join with O(degree^6) intermediate rows before DISTINCT collapses them.

## graph_accel Measured Timing (Option 0 Deployment)

Loaded 788 nodes (all types: Concept, Instance, Source, VocabType, etc.) and 2,159 edges in **22ms**. Memory: 312KB. 123 relationship types interned.

Measured with psql `\timing`, same "Way" concept.

**Note on node counts:** graph_accel finds more nodes than AGE at each depth because it traverses ALL node types (Concept + Instance + Source + VocabType), while the AGE benchmark queries filtered to `(target:Concept)` only. The traversal is broader but the timing comparison is valid — both start from the same node and traverse the same edges.

| Depth | Nodes Found | graph_accel Time | AGE Time | Speedup |
|-------|------------|-----------------|----------|---------|
| 1 | 23 | 0.101ms | 3,644ms | 36,000x |
| 2 | 103 | 0.066ms | 471ms | 7,100x |
| 3 | 232 | 0.122ms | 1,790ms | 14,700x |
| 4 | 508 | 0.267ms | 11,460ms | 42,900x |
| 5 | 679 | 0.378ms | 92,474ms | **244,600x** |
| 6 | 679 | 0.377ms | Hangs | **∞** |
| 10 | 679 | 0.376ms | Impossible | **∞** |

Graph saturation at depth 6: 679 of 788 nodes (86%) reachable from "Way". Remaining 109 nodes in disconnected components.

**Shortest path** ("Way" → "Homomorphism", the two highest-degree hubs):
- 3 hops: Way → INFLUENCES → ANALOGOUS_TO → REQUIRES → Homomorphism
- Time: **0.111ms**
- AGE equivalent would require a variable-length path query or BFS in Python

**Load time comparison:**
- graph_accel_load(): 22ms (788 nodes, 2,159 edges via SPI)
- This is a one-time cost per backend; subsequent queries are sub-millisecond

## Data Correctness Validation

Verified graph_accel returns the same concept set as AGE.

**Depth 1 — exact match:**
- AGE: 11 concepts | graph_accel: 11 concepts
- Diff: **0 differences** — identical concept_id sets

**Depth ≤ 2 — superset:**
- AGE: 45 concepts | graph_accel: 49 concepts
- All 45 AGE concepts present in graph_accel: **yes**
- Missing from graph_accel: **0**
- Extra in graph_accel: **4** (reached via non-Concept intermediaries)

The 4 extra concepts are reachable through Instance/Source intermediate nodes. AGE's Cypher query `(Concept)-[r]-(Concept)` restricts traversal to Concept-only paths. graph_accel's BFS traverses all edges regardless of intermediate node type, finding Concept nodes reachable via `Concept → Instance → Concept` or `Concept → Source → Concept` 2-hop paths.

**Implication for API integration (Phase 5):**
- When replacing `/query/related`, either filter graph_accel results to Concept-only OR load with `node_labels = 'Concept'` AND add edge filtering to skip cross-type edges
- Alternatively, accept the broader traversal — the extra concepts are genuinely connected and may be valuable for discovery

## Benchmark SQL (for reproduction)

```sql
-- Setup
LOAD 'age';
SET search_path = ag_catalog, public;

-- Verify target concept
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (c:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})
    RETURN c.concept_id, c.label
$$) as (concept_id agtype, label agtype);

-- AGE depth-N benchmark (replace N, add/remove hops as needed)
\timing on

-- Depth 1
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (start:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})-[r0]-(target:Concept)
    WHERE start <> target
    WITH DISTINCT target.concept_id as concept_id, target.label as label
    RETURN count(*) as found
$$) as (found agtype);

-- Depth 2
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (start:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})-[r0]-(h1:Concept)-[r1]-(target:Concept)
    WHERE start <> target
    WITH DISTINCT target.concept_id as concept_id, target.label as label
    RETURN count(*) as found
$$) as (found agtype);

-- Depth 3
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (start:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})-[r0]-(h1:Concept)-[r1]-(h2:Concept)-[r2]-(target:Concept)
    WHERE start <> target
    WITH DISTINCT target.concept_id as concept_id, target.label as label
    RETURN count(*) as found
$$) as (found agtype);

-- Depth 4
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (start:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})-[r0]-(h1:Concept)-[r1]-(h2:Concept)-[r2]-(h3:Concept)-[r3]-(target:Concept)
    WHERE start <> target
    WITH DISTINCT target.concept_id as concept_id, target.label as label
    RETURN count(*) as found
$$) as (found agtype);

-- Depth 5
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (start:Concept {concept_id: 'sha256:990a8_chunk1_d7639f13'})-[r0]-(h1:Concept)-[r1]-(h2:Concept)-[r2]-(h3:Concept)-[r3]-(h4:Concept)-[r4]-(target:Concept)
    WHERE start <> target
    WITH DISTINCT target.concept_id as concept_id, target.label as label
    RETURN count(*) as found
$$) as (found agtype);

-- graph_accel equivalent (after deployment)
CREATE EXTENSION IF NOT EXISTS graph_accel;
SET graph_accel.source_graph = 'knowledge_graph';
SET graph_accel.node_id_property = 'concept_id';
SELECT * FROM graph_accel_load();

\timing on
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 1);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 2);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 3);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 4);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 5);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 6);
SELECT * FROM graph_accel_neighborhood('sha256:990a8_chunk1_d7639f13', 10);
```
