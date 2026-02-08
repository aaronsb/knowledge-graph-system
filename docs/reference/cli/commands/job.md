# kg job

> Auto-generated

## job (jobs)

Manage and monitor ingestion jobs through their lifecycle (pending → approval → processing → completed/failed)

**Usage:**
```bash
kg job [options]
```

**Subcommands:**

- `status` - Get detailed status information for a job (progress, costs, errors) - use --watch to poll until completion
- `list` - List recent jobs with optional filtering by status or user - includes subcommands for common filters
- `approve` - Approve jobs for processing (ADR-014 approval workflow) - single job, batch pending, or filter by status
- `cancel` - Cancel a specific job by ID or batch cancel using filters (all, pending, running, queued, approved)
- `delete` - Permanently delete a job from database (removes record entirely, not just cancels)
- `cleanup` - Delete jobs matching filters (with preview) - safer alternative to clear
- `clear` - Clear ALL jobs from database (deprecated: use "cleanup --all --confirm" instead)

---

### status

Get detailed status information for a job (progress, costs, errors) - use --watch to poll until completion

**Usage:**
```bash
kg status <job-id>
```

**Arguments:**

- `<job-id>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-w, --watch` | Watch job until completion (polls every few seconds) | `false` |

### list

List recent jobs with optional filtering by status or user - includes subcommands for common filters

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-s, --status <status>` | Filter by status (pending|approved|queued|running|completed|failed|cancelled) | - |
| `-c, --client <user-id>` | Filter by user ID (view specific user's jobs) | - |
| `-l, --limit <n>` | Maximum jobs to return (max: 500, default: 100) | `"100"` |
| `-o, --offset <n>` | Number of jobs to skip for pagination (default: 0) | `"0"` |
| `--full-id` | Show full job IDs without truncation | `false` |

**Subcommands:**

- `pending` - List jobs awaiting approval
- `approved` - List approved jobs (queued or processing)
- `done` - List completed jobs
- `failed` - List failed jobs
- `cancelled` - List cancelled jobs

---

#### pending

List jobs awaiting approval

**Usage:**
```bash
kg pending [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `"20"` |
| `--full-id` | Show full job IDs (no truncation) | `false` |

#### approved

List approved jobs (queued or processing)

**Usage:**
```bash
kg approved [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `"20"` |
| `--full-id` | Show full job IDs (no truncation) | `false` |

#### done

List completed jobs

**Usage:**
```bash
kg done [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `"20"` |
| `--full-id` | Show full job IDs (no truncation) | `false` |

#### failed

List failed jobs

**Usage:**
```bash
kg failed [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `"20"` |
| `--full-id` | Show full job IDs (no truncation) | `false` |

#### cancelled

List cancelled jobs

**Usage:**
```bash
kg cancelled [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to return | `"20"` |
| `--full-id` | Show full job IDs (no truncation) | `false` |

### approve

Approve jobs for processing (ADR-014 approval workflow) - single job, batch pending, or filter by status

**Usage:**
```bash
kg approve [options]
```

**Subcommands:**

- `job` - Approve a specific job by ID after reviewing cost estimates
- `pending` - Approve all jobs awaiting approval (batch operation with confirmation)
- `filter` - Approve all jobs matching status filter

---

#### job

Approve a specific job by ID after reviewing cost estimates

**Usage:**
```bash
kg job <job-id>
```

**Arguments:**

- `<job-id>` - Required

#### pending

Approve all jobs awaiting approval (batch operation with confirmation)

**Usage:**
```bash
kg pending [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |
| `-l, --limit <n>` | Maximum jobs to approve (default: 100) | `"100"` |

#### filter

Approve all jobs matching status filter

**Usage:**
```bash
kg filter <status>
```

**Arguments:**

- `<status>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID | - |

### cancel

Cancel a specific job by ID or batch cancel using filters (all, pending, running, queued, approved)

**Usage:**
```bash
kg cancel <job-id-or-filter>
```

**Arguments:**

- `<job-id-or-filter>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --client <user-id>` | Filter by user ID for batch operations | - |
| `-l, --limit <n>` | Maximum jobs to cancel for safety (default: 100) | `"100"` |

### delete

Permanently delete a job from database (removes record entirely, not just cancels)

**Usage:**
```bash
kg delete <job-id>
```

**Arguments:**

- `<job-id>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Force delete even if job is processing (dangerous) | `false` |

### cleanup

Delete jobs matching filters (with preview) - safer alternative to clear

**Usage:**
```bash
kg cleanup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-s, --status <status>` | Filter by status (pending|cancelled|completed|failed|running) | - |
| `--system` | Only delete system/scheduled jobs | `false` |
| `--older-than <duration>` | Delete jobs older than duration (1h|24h|7d|30d) | - |
| `-t, --type <job-type>` | Filter by job type (ingestion|epistemic_remeasurement|projection|etc) | - |
| `--confirm` | Execute deletion (without this flag, shows preview only) | `false` |
| `--all` | Delete ALL jobs (nuclear option, requires --confirm) | `false` |

### clear

Clear ALL jobs from database (deprecated: use "cleanup --all --confirm" instead)

**Usage:**
```bash
kg clear [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--confirm` | Confirm deletion (REQUIRED for safety) | `false` |
