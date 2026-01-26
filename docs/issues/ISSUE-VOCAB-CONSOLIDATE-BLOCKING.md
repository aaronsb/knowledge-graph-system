# Bug Report: vocab consolidate --auto blocks entire API server

**Issue Type:** Bug
**Severity:** High
**Component:** API Server, Vocabulary Management
**Affects:** `kg vocab consolidate`, `/vocabulary/consolidate` endpoint

---

## Summary

The `kg vocab consolidate --auto` command (and direct `/vocabulary/consolidate` API calls) block the entire FastAPI server during execution, preventing ALL other API requests from being processed until consolidation completes.

---

## Problem

### Current Behavior

The `/vocabulary/consolidate` endpoint **synchronously awaits** the entire consolidation process:

**File:** `api/api/routes/vocabulary.py:447`
```python
# Run consolidation
results = await manager.aitl_consolidate_vocabulary(
    target_size=request.target_size,
    batch_size=request.batch_size,
    auto_execute_threshold=request.auto_execute_threshold,
    dry_run=request.dry_run
)
```

This blocks the FastAPI event loop, freezing the API server.

### Why This Is Bad

1. **Blocks ALL API endpoints** - No other requests can be processed during consolidation
2. **Long-running operation** - Consolidation makes many LLM API calls (can take minutes)
3. **Poor user experience** - Client hangs waiting for single HTTP response
4. **Unnecessary blocking** - Consolidation doesn't require exclusive database locks
5. **Scalability issue** - Server cannot handle concurrent operations

### Impact

- User runs `kg vocab consolidate --auto`
- API server becomes unresponsive for 2-5 minutes
- All other operations fail: `kg search`, `kg ingest`, web UI queries, etc.
- Single-point-of-failure for entire knowledge graph system

---

## Root Cause

The consolidation endpoint directly calls the consolidation logic and waits for completion, rather than enqueuing a background job like ingestion does.

**Blocking pattern (current):**
```python
# api/api/routes/vocabulary.py:447
results = await manager.aitl_consolidate_vocabulary(...)  # BLOCKS HERE
return ConsolidateVocabularyResponse(...)
```

**Non-blocking pattern (ingestion):**
```python
# api/api/routes/ingest.py:269
job_id = queue.enqueue("ingestion", job_data)  # Returns immediately
return JobSubmitResponse(job_id=job_id, ...)
```

---

## Expected Behavior

Consolidation should work like ingestion:

1. Client calls `/vocabulary/consolidate`
2. Endpoint enqueues job and returns **immediately** with `job_id`
3. Worker processes consolidation **in background**
4. Client polls `/jobs/{job_id}` for status and progress
5. API server remains responsive to other requests

---

## Evidence

### Infrastructure Already Exists

All the pieces are already built, just not wired together:

✅ **Worker:** `api/api/workers/vocab_consolidate_worker.py:16`
- `run_vocab_consolidate_worker(job_data, job_id, job_queue)`
- Already handles background consolidation
- Used by scheduled automatic consolidation

✅ **Launcher:** `api/api/launchers/vocab_consolidation.py:16`
- `VocabConsolidationLauncher` (extends `JobLauncher`)
- Prepares job data and enqueues to worker
- Used for hysteresis-based automatic consolidation

✅ **Job Queue:** `api/api/services/job_queue.py`
- PostgreSQL-backed job queue with progress tracking
- Used successfully by ingestion

❌ **Manual endpoint:** `api/api/routes/vocabulary.py:402`
- Does NOT use job queue
- Blocks synchronously

### Comparison: Ingestion vs Consolidation

| Feature | Ingestion | Consolidation |
|---------|-----------|---------------|
| Endpoint | `/ingest` | `/vocabulary/consolidate` |
| Pattern | Enqueues job, returns immediately | Blocks until complete |
| Worker | `ingestion_worker.py` ✅ | `vocab_consolidate_worker.py` ✅ |
| Job queue | Used ✅ | **NOT used** ❌ |
| API blocking | Non-blocking ✅ | **Blocking** ❌ |
| Progress tracking | Via `/jobs/{job_id}` ✅ | None ❌ |
| Can cancel | Yes ✅ | No ❌ |

---

## Solution

### 1. Update Endpoint Signature

**File:** `api/api/routes/vocabulary.py:402`

Add `BackgroundTasks` parameter (like ingestion):

```python
async def consolidate_vocabulary(
    background_tasks: BackgroundTasks,  # ADD THIS
    current_user: CurrentUser,
    _: None = Depends(require_role("admin")),
    request: ConsolidateVocabularyRequest = None
):
```

### 2. Enqueue Job Instead of Blocking

Replace synchronous await with job enqueue:

```python
# REMOVE THIS (blocking)
results = await manager.aitl_consolidate_vocabulary(...)

# ADD THIS (non-blocking)
from api.app.services.job_queue import get_job_queue
queue = get_job_queue()

job_data = {
    "operation": "consolidate",
    "auto_mode": not request.dry_run,
    "target_size": request.target_size,
    "batch_size": request.batch_size,
    "auto_execute_threshold": request.auto_execute_threshold,
    "dry_run": request.dry_run,
    "prune_unused": request.prune_unused,
    "user_id": current_user.id
}

job_id = queue.enqueue("vocab_consolidate", job_data)

return JobSubmitResponse(
    job_id=job_id,
    status="pending",
    message="Vocabulary consolidation job queued. Poll /jobs/{job_id} for progress."
)
```

### 3. Update Worker to Handle Manual Requests

**File:** `api/api/workers/vocab_consolidate_worker.py:60`

Worker already supports the required parameters. Just ensure it reads:
- `target_size`
- `batch_size` (currently hardcoded to 1)
- `auto_execute_threshold`
- `dry_run`
- `prune_unused` (new parameter to add)

### 4. Update CLI to Poll Job

**File:** Client-side (CLI implementation)

Change from:
```bash
kg vocab consolidate --auto
# Waits for HTTP response (blocks for minutes)
```

To:
```bash
kg vocab consolidate --auto
# Returns immediately with job_id
# Polls /jobs/{job_id} for status
# Streams progress updates
```

---

## Files to Modify

1. **`api/api/routes/vocabulary.py:402`** - Change endpoint to enqueue job
2. **`api/api/workers/vocab_consolidate_worker.py:60`** - Add support for manual parameters
3. **Client CLI** - Update to poll job status

---

## Testing

### Before Fix

```bash
# Terminal 1
kg vocab consolidate --auto
# Hangs for 2-5 minutes

# Terminal 2
kg search query "test"
# Times out - API server blocked
```

### After Fix

```bash
# Terminal 1
kg vocab consolidate --auto
# Returns immediately: "Job abc123 queued"
# Shows progress: "Processing... 45%"

# Terminal 2
kg search query "test"
# Works normally - API server responsive
```

---

## Related

- **ADR-014:** Job approval workflow (already used by ingestion)
- **ADR-050:** Vocabulary consolidation (AITL hysteresis)
- **Issue #131:** `kg vocab config` authentication failure
- **Issue #132:** `kg vocab analyze` missing current_user parameter

---

## Priority

**High** - This is a critical operational issue that makes the system unusable during consolidation. The infrastructure to fix it already exists, just needs to be wired together.
