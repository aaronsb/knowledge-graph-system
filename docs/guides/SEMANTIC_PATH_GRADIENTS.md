# Semantic Path Gradients: Analyzing Reasoning Chains in Embedding Space

**Status:** Experimental
**Date:** 2025-11-29
**Related:** [Large Concept Models (Meta, Dec 2024)](https://arxiv.org/abs/2412.08821), [Path-Constrained Retrieval](https://arxiv.org/html/2511.18313)

## Overview

This guide explores using **gradient-based analysis** on graph paths to measure semantic coherence, detect missing links, and validate reasoning chains. By treating concept embeddings as points in high-dimensional space, we can calculate directional derivatives (gradients) along relationship paths to understand conceptual flow.

## Background: Large Concept Models (LCM)

In December 2024, Meta introduced **Large Concept Models** - a shift from token-level to concept-level reasoning using sentence embeddings (SONAR space). This validates the approach of reasoning over concept embeddings rather than raw text.

**Key insight:** Our knowledge graph already operates in concept space. We can apply gradient-based analysis to reasoning paths just like LCMs do for language generation.

## What Can We Calculate?

Given a path through the graph: `A → B → C → D`

Where each concept has an embedding vector in ℝ^n (typically n=768 or 1536).

### 1. Semantic Gradient (First Derivative)

The **semantic gradient** between two concepts is the directional derivative in embedding space:

```python
gradient_AB = embedding_B - embedding_A
```

**Magnitude:** `‖gradient_AB‖` = semantic distance between concepts
**Direction:** Points toward the "semantic drift" from A to B

**Interpretation:**
- **Small gradient** → Concepts are semantically close (strong relationship)
- **Large gradient** → Concepts are far apart (weak relationship or missing intermediate)

### 2. Path Curvature (Second Derivative)

The **curvature** measures how sharply the semantic path "turns":

```python
gradient_AB = B - A
gradient_BC = C - B

curvature = gradient_BC - gradient_AB
```

**Interpretation:**
- **Low curvature** → Smooth, gradual progression (good learning path)
- **High curvature** → Sharp conceptual pivot (reasoning leap)

**Angular measure:**
```python
angle = arccos(cosine_similarity(gradient_AB, gradient_BC))
```

### 3. Path Coherence Score

Measures consistency of semantic spacing along a path:

```python
gradients = [B - A, C - B, D - C]
distances = [‖g‖ for g in gradients]

coherence = 1 - variance(distances)
```

**High coherence** → Consistent semantic spacing (coherent reasoning)
**Low coherence** → Erratic jumps (incoherent or incomplete path)

### 4. Semantic Momentum

Accumulated direction along path:

```python
momentum = (gradient_AB + gradient_BC) / 2

# Predict alignment with next concept
next_alignment = cosine_similarity(momentum, D - C)
```

**Positive alignment** → Next concept follows path trajectory
**Negative alignment** → Concept deviates from expected flow

### 5. Concept Drift Over Time

Track how concept embeddings change as new evidence is ingested:

```python
concept_t1 = get_concept_embedding_at_timestamp(t1)
concept_t2 = get_concept_embedding_at_timestamp(t2)

drift = concept_t2 - concept_t1
drift_rate = ‖drift‖ / (t2 - t1)
```

**Applications:**
- Detect evolving understanding of concepts
- Track semantic stability vs volatility
- Identify when new evidence significantly shifts meaning

## Practical Applications

### 1. Relationship Quality Scoring

**Problem:** Not all extracted relationships are equally strong.

**Solution:** Score relationships by semantic distance:

```sql
SELECT
  r.relationship_type,
  c1.label as source,
  c2.label as target,
  cosine_distance(c1.embedding, c2.embedding) as semantic_gap,
  CASE
    WHEN cosine_distance(c1.embedding, c2.embedding) < 0.3 THEN 'Strong'
    WHEN cosine_distance(c1.embedding, c2.embedding) < 0.5 THEN 'Moderate'
    ELSE 'Weak'
  END as relationship_strength
FROM relationships r
JOIN concepts c1 ON r.source_concept_id = c1.concept_id
JOIN concepts c2 ON r.target_concept_id = c2.concept_id
WHERE r.relationship_type = 'IMPLIES'
ORDER BY semantic_gap ASC;
```

**Insight:** Relationships with large semantic gaps may indicate:
- Incorrect extraction
- Missing intermediate concepts
- Weak inferential links

### 2. Missing Link Detection

**Problem:** Direct relationships might span large semantic distances.

**Solution:** Search for bridging concepts:

```python
def find_missing_links(source: Concept, target: Concept,
                      threshold: float = 0.5) -> List[Concept]:
    """Find concepts that bridge a large semantic gap"""

    gap = target.embedding - source.embedding
    gap_size = np.linalg.norm(gap)

    if gap_size < threshold:
        return []  # Direct link is fine

    # Search for concepts near the midpoint
    midpoint = (source.embedding + target.embedding) / 2
    candidates = search_concepts_near_vector(midpoint, threshold=0.7)

    # Filter to actual bridges
    bridges = []
    for candidate in candidates:
        # Calculate path distance via candidate
        dist_via = (
            np.linalg.norm(candidate.embedding - source.embedding) +
            np.linalg.norm(target.embedding - candidate.embedding)
        )

        # If detour is shorter or comparable, it's a good bridge
        if dist_via < gap_size * 1.2:  # Allow 20% overhead
            bridges.append(candidate)

    return bridges
```

**Example output:**
```
Source: "Machine Learning"
Target: "Neural Networks"
Gap: 0.68 (large)

Suggested bridges:
  - "Deep Learning" (reduces path distance by 35%)
  - "Backpropagation" (reduces path distance by 42%)
```

### 3. Learning Path Optimization

**Problem:** Which sequence of concepts provides the smoothest learning progression?

**Solution:** Optimize for low curvature and consistent spacing:

```python
def analyze_learning_path(concepts: List[Concept]) -> Dict:
    """Evaluate pedagogical quality of concept sequence"""

    embeddings = [c.embedding for c in concepts]

    # Calculate gradients between consecutive concepts
    gradients = [embeddings[i+1] - embeddings[i]
                 for i in range(len(embeddings)-1)]

    # Calculate metrics
    step_sizes = [np.linalg.norm(g) for g in gradients]

    # Curvature (angular changes)
    angles = []
    for i in range(len(gradients)-1):
        cos_sim = cosine_similarity(gradients[i], gradients[i+1])
        angles.append(np.arccos(np.clip(cos_sim, -1, 1)))

    return {
        'total_distance': sum(step_sizes),
        'avg_step_size': np.mean(step_sizes),
        'step_variance': np.var(step_sizes),  # Low = consistent pacing
        'avg_curvature': np.mean(angles) if angles else 0,  # Low = smooth
        'coherence_score': 1 - (np.var(step_sizes) / (np.mean(step_sizes) + 1e-8)),
        'quality': 'Good' if np.var(step_sizes) < 0.1 and np.mean(angles or [0]) < 0.5 else 'Poor'
    }
```

**Example:**
```python
# Compare two learning paths
path_a = ["Variables", "Functions", "Recursion", "Dynamic Programming"]
path_b = ["Variables", "Loops", "Functions", "Recursion", "Dynamic Programming"]

results_a = analyze_learning_path(get_concepts(path_a))
results_b = analyze_learning_path(get_concepts(path_b))

# Output:
# Path A: coherence=0.65, avg_curvature=0.82 (high jumps)
# Path B: coherence=0.89, avg_curvature=0.34 (smoother)
# Recommendation: Use Path B
```

### 4. Reasoning Chain Validation

**Problem:** Multi-hop reasoning chains may have weak links.

**Solution:** Analyze entire chain for coherence:

```python
def validate_reasoning_chain(chain: List[Concept]) -> Dict:
    """Check if reasoning chain is semantically coherent"""

    embeddings = [c.embedding for c in chain]
    gradients = [embeddings[i+1] - embeddings[i]
                 for i in range(len(embeddings)-1)]

    # Calculate coherence metrics
    distances = [np.linalg.norm(g) for g in gradients]

    # Identify weak links (unusually large jumps)
    mean_dist = np.mean(distances)
    std_dist = np.std(distances)
    weak_links = []

    for i, dist in enumerate(distances):
        if dist > mean_dist + 2 * std_dist:  # 2 sigma outlier
            weak_links.append({
                'step': f"{chain[i].label} → {chain[i+1].label}",
                'distance': dist,
                'severity': (dist - mean_dist) / std_dist
            })

    return {
        'chain_length': len(chain),
        'total_distance': sum(distances),
        'coherence': 1 - np.var(distances),
        'weak_links': weak_links,
        'valid': len(weak_links) == 0
    }
```

**Example output:**
```
Chain: ["Embedding Models", "Vector Search", "Semantic Similarity", "Cosine Distance"]
Coherence: 0.91
Weak links: None
Status: Valid reasoning chain

Chain: ["Embedding Models", "Database Indexes", "SQL Queries"]
Coherence: 0.43
Weak links:
  - "Embedding Models → Database Indexes" (distance: 0.78, severity: 3.2σ)
Status: Invalid - missing intermediate concept
```

### 5. Concept Evolution Timeline

**Problem:** How does a concept's meaning change as new evidence is added?

**Solution:** Track embedding drift over ingestion timeline:

```python
def track_concept_evolution(concept_id: str) -> List[Dict]:
    """Track how concept embedding changes over time"""

    # Get evidence in chronological order
    evidence = get_concept_evidence_timeline(concept_id)

    evolution = []
    prev_embedding = None

    for timestamp, sources in evidence.items():
        # Recalculate concept embedding using only evidence up to this point
        current_embedding = compute_concept_embedding(concept_id, until=timestamp)

        if prev_embedding is not None:
            drift = current_embedding - prev_embedding
            drift_magnitude = np.linalg.norm(drift)

            evolution.append({
                'timestamp': timestamp,
                'source_count': len(sources),
                'drift_magnitude': drift_magnitude,
                'drift_direction': drift / (drift_magnitude + 1e-8),
                'cumulative_drift': np.linalg.norm(current_embedding - evolution[0]['embedding'])
            })

        evolution.append({
            'timestamp': timestamp,
            'embedding': current_embedding,
            'source_count': len(sources)
        })

        prev_embedding = current_embedding

    return evolution
```

**Visualization:**
```
Concept: "Transformer Architecture"

2024-01: drift=0.00 (initial ingestion)
2024-03: drift=0.12 (attention mechanism details added)
2024-06: drift=0.08 (positional encoding refinements)
2024-09: drift=0.31 (flash attention breakthrough - significant shift!)
2024-11: drift=0.05 (minor clarifications)

Total drift: 0.56 (moderate evolution)
Stability: Medium (one major shift)
```

## SQL Extensions for Gradient Analysis

Add custom PostgreSQL functions for gradient calculations:

```sql
-- Semantic gradient (vector difference)
CREATE FUNCTION semantic_gradient(emb1 vector, emb2 vector)
RETURNS vector AS $$
  SELECT emb2 - emb1;
$$ LANGUAGE SQL IMMUTABLE;

-- Gradient magnitude (semantic distance)
CREATE FUNCTION gradient_magnitude(emb1 vector, emb2 vector)
RETURNS float AS $$
  SELECT l2_distance(emb1, emb2);
$$ LANGUAGE SQL IMMUTABLE;

-- Path coherence for array of embeddings
CREATE FUNCTION path_coherence(embeddings vector[])
RETURNS float AS $$
DECLARE
  distances float[] := '{}';
  mean_dist float;
  variance float;
BEGIN
  -- Calculate pairwise distances
  FOR i IN 1..array_length(embeddings, 1)-1 LOOP
    distances := distances || l2_distance(embeddings[i], embeddings[i+1]);
  END LOOP;

  -- Calculate variance
  SELECT AVG(d), VARIANCE(d) INTO mean_dist, variance FROM unnest(distances) d;

  -- Coherence = 1 - normalized variance
  RETURN 1 - (variance / (mean_dist + 0.0001));
END;
$$ LANGUAGE plpgsql;

-- Find weak links in reasoning path
CREATE FUNCTION find_weak_links(concept_ids text[])
RETURNS TABLE(
  source_id text,
  target_id text,
  semantic_gap float,
  severity float
) AS $$
DECLARE
  embeddings vector[];
  distances float[];
  mean_dist float;
  std_dist float;
BEGIN
  -- Fetch embeddings
  SELECT array_agg(c.embedding ORDER BY idx)
  INTO embeddings
  FROM unnest(concept_ids) WITH ORDINALITY AS t(id, idx)
  JOIN concepts c ON c.concept_id = t.id;

  -- Calculate distances
  FOR i IN 1..array_length(embeddings, 1)-1 LOOP
    distances[i] := l2_distance(embeddings[i], embeddings[i+1]);
  END LOOP;

  -- Calculate statistics
  SELECT AVG(d), STDDEV(d) INTO mean_dist, std_dist FROM unnest(distances) d;

  -- Return outliers (> 2 sigma)
  FOR i IN 1..array_length(distances, 1) LOOP
    IF distances[i] > mean_dist + 2 * std_dist THEN
      RETURN QUERY SELECT
        concept_ids[i],
        concept_ids[i+1],
        distances[i],
        (distances[i] - mean_dist) / std_dist;
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql;
```

## Example Queries

### Find relationships with large semantic gaps

```sql
SELECT
  c1.label as source,
  r.relationship_type,
  c2.label as target,
  gradient_magnitude(c1.embedding, c2.embedding) as gap
FROM relationships r
JOIN concepts c1 ON r.source_concept_id = c1.concept_id
JOIN concepts c2 ON r.target_concept_id = c2.concept_id
WHERE gradient_magnitude(c1.embedding, c2.embedding) > 0.6
ORDER BY gap DESC
LIMIT 20;
```

### Analyze multi-hop reasoning path

```sql
-- Find path from "Machine Learning" to "Neural Networks"
WITH RECURSIVE path AS (
  SELECT
    c1.concept_id,
    c1.label,
    c1.embedding,
    ARRAY[c1.concept_id] as path_ids,
    0 as depth
  FROM concepts c1
  WHERE c1.label = 'Machine Learning'

  UNION ALL

  SELECT
    c2.concept_id,
    c2.label,
    c2.embedding,
    p.path_ids || c2.concept_id,
    p.depth + 1
  FROM path p
  JOIN relationships r ON r.source_concept_id = p.concept_id
  JOIN concepts c2 ON r.target_concept_id = c2.concept_id
  WHERE c2.label = 'Neural Networks'
    AND p.depth < 5
    AND NOT c2.concept_id = ANY(p.path_ids)
)
SELECT
  array_to_string(array_agg(label ORDER BY depth), ' → ') as reasoning_path,
  path_coherence(array_agg(embedding ORDER BY depth)) as coherence
FROM path
WHERE depth = (SELECT MAX(depth) FROM path)
GROUP BY path_ids;
```

## Implementation Roadmap

### Phase 1: Core Gradient Functions (Experimental)
- [x] Research LCM and gradient-based approaches
- [ ] Implement Python gradient calculation utilities
- [ ] Test on sample paths from existing graph
- [ ] Validate metrics against manual analysis

### Phase 2: SQL Integration
- [ ] Add PostgreSQL vector arithmetic functions
- [ ] Implement path coherence calculations
- [ ] Create weak link detection queries
- [ ] Performance testing on large graphs

### Phase 3: API Endpoints
- [ ] `/queries/paths/analyze` - Analyze reasoning path
- [ ] `/queries/concepts/{id}/evolution` - Track concept drift
- [ ] `/queries/relationships/quality` - Relationship scoring
- [ ] `/queries/paths/suggest-bridges` - Missing link detection

### Phase 4: Visualization
- [ ] Path gradient visualization (2D projection)
- [ ] Concept drift timeline charts
- [ ] Relationship quality heatmaps
- [ ] Interactive path exploration

## Experimental Results

*This section will be populated as we test gradient analysis on real data.*

### Test 1: Relationship Quality Correlation

**Hypothesis:** Relationships with smaller semantic gaps have higher grounding scores.

**Method:** Compare `gradient_magnitude` vs `grounding_strength` for 1000 random relationships.

**Results:** TBD

### Test 2: Missing Link Detection Accuracy

**Hypothesis:** Bridging concepts improve path coherence by >30%.

**Method:** Identify 50 high-gap relationships, search for bridges, measure coherence improvement.

**Results:** TBD

### Test 3: Learning Path Optimization

**Hypothesis:** Paths with lower curvature are pedagogically superior.

**Method:** Compare gradient-optimized vs random concept sequences, user comprehension testing.

**Results:** TBD

## References

- [Large Concept Models: Language Modeling in a Sentence Representation Space](https://arxiv.org/abs/2412.08821) - Meta AI, Dec 2024
- [Path-Constrained Retrieval: Structural Approach to Reliable LLM Reasoning](https://arxiv.org/html/2511.18313)
- [Soft Reasoning Paths for Knowledge Graph Completion](https://arxiv.org/html/2505.03285)
- [Knowledge Graph Embeddings with Concepts](https://www.sciencedirect.com/science/article/abs/pii/S0950705118304945)
- [Semantic-guided Graph Neural Network for Heterogeneous Graph Embedding](https://www.sciencedirect.com/science/article/abs/pii/S095741742301312X)

## Related Documentation

- [Cross-Ontology Knowledge Linking](./CROSS_ONTOLOGY_LINKING.md) - Automatic semantic linking across domains
- [Architecture Documentation](../architecture/ARCHITECTURE.md) - Overall system design
- ADR-048: GraphQueryFacade - Query safety and namespace isolation
- ADR-068: Unified Embedding Regeneration - Embedding generation system

---

**Status:** This is experimental research. Gradient-based analysis shows promise based on recent LCM work, but requires validation on our specific graph structure and use cases. Feedback welcome!
