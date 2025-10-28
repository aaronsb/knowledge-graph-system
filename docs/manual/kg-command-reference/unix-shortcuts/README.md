# Unix-Style Shortcuts

Familiar Unix-style commands for resource management.

## Overview

The kg CLI provides Unix-style shortcuts that map to existing commands, making it feel familiar to Unix users:

| Unix Command | kg Shortcut | Maps To |
|--------------|-------------|---------|
| `ls` | `kg ls <resource>` | List resources |
| `stat` | `kg stat <resource> [id]` | Show status/statistics |
| `rm` | `kg rm <resource> <id>` | Remove/delete resources |
| `cat` / `bat` | `kg cat <resource> [id]` | Display resource details |

**Philosophy:** Provide intuitive, Unix-like interface while maintaining full command compatibility.

---

## Commands

### ls

List resources (like Unix `ls` command).

**Usage:**
```bash
kg ls [options] <resource>
```

**Arguments:**
- `<resource>` - Resource type: job, ontology, backup, config, role, permission, resource, user

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `-h, --help` | Display help for command |

**Examples:**

```bash
# List jobs
kg ls job

# List ontologies
kg ls ontology

# List backups
kg ls backup

# List with JSON output
kg ls job --json

# List users (admin only)
kg ls user
```

**Maps To:**

| Shortcut | Equivalent Command |
|----------|-------------------|
| `kg ls job` | `kg job list` |
| `kg ls ontology` | `kg ontology list` |
| `kg ls backup` | `kg admin list-backups` |
| `kg ls user` | `kg admin user list` |
| `kg ls role` | `kg admin rbac role list` |

**Output Example:**

```bash
kg ls ontology
# Same output as: kg ontology list

📚 Ontologies in Knowledge Graph
────────────────────────────────────────────────────────────
Ontology                    Files      Chunks      Concepts
────────────────────────────────────────────────────────────
Research Papers                12          45           234
Company Docs                    8          32           156
────────────────────────────────────────────────────────────
```

---

### stat

Show status or statistics (like Unix `stat` command).

**Usage:**
```bash
kg stat [options] <resource> [id]
```

**Arguments:**
- `<resource>` - Resource type: job, database
- `[id]` - Resource identifier (required for jobs)

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `-h, --help` | Display help for command |

**Examples:**

```bash
# Database statistics
kg stat database

# Job status
kg stat job job_abc123

# With JSON output
kg stat database --json
```

**Maps To:**

| Shortcut | Equivalent Command |
|----------|-------------------|
| `kg stat database` | `kg database stats` |
| `kg stat job <id>` | `kg job status <id>` |

**Output Example:**

```bash
kg stat database
# Same output as: kg database stats

📊 Database Statistics
────────────────────────────────────────────────────────────
Nodes
  Concepts: 1,234
  Sources: 45
  Instances: 2,456

Relationships
  Total: 3,567
────────────────────────────────────────────────────────────
```

---

### rm

Remove or delete resources (like Unix `rm` command).

**Usage:**
```bash
kg rm [options] <resource> <id>
```

**Arguments:**
- `<resource>` - Resource type: job, ontology, role, permission, user
- `<id>` - Resource identifier

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | requires confirmation |
| `--json` | Output as JSON | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Delete ontology (with confirmation)
kg rm ontology "Test Data"

# Force delete job (no confirmation)
kg rm job job_abc123 --force

# Delete user (admin only)
kg rm user user_123 -f
```

**Maps To:**

| Shortcut | Equivalent Command |
|----------|-------------------|
| `kg rm ontology <name>` | `kg ontology delete <name>` |
| `kg rm job <id>` | `kg job cancel <id>` |
| `kg rm user <id>` | `kg admin user delete <id>` |

**Interactive Confirmation:**

```bash
kg rm ontology "Test Data"

⚠ WARNING: This will DELETE the ontology "Test Data"

This will permanently delete:
  - 50 concepts
  - 5 sources
  - 75 instances
  - 100 relationships

Type the ontology name to confirm deletion:
```

**Force Mode:**

```bash
kg rm ontology "Test Data" -f
# Deletes immediately without confirmation
```

---

### cat / bat

Display resource details (like Unix `cat` command).

**Usage:**
```bash
kg cat [options] <resource> [id]
kg bat [options] <resource> [id]
```

**Note:** `bat` is an alias for `cat` (inspired by the `bat` utility).

**Arguments:**
- `<resource>` - Resource type: concept, config, job, role, ontology
- `[id]` - Resource identifier (optional for config)

**Options:**

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `-h, --help` | Display help for command |

**Examples:**

```bash
# Display concept details
kg cat concept concept_abc123

# Display config value
kg cat config apiUrl

# Display all config
kg cat config

# Display job details
kg cat job job_abc123

# Display ontology info
kg cat ontology "Research Papers"

# With JSON output
kg cat concept concept_abc123 --json
```

**Maps To:**

| Shortcut | Equivalent Command |
|----------|-------------------|
| `kg cat concept <id>` | `kg search details <id>` |
| `kg cat config [key]` | `kg config get [key]` |
| `kg cat job <id>` | `kg job status <id>` |
| `kg cat ontology <name>` | `kg ontology info <name>` |

**Output Example:**

```bash
kg cat concept concept_abc123
# Same output as: kg search details concept_abc123

Concept: Machine Learning Algorithms
ID: concept_abc123
Grounding Strength: ████████░░ 84%

Evidence (12 instances):
  [1] "Machine learning algorithms learn patterns..."
      Source: ai-overview.md (paragraph 3)
  ...
```

---

## Common Use Cases

### Quick Resource Listing

```bash
# List everything
kg ls job
kg ls ontology
kg ls backup
kg ls user
```

### Status Checks

```bash
# Check system
kg stat database

# Check specific job
kg stat job job_abc123
```

### Cleanup

```bash
# Delete test ontologies
kg rm ontology "Test 1" -f
kg rm ontology "Test 2" -f

# Cancel failed jobs
kg ls job --status failed | while read job; do
  kg rm job $job -f
done
```

### Inspection

```bash
# Inspect concept
kg cat concept concept_abc123

# Check config
kg cat config

# Review job
kg cat job job_abc123
```

---

## Unix-Style Patterns

### Chaining with Pipes

```bash
# List jobs and filter
kg ls job --json | jq '.[] | select(.status == "failed")'

# Get concept IDs
kg ls concept --json | jq -r '.[].concept_id'
```

### For Loops

```bash
# Delete all test ontologies
for onto in $(kg ls ontology | grep "Test" | awk '{print $1}'); do
  kg rm ontology "$onto" -f
done
```

### Status Checks

```bash
# Check database, exit if unhealthy
kg stat database > /dev/null || exit 1
```

---

## Comparison: Standard vs Shortcuts

### List Operations

```bash
# Standard
kg job list
kg ontology list
kg admin list-backups

# Shortcuts
kg ls job
kg ls ontology
kg ls backup
```

### Status/Stats

```bash
# Standard
kg database stats
kg job status job_abc123

# Shortcuts
kg stat database
kg stat job job_abc123
```

### Delete Operations

```bash
# Standard
kg ontology delete "Test"
kg job cancel job_abc123

# Shortcuts
kg rm ontology "Test"
kg rm job job_abc123
```

### Display Details

```bash
# Standard
kg search details concept_abc123
kg config get apiUrl

# Shortcuts
kg cat concept concept_abc123
kg cat config apiUrl
```

---

## Why Use Shortcuts?

**Advantages:**
- **Familiar** - Unix users feel at home
- **Concise** - Shorter commands
- **Consistent** - Same pattern across resources
- **Scriptable** - Easy to use in scripts

**When to Use:**
- Interactive shell work
- Quick operations
- Shell scripts
- Admin tasks

**When to Use Full Commands:**
- Scripts for other users (more explicit)
- Documentation (clearer intent)
- Complex operations (more options available)
- Learning the system

---

## Tips and Tricks

### Aliases

Add to your shell rc file:

```bash
alias kls='kg ls'
alias kstat='kg stat'
alias krm='kg rm'
alias kcat='kg cat'
```

### Quick Status Check

```bash
# One-liner system check
kg stat database && echo "✓ System healthy"
```

### Batch Delete

```bash
# Delete all failed jobs
kg ls job --json | \
  jq -r '.[] | select(.status == "failed") | .job_id' | \
  xargs -I {} kg rm job {} -f
```

### Resource Inspection

```bash
# Inspect first concept in results
CONCEPT=$(kg search query "ML" --json | jq -r '.[0].concept_id')
kg cat concept $CONCEPT
```

---

## Limitations

**Not Implemented:**
- `cd` (no directory structure)
- `mv` (use full commands for rename)
- `cp` (use backup/restore)
- `touch` (use create commands)
- `mkdir` (ontologies created via ingestion)

**Partial Implementation:**
- `ls` - Lists resources, not filesystem
- `rm` - Deletes resources, not files
- `cat` - Shows resource details, not file contents
- `stat` - Shows resource stats, not file stats

---

## Related Commands

- [`kg job`](../job/) - Full job management
- [`kg ontology`](../ontology/) - Full ontology management
- [`kg database`](../database/) - Full database commands
- [`kg search`](../search/) - Full search commands
- [`kg admin`](../admin/) - Full admin commands

---

## See Also

- [CLI Overview](../../01-getting-started/cli-basics.md)
- [Shell Integration](../../03-guides/shell-integration.md)
- [Scripting Guide](../../03-guides/scripting.md)
