# Enhancement: Cache Detailed Job Output for Async Retrieval

**Issue Type:** Enhancement
**Priority:** Medium
**Component:** Job Queue, API Design
**Related:** Vocabulary consolidation, long-running operations

---

## Summary

Store detailed job results in the job queue's `result` JSONB field to enable asynchronous retrieval of complex operation outputs. This prevents blocking API calls and provides automatic cleanup when jobs are deleted.

---

## Problem

### Current Situation

**Vocabulary consolidation** returns rich, detailed results:

```python
class ConsolidateVocabularyResponse(BaseModel):
    success: bool
    initial_size: int
    final_size: int
    size_reduction: int
    auto_executed: List[MergeResultInfo]      # Detailed merge operations
    needs_review: List[ReviewInfo]            # Pairs needing human review
    rejected: List[RejectionInfo]             # Rejected candidates
    pruned: Optional[List[str]]               # Pruned unused types
    pruned_count: Optional[int]
    message: str
```

**But the worker only stores summary counts** (`vocab_consolidate_worker.py:101-111`):

```python
result = {
    "status": "completed",
    "initial_size": initial_size,
    "final_size": final_size,
    "size_reduction": size_reduction,
    "auto_executed_count": len(results["auto_executed"]),     # Count only!
    "needs_review_count": len(results["needs_review"]),       # Count only!
    "rejected_count": len(results["rejected"]),               # Count only!
    "auto_mode": auto_mode,
    "dry_run": not auto_mode
}
```

**What's Missing:**
- ❌ Which specific types were merged?
- ❌ What was the LLM's reasoning for each merge?
- ❌ Which pairs need human review?
- ❌ What were the rejected candidates?

This detailed information is **lost** after the worker completes.

---

## Use Cases

### 1. **Post-Consolidation Review**

User runs consolidation overnight:
```bash
kg vocab consolidate --auto
# Job queued: abc123
# [Goes to sleep]
```

Next morning, wants to review what happened:
```bash
kg job show abc123
# ✅ Shows: "Merged 15 types, 3 need review"
# ❌ Cannot see: Which types? What was the reasoning?
```

### 2. **Audit Trail**

Need to understand why a specific vocabulary type was merged:
```bash
kg vocab history "knowledge representation"
# ✅ Can see: "Merged into 'knowledge modeling' on 2025-01-15"
# ❌ Cannot see: LLM reasoning, similarity score, alternative candidates
```

### 3. **Manual Review Queue**

Consolidation flagged pairs for human review:
```bash
kg vocab consolidate --auto
# Result: "3 pairs need review"
# ❌ Cannot retrieve: Which pairs? What's the similarity? Reasoning?
```

---

## Proposed Solution

### Pattern: Store Full Results in Job JSONB Field

The PostgreSQL job queue already supports storing arbitrary JSONB data in the `result` column:

```sql
CREATE TABLE kg_api.jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    ...
    result JSONB,  -- ← Store detailed output here
    ...
);
```

### Known Pattern (Ingestion)

Ingestion already stores detailed results (`ingestion_worker.py:361-374`):

```python
return {
    "status": "completed",
    "stats": {
        "chunks_processed": 42,
        "sources_created": 12,
        "concepts_created": 156,
        "concepts_linked": 89,
        "instances_created": 234,
        "relationships_created": 312
    },
    "cost": {
        "extraction": "$1.23",
        "embeddings": "$0.45",
        "total": "$1.68"
    },
    "ontology": "MyOntology",
    "filename": "document.txt"
}
```

This data is:
- ✅ Stored in job's `result` JSONB field
- ✅ Retrieved via `GET /jobs/{job_id}`
- ✅ Automatically deleted when job is deleted
- ✅ No separate storage/cleanup logic needed

### Apply Same Pattern to Consolidation

**File:** `api/api/workers/vocab_consolidate_worker.py:101-111`

**Before** (counts only):
```python
result = {
    "status": "completed",
    "initial_size": initial_size,
    "final_size": final_size,
    "size_reduction": size_reduction,
    "auto_executed_count": len(results["auto_executed"]),
    "needs_review_count": len(results["needs_review"]),
    "rejected_count": len(results["rejected"])
}
```

**After** (full details):
```python
result = {
    "status": "completed",
    "initial_size": initial_size,
    "final_size": final_size,
    "size_reduction": size_reduction,

    # Store full detailed lists
    "auto_executed": [
        {
            "deprecated": merge["deprecated"],
            "target": merge["target"],
            "similarity": merge["similarity"],
            "reasoning": merge["reasoning"],
            "blended_description": merge.get("blended_description"),
            "edges_affected": merge.get("edges_affected"),
            "edges_updated": merge.get("edges_updated")
        }
        for merge in results["auto_executed"]
    ],

    "needs_review": [
        {
            "type1": review["type1"],
            "type2": review["type2"],
            "suggested_term": review.get("suggested_term"),
            "suggested_description": review.get("suggested_description"),
            "similarity": review["similarity"],
            "reasoning": review["reasoning"],
            "edge_count1": review.get("edge_count1"),
            "edge_count2": review.get("edge_count2")
        }
        for review in results["needs_review"]
    ],

    "rejected": [
        {
            "type1": reject["type1"],
            "type2": reject["type2"],
            "reasoning": reject["reasoning"]
        }
        for reject in results["rejected"]
    ],

    "pruned": results.get("pruned", []),
    "pruned_count": len(results.get("pruned", [])),

    # Summary counts (for quick reference)
    "auto_executed_count": len(results["auto_executed"]),
    "needs_review_count": len(results["needs_review"]),
    "rejected_count": len(results["rejected"])
}
```

---

## Benefits

### 1. **Async Retrieval**
Client can retrieve detailed results any time after job completes:
```bash
kg job show abc123 --detailed
# Shows full merge history with reasoning
```

### 2. **Automatic Cleanup**
No separate storage or cleanup logic needed:
```bash
kg job delete abc123
# Deletes job AND all cached results
```

### 3. **No Database Schema Changes**
Result field is already JSONB - can store any structure

### 4. **Consistent Pattern**
Same approach used by ingestion, restore, and other workers

### 5. **Audit Trail**
Full history preserved until explicitly deleted

---

## Data Size Concerns

### Typical Consolidation Results

**Small consolidation** (10 merges):
- ~2-3 KB per merge (type names + reasoning)
- Total: ~30 KB

**Large consolidation** (100 merges):
- Total: ~300 KB

**PostgreSQL JSONB column:**
- Max size: 1 GB (theoretical)
- Practical limit: ~100 MB (before performance concerns)
- Our data: < 1 MB per job

**Conclusion:** JSONB storage is perfectly suitable for consolidation results.

---

## API Response Format

### GET /jobs/{job_id}

```json
{
  "job_id": "abc123",
  "job_type": "vocab_consolidate",
  "status": "completed",
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:35:23Z",

  "result": {
    "status": "completed",
    "initial_size": 120,
    "final_size": 95,
    "size_reduction": 25,

    "auto_executed": [
      {
        "deprecated": "knowledge representation",
        "target": "knowledge modeling",
        "similarity": 0.94,
        "reasoning": "Near-perfect synonyms with identical semantic meaning. The terms are used interchangeably in the corpus with no distinguishing context.",
        "blended_description": "The process of structuring and organizing knowledge...",
        "edges_affected": 15,
        "edges_updated": 15
      },
      // ... more merges
    ],

    "needs_review": [
      {
        "type1": "semantic network",
        "type2": "knowledge graph",
        "similarity": 0.82,
        "reasoning": "Related but distinct concepts. Semantic network is a more general term, while knowledge graph specifically refers to RDF-based representations. Recommend human review.",
        "edge_count1": 12,
        "edge_count2": 34
      },
      // ... more review items
    ],

    "rejected": [
      {
        "type1": "abstract",
        "type2": "concrete",
        "reasoning": "Directional inverse: These are antonyms, not synonyms. Should not be merged."
      }
    ],

    "pruned": ["unused_type_1", "unused_type_2"],
    "pruned_count": 2,

    "auto_executed_count": 23,
    "needs_review_count": 3,
    "rejected_count": 1
  }
}
```

---

## CLI Enhancement

### Current Behavior

```bash
kg vocab consolidate --auto
# Blocks for 2 minutes
# Prints summary
# Details lost
```

### Enhanced Behavior

```bash
kg vocab consolidate --auto
✓ Job abc123 queued
⏳ Processing... [▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░] 45%
✓ Completed in 2m 15s

Summary:
  Reduced: 120 → 95 types (25 reduced)
  Auto-executed: 23 merges
  Needs review: 3 pairs
  Rejected: 1 pair
  Pruned: 2 unused types

# View detailed results
kg job show abc123 --detailed

Auto-Executed Merges:
  1. "knowledge representation" → "knowledge modeling" (94% similar)
     Reasoning: Near-perfect synonyms with identical semantic meaning
     Edges: 15 updated

  2. "information system" → "information systems" (98% similar)
     Reasoning: Singular/plural variant with no semantic difference
     Edges: 8 updated

  ... (23 total)

Needs Review (3 pairs):
  1. "semantic network" vs "knowledge graph" (82% similar)
     Reasoning: Related but distinct concepts...

  ... (3 total)

# Delete job and results when done
kg job delete abc123
✓ Deleted job and cached results
```

---

## Implementation Steps

### 1. Update Worker Result

**File:** `api/api/workers/vocab_consolidate_worker.py:101`

Store full results instead of counts (code shown above).

### 2. Update Response Model (Optional)

**File:** `api/api/models/job.py:40`

Current `JobResult` is ingestion-specific. Options:

**Option A:** Make generic (breaking change)
```python
class JobResult(BaseModel):
    """Job completion result"""
    status: str
    data: Dict[str, Any]  # Generic data field
    message: Optional[str] = None
```

**Option B:** Type-specific results (polymorphic)
```python
class JobResult(BaseModel):
    status: str
    message: Optional[str] = None

class IngestionJobResult(JobResult):
    stats: JobStats
    cost: JobCost
    ...

class ConsolidationJobResult(JobResult):
    initial_size: int
    final_size: int
    auto_executed: List[Dict]
    ...
```

**Option C:** Keep generic, document structure
- Store different structures in `result` JSONB
- Document expected structure per job_type
- Most flexible, least type-safe

**Recommendation:** Option C for now, refactor to Option B if needed.

### 3. CLI Display

Add detailed output formatting to `kg job show {job_id}` command.

---

## Related Work

### Similar Patterns in Other Systems

**Jenkins Jobs:**
- Build logs stored in job artifact directory
- Console output cached on disk
- Deleted when job is deleted

**GitHub Actions:**
- Workflow logs stored with run metadata
- Logs expire after 90 days
- Can be manually deleted

**Our Pattern (Simpler):**
- Results stored in job's JSONB field
- No separate storage or expiration logic
- Deleted atomically with job

---

## Files to Modify

1. **`api/api/workers/vocab_consolidate_worker.py:101`**
   - Store full `auto_executed`, `needs_review`, `rejected` lists

2. **`api/api/models/job.py`** (optional)
   - Document expected result structure per job_type

3. **Client CLI** (`kg job show`)
   - Add `--detailed` flag to display full results
   - Pretty-print merge operations, reasoning, etc.

---

## Testing

```bash
# Run consolidation as background job
kg vocab consolidate --auto
# Job: abc123

# Check progress
kg job status abc123
# Status: processing (45%)

# Get detailed results
kg job show abc123 --detailed
# (Full merge history with reasoning)

# Clean up
kg job delete abc123
# (Job + results deleted)
```

---

## Future Enhancements

### 1. **Result Pagination**

For very large consolidations (>1000 merges), paginate results:
```bash
kg job show abc123 --auto-executed --page 1 --limit 50
```

### 2. **Result Export**

Export to file for offline analysis:
```bash
kg job export abc123 > consolidation_report.json
```

### 3. **Retention Policy**

Auto-delete old completed jobs:
```sql
DELETE FROM kg_api.jobs
WHERE status = 'completed'
  AND completed_at < NOW() - INTERVAL '30 days';
```

---

## Priority

**Medium** - This enhances usability and provides audit trail, but isn't blocking core functionality. Should be implemented alongside the non-blocking consolidation fix for complete async workflow.

---

## Related Issues

- **ISSUE-VOCAB-CONSOLIDATE-BLOCKING:** Main bug this enhances
- **ADR-014:** Job approval workflow (existing pattern)
- **ADR-050:** Vocabulary consolidation (AITL hysteresis)
