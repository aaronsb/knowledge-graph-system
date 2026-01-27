---
status: Proposed
date: 2025-12-09
deciders: System Architecture
related:
  - ADR-016
---

# ADR-076: Pathfinding Optimization for Apache AGE

## Context

Our pathfinding queries experience severe performance degradation at scale. A user querying path connections between concepts on a graph with ~100,000 nodes observes timeout behavior for paths longer than 4-5 hops. Investigation revealed the root cause is **exhaustive path enumeration** rather than optimized graph algorithms.

### Current Implementation

The `build_shortest_path_query` function in `api/api/services/query_service.py` generates:

```cypher
MATCH path = (from:Concept {concept_id: $from_id})-[*1..{max_hops}]-(to:Concept {concept_id: $to_id})
WITH path, length(path) as hops
RETURN nodes(path) as path_nodes, relationships(path) as path_rels, hops
ORDER BY hops ASC
LIMIT 10
```

### Why This Times Out

1. **Exhaustive Search:** The pattern `-[*1..N]-` tells Apache AGE to find **every possible path** of length 1 to N between two nodes.

2. **Order of Operations:** The query:
   - Enumerates ALL valid paths (potentially millions)
   - Holds them in memory
   - Sorts by length
   - Returns top 10

3. **Exponential Complexity:** With average branching factor `b`:
   - 3-hop search: O(b³) paths
   - 5-hop search: O(b⁵) paths
   - 10-hop search: O(b¹⁰) paths

   If branching factor is 20 (modest for our graph):
   - 5 hops = 3,200,000 paths to enumerate
   - 10 hops = 10,240,000,000,000 paths

### Documentation Contradiction

Our documentation at `docs/manual/06-reference/09-CYPHER_PATTERNS.md` shows `shortestPath()` usage:

```cypher
MATCH path = shortestPath((start)-[*]-(end))
RETURN path
```

However, the code comments in `query_service.py` correctly note:

> "Note: AGE doesn't support Neo4j's shortestPath(), all() predicate..."

### Apache AGE Limitations (Verified)

Investigation confirms Apache AGE **does NOT support `shortestPath()`**:

- [GitHub Issue #2162](https://github.com/apache/age/issues/2162) - `SHORTEST` keyword throws syntax error
- [GitHub Issue #195](https://github.com/apache/age/issues/195) - Variable-length paths exhibit exponential degradation
- AGE version 1.5.0 lacks native pathfinding algorithms
- openCypher standard doesn't mandate `shortestPath()` (Neo4j-specific extension)

**Observed Performance (from Issue #195):**
| Max Hops | Time (1.5M nodes, 1.2M edges) |
|----------|-------------------------------|
| 4        | 7 seconds                     |
| 5        | 3 minutes 30 seconds          |
| 6        | ~7 minutes                    |
| 10       | Indefinite hang               |

## Decision

Implement **Bidirectional Breadth-First Search (BFS)** in application code instead of relying on Cypher variable-length patterns for pathfinding.

### Strategy 1: Bidirectional BFS (Recommended for Shortest Path)

Instead of one query that enumerates all paths, use iterative neighbor expansion from both ends:

```python
def find_shortest_path(from_id: str, to_id: str, max_hops: int = 10) -> Optional[List[str]]:
    """
    Bidirectional BFS - meets in the middle.

    Time complexity: O(b^(d/2)) instead of O(b^d)
    For b=20, d=6: 8000 vs 64,000,000 node lookups
    """
    if from_id == to_id:
        return [from_id]

    # Track visited nodes and their parents from each direction
    forward_visited = {from_id: None}
    backward_visited = {to_id: None}

    # Current frontier sets
    forward_frontier = {from_id}
    backward_frontier = {to_id}

    for depth in range(max_hops // 2 + 1):
        # Expand the smaller frontier (optimization)
        if len(forward_frontier) <= len(backward_frontier):
            # Expand forward
            next_frontier = set()
            for node_id in forward_frontier:
                neighbors = get_neighbors(node_id)  # Single-hop query
                for neighbor in neighbors:
                    if neighbor not in forward_visited:
                        forward_visited[neighbor] = node_id
                        next_frontier.add(neighbor)

                    # Check for intersection
                    if neighbor in backward_visited:
                        return reconstruct_path(
                            neighbor, forward_visited, backward_visited
                        )
            forward_frontier = next_frontier
        else:
            # Expand backward (symmetric)
            ...

    return None  # No path found within max_hops
```

**Complexity Comparison:**
- Current (exhaustive): O(b^d) where b=branching factor, d=depth
- Bidirectional BFS: O(b^(d/2))
- For b=20, d=6: **8,000** vs **64,000,000** node lookups

### Reference Implementation

Drop-in implementation for `QueryService`:

```python
from typing import List, Dict, Set, Optional

def bidirectional_shortest_path(
    client,
    start_id: str,
    end_id: str,
    max_hops: int = 6
) -> Optional[List[str]]:
    """
    Finds the shortest path between two concepts using Bidirectional BFS.

    Why this is fast:
    - Instead of one massive exponential query, it runs ~2*depth small linear queries.
    - It expands from both sides simultaneously, meeting in the middle.
    - It stops strictly when the frontiers intersect.

    Args:
        client: Your AGEClient instance
        start_id: The starting Concept ID
        end_id: The target Concept ID
        max_hops: Safety limit to prevent infinite loops (default 6 is usually plenty)

    Returns:
        List of concept_ids forming the path [start, ..., end], or None if no path found.
    """

    # 0. Edge case: Start equals End
    if start_id == end_id:
        return [start_id]

    # 1. Initialize Frontiers
    # Maps define the path: {child_id: parent_id}
    # This allows us to trace the path back to the source/target once we meet.
    parents_start: Dict[str, Optional[str]] = {start_id: None}
    parents_end: Dict[str, Optional[str]] = {end_id: None}

    # Frontiers are the sets of nodes we are currently expanding
    front_start: Set[str] = {start_id}
    front_end: Set[str] = {end_id}

    # 2. Main Loop
    for _ in range(max_hops):
        # Optimization: Always expand the smaller frontier to minimize database load
        if len(front_start) > len(front_end):
            # Swap the references so we always process the smaller set
            front_start, front_end = front_end, front_start
            parents_start, parents_end = parents_end, parents_start

        if not front_start:
            # If a frontier is empty, the path is blocked
            return None

        # 3. Batch Query Neighbors
        # We fetch ALL neighbors for the entire frontier in one SQL query.
        # Note: We enforce :Concept labels to ignore metadata nodes (Sources/Instances)
        next_front = set()

        # Convert set to list for JSON serialization in query
        current_ids = list(front_start)

        query = """
        MATCH (current:Concept)-[]-(next:Concept)
        WHERE current.concept_id IN $ids
        RETURN current.concept_id as parent, next.concept_id as child
        """

        # Execute via your AGEClient
        results = client._execute_cypher(query, params={'ids': current_ids})

        # 4. Process Neighbors
        for row in results:
            parent = row['parent']
            child = row['child']

            # Check for Intersection: Have we seen this child in the OTHER frontier?
            if child in parents_end:
                # FOUND IT! The paths have met at 'child'.
                return _reconstruct_path(child, parent, parents_start, parents_end)

            # If not visited yet on this side, record it
            if child not in parents_start:
                parents_start[child] = parent
                next_front.add(child)

        # Advance the frontier
        front_start = next_front

    return None


def _reconstruct_path(
    meeting_node: str,
    meeting_parent_from_active_side: str,
    active_parents: Dict[str, str],
    passive_parents: Dict[str, str]
) -> List[str]:
    """
    Stitches the two half-paths together.

    Because we swap frontiers for optimization, we need to figure out which
    parent map belongs to the 'start' side and which to the 'end' side.
    """

    # 1. Record the connection across the meeting point
    active_parents[meeting_node] = meeting_parent_from_active_side

    # 2. Trace path A (from intersection to one root)
    path_a = []
    curr = meeting_node
    while curr is not None:
        path_a.append(curr)
        curr = active_parents.get(curr)

    # 3. Trace path B (from intersection to the other root)
    path_b = []
    curr = meeting_node
    while curr is not None:
        path_b.append(curr)
        curr = passive_parents.get(curr)

    # 4. Determine orientation and merge
    # Path A and Path B both start at meeting_node.
    # One goes to Start, one goes to End.

    # Reverse A to put root at the start: [RootA ... MeetingNode]
    path_a.reverse()

    # Path B is [MeetingNode ... RootB].
    # We slice path_b[1:] to avoid duplicating the meeting node.
    full_path = path_a + path_b[1:]

    return full_path
```

**Why This Wins:**
- **Database Load:** Instead of asking Postgres to "find all paths of length 5" (billions of ops), you ask it "get neighbors for these 50 nodes" (50 index lookups)
- **Memory:** Only the visited map in Python memory, which is O(N) compared to combinatorial explosion of paths
- **Concept Filtering:** The Cypher query `MATCH (current:Concept)-[]-(next:Concept)` inherently filters out Source and Instance nodes, solving the post-processing issue

### Strategy 2: Depth-Limited Search with Early Termination

For related concepts traversal (not point-to-point), use incremental depth queries:

```python
def find_related_concepts(start_id: str, max_depth: int = 3) -> List[Dict]:
    """
    Incremental depth search - stops when we have enough results.

    Each depth level is a separate, bounded query.
    """
    all_related = {}

    for depth in range(1, max_depth + 1):
        # Query ONLY this exact depth
        query = f"""
            MATCH (start:Concept {{concept_id: $start_id}})-[r*{depth}]-(related:Concept)
            WHERE related.concept_id <> $start_id
              AND NOT related.concept_id IN $already_seen
            RETURN DISTINCT related.concept_id, related.label
            LIMIT 100
        """

        results = execute_query(query, {
            'start_id': start_id,
            'already_seen': list(all_related.keys())
        })

        for r in results:
            if r['concept_id'] not in all_related:
                all_related[r['concept_id']] = {
                    'label': r['label'],
                    'distance': depth
                }

        # Early termination if we have enough
        if len(all_related) >= 50:
            break

    return list(all_related.values())
```

### Strategy 3: Pre-computed Path Hints (Future Optimization)

For frequently-accessed concept pairs, maintain a shortest-path cache:

```sql
CREATE TABLE path_cache (
    from_id VARCHAR(255),
    to_id VARCHAR(255),
    distance INTEGER,
    path_ids TEXT[],  -- Array of intermediate concept IDs
    computed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (from_id, to_id)
);

-- Index for fast lookups
CREATE INDEX path_cache_endpoints ON path_cache (from_id, to_id);
CREATE INDEX path_cache_distance ON path_cache (distance);
```

Cache invalidation strategy:
- Invalidate on concept deletion
- Lazy refresh on new relationship creation
- TTL-based expiration for freshness

### Strategy 4: External Graph Library (If Needed)

For advanced algorithms (Dijkstra with weights, A*), use [apache-age-dijkstra](https://pypi.org/project/apache-age-dijkstra/) or similar:

```python
from age_dijkstra import AGEDijkstra

dijkstra = AGEDijkstra(connection)
path = dijkstra.shortest_path(
    start_vertex='concept_123',
    end_vertex='concept_456',
    weight_property='confidence'
)
```

## Implementation Plan

### Phase 1: Fix Documentation (Immediate)

Update `docs/manual/06-reference/09-CYPHER_PATTERNS.md`:
- Remove incorrect `shortestPath()` examples
- Document actual AGE limitations
- Add performance warnings for variable-length patterns

### Phase 2: Implement Bidirectional BFS (Week 1-2)

1. Add `PathfindingService` class with bidirectional BFS
2. Replace `build_shortest_path_query` usage in `concept` MCP tool
3. Add query for single-hop neighbor retrieval
4. Add depth limit warnings/enforcement

### Phase 3: Optimize Related Concepts (Week 2-3)

1. Convert `build_related_concepts_query` to incremental depth
2. Add early termination when sufficient results found
3. Cap maximum depth at 4 hops with clear documentation

### Phase 4: Add Caching Layer (Week 3-4)

1. Implement path cache table
2. Add cache lookup before BFS
3. Populate cache on successful pathfinding
4. Add cache invalidation triggers

### Phase 5: Monitoring (Ongoing)

1. Add query timing metrics
2. Log slow pathfinding operations
3. Track cache hit rates
4. Alert on pathfinding timeouts

## Consequences

### Positive

1. **Dramatic Performance Improvement:** O(b^(d/2)) vs O(b^d) - exponential reduction
2. **Predictable Latency:** Bounded per-step queries instead of unbounded enumeration
3. **Scalability:** Works with graphs of any size
4. **Flexibility:** Application-level logic enables optimization impossible in Cypher
5. **Caching Opportunities:** Can store and reuse path computations

### Negative

1. **Code Complexity:** More application logic vs single Cypher query
2. **Multiple Round Trips:** N queries for N-hop path vs 1 query (but each query is fast)
3. **Cache Maintenance:** Need invalidation logic for path cache
4. **Testing Burden:** More code paths to test

### Neutral

1. **API Unchanged:** Same MCP/REST interface, different implementation
2. **Results Equivalent:** Same paths found, just faster
3. **Database Unchanged:** No schema changes required

## Alternatives Considered

### 1. Limit Max Hops to 3-4 (Rejected)

Artificially limiting path length doesn't solve the problem - it just hides it. Users would still experience slow queries at 4 hops.

### 2. Switch to Neo4j Enterprise (Rejected)

$180,000/year licensing cost. Also doesn't address root cause - would just get faster exhaustive search.

### 3. Use PostgreSQL Recursive CTEs (Considered)

Could implement BFS in SQL:

```sql
WITH RECURSIVE path_search AS (
    SELECT concept_id, ARRAY[concept_id] AS path, 0 AS depth
    FROM concepts WHERE concept_id = $start

    UNION ALL

    SELECT r.to_concept_id, ps.path || r.to_concept_id, ps.depth + 1
    FROM path_search ps
    JOIN relationships r ON ps.concept_id = r.from_concept_id
    WHERE ps.depth < $max_depth
      AND NOT r.to_concept_id = ANY(ps.path)
)
SELECT * FROM path_search WHERE concept_id = $end LIMIT 1;
```

This is viable but harder to optimize (bidirectional search, caching) than application code.

### 4. Pre-compute All Shortest Paths (Rejected)

Floyd-Warshall or similar O(n³) pre-computation is infeasible for 100K+ nodes (10^15 operations).

## References

- [Apache AGE GitHub Issue #2162 - shortestPath not supported](https://github.com/apache/age/issues/2162)
- [Apache AGE GitHub Issue #195 - Variable-length path performance](https://github.com/apache/age/issues/195)
- [apache-age-dijkstra PyPI package](https://pypi.org/project/apache-age-dijkstra/)
- [Bidirectional Search Algorithm](https://en.wikipedia.org/wiki/Bidirectional_search)
- [ADR-016: Apache AGE Migration](./database-schema/ADR-016-apache-age-migration.md)

## Notes

### Query Optimization Quick Wins

Even before implementing BFS, some immediate improvements:

1. **Direction matters:** Query from the node with fewer connections first
   - Issue #195 shows 661ms vs 79 seconds difference just by reversing direction

2. **Reduce branching factor:** Filter relationship types when possible
   - `[r:SUPPORTS|IMPLIES*1..5]` vs `[*1..5]`

3. **Early LIMIT in subqueries:**
   - Current: Find all paths, sort, limit
   - Better: Limit intermediate results

4. **Index on concept_id:** Ensure fast vertex lookup at path endpoints

### MCP Tool Impact

The `concept` tool's `connect` action is the primary consumer of pathfinding:

```python
# Current (slow)
paths = await kg.find_paths(from_id, to_id, max_hops=5)

# After optimization (fast)
path = await kg.find_shortest_path(from_id, to_id, max_hops=10)
```

The API contract remains the same - implementation changes internally.
