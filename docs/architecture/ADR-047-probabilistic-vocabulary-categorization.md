# ADR-047: Probabilistic Vocabulary Categorization

**Status:** Proposed
**Date:** 2025-10-26
**Deciders:** System Architects
**Related:** ADR-044 (Probabilistic Truth Convergence), ADR-025 (Dynamic Relationship Vocabulary), ADR-022 (Semantic Relationship Taxonomy)

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

**3. Storage Schema**

Update `relationship_vocabulary` table:

```sql
ALTER TABLE relationship_vocabulary
ADD COLUMN category_source VARCHAR(20) DEFAULT 'llm_generated',  -- 'builtin' or 'computed'
ADD COLUMN category_confidence FLOAT,  -- 0.0 to 1.0
ADD COLUMN category_scores JSONB;  -- Full score breakdown

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

# Recompute periodically or on demand
kg vocab refresh-categories
# Recalculates all 'computed' categories based on current embeddings
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

**1. Embedding Dependency**
- Requires embedding model consistency
- Changing models recalculates categories

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
- Categories can change as vocabulary grows
- May want to version/track category changes

**2. New Categories**
- System can detect "orphan" types (low scores across all categories)
- Signals need for new category seed

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Add schema columns (category_source, category_confidence, category_scores)
- [ ] Implement `compute_category_scores()` function
- [ ] Add category assignment to vocabulary insert logic

### Phase 2: Batch Categorization (Week 1)
- [ ] Compute categories for existing 88 llm_generated types
- [ ] Store scores in database
- [ ] Verify accuracy on sample types

### Phase 3: CLI Integration (Week 1)
- [ ] Update `kg vocab list` to show confidence
- [ ] Add `kg vocab category-scores <TYPE>` command
- [ ] Add `kg vocab refresh-categories` command

### Phase 4: Validation (Week 2)
- [ ] Compare computed categories to manual review
- [ ] Identify low-confidence types
- [ ] Determine if new category seeds needed

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
4. **Recomputation < 1 second** for all 118 types
5. **User can understand** why a type got its category (`kg vocab category-scores`)

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

- ADR-044: Probabilistic Truth Convergence (pattern we're following)
- ADR-025: Dynamic Relationship Vocabulary (allows new types)
- ADR-022: Semantic Relationship Taxonomy (defined the 8 categories)
- ADR-046: Grounding-Aware Vocabulary Management (vocabulary evolution)

---

**This ADR continues the evolution from fixed → probabilistic systems:**
1. Fixed relationships (5 types) → Dynamic vocabulary (ADR-025)
2. Fixed truth → Probabilistic grounding (ADR-044)
3. Fixed categories → Probabilistic categorization (ADR-047) ✨
