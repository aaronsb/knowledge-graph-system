# ADR-078: Embedding Landscape Explorer

**Status:** Accepted (Phase 1 implemented)
**Date:** 2025-12-11
**Updated:** 2025-12-12
**Deciders:** Engineering Team
**Related ADRs:**
- ADR-070: Polarity Axis Analysis (downstream consumer of discovered axes)
- ADR-063: Semantic Diversity as Authenticity Signal (diversity overlay)
- ADR-044: Probabilistic Truth Convergence (grounding overlay)
- ADR-058: Polarity Axis Triangulation (mathematical foundation)

## Overview

When you want to analyze where concepts fall on a semantic spectrum (using polarity axis analysis from ADR-070), you first need to know what spectrum to measure. Currently, this requires conceptual guesswork: "Maybe Modern↔Traditional is an interesting axis?" You're imposing structure before you've seen the data.

This ADR introduces the Embedding Landscape Explorer—a 3D visualization of all concept embeddings reduced via t-SNE or UMAP. Instead of guessing at axes, you literally see the semantic structure: clusters of related concepts, gradients between regions, outliers floating alone, and natural poles at opposite ends of the space. You can then click two points, see the 3D vector between them, and send those concept IDs directly to polarity axis analysis.

The key insight: **axis discovery becomes a visual task instead of a conceptual one**. You look at the landscape and say "I can see this dimension" rather than thinking "what dimension might matter here?"

---

## Context

### Current Exploration Workflow (Micro → Macro Problem)

The existing exploration pattern works "inside-out":

1. **Search** for a known term
2. **Expand** the neighborhood (add concepts 2 hops away)
3. **Discover** interesting connections by clicking around
4. **Analyze** by selecting two concepts for polarity axis

This works when you know where to start. But it fails when:
- You're new to an ontology and don't know what terms exist
- You want to understand the **overall structure** before diving in
- You're looking for unexpected patterns or outliers
- You want to find natural poles without guessing

### The Missing "Macro" View

We have:
- **2D/3D Force Graph** - Shows relationship structure (edges), but positions are arbitrary (force-directed layout, not semantic)
- **Polarity Axis** - Shows projection onto ONE user-defined axis
- **Vocabulary Chord** - Shows edge type categories and flows

We're missing:
- **Semantic positioning** - Where concepts actually sit in embedding space
- **Cluster discovery** - Natural groupings without predefined categories
- **Global structure** - The "shape" of knowledge before imposing analytical frames

### Dimensionality Reduction for Exploration

High-dimensional embeddings (768+ dimensions) contain rich semantic structure, but humans can't perceive it directly. Dimensionality reduction techniques project this structure into 2D or 3D while preserving important relationships:

**t-SNE (t-distributed Stochastic Neighbor Embedding):**
- Preserves local structure (nearby points stay nearby)
- Perplexity parameter controls local vs global emphasis
- Good for finding clusters
- Non-deterministic (different runs give different layouts)

**UMAP (Uniform Manifold Approximation and Projection):**
- Preserves both local and global structure better than t-SNE
- Faster computation
- More stable across runs
- Better at preserving distances (not just neighborhoods)

Both are well-suited for interactive exploration where the goal is pattern discovery, not precise measurement.

---

## Decision

Implement the **Embedding Landscape Explorer** as a new workspace that provides a 3D visualization of concept embeddings with interactive polarity axis discovery.

### Core Features

**1. 3D Embedding Projection**

Reduce concept embeddings to 3D using UMAP (preferred) or t-SNE:
- Server-side computation via Python (sklearn, umap-learn)
- Cache projections per ontology (invalidate on embedding changes)
- Support perplexity/n_neighbors tuning for different views

**2. Epistemic Overlays**

Map existing epistemic signals to visual properties:
- **Color** → Grounding strength (green = supported, red = contradicted)
- **Size** → Diversity score (large = rich evidence, small = echo chamber)
- **Opacity** → Confidence or evidence count
- **Shape** → Epistemic status of primary edges (optional)

**3. Interactive Axis Discovery**

Click-to-select workflow for polarity axis creation:
1. Click concept A → highlight and show info
2. Click concept B → draw 3D vector between them
3. Preview: temporarily color all points by projection onto this axis
4. "Analyze Axis" button → sends to `/query/polarity-axis` endpoint
5. Results displayed in companion panel or opens Polarity Explorer

**4. Cluster Exploration**

Tools for understanding natural groupings:
- Lasso/box selection to inspect cluster contents
- Cluster statistics (average grounding, diversity, concept count)
- "Expand cluster" to show only those concepts in neighborhood explorer

**5. Zoom Level Integration**

Connect to existing exploration workflow:
- Double-click concept → open in 2D/3D neighborhood explorer
- "Add to graph" → include in current exploration session
- Sync selection state across explorers

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Embedding Landscape Explorer                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   3D Viewport (Three.js)                 │   │
│  │                                                          │   │
│  │     ●(A)                                                 │   │
│  │       \                    ● ●                           │   │
│  │        \                  ●   ●                          │   │
│  │         \────────────────→●                              │   │
│  │          \              (axis preview)                   │   │
│  │           \                                              │   │
│  │            ●(B)              ●   ●                       │   │
│  │                               ● ●                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Perplexity   │ │ Color By     │ │ Selected Axis        │    │
│  │ [====●====]  │ │ [Grounding▼] │ │ A: "Modern Ways"     │    │
│  │ 5    30  100 │ │              │ │ B: "Traditional"     │    │
│  └──────────────┘ │ Size By      │ │ Magnitude: 0.847     │    │
│                   │ [Diversity▼] │ │ [Analyze Axis]       │    │
│  ┌──────────────┐ └──────────────┘ └──────────────────────┘    │
│  │ Algorithm    │                                              │
│  │ ○ t-SNE      │ ┌──────────────────────────────────────┐     │
│  │ ● UMAP       │ │ Concept Info                         │     │
│  └──────────────┘ │ Label: Modern Ways of Working        │     │
│                   │ Grounding: +0.127 (⚡ Moderate)       │     │
│                   │ Diversity: 0.377 (🌐 High)           │     │
│                   │ [Open in Explorer] [Add to Graph]    │     │
│                   └──────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### API Design

**Projection Dataset Lifecycle:**

Rather than on-demand computation, projections are pre-computed by a scheduled worker and served as static datasets:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Projection Dataset Lifecycle                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐         ┌──────────────────┐                      │
│  │  Ingestion  │────────▶│  Ontology        │                      │
│  │  Worker     │         │  changelist_id++ │                      │
│  └─────────────┘         └────────┬─────────┘                      │
│                                   │                                 │
│  ┌─────────────┐                  ▼                                │
│  │  Scheduler  │────────▶┌──────────────────┐                      │
│  │  (hourly or │         │  Projection      │──────▶ GPU-          │
│  │  post-ingest)│         │  Worker          │        accelerated  │
│  └─────────────┘         │                  │        UMAP          │
│                          │  • Compare       │                      │
│  ┌─────────────┐         │    changelist_id │                      │
│  │  Manual     │────────▶│  • Skip if       │                      │
│  │  Trigger    │         │    unchanged     │                      │
│  │  Endpoint   │         │  • Compute UMAP  │                      │
│  └─────────────┘         │  • Store dataset │                      │
│                          └────────┬─────────┘                      │
│                                   │                                 │
│                                   ▼                                 │
│                          ┌──────────────────┐                      │
│                          │  Static Dataset  │                      │
│                          │  (JSON file)     │                      │
│                          └────────┬─────────┘                      │
│                                   │                                 │
│                                   ▼                                 │
│                          ┌──────────────────┐                      │
│                          │  GET /projection │◀───── Browser        │
│                          │  (serves file)   │       downloads      │
│                          └──────────────────┘       once           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Endpoint: `GET /projection/{ontology}`**

Serves pre-computed projection dataset (fast, just file read):

```python
# Response
{
    "ontology": "Philosophy",
    "changelist_id": "cl_20251211_143022",  # For client cache invalidation
    "algorithm": "umap",
    "parameters": { "n_neighbors": 15, "min_dist": 0.1 },
    "computed_at": "2025-12-11T14:30:22Z",
    "concepts": [
        {
            "concept_id": "sha256:...",
            "label": "Modern Ways of Working",
            "x": 1.234,
            "y": -0.567,
            "z": 2.891,
            "grounding_strength": 0.127,
            "diversity_score": 0.377,
            "diversity_related_count": 34
        },
        // ... all concepts
    ],
    "statistics": {
        "concept_count": 156,
        "grounding_range": [-0.42, 0.51],
        "diversity_range": [0.12, 0.48],
        "computation_time_ms": 1250
    }
}
```

**Endpoint: `POST /projection/{ontology}/regenerate`** (admin only)

Manually trigger projection recomputation:

```python
# Request
{
    "force": false,  # If true, regenerate even if changelist unchanged
    "algorithm": "umap",  # Optional: override default
    "n_neighbors": 15,
    "min_dist": 0.1
}

# Response
{
    "status": "queued",  # or "skipped" if changelist unchanged
    "job_id": "job_abc123",
    "changelist_id": "cl_20251211_143022",
    "message": "Projection regeneration queued"
}
```

**Changelist Tracking (Reuses Existing Infrastructure):**

The system already tracks graph changes via `vocabulary_metrics_service.py`:
- `concept_creations_since_last_measurement`
- `vocabulary_changes_since_last_measurement`
- `relationship_creations_since_last_measurement`

The projection launcher follows the same pattern as `EpistemicRemeasurementLauncher`:

```python
class ProjectionLauncher(JobLauncher):
    def check_conditions(self) -> bool:
        metrics = self.vocab_metrics.get_remeasurement_needs()

        # Skip if no concept changes since last projection
        concept_delta = metrics['concept_creations_since_last_measurement']
        if concept_delta == 0:
            return False  # Nothing changed, skip

        # Optionally require minimum changes before regenerating
        return concept_delta >= self.min_changes_threshold  # e.g., 5
```

This ensures:
- **No redundant computation:** Skip if graph unchanged
- **Batched updates:** Wait for N changes before regenerating (configurable)
- **Consistent tracking:** Same counters used by epistemic measurement, vocabulary consolidation, etc.

**Browser Caching:**

```javascript
// Browser stores changelist_id in localStorage
const cached = localStorage.getItem(`projection_${ontology}`);
const cachedChangelistId = cached?.changelist_id;

// Fetch with If-None-Match header
const response = await fetch(`/projection/${ontology}`, {
  headers: { 'If-None-Match': cachedChangelistId }
});

if (response.status === 304) {
  // Use cached data
  return JSON.parse(cached.data);
} else {
  // New data, update cache
  const data = await response.json();
  localStorage.setItem(`projection_${ontology}`, {
    changelist_id: data.changelist_id,
    data: JSON.stringify(data)
  });
  return data;
}
```

### Implementation Phases

**Phase 1: Backend Projection Service**
- Create `api/services/embedding_projection.py`
- Implement UMAP and t-SNE projection
- Add caching layer with invalidation hooks
- Create API endpoint

**Phase 2: Basic 3D Visualization**
- Three.js viewport with OrbitControls
- Point cloud rendering with color/size mapping
- Hover tooltips showing concept info
- Click-to-select functionality

**Phase 3: Axis Discovery**
- Two-point selection mode
- 3D vector visualization between points
- "Analyze Axis" integration with polarity endpoint
- Axis preview (color points by projection)

**Phase 4: Advanced Features**
- Perplexity/n_neighbors live adjustment
- Cluster selection tools
- Integration with existing explorers
- Save/load projection configurations

---

## Consequences

### Positive

**1. Enables Top-Down Exploration**
- Start with global view, drill down to specifics
- No need to guess search terms for unfamiliar ontologies
- Discover structure before imposing analytical frames

**2. Visual Axis Discovery**
- Find natural semantic dimensions by seeing them
- Reduce guesswork in polarity axis analysis
- Compare multiple potential axes before committing

**3. Epistemic Landscape Awareness**
- See where contested concepts cluster
- Identify echo chambers (tight clusters, low diversity)
- Find outliers that may represent novel or poorly-integrated concepts

**4. Bridges Exploration Zoom Levels**
- Macro view connects to existing micro exploration
- Unified workflow from landscape → neighborhood → axis analysis

### Negative

**1. Computational Cost**
- UMAP/t-SNE on 1000+ concepts takes seconds
- Mitigation: Server-side caching, async computation

**2. Interpretation Complexity**
- Reduced dimensions lose information
- Distances in projection ≠ true semantic distances
- Mitigation: Clear documentation, perplexity tuning, show magnitude on axis selection

**3. Non-Determinism**
- Different runs may produce different layouts (especially t-SNE)
- Mitigation: Cache projections, seed random state, prefer UMAP for stability

**4. 3D Navigation Learning Curve**
- Not all users comfortable with 3D rotation
- Mitigation: Good defaults, 2D fallback option, camera presets

### Neutral

**1. Complements Rather Than Replaces**
- Existing explorers remain valuable for different tasks
- Landscape is for discovery, not detailed analysis

**2. Embedding Model Dependent**
- Projection structure depends on embedding model quality
- Changing models requires recomputation (already true for all embedding features)

---

## Alternatives Considered

### Alternative 1: 2D Only (No 3D)

**Approach:** Use 2D t-SNE/UMAP projection only.

**Pros:**
- Simpler implementation
- No 3D navigation complexity
- Works on all devices

**Cons:**
- Loses one dimension of structure
- More overlapping points
- Can't draw 3D vectors for axis preview

**Decision:** Support both 2D and 3D, with 3D as default for axis discovery workflow.

### Alternative 2: Client-Side Dimensionality Reduction

**Approach:** Send embeddings to browser, compute projection client-side using umap-js.

**Pros:**
- No server computation
- Interactive parameter tuning without API calls

**Cons:**
- Large data transfer (768 floats × N concepts)
- Slower on low-power devices
- Privacy concern (exposing raw embeddings)

**Decision:** Server-side computation with caching. Client only receives projected coordinates.

### Alternative 3: Pre-Computed Fixed Projections

**Approach:** Compute projections during ingestion, store as node properties.

**Pros:**
- Instant retrieval
- No runtime computation

**Cons:**
- Single fixed parameter set
- Storage overhead
- Can't tune perplexity/n_neighbors interactively

**Decision:** On-demand computation with caching allows parameter exploration while maintaining performance for repeated views.

### Alternative 4: PCA Instead of t-SNE/UMAP

**Approach:** Use Principal Component Analysis for dimensionality reduction.

**Pros:**
- Deterministic
- Fast (linear algebra)
- Preserves global variance structure

**Cons:**
- Assumes linear relationships
- Clusters less visible than t-SNE/UMAP
- First 3 PCs may not capture semantic structure well

**Decision:** Offer PCA as option for users who want deterministic projections, but default to UMAP for discovery.

---

## Technical Considerations

### Computational Complexity

**Understanding the math:**

UMAP and t-SNE reduce 768-dimensional embeddings to 3D coordinates. This is a matrix operation, not a simple geometric transformation:

| Algorithm | Complexity | 1,000 concepts | 10,000 concepts |
|-----------|------------|----------------|-----------------|
| UMAP | O(n^1.14) | ~1-2s | ~30s |
| t-SNE (Barnes-Hut) | O(n² log n) | ~5s | ~5min |
| t-SNE (exact) | O(n²) | ~30s | ~50min |

**Why UMAP is preferred:** Near-linear scaling, better global structure preservation, more stable across runs.

### Performance Architecture

**Recommended: Server-side computation with aggressive caching**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  API Cache  │────▶│   Compute   │
│  (renders   │◀────│  (Redis/    │◀────│   Worker    │
│   3D only)  │     │   memory)   │     │   (UMAP)    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │
   60fps 3D           < 100ms              1-30s (rare)
   rendering          cache hit            first compute
```

**Why not browser-side computation?**
- Transferring 768-dim embeddings is expensive (768 × 4 bytes × 1000 = 3MB)
- Browser JS is ~10x slower than Python/C++ for matrix ops
- umap-js works but is slow for >500 points
- WebGPU is bleeding edge and not widely supported

**Why not GPU acceleration?**
- cuML/RAPIDS requires NVIDIA GPU on server (not always available)
- Added deployment complexity
- CPU UMAP is fast enough with caching for typical ontology sizes

### Caching Strategy

**Cache key:** `(ontology_id, algorithm, n_neighbors, min_dist, random_seed)`

**Invalidation triggers:**
- Embedding regeneration (ADR-068)
- New concepts added to ontology
- User requests fresh projection with different parameters

**Cache warming:**
- Pre-compute default projection on ontology creation/modification
- Background job during low-usage periods

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| UMAP projection (500 concepts) | < 2s | First computation |
| UMAP projection (1000 concepts) | < 5s | First computation |
| UMAP projection (5000 concepts) | < 30s | First computation, show progress |
| Cached projection retrieval | < 100ms | Subsequent requests (most common) |
| 3D rendering (1000 points) | 60fps | Three.js handles this easily |
| 3D rendering (10000 points) | 30fps | May need LOD/culling |
| Axis analysis handoff | < 500ms | Reuses polarity endpoint |

### Scaling Considerations

For very large ontologies (10k+ concepts):
- **Async computation:** Return job ID, poll for completion, show spinner
- **Sample-based projection:** Compute on random subset, use out-of-sample extension for rest
- **Level-of-detail rendering:** Aggregate distant clusters into single points
- **Progressive loading:** Render nearest points first, add distant clusters over time

### GPU Acceleration (Future Enhancement)

If computation time becomes a bottleneck:

**Option 1: Server-side cuML (NVIDIA RAPIDS)**
```python
from cuml.manifold import UMAP
# 10-50x speedup on GPU
umap = UMAP(n_neighbors=15, min_dist=0.1)
projection = umap.fit_transform(embeddings)
```

**Option 2: Browser WebGPU (experimental)**
```javascript
// When WebGPU is widely supported
import { umap } from 'umap-webgpu';
const projection = await umap(embeddings, { useGPU: true });
```

**Current recommendation:** Start with CPU UMAP + caching. GPU acceleration adds complexity and is only needed if ontologies regularly exceed 5,000 concepts.

### Browser Compatibility

- Three.js requires WebGL
- Fallback to 2D canvas for unsupported browsers
- Touch support for mobile 3D navigation

---

## User Stories

**As an analyst exploring a new ontology:**
> I want to see the overall shape of concepts before searching, so I can understand what dimensions of knowledge exist without prior familiarity.

**As a researcher looking for contested areas:**
> I want to see where low-grounding concepts cluster, so I can identify regions of debate or uncertainty.

**As a user discovering polarity axes:**
> I want to click two concepts and instantly analyze how others fall between them, so I don't have to guess at meaningful semantic dimensions.

**As a knowledge curator:**
> I want to identify outlier concepts that don't cluster with others, so I can investigate whether they're poorly connected or genuinely novel.

---

## Success Metrics

**Adoption:**
- 50%+ of polarity axis analyses preceded by landscape exploration (within 3 months)
- Average 3+ axis attempts per landscape session (users exploring multiple dimensions)

**Discovery Value:**
- Users report finding unexpected clusters (qualitative feedback)
- Reduction in "no results" polarity analyses (better pole selection)

**Performance:**
- 95th percentile projection time < 5s
- Smooth 3D interaction (no jank at 1000 concepts)

---

## Future Considerations

### Projection History in Garage Storage

Currently, projections are cached as ephemeral JSON files in `/tmp/kg_projections/`. For production use and historical analysis, projections should be stored in Garage (S3-compatible object storage):

**Benefits:**
- **Time-series snapshots**: Track how the semantic landscape evolves as documents are ingested
- **Persistence**: Survives container restarts
- **Versioning**: Compare projections before/after significant ingestion events
- **Audit trail**: Understand how knowledge structure changed over time

**Proposed bucket structure:**
```
kg-projections/
├── {ontology}/
│   ├── latest.json              # Current projection (symlink or copy)
│   ├── 2025-12-12T23:55:11Z.json  # Historical snapshots
│   ├── 2025-12-11T14:30:00Z.json
│   └── ...
```

**Related work:**
This overlaps with a broader consideration for storing original source documents (not just images) in Garage. Currently only images are stored in object storage (ADR-057). A future ADR should address:
- Storing original text documents alongside extracted concepts
- Linking Source nodes to object storage URIs
- Retention policies for source materials vs. derived data (projections)

---

## References

- [UMAP: Uniform Manifold Approximation and Projection](https://arxiv.org/abs/1802.03426) - McInnes et al., 2018
- [t-SNE: Visualizing Data using t-SNE](https://jmlr.org/papers/v9/vandermaaten08a.html) - van der Maaten & Hinton, 2008
- [Three.js Documentation](https://threejs.org/docs/)
- [umap-learn Python Library](https://umap-learn.readthedocs.io/)

---

## Appendix: Perplexity/N_Neighbors Guide

**For t-SNE (perplexity parameter):**
- 5-10: Very local structure, many small clusters
- 30-50: Balanced local/global, good default
- 100+: Global structure, fewer larger clusters

**For UMAP (n_neighbors parameter):**
- 5-15: Local structure emphasized
- 15-50: Balanced, good default is 15
- 50+: More global structure

**Recommendation:** Start with UMAP n_neighbors=15, min_dist=0.1 for first exploration. Adjust if clusters seem too tight (increase min_dist) or too sparse (decrease n_neighbors).
