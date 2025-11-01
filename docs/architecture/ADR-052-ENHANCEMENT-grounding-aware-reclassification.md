# ADR-052 Enhancement: Grounding-Aware Vocabulary Classification

**Status:** Proposed
**Date:** 2025-10-31
**Related:** ADR-044 (Grounding), ADR-047 (Mechanistic Classification), ADR-052 (Consolidation Cycle)

## Context

Current `kg vocab refresh-categories` uses **mechanistic classification** - embedding similarity to category seed types. While fast and consistent, this approach:
- ❌ Doesn't consider how vocabulary is actually used in the graph
- ❌ Cannot detect when edge semantics drift from actual usage patterns
- ❌ Provides no empirical validation of categorization decisions

ADR-044 provides `grounding_strength` (0.0-1.0) on concepts, measuring Bayesian support vs contradiction. This enhancement leverages existing grounding infrastructure to add empirical validation of vocabulary classification.

### Problem: Static Classification vs Dynamic Usage

**Example Mismatch:**
- Edge type `IMPLIES` mechanistically categorized as `logical` (via embedding similarity)
- But connects concepts with average grounding of 0.55 (contested range)
- Name suggests: logical, established truth relationships
- Usage shows: hypothetical or evolving logical connections

**Opportunity:** Cross-validate mechanistic category against empirical usage patterns.

## Vocabulary Classification Architecture

### The State Machine

Vocabulary flows through a one-way state machine:

```
LLM Extraction → llm_generated → Mechanistic Classification → computed → Grounding Validation
    (ingestion)     (initial)       (kg vocab refresh)        (final)      (quality check)
```

**State Transitions:**

1. **Initial:** LLM discovers new type during ingestion → `category = "llm_generated"`
2. **Classification:** `kg vocab refresh-categories` assigns category via cosine similarity → `category_source = "computed"`
3. **Validation:** Grounding check validates classification (read-only, non-destructive)

**One-way property:** `llm_generated` → `computed` never reverses, preventing reclassification loops.

### The Bounded Exploration Model

**Components:**
- **c** = 11 protected categories (causation, composition, logical, evidential, semantic, temporal, dependency, derivation, operation, interaction, modification)
- **a** = 30 protected seed types (curator-controlled via `CATEGORY_SEEDS` constant)
- **b** = LLM-generated types (unbounded, emergent during ingestion)

**Formula:**
```
Total Semantic Space = c × (a + b)

Where:
  c = bounded dimensionality (11 categories)
  a = bounded initial coverage (30 seed types)
  b = unbounded emergent expansion (LLM-discovered types)
```

**Why This Works:**
1. **Bounded initial space:** Curator controls c and a (prevents category proliferation)
2. **Emergent expansion:** LLM freely generates b (supports general methods over hand-coding)
3. **One-way classification:** State transition prevents infinite loops
4. **Empirical validation:** Grounding check operates on `computed` state only (non-destructive)

## Decision

Add empirical validation to vocabulary classification using **dual-signal approach** with role distribution analogous to ADR-044's grounding formula.

### Dual-Signal Classification

**Signal 1: Semantic (What the word means)**

One-time setup - generate role prototype embeddings:

```python
ROLE_PROTOTYPES = {
    'AFFIRMATIVE': embedding("well-supported, validated, established, confirmed, proven"),
    'CONTESTED': embedding("debated, uncertain, evolving, disputed, questioned"),
    'HISTORICAL': embedding("outdated, deprecated, superseded, obsolete, replaced"),
    'CONTRADICTORY': embedding("refuted, disproven, contradicted, falsified, rejected")
}
# Store in database, generate once, use forever
```

Per-type classification:

```python
semantic_scores = {}
for role, prototype in ROLE_PROTOTYPES.items():
    semantic_scores[role] = cosine_similarity(edge_embedding, prototype)

semantic_role = max(semantic_scores, key=semantic_scores.get)
semantic_confidence = semantic_scores[semantic_role]
```

**Signal 2: Empirical (How it's used)**

Query grounding distribution for edge type (analogous to ADR-044's `support_weight / total_weight`):

```cypher
MATCH (s:Concept)-[r:IMPLIES]->(t:Concept)
WHERE s.grounding_strength IS NOT NULL AND t.grounding_strength IS NOT NULL
WITH (s.grounding_strength + t.grounding_strength) / 2 as avg_grounding

WITH count(CASE WHEN avg_grounding > 0.80 THEN 1 END) as affirmative_count,
     count(CASE WHEN avg_grounding BETWEEN 0.40 AND 0.80 THEN 1 END) as contested_count,
     count(CASE WHEN avg_grounding BETWEEN 0.20 AND 0.40 THEN 1 END) as historical_count,
     count(CASE WHEN avg_grounding < 0.20 THEN 1 END) as contradictory_count,
     count(*) as total_count

RETURN {
  'AFFIRMATIVE': affirmative_count / total_count,
  'CONTESTED': contested_count / total_count,
  'HISTORICAL': historical_count / total_count,
  'CONTRADICTORY': contradictory_count / total_count
} as role_distribution
```

**Cumulative Satisficing (2σ principle):**

Show only roles accounting for 95% of usage (filters noise in tail):

```python
def satisfice_role_distribution(distribution, threshold=0.95):
    """Return roles accounting for 95% of usage (analogous to 2σ)."""
    sorted_roles = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    cumulative = 0.0
    significant = {}

    for role, ratio in sorted_roles:
        cumulative += ratio
        significant[role] = ratio
        if cumulative >= threshold:
            break

    return significant
```

**Example:**
```python
full_distribution = {
    'CONTESTED': 0.55,      # 55% of edges
    'AFFIRMATIVE': 0.25,    # 80% cumulative
    'CONTRADICTORY': 0.15,  # 95% cumulative ← Stop here
    'HISTORICAL': 0.05      # (tail suppressed)
}

empirical_role = 'CONTESTED'  # Dominant role
empirical_confidence = 0.55
```

**Cross-Validation:**

```python
if semantic_role == empirical_role:
    # Agreement - high confidence
    status = "VALIDATED"
elif abs(semantic_confidence - empirical_confidence) < 0.20:
    # Weak signals - ambiguous
    status = "AMBIGUOUS"
elif semantic_confidence > empirical_confidence:
    # Trust semantic signal
    status = "SEMANTIC_OVERRIDE"
    suggestion = f"Word suggests {semantic_role}, but usage is {empirical_role}"
else:
    # Trust empirical signal
    status = "EMPIRICAL_OVERRIDE"
    suggestion = f"Usage suggests {empirical_role}, but word suggests {semantic_role}"
```

### Implementation

**Database Schema:**

```sql
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN role_distribution JSONB,
ADD COLUMN role_semantic VARCHAR(20),
ADD COLUMN role_empirical VARCHAR(20),
ADD COLUMN role_status VARCHAR(20),
ADD COLUMN role_last_calculated TIMESTAMP;

-- Graph nodes (ADR-048)
-- Add properties to :VocabType nodes:
-- v.role_distribution = {"AFFIRMATIVE": 0.70, "CONTESTED": 0.15, ...}
-- v.role_dominant = "AFFIRMATIVE"
-- v.role_confidence = 0.70
```

**Enhanced Workflow:**

```bash
kg vocab refresh-categories  # Grounding validation enabled by default
kg vocab refresh-categories --no-grounding  # Disable if needed
```

1. **Phase 1 (Mechanistic):** Assign category via cosine similarity to seed types
2. **Phase 2 (Empirical - Default):**
   - Compute semantic role (compare to 4 prototypes)
   - Query empirical role distribution (single Cypher query for all types)
   - Apply cumulative satisficing
   - Cross-validate signals
   - Store role distribution

**Performance:** ~150-600ms total (acceptable for periodic maintenance)
- Category assignment: ~50ms (existing)
- Grounding query: ~100-500ms (single query for all types)
- Role classification: ~20ms (4 cosine calcs × 200 types)

**API Endpoint:**

```python
POST /vocabulary/refresh-categories
{
  "only_computed": true,
  "with_grounding": true  // Default: enabled
}
```

## Use Cases

### Use Case 1: Quality Monitoring

Detect vocabulary misclassifications and category drift:

**Output Example:**
```
IMPLIES (logical category):
  Semantic role:   AFFIRMATIVE (0.88) - "logical inference"
  Empirical role:  CONTESTED (0.55) - connects debated concepts
  Status:          EMPIRICAL_OVERRIDE ⚠️

  Insight: Edge is used for hypothetical/evolving logic,
           not just established logical truths.

  Suggestion: Consider reclassifying to 'evidential' category
              or creating 'hypothetical_logical' subcategory.
```

**Benefits:**
- Identify vocabulary used differently than its name suggests
- Track category drift as domain knowledge evolves
- Provide evidence-based recommendations for manual reclassification

### Use Case 2: Role-Aware Path Filtering

Query graph with semantic role constraints:

**High-confidence knowledge paths:**
```cypher
MATCH path = (a:Concept)-[r*..5]->(b:Concept)
WHERE ALL(rel in r WHERE
  EXISTS {
    MATCH (v:VocabType {name: type(rel)})
    WHERE v.role_affirmative > 0.60
  }
)
RETURN path
ORDER BY reduce(s=1.0, rel in r | s * vocab_affirmative(type(rel))) DESC
LIMIT 10
```

**Explore contested knowledge:**
```cypher
MATCH path = (a)-[r*..5]->(b)
WHERE ALL(rel in r WHERE vocab_contested(type(rel)) > 0.40)
RETURN path
```

**Avoid refuted connections:**
```cypher
MATCH path = (a)-[r*..5]->(b)
WHERE NONE(rel in r WHERE
  vocab_contradictory(type(rel)) > 0.50 OR
  vocab_historical(type(rel)) > 0.50
)
RETURN path
```

**Combined edge + node filtering:**
```cypher
// Well-supported paths through well-supported concepts
MATCH path = (a)-[r*..5]->(b)
WHERE
  ALL(rel in r WHERE vocab_affirmative(type(rel)) > 0.60)  // Edge quality
  AND
  ALL(node in nodes(path) WHERE node.grounding_strength > 0.70)  // Node quality
RETURN path
```

**Benefits:**
- Context-aware graph traversal (find high-confidence vs explore contested areas)
- Confidence scoring for paths (multiplicative role strength)
- Trace historical evolution (follow HISTORICAL role edges)
- Semantic filtering without manual edge annotation

## Consequences

### Positive

1. **Empirical Validation**
   - Categories validated against actual usage, not just embedding similarity
   - Detects semantic drift as domain knowledge evolves
   - Cross-validates mechanistic predictions with graph-based evidence

2. **Zero Marginal Cost**
   - Leverages existing grounding infrastructure (ADR-044)
   - Single O(edges) query provides data for all vocabulary types
   - No LLM calls during refresh (prototypes generated once)

3. **Enhanced Query Capabilities**
   - Role-aware pathfinding enables semantic graph traversal
   - Confidence scoring for paths and connections
   - Supports diverse query patterns (high-confidence, contested, historical)

4. **Aligned with ADR-044**
   - Role distribution uses same ratio approach: `role_count / total_count`
   - Cumulative satisficing analogous to probabilistic truth convergence
   - Consistent mental model across concept grounding and edge semantics

### Negative

1. **Computational Cost**
   - Adds ~100-500ms to refresh operation
   - May be prohibitive for very large graphs (>1M edges)
   - Mitigated: Run as scheduled maintenance (weekly/monthly)

2. **Complexity**
   - Adds dual-signal validation layer to categorization
   - Requires understanding both embeddings and grounding
   - Mitigated: Clear documentation, optional feature flag

3. **Cold Start**
   - New vocabulary has no edges yet, no empirical signal
   - Falls back to semantic signal only
   - Mitigated: Natural - empirical validation requires usage

### Neutral

1. **Default Behavior**
   - Grounding validation enabled by default
   - Can be disabled via `--no-grounding` flag if needed
   - Provides richer information without requiring opt-in

2. **Storage Requirements**
   - Adds role_distribution JSONB column (~1KB per type)
   - Negligible impact (~200KB for 200 types)

## Alternatives Considered

### 1. Node-Only Grounding (Simpler)

```python
avg_grounding = avg(source.grounding, target.grounding)
empirical_role = threshold_classify(avg_grounding)
```

**Pros:** Simpler, faster (no cosine similarity to prototypes)
**Cons:** No semantic signal, can't detect word-usage mismatches
**Rejected:** Dual-signal provides richer validation and pathfinding capabilities

### 2. LLM-Based Reclassification

Generate category via LLM prompt with usage examples.

**Pros:** More sophisticated reasoning
**Cons:** Expensive (~$0.01 per type), slow (2-5s per type), requires LLM access
**Rejected:** Doesn't scale, violates general methods principle (ADR-052)

### 3. GNN-Based Edge Role Prediction

Train GNN model to predict edge roles using node features + edge embeddings.

**Pros:** Potentially higher accuracy (research-backed)
**Cons:** Requires training data, model deployment, ongoing retraining
**Rejected:** Adds complexity; dual-signal approach achieves validation without training overhead

## Validation Plan

### Hypothesis Testing

The core hypothesis—that edge semantic roles can be inferred from node grounding distribution—requires empirical validation before full deployment.

**Experiment Design:**
1. Sample 100-500 edges with diverse types and usage patterns
2. Manual labeling: Human experts classify edge semantic roles (ground truth)
3. Method comparison:
   - **Semantic-only:** Role from prototype similarity
   - **Empirical-only:** Role from node grounding distribution
   - **Dual-signal:** Cross-validated approach (proposed)
4. Metrics: Accuracy, precision, recall, F1 score per role
5. Analysis: Confusion matrix, agreement rates, failure modes

**Expected Outcomes:**
- Semantic-only: Good for new types, may drift from usage
- Empirical-only: Good for established types, fails on cold start
- Dual-signal: Best overall, detects mismatches, provides confidence

**Decision Criteria:**
- If dual-signal accuracy >85%: Proceed with implementation
- If single signal outperforms: Simplify to that approach
- If both weak (<70%): Revisit role definitions or thresholds

## Pedagogical Note: The Sleep Cycle Analogy

While this enhancement is primarily an optimization technique (empirical validation of mechanistic classification), it complements the sleep-based memory consolidation pattern from ADR-052:

**Phase 1: Deep Sleep (NREM)** → Consolidation/Pruning
- Removes vocabulary with `edge_count = 0` (unused synapses)
- Merges synonyms (consolidates redundant connections)
- Implemented in ADR-052 base

**Phase 2: REM Sleep** → Grounding-aware validation
- Tests vocabulary against empirical usage (grounding patterns)
- Refines semantic understanding based on actual experience
- Cross-validates predictions with observed data
- This enhancement

**Why the analogy works:**
1. Two-phase optimization with different goals (removal vs refinement)
2. Empirical testing against observed data (dream rehearsal vs grounding)
3. Quality improvement through pattern detection (coherence vs mismatches)

However, the analogy should not drive design decisions—the technical optimization benefits are the primary justification. The biological parallel is useful for explaining the pattern to users and developers.

## References

**Technical:**
- ADR-044: Probabilistic Truth Convergence (`grounding_strength` formula)
- ADR-047: Probabilistic Vocabulary Categorization (mechanistic approach)
- ADR-052: Vocabulary Expansion-Consolidation Cycle (pruning base)
- Shannon (1948): "A Mathematical Theory of Communication"
- Hegel (1807): "Phenomenology of Spirit" (dialectical reasoning)

**Pedagogical:**
- Walker & Stickgold (2006): "Sleep, Memory, and Plasticity"
- Tononi & Cirelli (2014): "Sleep and the Price of Plasticity"

---

**Last Updated:** 2025-10-31
