# kg job approve

Approve jobs for processing.

## Usage

```bash
kg job approve [options] [command]
```

## Description

Approve jobs that are in `awaiting_approval` status, allowing them to proceed to processing. This is part of the job approval workflow (ADR-014) that provides cost visibility before processing begins.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `job <job-id>` | Approve a specific job by ID | [↓](#job) |
| `pending` | Approve all jobs awaiting approval | [↓](#pending) |
| `filter <status>` | Approve all jobs matching status filter | [↓](#filter) |

---

## Subcommand Details

### job

Approve a specific job by ID.

**Usage:**
```bash
kg job approve job [options] <job-id>
```

**Arguments:**
- `<job-id>` - Job identifier to approve

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**Examples:**

```bash
# Approve single job
kg job approve job job_abc123

# Workflow: check cost then approve
kg job status job_abc123
# Review estimated cost: $0.15
kg job approve job job_abc123
```

**Output:**
```
✓ Job job_abc123 approved and queued for processing
```

---

### pending

Approve all jobs awaiting approval.

**Usage:**
```bash
kg job approve pending [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to approve | `100` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Approve all pending
kg job approve pending

# Approve with limit
kg job approve pending -l 10

# Approve for specific client
kg job approve pending -c client-123
```

**Confirmation:**

Requires confirmation for batch operations:

```
About to approve 15 jobs for processing.
Estimated total cost: $2.35

Continue? [y/N]:
```

**Output:**
```
Approved jobs:
  ✓ job_abc123 ($0.15)
  ✓ job_def456 ($0.22)
  ✓ job_ghi789 ($0.18)
  ...

Total approved: 15 jobs
Estimated cost: $2.35
```

---

### filter

Approve all jobs matching a status filter.

**Usage:**
```bash
kg job approve filter [options] <status>
```

**Arguments:**
- `<status>` - Status filter (e.g., `awaiting_approval`, `pending`)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to approve | `100` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Approve by status
kg job approve filter awaiting_approval

# With limit
kg job approve filter awaiting_approval -l 20
```

---

## Approval Workflow

```
┌──────────────────┐
│  Submit Document │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│   Job Created    │
│   (pending)      │
└────────┬─────────┘
         │
    ┌────┴────┐
    │  Auto?  │
    └────┬────┘
     Yes │ No
         │  │
         │  v
         │ ┌───────────────────┐
         │ │awaiting_approval  │ ← Check cost estimate
         │ │  Est. cost: $0.15 │
         │ └────────┬──────────┘
         │          │
         │          v
         │     ┌────────────┐
         │     │  Approve?  │
         │     └────┬───────┘
         │      Yes │ No
         │          │  │
         │          │  v
         │          │ ┌────────┐
         │          │ │ Cancel │
         │          │ └────────┘
         │          │
         v          v
┌──────────────────────┐
│   Approved/Queued    │
│    (processing)      │
└──────────────────────┘
```

---

## Cost Review Process

Before approving, review the estimated costs:

```bash
# 1. List pending jobs
kg job list pending

# 2. Check cost for specific job
kg job status job_abc123
# Shows:
#   Estimated cost:
#     Extraction: $0.12
#     Embeddings: $0.03
#     Total: $0.15

# 3. Decide
kg job approve job job_abc123
# or
kg job cancel job_abc123
```

---

## Common Use Cases

### Approve After Cost Review

```bash
# Submit with manual approval
kg ingest file -o "Docs" --no-approve large-doc.pdf

# Review job
JOB=$(kg job list pending | head -1 | awk '{print $1}')
kg job status $JOB

# Approve if acceptable
kg job approve job $JOB
```

### Batch Approval

```bash
# Check pending queue
kg job list pending

# Review total estimated cost
kg job list pending | wc -l
# 15 jobs

# Approve all (with confirmation)
kg job approve pending
```

### Selective Approval

```bash
# List pending with details
kg job list pending

# Approve specific cheap jobs
kg job approve job job_abc123  # $0.05
kg job approve job job_def456  # $0.08

# Cancel expensive one
kg job cancel job_ghi789  # $2.50
```

### Multi-Tenant Approval

```bash
# Approve for specific tenant
kg job approve pending -c tenant-prod

# Or review first
kg job list pending -c tenant-prod
kg job approve pending -c tenant-prod
```

---

## Auto-Approval Configuration

To skip manual approval step:

```bash
# Enable auto-approval globally
kg config auto-approve true

# Or per-ingestion
kg ingest file -o "Docs" document.txt
# (auto-approves by default if config set)

# Force manual approval even with auto-approve on
kg ingest file -o "Docs" --no-approve sensitive-doc.pdf
```

Related: [`kg config auto-approve`](../../config/#auto-approve)

---

## Safety Features

1. **Cost Visibility** - Always show estimated cost
2. **Confirmation Required** - Batch operations need confirmation
3. **Limit Protection** - Default limit of 100 prevents accidents
4. **Client Isolation** - Multi-tenant filtering prevents cross-tenant approval

---

## Troubleshooting

### Jobs Not Processing After Approval

**Cause:** Worker not running or queue backed up

**Check:**
```bash
kg admin status
kg job list approved
```

**Solution:**
```bash
# Restart API to restart workers
./scripts/stop-api.sh
./scripts/start-api.sh
```

### Cannot Find Job to Approve

**Cause:** Job may have auto-approved or been cancelled

**Check:**
```bash
# Check if already processing
kg job status job_abc123

# Check all statuses
kg job list --status queued
kg job list --status cancelled
```

---

## Related Commands

- [`kg job list pending`](../list/#pending) - View jobs awaiting approval
- [`kg job status`](../#status) - Check job details and cost
- [`kg job cancel`](../#cancel) - Cancel instead of approving
- [`kg config auto-approve`](../../config/#auto-approve) - Configure auto-approval
- [`kg ingest --no-approve`](../../ingest/#file) - Force manual approval

---

## See Also

- [Job Approval Workflow](../../../01-getting-started/ingestion.md#approval-workflow)
- [ADR-014: Job Approval Workflow](../../../../architecture/ADR-014-job-approval-workflow.md)
- [Cost Estimation](../../../06-reference/cost-estimation.md)
- [Main Job Commands](../)
