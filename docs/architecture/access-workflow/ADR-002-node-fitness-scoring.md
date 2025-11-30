# ADR-002: Node Fitness Scoring System

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-001 (Multi-Tier Access), ADR-004 (Pure Graph Design)

## Context

A knowledge graph should evolve over time, with useful concepts naturally rising in prominence based on actual usage patterns. Without an evolutionary mechanism, the system treats all concepts equally regardless of their utility. Additionally, pure semantic search can be biased toward popular concepts that may not be the most relevant for specific queries.

## Decision

Implement automatic fitness scoring based on query patterns, with manual curator override capability. Each Concept node will track usage metrics that influence search result rankings, creating a self-organizing knowledge network.

### Node Fitness Properties

```cypher
(:Concept {
  // Core properties
  concept_id: string,
  label: string,
  embedding: float[],

  // Provenance
  created_by: string,      // Agent/user identifier
  created_at: datetime,    // Creation timestamp
  source_type: enum,       // "document" | "conversation" | "inference"

  // Fitness metrics (auto-updated)
  query_count: integer,    // Total times retrieved
  relevance_sum: float,    // Cumulative match scores
  fitness_score: float,    // relevance_sum / query_count

  // Curator adjustments
  manual_bias: float,      // -1.0 to +1.0, curator override
  final_score: float,      // fitness_score + manual_bias

  // Quality flags
  flagged_for_review: boolean,
  confidence: float        // 0.0 to 1.0
})
```

### Auto-Update Mechanism

**Lazy Write Pattern:**
- Query operations queue fitness updates
- Batch flush every 100 queries or 10 seconds
- Updates happen outside query transaction (async)

```python
class ScoringQueue:
    updates = defaultdict(lambda: {"count": 0, "relevance": 0.0})

    def record_hit(concept_id: str, relevance: float):
        updates[concept_id]["count"] += 1
        updates[concept_id]["relevance"] += relevance

    async def flush():
        # Batch update Neo4j
        UNWIND $updates as u
        MATCH (c:Concept {concept_id: u.id})
        SET c.query_count = coalesce(c.query_count, 0) + u.count,
            c.relevance_sum = coalesce(c.relevance_sum, 0.0) + u.relevance,
            c.fitness_score = c.relevance_sum / c.query_count,
            c.final_score = c.fitness_score + coalesce(c.manual_bias, 0.0)
```

### Search Boosting

```cypher
// Vector search with fitness boost
CALL db.index.vector.queryNodes('concept-embeddings', 10, $embedding)
YIELD node, score
RETURN node, (score * (1 + node.final_score)) as boosted_score
ORDER BY boosted_score DESC
```

### Curator Interventions

```python
# Promote undervalued concept
curator.adjust_bias("concept_091", bias=+0.5, reason="Critical but obscure")

# Demote over-prominent concept
curator.adjust_bias("concept_042", bias=-0.3, reason="Popular but low quality")
```

## Consequences

### Positive
- Self-organizing knowledge network evolves based on actual usage
- Useful concepts naturally promoted through organic query patterns
- Combats semantic search bias (popular ≠ relevant)
- Curator can override automated scoring for edge cases
- Minimal storage overhead (4 floats per node)
- Provides feedback loop for quality assessment

### Negative
- Requires lazy write infrastructure to avoid query slowdown
- New concepts start with low scores (cold start problem)
- Potential feedback loops if agents rely too heavily on top results
- Manual bias requires curator judgment and ongoing maintenance

### Neutral
- Fitness scores accumulate over time - need periodic normalization strategy
- May want to decay old scores to adapt to changing usage patterns
- Need clear documentation on when to apply manual bias
