---
status: Draft
---

# ADR-014: Job Approval Workflow with Pre-Ingestion Analysis

## Status

**PROPOSED** - Implementation in progress

## Overview

Imagine you're about to process a large document through an AI system. You click submit, and suddenly hundreds of API calls start running—costing you money before you even realize what's happening. There's no way to see the estimated cost beforehand, no chance to review the settings, and no way to cancel once it starts. If you make a typo in the ontology name or select the wrong file, tough luck—you've already spent the money.

This ADR introduces a two-phase job submission workflow that gives you control back. Instead of immediately processing documents, the system first analyzes them quickly (without calling expensive LLMs) to give you estimates: how many chunks will be created, what the token usage will be, and most importantly, what it will cost. Only after you review and approve these estimates does processing begin.

Think of it like online shopping with a cart. You add items, review your cart with the total price, and only then click "purchase." This same pattern now applies to document ingestion—you queue documents, see the costs upfront, and approve when you're ready. Scripts that need automation can use an `--yes` flag to skip approval, while interactive users get transparency and control.

The system also handles interrupted jobs gracefully through database-based checkpointing. If the API crashes mid-processing (deployment, restart, power outage), jobs automatically resume from where they left off instead of starting over or losing progress entirely.

---

## Context

### Current State

The ingestion system currently follows an immediate execution model:

```
Submit → Queue → IMMEDIATELY Process
```

When a document is submitted via API:
1. File is uploaded and enqueued
2. Job starts processing immediately in background
3. User sees "queued" status but processing has already begun
4. No cost transparency before LLM calls are made
5. No ability to review or cancel before expensive operations

The shell script `scripts/ingest.sh` provides valuable pre-analysis:
- File statistics (size, word count)
- Estimated chunk count
- Cost estimates for extraction and embeddings
- Configuration preview
- Warnings (existing checkpoints, large files)

However, this analysis is only available when using the shell script directly, not through the API/CLI workflow.

### Problems

1. **No cost transparency**: Users commit to LLM costs before seeing estimates
2. **No review opportunity**: Can't inspect job details before processing starts
3. **Analysis only in shell script**: API users don't get pre-analysis benefits
4. **Immediate processing**: No pause for verification or approval
5. **Wasted costs on mistakes**: Typos in ontology names, wrong files, etc. still get processed

### Use Cases

- **Review before commit**: User wants to see cost estimate before approving
- **Batch submission**: Queue multiple jobs, review all estimates, approve selectively
- **Auto-approval**: Trusted scripts can auto-approve with `--yes` flag
- **Multi-user approval**: (Phase 2) One user submits, another approves
- **Cost controls**: Reject jobs exceeding budget thresholds

## Decision

### Implement Two-Phase Job Submission

**Phase 1: Queue + Analyze (fast)**
```
Submit → Queue as "pending" → Run analysis → "awaiting_approval"
```

**Phase 2: Approve + Process (slow)**
```
User approves → "approved" → FIFO queue picks up → "processing" → "completed"/"failed"
```

### Enhanced Job State Machine

```
pending            # Just queued, analysis running (auto, fast)
awaiting_approval  # Analysis complete, needs user approval
approved           # User approved, waiting for processor
processing         # Currently being processed
completed          # Successfully finished
failed             # Error during processing
cancelled          # User rejected, timeout, or system cancel
```

State transitions:
- `pending` → `awaiting_approval` (automatic, after analysis)
- `awaiting_approval` → `approved` (user action)
- `awaiting_approval` → `cancelled` (user action or 24h timeout)
- `approved` → `processing` (FIFO queue picks up)
- `processing` → `completed` (success)
- `processing` → `failed` (error)

### Job Model Enhancement

Add `analysis` field to job model:

```python
{
  "job_id": "job_abc123def",
  "status": "awaiting_approval",
  "analysis": {
    "file_stats": {
      "filename": "document.txt",
      "size_bytes": 2415616,
      "size_human": "2.3 MB",
      "word_count": 45000,
      "estimated_chunks": 45
    },
    "cost_estimate": {
      "extraction": {
        "model": "gpt-4o",
        "tokens_low": 22500,
        "tokens_high": 36000,
        "cost_low": 0.28,
        "cost_high": 0.36,
        "currency": "USD"
      },
      "embeddings": {
        "model": "text-embedding-3-small",
        "concepts_low": 225,
        "concepts_high": 360,
        "tokens_low": 18000,
        "tokens_high": 43200,
        "cost_low": 0.01,
        "cost_high": 0.01,
        "currency": "USD"
      },
      "total": {
        "cost_low": 0.29,
        "cost_high": 0.37,
        "currency": "USD"
      }
    },
    "config": {
      "target_words": 1000,
      "min_words": 800,
      "max_words": 1500,
      "overlap_words": 200,
      "checkpoint_interval": 5
    },
    "warnings": [
      "Large file - estimated processing time: 5-10 minutes",
      "No existing checkpoint found"
    ],
    "analyzed_at": "2025-10-08T02:30:00Z"
  },
  "created_at": "2025-10-08T02:30:00Z",
  "approved_at": null,
  "approved_by": null,  # Phase 2: track who approved
  "expires_at": "2025-10-09T02:30:00Z",  # 24h auto-cancel
  ...
}
```

### New API Endpoints

**POST /jobs/{job_id}/approve**
- Requires authentication (placeholder in Phase 1)
- Transitions job from `awaiting_approval` → `approved`
- Returns updated job status

**POST /jobs/{job_id}/cancel**
- Requires authentication (placeholder in Phase 1)
- Transitions job to `cancelled`
- Works for `pending`, `awaiting_approval`, or `approved` states
- Cannot cancel `processing` jobs in Phase 1

**GET /jobs (enhanced)**
- Add `status` filter parameter
- Add `limit` and `offset` for pagination
- Return jobs with analysis included

### Analysis Service

Create `src/api/services/job_analysis.py`:
- Port cost estimation logic from `scripts/ingest.sh`
- Calculate file stats (size, word count)
- Estimate chunk count based on config
- Estimate token usage and costs for extraction and embeddings
- Generate warnings (large files, checkpoints, etc.)
- Read cost configuration from environment/config

```python
class JobAnalyzer:
    def analyze_ingestion_job(self, job_data: Dict) -> Dict:
        """
        Analyze an ingestion job and return cost/stats estimates.

        Returns:
            analysis: Dict with file_stats, cost_estimate, config, warnings
        """
```

### Workflow Changes

#### Submit Ingestion (API)

```python
@router.post("/ingest")
async def ingest_document(...):
    # 1. Enqueue job (status: "pending")
    job_id = queue.enqueue("ingestion", job_data)

    # 2. Trigger analysis in background (fast, non-blocking)
    background_tasks.add_task(run_analysis, job_id)

    # 3. Return job_id immediately
    return {"job_id": job_id, "status": "pending"}


async def run_analysis(job_id: str):
    """Background task to analyze job"""
    job = queue.get_job(job_id)
    analyzer = JobAnalyzer()

    # Run analysis (fast - no LLM calls)
    analysis = analyzer.analyze_ingestion_job(job["job_data"])

    # Update job with analysis
    queue.update_job(job_id, {
        "status": "awaiting_approval",
        "analysis": analysis
    })
```

#### Approve Job (API)

```python
@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str, background_tasks: BackgroundTasks):
    job = queue.get_job(job_id)

    # Validate state
    if job["status"] != "awaiting_approval":
        raise HTTPException(400, "Job not awaiting approval")

    # Mark approved
    queue.update_job(job_id, {"status": "approved"})

    # Add to processing queue
    background_tasks.add_task(queue.execute_job, job_id)

    return {"job_id": job_id, "status": "approved"}
```

#### Job Processor

Approved jobs are picked up FIFO and executed. The existing `execute_job()` method already handles this, we just don't call it until approval.

### CLI Workflow

**Basic flow (manual approval):**
```bash
$ kg ingest document.txt --ontology "My Docs"
✓ Job queued: job_abc123def
  Status: pending (analyzing...)

$ kg jobs status job_abc123def
📊 Job Analysis - Awaiting Approval

  File: document.txt (2.3 MB, 45,000 words)
  Estimated chunks: ~45

  💰 Cost Estimate:
    Extraction (gpt-4o): $0.28 - $0.36
    Embeddings (text-embedding-3-small): $0.01
    Total: $0.29 - $0.37

  ⏱️  Estimated time: 5-10 minutes

  Commands:
    kg jobs approve job_abc123def   # Start processing
    kg jobs cancel job_abc123def    # Cancel job

$ kg jobs approve job_abc123def
✓ Job approved and queued for processing
  Monitor progress: kg jobs status job_abc123def
```

**Auto-approval flow:**
```bash
$ kg ingest document.txt --ontology "My Docs" --yes
✓ Job queued: job_abc123def
  Status: pending (analyzing...)

✓ Analysis complete
  Estimated cost: $0.29 - $0.37

✓ Auto-approved (--yes flag)
  Job processing started
  Monitor: kg jobs status job_abc123def
```

### Job Lifecycle Management (Scheduler)

A background scheduler runs periodically (e.g., hourly) to manage job lifecycle:

**Unapproved job expiration (24 hours):**
- Jobs in `pending` or `awaiting_approval` for >24h → `cancelled`
- Reason logged: "Expired - not approved within 24 hours"
- CLI warning when status checked: "Job will expire in X hours"

**Completed job deletion (48 hours):**
- Jobs in `completed` or `cancelled` for >48h → deleted from database
- Allows users to review recent job history
- Keeps database size manageable

**Failed job deletion (7 days):**
- Jobs in `failed` state for >7 days → deleted from database
- Longer retention for debugging and analysis
- Users can review errors before deletion

**Scheduler Configuration (Environment Variables):**
```bash
# Job lifecycle management
JOB_CLEANUP_INTERVAL=3600        # Run scheduler every hour (seconds)
JOB_APPROVAL_TIMEOUT=24          # Cancel unapproved after 24 hours
JOB_COMPLETED_RETENTION=48       # Delete completed/cancelled after 48 hours
JOB_FAILED_RETENTION=168         # Delete failed after 7 days (168 hours)
```

**Scheduler Implementation:**

Create `src/api/services/job_scheduler.py`:

```python
"""
Job lifecycle scheduler.

Runs periodic maintenance tasks:
- Cancel expired unapproved jobs
- Delete old completed/cancelled jobs
- Delete old failed jobs (longer retention)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import logging
import os

from .job_queue import get_job_queue

logger = logging.getLogger(__name__)


class JobScheduler:
    """Background scheduler for job lifecycle management"""

    def __init__(
        self,
        cleanup_interval: int = 3600,  # 1 hour
        approval_timeout: int = 24,    # 24 hours
        completed_retention: int = 48,  # 48 hours
        failed_retention: int = 168     # 7 days
    ):
        self.cleanup_interval = cleanup_interval
        self.approval_timeout = timedelta(hours=approval_timeout)
        self.completed_retention = timedelta(hours=completed_retention)
        self.failed_retention = timedelta(hours=failed_retention)
        self.running = False
        self.task: Optional[asyncio.Task] = None

    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info(f"Job scheduler started (interval: {self.cleanup_interval}s)")

    async def stop(self):
        """Stop the scheduler gracefully"""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Job scheduler stopped")

    async def _run(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self.cleanup_jobs()
            except Exception as e:
                logger.error(f"Error in job cleanup: {e}", exc_info=True)

            # Sleep until next run
            await asyncio.sleep(self.cleanup_interval)

    async def cleanup_jobs(self):
        """Run all cleanup tasks"""
        queue = get_job_queue()
        now = datetime.now()

        # Cancel unapproved jobs
        expired_count = 0
        for job in queue.list_jobs(status="awaiting_approval", limit=1000):
            created = datetime.fromisoformat(job["created_at"])
            age = now - created

            if age > self.approval_timeout:
                queue.update_job(job["job_id"], {
                    "status": "cancelled",
                    "error": f"Expired - not approved within {self.approval_timeout.total_seconds() / 3600:.0f} hours"
                })
                expired_count += 1

        if expired_count > 0:
            logger.info(f"Cancelled {expired_count} expired unapproved jobs")

        # Delete old completed/cancelled jobs
        deleted_completed = 0
        for job in queue.list_jobs(status="completed", limit=1000):
            if job.get("completed_at"):
                completed = datetime.fromisoformat(job["completed_at"])
                age = now - completed

                if age > self.completed_retention:
                    queue.delete_job(job["job_id"])
                    deleted_completed += 1

        for job in queue.list_jobs(status="cancelled", limit=1000):
            if job.get("completed_at"):
                completed = datetime.fromisoformat(job["completed_at"])
                age = now - completed

                if age > self.completed_retention:
                    queue.delete_job(job["job_id"])
                    deleted_completed += 1

        if deleted_completed > 0:
            logger.info(f"Deleted {deleted_completed} old completed/cancelled jobs")

        # Delete old failed jobs (longer retention)
        deleted_failed = 0
        for job in queue.list_jobs(status="failed", limit=1000):
            if job.get("completed_at"):
                completed = datetime.fromisoformat(job["completed_at"])
                age = now - completed

                if age > self.failed_retention:
                    queue.delete_job(job["job_id"])
                    deleted_failed += 1

        if deleted_failed > 0:
            logger.info(f"Deleted {deleted_failed} old failed jobs")


# Singleton instance
_scheduler_instance: Optional[JobScheduler] = None


def init_job_scheduler(**kwargs) -> JobScheduler:
    """
    Initialize job scheduler with environment config.

    Environment variables:
        JOB_CLEANUP_INTERVAL - Seconds between cleanup runs (default: 3600)
        JOB_APPROVAL_TIMEOUT - Hours before cancelling unapproved (default: 24)
        JOB_COMPLETED_RETENTION - Hours to keep completed/cancelled (default: 48)
        JOB_FAILED_RETENTION - Hours to keep failed jobs (default: 168)
    """
    global _scheduler_instance

    config = {
        "cleanup_interval": int(os.getenv("JOB_CLEANUP_INTERVAL", "3600")),
        "approval_timeout": int(os.getenv("JOB_APPROVAL_TIMEOUT", "24")),
        "completed_retention": int(os.getenv("JOB_COMPLETED_RETENTION", "48")),
        "failed_retention": int(os.getenv("JOB_FAILED_RETENTION", "168")),
    }
    config.update(kwargs)

    _scheduler_instance = JobScheduler(**config)
    return _scheduler_instance


def get_job_scheduler() -> JobScheduler:
    """Get the scheduler instance"""
    if _scheduler_instance is None:
        raise RuntimeError("Scheduler not initialized. Call init_job_scheduler() first.")
    return _scheduler_instance
```

**Integration in main.py:**

```python
from .services.job_scheduler import init_job_scheduler, get_job_scheduler

@app.on_event("startup")
async def startup_event():
    # ... existing queue init ...

    # Initialize and start scheduler
    scheduler = init_job_scheduler()
    scheduler.start()
    logger.info("✓ Job scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    # ... existing cleanup ...

    # Stop scheduler gracefully
    scheduler = get_job_scheduler()
    await scheduler.stop()
    logger.info("✓ Job scheduler stopped")
```

**Database Schema Update:**

Add `delete_job()` method to job queue:

```python
def delete_job(self, job_id: str) -> bool:
    """Permanently delete a job from database"""
    with self.lock:
        # Remove from memory
        if job_id in self.jobs:
            del self.jobs[job_id]

        # Delete from database
        self.db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        self.db.commit()

        return True
```

### Job Resumption After Interruption

**Problem:** API restarts, crashes, or hot reloads can interrupt jobs mid-processing, leaving them orphaned with status `processing` but no active worker.

**Solution:** Database-based checkpointing with automatic resume on startup.

#### Checkpoint Strategy (Database-Based)

After each chunk is processed, save resume state in `job_data`:

```python
# After processing chunk i
job_queue.update_job(job_id, {
    "progress": {
        "resume_from_chunk": i,  # Last completed chunk
        "chunks_processed": i,
        "chunks_total": total,
        ...
    },
    "job_data": {
        **job_data,
        "resume_from_chunk": i,
        "stats": {
            "concepts_created": stats.concepts_created,
            "relationships_created": stats.relationships_created,
            ...
        },
        "recent_concept_ids": recent_ids[-50:]  # Context for next chunk
    }
})
```

**Why database vs filesystem:**
- ✅ All data in one place (no file management)
- ✅ Transactional updates with job status
- ✅ Works with both PostgreSQL and SQLite queues
- ✅ Easy to query and monitor
- ✅ Minimal storage overhead (~2-5KB per job)
- ⚠️ Could migrate to filesystem if job_data becomes too large

#### Resume Flow

**On ingestion worker start:**
```python
# Check if this is a resumed job
resume_from_chunk = job_data.get("resume_from_chunk", 0)
is_resuming = resume_from_chunk > 0

if is_resuming:
    logger.info(f"🔄 Resuming from chunk {resume_from_chunk + 1}/{total}")
    # Load saved stats
    stats.concepts_created = saved_stats["concepts_created"]
    stats.relationships_created = saved_stats["relationships_created"]
    ...
    recent_concept_ids = job_data["recent_concept_ids"]

# Process chunks (skip already-completed)
for i, chunk in enumerate(chunks, 1):
    if i <= resume_from_chunk:
        logger.debug(f"⏭️  Skipping chunk {i} (already processed)")
        continue

    # Process chunk normally...
    process_chunk(...)

    # Save checkpoint
    update_job_with_checkpoint(...)
```

**On API startup (`main.py`):**
```python
# Resume interrupted jobs
processing_jobs = queue.list_jobs(status="processing", limit=500)

for job in processing_jobs:
    chunks_total = job["progress"]["chunks_total"]
    chunks_processed = job["progress"]["resume_from_chunk"]

    if chunks_processed < chunks_total:
        # Interrupted mid-processing - reset to approved
        queue.update_job(job_id, {"status": "approved"})
        logger.info(f"🔄 Queued for resume: {job_id} (chunk {chunks_processed + 1}/{chunks_total})")
    else:
        # Finished all chunks but didn't mark complete
        queue.update_job(job_id, {"status": "completed"})

# Start all approved jobs (includes resumed ones)
approved_jobs = queue.list_jobs(status="approved", limit=500)
for job in approved_jobs:
    queue.execute_job_async(job["job_id"])
```

#### Benefits

1. **Zero data loss**: Chunks already processed aren't re-done
2. **No duplicate concepts**: Stats preserved, relationships maintained
3. **Context preserved**: Recent concept IDs for semantic continuity
4. **Automatic recovery**: No manual intervention needed
5. **Progress visibility**: Resume point shown in job status
6. **Minimal overhead**: ~2-5KB per checkpoint

#### Example Scenario

```
1. User submits large document (125 chunks)
2. Job processes chunks 1-47 successfully
3. API crashes (deployment, restart, crash)
   → Job status: "processing", resume_from_chunk: 47
4. API restarts, detects interrupted job
   → Resets to "approved", triggers execution
5. Worker loads job, finds resume_from_chunk: 47
   → Skips chunks 1-47, resumes from chunk 48
6. Continues with saved stats (1,240 concepts, 3,876 relationships)
7. Completes chunks 48-125 normally
8. Marks job "completed" with final stats
```

#### Alternative Approaches Considered

**Option 1: Filesystem checkpoints**
- Use existing `src/api/lib/checkpoint.py` (already implemented but unused)
- Store chunks + progress in `.checkpoints/` directory
- ❌ File management complexity
- ❌ Orphaned files on incomplete cleanup
- ✅ Could handle very large job_data if needed

**Option 3: Stateless resume**
- Re-chunk document on resume (deterministic)
- Skip chunks by checking if concepts exist
- ❌ Extra LLM calls to check existence
- ❌ Non-deterministic if chunking algorithm changes
- ✅ No storage overhead

**Decision:** Use Option 2 (database) for simplicity. Can migrate to Option 1 if storage becomes an issue.

## Consequences

### Positive

1. **Cost transparency**: Users see estimates before committing
2. **Review opportunity**: Can inspect job details, verify parameters
3. **Mistake prevention**: Catch errors before wasting API costs
4. **Batch management**: Queue multiple, review all, approve selectively
5. **Better UX**: Clear workflow with predictable costs
6. **Audit trail**: Track who approved what (Phase 2)
7. **Consistent analysis**: Same cost logic whether using API or shell script
8. **Flexible approval**: Manual review or auto-approve with flag

### Negative

1. **Extra step**: Requires user action for approval (mitigated by `--yes`)
2. **Complexity**: More states and transitions to manage
3. **Storage**: Analysis data increases job size
4. **Expiration logic**: Need cleanup task for expired jobs
5. **Breaking change**: Existing API clients expect immediate processing

### Mitigation Strategies

- **Default to auto-approve**: Add server config `AUTO_APPROVE_JOBS=true` for backward compatibility
- **Client flag**: `--yes` or `--auto-approve` for scripts
- **Clear messaging**: CLI shows cost before asking for approval
- **Fast analysis**: Analysis is quick (no LLM calls), minimal delay
- **Grace period**: 24h expiration is generous

## Implementation Notes

### Phase 1 (Current)

**ADR and Documentation:**
- [x] ADR-014 documentation
- [ ] Update API documentation with new endpoints

**Backend Services:**
- [ ] Create `JobAnalyzer` service (src/api/services/job_analysis.py)
  - Port cost estimation logic from ingest.sh
  - File stats calculation (size, word count, chunks)
  - Cost estimates (extraction + embeddings)
  - Warning generation
- [ ] Create `JobScheduler` service (src/api/services/job_scheduler.py)
  - Periodic cleanup task (hourly)
  - Cancel unapproved jobs >24h
  - Delete completed/cancelled >48h
  - Delete failed jobs >7 days
  - Graceful start/stop

**Database and Models:**
- [ ] Add `analysis` field to job model (JSON)
- [ ] Add `approved_at`, `approved_by`, `expires_at` fields
- [ ] Add `delete_job()` method to job queue
- [ ] Add job states: `pending`, `awaiting_approval`, `approved`
- [ ] Database migration for new fields

**API Routes:**
- [ ] Add `POST /jobs/{job_id}/approve` endpoint
- [ ] Add `POST /jobs/{job_id}/cancel` endpoint (enhanced)
- [ ] Update `GET /jobs` with status filter
- [ ] Update ingest route to trigger analysis (BackgroundTask)
- [ ] Modify job queue to not auto-execute until approved

**CLI Commands:**
- [ ] Add `kg jobs approve <job_id>` command
- [ ] Add `kg jobs cancel <job_id>` command
- [ ] Update `kg jobs status <job_id>` to show analysis
- [ ] Add `--yes` / `--auto-approve` flag to `kg ingest`
- [ ] Add expiration warnings to job status

**Integration:**
- [ ] Initialize scheduler in main.py startup
- [ ] Stop scheduler gracefully on shutdown
- [ ] Add environment variables for scheduler config
- [ ] Add logging for cleanup operations

### Phase 2 (Future)

- [ ] Multi-user approval (track approved_by user ID)
- [ ] Approval permissions (who can approve what)
- [ ] Budget thresholds (auto-reject above limit)
- [ ] Approval webhooks/notifications
- [ ] Batch approval API endpoint
- [ ] Job priority/scheduling beyond FIFO

### Migration

For backward compatibility during rollout:

1. Add environment variable: `AUTO_APPROVE_JOBS=false` (default)
2. If `AUTO_APPROVE_JOBS=true`, jobs transition directly to `approved`
3. Existing scripts continue working with auto-approval
4. New clients can opt into approval workflow

### Cost Configuration

Cost estimates require pricing configuration in `.env`:

```bash
# Extraction costs (per 1M tokens)
TOKEN_COST_GPT4O=6.25
TOKEN_COST_GPT4O_MINI=0.375
TOKEN_COST_CLAUDE_SONNET_4=9.00

# Embedding costs (per 1M tokens)
TOKEN_COST_EMBEDDING_SMALL=0.02
TOKEN_COST_EMBEDDING_LARGE=0.13
```

Analyzer reads these values to calculate estimates.

## Alternatives Considered

### 1. Synchronous Analysis Before Queue

Return analysis in submit response, require separate approve call:

```
POST /ingest/analyze → Returns analysis (no queue)
POST /ingest/submit → Queue job (with pre-analysis)
```

**Rejected**: Two API calls for single operation, poor UX

### 2. Optional Analysis Flag

Only analyze if `?analyze=true` parameter provided:

```
POST /ingest?analyze=true → Queue with analysis
POST /ingest → Queue and immediately process (current behavior)
```

**Rejected**: Cost transparency should be default, not opt-in

### 3. Cost Threshold Auto-Approve

Auto-approve jobs below certain cost (e.g., $0.10):

```
if estimated_cost < threshold:
    auto_approve()
```

**Rejected**: Users should see all costs, arbitrary thresholds confusing

## References

- `scripts/ingest.sh` - Current pre-analysis implementation
- `src/api/services/job_queue.py` - Job queue abstraction
- `src/api/workers/ingestion_worker.py` - Ingestion execution
- ADR-012: API Server Architecture
- ADR-013: Unified TypeScript Client

## Decision Date

2025-10-08

## Authors

- aaronsb (user request and requirements)
- @claude (ADR documentation and implementation design)
