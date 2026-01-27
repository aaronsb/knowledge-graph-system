# ADR-002: Node Fitness Scoring System

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related ADRs:** ADR-001 (Multi-Tier Access), ADR-004 (Pure Graph Design)

## Overview

Imagine you have thousands of concepts in your knowledge graph. Some get used constantly in queries and prove incredibly helpful, while others were added once and never touched again. Treating them all equally means your most valuable insights get buried alongside random noise. How do you make the good stuff rise to the top naturally?

The answer is to track which concepts actually prove useful over time, based on real usage patterns. It's like a path through a forest—the more people walk a certain route, the more worn and visible it becomes. When someone searches for "organizational design," the concepts that have been repeatedly relevant to similar queries should rank higher than concepts that just happen to contain those words.

This decision implements automatic fitness scoring where each concept accumulates a track record based on how often it's retrieved and how relevant it proves to be. Think of it as a recommendation system, but for your own knowledge instead of products. The graph learns which concepts matter through actual use, not through someone manually tagging things as "important."

Importantly, this also includes a manual override capability for curators. Sometimes a concept is genuinely important but obscure, or popular but low-quality. Human judgment can boost or demote concepts when the automated scoring misses the mark. It's evolution with intelligent design as a backup plan.

---

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
