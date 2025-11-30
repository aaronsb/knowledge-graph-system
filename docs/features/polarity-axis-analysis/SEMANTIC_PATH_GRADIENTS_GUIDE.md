# Semantic Path Gradients - Experimental Implementation

**Status:** Experimental Research
**Branch:** `experiment/semantic-path-gradients`
**Date:** 2025-11-29

## Overview

This directory contains experimental code for analyzing reasoning paths in the knowledge graph using **gradient-based analysis** in embedding space.

Based on recent research in **Large Concept Models** (Meta, Dec 2024) and path-constrained retrieval, this approach treats concept embeddings as points in high-dimensional space and calculates directional derivatives (gradients) along relationship paths.

## What This Enables

1. **Relationship Quality Scoring** - Measure semantic distance between connected concepts
2. **Missing Link Detection** - Find concepts that bridge large semantic gaps
3. **Learning Path Optimization** - Compare pedagogical quality of concept sequences
4. **Reasoning Chain Validation** - Identify weak links in multi-hop reasoning
5. **Concept Evolution Tracking** - Monitor semantic drift as new evidence is added

## Files

- **`path_analysis.py`** - Core gradient calculation library
  - `SemanticPathAnalyzer` class with all gradient-based metrics
  - `Concept` dataclass for embedding + metadata
  - `PathMetrics` dataclass for analysis results

- **`examples.py`** - Example usage demonstrations
  - 5 runnable examples showing different use cases
  - Both simulated and real-graph scenarios

- **`sql_functions.sql`** - PostgreSQL extensions
  - Custom functions for gradient calculations
  - Path coherence scoring
  - Weak link detection
  - Relationship quality views

- **`README.md`** - This file

## Quick Start

### 1. Install Dependencies

```bash
# Already installed if you have the API dependencies
pip install numpy
```

### 2. Run Examples

```bash
cd experiments/semantic_gradients
python examples.py
```

This will run 5 demonstration examples with simulated data:
1. Basic path analysis with coherence scoring
2. Missing link detection and bridging concepts
3. Learning path comparison (which sequence is better?)
4. Semantic momentum prediction
5. Concept drift tracking over time

### 3. Install SQL Extensions (Optional)

```bash
# Apply SQL functions to your database
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph < sql_functions.sql

# Verify installation
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "\df semantic_*"
```

### 4. Test on Real Data

Once you have data in your knowledge graph:

```python
from path_analysis import SemanticPathAnalyzer, Concept
import numpy as np

# Fetch concepts from database (pseudo-code)
concepts = [
    Concept(
        concept_id=row['concept_id'],
        label=row['label'],
        embedding=np.array(row['embedding'])
    )
    for row in fetch_path_from_graph()
]

# Analyze
analyzer = SemanticPathAnalyzer()
metrics = analyzer.analyze_path(concepts)

print(f"Coherence: {metrics.coherence_score}")
print(f"Quality: {metrics.quality_rating}")
```

## Example SQL Queries

### Find weak relationships

```sql
SELECT * FROM relationship_quality
WHERE strength = 'Weak'
ORDER BY semantic_gap DESC
LIMIT 20;
```

### Analyze a specific path

```sql
SELECT
  array_to_string(array_agg(c.label ORDER BY idx), ' → ') as path,
  path_coherence(array_agg(c.embedding ORDER BY idx)) as coherence
FROM unnest(ARRAY['concept-id-1', 'concept-id-2', 'concept-id-3']) WITH ORDINALITY AS t(id, idx)
JOIN concepts c ON c.concept_id = t.id;
```

### Find bridging concepts

```sql
-- See sql_functions.sql for full example
-- Finds concepts that could bridge large semantic gaps
```

## Key Metrics Explained

### Semantic Gradient
- **What:** Directional derivative between two concepts in embedding space
- **Formula:** `gradient = embedding_B - embedding_A`
- **Interpretation:**
  - Small magnitude = concepts are close (strong relationship)
  - Large magnitude = concepts are far (weak or missing link)

### Path Coherence
- **What:** Consistency of semantic spacing along a path
- **Formula:** `coherence = 1 - variance(step_sizes) / mean(step_sizes)`
- **Range:** 0 to 1
- **Interpretation:**
  - High (>0.8) = smooth, consistent progression
  - Low (<0.5) = erratic jumps

### Curvature
- **What:** How sharply the semantic path "turns"
- **Formula:** Angular change between consecutive gradients
- **Interpretation:**
  - Low curvature = gradual transition (good for learning)
  - High curvature = sharp pivot (reasoning leap)

### Weak Link
- **What:** Step in path with unusually large semantic distance
- **Detection:** Distance > mean + 2σ (configurable)
- **Interpretation:** May indicate:
  - Incorrect relationship extraction
  - Missing intermediate concept
  - Weak inferential connection

## Research Foundation

This work builds on:

1. **Large Concept Models (LCM)** - Meta, Dec 2024
   - Reasoning in sentence-embedding space (concept space)
   - SONAR semantic embeddings
   - [Paper](https://arxiv.org/abs/2412.08821)

2. **Path-Constrained Retrieval** - 2025
   - Structural approach to LLM reasoning
   - Validates paths maintain logical relationships
   - [Paper](https://arxiv.org/html/2511.18313)

3. **Soft Reasoning Paths** - 2025
   - Gradient-based semantic gap measurement
   - [Paper](https://arxiv.org/html/2505.03285)

## Next Steps

### Immediate (Validation)
- [ ] Test on real knowledge graph paths
- [ ] Correlate semantic gap with grounding scores
- [ ] Validate weak link detection accuracy

### Near-term (Integration)
- [ ] Add API endpoints for path analysis
- [ ] Create visualization of semantic paths
- [ ] Integrate with relationship extraction pipeline

### Long-term (Advanced Features)
- [ ] Automatic missing link suggestion during ingestion
- [ ] Learning path generator using gradient optimization
- [ ] Temporal concept drift alerts
- [ ] Multi-path comparison for reasoning validation

## Notes

- This is **experimental research** - metrics and thresholds may need tuning
- Gradient calculations assume embeddings are in normalized space
- Path coherence is most meaningful for paths of 3+ concepts
- SQL functions require pgvector extension (already installed in our system)

## Related Documentation

- [`docs/guides/SEMANTIC_PATH_GRADIENTS.md`](../../docs/guides/SEMANTIC_PATH_GRADIENTS.md) - Comprehensive guide
- [`docs/guides/CROSS_ONTOLOGY_LINKING.md`](../../docs/guides/CROSS_ONTOLOGY_LINKING.md) - Cross-domain linking
- ADR-068: Unified Embedding Regeneration
- ADR-048: GraphQueryFacade

## Feedback

This is experimental work. Findings, suggestions, and results welcome!

---

**Status:** Active experimentation in progress on branch `experiment/semantic-path-gradients`
