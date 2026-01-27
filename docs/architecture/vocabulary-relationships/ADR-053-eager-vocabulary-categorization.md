# ADR-053: Eager Vocabulary Categorization

**Status:** Accepted
**Date:** 2025-11-01
**Implemented:** 2025-11-01
**Related ADRs:** ADR-052 (Vocabulary Expansion-Consolidation Cycle), ADR-047 (Probabilistic Vocabulary Categorization)

**Implementation Summary:** Core eager categorization was already functional in ADR-047. Fixed transaction isolation bug preventing auto-categorization. Edge types now automatically categorized during ingestion with ~65-90% confidence. Similarity analysis tools (kg vocab similar/opposite/analyze) remain as future enhancements.

## Overview

When your system learns a new relationship type like "HARMONIZES_WITH" during document ingestion, should it immediately figure out what semantic category it belongs to (causation? composition? interaction?), or should it mark it as "uncategorized" and wait for you to manually run a separate categorization command later? The lazy approach means your vocabulary sits in limbo—unusable for category-based queries until you remember to categorize it.

This ADR makes categorization happen automatically and immediately. The moment the system creates a new vocabulary type, it uses the embedding-based categorization logic (from ADR-047) to determine which semantic category it's most similar to. It's like having a librarian who immediately files each new book in the right section as it arrives, rather than stacking uncategorized books in a corner for later sorting. The implementation revealed that the core logic was already mostly there—what was missing was proper integration into the ingestion pipeline due to a database transaction isolation issue. Once fixed, new types get categorized with 65-90% confidence scores as they're created, eliminating the manual maintenance step. The vocabulary is always organized and queryable by category, without requiring you to remember to run refresh commands after ingestion completes.

---

## Context

The knowledge graph system manages edge vocabulary through a lifecycle: LLMs discover new relationship types during ingestion, and the system must categorize them into semantic groups (causation, temporal, logical, etc.) for organization and query purposes.

### Current State Machine

Vocabulary flows through a one-way state machine:

```
LLM Extraction → llm_generated → Manual Refresh → computed
    (ingestion)     (initial)    (kg vocab refresh)  (final)
```

**State Transitions:**

1. **Initial:** LLM discovers new edge type during chunk processing → `category = "llm_generated", category_source = "llm"`
2. **Classification:** User runs `kg vocab refresh-categories` → system computes category via embedding similarity → `category_source = "computed"`
3. **One-way property:** `llm_generated` → `computed` never reverses (prevents reclassification loops)

### The Bounded Exploration Model (ADR-052)

**Components:**
- **c** = 11 protected categories (causation, composition, logical, evidential, semantic, temporal, dependency, derivation, operation, interaction, modification)
- **a** = 30 protected seed types (curator-controlled via `CATEGORY_SEEDS` constant)
- **b** = LLM-generated types (unbounded, emergent during ingestion)

**Formula:**
```
Total Semantic Space = c × (a + b)

Where:
  c = bounded dimensionality (11 categories)
  a = bounded initial coverage (30 seed types)
  b = unbounded emergent expansion (LLM-discovered types)
```

**Why This Works:**
1. **Bounded initial space:** Curator controls c and a (prevents category proliferation)
2. **Emergent expansion:** LLM freely generates b (supports general methods over hand-coding)
3. **One-way classification:** State transition prevents infinite loops
4. **Consolidation cycle:** ADR-052 provides pruning and synonym merging to manage growth

### Problem: Manual Categorization Step

The current approach has inefficiencies:

1. **Lazy categorization:** New edge types remain `llm_generated` until manual refresh
2. **Extra maintenance step:** User must remember to run `kg vocab refresh-categories`
3. **Wasted computation:** We already generate embeddings during ingestion
4. **Delayed organization:** Edge types uncategorized until refresh

**Missed Opportunity:**

During ingestion, we:
1. Extract relationship type from LLM
2. Generate embedding for the type
3. Store in vocabulary table as `llm_generated`
4. **Stop** ❌

We have everything needed to categorize immediately:
- Edge type embedding (just generated)
- Category seed embeddings (already in database)
- Categorization algorithm (cosine similarity)

**Why not categorize right then?**

## Decision

**Move categorization from lazy (manual refresh) to eager (automatic during ingestion).**

### Updated State Machine

```
LLM Extraction → llm_generated → Immediate Categorization → computed
    (ingestion)     (transient)      (ingestion pipeline)    (final)
```

**New Flow:**

1. **LLM discovers edge type** → Extract "IMPLIES" from chunk
2. **Generate embedding** → Create vector representation (already happening)
3. **Categorize immediately** → Compare to category seeds via cosine similarity
4. **Store categorized** → `category = "logical", category_source = "computed"`

**State duration change:**
- **Before:** `llm_generated` persists until user runs refresh (hours/days/never)
- **After:** `llm_generated` is transient (milliseconds), immediately becomes `computed`

### Implementation

**Modify ingestion pipeline:**

```python
# src/api/lib/ingestion.py (or llm_extractor.py)

async def process_extracted_relationships(relationships: List[str], db_client):
    """Process and categorize LLM-extracted relationships."""

    for rel_type in relationships:
        # 1. Check if relationship type exists
        existing = await db_client.get_vocabulary_entry(rel_type)

        if not existing:
            # 2. Generate embedding (already happens)
            embedding = await ai_provider.generate_embedding(rel_type)

            # 3. Categorize immediately (NEW)
            category = await categorize_edge_type(
                edge_embedding=embedding,
                category_seeds=CATEGORY_SEEDS,
                db_client=db_client
            )

            # 4. Store as already-categorized
            await db_client.insert_vocabulary_entry(
                relationship_type=rel_type,
                embedding=embedding,
                category=category,
                category_source="computed",  # Not "llm"
                is_builtin=False,
                is_active=True
            )
```

**Helper function:**

```python
async def categorize_edge_type(
    edge_embedding: np.ndarray,
    category_seeds: Dict[str, List[str]],
    db_client
) -> str:
    """
    Categorize edge type by finding best-matching category via seed similarity.

    Returns category name (e.g., "logical", "temporal").
    """
    # Get embeddings for all seed types (cached in practice)
    seed_embeddings = await db_client.get_category_seed_embeddings()

    # For each category, find max similarity to any seed
    category_scores = {}
    for category, seeds in category_seeds.items():
        similarities = []
        for seed_type in seeds:
            if seed_type in seed_embeddings:
                sim = cosine_similarity(edge_embedding, seed_embeddings[seed_type])
                similarities.append(sim)

        if similarities:
            category_scores[category] = max(similarities)

    # Return category with highest similarity
    best_category = max(category_scores, key=category_scores.get)
    return best_category
```

### Backward Compatibility

**Keep `kg vocab refresh-categories` for edge cases:**

1. **Seed changes:** Curator updates `CATEGORY_SEEDS` → refresh all computed types
2. **Migration:** Categorize existing `llm_generated` entries from before this change
3. **Manual override:** User can force recategorization if needed

**Use cases:**
```bash
# Refresh all computed types (if seeds changed)
kg vocab refresh-categories --computed-only

# Refresh only uncategorized types (migration)
kg vocab refresh-categories --uncategorized-only

# Force refresh everything
kg vocab refresh-categories --force
```

## Embedding Similarity Analysis (Bonus)

With embeddings available, we can add vocabulary quality tools:

### Find Synonyms (Consolidation)

```bash
kg vocab similar IMPLIES --limit 10

# Output:
# Most similar to IMPLIES:
#   SUGGESTS      0.92  (logical)  - potential synonym
#   LEADS_TO      0.87  (causation) - semantically close
#   INDICATES     0.85  (evidential) - similar meaning
#   ...
```

### Find Antonyms (Semantic Range)

```bash
kg vocab opposite IMPLIES --limit 5

# Output:
# Least similar to IMPLIES:
#   CONTRADICTS   0.12  (logical)  - opposite meaning
#   REFUTES       0.18  (logical)  - negation
#   PREVENTS      0.23  (causation) - blocking action
```

### Validate Category Assignment

```bash
kg vocab analyze IMPLIES

# Output:
# Edge Type: IMPLIES
# Category: logical (computed)
# Category fit: 0.89 (strong match to category seeds)
#
# Most similar in same category:
#   ENTAILS       0.91
#   REQUIRES      0.88
#
# Most similar in other categories:
#   CAUSES        0.76  (causation) - may indicate miscategorization
```

**Use cases:**
1. **Synonym detection** for ADR-052 consolidation
2. **Category validation** (does assignment make sense?)
3. **Semantic structure** exploration (understand vocabulary space)
4. **Quality assurance** (identify miscategorizations)

## Consequences

### Positive

1. **No manual step:** Edge types automatically categorized during ingestion
2. **Immediate organization:** Vocabulary always properly categorized
3. **Zero marginal cost:** Leverages existing embedding generation
4. **Better UX:** Users don't need to remember refresh command
5. **Quality tools:** Similarity analysis enables vocabulary cleanup

### Negative

1. **Slight ingestion overhead:** Additional cosine similarity computation per new edge type
   - **Mitigated:** Only happens once per new type, not per edge instance
   - **Cost:** ~10-20ms per new type (negligible vs LLM extraction time)

2. **Category seeds must exist:** Requires `CATEGORY_SEEDS` to be populated
   - **Mitigated:** Already required for current refresh system
   - **Validated:** System checks on startup

### Neutral

1. **State machine change:** `llm_generated` becomes transient instead of persistent
   - **Impact:** Minimal - state still exists briefly during ingestion
   - **Benefit:** Clearer separation: uncategorized types are truly new

2. **`kg vocab refresh-categories` still needed:** For seed changes and migrations
   - **Frequency:** Rare (only when seeds change)
   - **Previous:** Regular maintenance (categorize new types)

## Implementation Plan

1. **Phase 1:** Add `categorize_edge_type()` helper function
2. **Phase 2:** Integrate into ingestion pipeline
3. **Phase 3:** Add `kg vocab similar/opposite/analyze` commands
4. **Phase 4:** Update documentation and tests

## Alternatives Considered

### 1. Keep Lazy Categorization

**Pros:** No changes needed, works today
**Cons:** Manual maintenance, delayed organization, wasted computation
**Rejected:** Eager is strictly better with no significant downsides

### 2. Background Worker Categorization

Categorize in background job after ingestion completes.

**Pros:** No ingestion latency impact
**Cons:** Added complexity, requires job queue, still delayed
**Rejected:** Overhead ~10-20ms per new type is negligible vs 2-5s LLM extraction

### 3. Defer All Categorization to Query Time

Never store category, compute on-demand via embedding similarity.

**Pros:** Always fresh, no storage
**Cons:** Query overhead, no category-based filtering in database
**Rejected:** Defeats purpose of categorization for organization

## Validation

**Success Criteria:**

1. New edge types automatically categorized during ingestion
2. `kg vocab list` shows no `llm_generated` types (unless just created)
3. Ingestion latency increase < 50ms per chunk
4. `kg vocab similar` produces sensible synonym candidates

**Testing:**

```bash
# Before: New type is llm_generated
kg ingest file test.txt
kg vocab list | grep SOME_NEW_TYPE  # category: llm_generated

# After: New type is immediately categorized
kg ingest file test.txt
kg vocab list | grep SOME_NEW_TYPE  # category: logical (or appropriate)
```

## References

**Related ADRs:**
- ADR-052: Vocabulary Expansion-Consolidation Cycle
- ADR-047: Probabilistic Vocabulary Categorization

**Technical:**
- Shannon (1948): "A Mathematical Theory of Communication"
- Mikolov et al. (2013): "Distributed Representations of Words and Phrases"

---

**Last Updated:** 2025-11-01
