# FUSE Job Visibility Plan

**Branch:** `feature/fuse-job-visibility`
**Date:** 2026-01-28

## Problem Statement

1. **Dolphin doesn't refresh** after file ingestion completes - the kernel isn't notified of directory changes
2. **No visibility into pending jobs** - users can't see ingestion progress in the filesystem

## Proposed Solution

Show pending/processing jobs as virtual files (`~filename.ext.job`) in the ontology's `documents/` directory. Reading the file shows job status.

### Example

```
~/Knowledge/ontology/AI Theory/documents/
├── selection_pressure_synthesis.md          # Completed document
└── ~new_paper.pdf.job                        # Job in progress (virtual file)
```

```bash
$ cat "~/Knowledge/ontology/AI Theory/documents/~new_paper.pdf.job"
# Job: job_abc123
status: processing
progress: 45%
stage: extracting_concepts
created: 2026-01-28T15:30:00Z
```

## Implementation Tasks

### 1. API: Add ontology filter to jobs endpoint

**File:** `api/app/routes/jobs.py` and `api/app/services/job_queue.py`

- Add `ontology` query parameter to `GET /jobs`
- Add `ontology` filter to `list_jobs()` method
- Allows FUSE to query "active jobs for this ontology" efficiently

```python
# In routes/jobs.py list_jobs():
ontology: Optional[str] = Query(None, description="Filter by ontology name")

# In job_queue.py list_jobs():
if ontology:
    conditions.append("j.ontology = %s")
    params.append(ontology)
```

### 2. FUSE: Add job file type and inode handling

**File:** `fuse/kg_fuse/models.py`

- Add `"job_file"` to entry types
- Add `job_id` field to InodeEntry

**File:** `fuse/kg_fuse/filesystem.py`

- Add `_get_or_create_job_inode()` helper
- Track active jobs per ontology

### 3. FUSE: Show job files in documents directory

**File:** `fuse/kg_fuse/filesystem.py` - `_list_documents()`

Current flow:
1. Fetch documents from API
2. Create inodes for each

New flow:
1. Fetch documents from API
2. Fetch active jobs for this ontology (status in pending/processing/awaiting_approval)
3. For each job with a filename, create `~{filename}.job` entry
4. Use shorter cache TTL for documents_dir (5s instead of 30s)

### 4. FUSE: Handle reading job files

**File:** `fuse/kg_fuse/filesystem.py` - `read()`

When reading a job_file:
1. Fetch job status from API
2. Format as TOML/YAML with:
   - job_id
   - status
   - progress (if available)
   - stage
   - created_at
   - error (if failed)

### 5. FUSE: Kernel notification for Dolphin refresh

**File:** `fuse/kg_fuse/filesystem.py`

The issue: Our `_invalidate_cache()` only clears internal Python cache, not the kernel's dentry cache.

Solution: After ingestion completes in `release()`, call `pyfuse3.invalidate_entry()` on the parent directory.

```python
# In release(), after successful ingestion:
import pyfuse3
# Schedule invalidation (can't call during request handling)
asyncio.create_task(self._notify_kernel_invalidation(parent_inode, filename))

async def _notify_kernel_invalidation(self, parent_inode: int, name: str):
    """Notify kernel that directory entry changed."""
    try:
        await pyfuse3.invalidate_entry_async(parent_inode, name.encode('utf-8'))
    except Exception as e:
        log.warning(f"Failed to invalidate entry: {e}")
```

**Note:** `invalidate_entry` cannot be called during request handling (deadlock risk). Must use async version or schedule for later.

### 6. Lazy Polling Approach (implemented)

Instead of background polling, we use demand-driven lazy polling:

1. **On ingestion** (`_ingest_document`): Track job in `_tracked_jobs` dict
2. **On listing** (`_list_documents`): Show `.job` files from local tracking (no API call)
3. **On read** (`_read_job`): Actually poll the API for job status
4. **On completion detected**: Mark job as "seen_complete", next read marks for removal
5. **Next listing**: Remove job from tracking, real document appears

This is more efficient:
- No background threads or polling
- API calls only when user explicitly reads `.job` file
- Natural lifecycle management through user actions

## File Changes Summary

| File | Changes |
|------|---------|
| `api/app/routes/jobs.py` | Add `ontology` query param |
| `api/app/services/job_queue.py` | Add `ontology` filter to `list_jobs()` |
| `fuse/kg_fuse/models.py` | Add `job_file` entry type, `job_id` field |
| `fuse/kg_fuse/filesystem.py` | Job file listing, reading, kernel invalidation |
| `fuse/kg_fuse/formatters.py` | Add `format_job()` for job file content |

## Testing

1. Create ontology via FUSE mkdir
2. Copy file into ontology via Dolphin
3. Verify `~filename.job` appears in `ls`
4. Verify `cat ~filename.job` shows job status
5. Wait for job completion
6. Verify Dolphin refreshes to show completed document
7. Verify job file disappears

## Dependencies

- pyfuse3 invalidation functions (already available)
- Jobs API (exists, needs ontology filter)

## Risks

- `invalidate_entry` timing is tricky - must not be called during request handling
- Job polling adds API load (mitigate with batching/caching)
- Race conditions between job completion and file listing
