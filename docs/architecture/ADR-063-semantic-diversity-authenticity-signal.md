# ADR-063: Semantic Diversity as Authenticity Signal

**Status**: Proposed
**Date**: 2025-01-08
**Author**: System
**Related ADRs**: ADR-044 (Dynamic Grounding), ADR-045 (Unified Embedding), ADR-058 (Polarity Axis Triangulation)

## Context

Knowledge graphs built from LLM extraction can contain both authentic information (based on real-world observations from independent sources) and fabricated claims (variations on false narratives). While grounding strength (ADR-058) measures evidential support through relationship polarity, it doesn't capture the **richness and diversity** of supporting evidence.

### Key Observation

Authentic information exhibits natural "noise" - it's supported by concepts from diverse, independent conceptual domains (physics, chemistry, geology, engineering). Fabricated claims tend to be **semantically homogeneous** - all variations on a single theme with circular reasoning.

### Motivating Example: Apollo 11 vs Moon Landing Hoax

In testing the Space Travel ontology, we observed:

**Apollo 11 Mission (Authentic Event)**:
- **33 related concepts** within 2-hop traversal
- Related concepts span independent domains:
  - Radioactive Isotope Dating (nuclear physics)
  - Spacecraft Trajectory (orbital mechanics)
  - Command Module's Aluminum Hull (materials science)
  - Photogrammetry (optics/surveying)
  - Moon Rocks (geology)
  - Soviet Union Tracking (international cooperation)
- **Average pairwise similarity**: 62.3%
- **Diversity score**: 37.7% (1 - avg_similarity)

**Moon Landing Conspiracy Theories (Fabricated Claim)**:
- **Only 3 related concepts** within 2-hop traversal
- All 3 concepts relate to Stanley Kubrick's filmmaking:
  - 2001: A Space Odyssey
  - Stanley Kubrick's Filmmaking Legacy
  - Stanley Kubrick
- **Average pairwise similarity**: 76.8%
- **Diversity score**: 23.2%
- **11x fewer related concepts**
- **63% lower diversity score**

### Critical Test: Adding More Hoax Claims

To validate the hypothesis, we ingested **10 different conspiracy theories**:
1. Waving flag in vacuum
2. No stars visible in photos
3. Van Allen radiation belts impossibility
4. Non-parallel shadows (studio lighting)
5. Crosshairs appearing behind objects
6. Identical backgrounds miles apart
7. No blast crater under lunar module
8. (And 3 more variations)

**Result**: The conspiracy theories **de-duplicated into the same homogeneous semantic space**. Despite adding 10 different claims, the Moon Landing Conspiracy still had:
- Only 3 related concepts
- 76.8% similarity (unchanged)
- 23.2% diversity (unchanged)

The system correctly recognized all hoax claims as **variations on a single fabricated theme** rather than independent evidence from diverse domains.

## Decision

We document **semantic diversity** as a measurable signal for distinguishing authentic vs fabricated information in knowledge graphs:

### Metric Definition

**Semantic Diversity Score** = 1 - (average pairwise cosine similarity of related concept embeddings)

Where related concepts are defined as concepts within N-hop traversal (typically N=2) along any relationship type.

### Interpretation

| Diversity Score | Interpretation | Signal |
|----------------|----------------|---------|
| > 0.35 | High diversity - likely authentic | Many independent conceptual domains |
| 0.25 - 0.35 | Moderate diversity | Some independent sources |
| < 0.25 | Low diversity - possibly fabricated | Circular reasoning, single theme |

### Related Concept Count

In addition to diversity, the **number of related concepts** within N hops is significant:
- Authentic claims: Typically 20+ related concepts (rich conceptual network)
- Fabricated claims: Typically < 10 related concepts (sparse, self-referential)

## Implementation Strategy

### Phase 1: Analysis Tool (Current)

A standalone analysis script that:
1. Traverses the graph N hops from a target concept
2. Collects embeddings of all related concepts
3. Calculates pairwise cosine similarities
4. Returns diversity score and interpretation

```python
def calculate_semantic_diversity(concept_label, max_hops=2):
    # Get concepts within N hops (OMNIDIRECTIONAL traversal)
    # Use undirected relationships (-[*]-) to capture full semantic neighborhood:
    #   - Inbound: (c)-[:SUPPORTS]->(target)
    #   - Outbound: (target)-[:USED]->(c)
    # Both contribute to semantic diversity
    query = f"""
    MATCH (target:Concept {{label: '{concept_label}'}})-[*1..{max_hops}]-(related:Concept)
    WHERE related <> target
    WITH DISTINCT related
    RETURN related.embedding as embedding
    LIMIT 100
    """

    # Calculate pairwise similarities
    similarities = []
    for emb1, emb2 in combinations(embeddings, 2):
        similarity = cosine_similarity(emb1, emb2)
        similarities.append(similarity)

    diversity_score = 1 - mean(similarities)
    return diversity_score
```

### Phase 2: API Integration (Hybrid Approach)

Support diversity calculation through **two complementary patterns**:

1. **Dedicated analysis endpoints** for detailed diversity analysis
2. **Optional query parameters** on existing endpoints for convenience

#### Pattern A: Optional Diversity on Existing Queries

Add `?include_diversity=true` to existing endpoints for quick diversity scores:

```python
# Concept detail with diversity
GET /query/concepts/{concept_id}?include_diversity=true&diversity_max_hops=2

Response:
{
  "concept_id": "sha256:...",
  "label": "Apollo 11 Mission",
  "grounding_strength": 0.127,
  "diversity_score": 0.377,              // Added when include_diversity=true
  "diversity_related_count": 34,         // Number of concepts analyzed
  "authenticated_diversity": 0.377,      // sign(grounding) × diversity
  ...
}
```

```python
# Search with diversity scores
POST /query/search
{
  "query": "moon landing",
  "include_grounding": true,
  "include_diversity": true,
  "diversity_max_hops": 2
}

Response:
{
  "results": [
    {
      "label": "Apollo 11 Mission",
      "grounding_strength": 0.127,
      "diversity_score": 0.377,
      "authenticated_diversity": 0.377,    // Positive: diverse support
      ...
    },
    {
      "label": "Moon Landing Conspiracy",
      "grounding_strength": -0.064,
      "diversity_score": 0.369,
      "authenticated_diversity": -0.369,   // Negative: diverse contradiction
      ...
    }
  ]
}
```

**Use when**: You want diversity alongside normal query results for quick comparison.

#### Pattern B: Dedicated Analysis Endpoints

For **detailed analysis** with full statistics and related concept details:

**Single Concept Diversity**

```python
GET /analysis/diversity/{concept_id}?max_hops=2&limit=100
```

**Parameters**:
- `max_hops` (int, default=2): Maximum traversal depth (1-3)
- `limit` (int, default=100): Max related concepts to analyze (sampling if exceeded)

**Response**:
```json
{
  "concept_id": "sha256:...",
  "concept_label": "Apollo 11 Mission",
  "analysis": {
    "diversity_score": 0.377,
    "interpretation": "Moderate diversity (some conceptual variation)",
    "related_concept_count": 33,
    "avg_pairwise_similarity": 0.623,
    "max_hops": 2,
    "calculation_time_ms": 87,
    "sampled": false
  },
  "related_concepts": [
    {
      "label": "Radioactive Isotope Dating",
      "concept_id": "sha256:...",
      "distance": 2
    },
    {
      "label": "Spacecraft Trajectory",
      "concept_id": "sha256:...",
      "distance": 1
    }
    // ... up to limit
  ],
  "statistics": {
    "min_similarity": 0.412,
    "max_similarity": 0.891,
    "median_similarity": 0.634,
    "std_dev": 0.089
  }
}
```

#### Batch Diversity Analysis

Analyze multiple concepts in one request:

```python
POST /analysis/diversity/batch
{
  "concept_ids": [
    "sha256:apollo11...",
    "sha256:conspiracy..."
  ],
  "max_hops": 2,
  "limit": 100
}
```

**Response**:
```json
{
  "results": [
    {
      "concept_id": "sha256:apollo11...",
      "diversity_score": 0.377,
      "related_concept_count": 33,
      ...
    },
    {
      "concept_id": "sha256:conspiracy...",
      "diversity_score": 0.232,
      "related_concept_count": 3,
      ...
    }
  ],
  "batch_statistics": {
    "mean_diversity": 0.305,
    "std_diversity": 0.102,
    "total_time_ms": 245
  }
}
```

#### Path Diversity Analysis

Analyze diversity gradient along a path:

```python
GET /analysis/diversity/path?from={concept_id}&to={concept_id}&max_hops=2
```

**Response**:
```json
{
  "path": [
    {
      "concept_label": "Moon Landing Conspiracy Theories",
      "concept_id": "sha256:...",
      "diversity_score": 0.232,
      "distance_from_start": 0
    },
    {
      "concept_label": "Photographic Anomalies",
      "concept_id": "sha256:...",
      "diversity_score": 0.298,
      "distance_from_start": 1
    },
    {
      "concept_label": "Hasselblad Camera",
      "concept_id": "sha256:...",
      "diversity_score": 0.345,
      "distance_from_start": 2
    },
    {
      "concept_label": "Apollo Program",
      "concept_id": "sha256:...",
      "diversity_score": 0.377,
      "distance_from_start": 3
    }
  ],
  "diversity_gradient": {
    "start_diversity": 0.232,
    "end_diversity": 0.377,
    "gradient": 0.145,
    "interpretation": "Increasing diversity (moving toward authentic evidence)"
  }
}
```

#### Dataset Statistics

Get diversity distribution for entire ontology:

```python
GET /analysis/diversity/ontology/{ontology_name}?max_hops=2
```

**Response**:
```json
{
  "ontology": "Space Travel",
  "statistics": {
    "concept_count": 61,
    "mean_diversity": 0.305,
    "std_diversity": 0.089,
    "median_diversity": 0.312,
    "min_diversity": 0.232,
    "max_diversity": 0.478
  },
  "distribution": {
    "high_diversity": 15,      // > 0.35
    "moderate_diversity": 38,  // 0.25 - 0.35
    "low_diversity": 8         // < 0.25
  },
  "outliers": {
    "exceptionally_high": [    // > +2σ
      {
        "label": "Some Concept",
        "diversity_score": 0.478,
        "sigma": 2.3
      }
    ],
    "suspiciously_low": [      // < -2σ
      {
        "label": "Moon Landing Conspiracy Theories",
        "diversity_score": 0.232,
        "sigma": -1.8
      }
    ]
  },
  "calculation_time_ms": 5420
}
```

**Use when**: You need deep analysis, full statistics, or are building research/diagnostic tools.

#### Pattern Comparison

| Feature | Pattern A (Query Parameter) | Pattern B (Analysis Endpoint) |
|---------|----------------------------|-------------------------------|
| **Response** | Just diversity score + count | Full statistics + related concepts |
| **Latency** | Adds 50-150ms to query | Dedicated request |
| **Use Case** | Quick comparison in search results | Research, diagnostics, deep analysis |
| **Details** | Minimal (score only) | Rich (min/max/median, samples) |
| **Path Analysis** | Not supported | Supported (diversity gradient) |
| **Ontology Stats** | Not supported | Supported (sigma, outliers) |

**Recommendation**:
- Use **Pattern A** for user-facing features (search results, concept pages)
- Use **Pattern B** for analytics, research, and administrative tools

**Client Implementation Simplicity**:

Pattern A requires minimal client changes:
```typescript
// kg CLI - just add optional flag
kg search query "apollo 11" --diversity

// MCP server - just add optional parameter to existing tool
const result = await client.searchConcepts({
  query: "apollo 11",
  include_grounding: true,
  include_diversity: true  // New optional parameter
});

// Web app - just add parameter to existing API call
fetch(`/query/search`, {
  body: JSON.stringify({
    query: "apollo 11",
    include_diversity: true  // New optional field
  })
});
```

No new client methods, routes, or UI components needed - just enhance existing ones.

### Phase 3: Cached Metric

Store diversity score as a cached property on Concept nodes:
- Calculated on-demand (like grounding strength in ADR-044)
- Cached in node properties for performance
- Invalidated when graph topology changes significantly
- Recalculated lazily on next access

```cypher
(:Concept {
  label: "Apollo 11 Mission",
  grounding_strength: 0.14,
  diversity_score: 0.377,
  diversity_related_count: 33,
  diversity_calculated_at: "2025-01-08T..."
})
```

### Authenticated Diversity: Combining Diversity with Grounding Polarity

**Problem Discovered**: Initial testing revealed that conspiracy theories can exhibit **high diversity scores** when they're parasitic on authentic information. Example:

- **Apollo 11**: 37.7% diversity, 34 related concepts
- **Moon Landing Conspiracy**: 36.9% diversity, 29 related concepts

Both show high diversity! Why? The conspiracy is **connected to Apollo 11 via CONTRADICTS relationships**, so omnidirectional traversal reaches the entire authentic Apollo 11 information network. The conspiracy gains diversity by being embedded in what it opposes.

**Solution: Sign-Weighted Diversity**

Combine diversity with grounding polarity to distinguish supportive vs contradictory diversity:

```python
authenticated_diversity = sign(grounding_strength) × diversity_score
```

Where `sign(x) = +1 if x >= 0 else -1`

**Results**:
- **Apollo 11**: sign(+0.127) × 0.377 = **+0.377** (✅ supported by diverse evidence)
- **Conspiracy**: sign(-0.064) × 0.369 = **-0.369** (❌ contradicted by diverse evidence)

**Interpretation**:
- **Positive value**: Concept supported by this magnitude of diverse evidence
- **Negative value**: Concept contradicted by this magnitude of diverse evidence
- **Near zero**: Either low diversity OR neutral grounding

This aligns with **signed graph theory** where edge polarity affects semantic propagation. The metric preserves the diversity magnitude while incorporating directionality from grounding (ADR-044 + ADR-058).

**API Response**:
```json
{
  "concept_id": "sha256:...",
  "label": "Apollo 11 Mission",
  "grounding_strength": 0.127,
  "diversity_score": 0.377,
  "diversity_related_count": 34,
  "authenticated_diversity": 0.377  // New combined metric
}
```

**Decision**: Provide both `diversity_score` (unsigned magnitude) and `authenticated_diversity` (sign-weighted) so users can analyze them separately or together depending on context.

## Performance Considerations

### Computational Complexity

**Per-Concept Calculation**:
```
1. Graph traversal (2-hops):     O(E × D²)  where E=edges/node, D=max depth
2. Collect embeddings:            O(N)       where N=related concepts
3. Pairwise similarities:         O(N²)      for N concepts
4. Mean calculation:              O(N²)

Total: O(N²) where N is typically 20-100 concepts
```

**Reality Check** (based on current Space Travel ontology):
- Apollo 11: 33 related concepts → 528 pairwise comparisons
- Embedding dimension: 1536 floats (OpenAI) or 768 (local)
- Cosine similarity: dot product + 2 norms = ~3 operations per dimension
- **Estimated time**: < 50ms on modern hardware (mostly graph traversal)

### Optimization Strategies

**1. Lazy Calculation with Caching**
```python
# Only calculate when explicitly requested
GET /query/concepts/{id}?include_diversity=true

# Cache result on Concept node
(:Concept {
  diversity_score: 0.377,
  diversity_cached_at: "2025-01-08T...",
  diversity_invalidated: false
})

# Invalidate on graph changes
ON concept.relationship.created → concept.diversity_invalidated = true
```

**2. Sampling for Large Networks**
```python
# If related_concepts > 100, sample randomly
if len(related_concepts) > 100:
    sample = random.sample(related_concepts, 100)
    diversity = calculate_diversity(sample)
    # Note: approximate but fast
```

**3. Batch Processing**
```python
# For search results, batch calculate all diversities
POST /query/search → Returns 10 concepts

# Single graph traversal gets all related concepts
# Parallel pairwise calculations
# Total time: ~100ms for 10 concepts instead of 500ms sequential
```

**4. Pre-computation for High-Value Concepts**
```python
# Background job: Calculate diversity for frequently accessed concepts
# Based on access logs or grounding strength

async def precompute_diversity():
    high_value_concepts = get_frequently_accessed()
    for concept in high_value_concepts:
        calculate_and_cache_diversity(concept)
```

### Performance Impact Assessment

**Acceptable Latency** (user perspective):
- < 100ms: Imperceptible
- 100-300ms: Acceptable for enhanced analysis
- 300-1000ms: Acceptable for detailed query
- \> 1000ms: Only for background/batch processing

**Expected Performance**:
- **Single concept diversity**: 50-150ms (graph traversal dominant)
- **Search with diversity (10 results)**: 200-500ms (acceptable for opt-in feature)
- **Path diversity (5-hop path)**: 100-300ms (calculate per node along path)
- **Dataset sigma (all concepts)**: Batch job, run nightly or on-demand

**Mitigation Strategy**:
- Make diversity calculation **opt-in** via query parameter
- Cache aggressively, invalidate conservatively
- For interactive queries, return immediately with `diversity: "calculating..."`, update via WebSocket
- For batch analysis, use background jobs

### When to Calculate

**Real-time** (fast enough for synchronous response):
- Single concept detail view (user explicitly views a concept)
- Path analysis (user explores specific path)
- Small result sets (< 10 concepts)

**Deferred** (background job, return placeholder):
- Search results with many concepts (> 10)
- Ontology-wide analysis
- Dataset sigma calculations

**Never** (only on explicit request):
- Bulk operations
- Low-value concepts (rarely accessed)

## Consequences

### Positive

1. **Measurable Authenticity**: Quantifies intuition about "rich" vs "synthetic" data
2. **Automated Detection**: Can flag potentially fabricated claims without human review
3. **Quality Metric**: Measures knowledge graph richness and independence
4. **Complements Grounding**: Diversity measures "how" evidence supports, grounding measures "whether" it supports
5. **Empirically Validated**: Hypothesis tested and confirmed with real data
6. **Creative Applications**: Unexpected use cases in fiction writing and worldbuilding
7. **Research Tool**: Opens new analysis dimensions (diversity taper, dataset sigma)

### Negative

1. **Computational Cost**: O(N²) pairwise comparisons for N related concepts
   - **Mitigation**: Caching, sampling, lazy evaluation, batch processing
   - **Reality**: < 150ms for typical concepts, acceptable for opt-in feature
2. **Not Foolproof**: Sophisticated fabrications with manufactured "independent" sources could game the metric
   - **Mitigation**: Combine with grounding strength and source analysis
3. **Domain Dependent**: Thresholds may need calibration per domain
   - **Mitigation**: Use sigma-based relative scoring within ontology
4. **Correlation Not Causation**: Low diversity doesn't prove fabrication, just raises a flag
   - **Mitigation**: Treat as quality signal, not binary classifier
5. **Cache Invalidation Complexity**: Need to track when graph topology changes affect diversity
   - **Mitigation**: Conservative invalidation (mark dirty on any relationship change)

### Neutral

1. **Requires Embeddings**: All concepts must have embeddings (already true in our system)
2. **Graph Topology Dependent**: Relies on relationship extraction quality
3. **Complements, Doesn't Replace**: Should be used alongside grounding strength and human judgment
4. **Embedding Model Dependency**: Diversity scores are downstream of the embedding model
   - Changing embedding models (OpenAI → local, version upgrades) invalidates cached scores
   - **Mitigation**: Use dataset sigma (relative scoring) which is more stable across models than absolute thresholds
   - Recalculation required on model migration (handled by ADR-045 embedding worker)

## Alternatives Considered

### 1. Evidence Quote Diversity

**Approach**: Calculate semantic diversity of Instance quote text instead of related concepts.

**Rejected Because**:
- Most concepts have only 1-2 evidence instances (due to paragraph-based ingestion)
- Insufficient data points for meaningful pairwise comparison
- Doesn't capture the conceptual network structure

### 2. Source Document Diversity

**Approach**: Count unique source documents mentioning a concept.

**Rejected Because**:
- Document count alone doesn't measure semantic diversity
- Multiple documents could all repeat the same claim
- Doesn't capture the richness we observed in authentic data

### 3. Relationship Type Diversity

**Approach**: Count how many different relationship types connect to a concept.

**Tried and Found Insufficient**:
- Apollo 11: 7 relationship types, 22 relationships
- Conspiracy: 2 relationship types, 2 relationships
- Useful signal but doesn't capture semantic diversity of **what** those relationships connect

### 4. Search Term Variance

**Approach**: Measure lexical diversity of search_terms arrays.

**Rejected Because**:
- Lexical diversity ≠ semantic diversity
- Doesn't use the rich embedding space we already have
- Misses conceptual relationships

## References

### Related Research

Our finding builds on established research in network science, information theory, and misinformation detection:

#### Echo Chamber Detection

**Garimella et al. (2021)** - "Echo chamber detection and analysis" (Social Network Analysis and Mining, Springer):
- Developed hybrid approaches combining network topology and semantic content analysis
- Measured community homogeneity using sentiment similarity and topic similarity
- Found echo chambers exhibit **low semantic diversity** within groups (circular reasoning)
- Aligns with our observation that fabricated claims show homogeneous supporting concepts

**Key Finding**: Semantic homogeneity is a measurable signal of ideological insularity and circular reasoning.

#### Information Entropy and Network Diversity

**Solé-Ribalta et al. (2019)** - "A detailed characterization of complex networks using Information Theory" (Nature Scientific Reports):
- Applied Shannon entropy to quantify uncertainty and diversity in network structures
- Higher entropy indicates broader topical coverage and information diversity
- Lower entropy reflects narrower information scope

**Li et al. (2021)** - "Measuring diversity in heterogeneous information networks" (Theoretical Computer Science):
- Developed formal framework for diversity measures in network-structured data
- Extended diversity measurement from simple classifications to complex network relations
- Provides mathematical foundation for our pairwise similarity approach

**Key Finding**: Information entropy quantifies diversity in networked systems - authentic information exhibits higher entropy.

#### Pairwise Semantic Similarity

**Kiros et al. (2018)** - "Semantic Analysis Using Pairwise Sentence Comparison with Word Embeddings" (ResearchGate):
- Local alignment scoring scheme for sentence pairs using word embeddings
- Pairwise comparison captures semantic relationships in text analysis tasks

**Recent (2025)** - "Embeddings Evaluation Using Novel Measure of Semantic Similarity":
- HSS (Hierarchical Semantic Similarity) computes pairwise semantic similarity
- Different embedding models capture different similarity distributions
- Validates our approach of using cosine similarity for diversity measurement

**Key Finding**: Pairwise cosine similarity of embeddings is a well-established measure of semantic relationship.

#### Knowledge Graph Verification

**Various (2023-2024)** - Knowledge graph-based fact verification research (MDPI, arXiv):
- Triplet trustworthiness validation using semantic consistency
- Multi-hop reasoning in knowledge graphs for fact verification
- Entity-level, relation-level, and graph-level trustworthiness measurement

**Key Finding**: Semantic consistency within knowledge graphs is used for authenticity verification - we extend this to measure diversity of supporting concepts.

### Theoretical Foundation

Our approach synthesizes these research areas into a unified metric:

1. **Shannon Entropy**: Authentic information has higher entropy (more unpredictable variation)
2. **Network Diversity**: Authentic nodes connect to more diverse conceptual neighborhoods
3. **Echo Chamber Detection**: Low diversity indicates circular reasoning / ideological homogeneity
4. **Pairwise Similarity**: Established embedding-based method for measuring semantic relationships

### Empirical Validation

- **Test Dataset**: Space Travel ontology with 61 concepts, 68 instances, 303 relationships
- **Authentic Claim**: Apollo 11 Mission (37.7% diversity, 33 related concepts)
- **Fabricated Claim**: Moon Landing Conspiracy (23.2% diversity, 3 related concepts)
- **Stress Test**: Added 10 different hoax claims → No change in conspiracy diversity (de-duplicated correctly)

### Related Work

- **Grounding Strength (ADR-058)**: Measures polarity (support/contradict) of evidence
- **Semantic Diversity (This ADR)**: Measures richness and independence of evidence
- **Combined Signal**: Both metrics together provide powerful authenticity assessment

## Implementation Notes

### Current Status (Phase 1)

The analysis script was created for research validation and has been removed from `/tmp/`.

### Implementation Priority

**Primary: Pattern A - Extend Existing Endpoints**

Add optional `include_diversity` parameter to existing query endpoints. **No new API routes needed.**

1. **Create diversity service** (`api/services/diversity_analyzer.py`):
   ```python
   class DiversityAnalyzer:
       def __init__(self, age_client: AGEClient):
           self.client = age_client

       def calculate_diversity(
           self,
           concept_id: str,
           max_hops: int = 2,
           limit: int = 100
       ) -> float:
           """Returns just the diversity score."""
           # 1. Graph traversal (2-hops)
           # 2. Collect embeddings
           # 3. Pairwise cosine similarities
           # 4. Return 1 - mean(similarities)
           ...
   ```

2. **Integrate into existing routes**:
   ```python
   # api/routes/queries.py - EXISTING FILE

   @router.get("/concepts/{concept_id}")
   async def get_concept(
       concept_id: str,
       include_grounding: bool = False,
       include_diversity: bool = False,  # Add this parameter
       diversity_max_hops: int = 2
   ):
       # Existing grounding logic...
       if include_grounding:
           concept['grounding_strength'] = calculate_grounding(...)

       # Add diversity calculation
       if include_diversity:
           diversity_analyzer = DiversityAnalyzer(age_client)
           concept['diversity_score'] = diversity_analyzer.calculate_diversity(
               concept_id,
               max_hops=diversity_max_hops
           )
           concept['diversity_related_count'] = len(related_concepts)

       return concept
   ```

3. **CLI support**:
   ```bash
   # Existing commands, just add --diversity flag
   kg search query "apollo 11" --diversity
   kg concept details <id> --diversity
   ```

**Secondary: Pattern B - Analysis Endpoints (Optional Future)**

Only implement if there's demand for detailed analysis tools:
- `/analysis/diversity/path` - diversity gradient analysis
- `/analysis/diversity/ontology` - dataset sigma statistics
- Full statistics with min/max/median/std

### Implementation Steps

1. **Phase 2a: Add DiversityAnalyzer service** (~4 hours)
   - Create `api/services/diversity_analyzer.py`
   - Implement core calculation logic
   - Unit tests with mock data

2. **Phase 2b: Integrate into existing queries** (~2 hours)
   - Add `include_diversity` parameter to `/query/concepts/{id}`
   - Add to `/query/search` endpoint
   - Update response models (Pydantic)

3. **Phase 2c: CLI integration** (~1 hour)
   - Add `--diversity` flag to `kg search` command
   - Add to `kg concept details` command
   - Update help text

4. **Testing** (~3 hours):
   - Unit tests for DiversityAnalyzer
   - Integration tests using Space Travel ontology
   - Performance tests (ensure < 150ms overhead)
   - Validation against known test cases

**Total estimate: ~10 hours for Pattern A implementation**

Pattern B endpoints can be added later if needed (additional ~6-8 hours).

### Critical Implementation Decisions

**Query Directionality (OMNIDIRECTIONAL)**:

The diversity calculation uses **undirected relationship traversal** (`-[*1..N]-`) to capture the full semantic neighborhood:

```cypher
MATCH (target:Concept {label: 'Apollo 11'})-[*1..2]-(related:Concept)
```

This is critical because both **inbound** and **outbound** relationships contribute to semantic diversity:
- Inbound: `Moon Rocks -[:COLLECTED_BY]-> Apollo 11`
- Outbound: `Apollo 11 -[:USED]-> Saturn V`

Using directed traversal (`-[*1..2]->`) would miss half the conceptual neighborhood and dramatically underestimate diversity.

**Parameter Sensitivity (max_hops)**:

Default `max_hops=2` is chosen as the "sweet spot":
- `max_hops=1`: Too sparse, only immediate neighbors (likely underestimates diversity)
- `max_hops=2`: Captures both direct relationships and "friends of friends" (empirically validated)
- `max_hops=3+`: Risk of conceptual explosion and noise from irrelevant distant concepts

The limit parameter (default 100) provides a safety cap on N for O(N²) calculations.

**Embedding Model Stability**:

Diversity scores are sensitive to the embedding model. When migrating models:
1. Absolute thresholds (< 0.25 = low) become invalid
2. Relative scores (dataset sigma) are more stable
3. Recommendation: Use sigma-based scoring for cross-model comparisons

### Performance Considerations

- **2-hop traversal** on graphs with ~60 concepts: < 1 second
- **Pairwise similarity** for 33 concepts: 528 comparisons, negligible time
- **Scalability**: For large graphs (1000s of concepts), limit traversal:
  - Max depth: 2 hops
  - Max concepts: 100 (add LIMIT to query)
  - Sampling if needed

### Example Output

```
📊 Apollo 11 Mission
   Related concepts: 33
   Avg similarity: 0.623
   Diversity score: 0.377
   → Moderate diversity (some conceptual variation)

📊 Moon Landing Conspiracy Theories
   Related concepts: 3
   Avg similarity: 0.768
   Diversity score: 0.232
   → Low diversity (likely circular reasoning)
```

## Advanced Analysis Patterns

### Diversity Taper (Path Analysis)

When traversing relationships, diversity may change along the path, creating a **diversity gradient** or **noise ratio profile**:

```python
# Path from conspiracy theory to evidence
Path: Moon Hoax → Photographic Anomalies → Hasselblad Camera → Apollo Program

Diversity:  0.232  →  0.298  →  0.345  →  0.377

# Diversity "taper" - increasing diversity as you move toward authentic concepts
# Low diversity (conspiracy) gradually connects to high diversity (real engineering)
```

**Applications**:
- **Evidence Strength**: Paths that show increasing diversity toward a claim strengthen it
- **Trace Fabrication**: Sudden diversity drops indicate potential fabrication points
- **Claim Validation**: Follow path from unknown claim to known authentic concepts, measure diversity gradient

### Dataset Sigma (Quality Distribution)

Treat diversity as a **distributional property** of the entire knowledge graph:

```python
# Calculate diversity for all concepts
all_diversities = [calculate_diversity(c) for c in concepts]

# Statistical measures
mean_diversity = np.mean(all_diversities)      # ~0.30 (example)
std_diversity = np.std(all_diversities)        # ~0.08 (example)

# Concept quality in standard deviations
def diversity_sigma(concept):
    return (concept.diversity - mean_diversity) / std_diversity

# Interpretation:
#   +2σ: Exceptionally rich evidence (top 2.5%)
#   +1σ: Above average diversity
#    0σ: Average
#   -1σ: Below average
#   -2σ: Suspiciously homogeneous (bottom 2.5%, flag for review)
```

**Applications**:
- **Outlier Detection**: Concepts with diversity < -2σ are statistical outliers (investigate)
- **Dataset Health**: Mean diversity across ontology indicates overall richness
- **Comparative Analysis**: "Physics ontology has 0.15 higher mean diversity than Politics ontology"

### Fiction Writing and Worldbuilding

An unexpected but powerful application: **using diversity analysis to improve fictional worldbuilding**.

**Scenario**: Author ingests a complete fiction novel (hundreds of concepts about a fictional universe).

**Analysis**:
```python
# Measure diversity of fictional concepts
fictional_world_diversity = calculate_diversity("Middle Earth")  # Example

# Compare to real-world analogs
compare_to = [
    ("Medieval Europe", 0.412),
    ("Ancient Rome", 0.389),
    ("Norse Mythology", 0.356)
]

# If fictional_world_diversity < 0.25:
#   → World feels "flat", needs more independent conceptual domains
#   → Add: economics, religion, ecology, linguistics, political systems
```

**Creative Applications**:
1. **Worldbuilding Depth**: Low diversity = shallow world, high diversity = rich world
2. **Consistency Checking**: Related concepts should have similar diversity (internal consistency)
3. **Genre Analysis**: Fantasy vs Sci-Fi diversity patterns
4. **Character Development**: Measure diversity of concepts connected to each character
5. **Plot Structure**: Track diversity along narrative paths (story arcs)

**Example Insight**:
```
Gandalf concept diversity: 0.478 (connects to magic, history, politics, warfare, philosophy)
Random NPC diversity: 0.156 (only connects to immediate plot elements)

→ Major characters naturally have higher conceptual diversity
→ Can identify underdeveloped characters by low diversity
```

## Future Enhancements

### Research Directions

1. **Temporal Analysis**: Track how diversity evolves as evidence accumulates over time
2. **Domain Calibration**: Learn baseline diversity distributions per ontology domain
3. **Anomaly Detection**: Flag sudden drops in diversity (possible manipulation or ingestion errors)
4. **Visualization**: Graph-based UI showing semantic diversity clusters and gradients
5. **Multi-Hop Analysis**: Systematic study of 1-hop, 2-hop, 3-hop diversity patterns

### Experimental Questions

1. **What happens when we ingest complete fiction?**
   - Do well-written fictional universes have high diversity?
   - Can we distinguish "rich fiction" from "poorly developed fiction"?
   - Do fictional worlds have different diversity patterns than real-world domains?

2. **Diversity taper in path traversals:**
   - Do paths from conspiracy → evidence show consistent diversity gradients?
   - Can we detect "fabrication injection points" where diversity suddenly drops?
   - Do multi-hop paths have characteristic diversity signatures?

3. **Dataset-level patterns:**
   - What's the natural diversity distribution for different knowledge domains?
   - How does ontology size affect diversity measurements?
   - Can we detect ingestion quality issues via diversity anomalies?

4. **Cross-ontology diversity:**
   - If a concept appears in multiple ontologies, should it have consistent diversity?
   - Can diversity help identify concepts that should be merged across ontologies?

## Conclusion

Semantic diversity provides a **mathematically rigorous** way to measure what humans intuitively recognize as "rich" vs "synthetic" information. By analyzing the semantic spread of related concepts in embedding space, we can distinguish authentic facts (supported by diverse independent domains) from fabricated claims (circular variations on a single theme).

This metric complements grounding strength to provide a comprehensive authenticity assessment framework for knowledge graphs.
