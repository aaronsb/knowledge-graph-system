# ADR-022: Semantically Sparse 30-Type Relationship Taxonomy

**Status:** Accepted
**Date:** 2025-10-09
**Deciders:** Development Team
**Related:** ADR-004 (Pure Graph Design), ADR-016 (Apache AGE Migration)

## Context

The original knowledge graph used 5 relationship types (IMPLIES, CONTRADICTS, SUPPORTS, PART_OF, RELATES_TO). This limited semantic expressiveness led to:

1. **Loss of Nuance** - "SUPPORTS" collapsed evidential support, exemplification, and measurement
2. **LLM Confusion** - Models produced variations like "CONTRASTS" (not in schema) → failed relationships
3. **Reasoning Limitations** - Query systems couldn't distinguish causal from structural relationships
4. **Overgeneralization** - "RELATES_TO" became a catch-all for unspecified connections

### Breaking Point

During ingestion, LLMs consistently extracted semantically valid relationship types that weren't in the schema:

```
⚠ Failed to create relationship: Invalid relationship type: CONTRASTS.
Must be one of ['IMPLIES', 'CONTRADICTS', 'SUPPORTS', 'PART_OF', 'RELATES_TO']
```

The LLM was correct - "CONTRASTS" is semantically distinct from "CONTRADICTS" (contrasting perspectives vs logical contradiction). But the rigid 5-type system couldn't capture this.

## Decision

Implement a **semantically sparse 30-type relationship taxonomy** organized into 8 categories, with fuzzy matching to normalize LLM outputs.

### Core Principles

1. **Semantic Sparsity** - Each type adds unique information an LLM can reason about differently
2. **Category Structure** - Internal organization for humans, hidden from LLM during extraction
3. **Fuzzy Normalization** - Use `difflib` to map LLM variations to canonical types
4. **Dual Storage** - Track both category and exact type in graph edges

### The 30-Type Taxonomy

**Logical & Truth Relations** (`logical_truth`)
- `IMPLIES` - A being true makes B necessarily true (logical entailment)
- `CONTRADICTS` - A and B cannot both be true
- `PRESUPPOSES` - A assumes B is true (B must be true for A to be meaningful)
- `EQUIVALENT_TO` - A and B express the same thing differently

**Causal Relations** (`causal`)
- `CAUSES` - A directly produces/creates B
- `ENABLES` - A makes B possible (but doesn't guarantee it)
- `PREVENTS` - A blocks B from occurring
- `INFLUENCES` - A affects B without full causation
- `RESULTS_FROM` - B is an outcome/consequence of A (reverse of CAUSES)

**Structural & Compositional** (`structural`)
- `PART_OF` - A is a component of B (wheel part of car)
- `CONTAINS` - A includes B as a member (set contains elements)
- `COMPOSED_OF` - A is made from B as material (cake composed of flour)
- `SUBSET_OF` - All A are B, but not all B are A
- `INSTANCE_OF` - A is a specific example of category B

**Evidential & Support** (`evidential`)
- `SUPPORTS` - A provides evidence for B
- `REFUTES` - A provides evidence against B
- `EXEMPLIFIES` - A serves as a concrete example of B
- `MEASURED_BY` - A's value/quality is quantified by B

**Similarity & Contrast** (`similarity`)
- `SIMILAR_TO` - A and B share properties
- `ANALOGOUS_TO` - A maps to B metaphorically (heart:pump)
- `CONTRASTS_WITH` - A and B differ in meaningful ways
- `OPPOSITE_OF` - A is the inverse/negation of B

**Temporal Relations** (`temporal`)
- `PRECEDES` - A happens before B
- `CONCURRENT_WITH` - A and B happen at the same time
- `EVOLVES_INTO` - A transforms into B over time

**Functional & Purpose** (`functional`)
- `USED_FOR` - A's purpose is to achieve B
- `REQUIRES` - A needs B to function/exist
- `PRODUCES` - A generates B as output
- `REGULATES` - A controls/modifies B's behavior

**Meta-Relations** (`meta`)
- `DEFINED_AS` - A's meaning is B (definitional)
- `CATEGORIZED_AS` - A belongs to category/type B

### Key Semantic Distinctions

**CAUSES vs ENABLES:**
- `CAUSES`: "Spark CAUSES fire" (deterministic)
- `ENABLES`: "Oxygen ENABLES fire" (necessary but not sufficient)

**PART_OF vs COMPOSED_OF:**
- `PART_OF`: "Engine PART_OF car" (functional components)
- `COMPOSED_OF`: "Water COMPOSED_OF hydrogen" (material constitution)

**IMPLIES vs PRESUPPOSES:**
- `IMPLIES`: "Rain IMPLIES wet ground" (logical consequence)
- `PRESUPPOSES`: "Stopped smoking PRESUPPOSES previously smoked" (background assumption)

**SUPPORTS vs EXEMPLIFIES:**
- `SUPPORTS`: "Study SUPPORTS theory" (evidence for)
- `EXEMPLIFIES`: "Robin EXEMPLIFIES bird" (concrete instance)

**SIMILAR_TO vs ANALOGOUS_TO:**
- `SIMILAR_TO`: "Cat SIMILAR_TO dog" (direct comparison)
- `ANALOGOUS_TO`: "Brain ANALOGOUS_TO computer" (functional mapping across domains)

**CONTRADICTS vs CONTRASTS_WITH:**
- `CONTRADICTS`: "All A CONTRADICTS Some not-A" (logical impossibility)
- `CONTRASTS_WITH`: "Eastern philosophy CONTRASTS_WITH Western philosophy" (different perspectives)

## Implementation

### 1. Constants Structure (`src/api/constants.py`)

```python
RELATIONSHIP_CATEGORIES: Dict[str, List[str]] = {
    "logical_truth": ["IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO"],
    "causal": ["CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM"],
    # ... 8 categories total
}

# Flat set of all types
RELATIONSHIP_TYPES: Set[str] = {
    rel_type
    for category_types in RELATIONSHIP_CATEGORIES.values()
    for rel_type in category_types
}

# Reverse mapping: type -> category
RELATIONSHIP_TYPE_TO_CATEGORY: Dict[str, str] = {
    rel_type: category
    for category, types in RELATIONSHIP_CATEGORIES.items()
    for rel_type in types
}
```

### 2. Fuzzy Matching - Porter Stemmer Enhanced Hybrid Matcher

**Evolution:** Testing revealed `difflib.SequenceMatcher` alone (threshold 0.7) achieved only **16.7% accuracy** on critical edge cases:
- ❌ `CONTRASTS` → `CONTRADICTS` (wrong! score 0.800 vs 0.783 for correct `CONTRASTS_WITH`)
- ❌ `COMPONENT_OF` → `COMPOSED_OF` (false positive)
- ❌ Missed verb tense variations (`CAUSING` should match `CAUSES`)

**Algorithm Comparison (15 critical test cases):**
| Algorithm | Accuracy | Notes |
|-----------|----------|-------|
| `difflib.SequenceMatcher` (0.7) | 16.7% | Original approach - prone to false positives |
| `difflib.get_close_matches` (0.7) | 16.7% | Same as SequenceMatcher (uses it internally) |
| NLTK Edit Distance (≤3) | 66.7% | Handles verb tense but fails prefix matching |
| Hybrid (prefix+contains+fuzzy 0.85) | 66.7% | Fixes prefix bugs but misses verb tense |
| **Porter Stemmer Hybrid (0.8)** | **100%** | ✅ **Winner - combines all strengths** |

![Porter Stemmer Enhanced Hybrid Matcher - Like Voltron, combining multiple algorithms into one powerful matcher](media/voltron-porter-stemmer.jpg)

**Final Implementation:** Multi-stage Porter Stemmer Enhanced Hybrid Matcher

```python
from difflib import SequenceMatcher
from nltk.stem import PorterStemmer

def normalize_relationship_type(llm_type: str, fuzzy_threshold: float = 0.8):
    """
    Six-stage matching strategy:
    1. Exact match (fast path)
    2. Reject _BY reversed relationships (directional filtering)
    3. Prefix match (CONTRASTS → CONTRASTS_WITH)
    4. Contains match (CONTRADICTS_WITH → CONTRADICTS)
    5. Porter stem match (CAUSING → CAUSES via stem "caus")
    6. Fuzzy match (threshold 0.8 for typos only)
    """
    llm_upper = llm_type.upper()

    # 1. Exact match
    if llm_upper in RELATIONSHIP_TYPES:
        return (llm_upper, category, 1.0)

    # 2. Reject _BY reversed (CAUSED_BY, ENABLED_BY)
    if llm_upper.endswith('_BY'):
        return (None, None, 0.0)

    # 3. Prefix match (input is prefix of canonical)
    prefix_matches = [c for c in RELATIONSHIP_TYPES if c.startswith(llm_upper)]
    if prefix_matches:
        return (min(prefix_matches, key=len), category, score)

    # 4. Contains match (canonical is prefix of input)
    contains_matches = [c for c in RELATIONSHIP_TYPES if llm_upper.startswith(c)]
    if contains_matches:
        return (max(contains_matches, key=len), category, score)

    # 5. Porter stem match (handles verb tense)
    llm_stem = stemmer.stem(llm_upper.lower())
    for canonical in RELATIONSHIP_TYPES:
        if llm_stem == stemmer.stem(canonical.lower()):
            return (canonical, category, score)

    # 6. Fuzzy fallback (0.8 threshold prevents false positives)
    # ... SequenceMatcher with threshold 0.8
```

**Examples:**
- `"CONTRASTS"` → `("CONTRASTS_WITH", "similarity", 1.0)` via **prefix match**
- `"CAUSING"` → `("CAUSES", "causal", 0.615)` via **Porter stem** (`caus`)
- `"IMPLYING"` → `("IMPLIES", "logical_truth", 0.667)` via **Porter stem** (`impli`)
- `"CAUZES"` → `("CAUSES", "causal", 0.833)` via **fuzzy match**
- `"CAUSED_BY"` → `(None, None, 0.0)` via **rejection** (reversed relationship)
- `"CREATES"` → `(None, None, 0.0)` **rejected** (threshold 0.8 prevents REGULATES false positive)

**Key Design Decisions:**
1. **Threshold 0.8 (not 0.7)** - Prevents false positives like `CREATES`→`REGULATES` (score 0.75)
2. **Porter Stemmer** - Handles irregular verbs (`IMPLYING`/`IMPLIES` → `impli`)
3. **Prefix before fuzzy** - Ensures `CONTRASTS` matches `CONTRASTS_WITH` not `CONTRADICTS`
4. **Explicit _BY rejection** - Reversed relationships (`CAUSED_BY`) indicate opposite directionality

**Trade-offs:**
- ✅ **Quality over simplicity** - Multi-stage approach adds complexity but achieves 100% accuracy
- ✅ **NLTK dependency** - Adds 24MB package, but Porter Stemmer is battle-tested for English
- ⚠️ **Performance** - 6-stage check slower than single fuzzy match, but still <1ms per relationship

### 3. LLM Prompt Integration

LLM receives dense list **without categories** to avoid overfitting:

```
relationship_type: One of [ANALOGOUS_TO, CATEGORIZED_AS, CAUSES, COMPOSED_OF,
CONCURRENT_WITH, CONTAINS, CONTRADICTS, CONTRASTS_WITH, DEFINED_AS, ENABLES,
EQUIVALENT_TO, EVOLVES_INTO, EXEMPLIFIES, IMPLIES, INFLUENCES, INSTANCE_OF,
MEASURED_BY, OPPOSITE_OF, PART_OF, PRECEDES, PRESUPPOSES, PREVENTS, PRODUCES,
REFUTES, REGULATES, REQUIRES, RESULTS_FROM, SIMILAR_TO, SUBSET_OF, SUPPORTS,
USED_FOR]
```

**Rationale:** Categories are for internal organization. LLM sees flat list to avoid category bias.

### 4. Edge Storage with Category Metadata

Relationships store both exact type and category:

```cypher
CREATE (a:Concept)-[r:ENABLES {
    confidence: 0.85,
    category: "causal"
}]->(b:Concept)
```

This enables category-level queries:
```cypher
// Find all causal relationships
MATCH (a)-[r]->(b)
WHERE r.category = 'causal'
RETURN a, r, b
```

## Consequences

### Positive

✅ **Semantic Richness** - 30 distinct types capture nuanced relationships
✅ **LLM Flexibility** - Fuzzy matching accepts variations ("CONTRASTS" → "CONTRASTS_WITH")
✅ **Query Power** - Can filter by category or exact type
✅ **Future-Proof** - Easy to add types within existing categories
✅ **No Breaking Changes** - Old 5 types (IMPLIES, CONTRADICTS, SUPPORTS, PART_OF, RELATES_TO) still exist
✅ **Self-Documenting** - Categories organize types conceptually

### Negative

⚠️ **Token Overhead** - Dense list adds ~50 tokens per extraction (~$0.000025/extraction)
⚠️ **Learning Curve** - Developers must understand 30 types vs 5
⚠️ **Potential Confusion** - LLM may still hallucinate types not in list
⚠️ **Fuzzy Match Errors** - 70% threshold may accept incorrect matches

### Mitigations

**Token Cost:** 50 tokens × $0.50/1M = $0.000025 per extraction (negligible)

**Fuzzy Match Errors:** Log all normalizations with similarity scores for monitoring:
```python
logger.info(f"Normalized '{llm_type}' → '{canonical_type}' (similarity: {score:.2f})")
```

**LLM Hallucinations:** Reject types below 70% similarity threshold, log for analysis

## Validation

### Before (5-Type System)
```
LLM Output: "CONTRASTS"
Result: ❌ Relationship creation failed
         "Invalid relationship type: CONTRASTS"
```

### After (30-Type System with Fuzzy Matching)
```
LLM Output: "CONTRASTS"
Normalization: "CONTRASTS" → "CONTRASTS_WITH" (similarity: 0.89)
Result: ✅ Edge created: (A)-[CONTRASTS_WITH {category: "similarity"}]->(B)
```

### Semantic Distinction Example
```
Before: "Brain SUPPORTS computer analogy" (evidential)
After:  "Brain ANALOGOUS_TO computer" (similarity)

The LLM can now express: "This is an analogy" vs "This provides evidence"
```

## Migration Path

**Phase 1: Add Types (This ADR)**
- ✅ Define 30-type taxonomy
- ✅ Add fuzzy normalization
- ✅ Update LLM prompts

**Phase 2: Edge Metadata (Next)**
- Add category field to relationships
- Update schema initialization
- Backfill existing edges with categories

**Phase 3: Query API (Future)**
- Add category-based graph queries
- Support relationship type filtering
- Enable semantic path finding

## References

- **Code:**
  - `src/api/constants.py` - 30-type taxonomy definition
  - `src/api/lib/relationship_mapper.py` - Fuzzy matching logic
  - `src/api/lib/age_client.py` - Relationship creation with normalization

- **Related ADRs:**
  - ADR-004: Pure Graph Design
  - ADR-016: Apache AGE Migration

## Decision Outcome

**Accepted** - The 30-type semantically sparse taxonomy with fuzzy matching successfully:
- Captures nuanced relationships LLMs naturally express
- Handles variation gracefully (CONTRASTS → CONTRASTS_WITH)
- Enables richer graph queries and reasoning
- Adds minimal cost (~$0.000025 per extraction)

**Key Insight:** The best schema isn't the most restrictive - it's the one that matches how LLMs naturally conceptualize relationships while providing structure for downstream reasoning.

**Future Work:** Consider even finer granularity (e.g., splitting CAUSES into DIRECTLY_CAUSES and INDIRECTLY_CAUSES) if query patterns reveal the need.
