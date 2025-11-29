# Polarity Axis Analysis - Implementation Plan

**Status:** Planning
**Date:** 2025-11-29
**Branch:** `experiment/semantic-path-gradients`

## Overview

Promote polarity axis analysis from experimental research to production feature. This enables semantic dimension discovery, concept positioning, and bidirectional relationship exploration via API endpoints.

## Current State (Experimental)

**What we have:**
- ✅ Core gradient analysis library (`path_analysis.py`)
- ✅ Polarity axis projection algorithm (`polarity_axis_analysis.py`)
- ✅ Grounding integration (reuses `AGEClient.calculate_grounding_strength_semantic()`)
- ✅ Proof of concept with real data (PREVENTS relationships)
- ✅ Comprehensive documentation (`SEMANTIC_PATH_GRADIENTS.md`)

**What works:**
- Tech Debt ↔ Technology Advantage axis
- Legacy Systems ↔ Digital Transformation axis
- Concept projection onto bidirectional semantic dimensions
- Grounding correlation with polarity

## Proposed Implementation

### Phase 1: Core Worker Service

Create `PolarityAxisWorker` for background analysis jobs.

**Location:** `api/api/workers/polarity_axis_worker.py`

**Responsibilities:**
1. Analyze polarity axes from opposing concept pairs
2. Project candidate concepts onto axes
3. Calculate grounding correlations
4. Return structured results with position, distance, direction

**Job Input:**
```python
{
    "job_type": "polarity_axis_analysis",
    "positive_pole_id": "sha256:...",  # Concept ID
    "negative_pole_id": "sha256:...",  # Concept ID
    "candidate_ids": ["sha256:...", ...],  # Optional list of concepts to project
    "auto_discover_candidates": true,  # Optional: find related concepts
    "discovery_params": {
        "max_candidates": 20,
        "relationship_types": ["SUPPORTS", "ENABLES", "PREVENTS"],
        "max_hops": 2
    }
}
```

**Job Output:**
```python
{
    "axis": {
        "positive_pole": {
            "concept_id": "...",
            "label": "Digital Transformation",
            "grounding": -0.022,
            "embedding_preview": [0.123, ...]  # First 10 dims
        },
        "negative_pole": {
            "concept_id": "...",
            "label": "Legacy Systems",
            "grounding": -0.075,
            "embedding_preview": [...]
        },
        "magnitude": 1.0714,  # Semantic distance between poles
        "axis_vector_preview": [...]  # First 10 dims of unit vector
    },
    "projections": [
        {
            "concept_id": "...",
            "label": "Agile",
            "position": 0.194,  # -1 to +1 scale
            "axis_distance": 1.0008,  # Orthogonal distance
            "direction": "positive",  # "positive" | "negative" | "neutral"
            "grounding": 0.227,
            "alignment": {
                "positive_pole_similarity": 0.845,
                "negative_pole_similarity": 0.621
            }
        },
        ...
    ],
    "statistics": {
        "total_concepts": 4,
        "position_range": [-0.114, 0.194],
        "mean_position": 0.043,
        "std_deviation": 0.140,
        "mean_axis_distance": 0.947,
        "direction_distribution": {
            "positive": 0,
            "negative": 0,
            "neutral": 4
        }
    },
    "grounding_correlation": {
        "pearson_r": 0.847,  # Correlation between position and grounding
        "p_value": 0.023,
        "interpretation": "Strong positive correlation: Concepts toward positive pole have higher grounding"
    }
}
```

### Phase 2: API Endpoints

**Location:** `api/api/routes/queries.py`

#### 1. Analyze Polarity Axis

**Endpoint:** `POST /queries/polarity-axis`

**Request Body:**
```json
{
    "positive_pole_id": "sha256:...",
    "negative_pole_id": "sha256:...",
    "candidate_ids": ["sha256:...", "..."],
    "auto_discover_candidates": false
}
```

**Response:** Job ID for background processing
```json
{
    "job_id": "job-uuid-...",
    "status": "queued",
    "estimated_duration_seconds": 15
}
```

#### 2. Discover Polarity Axes from Relationships

**Endpoint:** `POST /queries/discover-polarity-axes`

**Purpose:** Auto-discover polarity axes from PREVENTS, CONTRADICTS relationships

**Request Body:**
```json
{
    "relationship_types": ["PREVENTS", "CONTRADICTS"],
    "min_axis_magnitude": 0.5,  # Minimum semantic distance
    "max_results": 10
}
```

**Response:**
```json
{
    "axes": [
        {
            "positive_pole": {"concept_id": "...", "label": "Digital Transformation"},
            "negative_pole": {"concept_id": "...", "label": "Legacy Systems"},
            "relationship_type": "PREVENTS",
            "magnitude": 1.0714,
            "grounding_differential": 0.053  // positive.grounding - negative.grounding
        },
        ...
    ]
}
```

#### 3. Project Concept onto Known Axis

**Endpoint:** `GET /queries/polarity-axis/{axis_id}/project/{concept_id}`

**Purpose:** Quick projection of a concept onto a previously analyzed axis

**Response:**
```json
{
    "concept_id": "...",
    "label": "Agile",
    "position": 0.194,
    "direction": "positive",
    "grounding": 0.227,
    "axis_distance": 1.0008
}
```

### Phase 3: Caching & Optimization

**Problem:** Polarity axis calculation is expensive (fetch embeddings, project multiple concepts)

**Solution:** Cache axis definitions and projections

**Cache Strategy:**
```python
# Cache axis vector for reuse
cache_key = f"polarity_axis:{positive_id}:{negative_id}"
cached_axis = redis.get(cache_key)

# TTL: 1 hour (axes are stable unless graph changes)
# Invalidate on: concept embedding regeneration

# Cache individual projections
projection_key = f"projection:{axis_id}:{concept_id}"
# TTL: 30 minutes
```

### Phase 4: Integration Points

**Where this adds value:**

1. **Concept Search Results**
   - When user searches "operating model", show position on Modern ↔ Traditional axis
   - Visual indicator: `[Legacy ●────────── Modern]`

2. **Relationship Exploration**
   - When viewing PREVENTS relationships, offer "Analyze polarity axis"
   - Auto-suggest bridging concepts (neutral position concepts)

3. **Missing Link Detection**
   - Find concepts with high axis distance (orthogonal) as potential bridges
   - Suggest intermediate concepts to smooth semantic gaps

4. **Learning Path Generation**
   - Order concepts along axis for pedagogical progression
   - Start from familiar (user's current understanding) → unfamiliar

## ADR Recommendation

**Yes, this warrants an ADR** because:

1. **Architectural Decision:** Adding polarity axis analysis as a core query capability
2. **Multiple Alternatives:** Could be client-side computation, pre-computed, or on-demand
3. **Significant Consequences:**
   - Performance impact (embedding operations)
   - Caching strategy required
   - New API surface area
4. **Long-term Impact:** Affects how users explore conceptual dimensions

**Proposed ADR Number:** ADR-070

**Proposed Title:** "Polarity Axis Analysis for Bidirectional Semantic Dimensions"

**Key Decision:** On-demand polarity axis calculation via background workers, with caching for repeated queries

## Implementation Checklist

### Phase 1: Worker Service
- [ ] Create `api/api/workers/polarity_axis_worker.py`
- [ ] Implement `PolarityAxisAnalyzer` class (refactor from experiments)
- [ ] Add job types to worker registry
- [ ] Write unit tests for axis calculation
- [ ] Write unit tests for projection algorithm

### Phase 2: API Endpoints
- [ ] Add `/queries/polarity-axis` endpoint
- [ ] Add `/queries/discover-polarity-axes` endpoint
- [ ] Add `/queries/polarity-axis/{axis_id}/project/{concept_id}` endpoint
- [ ] Add request/response Pydantic models
- [ ] Write integration tests

### Phase 3: Caching
- [ ] Design cache key structure
- [ ] Implement Redis caching layer
- [ ] Add cache invalidation on embedding regeneration
- [ ] Add cache metrics (hit rate, TTL effectiveness)

### Phase 4: Documentation
- [ ] Write ADR-070
- [ ] Update API documentation (OpenAPI)
- [ ] Add usage examples to guides
- [ ] Update kg CLI to support polarity axis commands

### Phase 5: CLI Integration
- [ ] `kg polarity analyze <positive_id> <negative_id>`
- [ ] `kg polarity discover --type PREVENTS`
- [ ] `kg polarity project <axis_id> <concept_id>`

## Migration from Experiments

**Move these files:**
```
experiments/semantic_gradients/path_analysis.py
  → api/api/lib/semantic_analysis.py  (rename SemanticPathAnalyzer)

experiments/semantic_gradients/polarity_axis_analysis.py
  → api/api/workers/polarity_axis_worker.py  (refactor PolarityAxis into worker)

experiments/semantic_gradients/SEMANTIC_PATH_GRADIENTS.md
  → docs/guides/SEMANTIC_PATH_GRADIENTS.md  (keep comprehensive guide)
```

**Deprecate:**
- `experiments/semantic_gradients/examples.py` (keep for reference only)
- `experiments/semantic_gradients/analyze_mcp_path.py` (superseded by worker)

## Success Metrics

**Performance:**
- Polarity axis calculation: <5s for 20 candidates
- Cached projection: <100ms
- Axis discovery: <10s for 50 relationships

**Quality:**
- Grounding correlation >0.7 for strong axes (PREVENTS, CONTRADICTS)
- Position stability: ±0.05 across repeated calculations
- Direction accuracy: 90%+ alignment with human judgment (spot check)

**Adoption:**
- 10+ polarity axis analyses per week (user engagement)
- Cache hit rate >80% for popular axes
- Zero performance regressions on existing endpoints

## Risks & Mitigations

**Risk 1: Expensive computation**
- Mitigation: Background workers + caching
- Fallback: Pre-compute popular axes (Modern ↔ Traditional, etc.)

**Risk 2: Unintuitive results**
- Mitigation: Clear documentation, examples, visual aids
- Fallback: Allow manual axis definition (override auto-discovery)

**Risk 3: Cache invalidation complexity**
- Mitigation: Conservative TTL (1 hour), invalidate on embedding regen only
- Fallback: Allow force-refresh via query parameter

## Open Questions

1. **Should we persist axis definitions?**
   - Pro: Faster retrieval, historical tracking
   - Con: Schema overhead, invalidation complexity
   - **Recommendation:** Start with cache-only, add persistence if demand warrants

2. **How to handle multi-dimensional axes?**
   - Current: 1D projection (positive ↔ negative)
   - Future: Could project onto 2D plane (Modern/Traditional × Centralized/Decentralized)
   - **Recommendation:** Start with 1D, design for extension

3. **Should grounding be required for polarity?**
   - Current: Grounding adds interpretability but isn't required for projection
   - **Recommendation:** Optional enhancement, not requirement

## Timeline Estimate

- **Phase 1 (Worker Service):** 2-3 days
- **Phase 2 (API Endpoints):** 2 days
- **Phase 3 (Caching):** 1 day
- **Phase 4 (Documentation + ADR):** 1 day
- **Phase 5 (CLI Integration):** 1 day

**Total:** 7-8 days (1.5 sprints)

## Next Steps

1. Review this plan with team
2. Draft ADR-070
3. Create feature branch: `feature/polarity-axis-analysis`
4. Implement Phase 1 (worker service)
5. Add tests
6. Iterate based on feedback

---

**Questions? Concerns? Feedback welcome!**
