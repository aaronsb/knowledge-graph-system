# Vocabulary Category Guide

## Overview

The knowledge graph uses **probabilistic category assignment** (ADR-047) to automatically classify relationship types into 8 semantic categories. This guide explains how to interpret category scores, confidence levels, and ambiguity flags.

## The 8 Semantic Categories

All relationship types are classified into one of these fundamental categories:

| Category | Description | Example Types |
|----------|-------------|---------------|
| **causation** | Cause-and-effect relationships | CAUSES, ENABLES, PREVENTS, INFLUENCES, RESULTS_FROM |
| **composition** | Part-whole and containment | PART_OF, CONTAINS, COMPOSED_OF, SUBSET_OF, INSTANCE_OF |
| **logical** | Logical inference and contradiction | IMPLIES, CONTRADICTS, PRESUPPOSES, EQUIVALENT_TO |
| **evidential** | Evidence and support relationships | SUPPORTS, REFUTES, EXEMPLIFIES, MEASURED_BY |
| **semantic** | Meaning and similarity | SIMILAR_TO, ANALOGOUS_TO, CONTRASTS_WITH, DEFINES |
| **temporal** | Time-based relationships | PRECEDES, CONCURRENT_WITH, EVOLVES_INTO |
| **dependency** | Requirements and dependencies | DEPENDS_ON, REQUIRES, CONSUMES, PRODUCES |
| **derivation** | Origin and generation | DERIVED_FROM, GENERATED_BY, BASED_ON |

## How Categories Are Assigned

Categories emerge from **embedding similarity to seed types**:

1. Each category has 3-6 **builtin seed types** (30 total across all categories)
2. For any relationship type, we compute cosine similarity to all 30 seeds
3. **Category score = max similarity** to any seed in that category (satisficing approach)
4. The category with the highest score wins
5. If runner-up score > 70%, the type is flagged as **ambiguous**

### Why Max Instead of Mean?

Categories contain opposing polarities. For example, causation includes both:
- ENABLES (positive causation)
- PREVENTS (negative causation)

Using max similarity means: *"Is this type semantically similar to ANY seed in this category?"*
This correctly identifies both ENABLES and PREVENTS as causal, even though they're opposites.

## Understanding the Display

### In `kg vocab list`

```
TYPE                      CATEGORY          CONF    EDGES     STATUS
───────────────────────────────────────────────────────────────────────
ANALOGOUS_TO             semantic          100%        3          ✓ [B]
CAUSES                   causation         100%       10          ✓ [B]
COMPLEMENTS              composition       100%⚠       0          ✓ [B]
DEFINES                  semantic           58%        0          ✓ [B]
MYSTERIOUS_TYPE          causation          45%        1          ✓
```

**Columns:**
- **TYPE**: Relationship type name
- **CATEGORY**: Assigned semantic category
- **CONF**: Confidence percentage (see below)
- **EDGES**: Number of edges using this type in the graph
- **STATUS**: ✓ active, ✗ deprecated, [B] builtin

### Confidence Levels

Confidence shows how similar the type is to its assigned category's seed types:

| Range | Color | Meaning | Action |
|-------|-------|---------|--------|
| **≥70%** | 🟢 Green | **High confidence** - Clear category match | Auto-accept |
| **50-69%** | 🟡 Yellow | **Medium confidence** - Reasonable match | Auto-accept with monitoring |
| **<50%** | 🔴 Red | **Low confidence** - Weak match | Review needed, possible new category |
| **--** | Gray | **Builtin type** - Hand-assigned, no confidence needed | N/A |

**Examples:**
- `CAUSES 100%` - Perfect match to causation seeds
- `DEFINES 58%` - Moderate match to semantic seeds
- `MYSTERIOUS_TYPE 45%` - Weak match, may need human review

### The Ambiguity Flag ⚠

**What it means:** The type strongly matches TWO categories (runner-up > 70%)

**Why it appears:**
```
COMPLEMENTS: composition 100%⚠
  Primary:   composition 100%  (PART_OF, CONTAINS, etc.)
  Runner-up: semantic     73%  (SIMILAR_TO, ANALOGOUS_TO, etc.)
```

This type genuinely **spans multiple semantic categories**:
- Things that complement each other are compositionally related (parts working together)
- But they also have semantic similarity (complementary concepts share meaning)

**This is valuable information!** These types are:
- **Bridge nodes** connecting different semantic spaces
- **Multi-dimensional** relationships with rich meaning
- **Candidates for future multi-category support**

**Common ambiguous patterns:**
- **IMPLIES**: logical + causation (logical implications often have causal nature)
- **COMPLEMENTS**: composition + semantic (parts that work well together)
- **DERIVED_FROM**: derivation + causation (derivation often implies causation)

## Viewing Detailed Scores

Use `kg vocab category-scores <type>` to see the full breakdown:

```bash
$ kg vocab category-scores IMPLIES

📊 Category Scores: IMPLIES

Assignment
  Category:   logical
  Confidence: 100%
  Ambiguous:  Yes
  Runner-up:  causation (71%)

Similarity to Category Seeds
  logical         100%  ████████████████████
  causation        71%  ██████████████
  dependency       63%  █████████████
  composition      62%  ████████████
  evidential       62%  ████████████
  derivation       58%  ████████████
  temporal         58%  ████████████
  semantic         54%  ███████████
```

This shows:
- **Primary category**: logical (100% - perfect match to IMPLIES, CONTRADICTS, etc.)
- **Why ambiguous**: causation is 71% (>70% threshold)
- **Full landscape**: How similar the type is to all 8 categories

## Refreshing Categories

Categories can be recomputed after:
- **Vocabulary merges** (topology changed)
- **Embedding model changes** (semantic space shifted)
- **Seed type adjustments** (category definitions updated)

```bash
# Refresh only LLM-generated types (default)
kg vocab refresh-categories

# Refresh ALL types including builtins (testing)
kg vocab refresh-categories --all
```

**What happens:**
1. Recomputes similarity scores for each type
2. Updates category assignments in database
3. Recalculates ambiguity flags
4. Shows sample results

**When to refresh:**
- After merging synonyms: `kg vocab merge STRENGTHENS ENABLES`
- After model change: `kg admin embedding set --model nomic-embed-text`
- To verify system: `kg vocab refresh-categories --all`

## Interpreting Low Confidence

**Low confidence (<50%) can mean:**

1. **Missing seed type** - Need to add a new builtin type to this category
   ```
   CONFIGURES: dependency 45%
   → Maybe add CONFIGURES as a dependency seed type
   ```

2. **New category needed** - Type doesn't fit existing categories well
   ```
   REGULATES: causation 42%, composition 38%, logical 35%
   → Regulatory relationships might need their own category
   ```

3. **Truly ambiguous** - No dominant category
   ```
   CONTEXTUALIZES: semantic 48%, evidential 45%, composition 40%
   → Genuinely spans multiple semantic spaces
   ```

**Action items for low confidence types:**
1. Use `kg vocab category-scores <type>` to see full breakdown
2. Check if type is actually being used: look at EDGES column
3. If unused (0-1 edges), consider deprecation
4. If heavily used, either:
   - Add as seed type to strengthen category
   - Propose new category in ADR
   - Accept as legitimately ambiguous

## Category Distribution

Check overall distribution with `kg vocab list`:

```bash
$ kg vocab list | grep -c "causation"
$ kg vocab list | grep -c "composition"
```

**Healthy distribution** (30-90 types total):
- Roughly balanced across 8 categories (8-15 types each)
- Most types have ≥70% confidence (green)
- A few ambiguous types (⚠) spanning categories
- Very few low confidence types (<50%)

**Warning signs:**
- One category dominates (e.g., 40 causation, 3 temporal)
- Many low confidence types (lots of yellow/red)
- No ambiguous types (may indicate overfitting)

## Best Practices

### For Curators

1. **Monitor confidence** - Regularly review yellow/red types
2. **Investigate ambiguity** - Use `category-scores` to understand why types are ambiguous
3. **Merge synonyms** - Reduces vocabulary, then refresh categories
4. **Add seed types** - Strengthen weak categories by promoting good examples

### For Users

1. **Trust high confidence** (≥70%) - These are reliable classifications
2. **Understand ambiguity** (⚠) - Not a problem, just informative
3. **Question low confidence** (<50%) - These may need review
4. **Use detailed view** - `kg vocab category-scores` when investigating

### For Developers

1. **Don't override** - Categories are computed, not hand-assigned
2. **Refresh after changes** - Vocabulary merges, model changes require refresh
3. **Test with samples** - `kg vocab category-scores` on known types
4. **Monitor distribution** - Ensure balanced category usage

## Troubleshooting

### "Why is this type in the wrong category?"

Check detailed scores:
```bash
kg vocab category-scores MYSTERIOUS_TYPE
```

If the assigned category isn't actually the highest score, file a bug. If it is the highest but seems wrong, the seed types for that category may need adjustment.

### "Why is everything 100% confident?"

After running `kg vocab refresh-categories --all`, builtin types will show 100% because they're comparing against themselves (they ARE the seeds). This is expected.

LLM-generated types should show varied confidence based on their similarity to seeds.

### "Should I worry about ambiguous types?"

**No!** Ambiguity (⚠) indicates rich, multi-dimensional relationships. It's valuable information, not a problem.

Only worry if:
- Type has low confidence AND is heavily used
- Distribution is extremely unbalanced
- Many types cluster around 50% (indicates poor seed selection)

## Related Documentation

- **ADR-047**: Probabilistic Vocabulary Categorization (design rationale)
- **ADR-044**: Probabilistic Truth Convergence (similar pattern for grounding)
- **ADR-032**: Automatic Edge Vocabulary Expansion (vocabulary management)
- **ADR-022**: 30-Type Relationship Taxonomy (original seed types)

## Examples

### High Confidence, Not Ambiguous
```
CAUSES: causation 100%
```
Clear causal relationship, no ambiguity.

### High Confidence, Ambiguous
```
IMPLIES: logical 100%⚠ (runner-up: causation 71%)
```
Primarily logical, but strong causal undertones.

### Medium Confidence
```
DEFINES: semantic 58%
```
Reasonable semantic match, but not strong.

### Low Confidence (needs review)
```
CONFIGURES: dependency 45%
```
Weak match, may need new seed type or category.

---

**Last Updated:** 2025-10-27
**Related ADR:** ADR-047 (Probabilistic Vocabulary Categorization)
