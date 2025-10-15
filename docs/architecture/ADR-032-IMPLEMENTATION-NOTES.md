# ADR-032 Implementation Quick Reference

**Status:** Implementation Guide
**Date:** 2025-10-15
**Related:** ADR-032-automatic-edge-vocabulary-expansion.md

## Critical Implementation Details

### 1. Sliding Windows

**Edge Types:**
- MIN: 30 (protected core, never prune)
- MAX: 90 (soft limit, trigger optimization)
- HARD: 200 (block expansion, force curator)

**Categories:**
- MIN: 8 (protected core)
- MAX: 15 (hard limit)
- MERGE_THRESHOLD: 12 (start flagging merge opportunities)

### 2. Confidence Thresholds

**Category Classification:**
- `>= 0.3`: Assign to existing category (good fit)
- `< 0.3`: Propose new category (poor fit to all)

**Synonym Detection:**
- `>= 0.90`: High similarity, suggest merge
- `0.70-0.89`: Moderate similarity, flag for review
- `< 0.70`: Not synonyms

**AITL Decisions:**
- `>= 0.7`: Execute AI decision
- `< 0.7`: Fallback to HITL (low confidence)

### 3. Value Score Formula

```python
value_score = (
    edge_count * 1.0 +                    # Base: how many edges exist
    (avg_traversal / 100.0) * 0.5 +       # Usage: how often queried
    (bridge_count / 10.0) * 0.3 +         # Structural: connects subgraphs
    max(0, trend_14d) * 0.2               # Momentum: growing usage
)
```

**Bridge Detection:**
```python
# Low-activation node connecting to high-activation nodes
c_from.access_count < 10      # Source rarely accessed
c_to.access_count > 100       # Destination frequently accessed
```

### 4. Aggressiveness Zones

```
Position = (current_size - MIN) / (MAX - MIN)  # 0.0 to 1.0

Aggressiveness = CURVE.get_y_for_x(Position)

Zones:
  0.0-0.2: monitor  (just watch, no action)
  0.2-0.5: watch    (flag opportunities)
  0.5-0.7: merge    (prefer synonym merging)
  0.7-0.9: mixed    (merge + prune zero-edge)
  0.9-1.0: emergency (aggressive batch pruning)
```

### 5. Merge vs Prune Decision Tree

```
Need to reduce vocabulary?
  ├─ Check synonyms (similarity >= 0.90)
  │  ├─ Found? → MERGE (preserves edges)
  │  └─ Not found? → Continue
  │
  ├─ Check zero-edge types (edge_count == 0)
  │  ├─ Found? → PRUNE (safe, no data loss)
  │  └─ Not found? → Continue
  │
  └─ Last resort → PRUNE low-value types (lossy)
```

**Batching:**
```python
target_reduction = (current_size - MAX) + buffer  # buffer = 5
# Remove MORE than minimum to avoid immediate re-trigger
```

### 6. Bezier Curve Profiles

**Default: "aggressive"**
```python
CubicBezier(0.1, 0.0, 0.9, 1.0)
# Stays passive until 75 types, then sharp acceleration
```

**Other profiles:**
- `linear`: (0.0, 0.0, 1.0, 1.0) - constant rate
- `gentle`: (0.5, 0.5, 0.5, 0.5) - very gradual
- `exponential`: (0.7, 0.0, 0.84, 0.0) - explosive near limit
- `ease-in-out`: (0.42, 0.0, 0.58, 1.0) - smooth S-curve

### 7. Protected Sets

**Protected Edge Types:**
```python
is_builtin == TRUE  # 30 core types from ADR-022
# Can be merged into, but never deleted
```

**Protected Categories:**
```python
BUILTIN_CATEGORIES = [
    "logical_truth", "causal", "structural", "evidential",
    "similarity", "temporal", "functional", "meta"
]
# Can be merged into, but never deleted
```

### 8. Auto-Expansion Validation

**Allowed:**
- Uppercase alphanumeric + underscores
- Length: 3-50 characters
- Not in blacklist

**Rejected:**
- Ends with `_BY` (reversed relationship)
- Contains profanity/reserved terms
- Malformed (lowercase, special chars)

### 9. Database Tables (Minimal Additions)

**Already Exists:**
- `kg_api.relationship_vocabulary` ✓
- `kg_api.skipped_relationships` ✓
- `kg_api.vocabulary_audit` ✓

**Need to Add:**
```sql
-- History tracking
kg_api.vocabulary_history (
    relationship_type VARCHAR(100),
    action VARCHAR(50),  -- 'added', 'merged', 'pruned', 'restored'
    performed_by VARCHAR(100),
    performed_at TIMESTAMPTZ,
    snapshot JSONB,
    merge_target VARCHAR(100)
)

-- Category proposals
kg_api.category_proposals (
    id SERIAL PRIMARY KEY,
    proposed_name VARCHAR(100),
    trigger_edge_type VARCHAR(100),
    confidence_scores JSONB,
    llm_reasoning TEXT,
    status VARCHAR(50),  -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMPTZ
)

-- Pruning recommendations (HITL/AITL)
kg_api.pruning_recommendations (
    id SERIAL PRIMARY KEY,
    recommendation_type VARCHAR(50),  -- 'merge', 'prune', 'mixed'
    targets JSONB,  -- Array of types/pairs
    aggressiveness FLOAT,
    reasoning TEXT,
    status VARCHAR(50),  -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMPTZ
)
```

### 10. Configuration Keys

**Environment Variables:**
```bash
VOCAB_AGGRESSIVENESS=aggressive        # Bezier profile
VOCAB_PRUNING_MODE=aitl                # naive|hitl|aitl
VOCAB_MIN=30
VOCAB_MAX=90
VOCAB_HARD_LIMIT=200
CATEGORY_MAX=15
AITL_CONFIDENCE_THRESHOLD=0.7
AITL_REASONING_MODEL=claude-3-5-sonnet-20241022
```

### 11. Key Module Dependencies

```
aggressiveness_curve.py       # Pure math, no dependencies
    ↓
vocabulary_scoring.py         # Needs: DB queries (edge_usage_stats)
    ↓
category_classifier.py        # Needs: embeddings API
    ↓
synonym_detector.py           # Needs: embeddings API
    ↓
pruning_strategies.py         # Needs: all above + LLM (AITL mode)
    ↓
vocabulary_manager.py         # Orchestrates everything
```

### 12. Testing Checklist

**Unit Tests:**
- [ ] Bezier curves: all profiles, boundary conditions
- [ ] Value scoring: each component (edges, traversals, bridge, trend)
- [ ] Category classifier: good fit (>0.3), poor fit (<0.3), edge cases
- [ ] Synonym detector: high similarity (>0.9), moderate, low
- [ ] Pruning strategies: merge preference, zero-edge pruning, last resort

**Integration Tests:**
- [ ] Vocabulary manager: auto-expansion → classification → pruning
- [ ] Database operations: insert, update, history tracking
- [ ] End-to-end: ingest → expand → trigger → optimize → approve

**Edge Cases:**
- [ ] Vocabulary at exactly MAX (90 types)
- [ ] All categories at maximum (15 categories)
- [ ] No merge candidates available
- [ ] All types have edges (can't safe-prune)
- [ ] AITL confidence exactly at threshold (0.7)
- [ ] Bezier position at 0.0, 0.5, 1.0

### 13. Implementation Order (from TODO)

**Phase 1: Worker Modules (Isolated)**
1. aggressiveness_curve.py + tests
2. vocabulary_scoring.py + tests
3. category_classifier.py + tests
4. synonym_detector.py + tests
5. pruning_strategies.py + tests

**Phase 2: Orchestration**
6. vocabulary_manager.py + tests

**Phase 3: Integration**
7. Update schema (minimal)
8. Modify age_client.py (upsert hook)
9. Add API routes
10. Add CLI commands

**Phase 4: Configuration & E2E**
11. Environment variables
12. End-to-end tests

### 14. Critical "Don't Forget" Items

- [ ] **Batching:** Always add buffer (5) when pruning to reduce re-triggers
- [ ] **Merge First:** Check synonyms before pruning anything with edges
- [ ] **High Bar:** New categories need < 0.3 confidence for ALL existing
- [ ] **Bridge Preservation:** Low-value type with high bridge_count = KEEP
- [ ] **Fallback Category:** If new category rejected, assign to closest existing
- [ ] **Audit Trail:** Log every action to vocabulary_history
- [ ] **Rollback Support:** Store snapshot in JSONB before any destructive action
- [ ] **Protected Core:** is_builtin = TRUE immune to automatic pruning
- [ ] **Category Limits:** 8 min (protected), 15 max (hard stop)
- [ ] **Edge Type Limits:** 30 min (protected), 90 soft, 200 hard

### 15. Performance Considerations

**Embedding Calls:**
- Cache embeddings for existing types (avoid re-computing)
- Batch embedding generation when possible
- Category classification: avg of 4-5 types per category = ~40 embeddings

**Database Queries:**
- Value scoring: needs edge_usage_stats + concept_access_stats joins
- Bridge detection: potentially expensive (access_count filters on large tables)
- Consider materialized views for hot paths

**LLM Calls (AITL mode):**
- ~500-1000 tokens per decision
- Cost: ~$0.01 per decision (Claude Sonnet)
- Only triggered when vocabulary exceeds limit (infrequent)

### 16. Common Pitfalls to Avoid

❌ **Don't:** Prune based on age/time (graph value is structural)
❌ **Don't:** Use hardcoded if/else thresholds (use Bezier curves)
❌ **Don't:** Delete protected types (is_builtin = TRUE)
❌ **Don't:** Create categories above limit (check before proposing)
❌ **Don't:** Merge without snapshot (need rollback capability)
❌ **Don't:** Ignore confidence thresholds (prevents bad decisions)

✅ **Do:** Batch optimizations (reduce invocations)
✅ **Do:** Prefer merging over pruning (preserves data)
✅ **Do:** Log all actions to history (auditability)
✅ **Do:** Check bridge importance (structural value)
✅ **Do:** Use embeddings for similarity (not string matching)
✅ **Do:** Respect aggressiveness curve (smooth, predictable)

---

**Quick Reference URLs:**
- Full ADR: `docs/architecture/ADR-032-automatic-edge-vocabulary-expansion.md`
- ADR-022 (30-type taxonomy): `docs/architecture/ADR-022-semantic-relationship-taxonomy.md`
- Constants: `src/api/constants.py` (RELATIONSHIP_CATEGORIES)
- Bezier visualization: https://cubic-bezier.com (for testing control points)
