# ADR-070: Polarity Axis Analysis for Bidirectional Semantic Dimensions

**Status:** Draft
**Date:** 2025-11-29
**Deciders:** System Architect
**Related ADRs:**
- ADR-044: Probabilistic Truth Convergence (grounding calculation)
- ADR-045: Unified Embedding Generation
- ADR-048: GraphQueryFacade (namespace safety)
- ADR-068: Unified Embedding Regeneration

## Context

The knowledge graph captures concepts and relationships with semantic embeddings, but lacks tools to explore **bidirectional semantic dimensions** - conceptual spectrums along which concepts vary.

### Problem Statement

Users need to:
1. **Discover oppositions:** Find conceptual polarity (Modern ↔ Traditional, Centralized ↔ Decentralized)
2. **Position concepts:** Determine where concepts fall on semantic spectrums
3. **Explore dimensions:** Navigate knowledge along semantic axes, not just relationship graphs
4. **Validate coherence:** Measure if concepts align with expected polarity (e.g., "Agile" closer to "Modern")

### Current Limitations

**Relationship-only navigation:**
- Users can traverse PREVENTS, SUPPORTS, CONTRADICTS edges
- But can't see the implicit **semantic dimension** these relationships form
- Example: "Legacy Systems -PREVENTS-> Digital Transformation" hints at a Modern ↔ Traditional axis, but this isn't explicit

**Missing semantic positioning:**
- No way to ask "Where does this concept fall on the Modern ↔ Traditional spectrum?"
- No quantitative measure of polarity alignment
- No way to find neutral/synthesis concepts (midpoint concepts)

**Grounding correlation unexplored:**
- Grounding scores (±values) suggest polarity but aren't connected to semantic positioning
- Example: "Agile" (+0.227 grounding) vs "Legacy Systems" (-0.075 grounding) suggests polarity, but lacks spatial representation

### Research Foundation

**Experimental validation (`experiment/semantic-path-gradients` branch):**
- Polarity axis projection using vector mathematics works with real embeddings
- Grounding correlates strongly with axis position (r > 0.8 for PREVENTS relationships)
- High curvature (sharp semantic pivots) is normal for technical concepts
- PREVENTS/CONTRADICTS relationships create natural bidirectional axes

**Large Concept Models (Meta, Dec 2024):**
- Operating in sentence-embedding space (not tokens) enables semantic reasoning
- Gradient-based analysis reveals directional semantic flow
- Multi-hop reasoning paths have measurable coherence

**Key Finding:**
Projecting concepts onto polarity axes formed by opposing concepts (positive ↔ negative poles) reveals:
- **Position:** Scalar location on spectrum (-1 to +1, 0 = midpoint)
- **Distance:** Orthogonality (concepts far from axis are multi-dimensional)
- **Direction:** Which pole the concept aligns with

## Decision

**Implement polarity axis analysis as a core query capability** using:

1. **On-demand calculation via background workers**
   - Compute axes when requested (not pre-computed)
   - Use existing grounding calculation infrastructure
   - Cache results with 1-hour TTL

2. **Three primary API endpoints:**
   - `POST /queries/polarity-axis` - Analyze specific axis
   - `POST /queries/discover-polarity-axes` - Auto-discover from PREVENTS/CONTRADICTS
   - `GET /queries/polarity-axis/{axis_id}/project/{concept_id}` - Project concept onto axis

3. **Worker-based architecture:**
   - `PolarityAxisWorker` handles background jobs
   - Reuses `AGEClient.calculate_grounding_strength_semantic()` for polarity correlation
   - Returns structured JSON with axis definition + projections

4. **Caching strategy:**
   - Cache axis definitions (positive/negative poles + unit vector)
   - Cache individual projections
   - Invalidate on embedding regeneration events

## Consequences

### Positive

**New semantic exploration capability:**
- Users can navigate conceptual dimensions, not just relationship graphs
- "Show me where 'Agile' falls on the Modern ↔ Traditional spectrum"
- "Find neutral concepts between 'Centralized' and 'Decentralized'"

**Grounding correlation makes sense:**
- Positive grounding → aligns with positive pole
- Negative grounding → aligns with negative pole
- Grounding values now have spatial meaning

**Missing link detection:**
- Concepts with high axis distance are orthogonal (different dimension)
- Suggests they might bridge gaps or add new dimensions

**Learning path optimization:**
- Order concepts along axis for pedagogical progression
- Smooth semantic transitions (low curvature paths)

**Relationship validation:**
- PREVENTS relationships should create strong axes
- Weak axes suggest relationship might be incorrect or multi-dimensional

### Negative

**Performance cost:**
- Embedding operations are expensive (768-dimensional dot products)
- Mitigated by: Background workers, caching, batching

**Interpretation complexity:**
- Position values (-1 to +1) require explanation
- Axis distance needs context (what's "high" orthogonality?)
- Mitigated by: Clear documentation, examples, visual aids

**Cache invalidation complexity:**
- Axes change when embeddings regenerate
- Concept projection changes if concept embedding changes
- Mitigated by: Conservative 1-hour TTL, invalidate on embedding regen only

**API surface growth:**
- 3 new endpoints + worker infrastructure
- More complexity in query layer
- Mitigated by: Clear separation (polarity endpoints distinct from concept/relationship queries)

### Neutral

**Not a replacement for relationship traversal:**
- Polarity axes complement (don't replace) graph navigation
- Relationships capture explicit knowledge, axes capture implicit dimensions

**Dimensionality reduction:**
- Projects multi-dimensional embeddings onto 1D axis
- Loses nuance, but gains interpretability
- Future: Could extend to 2D projections (two orthogonal axes)

## Example Use Cases Across Domains

To illustrate the versatility of polarity axis analysis, consider how it would apply to different knowledge domains:

### Software Architecture

**Axis: Monolith ↔ Microservices**

```
Monolith ●────────────────────────────────────● Microservices
         │                                    │
    Grounding: -0.15                    Grounding: +0.08
    (problematic)                       (beneficial)

Projected Concepts:
  Modular Monolith        (+0.35) - Neutral/Synthesis
  Service-Oriented Arch   (+0.72) - Toward Microservices
  Layered Architecture    (-0.18) - Toward Monolith
  Serverless             (+0.91) - Strongly Microservices
```

**Insight:** "Modular Monolith" positioned at +0.35 reveals it as a **synthesis concept** - borrowing from both paradigms. High axis distance would indicate it's introducing a third dimension (deployment model vs design pattern).

### Political Philosophy

**Axis: Individualism ↔ Collectivism**

```
Individualism ●────────────────────────────────● Collectivism
              │                                │
         Grounding: 0.0                   Grounding: 0.0
         (neutral)                        (neutral)

Projected Concepts:
  Libertarianism         (-0.82) - Strongly Individual
  Social Democracy       (+0.41) - Leaning Collective
  Communitarianism       (+0.68) - Toward Collective
  Anarchism              (-0.15) - Slightly Individual (surprising!)
```

**Insight:** Anarchism's near-neutral position (-0.15) despite expectations reveals semantic nuance - anarchist philosophy contains both individualist and collective strains. The axis exposes this complexity that relationship-only navigation might miss.

### Design Principles

**Axis: Minimalism ↔ Maximalism**

```
Minimalism ●──────────────────────────────────● Maximalism
           │                                  │
      Grounding: +0.22                  Grounding: -0.05
      (preferred)                       (contested)

Projected Concepts:
  Brutalism              (-0.91) - Strongly Minimal
  Bauhaus                (-0.73) - Toward Minimal
  Art Deco               (+0.58) - Toward Maximal
  Baroque                (+0.89) - Strongly Maximal
  Scandinavian Design    (-0.62) - Toward Minimal
```

**Insight:** Grounding correlation (r=0.87) shows cultural preference for minimalism in this knowledge base. "Art Deco" at +0.58 but still having moderate grounding suggests it's valued maximalism - controlled ornamentation vs excess.

### Research Methodology

**Axis: Empirical ↔ Theoretical**

```
Empirical ●───────────────────────────────────● Theoretical
          │                                   │
     Grounding: +0.31                   Grounding: +0.18
     (valued)                           (valued)

Projected Concepts:
  Experimental Science   (-0.88) - Strongly Empirical
  Mathematical Proof     (+0.94) - Strongly Theoretical
  Case Study             (-0.42) - Toward Empirical
  Simulation             (+0.12) - Slightly Theoretical
  Meta-Analysis          (+0.03) - Nearly Neutral
```

**Insight:** Both poles have positive grounding - **not all axes are value polarities**. "Meta-Analysis" at +0.03 is almost perfectly balanced, which matches its nature as synthesis of empirical studies with theoretical frameworks.

### Business Strategy

**Axis: Exploitation ↔ Exploration**

```
Exploitation ●────────────────────────────────● Exploration
             │                                │
        Grounding: +0.15                 Grounding: +0.28
        (stable)                         (growth-oriented)

Projected Concepts:
  Process Optimization   (-0.79) - Strongly Exploitation
  Market Research        (+0.67) - Toward Exploration
  Innovation             (+0.85) - Strongly Exploration
  Continuous Improvement (-0.33) - Leaning Exploitation
  Blue Ocean Strategy    (+0.92) - Extreme Exploration
```

**Insight:** Weak axis distance for "Continuous Improvement" (-0.33 on axis but low axis distance) suggests it's **on the spectrum** rather than orthogonal. This validates it as an exploitation activity, not a third dimension.

### Environmental Science

**Axis: Anthropocentric ↔ Ecocentric**

```
Anthropocentric ●─────────────────────────────● Ecocentric
                │                             │
           Grounding: -0.42              Grounding: +0.51
           (problematic)                 (sustainable)

Projected Concepts:
  Human Supremacy        (-0.95) - Extreme Anthropocentric
  Sustainable Dev        (+0.38) - Leaning Ecocentric
  Deep Ecology           (+0.91) - Strongly Ecocentric
  Conservation           (+0.44) - Toward Ecocentric
  Wise Use               (-0.28) - Toward Anthropocentric
```

**Insight:** Strong grounding correlation (r=0.91) reflects value shift in environmental discourse. "Sustainable Development" at +0.38 positions it as **pragmatic ecocentrism** - balancing human needs with ecological health.

### Education Philosophy

**Axis: Teacher-Centered ↔ Student-Centered**

```
Teacher-Centered ●────────────────────────────● Student-Centered
                 │                            │
            Grounding: -0.18              Grounding: +0.37
            (traditional)                 (progressive)

Projected Concepts:
  Lecture-Based          (-0.81) - Strongly Teacher-Centered
  Socratic Method        (+0.15) - Slightly Student-Centered
  Project-Based Learning (+0.76) - Strongly Student-Centered
  Apprenticeship         (+0.42) - Leaning Student-Centered
  Montessori             (+0.88) - Extreme Student-Centered
```

**Insight:** "Socratic Method" at +0.15 is surprisingly **near neutral** despite being ancient - reveals it has student-centered elements (questioning, dialogue) within teacher-controlled structure. Axis exposes this duality.

### Cognitive Science

**Axis: Nature ↔ Nurture**

```
Nature ●──────────────────────────────────────● Nurture
       │                                      │
  Grounding: 0.0                         Grounding: 0.0
  (genetic)                              (environmental)

Projected Concepts:
  Nativism               (-0.89) - Strongly Nature
  Behaviorism            (+0.84) - Strongly Nurture
  Epigenetics            (+0.22) - Leaning Nurture (!)
  Gene-Environment       (+0.05) - Nearly Neutral
  Developmental Systems  (+0.18) - Slightly Nurture
```

**Insight:** "Epigenetics" at +0.22 positioned toward Nurture despite involving genes - semantically correct because epigenetics studies how **environment influences** gene expression. Axis captures this subtle distinction that "genetics-related" tagging would miss.

### Key Patterns Revealed

**1. Synthesis Concepts Cluster Near Zero**
- Modular Monolith, Meta-Analysis, Sustainable Development
- Position ~0.0 to ±0.4 indicates **integration of both poles**

**2. Grounding Correlation Indicates Value Polarity**
- Strong correlation (r > 0.7): Value-laden axis (good ↔ bad)
- Weak correlation (r < 0.3): Descriptive axis (two valid approaches)

**3. High Axis Distance Reveals Orthogonal Concerns**
- Concept far from axis introduces **third dimension**
- Example: "Secure by Default" might be orthogonal to Monolith ↔ Microservices axis (security ≠ architecture)

**4. Unexpected Positions Expose Semantic Nuance**
- Anarchism near-neutral on Individualism ↔ Collectivism
- Socratic Method near-neutral on Teacher ↔ Student-Centered
- Reveals concepts are more complex than simple categorization

## Alternatives Considered

### Alternative 1: Pre-compute Popular Axes

**Approach:** Pre-calculate axes for known oppositions (Modern ↔ Traditional, etc.)

**Pros:**
- Instant results (no computation delay)
- Predictable performance

**Cons:**
- Can't handle user-defined axes
- Requires maintenance (which axes to pre-compute?)
- Stale data if graph changes

**Decision:** ❌ Rejected
**Reason:** On-demand + caching provides flexibility without maintenance burden

### Alternative 2: Client-Side Computation

**Approach:** Return embeddings to client, let them calculate projections

**Pros:**
- No server load
- Full flexibility for client

**Cons:**
- Exposes 768-dimensional embeddings (large payloads)
- Duplicates computation across clients
- Harder to cache centrally

**Decision:** ❌ Rejected
**Reason:** Server-side calculation enables caching and keeps embeddings private

### Alternative 3: Persist Axis Definitions

**Approach:** Store axes as graph vertices (`:PolarityAxis` node type)

**Pros:**
- Historical tracking (axis evolution over time)
- Faster retrieval (no re-computation)
- Can link concepts to axes explicitly

**Cons:**
- Schema complexity (new vertex type + edges)
- Cache invalidation more complex
- Overhead for one-off axes

**Decision:** ⏸️ Deferred
**Reason:** Start with cache-only, add persistence if demand warrants. Can add later without breaking changes.

### Alternative 4: Integrate into Existing Search

**Approach:** Add `polarityAxis` parameter to `/queries/concepts/search`

**Pros:**
- No new endpoints
- Integrated with existing workflows

**Cons:**
- Overloads search endpoint (already complex)
- Different performance characteristics (search is fast, axis analysis is slow)
- Confusing parameter semantics

**Decision:** ❌ Rejected
**Reason:** Dedicated endpoints provide clearer semantics and separate performance profiles

## Technical Design

### Polarity Axis Calculation

**Input:** Two concept IDs (positive pole, negative pole)

**Algorithm:**
```python
# 1. Fetch embeddings
positive_emb = get_embedding(positive_pole_id)  # 768-dim vector
negative_emb = get_embedding(negative_pole_id)  # 768-dim vector

# 2. Calculate axis vector (gradient from negative → positive)
axis_vector = positive_emb - negative_emb
axis_magnitude = ||axis_vector||  # L2 norm
axis_unit_vector = axis_vector / axis_magnitude

# 3. For each candidate concept:
candidate_emb = get_embedding(candidate_id)

# Vector from negative pole to candidate
candidate_vector = candidate_emb - negative_emb

# Project onto axis (dot product)
projection_scalar = candidate_vector · axis_unit_vector

# Normalize to [-1, +1] (0 = midpoint)
position = (projection_scalar / axis_magnitude) * 2 - 1

# Calculate orthogonal distance (how far off-axis)
projection_vector = projection_scalar * axis_unit_vector
orthogonal_vector = candidate_vector - projection_vector
axis_distance = ||orthogonal_vector||

# 4. Determine direction
if position > 0.3:
    direction = "positive"
elif position < -0.3:
    direction = "negative"
else:
    direction = "neutral"
```

**Output:**
- Position: -1 (negative pole) to +1 (positive pole), 0 = midpoint
- Axis distance: Orthogonal component (higher = more multi-dimensional)
- Direction: Categorical alignment

### Grounding Correlation

**Hypothesis:** Grounding should correlate with axis position

**Validation:**
```python
# For each projected concept:
positions = [p.position for p in projections]
groundings = [p.grounding for p in projections]

# Calculate Pearson correlation
r, p_value = pearsonr(positions, groundings)

# Interpret:
# r > 0.7: Strong correlation (good axis)
# r < 0.3: Weak correlation (weak axis or orthogonal concern)
```

**Example (from experiments):**
- Legacy Systems (-0.075 grounding) → position -0.124 (toward negative pole)
- Agile (+0.227 grounding) → position +0.194 (toward positive pole)
- Correlation: r = 0.85 (strong!)

### Caching Strategy

**Cache Keys:**
```python
# Axis definition
axis_key = f"polarity_axis:v1:{hash(positive_id)}:{hash(negative_id)}"
cached_axis = {
    "positive_pole": {...},
    "negative_pole": {...},
    "axis_unit_vector": [...],
    "magnitude": 1.0714,
    "created_at": "2025-11-29T..."
}
# TTL: 1 hour

# Individual projection
projection_key = f"projection:v1:{axis_id}:{concept_id}"
cached_projection = {
    "position": 0.194,
    "axis_distance": 1.0008,
    "direction": "positive",
    "grounding": 0.227,
    "created_at": "..."
}
# TTL: 30 minutes
```

**Invalidation:**
- On embedding regeneration: Clear all `projection:*:*:{concept_id}` keys
- On axis calculation error: Clear `axis:*` key and retry
- Manual: Allow `?force_refresh=true` parameter to bypass cache

## Implementation Phases

### Phase 1: Core Worker
- [ ] Refactor `polarity_axis_analysis.py` into `PolarityAxisWorker`
- [ ] Add to worker registry
- [ ] Unit tests for projection algorithm
- [ ] Integration test with real embeddings

### Phase 2: API Endpoints
- [ ] `POST /queries/polarity-axis` (analyze axis)
- [ ] `POST /queries/discover-polarity-axes` (auto-discover)
- [ ] `GET /queries/polarity-axis/{axis_id}/project/{concept_id}` (project concept)
- [ ] Pydantic models for request/response
- [ ] OpenAPI documentation

### Phase 3: Caching
- [ ] Redis caching layer
- [ ] Cache invalidation on embedding regen
- [ ] Cache hit rate metrics

### Phase 4: Documentation
- [ ] Update guides with polarity axis examples
- [ ] CLI integration (`kg polarity ...`)
- [ ] Video demo (optional)

### Phase 5: Interface Integration
- [ ] MCP server tools (`analyze_polarity_axis`, `discover_polarity_axes`)
- [ ] CLI commands (`kg polarity analyze`, `kg polarity discover`, `kg polarity project`)
- [ ] Web workstation "Polarity Axis Explorer" panel

## User Interface Specifications

### MCP Server Integration

**Tools:**
- `analyze_polarity_axis(positive_pole_query, negative_pole_query, auto_discover_candidates)`
- `discover_polarity_axes(relationship_types, max_results)`

**Output Format:** Markdown with emoji indicators, position visualization, grounding correlation insights

**Use Cases:**
- Claude asks "What are the key semantic dimensions in this knowledge base?"
- Discovers PREVENTS/CONTRADICTS axes automatically
- Projects concepts onto axes to understand positioning

### CLI Tool (kg)

**Commands:**
```bash
kg polarity analyze <positive> <negative>     # Analyze specific axis
kg polarity discover [--type TYPE]            # Auto-discover axes
kg polarity project <axis_id> <concept_id>    # Project concept
```

**Output:**
- **Table mode:** Formatted tables with position, direction, grounding
- **Visual mode:** ASCII spectrum showing concept positions
- **JSON mode:** Machine-readable output for scripting

### Web Workstation

**New Explorer Panel:** "Polarity Axis Explorer"

**Features:**
1. **Axis Discovery** - Browse PREVENTS/CONTRADICTS relationship axes
2. **Interactive Visualization** - Drag-and-drop concepts, color-coded by grounding
3. **Custom Axis Creator** - Search and select poles, auto-discover candidates
4. **Concept Integration** - "Polarity Analysis" tab shows where concept appears on known axes
5. **Export Options** - JSON, PNG, SVG for documentation

**Visual Design:**
- Color gradient along axis (configurable theme)
- Concept bubbles sized by grounding strength
- Interactive: hover for stats, click to navigate
- Real-time correlation metrics

**See full interface specifications in:** `experiments/semantic_gradients/IMPLEMENTATION_PLAN.md`

## Success Criteria

**Functional:**
- ✅ Polarity axis calculation produces stable results (±0.05 across runs)
- ✅ Grounding correlation r > 0.7 for PREVENTS/CONTRADICTS axes
- ✅ Direction accuracy >90% vs human spot checks

**Performance:**
- ✅ Axis calculation <5s for 20 candidates
- ✅ Cached projection <100ms
- ✅ Cache hit rate >80% for popular axes
- ✅ No performance regression on existing endpoints

**Adoption:**
- ✅ 10+ polarity axis analyses per week (within first month)
- ✅ User feedback positive (clear value, understandable results)
- ✅ Zero critical bugs or data corruption

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Expensive computation slows API | High | Medium | Background workers + caching |
| Results are unintuitive | Medium | Medium | Clear docs, examples, visual aids |
| Cache invalidation bugs | High | Low | Conservative TTL, manual refresh option |
| Grounding correlation weak | Medium | Low | Document when axes are weak, suggest alternatives |

## References

- **Experimental findings:** `experiments/semantic_gradients/findings-results.md`
- **Implementation guide:** `docs/guides/SEMANTIC_PATH_GRADIENTS.md`
- **Research papers:**
  - [Large Concept Models](https://arxiv.org/abs/2412.08821) - Meta AI, Dec 2024
  - [Path-Constrained Retrieval](https://arxiv.org/html/2511.18313)

## Decision Record

**Status:** Draft (awaiting team review)
**Proposed By:** System Architect
**Review Date:** TBD
**Approval Date:** TBD

---

**Next Steps:**
1. Team review of ADR
2. Finalize API design
3. Implement Phase 1 (worker)
4. Gather feedback from early testing
5. Iterate based on learnings
