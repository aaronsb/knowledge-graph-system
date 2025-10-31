# ADR-052 Enhancement: Grounding-Aware Vocabulary Reclassification

**Status:** Proposed
**Date:** 2025-10-31
**Related:** ADR-044 (Grounding), ADR-047 (Category Classification), ADR-052 (Expansion-Consolidation Cycle)

## Context

Current `kg vocab refresh-categories` uses **mechanistic classification** - pure embedding similarity to hard-coded category prototypes. This approach:
- ✅ Is fast and stateless (~50-100ms)
- ✅ Provides consistent initial categorization
- ❌ Doesn't consider how vocabulary is actually used in the graph
- ❌ Cannot detect when categories drift from actual usage patterns
- ❌ Misses opportunities to validate categorization against empirical evidence

ADR-044 provides `grounding_strength` (0.0-1.0) for each concept, measuring Bayesian support vs contradiction. This metric is already calculated and stored on :Concept nodes. We can leverage this existing infrastructure to refine vocabulary categorization based on empirical usage patterns.

### Problem: Static Classification vs Dynamic Usage

**Example Mismatch:**
- Vocabulary type `CONTRADICTS` mechanistically classified as `logical_truth` (via embedding similarity)
- In practice, this relationship connects concepts with average grounding of 0.12 (highly refuted)
- The mechanistic category suggests "well-established truth relationships"
- The empirical usage suggests "relationships between contradictory/refuted concepts"
- **Optimization opportunity:** Detect this mismatch and flag for review or reclassification

### Available Data

ADR-044 already calculates and stores grounding for all concepts. We can query:

```cypher
MATCH (source:Concept)-[r:CONTRADICTS]->(target:Concept)
RETURN avg(source.grounding_strength + target.grounding_strength) / 2 as avg_grounding
// Result: 0.12 (contradictory usage pattern)
```

This reveals empirical usage patterns without additional computational cost for metric generation.

## Vocabulary Classification Architecture

### The State Machine

Vocabulary types flow through a one-way state machine that prevents reclassification loops:

```
LLM Extraction → llm_generated → Mechanistic Classification → computed → Grounding Validation
    (ingestion)     (initial)       (kg vocab refresh)        (final)      (quality check)
```

**State Transitions:**

1. **Initial State: `llm_generated`**
   - Set during ingestion when LLM discovers new relationship type
   - Category temporarily set to `"llm_generated"`
   - Embedding generated immediately for future matching
   - Example: `add_edge_type(type="ENHANCES", category="llm_generated")`

2. **Mechanistic Classification: `llm_generated` → `computed`**
   - `kg vocab refresh-categories` computes cosine similarity to seed types
   - Assigns best-matching category from 11 protected categories
   - Updates: `category_source = 'computed'`
   - **One-way transition:** Never reverts to `llm_generated`

3. **Empirical Validation: `computed` (read-only check)**
   - Proposed enhancement: Query grounding patterns from actual graph usage
   - Flag mismatches between mechanistic category and empirical role
   - **Non-destructive:** Does not change category or state
   - Provides evidence for curator review, does not auto-reclassify

### The Bounded Exploration Model

**Components:**

- **c** = 11 protected categories (causation, composition, logical, evidential, semantic, temporal, dependency, derivation, operation, interaction, modification)
- **a** = 30 protected seed types distributed across categories
- **b** = LLM-generated types (unbounded, emergent)

**Static Dictionary (Curator-Controlled):**

```python
CATEGORY_SEEDS = {
    'causation': ['CAUSES', 'ENABLES', 'PREVENTS', 'INFLUENCES', 'RESULTS_FROM'],
    'composition': ['PART_OF', 'CONTAINS', 'COMPOSED_OF', 'SUBSET_OF', 'INSTANCE_OF'],
    'logical': ['IMPLIES', 'CONTRADICTS', 'PRESUPPOSES', 'EQUIVALENT_TO'],
    # ... 11 categories, 30 seed types total
}
```

**Classification Algorithm:**

```python
# For each LLM-generated type
for category, seed_types in CATEGORY_SEEDS.items():
    similarities = []
    for seed in seed_types:
        similarity = cosine_similarity(type_embedding, seed_embedding)
        similarities.append(similarity)

    # Satisficing: max similarity (not mean)
    category_scores[category] = max(similarities)

# Assign to best match
best_category = max(category_scores, key=category_scores.get)
```

**Semantic Coverage Formula:**

```
Total Semantic Space = c × (a + b)

Where:
  c = 11 categories (bounded, curator-controlled dimensionality)
  a = 30 seed types (bounded, curator-controlled initial coverage)
  b = LLM-generated types (unbounded, emergent expansion)

Initial space:  a × c = 30 types × 11 categories = 330 "semantic coordinates"
Exploration:    b types discovered during ingestion (unbounded)
Organization:   Each b type maps to exactly one c category (via cosine similarity)
Total coverage: Sum of types per category across all c categories
```

### Why This Works

**1. Bounded Initial Space (Curator Control)**
- Protected categories (c=11) define semantic dimensions
- Protected seed types (a=30) provide grounding for each dimension
- Changes require manual updates to `CATEGORY_SEEDS` constant
- Prevents category proliferation

**2. Emergent Expansion (LLM Discovery)**
- LLM freely generates new relationship types (b) during ingestion
- No artificial constraints on vocabulary during extraction
- Each discovered type gets embedding for similarity matching
- Supports Sutton's Bitter Lesson: general methods > hand-coded vocabulary

**3. One-Way Classification (No Loops)**
- State transition: `llm_generated` → `computed` (irreversible)
- Prevents infinite reclassification cycles
- Default `refresh-categories` behavior only processes `computed` types (with `--computed-only` flag)
- Re-running refresh updates confidence/scores but not state machine position

**4. Empirical Validation Through Grounding (Quality Check)**
- Grounding validation operates on `computed` types only
- Cross-validates mechanistic category against actual usage patterns
- Flags mismatches for curator review
- Does **not** auto-reclassify (preserves one-way property)
- Provides empirical evidence to inform manual decisions

### Integration Point

This enhancement adds empirical validation **after** mechanistic classification completes:

```
Phase 1 (Existing): llm_generated → computed
  - Cosine similarity to seed types
  - Assign best-matching category
  - Set category_source = 'computed'

Phase 2 (Proposed): computed → grounding validation
  - Query average grounding for edge type
  - Classify empirical semantic role
  - Compare with mechanistic category
  - Flag mismatches (non-destructive)
```

The one-way state machine ensures grounding validation cannot trigger reclassification loops. It provides quality monitoring without disrupting the core classification workflow.

## Decision

Add a second phase to vocabulary refresh workflow that uses grounding metrics to refine category assignments:

### Two-Phase Classification

**Phase 1: Mechanistic Classification** (current, keep as-is)
- Uses cosine similarity to category seed embeddings
- Fast, stateless, embedding-based (~50-100ms)
- Assigns initial category based on semantic similarity
- Works for new vocabulary types with no usage history

**Phase 2: Empirical Validation** (new refinement phase)
- Query average grounding for each vocabulary type from actual graph usage
- Classify empirical semantic role based on grounding patterns:
  - `AFFIRMATIVE` (>0.80): Used between well-supported concepts
  - `CONTESTED` (0.40-0.80): Used between concepts with evolving evidence
  - `HISTORICAL` (0.20-0.40): Used between outdated/deprecated concepts
  - `CONTRADICTORY` (<0.20): Used between refuted/error concepts
- Cross-validate: Flag for review if grounding contradicts mechanistic category
- Store grounding metrics alongside category assignment for quality monitoring

### Implementation Strategy

#### 1. Query Average Grounding Per Edge Type

```cypher
MATCH (source:Concept)-[r]->(target:Concept)
WHERE source.grounding_strength IS NOT NULL
  AND target.grounding_strength IS NOT NULL
RETURN type(r) as edge_type,
       avg((source.grounding_strength + target.grounding_strength) / 2) as avg_grounding,
       stddev((source.grounding_strength + target.grounding_strength) / 2) as grounding_stddev,
       count(r) as edge_count
```

**Cost:** O(edges) - single graph traversal for all types
**Performance:** ~100-500ms for thousands of edges

#### 2. Semantic Role Classification

```python
def classify_semantic_role(avg_grounding: float) -> str:
    """
    Classify vocabulary by typical grounding of connected concepts.
    All roles are VALUABLE - used for enhanced reasoning, not pruning.
    """
    if avg_grounding > 0.80:
        return "AFFIRMATIVE"    # Well-supported knowledge
    elif avg_grounding > 0.40:
        return "CONTESTED"      # Evolving understanding
    elif avg_grounding > 0.20:
        return "HISTORICAL"     # Past states, outdated knowledge
    else:
        return "CONTRADICTORY"  # Refuted concepts, errors
```

#### 3. Cross-Validation with Mechanistic Category

Some categories should correlate with specific grounding roles:

| Category | Expected Grounding Role | Flag if Mismatch |
|----------|------------------------|------------------|
| `logical_truth` | AFFIRMATIVE | Yes (should be well-supported) |
| `evidential` | AFFIRMATIVE/CONTESTED | Maybe (depends on evidence quality) |
| `causal` | Any | No (causation can be affirmed or refuted) |
| `temporal` | Any | No (describes relationships, not truth) |

**Detection:** Flag vocabulary where mechanistic category strongly implies grounding role but actual usage differs.

#### 4. Database Schema Extensions

Add to `kg_api.relationship_vocabulary`:

```sql
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN avg_grounding FLOAT,
ADD COLUMN grounding_stddev FLOAT,
ADD COLUMN grounding_role VARCHAR(20),  -- AFFIRMATIVE/CONTESTED/HISTORICAL/CONTRADICTORY
ADD COLUMN grounding_category_mismatch BOOLEAN DEFAULT FALSE,
ADD COLUMN grounding_last_calculated TIMESTAMP;
```

Add to `:VocabType` graph nodes:

```cypher
// Properties to add
v.avg_grounding = 0.75
v.grounding_stddev = 0.15
v.grounding_role = "CONTESTED"
v.grounding_category_mismatch = false
```

#### 5. Enhanced `kg vocab refresh-categories` Workflow

```bash
kg vocab refresh-categories --with-grounding
```

Workflow:
1. **Phase 1 (Mechanistic Classification):**
   - Calculate embedding similarity to category seeds
   - Assign initial category based on semantic similarity

2. **Phase 2 (Empirical Validation):**
   - Query average grounding for all edge types (single Cypher query, ~100-500ms)
   - Classify empirical semantic role based on grounding patterns
   - Cross-validate: Detect category-role mismatches
   - Store grounding metrics for quality monitoring

3. **Output:**
   - Show both mechanistic category AND empirical role
   - Flag mismatches for curator review
   - Statistics on grounding distribution across categories

**Example Output:**

```
Refreshed 197 vocabulary types with grounding analysis

Category-Role Distribution:
  causal (AFFIRMATIVE):      18 types  [avg grounding: 0.82]
  causal (CONTESTED):        12 types  [avg grounding: 0.55]
  logical_truth (AFFIRMATIVE): 8 types  [avg grounding: 0.91]
  evidential (CONTESTED):     6 types  [avg grounding: 0.48]

Flagged Mismatches (4):
  ⚠ CONTRADICTS (logical_truth) - Expected AFFIRMATIVE, got CONTRADICTORY (avg: 0.12)
      Reason: This relationship mostly connects refuted claims
      Suggestion: Reclassify to 'evidential' or review usage
```

## Computational Feasibility

### Performance Analysis

**Phase 1 (Mechanistic):**
- ~200 types × 8 categories × 1 cosine calc = ~1600 ops
- Cost: ~50-100ms

**Phase 2 (Grounding-Aware):**
- Single Cypher query: `MATCH (s:Concept)-[r]->(t:Concept) RETURN type(r), avg(grounding)...`
- Traverses all edges once: O(edges)
- Cost: ~100-500ms for 1000-10000 edges

**Total:** ~150-600ms for complete refresh with grounding analysis

**Optimization:** Can be run asynchronously as scheduled job (ADR-050)

### Memory Requirements

- Grounding already calculated and stored on :Concept nodes (ADR-044)
- No need to recalculate grounding - just average existing values
- Minimal memory overhead

### Scalability

| Graph Size | Edges | Phase 2 Cost | Total Refresh |
|-----------|-------|-------------|---------------|
| Small | 1K | ~100ms | ~200ms |
| Medium | 10K | ~300ms | ~400ms |
| Large | 100K | ~1.5s | ~1.6s |
| Very Large | 1M+ | ~15s | ~15s |

**Acceptable:** Even for very large graphs, ~15s refresh is reasonable for periodic maintenance

## Consequences

### Positive

1. **Empirical Validation**
   - Categories validated against actual usage, not just embedding similarity
   - Detect when vocabulary is used differently than initially classified
   - Cross-validate mechanistic predictions with empirical observations

2. **Quality Monitoring**
   - Detect mismatches between category semantics and actual usage
   - Flag vocabulary that might be misnamed or misclassified
   - Alert to category drift over time as usage patterns evolve

3. **Enhanced Reasoning Capabilities**
   - Know which relationships describe well-supported vs refuted knowledge
   - Dialectical reasoning requires full spectrum of grounding roles
   - Enable queries like "show me causal relationships between contested concepts"

4. **Zero Marginal Cost**
   - Leverages existing grounding infrastructure (ADR-044)
   - No need to compute new metrics - just aggregate existing data
   - Single O(edges) query provides data for all vocabulary types

5. **Actionable Insights**
   - Provides curator with concrete evidence for reclassification decisions
   - Reduces manual review burden via automated mismatch detection
   - Suggests specific improvements based on empirical patterns

### Negative

1. **Computational Cost**
   - Adds ~100-500ms to refresh-categories operation
   - May be too slow for real-time classification

2. **Complexity**
   - Adds another dimension to vocabulary management
   - Requires understanding both embeddings and grounding

3. **Cold Start Problem**
   - New vocabulary types have no edges yet, so no grounding data
   - Falls back to mechanistic classification only

4. **Dependency on ADR-044**
   - Requires grounding_strength to be calculated and up-to-date
   - If grounding disabled, this feature unavailable

### Neutral

1. **Optional Feature**
   - Can be enabled via flag: `--with-grounding`
   - Doesn't change default behavior

2. **Storage Requirements**
   - Adds 4-5 columns to vocabulary table
   - Negligible space impact (~KB per 200 types)

## Implementation Plan

### Phase 1: Core Infrastructure
- [ ] Add database columns for grounding metrics
- [ ] Create `calculate_grounding_metrics()` method
- [ ] Add grounding role classification logic

### Phase 2: Refresh Integration
- [ ] Add `--with-grounding` flag to `kg vocab refresh-categories`
- [ ] Integrate grounding query into refresh workflow
- [ ] Store grounding metrics alongside category

### Phase 3: Mismatch Detection
- [ ] Define category-role expectations
- [ ] Implement mismatch detection
- [ ] Add review workflow for flagged types

### Phase 4: Scheduled Automation
- [ ] Integrate with ADR-050 scheduled jobs
- [ ] Weekly grounding refresh as maintenance task

## Alternatives Considered

### 1. Use LLM to Reclassify Based on Usage Examples
**Pros:** More sophisticated reasoning
**Cons:** Expensive (~$0.01 per type), slow (2-5s per type), requires LLM access
**Rejected:** Grounding-based approach is faster and cheaper

### 2. Manual Review Only
**Pros:** No automation complexity
**Cons:** Doesn't scale, requires curator time
**Rejected:** Goal is to reduce manual curation burden

### 3. Ignore Grounding, Use Only Embeddings
**Pros:** Simpler, faster
**Cons:** Misses empirical usage patterns, less accurate over time
**Rejected:** Grounding provides valuable empirical validation

## Future Enhancements

### 1. Time-Series Grounding Analysis
Track how grounding evolves over time:
- Vocabulary that becomes more contested
- Concepts that shift from supported to refuted

### 2. Category Drift Detection
Alert when category assignment becomes stale:
- Grounding role changes significantly
- Suggests periodic re-categorization

### 3. Automatic Category Creation
When grounding reveals a cluster of types with unique role:
- Propose new category based on grounding patterns
- Example: "refuted_causal" for low-grounding causal relationships

## Pedagogical Note: The Sleep Cycle Analogy

While this enhancement is primarily an optimization technique (empirical validation of mechanistic classification), it can be helpfully understood through the analogy of **sleep-based memory consolidation**:

### Two-Phase Consolidation Pattern

**Phase 1: Deep Sleep (NREM)** → Pruning unused vocabulary
- Implemented in ADR-052 base
- Removes vocabulary types with `edge_count = 0`
- Analogous to: Synaptic homeostasis during deep sleep (removal of unused connections)

**Phase 2: REM Sleep** → Grounding-aware reclassification
- This enhancement
- Tests vocabulary against empirical usage (grounding patterns)
- Refines categories based on actual experience
- Analogous to: Active memory rehearsal during REM sleep (strengthening coherent patterns, detecting inconsistencies)

### Why This Analogy Works

1. **Two-phase optimization:** Both systems use sequential phases for different optimization goals
2. **Empirical testing:** Both validate patterns against observed data (dream rehearsal vs grounding metrics)
3. **Quality improvement:** Both improve accuracy by detecting and correcting misalignments
4. **Natural sequencing:** Pruning first (remove noise) then refinement (improve signal)

However, the analogy should not drive design decisions - the technical optimization benefits are the primary justification. The biological parallel is useful for explaining the pattern to users and developers.

## References

**Technical:**
- ADR-044: Probabilistic Truth Convergence (grounding_strength metric)
- ADR-047: Probabilistic Vocabulary Categorization (current mechanistic approach)
- ADR-052: Vocabulary Expansion-Consolidation Cycle (consolidation/pruning base)
- Shannon (1948): "A Mathematical Theory of Communication" - noise carries information
- Hegel (1807): "Phenomenology of Spirit" - dialectical reasoning

**Pedagogical:**
- Walker & Stickgold (2006): "Sleep, Memory, and Plasticity" - REM consolidation research
- Tononi & Cirelli (2014): "Sleep and the Price of Plasticity" - synaptic homeostasis hypothesis

---

**Last Updated:** 2025-10-31
