# kg job list

List recent jobs with optional filtering.

## Usage

```bash
kg job list [options] [command]
```

## Description

List and filter ingestion jobs. Can show all jobs or filter by status, client, and other criteria.

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `-s, --status <status>` | Filter by status | - |
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return (max: 500) | `100` |
| `-o, --offset <n>` | Number of jobs to skip (pagination) | `0` |
| `--full-id` | Show full job IDs (no truncation) | `false` |
| `-h, --help` | Display help for command | - |

## Status Values

Valid values for `-s, --status`:
- `pending`
- `awaiting_approval`
- `approved`
- `queued`
- `processing`
- `completed`
- `failed`
- `cancelled`

## Subcommands

Convenience shortcuts for common filters:

| Command | Equivalent To | Description |
|---------|---------------|-------------|
| `pending` | `list --status awaiting_approval` | Jobs awaiting approval |
| `approved` | `list --status queued,processing` | Approved and running |
| `done` | `list --status completed` | Completed jobs |
| `failed` | `list --status failed` | Failed jobs |
| `cancelled` | `list --status cancelled` | Cancelled jobs |

---

## Examples

### List All Recent Jobs

```bash
kg job list
```

Output:
```
job_abc1234  completed   Documentation      5 min ago
job_def5678  processing  Research Papers    2 min ago
job_ghi9012  pending     Notes             1 min ago
...
(showing 100 of 247 total jobs)
```

### Filter by Status

```bash
kg job list --status processing
```

### Pagination

```bash
# First page
kg job list -l 50

# Second page
kg job list -l 50 -o 50

# Third page
kg job list -l 50 -o 100
```

### Multi-Tenant Filtering

```bash
kg job list -c client-123
```

### Show Full IDs

```bash
kg job list --full-id
```

Output:
```
job_abc1234567890  completed  Documentation
```

---

## Subcommand Details

### pending

List jobs awaiting approval.

**Usage:**
```bash
kg job list pending [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `20` |
| `--full-id` | Show full job IDs | `false` |
| `-h, --help` | Display help for command | - |

**Example:**
```bash
kg job list pending
```

---

### approved

List approved jobs (queued or processing).

**Usage:**
```bash
kg job list approved [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `20` |
| `--full-id` | Show full job IDs | `false` |
| `-h, --help` | Display help for command | - |

**Example:**
```bash
kg job list approved
```

---

### done

List completed jobs.

**Usage:**
```bash
kg job list done [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `20` |
| `--full-id` | Show full job IDs | `false` |
| `-h, --help` | Display help for command | - |

**Example:**
```bash
kg job list done
```

---

### failed

List failed jobs.

**Usage:**
```bash
kg job list failed [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `20` |
| `--full-id` | Show full job IDs | `false` |
| `-h, --help` | Display help for command | - |

**Example:**
```bash
# List failures
kg job list failed

# Investigate specific failure
kg job status job_abc123
```

---

### cancelled

List cancelled jobs.

**Usage:**
```bash
kg job list cancelled [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <client-id>` | Filter by client ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `20` |
| `--full-id` | Show full job IDs | `false` |
| `-h, --help` | Display help for command | - |

**Example:**
```bash
kg job list cancelled
```

---

## Common Use Cases

### Monitor Active Jobs

```bash
# Watch processing jobs
watch -n 5 'kg job list approved'
```

### Review Recent Activity

```bash
# Last 20 completed
kg job list done

# Last 20 failed
kg job list failed
```

### Check Approval Queue

```bash
kg job list pending
```

### Find Specific Job

```bash
# List with full IDs and grep
kg job list --full-id | grep "myfile"
```

---

## Related Commands

- [`kg job status`](../#status) - Get detailed job status
- [`kg job approve`](../approve/) - Approve pending jobs
- [`kg job cancel`](../#cancel) - Cancel jobs

---

## See Also

- [Job Management Guide](../../../06-reference/jobs.md)
- [Main Job Commands](../)
