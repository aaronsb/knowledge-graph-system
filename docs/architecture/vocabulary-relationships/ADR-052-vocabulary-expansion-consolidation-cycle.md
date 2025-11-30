# ADR-052: Vocabulary Expansion-Consolidation Cycle (The "Dreaming" Pattern)

**Status:** Accepted
**Date:** 2025-10-31
**Authors:** Aaron Bockelie (observation), Claude (documentation)

## Abstract

This document describes an emergent pattern in the vocabulary management system: **optimistic expansion followed by selective consolidation**. This two-phase cycle resembles biological memory consolidation (colloquially: "dreaming"), where vocabulary is acquired freely during learning, then refined during a consolidation phase. This observation grounds a fundamental principle: **you must possess vocabulary (words) to express knowledge (concepts)**, and general learning methods (expand → consolidate) outperform restrictive upfront prediction.

## Overview

Picture your knowledge graph ingesting 100 documents and discovering 245 relationship types—but when you check later, only 197 are actually used in connections between concepts. Did the system waste effort creating 48 unused types? Or was it exploring the semantic space to discover what vocabulary would actually be useful?

This ADR recognizes an emergent two-phase pattern that resembles how humans learn: during "waking" (ingestion), the system freely creates vocabulary whenever the AI suggests a new relationship type, without trying to predict upfront whether it'll be useful. Then during "consolidation" (periodic cleanup), the system reviews what was learned and keeps what's connected while pruning what never found a home. This pattern is grounded in a fundamental principle from learning theory: you must have words before you can express ideas. Trying to predict which words will be useful before seeing the text is harder than just learning broadly and consolidating afterward. The analogy to biological memory is pedagogical—this isn't inspired by neuroscience, but the parallel helps understand why optimistic expansion (low cost: just metadata) followed by selective pruning (based on actual usage) works better than restrictive upfront filtering. Think of it as the system asking "what vocabulary exists in this domain?" during learning, then asking "which vocabulary actually gets used?" during cleanup.

---

## Context

### The Problem Space

Knowledge graphs require a vocabulary of relationship types to express connections between concepts. Two competing approaches exist:

1. **Restrictive (Hand-Coded)**: Predict upfront which vocabulary will be useful, only create what you're "sure" about
2. **Generative (Learned)**: Generate vocabulary freely, consolidate later based on actual usage

### What We Observed

During ingestion, the system creates vocabulary entries **before** knowing if the corresponding relationship will succeed. Analysis of consolidation runs revealed ~48 vocabulary types with `edge_count = 0` (19.6% of total vocabulary). Initial interpretation: "inefficiency that needs fixing."

**Reframing**: This isn't a bug—it's exploration. The system is learning the semantic space.

## Core Principle: Vocabulary Precedes Knowledge

### Theoretical Foundation

**You cannot express what you cannot name.**

To create a relationship like `(ConceptA)-[:FACILITATES_UNDERSTANDING_OF]->(ConceptB)`, the system must first possess the term `FACILITATES_UNDERSTANDING_OF` in its vocabulary. Knowledge representation requires vocabulary as a prerequisite.

This is not speculative—it's provable both theoretically and in practice:
- **Theory**: Graph relationships require typed edges; types must exist before edges
- **Practice**: The ingestion pipeline must call `add_edge_type()` before `create_concept_relationship()`

The question is not *whether* to add vocabulary, but **when and how**.

## The Two-Phase Cycle

### Phase 1: Optimistic Expansion (Learning/Waking State)

**Location**: `src/api/lib/ingestion.py:398-424`

```python
# LLM suggests new relationship type
canonical_type = llm_rel_type.strip().upper()
category = "llm_generated"

# Add to vocabulary OPTIMISTICALLY (before relationship creation)
age_client.add_edge_type(
    relationship_type=canonical_type,
    category=category,
    description=f"LLM-generated relationship type from ingestion",
    ...
)

# THEN try to create the actual relationship
# (may fail - concept not found, validation error, etc.)
age_client.create_concept_relationship(...)
```

**Characteristics**:
- Vocabulary added **before** relationship validation
- LLM free to generate new semantic terms
- No upfront "usefulness" prediction
- Exploration prioritized over precision

**Why This Works**:
1. Subsequent chunks can reuse the term (vocabulary propagation)
2. LLM learns the domain's semantic space
3. Low cost: vocabulary metadata is cheap (just a row + graph node)
4. Aligns with Sutton's Bitter Lesson: general methods > hand-coded restrictions

### Phase 2: Consolidation (Sleep/Dreaming State)

**Location**: `src/api/services/vocabulary_manager.py:871-964` (ADR-050, implemented 2025-10-31)

```python
async def prune_unused_concepts(self, dry_run: bool = False):
    """
    Prune vocabulary types with 0 uses (excludes protected builtin types).

    This is the consolidation phase: review what was learned,
    keep what's connected/used, prune what never found a home.
    """
    for edge_type in edge_types:
        edge_count = info.get('edge_count', 0)
        is_builtin = info.get('is_builtin', False)

        # Skip protected vocabulary
        if is_builtin:
            continue

        # Prune unused exploration
        if edge_count == 0:
            # DELETE unused vocabulary permanently
            ...
```

**Characteristics**:
- Runs during `kg vocab consolidate` (after ingestion phases complete)
- Evaluates actual usage (`edge_count`)
- Protects core vocabulary (`is_builtin = True`)
- Permanently removes unused exploration

**Integration**:
```bash
# Consolidation workflow (default behavior)
kg vocab consolidate --auto
# 1. Merge similar types (semantic consolidation)
# 2. Prune unused types (remove failed exploration)
```

## The Biological Analogy: "Dreaming"

**Note**: This analogy is pedagogical, not a design inspiration. It helps humans understand the process by relating it to familiar biological patterns.

### Memory Consolidation During Sleep

**Waking State (Learning)**:
- Brain makes new synaptic connections freely
- Over-generates connections (exploration)
- Doesn't predict upfront which will be useful
- Optimizes for breadth, not precision

**REM Sleep (Testing)**:
- Rehearses connections in random combinations
- Tests which patterns are coherent
- Doesn't modify yet, just evaluates

**Deep Sleep (Consolidation)**:
- Strengthens frequently-used connections
- Prunes weak/unused synapses (synaptic homeostasis)
- Optimizes for long-term retention

### Our System's Parallel

**Ingestion (Learning)**:
- Generate vocabulary optimistically
- Create edges when concepts match
- Don't restrict vocabulary upfront
- Explore the semantic space

**Use (Testing)**:
- Attempt to create relationships
- Some succeed (edge created)
- Some fail (vocabulary unused)
- Natural selection by utility

**Consolidation (Sleep)**:
- Review vocabulary usage
- Merge similar terms (semantic compression)
- Prune unused terms (remove failed exploration)
- Optimize for efficiency

## Connection to Sutton's Bitter Lesson

From [*The Bitter Lesson*](http://incompleteideas.net/IncIdeas/BitterLesson.html) (Sutton, 2019):

> "The biggest lesson that can be read from 70 years of AI research is that general methods that leverage computation are ultimately the most effective."

### Hand-Coded Approach (Fights the Lesson)

```python
# BAD: Try to predict upfront if vocabulary will be useful
if predict_relationship_will_succeed(rel_type):
    add_edge_type(rel_type)  # Only add if "sure"
    create_relationship(...)
else:
    skip()  # Don't explore uncertain vocabulary
```

**Problems**:
- Requires hand-coded prediction logic
- Limits exploration to "safe" vocabulary
- Misses emergent semantic patterns
- Doesn't scale with computation

### General Method (Embraces the Lesson)

```python
# GOOD: Generate broadly, consolidate selectively
add_edge_type(rel_type)  # Optimistic expansion (cheap)
try:
    create_relationship(...)  # Natural selection by use
except:
    pass  # Failed exploration (pruned later)

# Later: Consolidation phase removes unused
consolidate_vocabulary()  # Leverage computation to prune
```

**Advantages**:
- No hand-coded restrictions
- Explores full semantic space
- Emergent vocabulary from actual use
- Scales with data and computation

## Implementation Evidence

### Consolidation Run (2025-10-31)

```
Initial Size:     245 types
Final Size:       197 types
Total Reduction:  -48 types (19.6%)

Breakdown:
  Merged:    86 pairs (semantic consolidation)
  Rejected:  37 pairs (not similar enough)
  Pruned:    48 types (unused exploration)
```

**Interpretation**:
- 48 types (19.6%) never created an actual edge
- These represent exploration that didn't connect
- System learned 245 potential semantic terms
- Consolidated to 197 actively-used terms
- The exploration cost was negligible (just metadata)

### Code Locations

| Phase | Location | Function |
|-------|----------|----------|
| **Expansion** | `src/api/lib/ingestion.py:408` | `age_client.add_edge_type()` |
| **Validation** | `src/api/lib/ingestion.py:438` | `create_concept_relationship()` |
| **Consolidation** | `src/api/services/vocabulary_manager.py:871` | `prune_unused_concepts()` |
| **Integration** | `src/api/routes/vocabulary.py:429` | Consolidation endpoint |

## Consequences

### Positive

1. **Vocabulary Freedom**: LLM can generate any semantic term without restriction
2. **Natural Selection**: Vocabulary utility determined by actual use, not prediction
3. **Exploration Cost**: Minimal (vocabulary metadata is cheap vs. prediction logic)
4. **Emergent Semantics**: Domain vocabulary emerges from data, not hand-coding
5. **Scalability**: More data + computation = better vocabulary, automatically
6. **Biological Plausibility**: Mirrors human learning (expand → consolidate)

### Negative

1. **Temporary Bloat**: Vocabulary grows during ingestion, must be consolidated
2. **Consolidation Required**: Not optional—must run to prevent unbounded growth
3. **Two-Phase Workflow**: Can't know "final" vocabulary until consolidation

### Neutral

1. **Metrics Interpretation**: High pruning % isn't "waste"—it's exploration breadth
2. **Consolidation Frequency**: Determined by vocabulary growth rate (configurable)

## Design Principles

### 1. Vocabulary Precedes Knowledge

**Principle**: You must have words before you can express ideas.

**Implementation**: Always create vocabulary before attempting relationships.

### 2. Optimistic Generation

**Principle**: Generate broadly, validate later (Sutton's Bitter Lesson).

**Implementation**: Don't predict upfront—add vocabulary optimistically, let use determine value.

### 3. Selective Consolidation

**Principle**: Prune based on evidence, not prediction.

**Implementation**: Remove vocabulary with `edge_count = 0` after learning phases.

### 4. Protect Core Knowledge

**Principle**: Some vocabulary is foundational, must never be pruned.

**Implementation**: `is_builtin = True` types are protected during consolidation.

## Future Enhancements

### 1. Usage-Weighted Pruning

Currently: Binary (used vs. unused)

**Future**: Weight by usage frequency
```python
# Prune aggressively if rarely used
if edge_count < 3:  # Low-usage threshold
    prune()
```

### 2. Temporal Decay

Currently: All-time usage counts

**Future**: Recent usage matters more
```python
# Prune if not used recently
if last_used < 90_days_ago:
    prune()
```

### 3. Consolidation Triggers

Currently: Manual (`kg vocab consolidate`)

**Future**: Automatic triggers (ADR-050 scheduled jobs)
```python
# Trigger when vocabulary bloat exceeds threshold
if inactive_ratio > 0.20:
    schedule_consolidation()
```

### 4. Vocabulary Reactivation

Currently: Deleted vocabulary is gone forever

**Future**: Archive + reactivate pattern
```python
# If pruned vocabulary gets reused, reactivate
if archived_type_matches(new_type):
    reactivate(archived_type)
```

### 5. Grounding-Aware Vocabulary Classification (ADR-044 Integration)

**The Insight**: Vocabulary used primarily in low-grounding concepts is not "toxic" to be pruned—it's **dialectically essential** for reasoning.

#### Shannon's Information Theory: Noise Carries Information

**Shannon's fundamental insight**: Both signal AND noise carry information about a system.

In our vocabulary:
- **High-grounding vocabulary** (avg grounding > 0.80): Signal—describes well-supported reality
- **Low-grounding vocabulary** (avg grounding < 0.40): Noise in truth-seeking, but **signal in reasoning**
  - Tells us what was tried and refuted
  - Tells us what alternatives were considered
  - Enables counterfactual reasoning ("what if?")
  - Preserves the error signal for learning

**Example:**
```python
# Vocabulary type: "CONTRADICTS"
edges_using_CONTRADICTS = [
    ("System uses Neo4j" → "System uses Apache AGE", grounding_target: 0.23),
    ("Similarity threshold 0.75" → "Similarity threshold 0.85", grounding_target: 0.28),
    ...
]

avg_grounding = 0.25  # Low grounding!

# WRONG: Prune "CONTRADICTS" because it only connects refuted concepts
# RIGHT: "CONTRADICTS" is ESSENTIAL for expressing contradiction itself!
```

**Pruning low-grounding vocabulary destroys the capacity to reason about alternatives.**

#### Hegelian Dialectic: Synthesis Requires Thesis + Antithesis

**Dialectical reasoning** (Hegel, 1807) requires vocabulary for expressing opposition:

```
Thesis:     "System uses Neo4j" (SUPPORTS edges)
Antithesis: "System uses Apache AGE" (CONTRADICTS edges)
Synthesis:  "System migrated from Neo4j to AGE in October 2025"
```

**To construct synthesis, you NEED vocabulary describing both:**
- `SUPPORTS` - affirms current truth (high grounding)
- `CONTRADICTS` - expresses conflict (low grounding on refuted side)
- `REPLACED_BY` - describes transition (moderate grounding)
- `HISTORICALLY_USED` - preserves context (low grounding on old state)

**Without contradiction vocabulary** → no dialectical reasoning → no synthesis → no understanding of change.

#### The Correct Enhancement: Classification, Not Pruning

**Current pruning criterion** (correct):
```python
if edge_count == 0:
    prune()  # Unused = expresses nothing
```

**WRONG approach** (what we almost did):
```python
if avg_grounding < 0.20:
    prune()  # "Toxic" vocabulary ❌ DESTROYS REASONING CAPABILITY
```

**CORRECT approach** (grounding-aware classification):
```python
# Calculate epistemic status based on average grounding of connected concepts
for vocab_type in active_vocabulary:
    edges = get_edges_using_vocabulary_type(vocab_type)

    if len(edges) == 0:
        prune("unused")  # Only criterion for pruning
        continue

    # Calculate grounding profile (ADR-044)
    groundings = [
        grounding_strength(edge.target_concept)
        for edge in edges
    ]

    avg_grounding = mean(groundings)
    max_grounding = max(groundings)

    # CLASSIFY epistemic status, don't prune
    vocab_type.epistemic_status = classify_epistemic_status(avg_grounding)
    vocab_type.grounding_stats = {
        'avg': avg_grounding,
        'max': max_grounding,
        'distribution': histogram(groundings)
    }

def classify_epistemic_status(avg_grounding):
    """
    Classify vocabulary by the typical grounding of concepts it connects.

    All roles are VALUABLE - none should be pruned based on grounding.
    """
    if avg_grounding > 0.80:
        return "AFFIRMATIVE"
        # Describes well-supported concepts
        # Examples: ENABLES, SUPPORTS, COMPOSED_OF

    elif avg_grounding > 0.40:
        return "CONTESTED"
        # Describes evolving understanding
        # Examples: ALTERNATIVE_TO, COMPETES_WITH

    elif avg_grounding > 0.20:
        return "HISTORICAL"
        # Describes past states or outdated concepts
        # Examples: REPLACED_BY, HISTORICALLY_USED, DEPRECATED_BY

    else:
        return "CONTRADICTORY"
        # Describes refuted concepts or conflicts
        # Examples: CONTRADICTS, DISPROVEN_BY, REFUTED_BY

    # ALL roles preserved - dialectical reasoning requires the full spectrum
```

#### Capabilities Enabled by Classification

**1. Contextual Query Filtering:**
```cypher
// Show me contradictory relationships (explore alternatives)
MATCH (c1)-[r]-(c2)
WHERE r.epistemic_status = 'CONTRADICTORY'
RETURN c1, r, c2

// Show me historical evolution (how did we get here?)
MATCH (c1)-[r]-(c2)
WHERE r.epistemic_status = 'HISTORICAL'
RETURN c1, r, c2
```

**2. Dialectical Analysis:**
```python
# Synthesize understanding from thesis + antithesis
thesis = concepts_with_role("AFFIRMATIVE")
antithesis = concepts_with_role("CONTRADICTORY")
synthesis = generate_synthesis(thesis, antithesis)
```

**3. Error Tracking:**
```python
# What was tried and why did it fail?
refuted_concepts = get_concepts(grounding < 0.20)
reasons = get_edges_to(refuted_concepts, role="CONTRADICTORY")
```

**4. Counterfactual Reasoning:**
```python
# What if we had chosen alternative X?
alternatives = get_edges(type="ALTERNATIVE_TO")
explore_counterfactual(alternative)
```

#### Pruning Remains Binary: Used vs. Unused

**The only valid pruning criterion:**
```
edge_count == 0  →  PRUNE (expresses nothing)
edge_count > 0   →  KEEP (classifies by grounding role)
```

**Why grounding doesn't determine pruning:**
- Low grounding ≠ useless
- Low grounding = describes refuted/historical/alternative concepts
- Refuted concepts are informationally valuable (what NOT to do)
- Historical concepts enable temporal reasoning (how we got here)
- Alternative concepts enable comparative reasoning (what else could work)

**The error is the signal** - pruning low-grounding vocabulary eliminates the system's ability to learn from mistakes and reason about change.

#### Information-Theoretic Justification

From Shannon (1948), mutual information between vocabulary and concepts:

```
I(Vocabulary; Concepts) = H(Concepts) - H(Concepts | Vocabulary)
```

Where:
- `H(Concepts)` = entropy of concept space (what concepts exist)
- `H(Concepts | Vocabulary)` = conditional entropy (uncertainty given vocabulary)

**High-grounding vocabulary** reduces uncertainty about **current truth**:
- "What is true now?" → AFFIRMATIVE vocabulary provides strong signal

**Low-grounding vocabulary** reduces uncertainty about **reasoning process**:
- "What was true?" → HISTORICAL vocabulary provides temporal signal
- "What alternatives exist?" → CONTRADICTORY vocabulary provides comparative signal
- "How did truth change?" → CONTESTED vocabulary provides evolutionary signal

**Pruning low-grounding vocabulary increases conditional entropy** for reasoning tasks:
- Lose ability to reason about change
- Lose ability to reason about alternatives
- Lose ability to learn from errors

**All vocabulary roles reduce entropy in different dimensions** - pruning based on grounding is informationally destructive.

#### Implementation Sketch

**Phase 1**: Calculate grounding statistics per vocabulary type
```python
# For each active vocabulary type
for vocab_type in vocabulary:
    edges = edges_of_type(vocab_type)
    if not edges:
        continue

    # Calculate grounding distribution
    groundings = [
        grounding_strength(edge.target_concept)
        for edge in edges
    ]

    stats = {
        'count': len(edges),
        'avg_grounding': mean(groundings),
        'median_grounding': median(groundings),
        'max_grounding': max(groundings),
        'min_grounding': min(groundings),
        'std_grounding': std(groundings)
    }

    # Store as vocabulary metadata (ADR-048)
    update_vocab_type(vocab_type, grounding_stats=stats)
```

**Phase 2**: Classify epistemic statuses
```python
# Assign role based on average grounding
vocab_type.epistemic_status = classify_epistemic_status(
    stats['avg_grounding']
)
```

**Phase 3**: Enable role-based querying
```cypher
// Find all vocabulary describing contradictions
MATCH (v:VocabType)
WHERE v.epistemic_status = 'CONTRADICTORY'
RETURN v.name, v.grounding_stats

// Find all vocabulary describing current truth
MATCH (v:VocabType)
WHERE v.epistemic_status = 'AFFIRMATIVE'
RETURN v.name, v.grounding_stats
```

**Phase 4**: Dialectical query patterns
```cypher
// Find thesis-antithesis pairs for synthesis
MATCH (thesis:Concept)-[r_contradict:CONTRADICTS]->(antithesis:Concept)
WHERE grounding_strength(thesis) > 0.20
  AND grounding_strength(antithesis) > 0.20
RETURN thesis, antithesis
// Both concepts have moderate grounding → contested domain, needs synthesis
```

#### Related ADRs

- **ADR-044**: Probabilistic Truth Convergence (provides grounding_strength metric)
- **ADR-045**: Unified Embedding Generation (enables grounding calculation)
- **ADR-046**: Grounding-Aware Vocabulary Management (usage tracking with quality metrics)

## Related Work

### Academic Parallels

1. **Synaptic Homeostasis Hypothesis** (Tononi & Cirelli, 2014): Sleep downscales synaptic strength to maintain cognitive capacity
2. **Memory Consolidation** (Stickgold, 2005): Sleep reorganizes and strengthens memory traces
3. **Constructive Memory** (Schacter, 1999): Memory is reconstructive, not reproductive

### System Parallels

1. **Garbage Collection** (McCarthy, 1960): Automatic memory reclamation based on reachability
2. **Generational Hypothesis**: Young objects die young, old objects persist (similar to our usage-based pruning)
3. **Mark-and-Sweep**: Two-phase memory management (mark live objects, sweep dead ones)

## References

- **Sutton, R.** (2019). *The Bitter Lesson*. [http://incompleteideas.net/IncIdeas/BitterLesson.html](http://incompleteideas.net/IncIdeas/BitterLesson.html)
- **Shannon, C. E.** (1948). A mathematical theory of communication. *Bell System Technical Journal*, 27(3), 379-423.
- **Hegel, G. W. F.** (1807). *Phänomenologie des Geistes* (Phenomenology of Spirit). Translated by A.V. Miller (1977). Oxford University Press.
- **Tononi, G., & Cirelli, C.** (2014). Sleep and the price of plasticity. *Neuron*, 81(1), 12-34.
- **Stickgold, R.** (2005). Sleep-dependent memory consolidation. *Nature*, 437, 1272-1278.
- **McCarthy, J.** (1960). Recursive functions of symbolic expressions and their computation by machine. *Communications of the ACM*, 3(4), 184-195.

## Related ADRs

- **ADR-025**: Dynamic Relationship Vocabulary (foundation for vocabulary expansion)
- **ADR-032**: Automatic Edge Vocabulary Expansion (optimistic generation strategy)
- **ADR-046**: Grounding-Aware Vocabulary Management (usage tracking)
- **ADR-047**: Probabilistic Vocabulary Categorization (semantic classification)
- **ADR-050**: Scheduled Jobs System (automation framework for consolidation)

---

**Last Updated**: 2025-10-31
**Status**: Accepted (pattern observed and documented)
**Implementation**: Complete (`prune_unused_concepts()` implemented 2025-10-31)
