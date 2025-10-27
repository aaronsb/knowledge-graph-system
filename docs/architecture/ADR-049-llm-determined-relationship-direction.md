# ADR-049: LLM-Determined Relationship Direction Semantics

**Status:** Proposed
**Date:** 2025-10-27
**Deciders:** System Architects
**Related:** ADR-047 (Probabilistic Categorization), ADR-048 (Vocabulary as Graph), ADR-022 (Semantic Taxonomy), ADR-025 (Dynamic Vocabulary)

## Context

### The Direction Problem

LLMs extract relationships with directional ambiguity. From extraction quality comparison (ADR-042 testing):

```python
# GPT-OSS 20B error:
"False sense of personal identity ENABLED_BY Language and Thought"
# ❌ Wrong! Should be: "Language ENABLES identity" (reversed direction)

# Qwen 2.5 14B error rate:
# Some relationships have unclear topology (which concept_id in from vs to?)
```

**Current prompt guidance:**
```python
"from_concept_id: Source concept"  # ← Graph terminology, not semantic!
"to_concept_id: Target concept"
```

**Problem:** "Source" refers to edge origin (topology), not semantic role (actor/receiver). LLM must guess which concept is the "actor."

### What We Already Track (Three Dimensions)

From ADR-047/ADR-048 implementation:

| Property | Storage | Granularity | Status |
|----------|---------|-------------|---------|
| **category** | :VocabType nodes + edges | Per type + per relationship | ✅ Complete (ADR-048) |
| **confidence** | Edges only | Per relationship | ✅ Complete (already collecting) |
| **direction_semantics** | ??? | ??? | ❌ Missing |

**Examples:**
```cypher
// Category (already stored)
(:VocabType {name: "ENABLES", category: "causation"})-[:IN_CATEGORY]->(:VocabCategory)

// Confidence (already stored)
(Meditation)-[ENABLES {confidence: 0.9, category: "causation"}]->(Enlightenment)

// Direction (missing!)
// Which concept acts? Which receives?
```

### How Others Handle Direction

**Neo4j (Property Graphs):**
- All relationships MUST have direction (topology)
- No semantic metadata about what direction means
- Best practice: Don't duplicate inverse relationships
- Example: `(A)-[:ENABLES]->(B)` stores once, query both ways

**RDF/OWL (Semantic Web):**
- `owl:inverseOf` defines inverse properties
- Reasoner infers inverse statements automatically
- Example: `:hasChild owl:inverseOf :hasParent`
- Cost: Requires reasoner, setup complexity

**Wikidata (Collaborative KG):**
- Store one direction + metadata about inverse property ID
- Manual maintenance of inverses (often missing!)
- Query both directions and merge results

**Key difference:** All systems model direction as **topology** or **metadata**, none teach LLM *how to reason about direction*.

## Decision

### Implement LLM-Determined Direction Semantics

**Core Principle:**
> The LLM must reason about direction based on frame of reference, not rely on hard-coded rules.

**Three direction values:**
- `"outward"`: from → to (from acts on to)
- `"inward"`: from ← to (from receives from to)
- `"bidirectional"`: no inherent direction (symmetric)

### Why Not Model Polarity?

**Considered fourth dimension:**
```python
polarity = "positive" | "negative" | "neutral" | "measured"
```

**Rejected as computational trap:**

1. **Emergent from type names** - PREVENTS obviously negative, ENABLES obviously positive
2. **LLM already knows** - From training data, doesn't need to be told
3. **Unclear query utility** - Would we filter by polarity or just by specific type?
4. **Maintenance burden** - Every new type needs polarity classification
5. **Over-engineering** - Adds complexity without proven utility

**The test:**
```python
# Query: "Show me negative relationships from Ego"
# Option 1: Filter by polarity metadata
negative_rels = filter(relationships, polarity="negative")

# Option 2: Filter by type names (already meaningful)
negative_types = ["PREVENTS", "CONTRADICTS", "REFUTES"]  # Obvious from name

# Conclusion: Don't store what LLM already knows
```

**Direction passes the test:**
- Not obvious from type name alone ("ENABLES" doesn't tell you which concept is actor)
- Maps to graph topology (affects traversal)
- LLM needs explicit teaching about frame of reference

### Architecture: Hybrid Model

**Parallel to ADR-047 (Probabilistic Categorization):**

| Aspect | ADR-047 Categories | ADR-049 Direction |
|--------|-------------------|-------------------|
| **Seed types** | 30 with manual categories | 30 shown as examples |
| **Mechanism** | Embedding similarity | LLM reasoning |
| **Storage** | Computed on first use | LLM decides on first use |
| **Growth** | Custom types auto-categorized | Custom types get LLM direction |

**Seed types as teaching examples (not rules):**
```python
# Prompt shows patterns:
"Example: ENABLES typically used outward (actor→target)"
"Example: RESULTS_FROM typically used inward (result←cause)"

# But NOT pre-populated in database
# LLM decides on first use, even for seed types
```

### Implementation: Three-Phase Capture Loop

#### Phase 1: Enhanced Prompt (Teaching)

```python
EXTRACTION_PROMPT = """
For each relationship, determine DIRECTION SEMANTICS based on frame of reference:

**OUTWARD (from → to):** The "from" concept ACTS on "to"
  Examples:
  - "Meditation ENABLES enlightenment" → from=meditation (actor), to=enlightenment (target)
  - "Ego PREVENTS awareness" → from=ego (blocker), to=awareness (blocked)
  - "Wheel PART_OF car" → from=wheel (component), to=car (whole)

**INWARD (from ← to):** The "from" concept RECEIVES from "to"
  Examples:
  - "Suffering RESULTS_FROM attachment" → from=suffering (result), to=attachment (cause)
  - "Temperature MEASURED_BY thermometer" → from=temperature (measured), to=thermometer (measurer)

**BIDIRECTIONAL:** Symmetric relationship (both directions equivalent)
  Examples:
  - "Ego SIMILAR_TO self-identity" → direction="bidirectional"
  - "Apple COMPETES_WITH Microsoft" → direction="bidirectional"

**Key Principle:** Consider which concept is the SUBJECT of the sentence:
- Active voice: "A enables B" → A is actor (outward)
- Passive voice: "A is caused by B" → A is receiver (inward)
- Mutual: "A competes with B" = "B competes with A" → bidirectional

For EVERY relationship (including novel types you create):
{{
  "from_concept_id": "concept_001",
  "to_concept_id": "concept_002",
  "relationship_type": "ENABLES",
  "direction_semantics": "outward",  // ← YOU MUST PROVIDE
  "confidence": 0.9
}}
"""
```

#### Phase 2: LLM Extraction (Reasoning)

```json
{
  "relationships": [
    {
      "from_concept_id": "meditation_001",
      "to_concept_id": "enlightenment_002",
      "relationship_type": "FACILITATES",
      "direction_semantics": "outward",
      "confidence": 0.85
    },
    {
      "from_concept_id": "suffering_001",
      "to_concept_id": "attachment_002",
      "relationship_type": "STEMS_FROM",
      "direction_semantics": "inward",
      "confidence": 0.90
    }
  ]
}
```

**LLM reasoning:**
- "Meditation facilitates..." → meditation acts → outward
- "Suffering stems from..." → suffering receives → inward

#### Phase 3: Storage and Feedback Loop

```python
# 1. Ingestion captures LLM's decision
for rel in extracted['relationships']:
    direction = rel.get('direction_semantics', 'outward')  # Safe default

    # Add to vocabulary with LLM's choice
    db.add_edge_type(
        relationship_type=rel['relationship_type'],
        category=inferred_category,
        direction_semantics=direction  # ← Store LLM's decision
    )

# 2. Store in graph
(:VocabType {
    name: "FACILITATES",
    category: "causation",
    direction_semantics: "outward",  # ← LLM decided
    usage_count: 1
})

# 3. Next extraction shows established patterns
query = """
MATCH (v:VocabType)-[:IN_CATEGORY]->(c)
WHERE v.is_active = 't'
RETURN v.name, v.direction_semantics, v.usage_count
ORDER BY v.usage_count DESC
"""

# Prompt includes:
"Existing types with direction patterns:
  ENABLES (47 uses, direction='outward')
  FACILITATES (3 uses, direction='outward')
  RESULTS_FROM (12 uses, direction='inward')
  COMPETES_WITH (5 uses, direction='bidirectional')"
```

### Schema Changes

**Migration 016:**
```sql
-- PostgreSQL table
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN direction_semantics VARCHAR(20) DEFAULT NULL;
-- NULL = not yet determined by LLM

-- Index for queries
CREATE INDEX idx_direction_semantics
ON kg_api.relationship_vocabulary(direction_semantics);
```

**Graph nodes:**
```cypher
// Add property to :VocabType nodes
MATCH (v:VocabType)
SET v.direction_semantics = null
// Will be set on first LLM usage
```

**JSON Schema Update:**
```json
{
  "relationships": [
    {
      "from_concept_id": "string",
      "to_concept_id": "string",
      "relationship_type": "string",
      "direction_semantics": "outward|inward|bidirectional",
      "confidence": "number (0.0-1.0)"
    }
  ]
}
```

## Consequences

### Positive

**1. Reduced Direction Errors**
- Explicit frame-of-reference teaching
- LLM understands actor vs receiver distinction
- Expected: 35% error rate → <10% error rate

**2. Emergent Pattern Learning**
```python
# Initially: Only examples in prompt
# After 100 documents:
OUTWARD: CAUSES, ENABLES, FACILITATES, MOTIVATES, ... (35 types)
INWARD: RESULTS_FROM, STEMS_FROM, DERIVED_FROM, ... (5 types)
BIDIRECTIONAL: SIMILAR_TO, COMPETES_WITH, MIRRORS, ... (8 types)

# LLM learns: "*_FROM suffix → usually inward"
# LLM learns: "Competition/similarity → usually bidirectional"
```

**3. Query Enhancement**
```cypher
// Find what enables X (actors)
MATCH (actor)-[r]->(target:Concept {label: "enlightenment"})
WHERE r.direction_semantics = 'outward'
  AND r.category = 'causation'
RETURN actor

// Find what X results from (causes)
MATCH (result)-[r]->(cause)
WHERE r.direction_semantics = 'inward'
  AND result.label = 'suffering'
RETURN cause
```

**4. Validation Heuristics**
```python
# Detect suspicious patterns
if rel_type.endswith("_FROM") and direction == "outward":
    logger.warning(f"Suspicious: {rel_type} marked outward (usually inward)")

if rel_type.endswith("_WITH") and direction != "bidirectional":
    logger.warning(f"Suspicious: {rel_type} marked directional (usually symmetric)")
```

**5. Consistency with ADR-047**
- Categories: Emergent from embeddings
- Direction: Emergent from LLM reasoning
- Both: Seed types are examples, not hard-coded behavior

### Negative

**1. LLM Must Reason (Cognitive Load)**
- Adds complexity to extraction task
- LLM must consider frame of reference for every relationship
- Risk: LLM ignores direction field or defaults always

**Mitigation:**
- Make direction_semantics REQUIRED in JSON schema
- Validate presence before ingestion
- Reject relationships without direction

**2. Inconsistent Initial Decisions**
- First LLM to use "ENABLES" decides direction forever
- Different models might decide differently
- Risk: Inconsistency across extraction sessions

**Mitigation:**
- Seed types get shown as examples with typical direction
- Most models will converge on obvious directions
- Can manually override if pattern clearly wrong

**3. Validation Complexity**
```python
# Need to validate LLM's decision
if direction not in ["outward", "inward", "bidirectional"]:
    # Invalid value - use default
    direction = "outward"

# Need to check for suspicious patterns
if rel_type.endswith("_FROM") and direction != "inward":
    # Flag for review
    pass
```

**4. Migration Burden**
- Existing 47 vocabulary types have no direction
- Options:
  - Let LLM decide on next use (clean, emergent)
  - Pre-seed with obvious defaults (faster, less pure)
  - Run batch categorization job (middle ground)

### Neutral

**1. No Impact on Existing Edges**
- Direction is vocabulary metadata
- Existing edges unchanged
- Only affects new extractions

**2. Three-Valued Property**
- Could extend later (e.g., "context-dependent")
- But keep simple for now

## Alternatives Considered

### Alternative 1: Hard-Code Direction for All Types

**Approach:**
```python
DIRECTION_SEMANTICS = {
    "CAUSES": "outward",
    "ENABLES": "outward",
    "RESULTS_FROM": "inward",
    ...
}
```

**Rejected:**
- Violates dynamic vocabulary principle (ADR-025)
- Can't handle custom types like "COMPETES_WITH"
- Breaks emergent pattern learning
- Inconsistent with ADR-047 (emergent categories)

### Alternative 2: Bidirectional by Default (Ignore Direction)

**Approach:**
- All relationships stored with arbitrary direction
- Query ignores direction (like Neo4j pattern)
- Don't model direction semantics at all

**Rejected:**
- Loses semantic information (CAUSES vs RESULTS_FROM)
- Can't filter by actor vs receiver in queries
- Direction errors remain in data
- Wastes opportunity to teach LLM

### Alternative 3: Store Both Directions (Duplicate Edges)

**Approach:**
```cypher
(A)-[:ENABLES]->(B)
(B)-[:ENABLED_BY]->(A)  // Inverse
```

**Rejected:**
- Doubles storage (47 types → 94 types for inverses)
- Maintenance nightmare (keep synchronized)
- Neo4j best practice: DON'T do this
- Better: Store once with direction metadata

### Alternative 4: Model Polarity (Positive/Negative)

**Approach:**
```python
{
    "relationship_type": "ENABLES",
    "direction_semantics": "outward",
    "polarity": "positive"  // ← Extra dimension
}
```

**Rejected:**
- Computational trap (discussed above)
- LLM already knows PREVENTS is negative
- Adds complexity without clear utility
- Can infer from type name when needed

### Alternative 5: OWL-Style Inverse Properties

**Approach:**
```python
INVERSE_PROPERTIES = {
    "ENABLES": "ENABLED_BY",
    "CAUSES": "CAUSED_BY",
    ...
}
```

**Rejected:**
- Requires maintaining inverse type definitions
- Doubles vocabulary size
- OWL reasoner not available in AGE
- Our approach simpler: one type + direction metadata

## Implementation Plan

### Phase 1: Schema and Seed Examples (Week 1)

- [ ] Migration 016: Add `direction_semantics` column to vocabulary table
- [ ] Update :VocabType nodes to have `direction_semantics` property
- [ ] Document 30 seed types with typical direction patterns (for prompt examples)
- [ ] Update `add_edge_type()` to accept `direction_semantics` parameter

### Phase 2: Prompt Enhancement (Week 1)

- [ ] Update EXTRACTION_PROMPT_TEMPLATE with frame-of-reference teaching
- [ ] Add direction examples (outward/inward/bidirectional)
- [ ] Update JSON schema to require `direction_semantics` field
- [ ] Add validation to reject relationships without direction

### Phase 3: Ingestion Integration (Week 1)

- [ ] Update ingestion.py to extract `direction_semantics` from LLM response
- [ ] Store direction in vocabulary when adding new types
- [ ] Add validation heuristics (detect suspicious patterns)
- [ ] Add logging for direction decisions

### Phase 4: Prompt Feedback Loop (Week 2)

- [ ] Query vocabulary graph for existing types with direction
- [ ] Dynamically build direction examples in prompt
- [ ] Show usage counts with direction patterns
- [ ] LLM learns from growing vocabulary

### Phase 5: Validation and Testing (Week 2)

- [ ] Test extraction with direction guidance
- [ ] Measure error reduction (baseline 35% → target <10%)
- [ ] Validate LLM decision quality
- [ ] Adjust prompt if patterns unclear

### Phase 6: Migration Strategy (Week 2)

**Decision point:** How to handle existing 47 types?

**Option A: Emergent (recommended)**
- Leave direction NULL for existing types
- LLM decides on next use
- Pure emergent approach

**Option B: Pre-seed obvious types**
- Set direction for obvious cases (CAUSES→outward, RESULTS_FROM→inward)
- Faster for common types
- Less pure but practical

**Option C: Batch categorization**
- Run one-time LLM job to classify existing types
- Store decisions as if LLM made them during extraction
- Middle ground

## Success Criteria

1. **LLM provides direction for >95% of relationships** (not defaulting to null)
2. **Direction error rate <10%** (down from 35% baseline)
3. **Validation heuristics flag <5% suspicious patterns** (acceptable false positive rate)
4. **Query utility:** Can filter by direction in graph traversals
5. **Pattern learning:** Custom types show consistent direction patterns after 3+ uses
6. **No performance regression:** <50ms overhead for direction processing

## Example Scenarios

### Scenario 1: Seed Type First Use

```python
# LLM extracts using seed type "ENABLES"
{
    "type": "ENABLES",
    "direction_semantics": "outward",  # LLM decided
    "confidence": 0.9
}

# Storage (first use sets the pattern)
UPDATE relationship_vocabulary
SET direction_semantics = 'outward'
WHERE relationship_type = 'ENABLES';

# Graph node
(:VocabType {name: "ENABLES", direction_semantics: "outward", usage_count: 1})

# Next extraction sees:
"ENABLES (1 use, direction='outward')"
```

### Scenario 2: Novel Vocabulary

```python
# LLM creates "COMPETES_WITH"
{
    "type": "COMPETES_WITH",
    "direction_semantics": "bidirectional",  # LLM reasoned: symmetric
    "confidence": 0.85
}

# Storage
INSERT INTO relationship_vocabulary (
    relationship_type,
    category,  # From embedding similarity
    direction_semantics,  # From LLM
    is_builtin
) VALUES ('COMPETES_WITH', 'semantic', 'bidirectional', false);

# Graph node
(:VocabType {name: "COMPETES_WITH", direction_semantics: "bidirectional"})

# Next extraction sees:
"COMPETES_WITH (1 use, direction='bidirectional')"
```

### Scenario 3: Direction-Aware Query

```cypher
// Find what meditation enables (outward relationships)
MATCH (meditation:Concept {label: "Meditation"})-[r]->(target)
MATCH (v:VocabType {name: type(r)})
WHERE v.direction_semantics = 'outward'
  AND v.category = 'causation'
RETURN target.label, type(r), r.confidence
ORDER BY r.confidence DESC

// Results:
// enlightenment, ENABLES, 0.92
// awareness, FACILITATES, 0.88
// growth, ENABLES, 0.85
```

## References

- **ADR-047:** Probabilistic Vocabulary Categorization (emergent categories)
- **ADR-048:** Vocabulary Metadata as First-Class Graph
- **ADR-025:** Dynamic Relationship Vocabulary (allows custom types)
- **ADR-022:** Semantic Relationship Taxonomy (30 seed types)
- **ADR-042:** Local LLM Inference (extraction quality comparison showing 35% direction errors)

## Related Documentation

- `docs/development/vocabulary-direction-analysis.md` - Initial analysis
- `docs/development/relationship-semantics-comparison.md` - How others handle direction

---

**This ADR establishes direction as the third dimension of relationship semantics:**
1. **Category** (computed via embeddings, ADR-047)
2. **Confidence** (per relationship, LLM-determined)
3. **Direction** (per type, LLM-determined, this ADR) ✨

Together, these three orthogonal properties enable rich semantic queries while maintaining the emergent, satisficing approach that characterizes this system's architecture.
