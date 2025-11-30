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

### Phase 3: Integration Points

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
   - Performance impact (embedding operations are expensive)
   - New API surface area (3 endpoints + worker)
   - Future optimization needs (global caching system for embedding-dependent queries)
4. **Long-term Impact:** Affects how users explore conceptual dimensions

**Proposed ADR Number:** ADR-070

**Proposed Title:** "Polarity Axis Analysis for Bidirectional Semantic Dimensions"

**Key Decision:** On-demand polarity axis calculation via background workers for flexible user-defined semantic exploration

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

### Phase 3: Documentation
- [ ] Write ADR-070
- [ ] Update API documentation (OpenAPI)
- [ ] Add usage examples to guides
- [ ] Update kg CLI to support polarity axis commands

### Phase 4: CLI Integration
- [ ] `kg polarity analyze <positive_id> <negative_id>`
- [ ] `kg polarity discover --type PREVENTS`
- [ ] `kg polarity project <axis_id> <concept_id>`

**Note on Performance:** A future global caching system for all embedding-dependent queries (concept search, grounding calculation, polarity analysis) would significantly improve performance. However, this ADR focuses on establishing the core capability first, with optimization addressed holistically across all query types later.

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
- Polarity axis calculation: <5s for 20 candidates (initial implementation without caching)
- Axis discovery: <10s for 50 relationships
- Background worker prevents API blocking during calculation

**Quality:**
- Grounding correlation >0.7 for strong axes (PREVENTS, CONTRADICTS)
- Position stability: ±0.05 across repeated calculations
- Direction accuracy: 90%+ alignment with human judgment (spot check)

**Adoption:**
- 10+ polarity axis analyses per week (user engagement)
- Zero performance regressions on existing endpoints
- Documentation enables self-service usage

## Risks & Mitigations

**Risk 1: Expensive computation affects user experience**
- Mitigation: Background workers prevent API blocking, job queue handles concurrent requests
- Future optimization: Global caching system for all embedding-dependent queries
- Fallback: Pre-compute popular axes if performance becomes critical

**Risk 2: Unintuitive results**
- Mitigation: Clear documentation, diverse examples, visual aids in interfaces
- Fallback: Allow manual axis definition (override auto-discovery)

**Risk 3: Users discover axes that don't make semantic sense**
- Mitigation: Provide grounding correlation metrics, allow filtering by correlation strength
- Fallback: Documentation on interpreting weak axes

## Open Questions

1. **Should we persist axis definitions in the graph?**
   - Pro: Faster retrieval, historical tracking, can query "which axes use this concept?"
   - Con: Schema overhead, invalidation complexity when embeddings change
   - **Recommendation:** Start with on-demand computation only, add persistence if usage patterns reveal value

2. **How to handle multi-dimensional axes?**
   - Current: 1D projection (positive ↔ negative)
   - Future: Could project onto 2D plane (Modern/Traditional × Centralized/Decentralized)
   - **Recommendation:** Start with 1D, design for extension

3. **Should grounding be required for polarity?**
   - Current: Grounding adds interpretability but isn't required for projection
   - **Recommendation:** Optional enhancement, not requirement

## Implementation Phases

- **Phase 1:** Worker Service
- **Phase 2:** API Endpoints
- **Phase 3:** Documentation + ADR
- **Phase 4:** Interface Integration (MCP, CLI, Web)

## User Interface Specifications

### MCP Server (Claude Desktop Integration)

**MCP Tool: `analyze_polarity_axis`**

```json
{
  "name": "analyze_polarity_axis",
  "description": "Analyze bidirectional semantic spectrum between two opposing concepts",
  "inputSchema": {
    "type": "object",
    "properties": {
      "positive_pole_query": {
        "type": "string",
        "description": "Search query for positive pole (e.g., 'Digital Transformation')"
      },
      "negative_pole_query": {
        "type": "string",
        "description": "Search query for negative pole (e.g., 'Legacy Systems')"
      },
      "auto_discover_candidates": {
        "type": "boolean",
        "description": "Auto-discover related concepts to project onto axis",
        "default": true
      }
    },
    "required": ["positive_pole_query", "negative_pole_query"]
  }
}
```

**MCP Tool: `discover_polarity_axes`**

```json
{
  "name": "discover_polarity_axes",
  "description": "Auto-discover polarity axes from oppositional relationships (PREVENTS, CONTRADICTS)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "relationship_types": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Relationship types to search (e.g., ['PREVENTS', 'CONTRADICTS'])",
        "default": ["PREVENTS", "CONTRADICTS"]
      },
      "max_results": {
        "type": "number",
        "description": "Maximum number of axes to return",
        "default": 10
      }
    }
  }
}
```

**Response Format:**
```
📊 Polarity Axis: Legacy Systems ↔ Digital Transformation
   Semantic Distance: 1.07
   Grounding Correlation: r=0.85 (strong)

Projected Concepts:
  ➕ Toward Digital Transformation:
     • Agile (+0.194) - grounding: +0.227
     • Modern Operating Model (+0.089) - grounding: +0.133

  ⚖️  Neutral/Mixed:
     • Tech Debt (-0.049) - grounding: 0.000

  ➖ Toward Legacy Systems:
     • Traditional Operating Models (-0.124) - grounding: -0.040

💡 Insight: Strong correlation between axis position and grounding suggests
   this is a meaningful semantic dimension with clear value polarity.
```

### CLI Tool (kg command)

**Command Structure:**

```bash
# Analyze specific polarity axis
kg polarity analyze <positive_concept> <negative_concept> [options]

# Auto-discover axes from relationships
kg polarity discover [--type PREVENTS] [--type CONTRADICTS] [--limit 10]

# Project single concept onto axis
kg polarity project <axis_id> <concept_id>

# Quick analysis from concept IDs
kg polarity axis <positive_id> <negative_id> [--candidates <id1> <id2> ...]
```

**Example Usage:**

```bash
$ kg polarity analyze "Digital Transformation" "Legacy Systems"
```

**Output (Table Format):**
```
Polarity Axis Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Positive Pole: Digital Transformation (grounding: -0.022)
Negative Pole: Legacy Systems (grounding: -0.075)
Semantic Distance: 1.071
Grounding Correlation: r=0.85, p=0.023 ✓ Strong

Projected Concepts (9 total)
┌────────────────────────────────┬──────────┬──────────┬───────────┐
│ Concept                        │ Position │ Direction│ Grounding │
├────────────────────────────────┼──────────┼──────────┼───────────┤
│ Agile                          │ +0.194   │ Positive │ +0.227    │
│ Modern Operating Model         │ +0.089   │ Neutral  │ +0.133    │
│ Tech Debt                      │ -0.049   │ Neutral  │ 0.000     │
│ Traditional Operating Models   │ -0.124   │ Negative │ -0.040    │
└────────────────────────────────┴──────────┴──────────┴───────────┘

Visual Spectrum:
Legacy Systems ●────────────┼────────────● Digital Transformation
                  ^         ^         ^
               -0.124    -0.049    +0.194
```

**Discover Mode:**
```bash
$ kg polarity discover --type PREVENTS --limit 5
```

**Output:**
```
Discovered Polarity Axes (PREVENTS relationships)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Tech Debt ↔ Technology Advantage
   Magnitude: 0.94 | Grounding Δ: 0.22 | r=0.88

2. Legacy Systems ↔ Digital Transformation
   Magnitude: 1.07 | Grounding Δ: 0.05 | r=0.85

3. Siloed Digital Transformation ↔ Digital Transformation
   Magnitude: 0.52 | Grounding Δ: 0.12 | r=0.76

4. Integration Challenges ↔ Technology Advantage
   Magnitude: 0.89 | Grounding Δ: 0.18 | r=0.82

5. Misalignment ↔ Enterprise Finance Organization
   Magnitude: 0.95 | Grounding Δ: 0.31 | r=0.79

Run 'kg polarity analyze <positive> <negative>' to explore an axis
```

**JSON Mode:**
```bash
$ kg polarity analyze "Modern" "Traditional" --json
{
  "axis": {
    "positive_pole": {"concept_id": "...", "label": "Modern Operating Model", "grounding": 0.133},
    "negative_pole": {"concept_id": "...", "label": "Traditional Operating Models", "grounding": -0.040},
    "magnitude": 0.5035
  },
  "projections": [...],
  "statistics": {...},
  "grounding_correlation": {"r": 0.85, "p_value": 0.023}
}
```

### Web Workstation (Browser Client)

**Location:** Explorer → Polarity Axis Explorer (new sidebar category)

**UI Components:**

**1. Axis Discovery Panel**
```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 Discover Polarity Axes                                   │
├─────────────────────────────────────────────────────────────┤
│ Relationship Types: [PREVENTS ▼] [CONTRADICTS ▼]           │
│                                                             │
│ Discovered Axes (5):                                        │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Tech Debt ↔ Technology Advantage                        │ │
│ │ ━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━              │ │
│ │ Magnitude: 0.94 | Correlation: r=0.88 🟢                │ │
│ │ [Explore →]                                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Legacy Systems ↔ Digital Transformation                 │ │
│ │ ━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━              │ │
│ │ Magnitude: 1.07 | Correlation: r=0.85 🟢                │ │
│ │ [Explore →]                                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Load More]                                                 │
└─────────────────────────────────────────────────────────────┘
```

**2. Axis Analysis View (Interactive)**
```
┌─────────────────────────────────────────────────────────────┐
│ Polarity Axis: Legacy Systems ↔ Digital Transformation     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ ◄────────────────────┼────────────────────►                │
│ Legacy Systems     Midpoint    Digital Transformation      │
│ Grounding: -0.075     0.00      Grounding: -0.022          │
│                                                             │
│ Projected Concepts:                                         │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                            ┼                            │ │
│ │  Traditional●          ●Tech  ●Agile                    │ │
│ │  Operating             Debt   Modern●                   │ │
│ │  Models                       Operating                 │ │
│ │                               Model                      │ │
│ │ ━━━━━━━━━━━━━━━━━━━━━━┼━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │ │
│ │ -1.0        -0.5       0        +0.5          +1.0      │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Statistics:                                                 │
│ • Semantic Distance: 1.071                                  │
│ • Grounding Correlation: r=0.85 (p=0.023) 🟢 Strong        │
│ • Mean Axis Distance: 0.753 (moderate orthogonality)       │
│                                                             │
│ Concept Details:                                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ✓ Agile                              Position: +0.194   │ │
│ │   Direction: Positive                Grounding: +0.227  │ │
│ │   Axis Distance: 1.008 (orthogonal)                     │ │
│ │   [View Concept] [View Relationships]                   │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ ○ Tech Debt                          Position: -0.049   │ │
│ │   Direction: Neutral                 Grounding: 0.000   │ │
│ │   Axis Distance: 0.872                                  │ │
│ │   [View Concept] [View Relationships]                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Export JSON] [Save Axis] [Share Link]                     │
└─────────────────────────────────────────────────────────────┘
```

**3. Custom Axis Creator**
```
┌─────────────────────────────────────────────────────────────┐
│ Create Custom Polarity Axis                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Positive Pole:                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [Search concepts...                           ] [🔍]    │ │
│ │                                                         │ │
│ │ Selected: Digital Transformation                        │ │
│ │ Grounding: -0.022                                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Negative Pole:                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [Search concepts...                           ] [🔍]    │ │
│ │                                                         │ │
│ │ Selected: Legacy Systems                                │ │
│ │ Grounding: -0.075                                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Options:                                                    │
│ ☑ Auto-discover related concepts                           │
│ ☑ Calculate grounding correlation                          │
│ ☐ Include only concepts with >0.5 grounding                │
│                                                             │
│ [Cancel] [Analyze Axis →]                                  │
└─────────────────────────────────────────────────────────────┘
```

**4. Integration with Concept View**

When viewing a concept, add "Polarity Analysis" tab:

```
┌─────────────────────────────────────────────────────────────┐
│ Concept: Agile                                              │
├─────────────────────────────────────────────────────────────┤
│ [Overview] [Relationships] [Evidence] [Polarity Analysis]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Position on Known Axes:                                     │
│                                                             │
│ Tech Debt ↔ Technology Advantage                           │
│ ━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━                  │
│                +0.194 (Positive)                            │
│                                                             │
│ Legacy Systems ↔ Digital Transformation                    │
│ ━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━                  │
│                +0.168 (Positive)                            │
│                                                             │
│ [Discover More Axes] [Create Custom Axis]                  │
└─────────────────────────────────────────────────────────────┘
```

**Visual Design Notes:**
- Use color gradient along axis (red → neutral → green OR custom theme)
- Concept bubbles sized by grounding strength
- Hover shows full stats (position, distance, grounding)
- Click concept bubble to navigate to concept view
- Drag concepts to see how adding them changes axis statistics
- Export axis as PNG/SVG for documentation

## Next Steps

1. Review this plan with team
2. Draft ADR-070
3. Create feature branch: `feature/polarity-axis-analysis`
4. Implement Phase 1 (worker service)
5. Add tests
6. Iterate based on feedback

---

**Questions? Concerns? Feedback welcome!**
