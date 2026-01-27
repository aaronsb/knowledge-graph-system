---
status: Accepted
date: 2025-10-26
deciders: System Architects
related:
  - ADR-044
  - ADR-025
  - ADR-022
  - ADR-048
---

# ADR-047: Probabilistic Vocabulary Categorization

- Migration 015: Schema fields for category scoring
- VocabularyCategorizer class: Core categorization logic
- Integrated into ingestion pipeline: add_edge_type() auto-categorizes new types
- Integrated into graph updates: VocabularyCategorizer updates :IN_CATEGORY relationships
- CLI commands: kg vocab refresh-categories (default: all types), kg vocab category-scores
- Embedding worker: Unified embedding generation for vocabulary and concepts
- Result: All 47 types properly categorized (30 builtin + 17 custom) with confidence scores

## Overview

When your AI learns a new relationship type like "HARMONIZES_WITH", which semantic category does it belong to? Is it about composition (how things fit together), interaction (how things affect each other), or something else entirely? The original system only knew how to categorize the 30 hand-picked relationship types—everything the AI discovered got dumped into a generic "llm_generated" bucket, losing valuable semantic information.

This ADR solves the categorization problem using the same embedding technology that powers concept matching. Think of it like having reference examples for each category: "causation" is defined by types like CAUSES and ENABLES, "composition" by PART_OF and CONTAINS. When a new type appears, the system generates its embedding vector (a mathematical representation of its meaning) and compares it to the embeddings of these reference types, asking "which category is this most similar to?" The result is probabilistic—a type might be 73% composition and 21% interaction, revealing semantic ambiguity. This automatic categorization happens immediately when new types are discovered, organizing your growing vocabulary without manual classification. The system can now filter queries by relationship category (show me all causal connections), detect when vocabulary is drifting toward certain semantic areas, and explain to users what kind of relationship "HARMONIZES_WITH" actually represents.

---

## Context

The relationship vocabulary system currently has two classification approaches:

**Builtin Types (30 types):** Hand-assigned semantic categories
```
CAUSES        → causation
COMPOSED_OF   → composition
IMPLIES       → logical
SUPPORTS      → evidential
...
```

**LLM-Generated Types (88+ types):** Generic "llm_generated" category
```
ENHANCES      → llm_generated  ❌ Not semantically useful
INTEGRATES    → llm_generated  ❌ Can't distinguish from ENHANCES
CONFIGURES    → llm_generated  ❌ Lost semantic information
...
```

### The Problem

Without meaningful categories, the system cannot:
- **Match relationships semantically** during extraction (Is "improves" similar to "enhances"?)
- **Filter graph traversals** by relationship type (Show me all causal relationships)
- **Explain relationships** to users (What kind of relationship is CONFIGURES?)
- **Detect category drift** (Are we generating too many causal vs structural types?)

### The Fundamental Constraint

The core challenge is **distilling unbounded semantic space into bounded knowledge**:

> We are essentially distilling a bunch of relationships that mean infinite things possibly, and satisficing it into a structure with bounded knowledge (our vocabulary).

LLMs can generate unlimited relationship variants (ENHANCES, AUGMENTS, STRENGTHENS, AMPLIFIES, BOOSTS...), but humans need a **bounded, semantically meaningful vocabulary** to understand and work with the graph. We can't enumerate all possible relationships, but we can satisfice them into 8 interpretable categories using our 30 hand-validated seed types as anchors.

This is fundamentally a **lossy compression** problem: preserve semantic utility while discarding infinite variation.

### Failed Approach: Fixed Classification

**Attempt 1:** Manually classify all 88 types
- **Problem:** Subjective, time-consuming, doesn't scale
- **Result:** Abandoned - too much manual work

**Attempt 2:** LLM auto-classification
- **Problem:** Adds LLM dependency, inconsistent, needs validation
- **Result:** Violates principle of avoiding LLM for metadata

## Decision

Implement **probabilistic category assignment** using embedding similarity - the same pattern that succeeded with grounding strength (ADR-044).

### Core Principle

> Categories emerge from semantic similarity to seed types, not fixed assignments.

Just as grounding scores emerge from SUPPORTS/CONTRADICTS relationships, categories emerge from similarity to the 30 builtin "seed" types.

### Architecture

**1. Seed Types (30 Builtin Types)**

These are the ground truth for each category:

```python
CATEGORY_SEEDS = {
    'causation': ['CAUSES', 'ENABLES', 'PREVENTS', 'INFLUENCES', 'RESULTS_FROM'],
    'composition': ['PART_OF', 'CONTAINS', 'COMPOSED_OF', 'SUBSET_OF', 'INSTANCE_OF'],
    'logical': ['IMPLIES', 'CONTRADICTS', 'PRESUPPOSES', 'EQUIVALENT_TO'],
    'evidential': ['SUPPORTS', 'REFUTES', 'EXEMPLIFIES', 'MEASURED_BY'],
    'semantic': ['SIMILAR_TO', 'ANALOGOUS_TO', 'CONTRASTS_WITH', 'OPPOSITE_OF'],
    'temporal': ['PRECEDES', 'CONCURRENT_WITH', 'EVOLVES_INTO'],
    'dependency': ['DEPENDS_ON', 'REQUIRES', 'CONSUMES', 'PRODUCES'],
    'derivation': ['DERIVED_FROM', 'GENERATED_BY', 'BASED_ON']
}
```

**2. Category Assignment via Embedding Similarity**

For each LLM-generated type:

```python
def compute_category_scores(relationship_type: str) -> Dict[str, float]:
    """
    Compute similarity to each category's seed types.

    Returns dict like:
    {
        'causation': 0.85,    # ENHANCES is very similar to ENABLES
        'composition': 0.45,  # Less similar to CONTAINS
        'logical': 0.23,      # Not similar to IMPLIES
        ...
    }
    """
    type_embedding = get_embedding(relationship_type)

    category_scores = {}
    for category, seed_types in CATEGORY_SEEDS.items():
        # Compute similarity to all seeds in this category
        similarities = [
            cosine_similarity(type_embedding, get_embedding(seed))
            for seed in seed_types
        ]
        # Category score = max similarity to any seed
        category_scores[category] = max(similarities)

    return category_scores

# Example:
scores = compute_category_scores("ENHANCES")
# => {'causation': 0.85, 'composition': 0.45, 'logical': 0.23, ...}

assigned_category = max(scores, key=scores.get)
confidence = scores[assigned_category]
# => category='causation', confidence=0.85
```

### Satisficing Strategy (Herbert Simon)

This algorithm uses **satisficing** (accept "good enough" vs. optimal):

**Why `max()` instead of `mean()`:**

```python
# Example: ENHANCES vs causation seeds
similarities = {
    'ENABLES':    0.87,  # Very similar! (same polarity)
    'CAUSES':     0.72,  # Similar
    'PREVENTS':   0.12,  # Opposite polarity (but still causal!)
    'INFLUENCES': 0.65   # Similar
}

max(similarities)  = 0.87  ✓ Satisficing: "Found one good match!"
mean(similarities) = 0.59  ✗ Optimizing: Wrongly penalized by PREVENTS
```

Categories contain **opposing polarities** (ENABLES vs PREVENTS are both causal). Max satisfices: "Is this semantically similar to ANY seed? Yes? Good enough!"

### Confidence Thresholds

Accept "good enough" based on confidence:

- **High (≥ 70%):** Auto-categorize confidently
- **Medium (50-69%):** Auto-categorize with warning
- **Low (< 50%):** Flag for curator review (possible new seed needed)

### Ambiguity Detection

When runner-up score is close to winner (> 0.70), flag as multi-category candidate:

```python
primary = max(scores, key=scores.get)
runner_up_score = sorted(scores.values(), reverse=True)[1]

if runner_up_score > 0.70:
    logger.info(f"Ambiguous: {type} could be {primary} OR {runner_up_category}")
    # Store category_ambiguous: true for future multi-category support
```

**3. Storage Schema**

Update `relationship_vocabulary` table:

```sql
ALTER TABLE relationship_vocabulary
ADD COLUMN category_source VARCHAR(20) DEFAULT 'computed',  -- 'builtin' or 'computed' (no overrides)
ADD COLUMN category_confidence FLOAT,  -- 0.0 to 1.0
ADD COLUMN category_scores JSONB,  -- Full score breakdown
ADD COLUMN category_ambiguous BOOLEAN DEFAULT false;  -- True if runner-up > 0.70

CREATE INDEX idx_relationship_category ON relationship_vocabulary(category);
CREATE INDEX idx_category_confidence ON relationship_vocabulary(category_confidence);

-- Example row:
-- type: ENHANCES
-- category: causation
-- category_source: computed
-- category_confidence: 0.85
-- category_scores: {"causation": 0.85, "composition": 0.45, "logical": 0.23, ...}
```

**4. Cache and Refresh**

Category assignments are cached but can be recomputed:

```python
# Compute once on vocabulary insert
INSERT INTO relationship_vocabulary (type, category, category_source, category_confidence)
VALUES ('ENHANCES', 'causation', 'computed', 0.85);

# Recompute on demand
kg vocab refresh-categories
# Recalculates all 'computed' categories based on current embeddings
```

**When to refresh categories:**

1. **After vocabulary merges** (vocabulary topology changes):
   ```bash
   kg vocab merge STRENGTHENS ENHANCES  # Consolidate synonyms
   kg vocab refresh-categories          # Recalculate with cleaner landscape
   ```

2. **After embedding model changes** (semantic space shifts):
   ```bash
   kg admin embedding set --model nomic-embed-text
   kg admin embedding regenerate --vocabulary
   kg vocab refresh-categories  # Automatically triggered
   ```

3. **After seed adjustments** (category definitions change):
   ```bash
   # If CATEGORY_SEEDS updated in code
   kg vocab refresh-categories  # Recalculate with new seeds
   ```

### CLI Integration

**Display categories with confidence:**

```bash
$ kg vocab list

TYPE          CATEGORY    EDGES  STATUS  CONFIDENCE
CAUSES        causation      91  ✓       builtin
ENHANCES      causation      28  ✓       85%
INTEGRATES    composition    15  ✓       78%
CONFIGURES    dependency      3  ✓       72%
MYSTERIOUS    causation       1  ✓       45%  ⚠ low confidence
```

**Show category breakdown:**

```bash
$ kg vocab category-scores ENHANCES

Similarity to category seeds:
  causation:    0.85  ███████████████████  (closest: ENABLES 0.87)
  composition:  0.45  █████████
  dependency:   0.38  ████████
  semantic:     0.31  ██████
  logical:      0.23  █████
  evidential:   0.19  ████
  temporal:     0.12  ██
  derivation:   0.08  ██

Assigned: causation (85% confidence)
```

### Ecological Pruning Workflow

Categories enable **ecological vocabulary management** without curator overrides.

**Core Philosophy:**
> The graph is timeless. Vocabulary is part of the graph.
> Curators observe current state, prune weak connections, let strong ones emerge.

**Vocabulary State (Timeless):**
- Types exist, connected to concepts via edges
- Edge count reflects usage (connection strength)
- Category confidence reflects cluster fit
- Strong types accumulate edges, weak types remain sparse

**Integrated Workflow with ADR-032 (Pruning) and ADR-046 (Synonym Detection):**

```bash
# 1. OBSERVE current state
kg vocab list
# ENHANCES:     causation, 87% confidence, 47 edges
# STRENGTHENS:  causation, 86% confidence, 12 edges
# SUPPORTS:     evidential, 91% confidence, 38 edges
# MYSTERIOUS:   causation, 45% confidence, 1 edge

# 2. FIND pruning candidates (ADR-047 categories reveal)
kg vocab find-synonyms --category causation --threshold 0.85
# ENHANCES ↔ STRENGTHENS: 0.89 similarity (same category)

kg vocab prune-candidates
# MYSTERIOUS: orphan (confidence < 50%, edge_count = 1)

# 3. MERGE synonyms (ADR-046)
kg vocab merge STRENGTHENS ENHANCES
# ENHANCES now has 59 edges (47 + 12)
# Result: 88 → 87 types

# 4. REFRESH categories (ADR-047)
kg vocab refresh-categories
# Recomputes with cleaner vocabulary topology
# ENHANCES confidence may shift (embedding landscape changed)

# 5. DEPRECATE weak types (ADR-032)
kg vocab deprecate MYSTERIOUS
# Result: 87 → 86 types

# 6. OBSERVE new state
kg vocab list
# ENHANCES: 59 edges (stronger)
# Fewer types, denser connections
# System converging on strong vocabulary
```

**What Categories Reveal:**

| Insight | Action | ADR |
|---------|--------|-----|
| **Orphans** (confidence < 50%, low edges) | Deprecate weak types | ADR-032 |
| **Synonyms** (same category, similarity > 0.85) | Merge redundant types | ADR-046 |
| **Imbalances** (40 causation, 3 temporal) | Need better seed diversity | ADR-047 |
| **Bridges** (ambiguous, runner-up > 0.70) | Keep valuable connectors | ADR-047 |

**Why No Curator Overrides:**

Categories are **computed from current embeddings and seeds**:
- Override = frozen state that doesn't evolve with system
- Model upgrades → embeddings change → override blocks benefits
- Vocabulary merges → topology changes → override becomes stale
- Better: Curators adjust seeds/topology, categories recompute

**Emergent Signal:**
After compaction, strong types accumulate more edges (reinforcement). System naturally converges on fewer, stronger vocabulary through graph dynamics, not temporal metrics.

## Consequences

### Positive

**1. No LLM Required**
- Uses embeddings we already generate
- Fast, deterministic, reproducible

**2. Scales Automatically**
- New LLM types get categorized immediately
- No manual classification backlog

**3. Semantic Accuracy**
- ENHANCES → causation (similar to ENABLES)
- INTEGRATES_WITH → composition (similar to COMPOSED_OF)
- Reflects actual semantic relationships

**4. Confidence Scores**
- Know when categorization is uncertain
- Low confidence → might need new category seed

**5. Follows Grounding Pattern**
- Probabilistic (scores not binary)
- Evidence-based (similarity to seeds)
- Query-time or cached (flexible)
- Transparent (show the math)

### Negative

**1. Embedding Model Changes**
- Requires embedding model consistency within a deployment
- Changing models triggers automatic recalculation:
  - `kg admin embedding regenerate --vocabulary` → `kg vocab refresh-categories` (automatic)
  - Categories recompute with new embeddings
  - Current state reflects current model (timeless)

**2. Seed Type Quality**
- Categories only as good as seed types
- Poorly chosen seeds = poor categorization

**3. Ambiguous Types**
- Some types genuinely span multiple categories
- Need threshold for "low confidence" warning

**4. Initial Computation**
- 88 types × 30 seeds = 2,640 similarity calculations
- Amortized via caching

### Neutral

**1. Category Evolution**
- Categories recompute when vocabulary topology changes (merges, model changes)
- Current state always reflects current embeddings and seeds
- No historical tracking needed (graph is timeless)

**2. New Categories**
- System can detect "orphan" types (low scores across all categories)
- Signals need for new category seed or vocabulary pruning

## Implementation Plan

### Phase 0: Seed Validation (Optional, Week 1)
- [ ] Compute pairwise similarity of seeds within each category
- [ ] Ensure seeds cluster (intra-category similarity > 0.65)
- [ ] Flag seeds that are outliers or better fit in different categories
- [ ] Document seed validation results

### Phase 1: Foundation (Week 1)
- [ ] Add schema columns (category_source, category_confidence, category_scores, category_ambiguous)
- [ ] Add indexes (idx_relationship_category, idx_category_confidence)
- [ ] Implement `compute_category_scores()` function with satisficing (max similarity)
- [ ] Add category assignment to vocabulary insert logic

### Phase 2: Batch Categorization (Week 1)
- [ ] Compute categories for existing 88 llm_generated types
- [ ] Store scores in database
- [ ] Verify accuracy on sample types
- [ ] Identify ambiguous types (runner-up > 0.70)

### Phase 3: CLI Integration (Week 1)
- [ ] Update `kg vocab list` to show confidence and ambiguous flag
- [ ] Add `kg vocab category-scores <TYPE>` command
- [ ] Add `kg vocab refresh-categories` command
- [ ] Add `kg vocab prune-candidates` command
- [ ] Add `kg vocab find-synonyms` command

### Phase 4: Validation (Week 2)
- [ ] Compare computed categories to manual review
- [ ] Identify low-confidence types (< 50%)
- [ ] Determine if new category seeds needed
- [ ] Test merge → refresh workflow

### Phase 5: Orphan Detection (Week 2)
- [ ] Implement `kg vocab find-orphans` command
- [ ] Definition: types with max_score < 50% across all categories
- [ ] Output recommendations (new seed? deprecate? merge?)
- [ ] Integrate with ecological pruning workflow

## Alternatives Considered

### Alternative 1: Manual Classification
**Rejected:** Doesn't scale, subjective, high maintenance

### Alternative 2: LLM Auto-Classification
**Rejected:** Adds LLM dependency for metadata (anti-pattern)

### Alternative 3: Hybrid (Embeddings + LLM validation)
**Rejected:** Unnecessary complexity, embeddings alone sufficient

### Alternative 4: Multi-Category Assignment
Allow types to have multiple categories (e.g., ENHANCES = 85% causal, 45% compositional)

**Deferred:** Start with single category (highest score), add multi-category if needed

## Success Criteria

1. **All llm_generated types get meaningful categories** (not generic "llm_generated")
2. **Category confidence ≥ 70%** for 80% of types
3. **No LLM calls** for category assignment
4. **Performance targets:**
   - Single type categorization: < 50ms (on vocab insert)
   - Batch refresh (all 118 types): < 1s
   - Category-scores CLI output: < 100ms
5. **User can understand** why a type got its category (`kg vocab category-scores`)
6. **Vocabulary convergence:** Strong types accumulate edges, weak types remain sparse (observable from current state)

## Example Categorization

Based on embedding similarity to seeds:

```
ENHANCES       → causation    (87% - very similar to ENABLES)
INTEGRATES     → composition  (82% - similar to COMPOSED_OF)
CONFIGURES     → dependency   (79% - similar to REQUIRES)
VALIDATES      → evidential   (91% - very similar to SUPPORTS)
EVOLVES_TO     → temporal     (88% - similar to EVOLVES_INTO)
DEFINES        → semantic     (76% - similar to DEFINES)
ADDRESSES      → causation    (73% - similar to CAUSES)
BUILDS_ON      → composition  (68% - similar to PART_OF)
```

## References

- **ADR-044:** Probabilistic Truth Convergence (pattern we're following)
- **ADR-032:** Automatic Edge Vocabulary Expansion (pruning weak types)
- **ADR-046:** Grounding-Aware Vocabulary Management (synonym detection via embeddings)
- **ADR-025:** Dynamic Relationship Vocabulary (allows new types)
- **ADR-022:** Semantic Relationship Taxonomy (defined the 8 categories)

---

**This ADR continues the evolution from fixed → probabilistic systems:**
1. Fixed relationships (5 types) → Dynamic vocabulary (ADR-025)
2. Fixed truth → Probabilistic grounding (ADR-044)
3. Fixed categories → Probabilistic categorization (ADR-047) ✨
