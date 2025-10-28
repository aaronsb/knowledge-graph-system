# kg job

Manage and monitor ingestion jobs.

## Usage

```bash
kg job|jobs [options] [command]
```

**Alias:** `jobs`

## Description

The `job` command provides comprehensive management of ingestion jobs. Jobs are created when documents are ingested and track the extraction, embedding, and graph insertion process.

Jobs progress through several states:
- **pending** - Submitted, cost estimated
- **awaiting_approval** - Waiting for manual approval (ADR-014)
- **approved** - Approved, waiting to be queued
- **queued** - In queue, waiting for worker
- **processing** - Actively being processed
- **completed** - Successfully finished
- **failed** - Encountered an error
- **cancelled** - Manually cancelled

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `status <job-id>` | Get job status | [↓](#status) |
| `list` | List recent jobs (optionally filtered) | [list/](./list/) |
| `approve` | Approve jobs for processing | [approve/](./approve/) |
| `cancel <job-id-or-filter>` | Cancel a job or jobs matching filter | [↓](#cancel) |
| `clear` | Clear ALL jobs from database | [↓](#clear) |

## Command Tree

```
kg job (jobs)
├── status <job-id>
├── list
│   ├── (list all with filters)
│   ├── pending
│   ├── approved
│   ├── done
│   ├── failed
│   └── cancelled
├── approve
│   ├── job <job-id>
│   ├── pending
│   └── filter <status>
├── cancel <job-id-or-filter>
└── clear
```

---

## Subcommand Details

### status

Get detailed status information for a specific job.

**Usage:**
```bash
kg job status [options] <job-id>
```

**Arguments:**
- `<job-id>` - Job identifier (e.g., `job_abc123`)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-w, --watch` | Watch job until completion (polls every few seconds) | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Check job status once
kg job status job_abc123

# Watch until complete
kg job status -w job_abc123

# Get status from ingestion
JOB_ID=$(kg ingest file -o "Docs" readme.md | grep "job_" | awk '{print $NF}')
kg job status $JOB_ID
```

**Output Example:**

```
Job: job_abc123
Status: completed
Ontology: Documentation
Created: 2024-01-15 14:30:22

Progress:
  Chunks processed: 5/5
  Concepts created: 23
  Sources created: 5
  Relationships: 47

Cost:
  Extraction: $0.15
  Embeddings: $0.02
  Total: $0.17

Duration: 45 seconds
```

**Watch Mode:**

With `-w`, continuously polls and updates status:

```bash
kg job status -w job_abc123

Watching job_abc123...
Status: processing
Chunks: 2/5 (40%)
...
Chunks: 5/5 (100%)
Status: completed ✓
```

---

### cancel

Cancel a job or multiple jobs matching a filter.

**Usage:**
```bash
kg job cancel [options] <job-id-or-filter>
```

**Arguments:**
- `<job-id-or-filter>` - Either a specific job ID or a filter keyword

**Filters:**
- `all` - Cancel all cancellable jobs
- `pending` - Cancel all pending jobs
- `running` / `processing` - Cancel currently processing jobs
- `queued` - Cancel queued jobs
- `approved` - Cancel approved but not yet processing

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID (for batch operations) | - |
| `-l, --limit <n>` | Maximum jobs to cancel | `100` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Cancel specific job
kg job cancel job_abc123

# Cancel all pending jobs
kg job cancel pending

# Cancel all cancellable jobs (with limit)
kg job cancel all --limit 50

# Cancel jobs for specific client
kg job cancel pending -c client-123
```

**Confirmation:**

Batch cancellations require confirmation:

```
About to cancel 15 jobs. Continue? [y/N]:
```

**Output:**

```
Cancelled jobs:
  ✓ job_abc123
  ✓ job_def456
  ✓ job_ghi789

Total cancelled: 3
```

**Safety:**
- Cannot cancel completed or failed jobs
- Processing jobs are stopped gracefully (may take a moment)
- Limit protects against accidental mass cancellation

---

### clear

Clear ALL jobs from the database. **Destructive operation.**

**Usage:**
```bash
kg job clear [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--confirm` | Confirm deletion (required) | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Attempt to clear (will fail without confirm)
kg job clear
# Error: Must use --confirm flag

# Clear all jobs
kg job clear --confirm
```

**Warning:**

```
⚠ WARNING: This will delete ALL jobs from the database!
This includes:
  - 150 pending jobs
  - 45 completed jobs
  - 12 failed jobs
  - 207 total jobs

This action CANNOT be undone.

Type 'DELETE ALL JOBS' to confirm:
```

**Use Cases:**
- Development/testing cleanup
- Starting fresh after configuration changes
- Clearing large backlog of old jobs

**Caution:** Only use when you're certain. Job data helps with debugging and historical analysis.

---

## List Commands

See [list/](./list/) for detailed documentation of list subcommands:

- `kg job list` - List all with filters
- `kg job list pending` - Jobs awaiting approval
- `kg job list approved` - Approved/queued/processing
- `kg job list done` - Completed jobs
- `kg job list failed` - Failed jobs
- `kg job list cancelled` - Cancelled jobs

---

## Approve Commands

See [approve/](./approve/) for detailed documentation of approve subcommands:

- `kg job approve job <id>` - Approve specific job
- `kg job approve pending` - Approve all pending
- `kg job approve filter <status>` - Approve by status

---

## Job Lifecycle

```
                   ┌──────────────┐
                   │   Ingestion  │
                   │   Submitted  │
                   └──────┬───────┘
                          │
                          v
                   ┌──────────────┐
                   │   pending    │ ← kg job list pending
                   └──────┬───────┘
                          │
                   ┌──────┴───────┐
                   │ Auto-approve?│
                   └──────┬───────┘
                     Yes  │  No
                          │   │
                          │   v
                          │ ┌──────────────────┐
                          │ │awaiting_approval │ ← kg job approve job <id>
                          │ └────────┬─────────┘   kg job approve pending
                          │          │
                          v          v
                   ┌──────────────┐
                   │   approved   │
                   └──────┬───────┘
                          │
                          v
                   ┌──────────────┐
                   │    queued    │ ← kg job list approved
                   └──────┬───────┘
                          │
                          v
                   ┌──────────────┐
                   │  processing  │ ← kg job status -w <id>
                   └──────┬───────┘
                          │
                   ┌──────┴────────┐
                   │               │
                   v               v
            ┌────────────┐  ┌───────────┐
            │ completed  │  │  failed   │
            └────────────┘  └───────────┘
               │                  │
               v                  v
         kg job list done   kg job list failed

        (cancelled possible at any stage before processing completes)
```

---

## Job Status Values

| Status | Description | Can Cancel? | Can Approve? |
|--------|-------------|-------------|--------------|
| `pending` | Just submitted, estimating cost | ✓ | ✓ |
| `awaiting_approval` | Waiting for manual approval | ✓ | ✓ |
| `approved` | Approved, will be queued | ✓ | - |
| `queued` | In queue, waiting for worker | ✓ | - |
| `processing` | Being processed by worker | ✓ | - |
| `completed` | Successfully finished | - | - |
| `failed` | Error occurred | - | - |
| `cancelled` | Manually cancelled | - | - |

---

## Common Workflows

### Monitor Single Job

```bash
# Submit and wait
kg ingest file -o "Docs" -w readme.md

# Or submit and monitor separately
JOB=$(kg ingest file -o "Docs" readme.md | grep job_ | awk '{print $NF}')
kg job status -w $JOB
```

### Batch Approval

```bash
# Check pending jobs
kg job list pending

# Approve all
kg job approve pending

# Or approve with limit
kg job approve pending -l 10
```

### Review Failed Jobs

```bash
# List failed jobs
kg job list failed

# Check specific failure
kg job status job_abc123

# Review error details (in output)
```

### Clean Up Old Jobs

```bash
# Cancel stale pending jobs
kg job cancel pending

# Clear completed jobs from DB
# (Currently requires full clear - selective cleanup TODO)
```

### Multi-Tenant Job Management

```bash
# List jobs for specific client
kg job list -c client-123

# Approve for specific client
kg job approve pending -c client-123

# Cancel for specific client
kg job cancel pending -c client-123
```

---

## Performance Tips

### High-Volume Ingestion

```bash
# Submit many jobs
for file in ./docs/*.md; do
  kg ingest file -o "Docs" "$file"
done

# Monitor progress
watch -n 5 'kg job list approved'

# Or batch status check
kg job list --status processing
```

### Job Queue Backlog

```bash
# Check queue depth
kg job list --status queued

# Check system health
kg admin status

# If workers stalled, restart API
./scripts/stop-api.sh && ./scripts/start-api.sh
```

---

## Troubleshooting

### Job Stuck in Pending

**Cause:** Waiting for approval

**Solution:**
```bash
kg job list pending
kg job approve pending
```

### Job Stuck in Processing

**Cause:** Worker crash or API restart

**Check:**
```bash
kg admin status
kg job status job_abc123
```

**Solution:**
```bash
# Restart API to recover
./scripts/stop-api.sh
./scripts/start-api.sh

# Or cancel and resubmit
kg job cancel job_abc123
kg ingest file -o "Docs" document.txt
```

### Failed Job

**Investigation:**
```bash
# Get error details
kg job status job_abc123

# Check API logs
tail -100 logs/api_*.log | grep job_abc123

# Check extraction model
kg admin extraction status
```

**Common Causes:**
- Malformed document
- LLM API timeout
- Embedding generation failure
- Database connection issue

---

## Related Commands

- [`kg ingest`](../ingest/) - Submit jobs
- [`kg config auto-approve`](../config/#auto-approve) - Configure auto-approval
- [`kg admin status`](../admin/#status) - System health
- [`kg admin scheduler`](../admin/#scheduler) - Job scheduler management

---

## See Also

- [Job Management Guide](../../06-reference/jobs.md)
- [ADR-014: Job Approval Workflow](../../../architecture/ADR-014-job-approval-workflow.md)
- [ADR-024: PostgreSQL Job Queue](../../../architecture/ADR-024-postgresql-job-queue.md)
- [Troubleshooting Jobs](../../05-maintenance/troubleshooting.md#jobs)
