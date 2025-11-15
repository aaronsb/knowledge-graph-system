# Bug Report: APPEARS_IN vs APPEARS Relationship Naming Inconsistency

**Issue Type:** Bug
**Severity:** High
**Component:** Graph Schema, Query Layer, Ingestion Pipeline
**Status:** Fixed

---

## Summary

The codebase had a systematic naming inconsistency: code created and queried `APPEARS_IN` relationships, but the actual relationship type in the graph was `APPEARS` (without `_IN`). This caused:
- Query failures (no results returned)
- Ontology statistics showing 0 concepts
- Concept details not displaying source associations

---

## Problem

### The Inconsistency

**Code created/queried:** `[:APPEARS_IN]`
**Graph contained:** `[:APPEARS]`

### Impact

**Query failures:**
```cypher
-- What code tried to query:
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
-- Result: No matches (relationship type doesn't exist)

-- What graph actually contained:
MATCH (c:Concept)-[:APPEARS]->(s:Source)
-- Result: Correct matches
```

**Visible symptoms:**
1. `kg ontology list` showed 0 concepts for all ontologies (fixed in commit ee520af)
2. Concept details endpoint didn't return source associations (fixed in commit 229e3a4)
3. Integrity checks reported false orphaned concepts
4. Ingestion created duplicate relationships with wrong names

### Root Cause

Inconsistency introduced during early development:
- Initial schema may have used `APPEARS_IN`
- Later changed to `APPEARS` for brevity
- Code not updated consistently throughout codebase

---

## Files Affected

### Relationship Creation (Critical Path)
- **api/lib/serialization.py** - Creates `APPEARS_IN` during ingestion
- **api/lib/integrity.py** - Creates `APPEARS_IN` during repairs
- **api/api/lib/age_client.py** - Creates `APPEARS_IN` in helper methods

### Query Layer (All Failed)
- **api/api/routes/ontology.py** - Queries for `APPEARS_IN` (5 instances)
- **api/api/routes/queries.py** - Queries for `APPEARS_IN` (3 instances)
- **api/api/services/embedding_worker.py** - Queries for `APPEARS_IN`
- **api/api/services/query_service.py** - Queries for `APPEARS_IN` (3 instances)
- **api/lib/age_ops.py** - Queries for `APPEARS_IN` (5 instances)

### Documentation & Metadata
- **api/api/lib/backup_integrity.py** - Lists `APPEARS_IN` as structural type
- **api/api/lib/gexf_exporter.py** - Color mapping for `APPEARS_IN`
- **api/admin/check_integrity.py** - Comment references `APPEARS_IN`
- **api/admin/prune.py** - Comment references `APPEARS_IN`

**Total instances:** ~40+ across 12 files

---

## Solution

### Global Find-Replace

Changed all instances of `APPEARS_IN` → `APPEARS` across entire codebase:

```bash
# Files modified (12 total):
api/lib/serialization.py
api/lib/integrity.py
api/lib/age_ops.py
api/api/lib/age_client.py
api/api/lib/backup_integrity.py
api/api/lib/gexf_exporter.py
api/api/routes/ontology.py
api/api/routes/queries.py
api/api/services/embedding_worker.py
api/api/services/query_service.py
api/admin/check_integrity.py
api/admin/prune.py
```

### Verification

```bash
# Before fix:
grep -r "APPEARS_IN" api --include="*.py" | wc -l
# 40+ matches

# After fix:
grep -r "APPEARS_IN" api --include="*.py" | wc -l
# 0 matches
```

---

## Testing

### Before Fix

```bash
# Ontology stats show 0 concepts
kg ontology list
# Genesis: 0 concepts
# Exodus: 0 concepts

# Concept details missing sources
kg search details <concept-id>
# No sources returned
```

### After Fix

```bash
# Ontology stats show correct counts
kg ontology list
# Genesis: 252 concepts
# Exodus: 172 concepts

# Concept details show sources
kg search details <concept-id>
# Sources: Genesis (para 23), Exodus (para 15), ...
```

---

## Related Issues

- **Commit ee520af** - Fixed `APPEARS_IN` in ontology.py line 64 (partial fix)
- **Commit 229e3a4** - Fixed `APPEARS_IN` in queries.py line 387 (partial fix)
- **This fix** - Systematic global fix of all instances

---

## Prevention

### Lessons Learned

1. **Schema changes must be global** - Renaming relationship types requires codebase-wide update
2. **Use constants** - Define relationship types as constants to prevent typos:
   ```python
   # constants.py
   REL_APPEARS = "APPEARS"
   REL_EVIDENCED_BY = "EVIDENCED_BY"
   REL_FROM_SOURCE = "FROM_SOURCE"
   ```
3. **Test coverage** - Integration tests should verify relationship types match schema
4. **Linting** - Could add linter rule to check relationship type consistency

### Future Architecture

This bug revealed a deeper architectural issue: `APPEARS` is hardcoded as a structural relationship type, unlike `SUPPORTS`/`CONTRADICTS` which use the vocabulary system.

See:
- **ADR-065** - Vocabulary-Based Provenance Relationships
- **ENHANCEMENT-VOCABULARY-APPEARS.md** - Implementation plan

---

## Commit

Fixed in branch: `feature/vocabulary-based-appears`

All `APPEARS_IN` → `APPEARS` replacements completed.
