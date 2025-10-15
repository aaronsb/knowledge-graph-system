# Pattern Repetition in Growth Management

**Date:** 2025-01-15
**Context:** Observed while implementing ADR-032 (vocabulary management)

## The Observation

The system uses the same organizational pattern at two different levels:

**Level 1: Managing Concepts (Nodes)**
```
Generate candidates → Check for duplicates → Merge if similar → Keep bounded
```

**Level 2: Managing Relationships (Edges)**
```
Generate edge types → Check for synonyms → Merge if similar → Keep bounded
```

Both use:
- Fuzzy similarity matching (cosine similarity on embeddings)
- Threshold-based decisions (when to merge vs. create new)
- Adaptive pressure (rules tighten as the collection grows)
- Stochastic inputs (LLM generation is non-deterministic)

## Why This Matters

**For Maintenance:**
- If you change the concept deduplication logic, consider the same change for edge vocabulary
- Tuning thresholds? Same principles apply at both levels
- Bug in merge logic? Check both implementations

**For Performance:**
- Both systems have the same scaling characteristics
- Both benefit from the same optimizations (embedding cache, batch similarity)
- Both have similar failure modes (threshold too loose → explosion, too tight → loss of nuance)

**For Testing:**
- Test cases for concept merging can inform edge vocabulary tests
- Same statistical properties (run twice, get similar but not identical results)
- Same edge cases (what happens at exactly threshold? what if embeddings are degenerate?)

## Why It's Not Surprising

This is just **the same problem appearing twice:**

**Problem:** Keep a collection from growing unbounded while preserving useful distinctions

**Solution:** Detect near-duplicates and merge them

The code implementations are different (concepts in `ingestion.py`, edges in `vocabulary_manager.py`), but the logic is the same because the problem is the same.

## Implementation Details

**Concept Level (src/api/lib/ingestion.py):**
- Fuzzy match against existing concepts: 0.85 similarity threshold
- Create new if no match found
- Evidence instances link to both new and matched concepts

**Edge Level (src/api/services/vocabulary_manager.py):**
- Synonym detection: 0.90 strong, 0.70 moderate similarity
- Value scoring to identify low-utility types
- Aggressiveness curve adjusts merge pressure based on vocabulary size

**Key Difference:** Edges have adaptive thresholds (aggressiveness curve), concepts use fixed threshold. This is because edge vocabulary has explicit size targets (30-90 types), concept space does not.

## What You Can Predict

**If vocabulary size > 90:**
- System will recommend aggressive merging
- Similar to how concept space would behave if we set CONCEPT_MAX

**If we add CONCEPT_MAX in the future:**
- We'd probably add an aggressiveness curve there too
- Would look very similar to vocabulary management
- Same tuning challenges (prevent thrashing, avoid over-consolidation)

**Adding a third level (categories, ontologies, etc.):**
- Would probably use this pattern again
- Start by copying vocabulary_manager.py structure
- Adjust similarity thresholds for the specific domain

## What This Isn't

- Not claiming the system is "emergent" or "self-aware"
- Not claiming this is a novel technique (it's standard deduplication)
- Not claiming fractal properties in the geometric sense
- Not claiming this makes the system "intelligent"

It's just the same organizational pattern used twice, which makes sense because we're solving the same class of problem twice. Like how a card game and a board game both have "take turns" even though one uses cards and one uses a board.

## Practical Takeaway

If you're adding a new feature that needs to:
1. Accept stochastic inputs (LLM, user entry, etc.)
2. Detect duplicates/near-duplicates
3. Keep a collection bounded
4. Preserve useful distinctions

Look at `vocabulary_manager.py` or the concept matching in `ingestion.py` - you're solving the same problem class, so the same approach probably works.

## References

- ADR-032: Automatic edge vocabulary expansion
- `src/api/lib/ingestion.py:match_concepts()` - Concept-level matching
- `src/api/services/vocabulary_manager.py:detect_synonyms()` - Edge-level matching
- `src/api/lib/aggressiveness_curve.py` - Adaptive threshold calculation
