# Relationship Semantics: How Others Do It vs. Our Proposal

## How Established Systems Handle Directionality

### Neo4j (Property Graph)

**Philosophy:** "Direction is always present but can be ignored"

```cypher
// All relationships MUST have a direction
(person:Person)-[:KNOWS]->(friend:Person)

// But you can traverse either way
MATCH (p:Person)-[:KNOWS]-(other:Person)  // Ignores direction

// Or explicitly both ways
MATCH (p:Person)<-[:KNOWS]->(other:Person)
```

**Best Practices:**
- Use active verbs: CONTROLS, MONITORS, OWNS
- Semantically non-directional relationships get arbitrary direction
- Don't create duplicate inverse relationships (wastes space/time)
- Direction is part of relationship's meaning when ambiguous

**Example:**
```
(A)-[:ENABLES]->(B)    // A enables B (directional)
(A)-[:SIMILAR_TO]->(B) // Arbitrary direction (symmetric)
```

### RDF/OWL (Semantic Web)

**Philosophy:** "Inverse properties define bidirectional semantics"

```turtle
# Define property and its inverse
:hasChild rdf:type owl:ObjectProperty .
:hasParent rdf:type owl:ObjectProperty ;
           owl:inverseOf :hasChild .

# Store only one direction
:Alice :hasChild :Bob .

# Reasoner infers:
:Bob :hasParent :Alice .
```

**Key Concepts:**
- `owl:inverseOf` - Relates two properties that are inverses
- `owl:SymmetricProperty` - Property equal to its own inverse
- `owl:TransitiveProperty` - Property that chains (ancestor relationships)
- Reasoners can infer inverse statements

**Benefits:**
- Store once, query either direction
- Formal semantics via OWL reasoning
- Guaranteed consistency

**Drawbacks:**
- Requires reasoner (computational overhead)
- Complex queries without reasoner

### Wikidata (Collaborative Knowledge Graph)

**Philosophy:** "Single direction storage + metadata about inverses"

```
Property: mother (P25)
  - inverse property: child (P40)
  - directionality: one way (from child to mother)

Property: spouse (P26)
  - symmetric: yes
  - directionality: bidirectional
```

**Storage:**
- Store relationship in ONE direction only
- Property metadata declares inverse property ID
- Manual or bot-assisted inverse maintenance

**Problem:**
- Inverses often missing
- Query requires checking both directions and merging results
- Community debate: Should inverses be auto-generated?

### Neo4j Best Practice (2024)

From community discussions:

**For symmetric relationships:**
```cypher
// WRONG: Redundant storage
(a)-[:PARTNER]->(b)
(b)-[:PARTNER]->(a)

// RIGHT: Single relationship, arbitrary direction
(a)-[:PARTNER]->(b)

// Query ignores direction
MATCH (person)-[:PARTNER]-(partner)
```

**For directional relationships:**
```cypher
// Direction is semantic meaning
(child)-[:HAS_PARENT]->(parent)  // Clear direction
(cause)-[:CAUSES]->(effect)      // Clear direction

// Relationship type embeds direction
(owner)-[:OWNS]->(property)      // Not OWNED_BY
```

## Your Proposal: Orthogonal Properties

### The Insight

> "one could technically have a direction and a negative strength, or possibly no direction and a strength too."

You're recognizing **two independent semantic dimensions:**

### Dimension 1: Direction (Topology)

```python
direction_semantics = "outward" | "inward" | "bidirectional"
```

- **outward**: from → to (A acts on B)
- **inward**: from ← to (A receives from B)
- **bidirectional**: no inherent direction (symmetric)

### Dimension 2: Polarity (Strength/Effect)

```python
polarity = "positive" | "negative" | "neutral" | "measured"
```

- **positive**: Relationship strengthens/enables/supports target
- **negative**: Relationship weakens/prevents/contradicts target
- **neutral**: Relationship describes without judgment
- **measured**: Relationship is quantitative, not qualitative

## Combining Direction + Polarity

### Causation Category Examples

| Type | Direction | Polarity | Meaning |
|------|-----------|----------|---------|
| CAUSES | outward | neutral | A produces B (no judgment) |
| ENABLES | outward | positive | A makes B possible (helpful) |
| PREVENTS | outward | negative | A blocks B (inhibiting) |
| INFLUENCES | outward | neutral | A affects B (unspecified how) |
| RESULTS_FROM | inward | neutral | A follows from B (reverse causation) |

### Evidential Category Examples

| Type | Direction | Polarity | Meaning |
|------|-----------|----------|---------|
| SUPPORTS | outward | positive | A provides evidence for B |
| REFUTES | outward | negative | A provides evidence against B |
| EXEMPLIFIES | outward | positive | A is concrete example of B |
| MEASURED_BY | inward | measured | A quantified by B |

### Semantic Category Examples

| Type | Direction | Polarity | Meaning |
|------|-----------|----------|---------|
| SIMILAR_TO | bidirectional | positive | A and B share properties |
| CONTRASTS_WITH | bidirectional | negative | A and B differ meaningfully |
| OPPOSITE_OF | bidirectional | negative | A is inverse of B |
| ANALOGOUS_TO | bidirectional | positive | A maps to B metaphorically |

### Temporal Category Examples

| Type | Direction | Polarity | Meaning |
|------|-----------|----------|---------|
| PRECEDES | outward | neutral | A happens before B |
| CONCURRENT_WITH | bidirectional | neutral | A and B simultaneous |
| EVOLVES_INTO | outward | positive | A transforms into B |

## Benefits of Orthogonal Model

### 1. Richer Semantic Query

```python
# Query by direction
"Show me all outward causal relationships"
→ CAUSES, ENABLES, PREVENTS, INFLUENCES

# Query by polarity
"Show me all negative relationships from Ego"
→ Ego PREVENTS enlightenment, Ego CONTRADICTS selflessness

# Query by both
"Show me bidirectional positive relationships"
→ SIMILAR_TO, ANALOGOUS_TO, EQUIVALENT_TO

# Query by strength + polarity
"Show me relationships with negative polarity"
→ PREVENTS, CONTRADICTS, REFUTES, OPPOSITE_OF
```

### 2. Auto-Correction Heuristics

```python
# LLM says: "A ENABLED_BY B" (wrong type)

# Fuzzy match finds: ENABLES (similarity 0.92)
# Direction check:
#   - ENABLED_BY suggests "inward" (passive voice)
#   - ENABLES has direction="outward"
#   - Polarity: positive (enabling is helpful)

# Auto-correction options:
# Option 1: Flip edge
#   from=A, to=B, type=ENABLED_BY
#   → from=B, to=A, type=ENABLES ✓

# Option 2: Accept as new type
#   Store ENABLED_BY with direction="inward", polarity="positive"
```

### 3. Prompt Engineering

```python
EXTRACTION_PROMPT = """
Relationship types grouped by semantics:

OUTWARD POSITIVE (from → to, enabling/supporting):
  CAUSES, ENABLES, SUPPORTS, PRODUCES, ...

OUTWARD NEGATIVE (from → to, blocking/contradicting):
  PREVENTS, REFUTES, CONTRADICTS, OPPOSES, ...

INWARD (from ← to, receiving/resulting):
  RESULTS_FROM, DERIVED_FROM, MEASURED_BY, ...

BIDIRECTIONAL POSITIVE (no direction, similar/connected):
  SIMILAR_TO, ANALOGOUS_TO, EQUIVALENT_TO, ...

BIDIRECTIONAL NEGATIVE (no direction, opposing/contrasting):
  CONTRASTS_WITH, OPPOSITE_OF, ...

Example:
- "Meditation ENABLES enlightenment" → outward positive
- "Ego PREVENTS enlightenment" → outward negative
- "Suffering RESULTS_FROM attachment" → inward neutral
- "Ego OPPOSITE_OF selflessness" → bidirectional negative
"""
```

### 4. Validation Rules

```python
def validate_relationship_semantics(rel, vocab):
    rel_type = vocab[rel['relationship_type']]

    # Check 1: Direction consistency
    if rel_type.direction == "bidirectional":
        # Can create either (A→B) or (B→A), both valid
        # Normalize to alphabetical order for deduplication
        pass

    # Check 2: Polarity consistency
    if rel_type.polarity == "negative" and rel.confidence > 0.9:
        # Negative relationships are strong statements
        # High confidence makes sense
        pass

    # Check 3: Direction + sentence structure
    if "by" in rel.source_sentence and rel_type.direction == "outward":
        # "A is enabled by B" suggests inward semantics
        # But ENABLES is outward
        # → Possible edge flip needed
        flag_for_review(rel)
```

## Proposed Schema Extension

### Vocabulary Metadata

```python
{
    "relationship_type": "ENABLES",
    "category": "causation",
    "direction_semantics": "outward",  # ← Already proposed
    "polarity": "positive",            # ← New dimension
    "symmetric": False,                # ← Derived from direction
    ...
}

{
    "relationship_type": "PREVENTS",
    "category": "causation",
    "direction_semantics": "outward",
    "polarity": "negative",            # ← Opposite effect
    "symmetric": False,
    ...
}

{
    "relationship_type": "SIMILAR_TO",
    "category": "semantic",
    "direction_semantics": "bidirectional",
    "polarity": "positive",
    "symmetric": True,                 # ← Derives from bidirectional
    ...
}
```

### Migration

```sql
ALTER TABLE kg_api.relationship_vocabulary
ADD COLUMN direction_semantics VARCHAR(20) DEFAULT 'outward',
ADD COLUMN polarity VARCHAR(20) DEFAULT 'neutral',
ADD COLUMN symmetric BOOLEAN DEFAULT FALSE;

-- Derived column
UPDATE kg_api.relationship_vocabulary
SET symmetric = (direction_semantics = 'bidirectional');
```

## Comparison to Other Systems

| System | Direction Model | Polarity Model | Inference | Storage |
|--------|----------------|----------------|-----------|---------|
| **Neo4j** | Always present, can ignore | Not modeled | None | Single edge |
| **RDF/OWL** | Explicit + inverseOf | Not modeled | Reasoner infers inverses | Single direction |
| **Wikidata** | Metadata property | Not modeled | Manual/bots | Single direction |
| **Ours (proposed)** | Metadata (3 values) | Metadata (4 values) | Optional validation | Single edge |

### Key Differences

**Neo4j:**
- ✅ Simple: Direction always exists
- ❌ No semantic metadata about direction meaning
- ❌ No polarity modeling

**RDF/OWL:**
- ✅ Formal semantics (owl:inverseOf)
- ✅ Automatic inference of inverse statements
- ❌ Requires reasoner (overhead)
- ❌ No polarity modeling
- ❌ Complex to set up

**Wikidata:**
- ✅ Explicit inverse property metadata
- ✅ Human-readable property descriptions
- ❌ Inverses often missing (manual maintenance)
- ❌ No polarity modeling
- ❌ Requires querying both directions

**Our Proposal:**
- ✅ Simple metadata (2 properties: direction, polarity)
- ✅ No reasoner required
- ✅ Richer semantic queries (by direction AND polarity)
- ✅ Prompt engineering guidance for LLM
- ✅ Auto-correction heuristics
- ❌ Custom approach (not standardized like OWL)

## Recommendations

### Minimal Implementation (Phase 1)

**Just direction:**
```python
direction_semantics = "outward" | "inward" | "bidirectional"
```

**Benefits:**
- Solves 90% of direction errors
- Simple to implement (~50 lines)
- Clear prompt guidance

### Full Implementation (Phase 2)

**Direction + Polarity:**
```python
direction_semantics = "outward" | "inward" | "bidirectional"
polarity = "positive" | "negative" | "neutral" | "measured"
```

**Benefits:**
- Richer semantic queries
- Better LLM guidance
- Validation heuristics
- Polarity-based graph analysis (find negative cycles, etc.)

### Comparison to Standards

**If we want OWL compatibility later:**
- `direction_semantics="bidirectional" + symmetric=true` → `owl:SymmetricProperty`
- `direction_semantics="inward"` → Could define `owl:inverseOf` relationship
- Polarity is custom (not in OWL standard)

**Trade-off:**
- OWL gives formal semantics + reasoner inference
- Our approach gives simplicity + prompt engineering utility
- Can bridge later if needed

## Conclusion

**Your insight is correct:** Direction and polarity are orthogonal properties.

**Others mostly ignore polarity:**
- Neo4j: No semantic metadata, just topology
- RDF/OWL: Focus on inverse properties, not polarity
- Wikidata: Some properties have "opposite of" but not systematic

**Our opportunity:**
- Model BOTH direction and polarity
- Use for prompt engineering (group by both dimensions)
- Enable richer semantic queries
- Start simple (direction only), extend later (add polarity)

**Simplest path forward:**
1. Phase 1: Add `direction_semantics` (outward/inward/bidirectional)
2. Test with LLM extraction, measure error reduction
3. Phase 2: Add `polarity` if semantic queries need it
