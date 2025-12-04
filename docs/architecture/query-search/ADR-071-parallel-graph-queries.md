# ADR-071: Parallel Graph Query Optimization

**Status:** Accepted
**Date:** 2025-12-01
**Updated:** 2025-12-04 (findings documented in ADR-071a)

## Context

Graph traversal queries with variable-length paths `[*1..N]` exhibit severe performance degradation as hop count increases. Polarity axis analysis (`api/lib/polarity_axis.py`) with `max_hops=2` takes over 3 minutes (180-261 seconds), making the feature unusable for interactive analysis.

### The Problem

When discovering candidates within 2 hops of two pole concepts:

1. Find all 1-hop neighbors of poles → ~200 concepts (500ms ✓)
2. Find neighbors of those 200 concepts → 200 × 100 = 20,000 potential paths (3+ min ✗)

**Root Cause:** PostgreSQL cannot parallelize Apache AGE Cypher queries because `ag_catalog.cypher()` appears as an opaque function call. PostgreSQL's parallel query machinery never activates.

**Affected Patterns:**
- Polarity candidate discovery (`api/lib/polarity_axis.py:190`)
- Neighborhood queries (`api/services/diversity_analyzer.py:174`)
- Path enrichment (web UI subgraph expansion)

All follow the same pattern: multi-hop traversal from seed concepts.

## Decision

Implement application-level parallelization using Python's `ThreadPoolExecutor` with connection pooling to execute multiple small Cypher queries concurrently instead of one large variable-length path query.

### Architecture: 2-Phase Parallel Execution

**Phase 1: Direct Neighbors (1-hop) - Single Batched Query**
```cypher
MATCH (seed:Concept)-[]-(neighbor:Concept)
WHERE seed.concept_id IN $seed_ids
  AND neighbor.embedding IS NOT NULL
RETURN DISTINCT neighbor.concept_id
```
Returns ~100-500 concepts in ~500ms.

**Phase 2: Extended Neighbors (2-hop) - Parallel Queries**

Split 1-hop results into chunks, execute in parallel with ThreadPoolExecutor:
- 8 workers (default)
- Each worker processes a chunk of seed IDs in one batched query
- Workers grab connections from existing psycopg2 connection pool
- Results merged and deduplicated

### Key Insight

**The Optimization:** Instead of 1 concept = 1 query (150 queries with network overhead), use chunking: 1 chunk = 1 batched query (8 queries total).

**Network Overhead Savings:**
- Old: 150 concepts × 10ms = 1,500ms wasted
- New: 8 chunks × 10ms = 80ms overhead
- **Savings:** 1,420ms from batching alone

## Implementation

### GraphParallelizer Class

```python
# api/lib/graph_parallelizer.py

@dataclass
class ParallelQueryConfig:
    max_workers: int = 8           # ThreadPoolExecutor size
    chunk_size: int = 20           # Concepts per worker chunk
    timeout_seconds: float = 120.0 # Wall-clock timeout
    per_worker_limit: int = 200    # Max results per worker
    discovery_slot_pct: float = 0.2 # Epsilon-greedy (ADR-071a)

class GraphParallelizer:
    """
    Reusable n-hop query parallelizer using connection pooling.

    Breaks multi-hop graph queries into:
    1. Phase 1: Fast single query for 1-hop neighbors
    2. Phase 2: Parallel queries for 2-hop neighbors
    """

    def get_nhop_neighbors(
        self,
        seed_ids: List[str],
        max_hops: int,
        filter_clause: str = "neighbor.embedding IS NOT NULL"
    ) -> Set[str]:
        # Phase 1: Single batched query
        neighbors_1hop = self._get_1hop_neighbors(seed_ids, filter_clause)

        if max_hops == 1:
            return neighbors_1hop

        # Phase 2: Parallel execution with chunking
        neighbors_2hop = self._get_2hop_neighbors_parallel(
            list(neighbors_1hop),
            filter_clause
        )

        return neighbors_1hop | neighbors_2hop
```

### Integration Example: Polarity Discovery

**Before (Sequential):**
```python
def discover_candidate_concepts(positive_pole_id, negative_pole_id, age_client, max_hops=2):
    # Single query with variable-length path - takes 3+ minutes
    results = age_client.facade.execute_raw(f"""
        MATCH (pole)-[*1..{max_hops}]-(candidate)
        WHERE pole.concept_id IN ['{positive_pole_id}', '{negative_pole_id}']
        RETURN DISTINCT candidate.concept_id
    """)
    return [r['concept_id'] for r in results]
```

**After (Parallel):**
```python
def discover_candidate_concepts(positive_pole_id, negative_pole_id, age_client, max_hops=2):
    parallelizer = GraphParallelizer(age_client)

    neighbor_ids = parallelizer.get_nhop_neighbors(
        seed_ids=[positive_pole_id, negative_pole_id],
        max_hops=max_hops,
        filter_clause="candidate.embedding IS NOT NULL"
    )

    return list(neighbor_ids)
```

## Consequences

### Positive

✅ **Expected 8-30x speedup** for 2-hop queries (3 minutes → 6-25 seconds)
✅ **Reusable pattern** for all multi-hop traversals
✅ **No new infrastructure** - uses existing connection pool + stdlib ThreadPoolExecutor
✅ **Graceful degradation** - partial results acceptable, timeout handling
✅ **Production-safe** - connection pool limits prevent resource exhaustion

### Negative

❌ **Connection pool contention** - requires monitoring and tuning
❌ **Result ordering undefined** - parallel execution loses deterministic ordering
❌ **Memory overhead** - holds more results in memory during merge phase
❌ **Complexity** - introduces concurrency concerns (timeouts, deadlocks, race conditions)

### Neutral

⚠️ **Database load increases** - more concurrent queries, but each smaller
⚠️ **Requires configuration** - worker count, timeouts, per-worker limits need tuning

## Safety Mitigations

### 1. Global Semaphore (Prevents Multi-User Deadlock)
```python
# Limit TOTAL concurrent graph workers across ALL requests
_GRAPH_WORKER_SEMAPHORE = threading.Semaphore(max_workers=8)
```
Without this: 2 users × 8 workers each = 16 connections → locks out other API endpoints.

### 2. Per-Worker Result Limits
```cypher
LIMIT {per_worker_limit}  -- Hard limit per worker
```
Prevents hub nodes with 10,000 neighbors from causing memory explosions.

### 3. Wall-Clock Timeout
```python
deadline = time.time() + timeout_seconds
# Strictly bounded execution regardless of worker count
```
Guarantees queries complete within timeout, not just individual workers.

### 4. Graceful Degradation
```python
try:
    neighbors = future.result(timeout=5)
    all_neighbors.update(neighbors)
except TimeoutError:
    logger.warning(f"Worker failed, continuing with partial results")
```
Partial results acceptable for graph exploration - one slow worker doesn't fail entire query.

### 5. Connection Pool Configuration
```python
# Increased from 10 to support parallel workers
self.pool = psycopg2.pool.SimpleConnectionPool(
    1,   # minconn
    20,  # maxconn (8 workers + 2 buffer + main queries)
    ...
)
```

**Rule of Thumb:**
```
max_workers ≤ (connection_pool_size - 2)
max_workers = 8  (default safe with pool_size=20)
```

### 6. Parameter Binding (Security)
```cypher
WHERE seed.concept_id IN $seed_ids  -- Parameterized
```
All queries use parameter binding to prevent Cypher injection, not f-string interpolation.

## Actual Performance Results (ADR-071a)

Implementation testing revealed:

| Workers | Chunk Size | Total Time | Speedup | Success Rate |
|---------|------------|------------|---------|--------------|
| Baseline | N/A | 4:21 (261s) | 1.0x | - |
| **1 worker** | 100 | **1:23 (83s)** | **3.15x** ✅ | 100% |
| 2 workers | 20 | 1:25 (85s) | 3.07x | 100% |
| 4 workers | 10 | 2:02 (122s) | 2.14x | 100% |
| 8 workers | 5 | 3:24 (204s) | 1.28x | 50% |

**Critical Discovery:** The 3x speedup comes from **batched queries with IN clauses**, NOT from parallelization. Parallelization adds overhead beyond 1-2 workers.

**See [ADR-071a: Parallel Implementation Findings](ADR-071a-parallel-implementation-findings.md) for detailed analysis.**

## Configuration Management

### Database-First (Following ADR-041/049 Pattern)

```sql
-- Migration: Add parallel query configuration
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN parallel_query_max_workers INTEGER DEFAULT 8
    CHECK (parallel_query_max_workers >= 1 AND parallel_query_max_workers <= 32);

ADD COLUMN parallel_query_timeout_seconds INTEGER DEFAULT 30
    CHECK (parallel_query_timeout_seconds >= 5 AND parallel_query_timeout_seconds <= 120);
```

### Loading Config
```python
def load_parallel_config() -> ParallelQueryConfig:
    """Load configuration from database (ADR-041/049 pattern)"""
    try:
        config = db.query("SELECT parallel_query_max_workers, ...")
        return ParallelQueryConfig(
            max_workers=config['parallel_query_max_workers'],
            timeout_seconds=config['parallel_query_timeout_seconds']
        )
    except:
        return ParallelQueryConfig()  # Fallback to defaults
```

## Alternatives Considered

### Option A: PostgreSQL Parallel Workers
**Pros:** Native parallelism
**Cons:** Doesn't work with AGE Cypher queries (opaque function calls)
**Decision:** Rejected - PostgreSQL can't see inside `ag_catalog.cypher()`

### Option B: Async/Await (asyncio)
**Pros:** Python-native async
**Cons:** psycopg2 is blocking (would require migration to psycopg3 or aiopg)
**Decision:** Rejected - too much refactoring for uncertain benefit

### Option C: Distributed Queue (Celery)
**Pros:** Battle-tested, scales horizontally
**Cons:** Massive complexity, external dependencies (Redis/RabbitMQ)
**Decision:** Rejected - overkill for current scale

### Option D: GraphQL DataLoader Pattern
**Pros:** Batch + cache
**Cons:** Designed for request-scoped batching, not multi-hop traversal
**Decision:** Rejected - different use case

## Related ADRs

- **[ADR-070: Polarity Axis Analysis](../ai-embeddings/ADR-070-polarity-axis-analysis.md)** - The feature that exposed this performance issue
- **[ADR-071a: Parallel Implementation Findings](ADR-071a-parallel-implementation-findings.md)** - Actual performance results and critical discoveries
- **[ADR-049: Rate Limiting and Concurrency](../ai-embeddings/ADR-049-rate-limiting-and-concurrency.md)** - Semaphore pattern for resource limiting
- **[ADR-048: GraphQueryFacade](../vocabulary-relationships/ADR-048-vocabulary-metadata-as-graph.md)** - Namespace-safe query interface

## References

- **Issue #155:** Polarity Candidate Discovery Optimization
- **PostgreSQL Parallel Query:** https://www.postgresql.org/docs/current/how-parallel-query-works.html
- **Python ThreadPoolExecutor:** https://docs.python.org/3/library/concurrent.futures.html
- **psycopg2 Connection Pooling:** https://www.psycopg.org/docs/pool.html

---

**Last Updated:** 2025-12-04
**Implementation Status:** Completed in PR #157
**Files Changed:**
- `api/api/lib/graph_parallelizer.py` (NEW - 475 lines)
- `api/api/lib/polarity_axis.py` (enhanced with parallel discovery)
- `api/api/lib/age_client.py` (connection pool increased to 20)
