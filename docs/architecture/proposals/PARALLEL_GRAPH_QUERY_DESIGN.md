# Parallel Graph Query Execution - Design Proposal

**Related:** Issue #155, ADR-049 (Concurrency), ADR-050 (Worker Pattern)
**Date:** 2025-12-01
**Status:** Draft

## Executive Summary

Alright, so here's the situation: we've got these graph traversal queries that are taking 3+ minutes to run, which is just ridiculous. The problem is that when you ask "find me all concepts within 2 hops of these poles," PostgreSQL ends up exploring every single path one after another like it's walking through a maze with a blindfold on. It's methodical, but painfully slow.

The fix? We're going to implement a reusable **n-hop parallelizer** that uses connection pooling and Python's `ThreadPoolExecutor` to turn this sequential slog into a parallel sprint. Instead of one query doing all the work, we'll have 8 (or 16, or 32) queries running simultaneously, each handling a small chunk of the graph.

**The Key Insight That Makes This Work:** PostgreSQL can't parallelize AGE Cypher queries on its own. Why? Because AGE queries aren't actually SQL queries—they're function calls to `ag_catalog.cypher()`. From PostgreSQL's perspective, it's just calling a function that returns some data, and it has no idea that function is doing complex graph traversal underneath. So PostgreSQL's parallel query machinery never kicks in.

But here's the beautiful part: while PostgreSQL can't parallelize a *single* graph query, it's perfectly happy running *multiple* graph queries at the same time. That's what connection pooling is for! So we flip the problem on its head—instead of asking the database to parallelize one big query, we break it into many small queries and run them in parallel ourselves. The database just sees "oh, I've got 8 concurrent connections asking for small chunks of data" and handles it beautifully.

## Problem Statement

### Current Performance Issues

Let me show you what's happening right now with polarity candidate discovery (`api/lib/polarity_axis.py:190-280`). We've got this query:

```cypher
MATCH (pole:Concept) WHERE pole.concept_id IN ['pole1', 'pole2']
MATCH (pole)-[*1..2]-(candidate:Concept)
WHERE candidate.embedding IS NOT NULL
RETURN DISTINCT candidate.concept_id
```

See that `[*1..2]` part? That's a variable-length path pattern, and it's where things go sideways. When you run this:

- **max_hops=1**: Takes about 500ms. Not bad! The query finds the immediate neighbors of your two pole concepts and returns them. We're talking maybe 100-200 concepts total.

- **max_hops=2**: Takes **over 3 minutes**. Completely unacceptable. What changed?

Here's what's happening under the hood. When you say "find me concepts within 2 hops," the database has to:

1. Find all 1-hop neighbors of pole1 and pole2 (let's say 100 concepts each = 200 total)
2. For each of those 200 concepts, find *their* neighbors (100 each again)
3. That's 200 × 100 = **20,000 potential paths** to explore

And here's the kicker: it's doing all of this **sequentially**, in a single thread. It's like asking one person to individually check 20,000 mailboxes when you could have 8 people each check 2,500 mailboxes at the same time.

**Why This Happens:**

The Cypher variable-length path pattern `[*1..N]` is powerful, but it evaluates all possible paths before filtering. So even though we only care about distinct concepts at the end, the database is internally tracking every possible way to reach each concept. For highly connected graphs (which ours is—concepts in a knowledge graph tend to be hubs), this creates a combinatorial explosion.

The statement timeout we tried to add? Doesn't work because of a connection pooling quirk. We set the timeout on connection A, but the query might run on connection B from the pool. Classic distributed systems gotcha.

### Affected Query Patterns

This problem affects **three major query types**:

| Query Type | Current Implementation | Performance Issue | File Location |
|------------|----------------------|-------------------|---------------|
| **Polarity Discovery** | `(pole)-[*1..N]-(candidate)` | 3+ min @ N=2 | `api/lib/polarity_axis.py:190` |
| **Neighborhood Queries** | `(center)-[*1..N]-(neighbor)` | Slow on hubs | `api/services/diversity_analyzer.py:174` |
| **Path Enrichment** | Get neighborhoods around each hop | Sequential, slow | `web/src/views/ExplorerView.tsx:199` |

**Shared Pattern:** All need multi-hop traversal from seed concepts.

## Proposed Solution

### Architecture: 2-Phase Parallel Execution

**Phase 1: Direct Neighbors (1-hop) - Single Query**
```python
# Fast query: Get immediate neighbors of all seed concepts
# Returns 100-500 concepts typically
neighbors_1hop = execute_query("""
    MATCH (seed:Concept)-[]-(neighbor:Concept)
    WHERE seed.concept_id IN $seed_ids
    AND neighbor.embedding IS NOT NULL
    RETURN DISTINCT neighbor.concept_id
""")
```

**Phase 2: Extended Neighbors (2-hop) - Parallel Queries**
```python
# Parallel execution: For each 1-hop neighbor, get their neighbors
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = []
    for neighbor_id in neighbors_1hop:
        future = executor.submit(
            get_1hop_neighbors,
            neighbor_id,
            connection_pool  # psycopg2 pool (already configured)
        )
        futures.append(future)

    # Collect and merge results
    neighbors_2hop = merge_and_deduplicate(futures)
```

### How It Actually Works (A Concrete Example)

Let me walk you through a real polarity analysis query to show you exactly what happens at each step.

**Scenario:** You're analyzing the polarity axis between "Centralized" and "Decentralized" with `max_hops=2`.

**Phase 1: The Fast Part (Single Query)**

We start with a simple, fast query to get all 1-hop neighbors of both poles:

```cypher
MATCH (seed:Concept)-[]-(neighbor:Concept)
WHERE seed.concept_id IN ['centralized_abc123', 'decentralized_def456']
  AND neighbor.embedding IS NOT NULL
RETURN DISTINCT neighbor.concept_id
```

This runs in ~500ms and returns, let's say, 150 concepts:
- 80 neighbors of "Centralized" (things like "Authority," "Control," "Hierarchy")
- 70 neighbors of "Decentralized" (things like "Autonomy," "Distribution," "Peer-to-peer")

Total: 150 concepts that are directly connected to our poles.

**Phase 2: The Parallel Part (8 Workers with Chunking)**

Now we need the neighbors of those 150 concepts. Instead of one query with `[*1..2]` (which would explore 150 × 100 = 15,000 paths sequentially), we use **chunking** to minimize network overhead.

**The Optimization:** Instead of 1 worker = 1 concept = 1 query (150 total queries), we do 1 worker = 1 chunk of concepts = 1 batched query (8 total queries).

Split 150 concepts into 8 chunks:
- Chunk 1: Concepts 1-19 (19 IDs)
- Chunk 2: Concepts 20-37 (18 IDs)
- Chunk 3: Concepts 38-56 (19 IDs)
- ... and so on ...
- Chunk 8: Concepts 134-150 (17 IDs)

Each worker:
1. Grabs a connection from the pool
2. Runs **ONE** batched query for its entire chunk:
```cypher
MATCH (seed:Concept)-[]-(neighbor:Concept)
WHERE seed.concept_id IN $seed_ids  -- All 19 IDs passed as parameter
  AND neighbor.embedding IS NOT NULL
RETURN DISTINCT neighbor.concept_id
LIMIT 2000  -- Higher limit since we're batching
```
3. Collects all neighbor IDs (deduped by DISTINCT)
4. Returns the connection to the pool
5. Reports its results back

**Why Chunking Matters:**

- **Network overhead:** Each query has ~10ms latency (connection setup, query parse, result marshal)
- **Old approach:** 150 concepts × 10ms = 1,500ms wasted in network overhead
- **New approach:** 8 chunks × 10ms = 80ms network overhead
- **Savings:** 1,420ms (1.4 seconds) just from batching!

Plus, the database can optimize a single batched query better than 19 separate queries (shared query plan, shared index lookups).

**The Timeline (With Chunking):**

```
T=0ms:     Start Phase 1 query
T=500ms:   Phase 1 complete (150 1-hop neighbors found)
T=500ms:   Split into 8 chunks of ~19 IDs each
T=502ms:   Launch 8 workers in parallel
T=504ms:   All 8 workers grab connections from pool
T=504ms:   All 8 workers start their batched queries

T=1500ms:  Worker 1 finishes its batched query (19 seeds) → returns connection
T=1520ms:  Worker 2 finishes its batched query (18 seeds) → returns connection
T=1540ms:  Worker 3 finishes its batched query (19 seeds) → returns connection
... workers finish between 1.5-1.8 seconds ...
T=1800ms:  Worker 8 finishes its batched query (17 seeds) → returns connection

T=1810ms:  Merge and deduplicate all results
T=1850ms:  Return final set of ~2,500 unique concepts
```

**Total Time:** ~1.85 seconds (less than 2 seconds!)

**Compare to Sequential:**

If we'd done this sequentially:
- Phase 1: 500ms (same)
- Phase 2: 150 concepts × 2s per query = 300s = **5 minutes**

**Total Time:** 5+ minutes

**Compare to Parallel Without Chunking:**

If we'd done parallel but with 150 individual queries:
- Phase 1: 500ms
- Phase 2: (150 ÷ 8) × 2s + 1.5s network overhead = ~5 seconds

**Total Time:** ~5.5 seconds

**With Chunking:** ~1.85 seconds

We just went from 5 minutes (sequential) to 1.85 seconds (parallel + chunked). That's a **160x speedup**.

Even compared to "parallel without chunking" (5.5s), chunking gives us a **3x improvement**.

### Why This Works

Let me walk you through why this approach is actually brilliant (and why it won't blow up in our faces).

**We're Not Reinventing Anything:**

First off, we're not adding new infrastructure. We already have connection pooling set up (`AGEClient.pool`)—that's been there since day one. And `ThreadPoolExecutor`? That's Python standard library. No new dependencies to manage, no new services to deploy, no new things to break at 2am.

Here's how it works in practice: Each thread in our pool grabs a connection from the existing pool, runs its query, and puts the connection back. It's like a checkout counter at a library—there are 20 books (connections), and people (threads) can check them out, use them, and return them. As long as you don't have more people trying to check out books than you have books, everything flows smoothly.

**The Math That Makes You Smile:**

Let's say we have 100 concepts from our 1-hop query, and each needs a 1-hop query of its own to find their neighbors. Currently:

- **Sequential (what we have now):** 100 queries × 2 seconds each = 200 seconds (over 3 minutes)

That's one query finishing, then the next starting, then the next... it's agonizing.

With 8 workers in parallel:
- **Parallel (8 workers):** 100 queries ÷ 8 workers × 2 seconds = 25 seconds

We just went from 3+ minutes to 25 seconds. That's an **8x speedup**. And if we're feeling ambitious and bump it to 32 workers (which we can, if we increase the connection pool size):

- **Parallel (32 workers):** 100 queries ÷ 32 workers × 2 seconds = 6.25 seconds

From 3 minutes to 6 seconds. That's a **30x speedup**. Your polarity analysis goes from "go grab a coffee" to "blink and you miss it."

**Why It's Actually Safe:**

You might be thinking "wait, won't 32 concurrent queries just overwhelm the database?" Great question! Here's why it won't:

1. **PostgreSQL is Built for This:** PostgreSQL uses MVCC (Multi-Version Concurrency Control), which means it can handle tons of concurrent reads without them blocking each other. Each query sees its own consistent snapshot of the data. This is literally what PostgreSQL was designed to do.

2. **Connection Pooling Prevents Chaos:** We're not creating 32 new connections to the database. We have a pool of (let's say) 20 connections. If we try to use more than 20 at once, the extras just wait in line. The pool acts as a natural rate limiter.

3. **It's Like ADR-049, But for Queries:** Remember how we solved the "100 concurrent OpenAI API calls = rate limit hell" problem? We used semaphores to limit concurrent requests. This is the exact same pattern, just applied to database queries instead of API calls. We're not cowboys here—we're using proven patterns.

## Design: Reusable Parallelizer Class

```python
# api/lib/graph_parallelizer.py

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Callable, Any, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParallelQueryConfig:
    """Configuration for parallel query execution"""
    max_workers: int = 8  # Like ADR-049 semaphores
    max_results_per_worker: int = 100  # Prevent runaway queries
    timeout_seconds: int = 30  # Per-worker timeout
    deduplicate: bool = True  # Remove duplicate results

class GraphParallelizer:
    """
    Reusable n-hop query parallelizer using connection pooling.

    Breaks multi-hop graph queries into:
    1. Phase 1: Fast single query for 1-hop neighbors
    2. Phase 2: Parallel queries for 2-hop neighbors

    Use Cases:
    - Polarity candidate discovery
    - Neighborhood queries
    - Path enrichment
    """

    def __init__(self, age_client, config: Optional[ParallelQueryConfig] = None):
        self.client = age_client
        self.config = config or ParallelQueryConfig()

    def get_nhop_neighbors(
        self,
        seed_ids: List[str],
        max_hops: int,
        filter_clause: str = "neighbor.embedding IS NOT NULL",
        relationship_filter: Optional[str] = None
    ) -> Set[str]:
        """
        Get n-hop neighbors of seed concepts using parallel execution.

        Args:
            seed_ids: Starting concept IDs
            max_hops: Maximum hops (1 or 2 recommended)
            filter_clause: Cypher WHERE clause for neighbors
            relationship_filter: Optional relationship type filter

        Returns:
            Set of neighbor concept IDs (deduped)
        """
        if max_hops < 1:
            return set()

        # Validate seed IDs to prevent injection
        for seed_id in seed_ids:
            from api.lib.polarity_axis import validate_concept_id
            validate_concept_id(seed_id)

        # Phase 1: Get 1-hop neighbors (fast single query)
        neighbors_1hop = self._get_1hop_neighbors(
            seed_ids,
            filter_clause,
            relationship_filter
        )

        logger.info(f"Phase 1: Found {len(neighbors_1hop)} 1-hop neighbors")

        if max_hops == 1:
            return neighbors_1hop

        # Phase 2: Get 2-hop neighbors in parallel
        neighbors_2hop = self._get_2hop_neighbors_parallel(
            list(neighbors_1hop),
            filter_clause,
            relationship_filter
        )

        logger.info(f"Phase 2: Found {len(neighbors_2hop)} total 2-hop neighbors")

        # Merge 1-hop and 2-hop (dedupe)
        all_neighbors = neighbors_1hop | neighbors_2hop

        # Remove seeds from results
        all_neighbors -= set(seed_ids)

        return all_neighbors

    def _get_1hop_neighbors(
        self,
        seed_ids: List[str],
        filter_clause: str,
        relationship_filter: Optional[str]
    ) -> Set[str]:
        """Get 1-hop neighbors in single query"""

        # Build relationship pattern
        rel_pattern = f"[:{relationship_filter}]" if relationship_filter else "[]"

        # Safe: IDs validated above, using parameterized query
        query = f"""
            MATCH (seed:Concept)-{rel_pattern}-(neighbor:Concept)
            WHERE seed.concept_id IN $seed_ids
              AND {filter_clause}
            RETURN DISTINCT neighbor.concept_id as concept_id
            LIMIT {self.config.max_results_per_worker * len(seed_ids)}
        """

        results = self.client.facade.execute_raw(
            query=query,
            params={"seed_ids": seed_ids},
            namespace="concept"
        )

        return {r['concept_id'] for r in results}

    def _get_2hop_neighbors_parallel(
        self,
        hop1_neighbors: List[str],
        filter_clause: str,
        relationship_filter: Optional[str]
    ) -> Set[str]:
        """Get 2-hop neighbors using parallel worker pool"""

        all_neighbors = set()

        # Use ThreadPoolExecutor for parallel queries
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all 1-hop neighbors for parallel processing
            futures = {
                executor.submit(
                    self._get_1hop_neighbors_worker,
                    neighbor_id,
                    filter_clause,
                    relationship_filter
                ): neighbor_id
                for neighbor_id in hop1_neighbors
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(futures, timeout=self.config.timeout_seconds):
                neighbor_id = futures[future]
                try:
                    neighbors = future.result(timeout=5.0)
                    all_neighbors.update(neighbors)
                    completed += 1

                    if completed % 10 == 0:
                        logger.debug(f"Completed {completed}/{len(hop1_neighbors)} workers")

                except Exception as e:
                    logger.warning(f"Worker failed for {neighbor_id}: {e}")
                    # Continue processing other workers

        logger.info(f"Parallel phase completed: {completed}/{len(hop1_neighbors)} workers succeeded")

        return all_neighbors

    def _get_1hop_neighbors_worker(
        self,
        seed_id: str,
        filter_clause: str,
        relationship_filter: Optional[str]
    ) -> Set[str]:
        """
        Worker function: Get 1-hop neighbors for single seed.

        Runs in thread pool - gets connection from pool, returns after query.
        """
        # Get connection from pool (thread-safe)
        conn = self.client.pool.getconn()

        try:
            # Build query
            rel_pattern = f"[:{relationship_filter}]" if relationship_filter else "[]"

            query = f"""
                SELECT * FROM ag_catalog.cypher('concept', $$
                    MATCH (seed:Concept {{concept_id: '{seed_id}'}})-{rel_pattern}-(neighbor:Concept)
                    WHERE {filter_clause}
                    RETURN DISTINCT neighbor.concept_id as concept_id
                    LIMIT {self.config.max_results_per_worker}
                $$) as (concept_id agtype);
            """

            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()

            # Extract concept IDs from agtype results
            neighbor_ids = set()
            for row in results:
                # Parse agtype JSON
                import json
                concept_id = json.loads(row[0])
                neighbor_ids.add(concept_id)

            return neighbor_ids

        finally:
            # Always return connection to pool
            self.client.pool.putconn(conn)
```

## Integration Examples

### Example 1: Polarity Candidate Discovery

**Before (Sequential):**
```python
def discover_candidate_concepts(positive_pole_id, negative_pole_id, age_client, max_hops=2):
    # Single query with variable-length path
    # Takes 3+ minutes for max_hops=2
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
    # Use parallelizer
    parallelizer = GraphParallelizer(age_client)

    neighbor_ids = parallelizer.get_nhop_neighbors(
        seed_ids=[positive_pole_id, negative_pole_id],
        max_hops=max_hops,
        filter_clause="candidate.embedding IS NOT NULL"
    )

    return list(neighbor_ids)
```

**Performance Improvement:** 3+ minutes → ~25 seconds (8x faster)

### Example 2: Neighborhood Queries (Diversity Analysis)

```python
# In api/services/diversity_analyzer.py

def get_related_concepts(self, concept_id, max_hops=2):
    parallelizer = GraphParallelizer(self.client)

    related_ids = parallelizer.get_nhop_neighbors(
        seed_ids=[concept_id],
        max_hops=max_hops,
        filter_clause="neighbor.embedding IS NOT NULL"
    )

    return related_ids
```

### Example 3: Path Enrichment (Web UI)

**Before (Sequential in React):**
```typescript
// web/src/views/ExplorerView.tsx:199
const neighborhoods = await Promise.all(
    nodeIds.map(nodeId =>
        apiClient.getSubgraph({ center_concept_id: nodeId, depth: 2 })
    )
);
```

**After (Parallel in Backend):**
```python
# New endpoint: POST /query/enriched-path
def get_enriched_path(from_id, to_id, depth=2):
    # Get path
    path = find_connection(from_id, to_id)
    node_ids = [n.id for n in path.nodes]

    # Parallel neighborhood queries
    parallelizer = GraphParallelizer(age_client)
    all_neighbors = parallelizer.get_nhop_neighbors(
        seed_ids=node_ids,
        max_hops=depth
    )

    # Fetch full nodes and return
    return build_graph(path.nodes + all_neighbors, path.relationships)
```

## Safety Considerations

### The "Hilariously Bad" Scenarios

Okay, so parallelization is great, but let me tell you about the ways this can go spectacularly, *exponentially* wrong if we're not careful. I'm talking "accidentally DoS your own database at 2am" wrong.

**Scenario 1: The Connection Pool Death Spiral**

Imagine this: You decide "more workers = faster!" and crank `max_workers` up to 100. Your code happily creates 100 threads, and each thread tries to grab a connection from the pool. But your pool only has 20 connections.

What happens? 20 threads get connections and start working. The other 80 threads sit there waiting. Forever. They never timeout because they're waiting on the pool's internal lock, not on a database query. Meanwhile, the 20 working threads finish and try to return their connections... but they can't, because the pool is deadlocked trying to satisfy the 80 waiting threads.

**Result:** Your entire application freezes. No queries run. You've created a perfect deadlock. Congratulations, you've just invented a way to DoS yourself with *parallelism*.

**Scenario 2: The Exponential Query Explosion**

Let's say you're feeling clever and decide to parallelize 3-hop queries. "If 2-hop with 8 workers is good, 3-hop with nested parallelism must be better!"

Here's the math:
- Phase 1: Get 1-hop neighbors → 200 concepts
- Phase 2: For each of 200 concepts, spawn 8 workers to get their neighbors → 1,600 concurrent queries
- Phase 3: For each of *those* results (let's say 10,000 concepts), spawn 8 workers → **80,000 concurrent queries**

Your database server: "Why do I hear boss music?"

Your connection pool (with 20 connections): *quiet sobbing*

Your RAM: "I'm sorry, Dave. I'm afraid I can't do that."

**Result:** You've just created an exponential explosion of concurrent work that will either exhaust connections, max out CPU, or fill RAM with millions of query results. The database doesn't crash—it just gets slower and slower until every query is waiting for every other query, and your monitoring starts sending you alerts that look like a Christmas tree.

**Scenario 3: The Memory Cascade Failure**

Each worker finds 100 neighbors. You have 200 workers. That's 20,000 concept IDs returned. "Great!" you think. But then your code loads the *full* concept objects (with embeddings, descriptions, relationships) for all 20,000.

Each concept with embedding: ~4KB (1536 floats × 4 bytes + metadata)
20,000 concepts × 4KB = **80MB**

Not too bad, right? But you're running this in a web request. And someone else is running a polarity analysis. And someone else is running a neighborhood query. And suddenly you've got 5 parallel operations each loading 80MB of concept data.

Python's garbage collector: "I'm working as fast as I can!"

Your API server: *OOM killed by Linux*

**Result:** Your API container gets OOM-killed, restarts, and immediately gets hit with the same queries again because they're in the retry queue. Welcome to the restart loop. Population: you, at 3am, wondering why you ever thought caching was optional.

**Scenario 4: The Thundering Herd Returns**

Remember ADR-049, where we solved the "100 concurrent API calls hit rate limits" problem? Imagine doing the exact same thing, but to your own database.

You spawn 100 workers, they all hit the database at once. PostgreSQL goes "okay, I can handle this... barely." But then:
- Each query takes 2 seconds
- During those 2 seconds, more polarity analyses start
- Each new analysis spawns 100 more workers
- You now have 400 concurrent database queries

PostgreSQL's connection limit: 100 connections
Your query count: 400 connections needed

**Result:** 300 queries waiting for connections, blocking their threads, blocking your threadpool, cascading back to block your API endpoints. Your entire API becomes unresponsive. Your users think the site is down. Your monitoring thinks the database is down. The database is fine—it's just laughing at you.

**How We Prevent All This (The Mitigations):**

These aren't just theoretical horror stories. This is what *will* happen if we ship this without guardrails. So here's how we keep the wheels on:

#### 1. Global Semaphore (Preventing Multi-User Deadlock)

**The Critical Bug in the Original Design:**

The original plan said "8 workers per request is safe with a 20-connection pool." But that only works for a **single user**. Here's what actually happens in production:

- User A starts polarity analysis: 1 main + 8 workers = **9 connections**
- User B starts polarity analysis: 1 main + 8 workers = **9 connections**
- Total: **18/20 connections used**
- User C (or a health check endpoint): **BLOCKED**

Two simultaneous analysts lock out the entire application. This is a showstopper bug.

**The Fix: Application-Level Global Semaphore**

We need to limit the total number of graph workers **across the entire application**, not per request:

```python
# Global singleton semaphore (initialized once at app startup)
_GRAPH_WORKER_SEMAPHORE = None

def get_global_graph_semaphore(max_workers: int = 8) -> threading.Semaphore:
    """
    Get or create the global graph worker semaphore.

    This limits TOTAL concurrent graph workers across ALL requests.
    """
    global _GRAPH_WORKER_SEMAPHORE
    if _GRAPH_WORKER_SEMAPHORE is None:
        _GRAPH_WORKER_SEMAPHORE = threading.Semaphore(max_workers)
    return _GRAPH_WORKER_SEMAPHORE

class GraphParallelizer:
    def __init__(self, age_client, config: Optional[ParallelQueryConfig] = None):
        self.client = age_client
        self.config = config or ParallelQueryConfig()
        self.global_semaphore = get_global_graph_semaphore(self.config.max_workers)

    def _get_1hop_neighbors_worker(self, seed_id, ...):
        # Acquire from GLOBAL semaphore, not per-request
        with self.global_semaphore:
            conn = self.client.pool.getconn()
            try:
                # ... run query ...
            finally:
                self.client.pool.putconn(conn)
```

**How This Works:**

With `max_workers=8` globally:

- User A starts query: Acquires 8 slots from global semaphore
- User B starts query: Tries to acquire 8 slots, but only 0 available → **waits**
- User A finishes: Releases 8 slots
- User B proceeds: Acquires 8 slots

**Graceful Degradation Option:**

Instead of blocking User B, we could degrade to sequential execution:

```python
def get_nhop_neighbors(self, seed_ids, max_hops, ...):
    # Try to acquire workers from global pool
    available_workers = 0
    acquired_slots = []

    for _ in range(self.config.max_workers):
        if self.global_semaphore.acquire(blocking=False):
            acquired_slots.append(True)
            available_workers += 1
        else:
            break

    if available_workers == 0:
        # No workers available - degrade to sequential
        logger.warning("Global worker pool exhausted, running sequentially")
        return self._sequential_fallback(seed_ids, max_hops)

    # Use however many workers we got
    logger.info(f"Acquired {available_workers}/{self.config.max_workers} workers")
    # ... proceed with available_workers ...
```

**Alternative: Dedicated Connection Pool**

Another approach is separate pools:

```python
# Main API pool: 10 connections
main_pool = psycopg2.pool.SimpleConnectionPool(2, 10, ...)

# Graph worker pool: 10 connections
graph_worker_pool = psycopg2.pool.SimpleConnectionPool(2, 10, ...)
```

**Benefit:** API endpoints never hang even if graph workers are maxed out.

**Trade-off:** More complex connection management, but better isolation.

**Recommended Configuration:**
```
Total PostgreSQL connections: 100
Main API pool: 10 connections
Graph worker pool: 10 connections (8 workers + 2 buffer)
Reserved for monitoring/admin: 5 connections

Result: 2 concurrent graph analyses can run without blocking API
```

#### 2. Per-Worker Result Limits (Preventing Memory Explosions)

**The Fix:**
```python
max_results_per_worker: int = 100  # Prevent runaway queries
```

Each worker is allowed to return a maximum of 100 concepts. Why? Because if we have 200 workers and each one can return unlimited results, one "hub" concept with 10,000 neighbors could single-handedly blow up our memory.

**The Implementation:**

Every query we generate has a hard LIMIT clause:

```cypher
MATCH (seed:Concept {concept_id: 'abc123'})-[]-(neighbor:Concept)
WHERE neighbor.embedding IS NOT NULL
RETURN DISTINCT neighbor.concept_id
LIMIT 100  -- Hard limit per worker
```

So even if a concept has 10,000 neighbors (looking at you, highly connected hub nodes), each worker only returns 100. This means:

- 200 workers × 100 results = 20,000 concepts maximum
- 20,000 concepts × 4KB each = 80MB maximum memory
- Totally manageable, even with multiple concurrent analyses

**The Trade-off:**

"But what if I'm missing important concepts?" Fair question. Here's the thing: if a concept has 10,000 neighbors, the first 100 are going to be pretty representative. You're not losing critical information—you're avoiding exponential explosion for marginal gains. And remember, we're usually looking for concepts with embeddings for similarity analysis. Those 100 are likely the most relevant anyway (if we're smart about ordering, which we can be).

#### 3. Timeouts (Preventing Infinite Waits)

**The Fix:**
```python
timeout_seconds: int = 30  # Kill slow workers

# In executor
futures = as_completed(futures, timeout=30)
future.result(timeout=5)  # Per-future timeout
```

We have two levels of timeouts:

1. **Batch timeout (30s):** The entire parallel batch must complete within 30 seconds. If it doesn't, we stop waiting for stragglers and return what we have.

2. **Per-worker timeout (5s):** Each individual worker gets 5 seconds to complete its query. If a query is still running after 5 seconds, something's wrong (probably hit a super-connected hub node), and we kill it.

**Why This Matters:**

Without timeouts, one pathological query can block your entire parallelizer. Imagine:
- Worker 1-7: Complete in 2 seconds each ✓
- Worker 8: Hits a concept with 100,000 neighbors, takes 5 minutes ✗

With timeouts, worker 8 gets killed after 5 seconds, and we return the results from workers 1-7. You get 87.5% of your data in 5 seconds instead of 100% of your data in 5 minutes. That's a trade worth making.

#### 4. Graceful Degradation (Partial Results Are OK)

**The Philosophy:**

```python
try:
    neighbors = future.result(timeout=5)
    all_neighbors.update(neighbors)
except TimeoutError:
    logger.warning(f"Worker failed for {neighbor_id}, skipping")
    # Continue with other workers - partial results OK
```

Here's a key insight: for graph discovery queries, **partial results are perfectly acceptable**. If we're discovering 20 candidate concepts for a polarity analysis, and one worker fails, we still have 19 concepts. That's enough to do meaningful analysis.

This is different from, say, a database transaction where you need all-or-nothing. Graph exploration is inherently fuzzy—you're sampling the graph, not enumerating it exhaustively. So we embrace partial failures:

- Worker succeeds → add its results to the set
- Worker times out → log a warning, keep going
- Worker crashes → log an error, keep going
- All workers fail → okay, *now* we return an error

This makes the system resilient. One bad concept with pathological connectivity can't bring down the entire analysis.

#### 5. Security: Parameter Binding (Preventing Cypher Injection)

**The Vulnerability:**

The original implementation used f-strings to build Cypher queries:

```python
query = f"""
    MATCH (seed:Concept {{concept_id: '{seed_id}'}})...
"""
```

Even with `validate_concept_id()`, this is technically a **Cypher injection vulnerability**. If validation has a bug, or if IDs come from a different source, an attacker could inject:

```python
seed_id = "abc'})-[:ADMIN]->(u:User) WHERE u.username='admin' SET u.password='"
```

**The Limitation:**

AGE's `ag_catalog.cypher()` function takes a Cypher string literal. Unlike regular SQL with `%s` placeholders, we can't easily pass parameters *into* the Cypher string from psycopg2.

**The Solution: Strict Validation + Safe Escaping**

1. **Allowlist Validation:** Only allow alphanumeric, underscores, hyphens, and colons:
```python
def validate_concept_id(concept_id: str) -> None:
    if not re.match(r'^[a-zA-Z0-9_\-:]+$', concept_id):
        raise ValueError("Invalid concept ID format")
```

2. **Parameter Binding Where Possible:** Use the Cypher `$param` syntax inside the string:
```python
query = f"""
    SELECT * FROM ag_catalog.cypher('concept', $$
        MATCH (seed:Concept)-[]-(neighbor:Concept)
        WHERE seed.concept_id IN $seed_ids
        RETURN DISTINCT neighbor.concept_id
    $$) as (concept_id agtype);
"""
# Pass seed_ids as psycopg2 parameter (safe)
cursor.execute(query, {'seed_ids': json.dumps(seed_ids)})
```

3. **Escape Single Quotes:** If we must use f-strings, escape any quotes:
```python
seed_id_safe = seed_id.replace("'", "''")  # SQL escaping
query = f"MATCH (seed {{concept_id: '{seed_id_safe}'}})"
```

**Recommended Approach:**

Use chunking (as described above), which allows us to pass lists via parameterized queries instead of individual f-string interpolation.

#### 6. Wall-Clock Timeout (Strictly Bounded Execution)

**The Bug:**

The original code used:
```python
for future in as_completed(futures, timeout=30):
    result = future.result(timeout=5)
```

**Problem:** `as_completed(timeout=30)` only times out if it's waiting for the *next* result, not for the *total* execution time. If you have 8 workers that each take 29 seconds, `as_completed` never times out because results keep arriving.

**The Fix: Track Deadline**

```python
def _get_2hop_neighbors_parallel(self, hop1_neighbors, ...):
    deadline = time.time() + self.config.timeout_seconds
    all_neighbors = set()

    with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
        futures = {executor.submit(...): nid for nid in hop1_neighbors}

        while futures and time.time() < deadline:
            # Calculate remaining time
            remaining = deadline - time.time()
            if remaining <= 0:
                logger.warning("Wall-clock timeout reached, returning partial results")
                break

            # Wait for next result with adjusted timeout
            try:
                done, pending = concurrent.futures.wait(
                    futures.keys(),
                    timeout=min(remaining, 5.0),  # At most 5s per iteration
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    nid = futures.pop(future)
                    try:
                        neighbors = future.result(timeout=0.1)  # Already done
                        all_neighbors.update(neighbors)
                    except Exception as e:
                        logger.warning(f"Worker failed for {nid}: {e}")

            except concurrent.futures.TimeoutError:
                # No results ready yet, loop will check deadline
                pass

        # Cancel any remaining workers if we hit deadline
        if futures:
            logger.warning(f"Cancelling {len(futures)} slow workers due to timeout")
            for future in futures:
                future.cancel()

    return all_neighbors
```

**Benefit:** Guarantees total execution time ≤ `timeout_seconds`, regardless of worker count or individual query times.

#### 7. Database-Side Safety
```sql
-- PostgreSQL connection limits (already configured)
max_connections = 100
superuser_reserved_connections = 3

-- AGE client pool (already configured)
minconn = 2
maxconn = 20  -- Conservative default
```

**Rule of Thumb:**
```
max_workers ≤ (connection_pool_size - 2)
max_workers = 8  (default safe)
max_workers = 16 (if pool_size ≥ 18)
max_workers = 32 (if pool_size ≥ 34, requires tuning)
```

## Configuration Management

### Database-First (Like ADR-049)

```sql
-- Migration 020: Add parallel query configuration
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN parallel_query_max_workers INTEGER DEFAULT 8
    CHECK (parallel_query_max_workers >= 1 AND parallel_query_max_workers <= 32);

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN parallel_query_timeout_seconds INTEGER DEFAULT 30
    CHECK (parallel_query_timeout_seconds >= 5 AND parallel_query_timeout_seconds <= 120);
```

### Loading Config
```python
def load_parallel_config() -> ParallelQueryConfig:
    """Load configuration from database (ADR-041/049 pattern)"""
    try:
        # Try database first
        config = db.query("SELECT parallel_query_max_workers, parallel_query_timeout_seconds ...")
        return ParallelQueryConfig(
            max_workers=config['parallel_query_max_workers'],
            timeout_seconds=config['parallel_query_timeout_seconds']
        )
    except:
        # Fallback to environment variables
        return ParallelQueryConfig(
            max_workers=int(os.getenv('PARALLEL_QUERY_MAX_WORKERS', 8)),
            timeout_seconds=int(os.getenv('PARALLEL_QUERY_TIMEOUT_SECONDS', 30))
        )
```

## Performance Estimates

### Polarity Discovery (max_hops=2, 20 candidates)

| Configuration | Estimated Time | Speedup |
|--------------|----------------|---------|
| **Current (sequential)** | 180s (3 min) | 1x baseline |
| **Parallel (4 workers)** | 45s | 4x faster |
| **Parallel (8 workers)** | 22s | 8x faster |
| **Parallel (16 workers)** | 11s | 16x faster |
| **Parallel (32 workers)** | 6s | 30x faster |

**Assumptions:**
- 100 1-hop neighbors per pole
- 2s per 1-hop query
- Database can handle concurrent load
- Connection pool has capacity

### Neighborhood Queries (diversity analysis)

| Scenario | Current | Parallel (8 workers) | Improvement |
|----------|---------|---------------------|-------------|
| 1-hop | ~500ms | ~500ms | No change (already fast) |
| 2-hop | ~8s | ~2s | **4x faster** |
| 3-hop | ~60s | ~15s | **4x faster** |

## Testing Strategy

### Unit Tests
```python
def test_parallel_nhop_neighbors():
    """Test parallel 2-hop neighbor discovery"""
    parallelizer = GraphParallelizer(client, ParallelQueryConfig(max_workers=4))

    neighbors = parallelizer.get_nhop_neighbors(
        seed_ids=['concept1', 'concept2'],
        max_hops=2
    )

    assert len(neighbors) > 0
    assert 'concept1' not in neighbors  # Seeds excluded
```

### Integration Tests
```python
def test_polarity_discovery_parallel():
    """Compare sequential vs parallel performance"""
    # Sequential
    start = time.time()
    sequential_results = discover_candidate_concepts_sequential(...)
    sequential_time = time.time() - start

    # Parallel
    start = time.time()
    parallel_results = discover_candidate_concepts_parallel(...)
    parallel_time = time.time() - start

    # Same results
    assert set(sequential_results) == set(parallel_results)

    # Faster (at least 2x for max_hops=2)
    assert parallel_time < sequential_time / 2
```

### Load Tests
```python
def test_connection_pool_saturation():
    """Verify workers don't exhaust connection pool"""
    # Simulate 100 concurrent queries
    parallelizer = GraphParallelizer(client, ParallelQueryConfig(max_workers=32))

    # Should not deadlock or fail
    results = parallelizer.get_nhop_neighbors(
        seed_ids=list(range(100)),  # Many seeds
        max_hops=2
    )

    # Should complete without errors
    assert len(results) > 0
```

## Implementation Plan

### Phase 1: Core Parallelizer (Week 1)
- [ ] Implement `GraphParallelizer` class
- [ ] Add configuration schema (migration 020)
- [ ] Write unit tests
- [ ] Document API

### Phase 2: Polarity Integration (Week 2)
- [ ] Update `discover_candidate_concepts()` to use parallelizer
- [ ] Add performance logging
- [ ] Test with max_hops=1,2,3
- [ ] Update issue #155 with results

### Phase 3: Neighborhood Queries (Week 3)
- [ ] Update `DiversityAnalyzer` to use parallelizer
- [ ] Update related concepts endpoint
- [ ] Performance benchmarks

### Phase 4: Path Enrichment (Week 4)
- [ ] Create enriched path endpoint
- [ ] Update web UI to use new endpoint
- [ ] End-to-end testing

### Phase 5: Monitoring & Tuning (Week 5)
- [ ] Add performance metrics
- [ ] Connection pool monitoring
- [ ] Auto-tuning recommendations
- [ ] Production deployment

## Alternatives Considered

### Option A: PostgreSQL Parallel Workers
**Pros:** Native parallelism
**Cons:** Doesn't work with AGE Cypher queries (they're function calls)
**Decision:** Rejected

### Option B: Async/Await (asyncio)
**Pros:** Python-native async
**Cons:** psycopg2 is blocking (would need psycopg3 or aiopg)
**Decision:** Rejected (too much refactoring)

### Option C: Distributed Queue (Celery)
**Pros:** Battle-tested, scales horizontally
**Cons:** Massive complexity, external dependencies (Redis/RabbitMQ)
**Decision:** Rejected (overkill for current scale)

### Option D: GraphQL DataLoader Pattern
**Pros:** Batch + cache
**Cons:** Designed for request-scoped batching, not multi-hop traversal
**Decision:** Rejected (different use case)

## Future Enhancements

### Phase 2: 3-Hop Parallelization
Extend to 3 hops with nested parallelization:
```
1-hop: Single query
2-hop: Parallel (8 workers)
3-hop: Nested parallel (8 × 8 = 64 sub-workers)
```

### Phase 3: Query Result Caching
Cache 1-hop neighbor results for frequently queried concepts:
```python
@lru_cache(maxsize=1000)
def get_cached_1hop_neighbors(concept_id):
    return _get_1hop_neighbors_uncached(concept_id)
```

### Phase 4: Adaptive Worker Count
Automatically adjust worker count based on query load:
```python
def calculate_optimal_workers(query_count, avg_query_time):
    # More workers for large batches, fewer for small
    return min(32, max(4, query_count // 10))
```

## Open Questions

1. **Connection pool sizing:** Should we increase default pool size from 20 to 40?
2. **Worker count tuning:** Start with 8 or go aggressive with 16?
3. **Timeout handling:** Should timeout kill entire batch or just slow workers?
4. **Result ordering:** Does order matter for candidate discovery?
5. **Caching layer:** Worth adding Redis cache for 1-hop neighbors?

## References

- **Issue #155:** Polarity Candidate Discovery Optimization
- **ADR-049:** Rate Limiting and Per-Provider Concurrency
- **ADR-050:** Scheduled Jobs System (Worker Pattern)
- **PostgreSQL Parallel Query:** https://www.postgresql.org/docs/current/how-parallel-query-works.html
- **Python ThreadPoolExecutor:** https://docs.python.org/3/library/concurrent.futures.html
- **psycopg2 Connection Pooling:** https://www.psycopg.org/docs/pool.html

---

**Last Updated:** 2025-12-01
**Next Steps:** Review with team, validate approach, begin Phase 1 implementation
