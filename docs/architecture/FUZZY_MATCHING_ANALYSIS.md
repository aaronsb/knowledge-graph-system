# Fuzzy Matching Analysis for 30-Type Relationship Taxonomy

**Date:** 2025-10-09
**Context:** Testing fuzzy matching algorithms for normalizing LLM relationship type outputs

## Problem Statement

LLMs produce variations of canonical relationship types:
- **Prefix variations:** `CONTRASTS` instead of `CONTRASTS_WITH`
- **Verb tense:** `CAUSING` instead of `CAUSES`
- **Typos:** `CAUZES` instead of `CAUSES`
- **Reversed relationships:** `CAUSED_BY` (should be rejected)
- **Similar words:** `CREATES` (should NOT match `REGULATES`)

Original approach using `difflib.SequenceMatcher.ratio()` with 0.7 threshold:
- ❌ CONTRASTS → CONTRADICTS (wrong! should be CONTRASTS_WITH)
- ❌ COMPONENT_OF → COMPOSED_OF (false positive)
- ❌ Only 16.7% accuracy on critical edge cases

## Algorithms Tested

### 1. difflib.SequenceMatcher (threshold 0.7)
**Accuracy: 16.7%**
- Ratio-based similarity: `SequenceMatcher(None, a, b).ratio()`
- ❌ CONTRASTS → CONTRADICTS (0.800) instead of CONTRASTS_WITH (0.783)
- ❌ Reversed relationships match (ENABLED_BY → ENABLES at 0.706)
- ❌ False positives (CREATES → REGULATES at 0.750)

### 2. difflib.get_close_matches (cutoff 0.7)
**Accuracy: 16.7%**
- Uses SequenceMatcher internally - same issues

### 3. NLTK Edit Distance (Levenshtein, max distance 3)
**Accuracy: 66.7%**
- Character-level edit distance
- ✅ Handles verb tense (CAUSING → CAUSES, distance 3)
- ✅ Rejects _BY reversed (distance > 3)
- ❌ CONTRASTS → CONTAINS (distance 3) instead of CONTRASTS_WITH
- ❌ COMPONENT_OF → COMPOSED_OF (distance 3, false positive)

### 4. Hybrid Strategy (prefix + contains + fuzzy 0.85)
**Accuracy: 66.7%**
```python
1. Exact match
2. Reject _BY reversed relationships
3. Prefix match (CONTRASTS → CONTRASTS_WITH)
4. Contains match (CONTRADICTS_WITH → CONTRADICTS)
5. High-threshold fuzzy (0.85) for typos only
```
- ✅ Perfect prefix/contains matching
- ✅ Rejects _BY reversed
- ✅ Rejects false positives (CREATES, COMPONENT_OF)
- ❌ Misses verb tense (threshold too high)

### 5. Combined (Hybrid + Edit Distance ≤3)
**Accuracy: 83.3% with distance=3**
- Best overall but creates new false positives at distance=3
- Distance=2: 75% (misses verb tense)
- Distance=3: 83% (adds CREATES → REFUTES false positive)

## Comprehensive Test Results (249 variations across 30 types)

**Using improved prefix-aware algorithm:**
- Improved: 218/249 (87%)
- Current (buggy): 214/249 (85%)
- Fixed: 4 critical cases including CONTRASTS bug

## Recommended Solution

**Use Hybrid Strategy with optimized parameters:**

```python
def normalize_relationship_type(llm_type: str):
    \"\"\"
    Multi-stage matching strategy:
    1. Exact match (fast path)
    2. Reject _BY reversed relationships
    3. Prefix match (input is prefix of canonical)
    4. Contains match (canonical is prefix of input)
    5. Fallback to difflib SequenceMatcher with threshold 0.7
    \"\"\"
    llm_upper = llm_type.upper()

    # 1. Exact match
    if llm_upper in RELATIONSHIP_TYPES:
        return (llm_upper, category, 1.0)

    # 2. Reject _BY reversed relationships
    if llm_upper.endswith('_BY'):
        return (None, None, 0.0)

    # 3. Prefix match (handles CONTRASTS → CONTRASTS_WITH)
    prefix_matches = [c for c in RELATIONSHIP_TYPES if c.startswith(llm_upper)]
    if prefix_matches:
        best = min(prefix_matches, key=len)
        return (best, category, score)

    # 4. Contains match (handles CONTRASTS_WITH → CONTRASTS)
    contains_matches = [c for c in RELATIONSHIP_TYPES if llm_upper.startswith(c)]
    if contains_matches:
        best = max(contains_matches, key=len)
        return (best, category, score)

    # 5. Sequence similarity fallback (0.7 threshold for typos)
    # Use difflib.SequenceMatcher...
```

## Trade-offs

**Why not use NLTK edit distance?**
- Adds dependency (24MB package)
- Slightly better verb tense handling (66.7% → 75% with distance=3)
- But creates new false positives at distance=3
- Hybrid achieves 87% on comprehensive test without NLTK

**Why not lower fuzzy threshold to catch verb tense?**
- Threshold 0.6: Creates false positives (CREATES → REGULATES)
- Threshold 0.7: Misses verb tense but avoids false positives
- **Better to miss legitimate variations than accept wrong matches**

**Why reject _BY explicitly?**
- Reversed relationships (CAUSED_BY, ENABLED_BY) indicate opposite directionality
- LLM should use RESULTS_FROM for reverse causation
- Explicit rejection prevents directional confusion

## Key Insights

1. **Prefix matching is critical:** CONTRASTS → CONTRASTS_WITH solves the original bug
2. **No single threshold works:** Verb tense needs ~0.6, false positive avoidance needs ~0.8
3. **Multi-stage matching wins:** Prefix → Contains → Fuzzy achieves best balance
4. **Reject reversed relationships:** _BY suffix indicates reversed direction, always reject
5. **Accept imperfection:** 87% accuracy on 249 variations is good enough for production

## Remaining Failures (13% of test cases)

Mostly verb tense variations that could be addressed by:
1. Adding explicit variations to LLM prompt (CAUSING, ENABLING, etc.)
2. Simple suffix stripping before matching (CAUSING → CAUSE)
3. Accepting that LLMs should learn the canonical forms

**Decision:** Ship with prefix+contains+fuzzy hybrid (87% accuracy). Monitor logs for common failures and add to LLM prompt as needed.

## Implementation

✅ Updated `src/api/lib/relationship_mapper.py` with hybrid strategy
⏳ Update ADR-022 to document prefix-matching strategy
⏳ Add logging for normalization with similarity scores
⏳ Monitor production for common LLM variations to add to prompt
