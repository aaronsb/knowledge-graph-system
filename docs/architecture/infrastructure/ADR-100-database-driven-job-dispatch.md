---
status: Accepted
date: 2026-03-01
deciders:
  - aaronsb
  - claude
related:
  - ADR-014
  - ADR-028
  - ADR-050
---

# ADR-100: Database-Driven Job Dispatch

## Context

The current job system has two dispatch paths that evolved independently:

1. **Serial ingestion** — `queue_serial_job()` spawns raw `threading.Thread` instances outside the pool. A completing job calls `_process_next_serial_job()` to chain the next one from within the thread.

2. **System/parallel jobs** — `execute_job_async()` submits to a shared `ThreadPoolExecutor` with 4 slots. Projection (t-SNE), vocab refresh, annealing, and parallel ingestion all compete for these slots.

This creates three observable problems:

**Thread pool starvation.** A t-SNE projection is CPU-bound for 30-120+ seconds. A vocab refresh makes serialized embedding API calls across 50+ types. When system jobs fill all 4 pool slots, any parallel-mode ingestion job queues behind them with no visibility into why.

**In-memory dispatch state.** The `ThreadPoolExecutor`'s internal queue and the serial chaining logic (`_process_next_serial_job`) are in-process memory. If the API container restarts, queued pool submissions are lost and the serial chain breaks. Jobs left in `running` state require manual intervention.

**Connection pool proliferation.** Each worker instantiates its own `AGEClient` with a `ThreadedConnectionPool(1, 20)`. Under 4 concurrent jobs plus the queue's own pool, PostgreSQL can see 80+ connections competing for shared buffers and row-level locks. Ingestion MERGE operations stall when projection workers hold long-running reads.

Additionally, the two dispatch paths make the system hard to reason about: serial jobs bypass the pool entirely, system jobs go through it, and there's no unified model for backpressure, priority, or observability.

### What works well today

The job *state machine* (pending → approved → running → completed/failed) is already in PostgreSQL. The worker registry, progress tracking via SSE, and checkpoint/resume are solid. ADR-014's approval workflow and ADR-050's scheduling layer both work correctly. The problem is specifically in **how work gets dispatched to threads**, not in the job lifecycle itself.

## Decision

Replace in-memory thread dispatch with a database-driven claim model. Workers poll PostgreSQL for claimable work using atomic `UPDATE ... RETURNING` instead of being handed work by in-memory submission.

### Core change: poll-and-claim replaces push-dispatch

```
Current:  approve → in-memory submit → thread runs job
Proposed: approve → job sits in DB → worker polls → atomic claim → worker runs job
```

The job table becomes the sole coordination point. No in-memory queues, no thread chaining.

### Job claim mechanism

Workers claim jobs atomically:

```sql
UPDATE kg_api.jobs
SET status = 'running',
    claimed_by = :worker_id,
    claimed_at = NOW()
WHERE id = (
    SELECT id FROM kg_api.jobs
    WHERE status = 'approved'
      AND job_type = ANY(:claimable_types)
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

`FOR UPDATE SKIP LOCKED` ensures multiple worker threads can poll concurrently without blocking each other — if one row is being claimed, the next worker skips it and tries the next eligible job.

### Worker lanes (database-configured)

Instead of one shared pool, define typed lanes with independent slot budgets. Lane definitions live in a `kg_api.worker_lanes` table so they can be tuned at runtime without restarting the container:

```sql
CREATE TABLE kg_api.worker_lanes (
    name         TEXT PRIMARY KEY,
    job_types    TEXT[] NOT NULL,          -- job types this lane claims
    max_slots    INTEGER NOT NULL DEFAULT 1,
    poll_interval_ms INTEGER NOT NULL DEFAULT 5000,
    stale_timeout_minutes INTEGER NOT NULL DEFAULT 30,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Default lane configuration (seeded by migration):

| Lane | Types | Slots | Poll Interval | Rationale |
|------|-------|-------|---------------|-----------|
| `interactive` | ingestion, ingest_image, polarity | 2 | 2s | User-initiated, latency-sensitive |
| `maintenance` | projection, vocab_refresh, epistemic_remeasurement, ontology_annealing, proposal_execution | 1 | 15s | Background, can wait |
| `system` | restore, vocab_consolidate, artifact_cleanup, source_embedding | 1 | 30s | Infrastructure housekeeping |

Each lane is a polling loop with its own concurrency limit. A t-SNE job filling the maintenance lane cannot prevent an ingest job from claiming an interactive slot.

Slot counts and poll intervals are read from the table on each poll cycle, so changes take effect within one interval — no restart needed. Environment variables can override as a bootstrap mechanism before the database is available.

### Poll loop

Each lane runs a simple async polling loop:

```python
async def lane_loop(lane_name: str):
    while running:
        config = await load_lane_config(lane_name)
        if not config.enabled:
            await asyncio.sleep(config.poll_interval_ms / 1000)
            continue
        async with asyncio.Semaphore(config.max_slots):
            job = await claim_next_job(config.job_types)
            if job:
                asyncio.get_event_loop().run_in_executor(
                    executor, execute_job, job.id
                )
            else:
                await asyncio.sleep(config.poll_interval_ms / 1000)
```

### Job control operations (worker-level)

The existing `/jobs` routes (list, cancel, approve, delete, SSE) manage the **job lifecycle** — a user's view of their ingestion work. Those routes remain unchanged.

This ADR adds a separate set of **worker-level controls** for platform operators. The distinction: existing job controls answer "what's happening with my ingest?" while these answer "what's consuming worker capacity and how do I intervene?"

The gap today: `DELETE /jobs/{id}` refuses to cancel a job in `processing`/`running` state. A runaway t-SNE or vocab refresh has no kill switch — you wait or restart the container.

| Operation | Analogy | Effect |
|-----------|---------|--------|
| **cancel running job** | `kill` | Set `cancelled` flag. Worker checks the flag at the next checkpoint/chunk boundary and stops gracefully. Unlike the existing cancel (which only works on queued jobs), this targets jobs already executing. |
| **reprioritize** | `nice` | Change the `priority` column on a queued job. Higher priority jobs are claimed first (`ORDER BY priority DESC`). |
| **inspect workers** | `ps` | Return slot utilization per lane, which jobs occupy which slots, queue depth per lane, and claim timestamps. Not a duplicate of `GET /jobs` — this is the worker topology view. |
| **drain lane** | `kill -STOP` (lane) | Set `enabled = FALSE` on a lane. The poll loop stops claiming new jobs; running jobs finish naturally. |
| **resume lane** | `kill -CONT` (lane) | Set `enabled = TRUE`. Polling resumes. |

**Cancel mechanism**: Ingestion jobs already check for cancellation between chunks (the checkpoint/resume system). This ADR extends that pattern to all job types — workers check the `cancelled` flag at natural yield points (between t-SNE iterations, between vocab types, between embedding batches). The cancel sets the flag and the worker exits cleanly, preserving any partial state.

### Priority column

A `priority` column (integer, higher = more urgent, default 0) on the jobs table. User-initiated ingestion defaults to priority 10, scheduled maintenance to 0. The `reprioritize` operation allows an admin to bump or lower a job's priority at runtime.

### Stale job recovery

Jobs stuck in `running` beyond the lane's `stale_timeout_minutes` are reset to `approved` by the existing scheduler loop (ADR-050). The `claimed_by` and `claimed_at` columns make this query straightforward:

```sql
UPDATE kg_api.jobs
SET status = 'approved', claimed_by = NULL, claimed_at = NULL, retries = retries + 1
WHERE status = 'running'
  AND claimed_at < NOW() - INTERVAL '1 minute' * :stale_timeout
  AND retries < max_retries;
```

### Serial ordering preserved

Serial ingestion ordering is maintained by the claim query's `ORDER BY priority DESC, created_at ASC` combined with the interactive lane's slot count. With 2 interactive slots, two ingestion jobs can run concurrently (which is already possible today via raw threads). If strict single-file ordering is needed, the lane's `max_slots` can be set to 1 via the API.

### RBAC integration

Job control operations are gated by RBAC permissions (ADR-028). The migration adds these permissions to the platform admin role:

| Permission | Scope | Operations |
|------------|-------|------------|
| `jobs:manage` | Platform | cancel, reprioritize, drain/resume lanes, modify lane config |
| `jobs:view` | Platform | inspect jobs, view lane status and slot utilization |

Both permissions are added to the `platform_admin` role by the migration. They are also available as resources in the RBAC system, so custom roles can be granted `jobs:view` (for monitoring dashboards) or `jobs:manage` (for operators) independently.

The existing `jobs:read` permission (list/view own jobs) remains unchanged for non-admin users.

### API endpoints

These live under `/admin/workers/` to distinguish them from the existing `/jobs/` lifecycle routes.

```
GET    /admin/workers/lanes              # List lanes, slot utilization    (jobs:view)
PATCH  /admin/workers/lanes/:name        # Update lane config              (jobs:manage)
GET    /admin/workers/status             # Slot utilization, queue depth   (jobs:view)
POST   /admin/workers/jobs/:id/cancel    # Cancel a running job            (jobs:manage)
PATCH  /admin/workers/jobs/:id/priority  # Reprioritize a queued job       (jobs:manage)
```

The existing routes are unchanged:

```
GET    /jobs                    # List jobs (user-scoped)          (jobs:read)
GET    /jobs/:id                # Job status + progress            (jobs:read)
DELETE /jobs/:id                # Cancel queued / delete finished  (jobs:cancel)
POST   /jobs/:id/approve        # Approve for processing           (jobs:cancel)
GET    /jobs/:id/stream         # SSE progress stream              (jobs:read)
```

### Schema migration

A single migration adds:

1. `kg_api.worker_lanes` table with default lane seed data
2. `priority` column on `kg_api.jobs` (default 0)
3. `claimed_by` and `claimed_at` columns on `kg_api.jobs`
4. `cancelled` boolean column on `kg_api.jobs` (default FALSE)
5. `jobs:manage` and `jobs:view` permissions registered as RBAC resources
6. Both permissions granted to `platform_admin` role

### Connection pool changes

This ADR does not prescribe connection pool consolidation, but the lane model naturally limits concurrency. With default lane config (2 + 1 + 1 = 4 concurrent workers), each with its own AGEClient, connection behavior is similar to today's `ThreadPoolExecutor(4)` but with predictable distribution. Adjusting lane slots adjusts the connection ceiling proportionally.

A future ADR could address shared connection pooling if connection counts remain a concern.

## Consequences

### Positive

- **No in-memory dispatch state.** All coordination is in PostgreSQL. Container restarts lose nothing — workers resume polling and reclaim stale jobs automatically.
- **Job types can't starve each other.** Lane separation guarantees interactive work gets slots regardless of background load.
- **Observable backpressure.** A query on the jobs table shows exactly how many jobs are queued per type and how long they've been waiting. No hidden ThreadPoolExecutor queue.
- **Crash recovery is automatic.** Stale job reaping replaces the manual "find stuck running jobs" workflow.
- **Runtime tunable.** Lane slot counts, poll intervals, and timeouts can be adjusted via API without container restarts. Performance tuning becomes an operational concern, not a deployment concern.
- **Process control.** Admins can cancel runaway jobs, reprioritize work, and drain lanes for maintenance — capabilities that don't exist today.
- **RBAC from day one.** Job control operations are permissioned resources, available to custom roles and auditable through the existing grant system.
- **Incremental migration.** Can be implemented lane-by-lane — start with interactive, move maintenance, then system.

### Negative

- **Polling latency.** Jobs aren't started instantly on approval — there's up to one poll interval of delay. For interactive work (2s poll), this is acceptable. For truly instant dispatch, a `NOTIFY/LISTEN` optimization can be added later.
- **More SQL.** The claim query, stale recovery, lane config table, and RBAC grants are new SQL that needs testing and maintenance.
- **Configuration surface.** Lane definitions, slot counts, poll intervals, stale timeouts, and priority values are all tunable — more knobs means more things to get wrong. Sensible defaults mitigate this.

### Neutral

- **ADR-050 scheduler unchanged.** The scheduler still creates jobs on schedule. It just stops calling `execute_job_async()` directly — the poll loop picks up approved jobs.
- **ADR-014 approval workflow unchanged.** The approval step still transitions jobs to `approved`. The difference is what happens after: polling replaces push.
- **Worker code unchanged.** The `execute_job()` method and individual worker functions don't change. Only the dispatch layer around them changes.
- **Serial chaining removed.** `_process_next_serial_job()` and `queue_serial_job()` are deleted. The poll loop handles ordering naturally.
- **RBAC scope.** `jobs:manage` and `jobs:view` are new permission resources. Existing user-facing job permissions (`jobs:read`) are unchanged.

## Alternatives Considered

### External message broker (Redis, RabbitMQ, Celery)

Would solve the in-memory state problem and add real job priorities, retries, and dead-letter queues. Rejected because:
- Adds an infrastructure dependency to a system that currently only needs PostgreSQL
- The job volume (tens per hour, not thousands per second) doesn't justify the complexity
- PostgreSQL's `SKIP LOCKED` provides sufficient coordination for our scale

### `asyncio.Queue` replacing `ThreadPoolExecutor`

Would keep dispatch in-memory but make it async-native. Rejected because it doesn't solve the core problem: in-memory state is lost on restart, and there's no natural way to separate job types into lanes.

### `LISTEN/NOTIFY` instead of polling

PostgreSQL can push notifications when jobs are approved, eliminating poll latency. This is a valid optimization but adds complexity (persistent listener connections, reconnection logic). Polling is simpler to implement and debug. `LISTEN/NOTIFY` can be layered on later if the poll interval becomes a UX issue for interactive jobs.

### Keep current model, just increase pool size

More slots would reduce starvation but not eliminate it. Still loses state on restart, still has no type separation, and makes connection pool proliferation worse.
