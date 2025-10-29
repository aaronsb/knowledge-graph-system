# ADR-050: Scheduled Jobs System

**Status:** Proposed
**Date:** 2025-10-28
**Deciders:** Development Team
**Related:** ADR-012 (API Server Architecture), ADR-014 (Job Approval Workflow), ADR-049 (Rate Limiting)

## Context

The system needs automated maintenance tasks that run on schedules:

**Immediate Needs:**
1. **Category Refresh**: Automatically re-integrate LLM-generated vocabulary categories that haven't been merged
2. **Vocabulary Consolidation**: Auto-consolidate vocabulary based on hysteresis curves to maintain optimal spread

**Current System:**

We have a proven, battle-tested job queue system (`job_queue.py`) that handles:
- ✅ Job submission via `enqueue(job_type, job_data)`
- ✅ Worker registry and execution
- ✅ Progress tracking for SSE streaming
- ✅ Checkpoint/resume from failure
- ✅ Serial/parallel execution modes
- ✅ Approval workflow (ADR-014)
- ✅ Content deduplication
- ✅ Works reliably in production

**What's Missing:**

Just one thing: **timing** (when to trigger jobs automatically).

Currently, all jobs are triggered manually via:
- CLI: `kg ingest file ...`, `kg vocab consolidate ...`
- API: `POST /ingest`, `POST /admin/...`

**Problem Statement:**

We need scheduled execution of jobs, but:
- ❌ Don't want external dependencies (APScheduler, Celery, Redis)
- ❌ Don't want to replace working infrastructure
- ❌ Don't want complex migration paths
- ✅ Want to extend what we have consistently

## Decision

**Add a simple scheduling layer on top of the existing job queue.**

No external dependencies. No major refactoring. Just extend our system.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │          Scheduler (NEW - Simple Background Task)       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  Config: kg_api.scheduled_jobs (cron schedules)        │ │
│  │  Loop: asyncio.create_task() checks every 60s          │ │
│  │  Logic: If schedule fires → call launcher              │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ↓ (schedule fires)                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Job Launchers (NEW)                        │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  • CategoryRefreshLauncher                             │ │
│  │  • VocabConsolidationLauncher                          │ │
│  │                                                          │ │
│  │  Each launcher:                                         │ │
│  │    1. check_conditions() → bool                        │ │
│  │    2. prepare_job_data() → dict                        │ │
│  │    3. queue.enqueue(job_type, job_data) → job_id       │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ↓ (enqueues)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Existing Job Queue (UNCHANGED)                  │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  • PostgreSQLJobQueue (proven, works)                  │ │
│  │  • Worker registry                                      │ │
│  │  • Progress tracking (SSE)                             │ │
│  │  • Approval workflow (ADR-014)                         │ │
│  │  • Checkpoint/resume                                    │ │
│  │  • Serial/parallel execution                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Worker Functions (UNCHANGED)                    │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  • run_ingestion_worker(job_data, job_id, queue)       │ │
│  │  • run_restore_worker(job_data, job_id, queue)         │ │
│  │  • run_vocab_refresh_worker(job_data, job_id, queue)   │ │
│  │  • run_vocab_consolidate_worker(job_data, job_id, ...)│ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- ✅ **Minimal additions**: Scheduler loop + launchers
- ✅ **Zero changes**: Existing job queue, workers, approval workflow
- ✅ **No dependencies**: Pure Python, asyncio background task
- ✅ **Consistent**: Scheduled jobs use same queue as manual jobs

### Taxonomy: Tasks, Jobs, and Workers

**Clear separation of concerns with consistent interfaces:**

```
Trigger Type          → Launcher/Caller       → Job Queue        → Worker Function
─────────────────────────────────────────────────────────────────────────────────
SCHEDULED TASK        → Launcher checks       → enqueue()        → run_worker()
(time-based)            conditions, prepares     manages           does actual
                        job_data                 execution         work

ON-DEMAND JOB         → API endpoint          → enqueue()        → run_worker()
(user-triggered)        prepares job_data       manages           (same worker!)
                                                execution
```

#### Task Types (Scheduled)

| Task Name | Schedule | Launcher | Worker | Purpose |
|-----------|----------|----------|--------|---------|
| `category_refresh` | Every 6 hours | `CategoryRefreshLauncher` | `vocab_refresh_worker` | Re-integrate llm_generated vocabulary categories |
| `vocab_consolidation` | Every 12 hours | `VocabConsolidationLauncher` | `vocab_consolidate_worker` | Auto-consolidate vocabulary based on hysteresis |

**Key Point:** Scheduled tasks = timing + condition check → enqueue job

#### Job Types (Workers)

| Job Type | Worker Function | Trigger Sources | Purpose |
|----------|----------------|-----------------|---------|
| `ingestion` | `run_ingestion_worker` | CLI (`kg ingest`), API (`POST /ingest`) | Extract concepts from documents |
| `restore` | `run_restore_worker` | CLI, API | Restore ontology from backup |
| `backup` | `run_backup_worker` | CLI, API | Backup ontology to file |
| `vocab_refresh` | `run_vocab_refresh_worker` | Scheduled (`category_refresh`), Manual | Refresh vocabulary categories |
| `vocab_consolidate` | `run_vocab_consolidate_worker` | Scheduled (`vocab_consolidation`), Manual (`kg vocab consolidate --auto`) | Consolidate vocabulary types |

**Key Point:** Workers don't care how they were triggered. They just receive `job_data` and do work.

#### Interface Contract

**All workers follow the same signature:**
```python
def run_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Worker function signature (consistent for all job types).

    Args:
        job_data: Job-specific parameters
            - Prepared by launcher (scheduled)
            - Or by API endpoint (on-demand)
        job_id: Unique job identifier
            - For progress tracking via job_queue.update_job()
        job_queue: Queue reference
            - For progress updates during execution

    Returns:
        Result dict (success) or raises exception (failure)
    """
```

**Example Flow (Scheduled Task):**
```
1. Scheduler: "category_refresh schedule is due"
2. Scheduler: Creates CategoryRefreshLauncher(queue)
3. Launcher: check_conditions() → True (found llm_generated categories)
4. Launcher: prepare_job_data() → {"operation": "refresh_categories", ...}
5. Launcher: queue.enqueue("vocab_refresh", job_data) → job_id
6. Queue: Finds run_vocab_refresh_worker in worker_registry
7. Queue: Executes worker(job_data, job_id, queue)
8. Worker: Does actual refresh work, updates progress via queue
9. Worker: Returns result dict or raises exception
10. Queue: Updates job status to "completed" or "failed"
```

**Example Flow (On-Demand Job):**
```
1. User: kg ingest file doc.txt
2. CLI: Calls POST /ingest with file data
3. API: Prepares job_data = {"content": ..., "ontology": ...}
4. API: queue.enqueue("ingestion", job_data) → job_id
5. Queue: Finds run_ingestion_worker in worker_registry
6. Queue: Executes worker(job_data, job_id, queue)
7. Worker: Does actual ingestion, updates progress via queue
8. Worker: Returns result dict or raises exception
9. Queue: Updates job status to "completed" or "failed"
```

**Key Insight:** Same queue, same workers, different trigger source. Workers are blissfully unaware.

#### Generic Launcher Pattern

**You can schedule ANY worker with a launcher:**

```python
class GenericJobLauncher(JobLauncher):
    """
    Generic launcher that can invoke any worker in the system.

    Configure via database:
    - job_type: Which worker to call
    - job_data_template: What parameters to pass
    - condition_check: Optional SQL query or Python callable
    """

    def __init__(self, job_queue, config: Dict):
        super().__init__(job_queue)
        self.job_type = config['job_type']
        self.job_data_template = config['job_data_template']
        self.condition_sql = config.get('condition_sql')

    def check_conditions(self) -> bool:
        if not self.condition_sql:
            return True  # Always run if no condition

        # Execute condition SQL
        result = execute_sql(self.condition_sql)
        return bool(result)

    def prepare_job_data(self) -> Dict:
        return self.job_data_template

    def get_job_type(self) -> str:
        return self.job_type
```

**Example: Schedule ANY job without writing custom launcher code:**

```sql
-- Schedule a backup every day at 2am
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES (
    'daily_backup',
    'GenericJobLauncher',
    '0 2 * * *',  -- 2am daily
    TRUE
);

-- Store launcher config separately
INSERT INTO kg_api.launcher_config (schedule_name, job_type, job_data_template)
VALUES (
    'daily_backup',
    'backup',  -- calls run_backup_worker
    '{"ontology": "Production", "backup_type": "full"}'::jsonb
);
```

**This means:**
- ✅ New scheduled tasks don't require new launcher classes
- ✅ Can schedule any worker (ingestion, restore, backup, vocab, etc.)
- ✅ Configuration-driven (database), not code-driven
- ✅ Custom launchers only needed for complex condition logic

#### Schedule Types: Polling vs Direct Execution

**Two distinct patterns:**

**Pattern A: Direct Execution (Simple)**
```
Schedule: "Run backup at 2am daily"
Condition: None (always run)
Behavior: Every trigger → enqueue job

Example:
  trigger (2am) → launcher.check_conditions() → True → enqueue job
  trigger (2am) → launcher.check_conditions() → True → enqueue job
  trigger (2am) → launcher.check_conditions() → True → enqueue job
```

**Pattern B: Polling with Rare Condition (Smart)**
```
Schedule: "Check every 30 minutes"
Condition: "Are there llm_generated categories?"
Behavior: Trigger often, job rarely

Example:
  trigger (00:00) → check_conditions() → False → skip (no job)
  trigger (00:30) → check_conditions() → False → skip (no job)
  trigger (01:00) → check_conditions() → False → skip (no job)
  ... 100 more times ...
  trigger (50:30) → check_conditions() → True → enqueue job! ✅
  trigger (51:00) → check_conditions() → False → skip (job completed, nothing to do)
```

**Real-World Example: Category Refresh**
```python
# Schedule: Every 6 hours (4 times per day)
# Reality: Might only find work once every 2-3 days

class CategoryRefreshLauncher(JobLauncher):
    def check_conditions(self) -> bool:
        # This might return False 20+ times before finding work
        categories = client.get_vocabulary_categories()
        return any('llm_generated' in cat.get('relationship_types', [])
                   for cat in categories)
```

**Logs show the pattern:**
```
2025-10-28 00:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-28 06:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-28 12:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-28 18:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-29 00:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-29 06:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping
2025-10-29 12:00 ✓   CategoryRefreshLauncher: Found category 'Temporal' with llm_generated
2025-10-29 12:00 ✅  CategoryRefreshLauncher: Enqueued job job_abc123
2025-10-29 18:00 ⏭️  CategoryRefreshLauncher: Conditions not met, skipping (job handled it)
```

**Configuration Examples:**

```sql
-- Pattern A: Always run (backup every night)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron)
VALUES (
    'nightly_backup',
    'GenericJobLauncher',
    '0 2 * * *'  -- 2am daily, no condition, always runs
);

-- Pattern B: Poll frequently, run rarely (vocab maintenance)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron)
VALUES (
    'vocab_cleanup',
    'VocabCleanupLauncher',
    '*/30 * * * *'  -- Every 30 minutes, but only runs if cleanup needed
);
```

**Why This Pattern?**

**Benefits:**
- ✅ Responsive: Don't wait 6 hours when condition becomes true
- ✅ Self-healing: If job fails, next check might succeed
- ✅ Adaptive: Condition logic can be complex (hysteresis, thresholds)
- ✅ Efficient: Condition check is cheap (SQL query), job is expensive (LLM calls)

**Cost:**
- ❌ Frequent condition checks (but cheap: ~1ms SQL query)
- ❌ Many "skip" log entries (but informative for monitoring)

**Design Principle:**
> "Check often (cheap), work rarely (expensive)"

**Schedule as Rate Limit, Not Exact Timing:**

The schedule interval is really a **minimum spacing** / **cooldown period**, not a precise execution time:

```
Schedule: "*/30 * * * *" (every 30 minutes)

Translation: "This worker is resource-intensive. Don't run it more often than
             every 30 minutes. When it does run, it probably won't need to
             run again for a long time."

Reality:
  - Launcher fires every 30 minutes (cheap condition check)
  - Worker runs once every few days (expensive work, when needed)
  - Schedule prevents over-execution, condition prevents under-utilization
```

**We don't have to guess WHEN to run it:**
- ❌ Bad: "Should we run vocab consolidation at 2am? 3am? Tuesday?"
- ✅ Good: "Check every 30 minutes if consolidation is needed, but never run more often than that"

**The job regulates itself:**
- Launcher checks: "Is there work?" (1ms SQL query)
- If yes: Enqueue expensive job
- If no: Skip, check again in 30 minutes
- Once job completes: Condition likely False for hours/days
- Self-regulating: No need to predict or tune exact timing

**Example: Vocabulary Consolidation**
```
Schedule: Every 30 minutes
Condition: inactive_types > 20% of active_types
Behavior:
  - Checks 48 times per day (cheap)
  - Runs ~once per week when threshold exceeded (expensive)
  - After running, threshold not exceeded for days
  - Perfect: Protected from over-execution, responsive to actual need
```

This is why launchers exist - they're the intelligent filter between schedule timing and actual job execution.

### Architecture Clarification: Code vs Configuration

**What's in PostgreSQL (Configuration):**
```
kg_api.scheduled_jobs:
  - Schedule definitions (cron, enabled, retries)
  - Execution history (last_run, last_success, last_failure)
  - Status tracking (retry_count, next_run)

kg_api.jobs:
  - Job execution results (existing table, unchanged)
  - Progress tracking for SSE streaming
  - Deduplication via content_hash
```

**What's in Python Code (Logic):**
```
Launchers (src/api/launchers/):
  - Condition checking logic
  - Job data preparation
  - NOT API endpoints (internal only)
  - Called by scheduler loop

Example:
  category_refresh.py         ← Custom condition logic (code)
  vocab_consolidation.py      ← Hysteresis logic (code)
  generic_launcher.py         ← Simple pass-through (code)
```

**Key Point:**
- ✅ **Configuration lives in PostgreSQL** (schedules, timing, history)
- ✅ **Launchers are Python classes** (condition logic requires code)
- ❌ **NOT a universal job authoring system** (too complex, not needed)

**Adding a New Scheduled Task:**
```python
# 1. Write launcher class (if custom logic needed)
# src/api/launchers/my_task.py
class MyTaskLauncher(JobLauncher):
    def check_conditions(self) -> bool:
        # Your condition logic here
        return some_check()

    def prepare_job_data(self) -> Dict:
        return {"operation": "my_task"}

    def get_job_type(self) -> str:
        return "my_worker"

# 2. Register launcher in main.py
launcher_registry = {
    'MyTaskLauncher': MyTaskLauncher,  # Add this line
    ...
}

# 3. Configure schedule in PostgreSQL (via API or SQL)
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron)
VALUES ('my_task', 'MyTaskLauncher', '0 */2 * * *');
```

**For simple tasks (no condition logic), use GenericJobLauncher:**
```sql
-- No code required! Just configure in database
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron)
VALUES ('nightly_backup', 'GenericJobLauncher', '0 2 * * *');

INSERT INTO kg_api.launcher_config (schedule_name, job_type, job_data_template)
VALUES ('nightly_backup', 'backup', '{"ontology": "Production"}'::jsonb);
```

### Management APIs

**Endpoint Separation: Jobs vs Schedules**

The system has two distinct endpoint namespaces:

| Namespace | Purpose | Examples |
|-----------|---------|----------|
| `/jobs` | **Job execution instances** | List running jobs, get job status, delete job records |
| `/admin/scheduled-jobs` | **Schedule configuration** | List schedules, enable/disable, update cron expressions |

**Why separate?**
- A **job** is an execution instance (specific ingestion run with progress, results)
- A **scheduled job** is a configuration (the schedule definition that creates jobs)
- One schedule creates many job instances over time
- Example: `category_refresh` schedule (1 config) → 100+ job executions over weeks

**Concrete Example:**
```
Schedule: "category_refresh" (cron: "0 */6 * * *")
  ├─ Job execution 1: job_abc123 (2025-10-28 06:00, completed)
  ├─ Job execution 2: job_abc456 (2025-10-28 12:00, completed)
  ├─ Job execution 3: job_abc789 (2025-10-28 18:00, running)
  └─ Job execution 4: job_abcXYZ (2025-10-29 00:00, pending)

GET /admin/scheduled-jobs/category_refresh  → Schedule config
GET /jobs/job_abc123                        → Specific execution
```

**All scheduled job management via REST API:**

#### GET /admin/scheduled-jobs
List all scheduled jobs with status.

**Response:**
```json
{
  "schedules": [
    {
      "id": 1,
      "name": "category_refresh",
      "launcher_class": "CategoryRefreshLauncher",
      "schedule_cron": "0 */6 * * *",
      "enabled": true,
      "max_retries": 5,
      "retry_count": 0,
      "last_run": "2025-10-28T12:00:00Z",
      "last_success": "2025-10-28T12:00:00Z",
      "last_failure": null,
      "next_run": "2025-10-28T18:00:00Z",
      "created_at": "2025-10-27T00:00:00Z"
    }
  ]
}
```

#### GET /admin/scheduled-jobs/{name}
Get details for a specific scheduled job.

**Response:**
```json
{
  "id": 1,
  "name": "category_refresh",
  "launcher_class": "CategoryRefreshLauncher",
  "schedule_cron": "0 */6 * * *",
  "enabled": true,
  "max_retries": 5,
  "retry_count": 0,
  "last_run": "2025-10-28T12:00:00Z",
  "last_success": "2025-10-28T12:00:00Z",
  "last_failure": null,
  "next_run": "2025-10-28T18:00:00Z",
  "recent_jobs": [
    {
      "job_id": "job_abc123",
      "status": "completed",
      "created_at": "2025-10-28T12:00:00Z",
      "completed_at": "2025-10-28T12:05:23Z"
    }
  ]
}
```

#### POST /admin/scheduled-jobs/{name}/enable
Enable a disabled schedule.

**Response:**
```json
{
  "success": true,
  "message": "Schedule 'category_refresh' enabled",
  "next_run": "2025-10-28T18:00:00Z"
}
```

#### POST /admin/scheduled-jobs/{name}/disable
Disable a schedule.

**Response:**
```json
{
  "success": true,
  "message": "Schedule 'category_refresh' disabled"
}
```

#### POST /admin/scheduled-jobs/{name}/trigger
Manually trigger a schedule now (bypasses timing, still checks conditions).

**Response:**
```json
{
  "success": true,
  "job_id": "job_xyz789",
  "message": "Schedule 'category_refresh' triggered manually"
}
```

#### PATCH /admin/scheduled-jobs/{name}
Update schedule configuration.

**Request:**
```json
{
  "schedule_cron": "0 */2 * * *",  // Optional: Update cron expression
  "max_retries": 10,                // Optional: Update retry limit
  "enabled": true                   // Optional: Enable/disable
}
```

**Response:**
```json
{
  "success": true,
  "message": "Schedule 'category_refresh' updated",
  "next_run": "2025-10-28T14:00:00Z"
}
```

#### GET /admin/scheduled-jobs/{name}/history
Get execution history for a schedule.

**Response:**
```json
{
  "schedule_name": "category_refresh",
  "history": [
    {
      "run_time": "2025-10-28T12:00:00Z",
      "outcome": "success",
      "job_id": "job_abc123",
      "conditions_met": true
    },
    {
      "run_time": "2025-10-28T06:00:00Z",
      "outcome": "skipped",
      "job_id": null,
      "conditions_met": false
    }
  ],
  "stats": {
    "total_runs": 48,
    "successful_runs": 3,
    "skipped_runs": 44,
    "failed_runs": 1,
    "success_rate": "75%"
  }
}
```

### CLI Commands

**Corresponding CLI commands for user-friendly management:**

```bash
# List all schedules
kg admin scheduled list

# Show schedule details
kg admin scheduled status category_refresh

# Enable/disable
kg admin scheduled enable category_refresh
kg admin scheduled disable category_refresh

# Manually trigger
kg admin scheduled trigger category_refresh

# Update schedule
kg admin scheduled update category_refresh --cron "0 */2 * * *"

# View history
kg admin scheduled history category_refresh --limit 20
```

## Job Ownership and Permissions

**Problem:** Users shouldn't be able to delete system-scheduled jobs, but we need convenient access to manage their own jobs.

### Schema Enhancement

**Add ownership tracking to `kg_api.jobs`:**

```sql
-- Migration 019: Add job ownership and source tracking
ALTER TABLE kg_api.jobs
ADD COLUMN IF NOT EXISTS job_source VARCHAR(50) DEFAULT 'user_cli',
ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS is_system_job BOOLEAN DEFAULT FALSE;

-- Create index for permission checks
CREATE INDEX IF NOT EXISTS idx_jobs_ownership
ON kg_api.jobs(created_by, is_system_job);
```

**Job Source Types:**
- `user_cli` - User invoked via CLI (`kg ingest file ...`)
- `user_api` - User invoked via API (`POST /ingest`)
- `scheduled_task` - System-scheduled task (category_refresh, vocab_consolidation)
- `system` - System internal job (backup, restore, maintenance)

### Permission Rules

**User Permissions:**
```
✅ CAN:
  - List their own jobs (WHERE created_by = user)
  - Delete their own jobs (WHERE created_by = user AND is_system_job = FALSE)
  - Cancel their own running jobs
  - View status of their own jobs

❌ CANNOT:
  - Delete system jobs (WHERE is_system_job = TRUE)
  - Delete other users' jobs
  - Modify scheduled tasks
```

**Admin Permissions:**
```
✅ CAN:
  - List ALL jobs (no filter)
  - Delete ANY job (including system jobs)
  - Cancel ANY running job
  - Modify scheduled tasks
```

### CLI Taxonomy Restructure

**Current (Flat - No Permissions):**
```bash
kg jobs list             # Lists ALL jobs (unsafe)
kg jobs delete ID        # Deletes ANY job (unsafe!)
```

**Proposed (Hierarchical - Permission-Aware):**

```bash
# User commands (scoped to user's jobs)
kg ingest jobs list                    # List MY ingestion jobs
kg ingest jobs delete JOB_ID           # Delete MY ingestion job
kg ingest jobs cancel JOB_ID           # Cancel MY running job

kg vocab jobs list                     # List MY vocab jobs
kg vocab jobs delete JOB_ID            # Delete MY vocab job

kg jobs list                           # List ALL my jobs (all types)
kg jobs delete JOB_ID                  # Delete my job (permission check)

# Admin commands (global scope)
kg admin jobs list                     # List ALL jobs (all users)
kg admin jobs list --system            # List system/scheduled jobs only
kg admin jobs delete JOB_ID            # Delete ANY job (with confirmation)
kg admin jobs stats                    # Job statistics
```

**Example: User tries to delete system job (blocked):**
```bash
$ kg jobs delete job_sys456
❌ Error: Cannot delete system job job_sys456 (scheduled task)
   Use 'kg admin jobs delete' if you have admin privileges
```

### API Permission Enforcement

```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, current_user: str = "cli_user"):
    """Delete a job (user can only delete their own non-system jobs)."""
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Permission check: System jobs protected
    if job.get("is_system_job", False):
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete system job. Use admin API if authorized."
        )

    # Permission check: Own jobs only
    if job.get("created_by") != current_user:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete job created by another user"
        )

    success = queue.delete_job(job_id)
    return {"success": True, "message": f"Job {job_id} deleted"}
```

### Scheduled Job Creation (System Ownership)

**Mark scheduler-created jobs as system:**

```python
class JobLauncher(ABC):
    def launch(self) -> Optional[str]:
        # Enqueue job
        job_id = self.job_queue.enqueue(
            job_type=self.get_job_type(),
            job_data=job_data
        )

        # Mark as system job
        if job_id:
            self.job_queue.update_job(job_id, {
                "is_system_job": True,
                "job_source": "scheduled_task",
                "created_by": f"system:scheduler:{self.__class__.__name__}"
            })

        return job_id
```

### Components

#### 1. Schedule Configuration Table

```sql
-- Migration 019: Add scheduled jobs configuration
CREATE TABLE IF NOT EXISTS kg_api.scheduled_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    launcher_class VARCHAR(255) NOT NULL,
    schedule_cron VARCHAR(100) NOT NULL,  -- Cron expression: "0 */6 * * *"
    enabled BOOLEAN DEFAULT TRUE,
    max_retries INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    last_run TIMESTAMP,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    next_run TIMESTAMP,  -- Calculated from cron
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default scheduled jobs
INSERT INTO kg_api.scheduled_jobs (name, launcher_class, schedule_cron, enabled)
VALUES
    ('category_refresh', 'CategoryRefreshLauncher', '0 */6 * * *', TRUE),
    ('vocab_consolidation', 'VocabConsolidationLauncher', '0 */12 * * *', TRUE)
ON CONFLICT (name) DO NOTHING;
```

#### 2. Simple Scheduler Loop

```python
# src/api/services/scheduler.py

import asyncio
import logging
from datetime import datetime, timedelta
from croniter import croniter  # Simple cron parser library
from typing import Dict, Type

logger = logging.getLogger(__name__)

class JobScheduler:
    """
    Simple scheduler that triggers launchers based on cron schedules.

    No fancy features. Just checks schedules every 60 seconds and
    fires launchers when schedules match.
    """

    def __init__(self, job_queue, launcher_registry: Dict[str, Type]):
        self.job_queue = job_queue
        self.launcher_registry = launcher_registry
        self.running = False
        self.task = None

    async def start(self):
        """Start the scheduler loop"""
        self.running = True
        self.task = asyncio.create_task(self._schedule_loop())
        logger.info("✅ Job scheduler started")

    async def stop(self):
        """Stop the scheduler loop"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Job scheduler stopped")

    async def _schedule_loop(self):
        """
        Main scheduler loop.

        Checks schedules every 60 seconds, triggers launchers when due.
        """
        while self.running:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}", exc_info=True)

            # Sleep 60 seconds before next check
            await asyncio.sleep(60)

    async def _check_schedules(self):
        """
        Check all enabled schedules and trigger if due.

        Uses PostgreSQL advisory lock to ensure only one worker checks
        schedules in multi-worker deployments (e.g., Gunicorn -w 4).
        """
        from src.api.lib.age_client import AGEClient

        client = AGEClient()
        conn = client.pool.getconn()

        try:
            with conn.cursor() as cur:
                # --- MULTI-WORKER SAFETY ---
                # Try to acquire a unique, non-blocking advisory lock.
                # Only one worker across all processes can hold this lock.
                # Key: 1050 (arbitrary unique integer for this system)
                cur.execute("SELECT pg_try_advisory_lock(1050)")
                got_lock = cur.fetchone()[0]

                if not got_lock:
                    # Another worker has the lock and is checking schedules.
                    # This worker should do nothing to avoid duplicate job creation.
                    logger.debug(
                        "Scheduler lock held by another worker, skipping check cycle"
                    )
                    return

                # If we're here, we are the ONLY worker running schedule checks
                logger.debug("Acquired scheduler lock, proceeding with schedule check")
                # --- END MULTI-WORKER SAFETY ---
                cur.execute("""
                    SELECT id, name, launcher_class, schedule_cron,
                           retry_count, max_retries, last_run, next_run
                    FROM kg_api.scheduled_jobs
                    WHERE enabled = TRUE
                    ORDER BY next_run ASC NULLS FIRST
                """)

                schedules = cur.fetchall()
                now = datetime.now()

                for schedule in schedules:
                    schedule_id, name, launcher_class, cron_expr, \
                    retry_count, max_retries, last_run, next_run = schedule

                    # Calculate next run if not set
                    if not next_run:
                        cron = croniter(cron_expr, now)
                        next_run = cron.get_next(datetime)

                        cur.execute("""
                            UPDATE kg_api.scheduled_jobs
                            SET next_run = %s
                            WHERE id = %s
                        """, (next_run, schedule_id))
                        conn.commit()
                        continue

                    # Check if due
                    if next_run <= now:
                        logger.info(f"⏰ Schedule '{name}' is due, triggering launcher")

                        # Get launcher class
                        launcher_cls = self.launcher_registry.get(launcher_class)
                        if not launcher_cls:
                            logger.error(f"❌ Unknown launcher: {launcher_class}")
                            continue

                        # Create launcher instance
                        launcher = launcher_cls(self.job_queue, max_retries)

                        # Trigger launcher (three possible outcomes)
                        job_id = None
                        launch_failed = False

                        try:
                            # launch() returns job_id, None (for skip),
                            # or raises Exception (for failure)
                            job_id = launcher.launch()
                        except Exception as e:
                            logger.error(
                                f"❌ Schedule '{name}' launcher failed: {e}",
                                exc_info=True
                            )
                            launch_failed = True

                        # Calculate next run time for schedule advancement
                        cron = croniter(cron_expr, now)
                        next_next_run = cron.get_next(datetime)

                        if job_id:
                            # Outcome 1: Success - Job enqueued
                            # Reset retry_count, update last_success
                            cur.execute("""
                                UPDATE kg_api.scheduled_jobs
                                SET last_run = %s,
                                    last_success = %s,
                                    next_run = %s,
                                    retry_count = 0
                                WHERE id = %s
                            """, (now, now, next_next_run, schedule_id))
                            logger.info(f"✅ Schedule '{name}' triggered job {job_id}")

                        elif not launch_failed:
                            # Outcome 2: Normal skip - Conditions not met
                            # This is healthy, reset retry_count, advance schedule
                            # Don't update last_success (no job ran)
                            cur.execute("""
                                UPDATE kg_api.scheduled_jobs
                                SET last_run = %s,
                                    next_run = %s,
                                    retry_count = 0
                                WHERE id = %s
                            """, (now, next_next_run, schedule_id))
                            logger.info(f"⏭️  Schedule '{name}' skipped (conditions not met)")

                        else:
                            # Outcome 3: Launcher failure - Exception raised
                            # Increment retry_count, apply exponential backoff
                            new_retry_count = retry_count + 1

                            if new_retry_count >= max_retries:
                                # Max retries exceeded, disable schedule
                                logger.error(
                                    f"❌ Schedule '{name}' max retries exceeded, disabling"
                                )
                                cur.execute("""
                                    UPDATE kg_api.scheduled_jobs
                                    SET last_run = %s,
                                        last_failure = %s,
                                        retry_count = %s,
                                        enabled = FALSE
                                    WHERE id = %s
                                """, (now, now, new_retry_count, schedule_id))
                            else:
                                # Exponential backoff: retry sooner
                                backoff_minutes = min(2 ** new_retry_count, 60)
                                retry_time = now + timedelta(minutes=backoff_minutes)

                                logger.warning(
                                    f"⚠️  Schedule '{name}' failed (retry {new_retry_count}/{max_retries}), "
                                    f"retrying in {backoff_minutes}min"
                                )
                                cur.execute("""
                                    UPDATE kg_api.scheduled_jobs
                                    SET last_run = %s,
                                        last_failure = %s,
                                        next_run = %s,
                                        retry_count = %s
                                    WHERE id = %s
                                """, (now, now, retry_time, new_retry_count, schedule_id))

                        conn.commit()

        finally:
            # --- MULTI-WORKER SAFETY ---
            # Always release the advisory lock, even if we failed.
            # This allows another worker to take over on the next 60s poll.
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(1050)")
            # --- END MULTI-WORKER SAFETY ---
            client.pool.putconn(conn)
```

#### 3. Job Launcher Base Class

```python
# src/api/launchers/base.py

from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class JobLauncher(ABC):
    """
    Base class for scheduled job launchers.

    Launchers are lightweight "sequencers" that:
    1. Check if conditions are met to run a job
    2. Prepare job_data for the worker
    3. Enqueue job to existing job queue

    The existing job queue handles execution, progress, approval, etc.
    """

    def __init__(self, job_queue, max_retries: int = 5):
        self.job_queue = job_queue
        self.max_retries = max_retries

    @abstractmethod
    def check_conditions(self) -> bool:
        """
        Check if conditions are met to run this job.

        Returns:
            True if job should run, False to skip

        Example:
            - Check if there are llm_generated categories
            - Check if vocabulary spread exceeds threshold
        """
        pass

    @abstractmethod
    def prepare_job_data(self) -> Dict:
        """
        Prepare job_data dict for the worker function.

        Returns:
            Dict with parameters for the worker
        """
        pass

    @abstractmethod
    def get_job_type(self) -> str:
        """
        Return the job type for worker registry lookup.

        Returns:
            Job type string (e.g., "vocab_refresh", "vocab_consolidate")
        """
        pass

    def launch(self) -> Optional[str]:
        """
        Execute the launcher: check conditions, prepare data, enqueue job.

        Returns:
            job_id if enqueued, None if conditions not met (normal skip).

        Raises:
            Exception: If condition check, data prep, or enqueueing fails.

        Important: A return value of None means "conditions not met, this is
        normal, don't treat as failure." Any actual failure should raise an
        exception so the scheduler can distinguish:
            - Success (job_id returned) → Reset retry_count
            - Skip (None returned) → Reset retry_count, advance schedule
            - Failure (exception raised) → Increment retry_count, backoff
        """
        # Let exceptions bubble up - scheduler handles them
        if not self.check_conditions():
            logger.info(f"⏭️  {self.__class__.__name__}: Conditions not met, skipping")
            return None  # Normal skip, not a failure

        logger.info(f"✓  {self.__class__.__name__}: Conditions met, preparing job")

        # Let exceptions bubble up
        job_data = self.prepare_job_data()

        # Let exceptions bubble up
        job_id = self.job_queue.enqueue(
            job_type=self.get_job_type(),
            job_data=job_data
        )

        # Mark as system job
        if job_id:
            self.job_queue.update_job(job_id, {
                "is_system_job": True,
                "job_source": "scheduled_task",
                "created_by": f"system:scheduler:{self.__class__.__name__}"
            })

        logger.info(f"✅ {self.__class__.__name__}: Enqueued job {job_id}")
        return job_id
```

#### 4. Example Launchers

**Category Refresh Launcher:**
```python
# src/api/launchers/category_refresh.py

from .base import JobLauncher
from src.api.lib.age_client import AGEClient
from typing import Dict

class CategoryRefreshLauncher(JobLauncher):
    """
    Automatically refresh vocabulary categories with llm_generated entries.

    Checks: Are there categories with "llm_generated" that need re-integration?
    Worker: vocab_refresh_worker
    Schedule: Every 6 hours
    """

    def check_conditions(self) -> bool:
        """Check if any categories have llm_generated entries"""
        client = AGEClient()
        categories = client.get_vocabulary_categories()

        for category in categories:
            if 'llm_generated' in category.get('relationship_types', []):
                return True

        return False

    def prepare_job_data(self) -> Dict:
        """Prepare data for vocab refresh worker"""
        return {
            "operation": "refresh_categories",
            "auto_mode": True,
            "filter": "llm_generated"
        }

    def get_job_type(self) -> str:
        return "vocab_refresh"
```

**Vocabulary Consolidation Launcher:**
```python
# src/api/launchers/vocab_consolidation.py

from .base import JobLauncher
from src.api.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class VocabConsolidationLauncher(JobLauncher):
    """
    Automatically consolidate vocabulary based on hysteresis curve.

    Checks: Does vocab spread exceed consolidation threshold?
    Worker: vocab_consolidate_worker
    Schedule: Every 12 hours
    """

    def check_conditions(self) -> bool:
        """Check if vocabulary spread exceeds consolidation threshold"""
        client = AGEClient()
        stats = client.get_vocabulary_stats()

        total_types = stats['total_types']
        active_types = stats['active_types']
        inactive_types = stats['inactive_types']

        # Hysteresis thresholds:
        # - Consolidate when active > 50 and inactive > 20% of active
        # - Don't consolidate if inactive < 10% of active (avoid thrashing)

        if active_types > 50:
            inactive_ratio = inactive_types / active_types

            # Upper threshold: consolidate
            if inactive_ratio > 0.20:
                logger.info(
                    f"✓ Consolidation threshold exceeded: "
                    f"{inactive_types}/{active_types} = {inactive_ratio:.1%} > 20%"
                )
                return True

            # Lower threshold: prevent thrashing
            if inactive_ratio < 0.10:
                logger.info(
                    f"⏭️  Consolidation threshold not reached: "
                    f"{inactive_types}/{active_types} = {inactive_ratio:.1%} < 10% (hysteresis)"
                )
                return False

        return False

    def prepare_job_data(self) -> Dict:
        """Prepare data for vocab consolidation worker"""
        return {
            "operation": "consolidate",
            "auto_mode": True,
            "strategy": "hysteresis"
        }

    def get_job_type(self) -> str:
        return "vocab_consolidate"
```

#### 5. FastAPI Integration

```python
# In src/api/main.py

from src.api.services.scheduler import JobScheduler
from src.api.launchers.category_refresh import CategoryRefreshLauncher
from src.api.launchers.vocab_consolidation import VocabConsolidationLauncher

# At startup
@app.on_event("startup")
async def startup_event():
    # Initialize existing job queue (unchanged)
    global queue
    queue = init_job_queue()

    # Register existing workers (unchanged)
    queue.register_worker("ingestion", run_ingestion_worker)
    queue.register_worker("restore", run_restore_worker)

    # Register NEW vocab workers
    queue.register_worker("vocab_refresh", run_vocab_refresh_worker)
    queue.register_worker("vocab_consolidate", run_vocab_consolidate_worker)

    # Create launcher registry
    launcher_registry = {
        'CategoryRefreshLauncher': CategoryRefreshLauncher,
        'VocabConsolidationLauncher': VocabConsolidationLauncher
    }

    # Start scheduler
    global scheduler
    scheduler = JobScheduler(queue, launcher_registry)
    await scheduler.start()
    logger.info("✅ Scheduled jobs initialized")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop scheduler
    await scheduler.stop()
```

## Production Deployment Considerations

### Multi-Worker Safety (Critical)

**Problem:** In production, FastAPI runs with multiple Gunicorn workers:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.api.main:app
```

Each worker process runs the `startup_event`, creating **N separate scheduler loops**. Without coordination, all N schedulers will check schedules simultaneously, causing **duplicate job creation**.

**Example (without advisory lock):**
```
2025-10-29 00:00:00 - Worker 1: Schedule 'category_refresh' due → Enqueue job_abc123
2025-10-29 00:00:00 - Worker 2: Schedule 'category_refresh' due → Enqueue job_abc456
2025-10-29 00:00:00 - Worker 3: Schedule 'category_refresh' due → Enqueue job_abc789
2025-10-29 00:00:00 - Worker 4: Schedule 'category_refresh' due → Enqueue job_abcXYZ
Result: 4 identical jobs instead of 1 ❌
```

**Solution: PostgreSQL Advisory Locks**

Advisory locks are lightweight, session-level locks that coordinate across processes:

```python
# In _check_schedules():
cur.execute("SELECT pg_try_advisory_lock(1050)")
got_lock = cur.fetchone()[0]

if not got_lock:
    # Another worker is handling schedules, skip
    return

# Only one worker reaches here
# ... trigger launchers ...

# Always release lock in finally block
cur.execute("SELECT pg_advisory_unlock(1050)")
```

**How it works:**
- Lock key `1050` is unique to the scheduler (arbitrary integer)
- `pg_try_advisory_lock()` is **non-blocking** - returns immediately
- Only one process across all workers can hold the lock
- Other workers see `got_lock=False` and skip the check cycle
- Lock auto-releases on connection close (failsafe)

**Benefits:**
- ✅ No external coordination service (Redis, ZooKeeper)
- ✅ No database table contention
- ✅ Automatic failover (if lock holder crashes, next worker takes over)
- ✅ Zero configuration required

**Testing multi-worker safety:**
```bash
# Start with 4 workers
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.api.main:app

# Watch logs - you should see only ONE worker per minute logging:
# "Acquired scheduler lock, proceeding with schedule check"
# Other 3 workers: "Scheduler lock held by another worker, skipping check cycle"

# Verify only ONE job created per schedule trigger
kg jobs list --limit 10 | grep category_refresh
```

### Distinguishing Skip from Failure (Critical)

**Problem:** The launcher returns `None` in two very different scenarios:
1. **Normal skip**: Conditions not met (healthy, expected)
2. **Actual failure**: Exception during condition check or enqueueing (needs retry)

Treating both as "failure" causes schedules to get disabled after 5 normal skips.

**Solution: Three-Outcome Pattern**

Launcher returns three possible outcomes:
- `job_id` → Success (job enqueued)
- `None` → Skip (conditions not met, normal)
- `Exception` → Failure (needs retry/backoff)

```python
# Launcher.launch() - Let exceptions bubble up
def launch(self) -> Optional[str]:
    if not self.check_conditions():
        return None  # Normal skip, not a failure

    job_data = self.prepare_job_data()  # Raises on failure
    job_id = self.job_queue.enqueue(...)  # Raises on failure
    return job_id

# Scheduler._check_schedules() - Handle three outcomes
try:
    job_id = launcher.launch()
except Exception as e:
    launch_failed = True

if job_id:
    # Success: reset retry_count, update last_success
elif not launch_failed:
    # Skip: reset retry_count, advance schedule (DON'T increment retries!)
else:
    # Failure: increment retry_count, exponential backoff
```

**Why this matters:**
```
Without fix:
  00:00 ⏭️  Skip (conditions not met) → retry_count = 1
  06:00 ⏭️  Skip (conditions not met) → retry_count = 2
  12:00 ⏭️  Skip (conditions not met) → retry_count = 3
  18:00 ⏭️  Skip (conditions not met) → retry_count = 4
  24:00 ⏭️  Skip (conditions not met) → retry_count = 5
  30:00 ❌  Schedule disabled (max retries) - WRONG!

With fix:
  00:00 ⏭️  Skip (conditions not met) → retry_count = 0 ✅
  06:00 ⏭️  Skip (conditions not met) → retry_count = 0 ✅
  48:00 ✅  Success (conditions met) → retry_count = 0 ✅
  Schedule stays healthy ✅
```

### Monitoring Requirements

**Key metrics to track:**
- Scheduler lock acquisition rate (should be ~60 locks/hour = 1 per minute)
- Schedule success rate (last_success vs last_failure)
- Skip vs failure ratio (high skip rate is normal for polling pattern)
- Job queue depth (scheduled jobs vs manual jobs)

**Log patterns to watch:**
```
✅ Good: Multiple workers, one active scheduler
Worker 1: "Acquired scheduler lock, proceeding..."
Worker 2: "Scheduler lock held by another worker, skipping"
Worker 3: "Scheduler lock held by another worker, skipping"
Worker 4: "Scheduler lock held by another worker, skipping"

❌ Bad: All workers acquiring lock (advisory lock not working)
Worker 1: "Acquired scheduler lock..."
Worker 2: "Acquired scheduler lock..."  ← PROBLEM!
Worker 3: "Acquired scheduler lock..."  ← PROBLEM!
Worker 4: "Acquired scheduler lock..."  ← PROBLEM!
```

## Consequences

### Positive

**Minimal Changes:**
- ✅ Zero changes to existing job queue
- ✅ Zero changes to existing workers
- ✅ Zero changes to approval workflow
- ✅ Just add: scheduler loop + launchers

**No External Dependencies:**
- ✅ No APScheduler, Celery, Redis, RabbitMQ
- ✅ Just Python stdlib (asyncio) + croniter (cron parsing)
- ✅ One new table: `kg_api.scheduled_jobs`

**Consistency:**
- ✅ Scheduled jobs use same queue as manual jobs
- ✅ Same workers, same progress tracking, same SSE streaming
- ✅ Same approval workflow (if needed)

**Simple to Understand:**
- ✅ Clear separation: Scheduler (timing) → Launcher (conditions) → Queue (execution)
- ✅ Easy to add new scheduled jobs (create launcher, add to registry)
- ✅ Easy to debug (check schedule table, launcher logs)

### Negative

**Custom Code:**
- ❌ We maintain the scheduler loop (but it's simple)
- ❌ Not battle-tested like APScheduler (but we control it)

**Cron Parsing:**
- ❌ Need croniter library for cron expressions
- ❌ Could use simple intervals instead (every 6 hours = `schedule_interval_seconds`)

**Monitoring:**
- ❌ Need to monitor scheduler health (is the loop running?)
- ❌ Need to track schedule failures (last_success, last_failure)

**Multi-Worker Coordination:**
- ❌ Requires advisory locks in multi-worker deployments (but simple to implement)
- ❌ Single point of failure in scheduler loop (but auto-recovers via lock failover)

## Alternatives Considered

### Option A: APScheduler

**Pros:**
- Battle-tested, mature
- Many features (persistent, distributed, etc.)

**Cons:**
- External dependency
- Would still need launcher abstraction
- More complex than needed

**Decision:** Rejected - Unnecessary dependency

### Option B: System Cron

**Pros:**
- Dead simple
- OS-level

**Cons:**
- No integration with job queue
- No condition checks
- No exponential backoff
- Must configure on every server

**Decision:** Rejected - Not integrated with our system

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Add croniter dependency
- [ ] Create migration 019 (scheduled_jobs table)
- [ ] Implement JobScheduler class
- [ ] Implement JobLauncher base class
- [ ] Integrate with FastAPI lifecycle

### Phase 2: First Launcher (Week 2)
- [ ] Implement CategoryRefreshLauncher
- [ ] Implement vocab_refresh_worker
- [ ] Register worker in main.py
- [ ] Test with manual schedule trigger
- [ ] Monitor logs for condition checks

### Phase 3: Second Launcher (Week 3)
- [ ] Implement VocabConsolidationLauncher
- [ ] Implement vocab_consolidate_worker
- [ ] Register worker in main.py
- [ ] Tune hysteresis thresholds
- [ ] Test with production data

### Phase 4: Monitoring & API (Week 4)
- [ ] Add scheduled job endpoints (list, enable, disable, trigger)
- [ ] Add CLI commands (`kg admin scheduled list`, `kg admin scheduled trigger`)
- [ ] Add logging and metrics
- [ ] Document in user guide

## Testing Strategy

### Unit Tests
```python
def test_category_refresh_launcher_conditions():
    """Test condition checking logic"""
    launcher = CategoryRefreshLauncher(queue)
    # Mock AGE client to return categories with llm_generated
    assert launcher.check_conditions() == True

def test_scheduler_loop_fires_launcher():
    """Test scheduler triggers launcher at scheduled time"""
    # Mock schedule that's due now
    # Verify launcher.launch() called
```

### Integration Tests
```python
def test_scheduled_job_end_to_end():
    """Test full scheduled job flow"""
    # 1. Insert schedule with past next_run
    # 2. Run scheduler._check_schedules()
    # 3. Verify job enqueued
    # 4. Verify schedule updated
```

### Manual Testing
```bash
# 1. Start API (single worker for initial testing)
./scripts/start-api.sh -y

# 2. Check scheduled jobs
psql -c "SELECT * FROM kg_api.scheduled_jobs"

# 3. Manually trigger
psql -c "UPDATE kg_api.scheduled_jobs SET next_run = NOW() WHERE name = 'category_refresh'"

# 4. Watch logs
tail -f logs/api_*.log | grep -i "launcher\|schedule"

# 5. Verify job created
kg jobs list --limit 5
```

### Multi-Worker Testing (Critical)
```bash
# 1. Start API with 4 workers
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.api.main:app

# 2. Watch logs for lock acquisition pattern (should see only ONE worker per minute)
tail -f logs/api_*.log | grep -i "scheduler lock"

# Expected pattern (repeated every 60 seconds):
# Worker 1: "Acquired scheduler lock, proceeding with schedule check"
# Worker 2: "Scheduler lock held by another worker, skipping check cycle"
# Worker 3: "Scheduler lock held by another worker, skipping check cycle"
# Worker 4: "Scheduler lock held by another worker, skipping check cycle"

# 3. Trigger a schedule manually
psql -c "UPDATE kg_api.scheduled_jobs SET next_run = NOW() WHERE name = 'category_refresh'"

# 4. Verify only ONE job created (not 4!)
kg jobs list --limit 10 | grep category_refresh
# Should show exactly 1 job, not 4

# 5. Check advisory lock status in PostgreSQL
psql -c "SELECT * FROM pg_locks WHERE locktype = 'advisory'"
# Should show lock key 1050 held by one backend process
```

## Monitoring

**Key Metrics:**
- Scheduler loop health (last check time)
- Schedule success rate (last_success vs last_failure)
- Launcher condition check frequency (true / false ratio)
- Job queue depth (scheduled jobs vs manual jobs)

**Log Examples:**
```
INFO: ✅ Job scheduler started
INFO: ⏰ Schedule 'category_refresh' is due, triggering launcher
INFO: ✓ CategoryRefreshLauncher: Found category 'Temporal Expressions' with llm_generated entries
INFO: ✅ CategoryRefreshLauncher: Enqueued job job_abc123
INFO: ⏭️  VocabConsolidationLauncher: Conditions not met, skipping (inactive ratio 8% < 10%)
WARNING: ⚠️  Schedule 'vocab_consolidation' failed (retry 2/5), retrying in 4min
ERROR: ❌ Schedule 'category_refresh' max retries exceeded, disabling
```

## Future Enhancements

### Phase 2: Advanced Features
- [ ] Calendar-aware scheduling (skip weekends, holidays)
- [ ] Dependency chains (job B after job A completes)
- [ ] Dynamic schedule adjustment based on metrics

### Phase 3: Distributed Execution
- [ ] Multi-node scheduler coordination (leader election)
- [ ] Distributed schedule locks (prevent duplicate execution)

### Phase 4: Machine Learning
- [ ] Predict optimal consolidation timing
- [ ] Auto-tune hysteresis thresholds
- [ ] Anomaly detection for schedule failures

## References

- **croniter:** https://pypi.org/project/croniter/
- **ADR-012:** API Server Architecture
- **ADR-014:** Job Approval Workflow
- **ADR-049:** Rate Limiting and Per-Provider Concurrency

---

**Last Updated:** 2025-10-28
