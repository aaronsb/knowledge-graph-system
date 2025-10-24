# ADR-044: Probabilistic Truth Convergence Through Contradiction Resolution

**Status:** Proposed
**Date:** 2025-01-24
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
| Empirical validation via coding benchmarks | Empirical validation via edge count analysis |
| Fitness = performance on tasks | Fitness = `1 - contradiction_ratio` |
| Keeps changes that improve benchmark scores | Keeps concepts with low contradiction ratios |
| Rejects changes that hurt performance | Marks concepts with ≥80% contradictions as IRRELEVANT |
| Reversible (can revert bad changes) | Reversible (can reinstate concepts if evidence shifts) |

**In our context:**
- **External system = Real world:** Documents, code, architecture decisions provide empirical evidence
- **Fitness function = Contradiction ratio:** Concepts with ≥80% contradictions empirically fail fitness test
- **Evolutionary selection:** High-contradiction concepts marked IRRELEVANT (removed from active query set)
- **Self-modification:** Graph structure evolves based on statistical evidence, not programmer assertions
- **Empirical validation:** No attempt to "prove" a concept is wrong - just measure contradiction preponderance

**Key quote from DGM paper:**
> "The DGM relaxes the Gödel Machine's impractical requirement of theoretically proving that a change will improve the system, instead requiring empirical evidence from experiments."

**Our application:**
> We relax the requirement of formally proving a concept is "false," instead requiring empirical evidence (contradiction ratio ≥80%) that the concept conflicts with observed reality.

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
- Initially, Neo4j concept has strong support (12 SUPPORTS edges) - it's dominant
- Apache AGE concept emerges with contradictory evidence (47 CONTRADICTS edges against Neo4j)
- Neo4j concept's fitness drops: `contradiction_ratio = 0.80` → fails survival threshold
- Apache AGE concept becomes dominant in the ecosystem

**Natural selection mechanism:**
- Fitness function = contradiction ratio
- Selection pressure = 80% threshold (three sigma)
- Survival = concepts with low contradiction ratios remain ACTIVE
- Extinction = concepts with high contradiction ratios marked IRRELEVANT

**Key insight:** We're not programming truth - we're letting truth emerge from competitive evolutionary pressure based on evidence accumulation.

**Unlike biological evolution:**
- "Extinct" concepts aren't deleted (reversible marking)
- Can be "resurrected" if environment changes (Neo4j might return for multi-region architecture)
- Fitness is recalculated continuously as new evidence arrives

This is **conceptual Darwinism** - ideas survive based on their fit with observable reality, not programmer assertions.

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

### Implement Non-Destructive, Probabilistic Truth Convergence

**Core Principle:** Truth emerges from statistical preponderance of evidence, not absolute certainty.

### Mechanism: Edge Weight Analysis with Statistical Thresholds

**1. Track Contradiction Metrics per Concept**

For any concept node, calculate:

```python
support_edges = count(incoming SUPPORTS relationships)
contradiction_edges = count(incoming CONTRADICTS relationships)
total_edges = support_edges + contradiction_edges

contradiction_ratio = contradiction_edges / total_edges if total_edges > 0 else 0
```

**2. Apply Statistical Threshold (Three Sigma Rule)**

When `contradiction_ratio ≥ 0.80` (80th percentile):
- Concept has **overwhelming contradictory evidence**
- Trigger **introspection agent** for evaluation

**Why 80%?**
- Corresponds to ~1.28σ in normal distribution
- Represents clear statistical signal while avoiding noise
- Requires 4:1 ratio of contradictions to supports (strong evidence shift)

**3. Agent-Based Introspection**

When threshold triggered:

```
Agent retrieves:
  - Highly contradicted concept
  - All adjacent CONTRADICTS edges
  - All adjacent SUPPORTS edges
  - Evidence text from all instances
  - Source documents and dates

Agent reasons:
  "Given evidence that:
   - Neo4j mentioned in 12 documents (2025-10-01 to 2025-10-08)
   - Apache AGE mentioned in 47 documents (2025-10-10 to 2025-01-24)
   - ADR-016 states migration occurred 2025-10-09
   - Current codebase uses age_client.py, not neo4j_client.py

   Recommendation: Mark 'System uses Neo4j' as IRRELEVANT
   Reasoning: Temporal evidence + codebase verification + explicit ADR
   Confidence: 0.95"
```

**4. Non-Destructive Marking**

If agent confidence ≥ 0.90:
- Add `status: IRRELEVANT` property to concept node
- Add `marked_irrelevant_date: timestamp`
- Add `marked_irrelevant_reason: string` (agent's reasoning)
- **Do NOT delete node**
- **Do NOT delete edges**
- **Do NOT delete evidence**

**Effect on queries:**
- Default queries exclude `status: IRRELEVANT` concepts
- Historical queries can include them with flag: `include_irrelevant=true`
- Provenance preserved for audit

### Reversibility: Truth Can Shift Back

**Scenario:** New evidence reverses the contradiction direction

**Example:**
1. System marks "Neo4j" as IRRELEVANT (80% contradictions)
2. Later, 50 new documents describe "Neo4j cluster for HA" (future architecture)
3. New SUPPORTS edges overwhelm old CONTRADICTS edges
4. Recalculated ratio: `contradiction_ratio = 0.15` (now only 15% contradictions)

**Trigger re-evaluation when:**
- Concept marked IRRELEVANT
- New edges added
- Recalculated `contradiction_ratio < 0.30` (reversed threshold)
- Agent introspection with new evidence

**If agent confidence ≥ 0.90 to unmark:**
- Remove `status: IRRELEVANT`
- Add `status: REINSTATED`
- Add `reinstated_date: timestamp`
- Add `reinstated_reason: string`

**Cascading re-evaluation:**
- When concept reinstated, queue adjacent IRRELEVANT concepts for re-evaluation
- Process at lower priority (not urgent)
- Allows graph to "heal" if truth shifts

## Implementation

### Phase 1: Detection & Metrics (Immediate)

**1. Contradiction Analysis Query:**

```cypher
// Find concepts with high contradiction ratios
MATCH (c:Concept)
OPTIONAL MATCH (c)<-[s:SUPPORTS]-()
OPTIONAL MATCH (c)<-[d:CONTRADICTS]-()
WITH c,
     count(DISTINCT s) as support_count,
     count(DISTINCT d) as contradict_count,
     count(DISTINCT s) + count(DISTINCT d) as total_edges
WHERE total_edges > 5  // Minimum edge count for statistical significance
WITH c,
     support_count,
     contradict_count,
     total_edges,
     CASE WHEN total_edges > 0
          THEN toFloat(contradict_count) / toFloat(total_edges)
          ELSE 0.0
     END as contradiction_ratio
WHERE contradiction_ratio >= 0.80
RETURN c.label,
       c.concept_id,
       support_count,
       contradict_count,
       contradiction_ratio
ORDER BY contradiction_ratio DESC, contradict_count DESC
```

**2. Add concept properties:**
```cypher
(:Concept {
  status: "ACTIVE" | "IRRELEVANT" | "REINSTATED",
  marked_irrelevant_date: timestamp,
  marked_irrelevant_reason: text,
  marked_irrelevant_confidence: float,
  reinstated_date: timestamp,
  reinstated_reason: text
})
```

**3. API endpoints:**
- `GET /admin/contradictions` - List high-contradiction concepts
- `POST /admin/introspect/{concept_id}` - Trigger agent evaluation
- `POST /admin/mark-irrelevant/{concept_id}` - Manual override
- `POST /admin/reinstate/{concept_id}` - Manual reinstatement

### Phase 2: Agent Introspection (Near-term)

**Introspection Agent prompt:**

```
You are analyzing a concept in a knowledge graph that has contradictory evidence.

Concept: {label}
Support edges: {support_count}
Contradict edges: {contradict_count}
Contradiction ratio: {contradiction_ratio}

Evidence supporting this concept:
{formatted_support_evidence}

Evidence contradicting this concept:
{formatted_contradict_evidence}

Source documents:
{document_list_with_dates}

Your task:
1. Analyze the temporal pattern (are contradictions newer?)
2. Assess evidence quality (are contradictions more specific/authoritative?)
3. Consider scope (is this historical vs current state?)
4. Recommend: MARK_IRRELEVANT or KEEP_ACTIVE

Provide:
- Decision: MARK_IRRELEVANT | KEEP_ACTIVE
- Confidence: 0.0-1.0
- Reasoning: 2-3 sentence explanation grounded in evidence

Format response as JSON.
```

**Agent uses:**
- OpenAI GPT-4o or Anthropic Claude Sonnet 4
- Temperature: 0.1 (low, for consistency)
- Max tokens: 500
- Retrieves up to 50 evidence instances per concept

### Phase 3: Automated Resolution (Future)

**Background job scheduler:**
- Run contradiction analysis daily
- Queue concepts with `contradiction_ratio ≥ 0.80` for introspection
- Batch process with rate limiting (avoid API cost spikes)
- Log all decisions for audit

**Monitoring metrics:**
- Concepts marked irrelevant per day
- Concepts reinstated per day
- Average contradiction ratio over time
- Agent decision confidence distribution

## Examples

### Example 1: Neo4j → Apache AGE (Actual)

**Initial state (2025-10-08):**
```
(:Concept {label: "System uses Neo4j"})
  ← SUPPORTS ← (12 evidence instances from docs)
  ← SUPPORTS ← (Architecture overview)
  ← SUPPORTS ← (Setup scripts)
```

**After ingestion (2025-01-24):**
```
(:Concept {label: "System uses Neo4j"})
  ← SUPPORTS ← (12 evidence instances from old docs)
  ← CONTRADICTS ← (47 evidence instances from new docs)
  ← CONTRADICTS ← (ADR-016: Migration decision)
  ← CONTRADICTS ← (age_client.py in codebase)
  ← CONTRADICTS ← (README.md: "Apache AGE + PostgreSQL")

Metrics:
  support_edges: 12
  contradict_edges: 47
  contradiction_ratio: 47/59 = 0.797 ≈ 0.80 ✓ THRESHOLD TRIGGERED
```

**Agent introspection:**
```json
{
  "decision": "MARK_IRRELEVANT",
  "confidence": 0.95,
  "reasoning": "Temporal analysis shows Neo4j references end 2025-10-08. ADR-016 explicitly documents migration to Apache AGE on 2025-10-09. Current codebase (age_client.py) and all recent documentation reference Apache AGE. Neo4j represents historical state, not current architecture."
}
```

**Result:**
```
(:Concept {
  label: "System uses Neo4j",
  status: "IRRELEVANT",
  marked_irrelevant_date: "2025-01-24T10:30:00Z",
  marked_irrelevant_reason: "Temporal analysis shows...",
  marked_irrelevant_confidence: 0.95
})
```

**Query behavior:**
```cypher
// Default query (excludes irrelevant)
MATCH (c:Concept)
WHERE c.status <> 'IRRELEVANT' OR c.status IS NULL
RETURN c

// Historical query (includes all)
MATCH (c:Concept)
RETURN c
```

### Example 2: Threshold-Based Confidence Reversal

**Scenario:** Documentation incorrectly states threshold is 0.75

**Initial state:**
```
(:Concept {label: "Similarity threshold is 0.75"})
  ← SUPPORTS ← (Introduction doc: "≥0.75 cosine")
  ← SUPPORTS ← (Research notes: "0.75 default")
```

**After verification:**
```
(:Concept {label: "Similarity threshold is 0.85"})
  ← SUPPORTS ← (age_client.py: threshold=0.85)
  ← SUPPORTS ← (ingestion.py: "≥ 0.85")
  ← SUPPORTS ← (ADR-030: "Match threshold: 80% similarity")
  ← CONTRADICTS → "Similarity threshold is 0.75"

Metrics for "0.75" concept:
  support_edges: 2
  contradict_edges: 3 (from code + docs)
  contradiction_ratio: 3/5 = 0.60  (below 0.80 threshold)
```

**No automatic action** (ratio too low), but manual introspection available.

**Manual resolution:**
- Developer runs: `kg admin introspect similarity-threshold-0-75`
- Agent analyzes: code is authoritative source
- Decision: MARK_IRRELEVANT (confidence: 0.92)

### Example 3: Reversibility - Future Architecture Change

**Current state:**
```
(:Concept {
  label: "System uses Neo4j",
  status: "IRRELEVANT"
})
```

**Future ingestion (2026-06-01):**
- New ADR: "ADR-089: Neo4j Enterprise for Multi-Region HA"
- Architecture docs: "PostgreSQL + AGE for single-region, Neo4j for geo-distributed"
- Deployment guides: "Neo4j cluster configuration"

**Edge changes:**
```
(:Concept {label: "System uses Neo4j"})
  ← SUPPORTS ← (35 new evidence instances about Neo4j cluster)
  ← CONTRADICTS ← (12 old "replaced by AGE" statements)

Recalculated:
  support_edges: 47 (12 old + 35 new)
  contradict_edges: 47 (same)
  contradiction_ratio: 47/94 = 0.50  (dropped from 0.80)
```

**Automatic re-evaluation triggered:**
- `contradiction_ratio < 0.30`? No (it's 0.50)
- Manual introspection available
- Developer decides: Context matters - both are true (AGE for single-region, Neo4j for multi-region)

**Solution:**
- Refine concept: "System uses Neo4j" → split into two concepts
  - "System uses Neo4j for geo-distributed deployment"
  - "System uses Apache AGE for single-region deployment"
- Both ACTIVE, no contradiction

## Consequences

### Positive

✅ **Non-destructive:** Historical information preserved
✅ **Reversible:** Truth can shift as evidence accumulates
✅ **Statistical:** Grounded in quantitative evidence, not arbitrary rules
✅ **Transparent:** Agent reasoning logged and auditable
✅ **Scalable:** Automated detection, human oversight for edge cases
✅ **Philosophically sound:** Acknowledges Gödelian incompleteness
✅ **Query-time filtering:** Default queries exclude noise, historians can include it

### Negative

⚠️ **Agent costs:** Each introspection = 1 LLM API call (~$0.01-0.05)
⚠️ **Threshold tuning:** 80% may need domain-specific adjustment
⚠️ **Cascade complexity:** Reinstating one concept may trigger many re-evaluations
⚠️ **Edge case ambiguity:** What if contradiction_ratio = 0.79? (just below threshold)
⚠️ **Temporal bias:** System favors newer information by default

### Trade-offs

**Precision vs Recall:**
- High threshold (0.90): Few false positives, miss some true contradictions
- Low threshold (0.70): Catch more contradictions, risk marking valid concepts irrelevant
- **Current choice (0.80):** Balance point

**Automation vs Control:**
- Fully automated: Fast, scales, but may make mistakes
- Manual approval: Accurate, but doesn't scale
- **Hybrid approach:** Automated detection + agent recommendation + optional human override

**Deletion vs Marking:**
- Delete: Clean graph, but catastrophic if wrong
- Mark irrelevant: Cluttered graph, but reversible
- **Current choice:** Mark (reversibility > cleanliness)

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

**1. Simple Contradiction (Neo4j example)**
- Ingest 12 Neo4j references → concept created
- Ingest 47 Apache AGE references → contradictions accumulate
- Verify: `contradiction_ratio ≥ 0.80` triggers introspection
- Verify: Agent marks Neo4j as IRRELEVANT
- Verify: Default queries exclude it

**2. Partial Contradiction (Below Threshold)**
- Ingest concept with 60% contradictions
- Verify: No automatic action
- Verify: Manual introspection available
- Verify: Agent can still recommend action

**3. Reversal (Reinstatement)**
- Mark concept IRRELEVANT (80% contradictions)
- Ingest new SUPPORTS edges
- Recalculate: `contradiction_ratio < 0.30`
- Verify: Agent reinstates concept
- Verify: Cascading re-evaluation queued

**4. Historical Query**
- Mark concept IRRELEVANT
- Query with `include_irrelevant=false` (default)
- Verify: Concept excluded
- Query with `include_irrelevant=true`
- Verify: Concept included with status marker

### Metrics to Track

- **Contradiction detection rate:** Concepts flagged per week
- **Agent decision accuracy:** Manual review of 10% sample
- **Reinstatement frequency:** How often truth reverses?
- **Query impact:** Performance with/without irrelevant filtering

## Implementation Status

- [ ] Phase 1: Detection & Metrics
  - [ ] Add contradiction analysis query
  - [ ] Add concept status properties
  - [ ] Add admin API endpoints
  - [ ] Add manual introspection endpoint
- [ ] Phase 2: Agent Introspection
  - [ ] Build introspection agent prompt
  - [ ] Implement agent API integration
  - [ ] Add decision logging
  - [ ] Add manual override capability
- [ ] Phase 3: Automation
  - [ ] Build background scheduler
  - [ ] Implement automated contradiction detection
  - [ ] Add reinstatement triggers
  - [ ] Build monitoring dashboard

**Next Steps:**
1. Implement contradiction analysis query (immediate)
2. Test with Neo4j → Apache AGE example
3. Gather metrics on contradiction frequency in production graph
4. Refine threshold based on real-world data

---

**Last Updated:** 2025-01-24
**Next Review:** After Phase 1 implementation
