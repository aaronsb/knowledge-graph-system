# Vocab CLI Errors Investigation

**Date**: 2026-01-26
**Branch**: fix/vocab-cli-errors

## Summary

QA investigation of `kg vocab *` commands revealed one critical bug in the API.

## Commands Tested

| Command | Status | Notes |
|---------|--------|-------|
| `kg vocab list` | OK | Works correctly |
| `kg vocab status` | OK | Works correctly |
| `kg vocab category-scores <type>` | OK | Works correctly |
| `kg vocab analyze <type>` | OK | Works correctly |
| `kg vocab similar <type>` | OK | Works correctly |
| `kg vocab opposite <type>` | OK | Works correctly |
| `kg vocab search <query>` | ERROR | Returns error when query doesn't match an exact type |
| `kg vocab consolidate --dry-run` | OK | Works correctly |
| `kg vocab config` | OK | Works correctly |
| `kg vocab profiles list` | OK | Works correctly |
| `kg vocab sync --dry-run` | OK | Works correctly |
| `kg vocab epistemic-status list` | OK | Returns empty (no stored data) |
| `kg vocab epistemic-status show <type>` | OK | Shows UNCLASSIFIED |
| `kg vocab epistemic-status measure` | PARTIAL | Measurement runs but storage fails |

## Critical Bug: Epistemic Status Storage Failure

### Symptoms
When running `kg vocab epistemic-status measure`, measurements are calculated correctly but fail to persist to the graph. The API logs show:

```
ERROR | api.app.lib.age_client | Error: syntax error at or near ""total_edges""
WARNING | api.app.services.epistemic_status_service | Failed to store epistemic status for <TYPE>: syntax error at or near ""total_edges""
```

This error repeats for every vocabulary type (97 times).

### Root Cause
**File**: `api/app/lib/age_client.py:127-130`

When the AGE client handles dict parameters, it converts them to JSON:
```python
elif isinstance(value, (list, dict)):
    value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
    query = query.replace(f"${key}", value_str)
```

The problem: `json.dumps()` produces `{"total_edges": 1}` (quoted keys), but Cypher expects `{total_edges: 1}` (unquoted keys). The quoted format causes a syntax error.

**File**: `api/app/services/epistemic_status_service.py:292-298`

The service passes the stats dict directly:
```python
params = {
    'stats': data['stats']  # Dict with keys like 'total_edges', 'avg_grounding', etc.
}
```

### Fix Options

1. **Store as JSON string** (recommended): Wrap dict values in quotes so they're stored as string literals
   ```python
   # In age_client.py
   elif isinstance(value, (list, dict)):
       value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
       query = query.replace(f"${key}", f"'{value_str}'")  # Add quotes!
   ```

2. **Convert to Cypher map format**: Transform Python dict to Cypher-compatible format (more complex)

3. **Serialize before passing**: Have callers serialize dicts to JSON strings before passing
   ```python
   # In epistemic_status_service.py
   'stats': json.dumps(data['stats'])  # Caller serializes
   ```

## Minor Issues

### `kg vocab search` Error Message
When searching with a phrase like "causes something", it tries to find an embedding for "CAUSES_SOMETHING" (the uppercased, underscored version) and fails:
```
No embedding found for relationship type: CAUSES_SOMETHING
```

This is expected behavior (no matching type exists), but the error message is confusing. The CLI should clarify this is a semantic search that requires existing types.

## Resolution

**Fixed**: Dict serialization in `age_client.py` - now wraps dicts in quotes to store as JSON strings.

**Verified**: `kg vocab epistemic-status measure` now stores all 97 types successfully.

**GitHub Issue**: #220 proposes native Cypher map syntax for future consideration.

## Remaining Minor Issue

`kg vocab search` error messaging could be improved (low priority).
