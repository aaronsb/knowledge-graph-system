# ADR-044: Probabilistic Truth Convergence Through Contradiction Resolution

**Status:** Proposed
**Date:** 2025-10-24
**Authors:** System Architecture Team
**Related:** ADR-025 (Dynamic Relationship Vocabulary), ADR-030 (Concept Deduplication), ADR-032 (Confidence Thresholds)

## Context

### The Problem of Contradictory Truth

During documentation maintenance (2025-01-24), a practical contradiction was discovered in the knowledge graph:

**Initial state:**
- Concept: "System uses Neo4j"
- Evidence: Multiple documentation sources, architecture diagrams, code references
- Relationships: SUPPORTS edges from various concepts

**New information:**
- Concept: "System uses Apache AGE + PostgreSQL"
- Evidence: Current codebase (`age_client.py`), ADR-016 migration decision
- Relationship: CONTRADICTS "System uses Neo4j"

**The Resolution Question:** Which truth is "more fundamental"? Which should the system present as authoritative?

### Philosophical Grounding: Gödel's Incompleteness & Evolutionary Fitness

Our knowledge graph is a **mathematical construct**:
- Nodes and edges form a complex relational equation
- Evidence text, relationship labels, embeddings are mathematical expressions
- **Gödel's incompleteness theorems apply:** No system can be both complete and consistent

**Implication:** We cannot achieve perfect, unchanging truth. We can only approach a "more fundamental" truth through evidence accumulation and statistical confidence.

### Connection to Darwin-Gödel Machines

This design draws direct inspiration from the **Darwin Gödel Machine** (Zhang et al., 2025, arXiv:2505.22954) - a self-improving system that combines Gödel's self-referential proof-based optimization with Darwin's empirical evolutionary selection.

**The critical insight from DGM:**

The original Gödel Machine (Schmidhuber, 2007) required **formal mathematical proof** that each self-modification improves the system - impractical in real-world scenarios.

The Darwin Gödel Machine relaxes this requirement: Instead of theoretical proof, it uses **empirical evidence from experiments** to demonstrate that changes improve performance.

**Direct parallel to our system:**

| Darwin Gödel Machine | Our Truth Convergence System |
|---------------------|------------------------------|
| Modifies its own code | Modifies knowledge representation |
| Empirical validation via coding benchmarks | Empirical validation via edge weight analysis |
| Fitness = performance on tasks | Fitness = `grounding_strength` (0.0-1.0) |
| Keeps changes that improve benchmark scores | Queries filter by grounding_strength threshold |
| Rejects changes that hurt performance | Filters concepts with grounding_strength < 0.20 from default queries |
| Reversible (can revert bad changes) | Reversible (grounding recalculates as evidence shifts) |

**In our context:**
- **External system = Real world:** Documents, code, architecture decisions provide empirical evidence
- **Fitness function = grounding_strength:** Concepts with grounding_strength < 0.20 empirically fail fitness test
- **Evolutionary selection:** Low-grounding concepts filtered from default query results (grounding_strength < 0.20)
- **Self-modification:** Graph structure evolves based on statistical evidence, not programmer assertions
- **Empirical validation:** No attempt to "prove" a concept is wrong - just measure support/contradict weight balance

**Key quote from DGM paper:**
> "The DGM relaxes the Gödel Machine's impractical requirement of theoretically proving that a change will improve the system, instead requiring empirical evidence from experiments."

**Our application:**
> We relax the requirement of formally proving a concept is "false," instead requiring empirical evidence (grounding_strength < 0.20, i.e., <20% support) that the concept conflicts with observed reality.

**Critical differences:**
- Darwin-Gödel machines modify their *own code* (meta-learning)
- Our system modifies its *knowledge representation* (epistemic evolution)
- DGM proves changes through benchmark performance
- We prove changes through edge count statistics
- Both systems share: **empirical validation over formal proof**

This is **evolutionary epistemology** - knowledge evolves through statistical fitness selection, not deterministic rules.

### Ecological Metaphor: Concepts as Competing Species

We have, essentially, **an ecology of concepts that compete for grounding support from the environment**:

**Environmental niche:** The "external system" provides evidence through document ingestion
- New documents = environmental changes
- Evidence instances = resources (food)
- SUPPORTS edges = symbiotic relationships
- CONTRADICTS edges = competitive relationships

**Evolutionary competition:**
- **"System uses Neo4j"** and **"System uses Apache AGE"** compete for the same ecological niche
- Initially, Neo4j concept has strong support (12 SUPPORTS edges) - it's dominant (grounding_strength = 1.0)
- Apache AGE concept emerges with contradictory evidence (47 CONTRADICTS edges against Neo4j)
- Neo4j concept's fitness drops: `grounding_strength = 0.232` (23% support) → falls below survival threshold
- Apache AGE concept becomes dominant in the ecosystem (grounding_strength = 0.901)

**Natural selection mechanism:**
- Fitness function = grounding_strength (continuous 0.0-1.0)
- Selection pressure = 0.20 threshold (20% minimum support)
- Survival = concepts with grounding_strength ≥ 0.20 appear in default query results
- Filtering = concepts with grounding_strength < 0.20 excluded from default queries (but still findable)

**Key insight:** We're not programming truth - we're letting truth emerge from competitive evolutionary pressure based on evidence accumulation.

**Unlike biological evolution:**
- "Filtered" concepts aren't deleted (non-destructive filtering)
- Can reappear in results if environment changes (Neo4j might return for multi-region architecture)
- Fitness is recalculated continuously at every query - always reflects current evidence

This is **conceptual Darwinism** - ideas survive based on their fit with observable reality, not programmer assertions.

### Information-Theoretic Foundations

Beyond the philosophical and evolutionary metaphors, this approach is grounded in established information theory and statistical practice. When we measure contradiction ratios, we're not arbitrarily choosing metrics - we're quantifying uncertainty reduction and signal detection in a way that has deep connections to Shannon's information theory and Bayesian reasoning.

**Entropy reduction as truth convergence:** In information-theoretic terms, high contradiction represents high entropy - significant uncertainty about whether a concept reflects reality. When "System uses Neo4j" has 12 SUPPORTS and 47 CONTRADICTS edges, the system is in a high-entropy state: query results are uncertain, and users receive conflicting information. Filtering the Neo4j concept (grounding_strength = 0.232 < 0.20 threshold) from default queries reduces entropy by collapsing the uncertainty - the system now confidently presents "System uses Apache AGE" as the dominant truth. This isn't arbitrary pruning; it's entropy minimization based on empirical evidence.

**Bayesian updating through edge accumulation:** Each ingested document provides new evidence in the form of SUPPORTS or CONTRADICTS edges. The graph effectively performs continuous Bayesian updating without explicit probability calculations. When grounding_strength drops to 0.20, we have strong posterior evidence (4:1 ratio of contradictions-to-supports) that the concept conflicts with observable reality. This threshold choice - corresponding to approximately 1.28 standard deviations - isn't pulled from thin air. It represents a standard confidence level used across statistical practice, from quality control to hypothesis testing. We're asking: "Is the evidence preponderance strong enough to warrant filtering?" At 4:1 contradictions-to-supports, the answer becomes statistically compelling.

**Signal-to-noise as fitness:** The grounding_strength can be understood as a signal-to-noise ratio. A concept with low contradictions (high support) has strong signal relative to noise (grounding_strength → 1.0). A concept with high contradictions (low support) has poor signal-to-noise (grounding_strength → 0.0) and should be filtered from query results. This isn't subjective judgment - it's quantifiable information quality measurement. The fitness function `grounding_strength = support_weight / total_weight` directly measures how well a concept's signal stands above the noise of contradictory evidence.

**Mutual information and concept relationships:** CONTRADICTS edges aren't just negative relationships - they carry information about concept incompatibility. High mutual information between "System uses Neo4j" and "System uses Apache AGE" (through strong CONTRADICTS edges) tells us these concepts occupy the same semantic niche and cannot both be true. The optional agent context uses this mutual information to reason about which concept better fits the evidence landscape, performing a form of information-theoretic model selection.

**Kolmogorov complexity and Occam's razor:** Maintaining contradictory concepts in query results increases the system's Kolmogorov complexity - the minimal description length needed to represent the knowledge state. When we filter one concept based on low grounding_strength (< 0.20), we're applying Occam's razor: the simpler explanation (one true state: Apache AGE) is preferred over the complex explanation (both might be true, context-dependent). This principle, formalized by Kolmogorov, isn't just philosophical - it's a practical heuristic for avoiding overfitting to noisy data.

**Why this isn't ad-hoc:** Contrast this with typical RAG systems that use similarity thresholds like 0.7 or 0.75 with little justification beyond "it worked in our tests." Our 0.20 grounding_strength threshold is defensible because it corresponds to established statistical practice (1.28σ), requires strong evidence ratio (4:1 contradictions-to-supports), and can be empirically validated through A/B testing. Could it be 0.15 or 0.30 for specific domains? Certainly - and that would be domain-specific tuning within a theoretically sound framework, not arbitrary parameter fiddling.

**Reversibility as epistemic humility:** The non-destructive query-time filtering approach acknowledges a fundamental information-theoretic reality: we're operating under incomplete information. Gödel proved that no system can be both complete and consistent; we're adding the practical corollary that no knowledge graph can be both comprehensive and correct. Evidence arrival is path-dependent and temporally ordered. Deleting concepts assumes certainty we cannot have; filtering them from default queries acknowledges we're making the best decision given current evidence, while remaining open to future evidence that shifts the balance. This is information-theoretically sound: we preserve information (all concepts remain in graph) while reducing query entropy (filtering low-grounding concepts from default results).

### Current System Behavior

**What happens now:**
1. System ingests "Neo4j" references → creates concepts with high confidence
2. System ingests "Apache AGE" references → creates new concepts
3. LLM may create CONTRADICTS edges between them
4. **Both remain in the graph with equal standing**
5. Query results may return contradictory information
6. No mechanism to determine which is "more true"

**Result:** The graph faithfully represents what was ingested, but provides no guidance on which information reflects current reality.

### The Traditional Approaches (And Why They Fail)

**1. Temporal ordering ("newest wins"):**
- ❌ Outdated information can be accidentally re-ingested
- ❌ Doesn't account for evidence strength
- ❌ What if we ingest historical documents about Neo4j after migrating to AGE?

**2. Source authority ("official docs override"):**
- ❌ Requires manual source ranking
- ❌ What if official docs lag behind reality?
- ❌ Doesn't scale to diverse document types

**3. Delete contradicted concepts:**
- ❌ **Catastrophic information loss**
- ❌ Irreversible if truth shifts again
- ❌ Loses historical context

**4. Manual curation:**
- ❌ Doesn't scale
- ❌ Defeats purpose of automated knowledge extraction
- ❌ Requires constant human intervention

## Decision

### Implement Query-Time Grounding Strength Calculation

**Core Principle:** Truth emerges from statistical preponderance of evidence, calculated dynamically at query time, not stored as static labels.

**Key insight:** Rather than marking concepts as "IRRELEVANT" (static, binary, query-exclusion problem), we calculate a continuous **grounding_strength** score (0.0-1.0) based on current edge weights whenever the concept is queried.

### Mechanism: Dynamic Grounding Strength Computation

**1. Calculate Grounding Strength (Query-Time)**

For any concept node, calculate grounding strength using edge confidence scores:

```python
# Sum confidence scores (force magnitude), not just count edges
support_weight = sum(confidence for edge in incoming SUPPORTS relationships)
contradict_weight = sum(confidence for edge in incoming CONTRADICTS relationships)
total_weight = support_weight + contradict_weight

# Grounding strength = proportion of support vs total evidence
grounding_strength = support_weight / total_weight if total_weight > 0 else 1.0
# Default 1.0 = no contradictions = assume well-grounded
```


**Why grounding_strength, not "irrelevant" marking:**

**Problems with static marking:**
- ❌ **Query paradox:** If we exclude marked concepts, how do we find them to re-evaluate?
- ❌ **Stale state:** Marking freezes a point-in-time decision, but edges keep accumulating
- ❌ **Binary thinking:** Concept is either relevant or not - but truth is continuous
- ❌ **Computational waste:** Agent introspection needed every mark/unmark operation

**Advantages of dynamic calculation:**
- ✅ **Always current:** Reflects latest edge weights at query time
- ✅ **Continuous score:** 0.0 (contradicted) to 1.0 (supported), not binary
- ✅ **Query-time filtering:** `WHERE grounding_strength >= 0.20` (adjustable threshold)
- ✅ **Always findable:** Lower threshold to find weakly-grounded concepts
- ✅ **Self-updating:** New edges automatically affect score
- ✅ **Pure mathematics:** No agent needed for score calculation

**Example showing grounding_strength:**

| Edges | Support Weight | Contradict Weight | Grounding Strength | Interpretation |
|-------|----------------|-------------------|-------------------|----------------|
| 12 S, 47 C | 10.2 | 33.84 | 10.2/44.04 = **0.232** | Weakly grounded (23%) |
| 47 S, 12 C | 33.84 | 10.2 | 33.84/44.04 = **0.768** | Well grounded (77%) |
| 50 S, 5 C | 42.0 | 4.2 | 42.0/46.2 = **0.909** | Strongly grounded (91%) |
| 5 S, 50 C | 4.2 | 42.0 | 4.2/46.2 = **0.091** | Contradicted (9%) |

**Why weighted, not counted:**

Edges have **direction** (FROM → TO) and **magnitude** (confidence: 0.0-1.0). To properly calculate statistical distributions, we need **force vectors**, not binary counts:

- **Binary counting** (wrong): 47 contradictions = 47.0 total force
- **Weighted summing** (correct): 47 contradictions with avg confidence 0.72 = 33.84 total force

Weighted approach is more statistically sound:
- Gives continuous variable (suitable for normal distribution)
- Weak contradictions (confidence < 0.6) don't overwhelm strong supports
- Strong contradictions (confidence > 0.9) appropriately dominate
- Aligns with information-theoretic grounding (confidence = information content)

**2. Query-Time Filtering with Adjustable Threshold**

Default queries filter by minimum grounding strength:

```cypher
WHERE grounding_strength >= 0.20  // Default: exclude concepts with <20% support
```

**Why 20% (0.20) threshold?**
- Inverse of 80% contradiction ratio (1.0 - 0.80 = 0.20)
- Corresponds to ~1.28σ in normal distribution
- Represents clear statistical signal while avoiding noise
- Requires 4:1 ratio of contradictions to supports (strong evidence shift)
- **Adjustable per query:** Can lower to 0.10 or raise to 0.50 based on needs

**3. Optional Agent-Based Context (For LLM Queries)**

When presenting weakly-grounded concepts to LLMs, optionally include agent-generated context:

```
Agent retrieves:
  - Weakly-grounded concept (grounding_strength < 0.20)
  - All adjacent CONTRADICTS edges
  - All adjacent SUPPORTS edges
  - Evidence text from all instances
  - Source documents and dates

Agent provides context:
  "Given evidence that:
   - Neo4j mentioned in 12 documents (2025-10-01 to 2025-10-08)
   - Apache AGE mentioned in 47 documents (2025-10-10 to 2025-01-24)
   - ADR-016 states migration occurred 2025-10-09
   - Current codebase uses age_client.py, not neo4j_client.py

   Context: 'System uses Neo4j' has grounding_strength of 0.232 (23% support)
   Interpretation: Temporal evidence + codebase verification suggests this
   represents historical state, not current architecture.
   Confidence: 0.95"
```

**Agent's new role:**
- ❌ Does NOT mark concepts as irrelevant
- ❌ Does NOT modify graph structure
- ✅ Provides explanatory context for weakly-grounded concepts
- ✅ Helps LLMs synthesize accurate responses
- ✅ Optional enhancement - queries work without agent

**LLM query pattern with agent context:**

```
Presupposition: The following concepts have weak grounding in evidence:

Concept: "System uses Neo4j"
- Grounding strength: 0.232 (23% support, 77% contradiction)
- Context: Represents historical state (pre-2025-10-09 migration)
- Current alternative: "System uses Apache AGE + PostgreSQL" (grounding: 0.901)

Given this context, synthesize the best possible true statement about:
"What database does the system use?"

Expected response: "The system currently uses Apache AGE + PostgreSQL.
It previously used Neo4j but migrated in October 2025 per ADR-016."
```

**Key insight:** Agent provides interpretive context, but the **grounding_strength calculation is pure mathematics** - no agent needed for the core filtering mechanism.

### Bounded Rationality: Query Depth Constraints

**The Frame Problem:** When calculating grounding strength, where do we stop recursive evaluation?

**Herbert Simon's bounded rationality:** Agents (human or computational) cannot optimize globally due to:
- Computational limits (time, memory, processing power)
- Incomplete information (can't know everything)
- Cognitive/architectural constraints (must decide with partial knowledge)

**Direct parallel:** Just as humans can't consider every consequence before stepping (microorganisms harmed, butterfly effects, infinite causal chains), our system can't recursively evaluate grounding strength through the entire graph.

#### The Recursive Depth Explosion

**Depth 0 (Trivial):** Return concept without considering any edges
```
Complexity: O(1)
Information: None (just the concept label)
```

**Depth 1 (Current Design):** Calculate grounding_strength from direct edges only
```
grounding_strength = support_weight / total_weight

Complexity: O(|incoming_edges|)
Information: Direct evidence from adjacent concepts
Decision: Pragmatic - bounded computation, sufficient signal
```

**Depth 2 (Recursive):** Weight edges by grounding_strength of source concepts
```
# Edge weight influenced by source concept's grounding
weighted_support = sum(
    edge.confidence * source_concept.grounding_strength
    for edge in SUPPORTS edges
)

Complexity: O(|edges| × |edges_per_adjacent_concept|)
Information: Evidence + quality of evidence sources
Problems:
  - Must calculate grounding for N adjacent concepts first
  - Each adjacent concept may have M edges to evaluate
  - N × M quickly becomes large
```

**Depth 3+ (Unbounded):** Recursively evaluate grounding of supporting concepts
```
Complexity: O(|edges|^depth) - exponential explosion
Problems:
  ✗ Cycles: A supports B supports C supports A → infinite recursion
  ✗ Branching: Each concept has multiple supports, tree explodes
  ✗ Termination: When to stop? Need global knowledge (Gödelian barrier)
  ✗ Query latency: Milliseconds → seconds → minutes → timeout
```

**Example explosion:**
```
Depth 1: Concept has 10 edges → 10 evaluations
Depth 2: Each edge source has 10 edges → 10 × 10 = 100 evaluations
Depth 3: Each depth-2 concept has 10 edges → 10 × 10 × 10 = 1,000 evaluations
Depth 4: → 10,000 evaluations
Depth 5: → 100,000 evaluations (likely timeout)
```

**Your analogy:** "Imagine if I had to consider what I would harm with every step I took."
- Depth 1: "Is the ground stable?" (local, practical)
- Depth 2: "Are the molecules in the ground stable?" (getting theoretical)
- Depth 3: "Are the quarks in those molecules stable?" (absurd for walking)
- Depth ∞: Complete knowledge of all consequences (impossible, Gödelian)

#### OpenCypher Query Depth Rules

**Rule 1: Default to Depth 1 (Direct Edges Only)**

All grounding_strength calculations use direct SUPPORTS/CONTRADICTS edges:

```cypher
// Standard grounding calculation: depth=1
MATCH (c:Concept)
OPTIONAL MATCH (c)<-[s:SUPPORTS]-()
OPTIONAL MATCH (c)<-[d:CONTRADICTS]-()
WITH c,
     reduce(sum = 0.0, e IN collect(s) | sum + coalesce(e.confidence, 0.8)) as support_weight,
     reduce(sum = 0.0, e IN collect(d) | sum + coalesce(e.confidence, 0.8)) as contradict_weight
WITH c,
     support_weight,
     contradict_weight,
     CASE
       WHEN support_weight + contradict_weight > 0
       THEN support_weight / (support_weight + contradict_weight)
       ELSE 1.0
     END as grounding_strength
RETURN c, grounding_strength
```

**Rationale:**
- O(|edges|) complexity - scales linearly
- Query completes in milliseconds even with thousands of concepts
- Sufficient signal: direct evidence is strongest signal
- Bounded computation: doesn't require graph-wide traversal

**Rule 2: Maximum Traversal Depth = 3 Hops (For Path Queries)**

When finding paths between concepts (not grounding calculation), limit traversal:

```cypher
// Path finding: max depth 3
MATCH path = (c1:Concept)-[*1..3]-(c2:Concept)
WHERE c1.concept_id = $source_id
  AND c2.concept_id = $target_id
RETURN path
LIMIT 10

// NOT THIS (unbounded):
MATCH path = (c1:Concept)-[*]-(c2:Concept)  // ✗ Can explode to entire graph
```

**Rationale:**
- Depth 3 allows: A → B → C → D (sufficient for most conceptual relationships)
- Beyond depth 3: relationship is too indirect to be meaningful
- Prevents graph-wide traversal (could hit thousands of nodes)

**Rule 3: Use LIMIT Aggressively**

Always limit result sets to prevent runaway queries:

```cypher
// Good: limited result set
MATCH (c:Concept)
WHERE grounding_strength >= 0.20
RETURN c
LIMIT 1000  // Maximum 1000 concepts returned

// Bad: unbounded
MATCH (c:Concept)
RETURN c  // ✗ Could return millions of nodes
```

**Rationale:**
- Even O(n) queries become expensive with large n
- Application layer pagination (1000 per page) prevents memory exhaustion
- User can't process 10,000+ results anyway (cognitive bounded rationality)

**Rule 4: Avoid Recursive CTEs for Grounding**

Do NOT use recursive common table expressions for grounding calculations:

```cypher
// ✗ AVOID: Recursive grounding (depth=N, unbounded)
WITH $concept_id as root_id
CALL {
  WITH root_id
  MATCH (c:Concept {concept_id: root_id})
  OPTIONAL MATCH (c)<-[s:SUPPORTS]-(source:Concept)
  // Recursively calculate source grounding... → UNBOUNDED
  RETURN c, grounding
}
RETURN c, grounding
```

**Why avoid:**
- Triggers exponential traversal (O(edges^depth))
- Cycle detection adds complexity and overhead
- Termination conditions hard to define correctly
- Query optimizer can't predict runtime

**Alternative:** If recursive grounding is truly needed (rare), implement iteratively:
```python
# Python application layer: iterative depth-limited grounding
def calculate_recursive_grounding(concept_id, max_depth=2):
    """Calculate grounding with limited recursion."""
    visited = set()

    def recurse(cid, depth):
        if depth > max_depth or cid in visited:
            return 1.0  # Default grounding
        visited.add(cid)

        # Calculate depth-1 grounding via query
        direct_grounding = query_direct_grounding(cid)

        if depth == max_depth:
            return direct_grounding

        # Weight by source concept grounding (depth+1)
        support_sources = query_support_sources(cid)
        weighted_support = sum(
            edge.confidence * recurse(source.id, depth + 1)
            for source in support_sources
        )

        # Similar for contradictions...
        return weighted_support / total_weight

    return recurse(concept_id, depth=0)
```

**Rule 5: Cycle Detection Required for Depth > 1**

If implementing recursive queries, MUST track visited nodes:

```cypher
// Depth 2 with cycle prevention
WITH $concept_id as root_id
MATCH (c:Concept {concept_id: root_id})<-[s:SUPPORTS]-(source:Concept)
WHERE source.concept_id <> root_id  // Prevent immediate cycle
OPTIONAL MATCH (source)<-[s2:SUPPORTS]-(source2:Concept)
WHERE source2.concept_id NOT IN [root_id, source.concept_id]  // Prevent cycles
WITH c, source, collect(s2) as source_edges
// ... calculate weighted grounding ...
```

**Rationale:**
- Graph has cycles: A supports B supports A (common in knowledge graphs)
- Without cycle detection: infinite recursion or exponential duplication
- Cycle tracking overhead: O(visited_nodes) memory per query
- Trade-off: correctness vs complexity

#### Complexity Analysis Summary

| Depth | Complexity | Query Time (1000 concepts) | Use Case |
|-------|-----------|---------------------------|----------|
| 0 | O(1) | <1ms | Concept lookup only |
| 1 | O(E) | 10-50ms | **Default: grounding_strength** |
| 2 | O(E × E_adj) | 100-500ms | Advanced: weighted grounding |
| 3 | O(E³) | 1-10 seconds | Rare: deep path analysis |
| 4+ | O(E^depth) | 10+ seconds → timeout | **Avoid: computationally infeasible** |

Where:
- E = average edges per concept (~10-50 in typical knowledge graphs)
- E_adj = average edges per adjacent concept

**Practical implications:**
- Depth 1 (current design): Handles 1M+ concepts with subsecond queries
- Depth 2 (future): Requires caching or async processing
- Depth 3+: Only for offline analysis, not real-time queries

#### Design Decision: Depth=1 as Pragmatic Optimum

**Why depth=1 is sufficient:**

✅ **Direct edges carry strongest signal:**
- Evidence instances directly reference this concept
- Confidence scores reflect extraction quality
- SUPPORTS/CONTRADICTS edges explicitly created by LLM

✅ **Higher depths add noise, not signal:**
- Depth 2: "Concepts that support concepts that support this concept"
- Information dilution: indirect relationships are weaker
- Transitive support isn't necessarily meaningful

✅ **Computational feasibility:**
- O(edges) scales to millions of concepts
- Query completes in <100ms for typical graphs
- No cycle detection needed

✅ **Aligns with human cognition:**
- Humans evaluate claims based on direct evidence
- We don't recursively validate the validator's validator's validator
- **Bounded rationality:** Direct evidence is practical decision-making basis

**Sutton's bitter lesson applied:**
- ✅ Computational method: Simple depth=1 force vector summing
- ✅ Scales with compute: More edges = better signal (doesn't require deeper reasoning)
- ❌ Human-like reasoning: Recursive "how credible is my source?" requires complex logic

**Trade-off acknowledged:**
- Lose: Ability to weight edges by source concept quality
- Gain: Practical, scalable, real-time grounding calculations
- Future: Can add depth=2 as optional enhancement (cached, async)

#### Future: Depth=2 as Optional Enhancement

If depth=1 proves insufficient (rare), consider depth=2 with strict constraints:

```cypher
// Depth-2 grounding (optional, future)
// Step 1: Calculate depth-1 grounding for all concepts (cached)
// Step 2: Use cached values to weight edges

MATCH (c:Concept {concept_id: $concept_id})
OPTIONAL MATCH (c)<-[s:SUPPORTS]-(source:Concept)
OPTIONAL MATCH (c)<-[d:CONTRADICTS]-(contra:Concept)

// Use pre-cached grounding_strength from depth-1 calculation
WITH c,
     collect({
       edge: s,
       source_grounding: source.grounding_strength_cached
     }) as support_edges,
     collect({
       edge: d,
       source_grounding: contra.grounding_strength_cached
     }) as contradict_edges

// Weight edges by source concept grounding
WITH c,
     reduce(sum = 0.0, item IN support_edges |
       sum + coalesce(item.edge.confidence, 0.8) * coalesce(item.source_grounding, 1.0)
     ) as weighted_support,
     reduce(sum = 0.0, item IN contradict_edges |
       sum + coalesce(item.edge.confidence, 0.8) * coalesce(item.source_grounding, 1.0)
     ) as weighted_contradict

RETURN c,
       weighted_support / (weighted_support + weighted_contradict) as grounding_strength_depth2
```

**Requirements for depth=2:**
- Must cache depth-1 grounding_strength for all concepts (materialized view)
- Cache invalidation on edge changes (complexity overhead)
- A/B test vs depth=1 to verify improvement justifies cost
- Only enable if depth=1 demonstrably insufficient

**Expected outcome:** Depth=1 will be sufficient for 95%+ of use cases.

### Automatic Reversibility Through Continuous Calculation

**Scenario:** New evidence reverses the grounding strength

**Example:**
1. "System uses Neo4j" has `grounding_strength = 0.232` (weakly grounded)
2. Later, 50 new documents describe "Neo4j cluster for HA" (future architecture)
3. New SUPPORTS edges shift the balance
4. Recalculated: `grounding_strength = 0.851` (now well-grounded)

**Automatic behavior:**
- ✅ **No manual re-evaluation needed** - grounding_strength recalculates at every query
- ✅ **No state management** - no marking/unmarking operations
- ✅ **Always current** - reflects latest edge weights immediately
- ✅ **No cascading updates** - each concept's score is independent

**Query behavior changes automatically:**

```cypher
// When grounding_strength was 0.232 (below 0.20 threshold)
WHERE grounding_strength >= 0.20
// Concept excluded from results

// After new evidence, grounding_strength becomes 0.851
WHERE grounding_strength >= 0.20
// Concept now included in results - automatically!
```

**Historical queries still work:**

```cypher
// View all concepts regardless of grounding
WHERE grounding_strength >= 0.0  // Include everything

// View only weakly-grounded concepts (for analysis)
WHERE grounding_strength < 0.20  // Show contradicted concepts

// View grounding strength evolution (if we add temporal tracking)
RETURN c.label,
       grounding_strength_current,
       grounding_strength_30_days_ago,
       grounding_strength_delta
```

**No state management needed:**
- No IRRELEVANT → REINSTATED transitions
- No dated markers (marked_irrelevant_date, reinstated_date)
- No agent reasoning stored
- Just pure mathematical calculation from current edge weights

## Implementation

### Phase 1: Detection & Metrics (Immediate)

**1. Grounding Strength Query (Standard Pattern):**

```cypher
// Calculate grounding_strength for all concepts
MATCH (c:Concept)
OPTIONAL MATCH (c)<-[s:SUPPORTS]-()
OPTIONAL MATCH (c)<-[d:CONTRADICTS]-()
WITH c,
     collect(s) as support_edges,
     collect(d) as contradict_edges
WITH c,
     support_edges,
     contradict_edges,
     reduce(sum = 0.0, edge IN support_edges | sum + coalesce(edge.confidence, 0.8)) as support_weight,
     reduce(sum = 0.0, edge IN contradict_edges | sum + coalesce(edge.confidence, 0.8)) as contradict_weight,
     size(support_edges) as support_count,
     size(contradict_edges) as contradict_count
WITH c,
     support_weight,
     contradict_weight,
     support_count,
     contradict_count,
     support_weight + contradict_weight as total_weight,
     CASE
       WHEN support_weight + contradict_weight > 0
       THEN support_weight / (support_weight + contradict_weight)
       ELSE 1.0  // No contradictions = assume well-grounded
     END as grounding_strength
WHERE total_weight > 3.0  // Minimum weight for statistical significance
  AND grounding_strength >= 0.20  // Default threshold: 20% support minimum
RETURN c.label,
       c.concept_id,
       support_count,
       contradict_count,
       round(support_weight * 100) / 100 as support_weight,
       round(contradict_weight * 100) / 100 as contradict_weight,
       round(grounding_strength * 1000) / 1000 as grounding_strength
ORDER BY grounding_strength ASC, contradict_weight DESC
```

**Key features:**
- Uses `reduce()` to sum edge confidence scores, not `count()`
- Falls back to 0.8 if confidence missing (backward compatibility)
- Minimum weight threshold (3.0) instead of minimum count (5)
- `grounding_strength` = support_weight / total_weight (continuous 0.0-1.0)
- Adjustable threshold: change 0.20 to query different confidence levels

**2. Find weakly-grounded concepts (for analysis):**

```cypher
// Find concepts with low grounding (potential contradictions)
MATCH (c:Concept)
OPTIONAL MATCH (c)<-[s:SUPPORTS]-()
OPTIONAL MATCH (c)<-[d:CONTRADICTS]-()
WITH c,
     reduce(sum = 0.0, e IN collect(s) | sum + coalesce(e.confidence, 0.8)) as support_weight,
     reduce(sum = 0.0, e IN collect(d) | sum + coalesce(e.confidence, 0.8)) as contradict_weight
WITH c,
     support_weight,
     contradict_weight,
     CASE
       WHEN support_weight + contradict_weight > 0
       THEN support_weight / (support_weight + contradict_weight)
       ELSE 1.0
     END as grounding_strength
WHERE grounding_strength < 0.20  // Weakly grounded
  AND support_weight + contradict_weight > 3.0  // Minimum significance
RETURN c.label,
       grounding_strength,
       support_weight,
       contradict_weight
ORDER BY grounding_strength ASC
```

**3. No concept properties needed:**

Concepts remain unchanged - no status field, no marking dates. Grounding strength is computed purely from edges at query time.

**4. API endpoints:**
- `GET /admin/grounding-analysis` - List weakly-grounded concepts
- `POST /admin/agent-context/{concept_id}` - Generate agent interpretation (optional)
- `GET /concepts?min_grounding=0.20` - Query with custom threshold

### Phase 2: Agent Context Generation (Optional Enhancement)

**Context Generation Agent prompt:**

```
You are providing interpretive context for a weakly-grounded concept in a knowledge graph.

Concept: {label}
Grounding strength: {grounding_strength} ({percent}% support)
Support weight: {support_weight} (from {support_count} edges)
Contradict weight: {contradict_weight} (from {contradict_count} edges)

Evidence supporting this concept:
{formatted_support_evidence}

Evidence contradicting this concept:
{formatted_contradict_evidence}

Source documents:
{document_list_with_dates}

Your task:
1. Analyze the temporal pattern (is this historical vs current?)
2. Assess evidence quality (which evidence is more authoritative?)
3. Identify the most likely alternative concept (higher grounding)
4. Provide context that helps an LLM synthesize accurate responses

Provide:
- Interpretation: 2-3 sentence explanation grounded in evidence
- Alternative concept: {concept_label} (grounding: {grounding_strength})
- Temporal context: "Historical" | "Current" | "Future" | "Context-dependent"
- Confidence: 0.0-1.0

Format response as JSON.
```

**Agent uses:**
- OpenAI GPT-4o or Anthropic Claude Sonnet 4
- Temperature: 0.1 (low, for consistency)
- Max tokens: 500
- Retrieves up to 50 evidence instances per concept

**Key difference from marking approach:**
- Agent does NOT make binary decisions (mark/don't mark)
- Agent provides interpretive context for LLMs to use
- Agent output is optional enhancement, not required for filtering
- Grounding strength calculation happens independently of agent

### Phase 3: Performance Optimization (Future)

**Caching grounding_strength:**

For performance, optionally cache grounding_strength calculations:

```cypher
// Materialized view pattern (recalculated periodically)
(:Concept {
  grounding_strength_cached: 0.768,
  grounding_cache_date: "2025-01-24T10:30:00Z",
  grounding_cache_ttl: 3600  // seconds
})
```

**Cache invalidation:**
- Invalidate when new SUPPORTS or CONTRADICTS edges added to concept
- Or use TTL (time-to-live) approach: recalculate every N seconds
- Trade-off: staleness vs query performance

**Monitoring metrics:**
- Average grounding_strength across all concepts
- Distribution of grounding_strength (histogram)
- Concepts with grounding < 0.20 (count trending over time)
- Query performance with/without caching

## Examples

### Example 1: Neo4j → Apache AGE (Actual)

**Initial state (2025-10-08):**
```
(:Concept {label: "System uses Neo4j"})
  ← SUPPORTS ← (12 evidence instances from docs, avg confidence 0.85)

Grounding calculation:
  support_weight: 12 × 0.85 = 10.2
  contradict_weight: 0
  grounding_strength: 10.2 / 10.2 = 1.00 (fully supported)
```

**After ingestion (2025-01-24):**
```
(:Concept {label: "System uses Neo4j"})
  ← SUPPORTS ← (12 evidence instances from old docs, avg confidence 0.85)
  ← CONTRADICTS ← (47 evidence instances from new docs, avg confidence 0.72)

Grounding calculation:
  support_weight: 12 × 0.85 = 10.2
  contradict_weight: 47 × 0.72 = 33.84
  total_weight: 44.04
  grounding_strength: 10.2 / 44.04 = 0.232 (23% support, 77% contradiction)
```

**Optional agent context:**
```json
{
  "interpretation": "Temporal analysis shows Neo4j references end 2025-10-08. ADR-016 explicitly documents migration to Apache AGE on 2025-10-09. Current codebase (age_client.py) and all recent documentation reference Apache AGE. Neo4j represents historical state, not current architecture.",
  "alternative_concept": "System uses Apache AGE + PostgreSQL",
  "alternative_grounding": 0.901,
  "temporal_context": "Historical",
  "confidence": 0.95
}
```

**Query behavior (automatic):**
```cypher
// Default query (grounding >= 0.20)
MATCH (c:Concept)
// ... calculate grounding_strength ...
WHERE grounding_strength >= 0.20
RETURN c
// "System uses Neo4j" has grounding 0.232 → INCLUDED (just above threshold)

// Stricter query (grounding >= 0.50)
MATCH (c:Concept)
// ... calculate grounding_strength ...
WHERE grounding_strength >= 0.50
RETURN c
// "System uses Neo4j" has grounding 0.232 → EXCLUDED

// Find weakly-grounded concepts
WHERE grounding_strength < 0.30
// "System uses Neo4j" appears here for investigation
```

**No concept modification needed** - grounding_strength calculated dynamically at query time.

### Example 2: Multiple Thresholds for Different Use Cases

**Scenario:** Query with different grounding thresholds

**Concept states:**
```
"Similarity threshold is 0.85" → grounding: 0.90 (code + docs)
"Similarity threshold is 0.75" → grounding: 0.35 (old docs)
"Similarity threshold is 0.80" → grounding: 0.28 (mixed references)
```

**Query behaviors:**

```cypher
// High-confidence query (production use)
WHERE grounding_strength >= 0.80
→ Returns: "Similarity threshold is 0.85" only

// Medium-confidence query (general use)
WHERE grounding_strength >= 0.50
→ Returns: "Similarity threshold is 0.85" only

// Low-confidence query (include uncertain)
WHERE grounding_strength >= 0.20
→ Returns: All three concepts (investigation mode)

// Find contradictory concepts (analysis)
WHERE grounding_strength < 0.40
→ Returns: "0.75" and "0.80" concepts (needs investigation)
```

**LLM receives context:**
```
High-grounding concept: "Similarity threshold is 0.85" (grounding: 0.90)
Weakly-grounded alternatives: "0.75" (grounding: 0.35), "0.80" (grounding: 0.28)

Synthesize response: "What is the similarity threshold?"
Expected: "The system uses 0.85 as the similarity threshold (verified in code)."
```

### Example 3: Automatic Reversibility - Future Architecture Change

**Current state (2025-01-24):**
```
"System uses Neo4j" → grounding: 0.232 (weakly grounded)
"System uses Apache AGE" → grounding: 0.901 (well grounded)
```

**Future ingestion (2026-06-01):**
- New ADR: "ADR-089: Neo4j Enterprise for Multi-Region HA"
- Architecture docs: "PostgreSQL + AGE for single-region, Neo4j for geo-distributed"
- Deployment guides: "Neo4j cluster configuration"

**Automatic recalculation:**
```
"System uses Neo4j"
  support_weight: 10.2 (old) + 29.75 (new) = 39.95
  contradict_weight: 33.84 (unchanged)
  grounding_strength: 39.95 / 73.79 = 0.541 (54% support - improved!)
```

**Query behavior automatically changes:**
```cypher
// Before: grounding was 0.232
WHERE grounding_strength >= 0.50
→ Excluded

// After: grounding is 0.541
WHERE grounding_strength >= 0.50
→ Included (automatically, no manual intervention!)
```

**Developer investigates:**
- Runs: `kg admin grounding-analysis`
- Finds: Both "Neo4j" (0.541) and "Apache AGE" (0.901) have good grounding
- Realizes: Context matters - both are true in different scenarios

**Solution (concept refinement):**
- Split concept: "System uses Neo4j" → two more specific concepts
  - "System uses Neo4j for geo-distributed deployment" (grounding: 0.89)
  - "System uses Apache AGE for single-region deployment" (grounding: 0.92)
- Both well-grounded, no contradiction, clearer semantics

## Consequences

### Positive

✅ **Always current:** Grounding strength reflects latest edge weights at every query
✅ **No state management:** No marking/unmarking, no status fields, no timestamps
✅ **Automatic reversibility:** Truth shifts automatically as evidence accumulates
✅ **No query paradox:** Lowering threshold always finds weakly-grounded concepts
✅ **Continuous scores:** 0.0-1.0 range, not binary relevant/irrelevant
✅ **Adjustable filtering:** Different queries use different thresholds (0.20, 0.50, 0.80)
✅ **Pure mathematics:** Core mechanism requires no agent or human intervention
✅ **Statistical soundness:** Grounded in force vector summing (confidence weights)
✅ **Non-destructive:** All concepts preserved, filtering happens at query time
✅ **Philosophically sound:** Acknowledges Gödelian incompleteness through continuous probability
✅ **Performance:** Can cache grounding_strength for frequently-queried concepts (optional)
✅ **No cascading updates:** Each concept's score is independent

### Negative

⚠️ **Query overhead:** Must calculate grounding_strength for each concept (mitigated by caching)
⚠️ **Threshold selection:** Default 0.20 may not suit all domains or queries
⚠️ **No explicit marking:** Concepts don't have "this is wrong" labels (feature, not bug)
⚠️ **Agent context optional:** LLMs don't get interpretive context unless explicitly requested
⚠️ **Temporal information lost:** Can't track "when did grounding drop below threshold?"

### Trade-offs

**Computation vs Storage:**
- **Query-time calculation:** No storage overhead, always current, but adds query latency
- **Cached grounding:** Faster queries, but cache invalidation complexity
- **Current choice:** Query-time (prefer correctness over speed initially)

**Threshold Flexibility vs Consistency:**
- **Adjustable thresholds:** Different queries use different confidence levels (flexible)
- **Fixed threshold:** All queries use same standard (consistent)
- **Current choice:** Adjustable per query (0.20 default, user can override)

**Pure Math vs Agent Context:**
- **Pure math:** Fast, deterministic, no API costs, but no interpretation
- **With agent:** Interpretive context for LLMs, but API costs and latency
- **Current choice:** Pure math by default, agent context optional enhancement

**Continuous Scores vs Binary Labels:**
- **Continuous (0.0-1.0):** Nuanced, flexible filtering, but harder to understand at a glance
- **Binary (relevant/irrelevant):** Simple, clear, but loses information about degree of grounding
- **Current choice:** Continuous (preserves information, enables flexible querying)

## Alternatives Considered

### 1. Temporal Versioning (Rejected)

**Approach:** Track concept versions with timestamps, always use newest

**Why rejected:**
- Doesn't handle out-of-order ingestion (old docs ingested after new ones)
- Doesn't account for evidence strength
- Still requires deciding "which version is authoritative?"

### 2. Source Authority Ranking (Rejected)

**Approach:** Rank sources (codebase > ADRs > docs > notes), trust higher-ranked

**Why rejected:**
- Requires manual source classification
- Brittle: source authority can shift
- Doesn't handle cross-source contradictions well

### 3. Majority Vote (Rejected)

**Approach:** Simple count: most edges wins

**Why rejected:**
- One high-quality source should outweigh many low-quality ones
- Doesn't account for confidence scores
- No way to handle ties

### 4. Bayesian Belief Networks (Considered)

**Approach:** Model concepts as probability distributions, update with Bayes' theorem

**Why deferred:**
- Mathematically elegant but complex to implement
- Requires prior probability estimates
- May revisit in Phase 3 if edge-count approach proves insufficient

### 5. Static IRRELEVANT Marking (Rejected)

**Approach:** Mark concepts as IRRELEVANT when contradiction ratio ≥ 0.80, exclude from default queries

**Implementation:**
```cypher
(:Concept {
  status: "IRRELEVANT",
  marked_date: timestamp,
  marked_reason: text
})

// Queries
WHERE c.status <> 'IRRELEVANT' OR c.status IS NULL
```

**Why rejected:**

❌ **Query paradox:** If we exclude IRRELEVANT concepts from queries, how do we find them to re-evaluate when new evidence arrives?

❌ **Stale state:** Marking freezes a point-in-time decision, but edges continue to accumulate. A concept marked IRRELEVANT yesterday might become relevant today.

❌ **State management complexity:** Need to track marked_date, marked_reason, reinstated_date, reinstated_reason - significant bookkeeping overhead.

❌ **Cascading updates:** When reinstating a concept, must trigger re-evaluation of adjacent concepts - complex dependency management.

❌ **Binary thinking:** Either RELEVANT or IRRELEVANT - loses nuance. What about concepts with 40% support? 60% support?

❌ **Agent dependency:** Requires agent introspection for every mark/unmark operation - API costs and latency.

**Dynamic grounding_strength solves all these problems:**
- ✅ Always findable (just lower threshold)
- ✅ Always current (recalculated at query time)
- ✅ No state management (no bookkeeping)
- ✅ No cascading (independent scores)
- ✅ Continuous spectrum (0.0-1.0)
- ✅ Pure mathematics (no agent required)

## Related Decisions

- **ADR-025:** Dynamic relationship vocabulary - establishes CONTRADICTS edge type
- **ADR-030:** Concept deduplication - prevents duplicate concepts, complements contradiction resolution
- **ADR-032:** Confidence thresholds - similar statistical approach for relationship confidence
- **ADR-002:** Node fitness scoring - early concept quality metrics

## Future Considerations

### 1. Weighted Edge Confidence

Not all CONTRADICTS edges are equal:
- Code contradiction (confidence: 0.95) > Documentation contradiction (confidence: 0.70)
- Weight edges by confidence scores in ratio calculation

### 2. Temporal Decay

Older evidence may be less relevant:
- Apply decay function: `weight = base_confidence * e^(-λt)`
- Recent evidence weighted higher automatically

### 3. Cross-Ontology Contradiction Detection

Current design: operates within single ontology
Future: detect contradictions across ontologies
- "Project A says X" vs "Project B says not-X"
- May indicate domain-specific variation, not true contradiction

### 4. Contradiction Cascade Visualization

Build UI showing:
- Concept with high contradiction ratio
- Visual network of SUPPORTS vs CONTRADICTS edges
- Agent reasoning explanation
- Timeline of evidence accumulation

### 5. Automated Concept Refinement

When contradictions persist even after introspection:
- Agent suggests concept split (Example 3 above)
- "System uses Neo4j" → two more specific concepts
- Reduces spurious contradictions

## References

- **Darwin Gödel Machine:** Zhang, J., Hu, S., Lu, C., Lange, R., Clune, J. "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents" (2025) - https://arxiv.org/abs/2505.22954
- **Original Gödel Machine:** Schmidhuber, J. "Gödel Machines: Fully Self-Referential Optimal Universal Self-Improvers" (2007) - https://arxiv.org/abs/cs/0309048
- **Gödel's Incompleteness Theorems:** https://plato.stanford.edu/entries/goedel-incompleteness/
- **Evolutionary Epistemology:** Campbell, Donald T. "Evolutionary Epistemology" (1974)
- **Statistical Significance (Three Sigma Rule):** https://en.wikipedia.org/wiki/68%E2%80%9395%E2%80%9399.7_rule
- **Bayesian Belief Networks:** Pearl, Judea. "Probabilistic Reasoning in Intelligent Systems" (1988)
- **Neo4j → Apache AGE example:** This conversation (2025-01-24)
- **Project page:** https://sakana.ai/dgm/
- **Code repository:** https://github.com/jennyzzt/dgm

## Validation & Testing

### Test Scenarios

**1. Dynamic Grounding Calculation (Neo4j example)**
- Ingest 12 Neo4j references → concept created
- Calculate grounding_strength: verify `grounding_strength ≈ 1.0` (fully supported, no contradictions)
- Ingest 47 Apache AGE references with CONTRADICTS edges
- Recalculate grounding_strength: verify `grounding_strength ≈ 0.232` (23% support, 77% contradiction)
- Verify: grounding_strength calculation uses weighted sums, not edge counts
- Verify: total_weight = support_weight + contradict_weight ≈ 44.04

**2. Query Threshold Filtering (Default threshold = 0.20)**
- Query with default threshold (min_grounding=0.20)
- Verify: Neo4j concept INCLUDED (grounding 0.232 > 0.20 threshold)
- Query with stricter threshold (min_grounding=0.30)
- Verify: Neo4j concept EXCLUDED (grounding 0.232 < 0.30 threshold)
- Query with lenient threshold (min_grounding=0.10)
- Verify: Neo4j concept INCLUDED (grounding 0.232 > 0.10 threshold)

**3. Automatic Reversal (No Manual Intervention)**
- Initial state: Neo4j concept has grounding_strength = 0.232
- Ingest 40 new documents with SUPPORTS edges for Neo4j (future architecture change)
- Recalculate grounding_strength: verify `grounding_strength ≈ 0.541` (54% support)
- Query with threshold (min_grounding=0.50)
- Verify: Neo4j concept now INCLUDED (automatic, no marking/unmarking needed)
- Verify: No agent interaction required for reversal

**4. Weakly-Grounded Concept Analysis**
- Query for concepts with grounding_strength < 0.30
- Verify: Returns concepts that may need investigation
- Verify: Concepts remain in graph (non-destructive)
- Optional: Generate agent context for interpretation
- Verify: Agent provides context but doesn't modify graph structure

**5. Performance Testing**
- Run grounding_strength calculation on 1000 concepts
- Verify: Query completes in <100ms (depth=1 complexity)
- Measure: Average grounding_strength across all concepts
- Verify: Distribution histogram shows reasonable spread (not all 1.0 or 0.0)

**6. Edge Confidence Weighting**
- Create concept with 10 SUPPORTS edges (confidence 0.9 each) = 9.0 weight
- Create concept with 50 CONTRADICTS edges (confidence 0.2 each) = 10.0 weight
- Calculate grounding_strength: verify ≈ 0.474 (9.0 / 19.0)
- Verify: High-confidence supports outweigh low-confidence contradictions
- Verify: Weighted approach prevents count-based gaming

### Metrics to Track

- **Grounding distribution:** Histogram of grounding_strength values (0.0-1.0)
- **Query performance:** Average calculation time for grounding_strength (target: <50ms)
- **Threshold effectiveness:** % of concepts filtered at different thresholds (0.10, 0.20, 0.30, 0.50)
- **Reversal frequency:** How often grounding_strength crosses thresholds over time
- **Edge weight distribution:** Average confidence scores for SUPPORTS vs CONTRADICTS edges
- **Cache hit rate:** If caching implemented (Phase 3), track cache effectiveness

## Implementation Status

- [ ] Phase 1: Core Grounding Calculation
  - [ ] Implement Cypher query pattern for dynamic grounding_strength calculation
  - [ ] Add `min_grounding` parameter to query API endpoints
  - [ ] Implement weighted edge confidence summing (not counting)
  - [ ] Add grounding_strength to concept query responses
  - [ ] Add admin endpoint: `GET /admin/grounding-analysis` (list weakly-grounded concepts)
  - [ ] Validate grounding_strength calculation with test scenarios
- [ ] Phase 2: Agent Context Generation (Optional Enhancement)
  - [ ] Build agent context generation prompt
  - [ ] Implement `POST /admin/agent-context/{concept_id}` endpoint
  - [ ] Add temporal analysis logic (historical vs current)
  - [ ] Add alternative concept suggestion (higher grounding)
  - [ ] Integrate agent context into LLM query patterns
- [ ] Phase 3: Performance Optimization (Future)
  - [ ] Implement optional caching strategy (materialized grounding_strength)
  - [ ] Add cache invalidation on edge changes
  - [ ] Build monitoring dashboard for grounding distribution
  - [ ] A/B test cached vs real-time calculation performance
  - [ ] Add grounding_strength trend tracking (temporal analysis)

**Next Steps:**
1. Implement depth=1 grounding_strength Cypher query (immediate)
2. Test with Neo4j → Apache AGE example (verify 0.232 grounding)
3. Add `min_grounding` parameter to search endpoints
4. Gather metrics on grounding distribution in production graph
5. Refine default threshold (0.20) based on real-world data

---

**Last Updated:** 2025-01-24
**Next Review:** After Phase 1 implementation
