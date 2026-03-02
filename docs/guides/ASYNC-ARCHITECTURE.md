# Async Architecture and Worker Lanes

## Overview

The knowledge graph platform processes documents through a multi-stage pipeline: chunking, LLM extraction, concept matching, and graph upsert. Each stage involves CPU-bound or I/O-bound work that must run concurrently without starving the API server or exhausting database connections.

ADR-100 replaced the original in-memory thread dispatch model with **database-driven worker lanes** — typed job queues coordinated entirely through PostgreSQL, with no in-memory dispatch state.

## Process Model

The API runs as a **FastAPI application under Uvicorn with 2 OS-level worker processes** (`--workers 2` in the Dockerfile). Each process is a full Python interpreter with its own event loop and thread pools.

Only one process becomes the **dispatch leader**. On startup, each process attempts a PostgreSQL session-level advisory lock (`pg_try_advisory_lock(100_000_001)` in `api/app/main.py`). The winner starts:

- **LaneManager** — poll loops that claim and execute jobs
- **JobScheduler** — lifecycle cleanup (stale recovery, expired job cancellation)
- **ScheduledJobsManager** — cron-like maintenance job creation

The non-leader process handles HTTP requests only. If the leader process dies, the next restart races for the lock again.

## Worker Lanes

A **lane** is a named polling loop with its own concurrency limit and job type affinity. Lane configuration lives in the `kg_api.worker_lanes` PostgreSQL table and is re-read on every poll cycle — changes take effect without a container restart.

### Default Lane Configuration

| Lane | Job Types | Slots | Poll Interval | Stale Timeout |
|------|-----------|-------|---------------|---------------|
| `interactive` | ingestion, ingest_image, polarity | 2 | 2s | 30m |
| `maintenance` | projection, vocab_refresh, epistemic_remeasurement, ontology_annealing, proposal_execution | 1 | 15s | 60m |
| `system` | restore, vocab_consolidate, artifact_cleanup, source_embedding | 1 | 30s | 120m |

Lane separation guarantees that a long-running t-SNE projection in the maintenance lane cannot prevent an ingestion job from claiming an interactive slot.

### Poll-and-Claim

Each lane runs an async polling loop in `api/app/services/lane_manager.py`. On each cycle:

1. Check if slots are available (`active_jobs < max_slots`)
2. Attempt an atomic claim query against the jobs table
3. If a job is claimed, submit it to the `ThreadPoolExecutor` for execution
4. If no job available, sleep for the lane's `poll_interval_ms`

The claim query uses `FOR UPDATE SKIP LOCKED` so multiple lanes can poll concurrently without blocking:

```sql
UPDATE kg_api.jobs
SET status = 'running', claimed_by = :worker_id, claimed_at = NOW()
WHERE job_id = (
    SELECT job_id FROM kg_api.jobs
    WHERE status = 'approved' AND job_type = ANY(:claimable_types)
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

## Thread Pool Inventory

| Pool | Location | Workers | Purpose |
|------|----------|---------|---------|
| Lane executor | `lane_manager.py` | 4 (`MAX_CONCURRENT_JOBS`) | Runs claimed jobs in threads |
| Legacy job executor | `job_queue.py` | 4 (`MAX_CONCURRENT_JOBS`) | Fallback if lane manager unavailable |
| Local embedding | `embedding_worker.py` | 1 (fixed) | Serializes GPU/CPU model access |
| Graph parallelizer | `graph_parallelizer.py` | 8 (per-request) | Multi-hop Cypher fan-out |

All heavy work (database queries, LLM calls, embeddings) runs in synchronous threads. The async event loop orchestrates via `loop.run_in_executor()`.

## Connection Pools

The platform uses **psycopg2's `ThreadedConnectionPool`** (synchronous). There is no async database driver.

| Pool | Location | Min/Max | Purpose |
|------|----------|---------|---------|
| Job queue | `job_queue.py` | 1/10 | Job lifecycle and claim operations |
| AGEClient | `age_client/base.py` | 1/20 | Cypher graph queries |
| Auth | `dependencies/auth.py` | 1/5 | RBAC permission checks |

Each `AGEClient()` instantiation creates its own pool. With default lane config (4 total slots), worst case is ~80 connections from workers plus the job queue and auth pools. The lane model bounds this indirectly by limiting concurrent workers.

## Concurrency Controls

| Control | Mechanism | Default | Location |
|---------|-----------|---------|----------|
| AI provider rate limiting | `threading.Semaphore` per provider | ollama=1, anthropic=4, openai=8 | `rate_limiter.py` |
| Global graph workers | `threading.Semaphore` singleton | 8 | `graph_parallelizer.py` |
| Lane slot enforcement | In-memory set + `call_soon_threadsafe` | Per lane config | `lane_manager.py` |
| Job claim atomicity | `FOR UPDATE SKIP LOCKED` | — | `lane_manager.py` |
| API backoff | Exponential retry with jitter | 60s cap | `rate_limiter.py` |
| Cancellation | Poll `cancelled` column at chunk boundaries | — | `job_queue.py` |
| Global thread cap | `MAX_CONCURRENT_THREADS` env var | 32 | `rate_limiter.py` |

## Tuning

### When to increase slots

If ingestion jobs are queuing behind each other and the system has CPU/memory headroom, increase the interactive lane's `max_slots`:

```bash
# Via API (takes effect on next poll cycle)
curl -X PATCH http://localhost:8000/admin/workers/lanes/interactive \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"max_slots": 3}'
```

### When to reduce poll interval

If the 2-second interactive poll delay is noticeable for user-triggered ingestion, reduce `poll_interval_ms`. Lower values increase database polling load slightly.

### When to drain a lane

For maintenance operations (database migrations, schema changes), drain a lane to stop claiming new jobs while letting running jobs finish:

```bash
curl -X PATCH http://localhost:8000/admin/workers/lanes/maintenance \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"enabled": false}'
```

Re-enable with `{"enabled": true}` when done.

## Admin Endpoints

All endpoints require authentication and `workers:view` or `workers:manage` RBAC permissions.

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/admin/workers/status` | `workers:view` | Slot utilization, running jobs, queue depth |
| GET | `/admin/workers/lanes` | `workers:view` | Per-lane config with utilization |
| PATCH | `/admin/workers/lanes/{name}` | `workers:manage` | Update lane config at runtime |
| POST | `/admin/workers/jobs/{id}/cancel` | `workers:manage` | Cancel a running job (sets cancelled flag) |
| PATCH | `/admin/workers/jobs/{id}/priority` | `workers:manage` | Reprioritize a queued job |

## CLI Reference

```bash
kg admin workers          # Slot overview, lane summary, active jobs
kg admin workers lanes    # Per-lane config detail with utilization
```

## MCP Resource

The `workers/status` MCP resource combines both status and lane data:

```
Resource URI: workers/status
```

## RBAC

| Permission | Scope | Grants |
|------------|-------|--------|
| `workers:view` | Platform | Read lane config, slot utilization, queue depth |
| `workers:manage` | Platform | Cancel jobs, reprioritize, modify lane config, drain/resume lanes |

Both permissions are granted to the `platform_admin` role by the ADR-100 migration. Custom roles can be granted either permission independently via the RBAC system.
