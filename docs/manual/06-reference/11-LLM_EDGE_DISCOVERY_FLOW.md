# LLM Edge Discovery Flow

**Reference Guide:** Complete path for LLM-discovered relationship types from extraction to categorization.

**Related ADRs:**
- ADR-032: Automatic Edge Vocabulary Expansion
- ADR-047: Probabilistic Vocabulary Categorization
- ADR-048: Vocabulary Metadata as Graph

---

## Overview

When the LLM extracts a new relationship type that doesn't exist in the vocabulary, the system automatically:
1. Adds it to the vocabulary
2. Generates its embedding
3. **Computes its semantic category** using probabilistic categorization
4. Creates graph metadata nodes

This transforms opaque "llm_generated" types into semantically meaningful categories.

---

## Complete Flow

### 1. Discovery During Ingestion

**Location:** `src/api/lib/ingestion.py:383-412`

```python
# LLM extracts relationship from text
llm_rel_type = "ENHANCES"  # From LLM extraction

# Try to fuzzy-match against existing vocabulary
canonical_type, category, similarity = normalize_relationship_type(
    llm_rel_type,
    age_client=age_client
)

if not canonical_type:
    # New type discovered - accept it (ADR-032)
    canonical_type = llm_rel_type.strip().upper()
    category = "llm_generated"  # Temporary placeholder

    # Add to vocabulary with auto-categorization
    age_client.add_edge_type(
        relationship_type=canonical_type,
        category=category,
        description="LLM-generated relationship type from ingestion",
        added_by="llm_extractor",
        is_builtin=False,
        ai_provider=provider,  # For embedding generation
        auto_categorize=True   # Enable ADR-047 categorization
    )
```

**Result:** New type "ENHANCES" added with temporary category "llm_generated"

---

### 2. Automatic Categorization

**Location:** `src/api/lib/age_client.py:1332-1419`

#### Step A: Add to Vocabulary Table

```sql
INSERT INTO kg_api.relationship_vocabulary
    (relationship_type, description, category, added_by, is_builtin, is_active)
VALUES ('ENHANCES', 'LLM-generated...', 'llm_generated', 'llm_extractor', FALSE, TRUE)
```

#### Step B: Generate Embedding

```python
# Convert to descriptive text
descriptive_text = "relationship: enhances"

# Generate embedding
embedding_response = ai_provider.generate_embedding(descriptive_text)
embedding = embedding_response["embedding"]  # 1536-dim vector
model = embedding_response.get("model", "text-embedding-ada-002")

# Store in database
UPDATE kg_api.relationship_vocabulary
SET embedding = '[0.023, -0.145, ...]'::jsonb,
    embedding_model = 'text-embedding-ada-002',
    embedding_generated_at = NOW()
WHERE relationship_type = 'ENHANCES'
```

**Result:** "ENHANCES" now has embedding for similarity matching

#### Step C: Compute Semantic Category (ADR-047)

```python
if auto_categorize and category == "llm_generated":
    from src.api.lib.vocabulary_categorizer import VocabularyCategorizer

    categorizer = VocabularyCategorizer(age_client, ai_provider)
    assignment = await categorizer.assign_category("ENHANCES")
```

**Categorization Algorithm:**

1. **Get target embedding:**
   ```python
   enhances_embedding = get_embedding("ENHANCES")
   ```

2. **Compute similarity to 30 seed types across 8 categories:**
   ```python
   CATEGORY_SEEDS = {
       'causation': ['CAUSES', 'ENABLES', 'PREVENTS', 'INFLUENCES', 'RESULTS_FROM'],
       'composition': ['PART_OF', 'COMPOSED_OF', 'CONTAINS', 'COMPLEMENTS'],
       'logical': ['IMPLIES', 'CONTRADICTS', 'PRESUPPOSES'],
       'evidential': ['SUPPORTS', 'REFUTES', 'EXEMPLIFIES'],
       'semantic': ['SIMILAR_TO', 'ANALOGOUS_TO', 'OPPOSITE_OF'],
       'temporal': ['PRECEDES', 'CONCURRENT_WITH', 'EVOLVES_INTO'],
       'dependency': ['DEPENDS_ON', 'REQUIRES', 'CONSUMES', 'PRODUCES'],
       'derivation': ['DERIVED_FROM', 'GENERATED_BY', 'BASED_ON']
   }

   for category, seeds in CATEGORY_SEEDS.items():
       similarities = []
       for seed in seeds:
           seed_embedding = get_embedding(seed)
           sim = cosine_similarity(enhances_embedding, seed_embedding)
           similarities.append(sim)

       # Category score = max similarity (satisficing, not mean)
       category_scores[category] = max(similarities)
   ```

3. **Assign primary category:**
   ```python
   # Example scores
   scores = {
       'causation': 0.85,      # ← Winner
       'composition': 0.45,
       'logical': 0.32,
       'evidential': 0.51,     # ← Runner-up
       'semantic': 0.28,
       'temporal': 0.15,
       'dependency': 0.38,
       'derivation': 0.22
   }

   primary_category = 'causation'
   confidence = 0.85
   ambiguous = (0.51 > 0.70)  # False - not ambiguous
   ```

4. **Update database:**
   ```sql
   UPDATE kg_api.relationship_vocabulary
   SET category = 'causation',                    -- Was "llm_generated"
       category_source = 'computed',
       category_confidence = 0.85,
       category_scores = '{"causation": 0.85, ...}'::jsonb,
       category_ambiguous = false
   WHERE relationship_type = 'ENHANCES'
   ```

**Log Output:**
```
🎯 Auto-categorized 'ENHANCES' → causation (confidence: 85%)
```

#### Step D: Create Graph Metadata

```cypher
MERGE (v:VocabType {name: 'ENHANCES'})
SET v.category = 'causation',           # Computed category, not "llm_generated"
    v.description = 'LLM-generated relationship type from ingestion',
    v.is_builtin = 'f',
    v.is_active = 't',
    v.added_by = 'llm_extractor',
    v.usage_count = 0
RETURN v.name as name
```

**Result:** `:VocabType` node created with proper semantic category

---

## Final Result

### Before (Without Auto-Categorization)

```bash
kg vocab list
```

```
TYPE           CATEGORY          CONF    EDGES     STATUS
ENHANCES       llm_generated     --      5         ✓
```

**Problems:**
- ❌ No semantic meaning
- ❌ Can't match similar types ("IMPROVES" vs "ENHANCES")
- ❌ Can't filter by category
- ❌ No explainability

### After (With Auto-Categorization)

```bash
kg vocab list
```

```
TYPE           CATEGORY          CONF    EDGES     STATUS
ENHANCES       causation         85%     5         ✓
```

**Benefits:**
- ✅ Semantic meaning: "ENHANCES" is a causal relationship
- ✅ Similar types cluster: "IMPROVES", "STRENGTHENS" → causation
- ✅ Graph filters: Show all `category='causation'` relationships
- ✅ Explainable: Users understand what the relationship means

---

## Category Semantics

The 8 semantic categories emerge from embedding similarity to 30 hand-validated seed types:

| Category | Meaning | Example Seeds |
|----------|---------|---------------|
| **causation** | One thing causes or influences another | CAUSES, ENABLES, PREVENTS, INFLUENCES |
| **composition** | Part-whole relationships | PART_OF, COMPOSED_OF, CONTAINS |
| **logical** | Logical implications and contradictions | IMPLIES, CONTRADICTS, PRESUPPOSES |
| **evidential** | Evidence and support relationships | SUPPORTS, REFUTES, EXEMPLIFIES |
| **semantic** | Similarity and contrast | SIMILAR_TO, ANALOGOUS_TO, OPPOSITE_OF |
| **temporal** | Time-based ordering | PRECEDES, CONCURRENT_WITH, EVOLVES_INTO |
| **dependency** | Dependencies and requirements | DEPENDS_ON, REQUIRES, CONSUMES |
| **derivation** | Origin and derivation | DERIVED_FROM, GENERATED_BY, BASED_ON |

---

## Confidence Thresholds

| Confidence | Interpretation | Action |
|------------|----------------|--------|
| ≥ 70% | **High confidence** | Auto-categorize without warning |
| 50-69% | **Medium confidence** | Auto-categorize with log message |
| < 50% | **Low confidence** | Still auto-categorize, but flag for review |

**Ambiguity Detection:**
- If runner-up score > 0.70, type is flagged as `category_ambiguous = true`
- Example: "IMPLEMENTS" might score high for both "logical" and "causation"

---

## Example: Real Categorization

### Discovery Log

```
15:19:47 | INFO | src.api.lib.ingestion | 🆕 New edge type discovered: 'ADDRESSES' (embedding generated)
15:19:47 | INFO | src.api.lib.age_client | 🎯 Auto-categorized 'ADDRESSES' → causation (confidence: 72%)

15:19:48 | INFO | src.api.lib.ingestion | 🆕 New edge type discovered: 'INCLUDES' (embedding generated)
15:19:48 | INFO | src.api.lib.age_client | 🎯 Auto-categorized 'INCLUDES' → composition (confidence: 88%)

15:19:49 | INFO | src.api.lib.ingestion | 🆕 New edge type discovered: 'ENHANCES' (embedding generated)
15:19:49 | INFO | src.api.lib.age_client | 🎯 Auto-categorized 'ENHANCES' → causation (confidence: 85%)
```

### Verification

```bash
kg vocab list | grep -E "ADDRESSES|INCLUDES|ENHANCES"
```

```
ADDRESSES      causation         72%     1         ✓
INCLUDES       composition       88%     4         ✓
ENHANCES       causation         85%     5         ✓
```

### Category Scores (Detail View)

```bash
kg vocab category-scores ENHANCES
```

```json
{
  "relationship_type": "ENHANCES",
  "category": "causation",
  "confidence": 0.85,
  "ambiguous": false,
  "scores": {
    "causation": 0.85,
    "evidential": 0.51,
    "composition": 0.45,
    "dependency": 0.38,
    "logical": 0.32,
    "semantic": 0.28,
    "derivation": 0.22,
    "temporal": 0.15
  },
  "runner_up": {
    "category": "evidential",
    "score": 0.51
  }
}
```

---

## Configuration

### Enable/Disable Auto-Categorization

**Default:** Enabled (`auto_categorize=True`)

**Disable for specific call:**
```python
age_client.add_edge_type(
    relationship_type="CUSTOM_TYPE",
    category="llm_generated",
    auto_categorize=False  # Skip categorization
)
```

**When to disable:**
- Testing vocabulary system
- Debugging categorization issues
- Manual category assignment needed

---

## Fallback Behavior

If auto-categorization fails (e.g., embedding generation error, no seed embeddings available):

1. **Warning logged:**
   ```
   WARNING | Failed to auto-categorize 'ENHANCES': No embedding found for seed type 'CAUSES'
   ```

2. **Category remains:** `"llm_generated"`

3. **Operation continues:** Type is still added to vocabulary

4. **Manual fix:** Run `kg vocab refresh-categories` to retry

---

## Manual Recategorization

### Refresh All LLM-Generated Types

```bash
kg vocab refresh-categories
```

**Effect:**
- Recomputes categories for all types with `category_source='computed'`
- Updates confidence scores
- Detects new ambiguities

### Refresh Specific Type

```bash
kg vocab refresh-categories --type ENHANCES
```

### View Category Scores Before Committing

```bash
kg vocab category-scores ENHANCES
```

---

## Performance Impact

| Operation | Time Added | Impact |
|-----------|------------|--------|
| **Embedding generation** | ~100ms | Already required for fuzzy matching |
| **Category computation** | ~10ms | 30 cosine similarities (fast) |
| **Database update** | ~5ms | Single UPDATE query |
| **Total overhead** | ~115ms | Negligible in 2-3 minute ingestion jobs |

**Optimization:**
- Categorization only runs once per unique type
- Subsequent chunks reuse existing vocabulary
- Background ingestion pipeline already async

---

## Troubleshooting

### Problem: All types remain "llm_generated"

**Cause:** Auto-categorization disabled or seed embeddings missing

**Fix:**
```bash
# Check if seed types have embeddings
kg vocab list --include-builtin | grep -E "CAUSES|ENABLES|IMPLIES"

# Regenerate embeddings if missing
kg admin regenerate-embeddings --ontology "System Seeds"

# Retry categorization
kg vocab refresh-categories
```

---

### Problem: Unexpected category assigned

**Cause:** Embedding similarity led to different category than expected

**Investigation:**
```bash
# View full category scores
kg vocab category-scores SUSPICIOUS_TYPE

# Check similarity to seed types manually
kg vocab show SUSPICIOUS_TYPE --verbose
```

**Fix (if needed):**
```bash
# Manual override (stores in database)
kg vocab update SUSPICIOUS_TYPE --category causation --manual
```

---

### Problem: High ambiguity flag

**Symptom:** `category_ambiguous = true`, runner-up score > 0.70

**Investigation:**
```bash
kg vocab category-scores AMBIGUOUS_TYPE
# Check runner_up category and score
```

**Interpretation:**
- Type genuinely spans multiple categories (e.g., "IMPLEMENTS" = logical + causation)
- Not necessarily an error - indicates semantic richness

**Action:**
- Accept computed category (highest score wins)
- OR manually assign based on domain knowledge
- OR merge with existing type if truly redundant

---

## Architecture Notes

### Why Satisficing (Max) Instead of Mean?

**Problem with Mean:**
```python
# PREVENTS has semantic duality
similarity('PREVENTS', 'CAUSES') = 0.85      # High (causal)
similarity('PREVENTS', 'OPPOSITE_OF') = 0.78  # High (opposite polarity)

# Mean would dilute signal
mean([0.85, 0.78, 0.15, 0.22, ...]) = 0.42  # Lost causation signal
```

**Satisficing (Max):**
```python
# Max preserves strongest signal
causation_score = max([0.85, ...]) = 0.85  # Preserves signal
semantic_score = max([0.78, ...]) = 0.78   # Runner-up preserved

# Winner: causation (0.85 > 0.78)
```

**Principle:** A type belongs to a category if it's similar to **any** seed in that category.

---

### Why Embeddings Instead of Rules?

**Rules approach:**
```python
if "enhance" in rel_type or "improve" in rel_type:
    category = "causation"
elif "part" in rel_type or "contain" in rel_type:
    category = "composition"
```

**Problems:**
- ❌ Doesn't scale (infinite variations)
- ❌ Misses synonyms ("AUGMENTS", "STRENGTHENS")
- ❌ Requires manual updates
- ❌ No confidence scores

**Embedding approach:**
```python
category_scores = compute_similarity_to_seeds(rel_type)
category = max(category_scores)
```

**Advantages:**
- ✅ Handles unseen variations
- ✅ Catches synonyms automatically
- ✅ Self-maintaining (driven by seed types)
- ✅ Probabilistic (confidence + ambiguity)

---

## Future Enhancements

### Phase 3.3: Category Nodes (ADR-048)

Currently category is a property. Future: Category relationships to dedicated nodes.

```cypher
# Current (Phase 3.2)
(:VocabType {name: 'ENHANCES', category: 'causation'})

# Future (Phase 3.3)
(:VocabType {name: 'ENHANCES'})-[:IN_CATEGORY]->(:VocabCategory {name: 'causation'})
```

**Benefits:**
- Query by category traversal
- Category-level metadata (descriptions, examples)
- Category hierarchy (sub-categories)

---

### Adaptive Seed Types

**Idea:** Periodically promote high-usage custom types to seed status

```python
# ENHANCES used 500 times with consistent 'causation' categorization
# Promote to seed type for 'causation' category
CATEGORY_SEEDS['causation'].append('ENHANCES')
```

**Benefits:**
- Vocabulary learns from usage patterns
- Improves categorization accuracy over time
- Reduces dependency on hand-picked seeds

---

## Summary

**Key Points:**

1. **Automatic:** LLM-discovered types are categorized immediately during ingestion
2. **Probabilistic:** Uses embedding similarity to 30 seed types across 8 categories
3. **Satisficing:** Max similarity (not mean) preserves strongest semantic signal
4. **Transparent:** Logs categorization with confidence scores
5. **Fallback-safe:** Failures don't block ingestion, category remains "llm_generated"
6. **Auditable:** Full category scores stored in database
7. **Reconfigurable:** Can refresh categories anytime with `kg vocab refresh-categories`

**Impact:**

- Transforms opaque "llm_generated" into semantic categories
- Enables category-based filtering and graph traversals
- Improves vocabulary matching for subsequent chunks
- Provides explainability for relationship types

**Related Documentation:**

- ADR-047: Probabilistic Vocabulary Categorization
- ADR-048: Vocabulary Metadata as Graph
- ADR-032: Automatic Edge Vocabulary Expansion
- `docs/guides/VOCABULARY_CATEGORIES.md`: User guide for category management
