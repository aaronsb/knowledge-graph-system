# Query Safety Baseline - Technical Debt

**Date:** 2025-10-27
**ADR:** ADR-048 (Vocabulary Metadata as First-Class Graph)
**Phase:** Phase 2 - Critical Path Migration ✅ COMPLETE

## Summary

~~Initial query safety audit identified **3 unsafe queries** in the codebase.~~ **All unsafe queries have been fixed!**

**Phase 1 (Complete):** Identified 3 unsafe queries that would cause catastrophic failures in Phase 3
**Phase 2 (Complete):** Fixed all 3 unsafe queries with namespace-aware alternatives
**Current Status:** ✅ **0 unsafe queries** - Ready for Phase 3

## Phase 2 Fixes (2025-10-27)

All 3 unsafe queries have been migrated to namespace-aware alternatives:

### Fix 1: Database Health Check ✅
**File:** `src/api/routes/database.py:195`
**Before:** `MATCH (n) RETURN count(n)` (counted ALL nodes)
**After:** `client.facade.count_concepts()` (namespace-aware)
**Impact:** Health check now returns correct concept count, won't be affected by vocabulary nodes

### Fix 2: Restore Worker - Delete Relationships ✅
**File:** `src/api/workers/restore_worker.py:230`
**Before:** `MATCH (n)-[r]-() DELETE r` (deleted ALL relationships)
**After:** Explicit deletion by namespace:
```python
client._execute_cypher("MATCH (c:Concept)-[r]-() DELETE r")
client._execute_cypher("MATCH (s:Source)-[r]-() DELETE r")
client._execute_cypher("MATCH (i:Instance)-[r]-() DELETE r")
```
**Impact:** Restore preserves vocabulary metadata, only clears concept graph

### Fix 3: Restore Worker - Delete Nodes ✅
**File:** `src/api/workers/restore_worker.py:233`
**Before:** `MATCH (n) DELETE n` (deleted ALL nodes)
**After:** Explicit deletion by namespace:
```python
client._execute_cypher("MATCH (c:Concept) DELETE c")
client._execute_cypher("MATCH (s:Source) DELETE s")
client._execute_cypher("MATCH (i:Instance) DELETE i")
```
**Impact:** Vocabulary nodes (:VocabType, :VocabCategory) are preserved during restore

## Original Findings (Phase 1)

### 1. Health Check Node Count
**File:** `src/api/routes/database.py:195`
**Query:** `MATCH (n) RETURN count(n) as node_count LIMIT 1`
**Purpose:** Verify graph is accessible
**Risk:** Once vocabulary is in graph, counts ALL nodes (concepts + vocabulary)

**Fix Required:**
```python
# Before (unsafe)
graph_check = client._execute_cypher(
    "MATCH (n) RETURN count(n) as node_count LIMIT 1",
    fetch_one=True
)

# After (safe)
graph_check = client._execute_cypher(
    "MATCH (n:Concept) RETURN count(n) as concept_count LIMIT 1",
    fetch_one=True
)
```

### 2. Restore Worker - Delete All Relationships
**File:** `src/api/workers/restore_worker.py:230`
**Query:** `MATCH (n)-[r]-() DELETE r`
**Purpose:** Clear database before restore
**Risk:** CRITICAL - Would delete vocabulary relationships in Phase 3

**Fix Required:**
```python
# Before (unsafe - deletes EVERYTHING)
client._execute_cypher("MATCH (n)-[r]-() DELETE r")

# After (safe - only delete concept graph)
client._execute_cypher("MATCH (n:Concept)-[r]-() DELETE r")
client._execute_cypher("MATCH (n:Source)-[r]-() DELETE r")
client._execute_cypher("MATCH (n:Instance)-[r]-() DELETE r")
# Vocabulary graph remains intact
```

### 3. Restore Worker - Delete All Nodes
**File:** `src/api/workers/restore_worker.py:233`
**Query:** `MATCH (n) DELETE n`
**Purpose:** Clear database before restore
**Risk:** CRITICAL - Would delete vocabulary nodes in Phase 3

**Fix Required:**
```python
# Before (unsafe - deletes EVERYTHING)
client._execute_cypher("MATCH (n) DELETE n")

# After (safe - only delete concept graph)
client._execute_cypher("MATCH (n:Concept) DELETE n")
client._execute_cypher("MATCH (n:Source) DELETE n")
client._execute_cypher("MATCH (n:Instance) DELETE n")
# Vocabulary graph remains intact
```

## Prioritization

| Query | Severity | Phase | Rationale |
|-------|----------|-------|-----------|
| restore_worker.py:230 | **CRITICAL** | Before Phase 3 | Would destroy vocabulary metadata |
| restore_worker.py:233 | **CRITICAL** | Before Phase 3 | Would destroy vocabulary metadata |
| database.py:195 | **HIGH** | Before Phase 3 | Would return incorrect counts |

## Migration Strategy

### Phase 1 (Current)
- ✅ Query linter identifies unsafe patterns
- ✅ Baseline documented
- ⏳ Add linter to CI to prevent new unsafe queries

### Phase 2 (Before Vocabulary Migration)
- Fix restore_worker.py to be label-aware
- Fix health check to count only concept nodes
- Verify all queries pass linter

### Phase 3 (Vocabulary Migration)
- Move vocabulary to graph only after Phase 2 complete
- Vocabulary graph isolated from restore operations
- Health checks correctly distinguish namespace

## Architectural Implication

This audit validates ADR-048's core thesis:

> **Without namespace isolation, operations that are "safe" in single-namespace graphs become catastrophic in multi-namespace graphs.**

The restore worker assumes it owns the entire graph. Once vocabulary metadata lives in the graph, this assumption breaks. GraphQueryFacade enforces namespace awareness to prevent this class of bugs.

## Phase Completion Status

### Phase 1: Foundation ✅
1. ✅ Create query linter (`scripts/lint_queries.py`)
2. ✅ Add linter to CI workflow
3. ✅ Create GraphQueryFacade with safe abstractions
4. ✅ Document baseline technical debt

### Phase 2: Critical Path Migration ✅
1. ✅ Fix restore_worker.py (CRITICAL - would destroy vocabulary)
2. ✅ Fix database.py health check (incorrect counts)
3. ✅ Re-run linter and verify 0 errors
4. ✅ Test fixes with live system

### Phase 3: Vocabulary to Graph (Ready)
- All blocking issues resolved
- Namespace safety infrastructure complete
- Safe to proceed with vocabulary migration

## Metrics

### Before Phase 2
- **Total unsafe queries:** 3
- **Critical severity:** 2 (restore worker)
- **High severity:** 1 (health check)

### After Phase 2 ✅
- **Total unsafe queries:** 0 🎉
- **Critical severity:** 0
- **High severity:** 0
- **System status:** Ready for Phase 3

---

**Last Updated:** 2025-10-27
**Next Audit:** After Phase 2 migrations complete
