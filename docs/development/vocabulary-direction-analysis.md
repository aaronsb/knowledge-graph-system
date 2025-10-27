# Vocabulary Direction Semantics Analysis

## Classification of 30 Builtin Types

### OUTWARD (from → to) - 27 types

**Causation (4 outward):**
- CAUSES: A directly produces B
- ENABLES: A makes B possible
- PREVENTS: A blocks B from occurring
- INFLUENCES: A affects B

**Causation (1 inward):**
- RESULTS_FROM: A results from B (B causes A) ← INWARD

**Logical (4 types):**
- IMPLIES: A being true makes B necessarily true
- CONTRADICTS: A and B cannot both be true (bidirectional?)
- PRESUPPOSES: A assumes B is true
- EQUIVALENT_TO: A and B express the same thing (bidirectional)

**Structural (5 types):**
- PART_OF: A is component of B (component → whole)
- CONTAINS: A includes B (container → contained)
- COMPOSED_OF: A is made from B as material (whole → material)
- SUBSET_OF: All A are B (subset → superset)
- INSTANCE_OF: A is example of category B (instance → category)

**Evidential (3 outward + 1 ambiguous):**
- SUPPORTS: A provides evidence for B
- REFUTES: A provides evidence against B
- EXEMPLIFIES: A serves as concrete example of B
- MEASURED_BY: A quantified by B (measured ← measurer) - could be INWARD

**Similarity (4 types - all bidirectional?):**
- SIMILAR_TO: A and B share properties
- ANALOGOUS_TO: A maps to B metaphorically
- CONTRASTS_WITH: A and B differ meaningfully
- OPPOSITE_OF: A is inverse of B

**Temporal (3 types):**
- PRECEDES: A happens before B
- CONCURRENT_WITH: A and B happen simultaneously (bidirectional)
- EVOLVES_INTO: A transforms into B

**Functional (4 types):**
- USED_FOR: A's purpose is to achieve B
- REQUIRES: A needs B to function
- PRODUCES: A generates B as output
- REGULATES: A controls B's behavior

**Meta (2 types):**
- DEFINED_AS: A's meaning is B
- CATEGORIZED_AS: A belongs to category B

## Proposed Classification

```python
DIRECTION_SEMANTICS = {
    # OUTWARD (from → to): 24 types
    "outward": [
        "CAUSES", "ENABLES", "PREVENTS", "INFLUENCES",
        "IMPLIES", "PRESUPPOSES",
        "PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF", "INSTANCE_OF",
        "SUPPORTS", "REFUTES", "EXEMPLIFIES",
        "PRECEDES", "EVOLVES_INTO",
        "USED_FOR", "REQUIRES", "PRODUCES", "REGULATES",
        "DEFINED_AS", "CATEGORIZED_AS",
        "COMPLEMENTS",  # From ADR-048
    ],

    # INWARD (from ← to): 2 types
    "inward": [
        "RESULTS_FROM",  # A results from B (B causes A)
        "MEASURED_BY",   # A measured by B (B measures A)
    ],

    # BIDIRECTIONAL (no inherent direction): 4 types
    "bidirectional": [
        "SIMILAR_TO",
        "ANALOGOUS_TO",
        "CONTRASTS_WITH",
        "OPPOSITE_OF",
        "EQUIVALENT_TO",
        "CONTRADICTS",  # A contradicts B = B contradicts A
        "CONCURRENT_WITH",
    ],
}
```

## Benefits

1. **Simple**: One property per type, three possible values
2. **Stored once**: In vocabulary metadata (both table and :VocabType node)
3. **Prompt clarity**: LLM sees grouped types with clear direction
4. **Validation**: Can detect reversed relationships
5. **Auto-correction**: Can flip edges if direction wrong
6. **Extensible**: New custom types get direction from categorization

## Example Corrections

**Before (GPT-OSS error):**
```json
{
  "from": "false_sense_of_personal_identity",
  "to": "language_and_thought",
  "type": "ENABLED_BY"  // ← Wrong type! Not in vocabulary
}
```

**With direction semantics:**
1. Fuzzy matcher finds closest: "ENABLES" (outward)
2. Direction check: Should be "language ENABLES identity" (language → identity)
3. Auto-correct: Flip edge or reject relationship

## Implementation Steps

1. **Migration 016**: Add `direction_semantics` column
2. **Seed data**: Update 30 builtin types with direction
3. **VocabularyCategorizer**: Assign direction to new custom types (heuristic or default to "outward")
4. **Prompt update**: Group types by direction in extraction prompt
5. **Validation**: Add direction checking in ingestion pipeline
