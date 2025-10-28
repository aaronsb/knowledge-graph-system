# kg admin

System administration and management.

## Usage

```bash
kg admin [options] [command]
```

## Description

The `admin` command provides system administration capabilities including:

- **System Status** - Docker, database, environment health
- **Backup & Restore** - Full system and per-ontology backups (ADR-036)
- **Database Management** - Reset, regenerate embeddings
- **Job Scheduler** - Monitor and manage background workers (ADR-014)
- **User Management** - Create, update, delete users
- **RBAC** - Role-based access control (ADR-028)
- **Model Configuration** - Embedding and extraction models (ADR-039, ADR-041)
- **API Keys** - Manage AI provider keys (ADR-031)

**⚠️ Important:** Many admin commands require authentication and are destructive. Use with caution in production.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `status` | Show system status (Docker, database, environment) | [↓](#status) |
| `backup` | Create a database backup | [↓](#backup) |
| `list-backups` | List available backup files | [↓](#list-backups) |
| `restore` | Restore a database backup | [↓](#restore) |
| `reset` | Reset database (DESTRUCTIVE) | [↓](#reset) |
| `scheduler` | Job scheduler management | [↓](#scheduler) |
| `regenerate-embeddings` | Regenerate embeddings for concepts | [↓](#regenerate-embeddings) |
| `user` | User management commands | [↓](#user) |
| `rbac` | Manage roles, permissions, access control | [↓](#rbac) |
| `embedding` | Manage embedding model configuration | [↓](#embedding) |
| `extraction` | Manage AI extraction model configuration | [↓](#extraction) |
| `keys` | Manage API keys for AI providers | [↓](#keys) |

## Command Tree

```
kg admin
├── status
├── backup
├── list-backups
├── restore
├── reset
├── scheduler
│   ├── status
│   └── cleanup
├── regenerate-embeddings
├── user
│   ├── list
│   ├── get <user_id>
│   ├── create <username>
│   ├── update <user_id>
│   └── delete <user_id>
├── rbac
│   ├── resource (resources)
│   ├── role (roles)
│   ├── permission (permissions)
│   └── assign
├── embedding
│   ├── list
│   ├── create
│   ├── activate <config-id>
│   ├── reload
│   ├── protect <config-id>
│   ├── unprotect <config-id>
│   └── delete <config-id>
├── extraction
│   ├── config
│   └── set
└── keys
    ├── list
    ├── set <provider>
    └── delete <provider>
```

---

## Subcommand Details

### status

Show comprehensive system status including Docker, database, and environment.

**Usage:**
```bash
kg admin status [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Docker Status**
   - PostgreSQL container state
   - Container health
   - Uptime

2. **Database Connection**
   - Connection status
   - Database URI
   - Version information

3. **Database Statistics**
   - Concept count
   - Source count
   - Instance count
   - Relationship count

4. **Python Environment**
   - Virtual environment status
   - Python version

5. **Configuration**
   - .env file status
   - API key configuration status
   - Access credentials

**Examples:**

```bash
# Check system status
kg admin status
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📊 System Status
────────────────────────────────────────────────────────────────────────────────

Docker
  ✓ PostgreSQL container running
    Container: knowledge-graph-postgres
    Status: Up 5 hours (healthy)

Database Connection
  ✓ Connected to PostgreSQL + AGE
    URI: postgresql://localhost:5432/knowledge_graph

Database Statistics
  Concepts: 1,234
  Sources: 45
  Instances: 2,456
  Relationships: 3,567

Python Environment
  ✓ Virtual environment exists
    Version: Python 3.11.5

Configuration
  ✓ .env file exists
    ANTHROPIC_API_KEY: configured
    OPENAI_API_KEY: configured

Access Points
  PostgreSQL: postgresql://localhost:5432/knowledge_graph
  Credentials: admin/password

────────────────────────────────────────────────────────────────────────────────
```

**Use Cases:**

- **Health Check** - Verify all components are running
- **Troubleshooting** - Diagnose system issues
- **Monitoring** - Regular status checks
- **Documentation** - Capture environment details

---

### backup

Create a full system backup or per-ontology backup.

**Usage:**
```bash
kg admin backup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Backup type: "full" or "ontology" | - |
| `--ontology <name>` | Ontology name (required if type is ontology) | - |
| `--output <filename>` | Custom output filename | auto-generated |
| `--format <format>` | Export format: "json" (restorable) or "gexf" (visualization) | `json` |
| `-h, --help` | Display help for command | - |

**Backup Types:**

**Full Backup:**
- All ontologies
- All concepts, sources, instances
- All relationships
- Vocabulary metadata
- User data (if multi-tenant)

**Ontology Backup:**
- Single ontology
- All concepts in ontology
- All sources in ontology
- All relationships involving concepts
- Portable across systems

**Export Formats:**

**JSON (default):**
- Native format
- Restorable with `kg admin restore`
- Includes all metadata
- Human-readable

**GEXF:**
- Gephi-compatible
- Visualization only (not restorable)
- Graph structure
- Node/edge attributes

**Examples:**

```bash
# Full system backup
kg admin backup --type full

# Ontology backup
kg admin backup --type ontology --ontology "Research Papers"

# Custom filename
kg admin backup --type full --output backup-prod-2024-01-15.json

# Export for Gephi visualization
kg admin backup --type ontology \
  --ontology "Project Docs" \
  --format gexf \
  --output project-graph.gexf
```

**Output Example:**

```
Creating backup...
  Type: full
  Format: json

Progress:
  ✓ Exporting concepts (1,234)
  ✓ Exporting sources (45)
  ✓ Exporting instances (2,456)
  ✓ Exporting relationships (3,567)
  ✓ Exporting vocabulary (55 types)
  ✓ Writing backup file

Backup created successfully:
  File: /backups/kg-backup-full-20240115-143022.json
  Size: 15.2 MB
  Duration: 8.3s
```

**Use Cases:**

- **Disaster Recovery** - Regular full backups
- **Migration** - Move ontologies between systems
- **Archiving** - Snapshot ontologies before major changes
- **Visualization** - Export to Gephi for analysis
- **Development** - Backup before testing

---

### list-backups

List all available backup files in the configured backup directory.

**Usage:**
```bash
kg admin list-backups [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**Examples:**

```bash
# List backups
kg admin list-backups
```

**Output Example:**

```
📁 Available Backups

────────────────────────────────────────────────────────────────────────────────
FILENAME                                    TYPE         SIZE       DATE
────────────────────────────────────────────────────────────────────────────────
kg-backup-full-20240115-143022.json        full         15.2 MB    2024-01-15 14:30
kg-backup-ontology-Research-20240114.json  ontology     2.1 MB     2024-01-14 09:15
kg-backup-full-20240110-080000.json        full         14.8 MB    2024-01-10 08:00
────────────────────────────────────────────────────────────────────────────────

3 backup files found
Total size: 32.1 MB
```

---

### restore

Restore a database backup (full or ontology).

**Usage:**
```bash
kg admin restore [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--file <name>` | Backup filename (from configured directory) | - |
| `--path <path>` | Custom backup file path (overrides directory) | - |
| `--merge` | Merge into existing ontology if it exists | error if exists |
| `--deps <action>` | Handle external dependencies: prune, stitch, defer | `prune` |
| `-h, --help` | Display help for command | - |

**Dependency Handling** (ADR-036):

**prune:**
- Remove relationships to concepts outside backup
- Clean, self-contained ontology
- Recommended for most cases

**stitch:**
- Try to reconnect to existing concepts
- Match by label/embedding similarity
- May create unintended connections

**defer:**
- Store references, reconnect later
- Requires manual resolution
- Advanced use case

**Examples:**

```bash
# Restore from configured directory
kg admin restore --file kg-backup-full-20240115-143022.json

# Restore from custom path
kg admin restore --path /tmp/backup.json

# Merge into existing ontology
kg admin restore --file ontology-backup.json --merge

# Restore with dependency stitching
kg admin restore --file backup.json --deps stitch
```

**Output Example:**

```
⚠ WARNING: This will restore data to the database.

Backup file: kg-backup-full-20240115-143022.json
Type: full
Size: 15.2 MB

This will:
  - Import 1,234 concepts
  - Import 45 sources
  - Import 2,456 instances
  - Import 3,567 relationships
  - Overwrite existing ontologies (if conflicts)

Type 'RESTORE' to confirm:
```

**After Confirmation:**

```
Restoring backup...
  ✓ Validated backup file
  ✓ Imported concepts (1,234)
  ✓ Imported sources (45)
  ✓ Imported instances (2,456)
  ✓ Imported relationships (3,567)
  ✓ Updated vocabulary

Restore completed successfully
Duration: 12.5s

⚠ IMPORTANT: Restart API server to clear connection pools:
  ./scripts/stop-api.sh && ./scripts/start-api.sh
```

---

### reset

Reset database to baseline state. **DESTRUCTIVE OPERATION.**

**Usage:**
```bash
kg admin reset [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-logs` | Do not clear log files | clears logs |
| `--no-checkpoints` | Do not clear checkpoint files | clears checkpoints |
| `-h, --help` | Display help for command | - |

**What Gets Deleted:**

- **All concepts**
- **All sources**
- **All instances**
- **All relationships**
- **All ontologies**
- **All jobs**
- **Vocabulary metadata** (reset to builtins)
- **Log files** (unless --no-logs)
- **Checkpoint files** (unless --no-checkpoints)

**What's Preserved:**

- **Database schema** (tables, AGE graph)
- **Users** (authentication)
- **Configuration** (.env, API keys)
- **Migrations history**

**Examples:**

```bash
# Full reset
kg admin reset

# Reset without clearing logs
kg admin reset --no-logs

# Reset without clearing checkpoints
kg admin reset --no-checkpoints
```

**Interactive Confirmation:**

```
⚠ WARNING: This will DELETE ALL DATA from the database!

This action will:
  - Delete 1,234 concepts
  - Delete 45 sources
  - Delete 2,456 instances
  - Delete 3,567 relationships
  - Delete all jobs
  - Reset vocabulary to builtins
  - Clear log files
  - Clear checkpoint files

This action CANNOT be undone.

Type 'DELETE ALL DATA' to confirm:
```

**After Confirmation:**

```
Resetting database...
  ✓ Deleted all concepts
  ✓ Deleted all sources
  ✓ Deleted all instances
  ✓ Deleted all relationships
  ✓ Deleted all jobs
  ✓ Reset vocabulary
  ✓ Cleared logs
  ✓ Cleared checkpoints

Database reset complete

⚠ CRITICAL: Restart API server immediately:
  ./scripts/stop-api.sh && ./scripts/start-api.sh

Then re-initialize if needed:
  ./scripts/initialize-auth.sh
```

**⚠️ DANGER:** Always backup before resetting. This operation is irreversible.

---

### scheduler

Job scheduler management for background ingestion jobs.

**Usage:**
```bash
kg admin scheduler [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `status` | Show job scheduler status and configuration |
| `cleanup` | Manually trigger scheduler cleanup |

#### scheduler status

**Usage:**
```bash
kg admin scheduler status
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
⚙️ Job Scheduler Status
────────────────────────────────────────────────────────────────────────────────

Status
  Scheduler: ✓ Running
  Workers: 2 active
  Queue Depth: 3 pending jobs

Configuration
  Max Workers: 4
  Cleanup Interval: 3600s (1 hour)
  Job Timeout: 7200s (2 hours)
  Retention: 30 days

Active Jobs
  job_abc123: processing (chunk 3/5)
  job_def456: processing (chunk 1/8)

Recent Activity
  Completed: 45 jobs (last 24h)
  Failed: 2 jobs (last 24h)
  Cancelled: 1 job (last 24h)

────────────────────────────────────────────────────────────────────────────────
```

#### scheduler cleanup

Manually trigger scheduler cleanup to cancel expired jobs and delete old completed jobs.

**Usage:**
```bash
kg admin scheduler cleanup
```

**Output Example:**

```
Running scheduler cleanup...
  ✓ Cancelled 2 expired jobs
  ✓ Deleted 15 old completed jobs (>30 days)
  ✓ Deleted 3 old failed jobs (>30 days)

Cleanup complete
```

---

### regenerate-embeddings

Regenerate vector embeddings for concept nodes (useful after model changes).

**Usage:**
```bash
kg admin regenerate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--concepts` | Regenerate concept embeddings | `true` |
| `--only-missing` | Only generate for concepts without embeddings | `false` |
| `--ontology <name>` | Limit to specific ontology | all ontologies |
| `--limit <n>` | Maximum number to process (for testing) | unlimited |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Regenerate all concept embeddings
kg admin regenerate-embeddings

# Only generate missing
kg admin regenerate-embeddings --only-missing

# Limit to specific ontology
kg admin regenerate-embeddings --ontology "Research Papers"

# Test with limit
kg admin regenerate-embeddings --limit 100
```

**Output Example:**

```
Regenerating concept embeddings...

Scanning concepts...
  Total concepts: 1,234
  Will regenerate: 1,234

Progress:
  [████████████████████████████░░] 95% (1,173/1,234)
  Current: Transformer Architecture
  Rate: ~50 concepts/sec
  ETA: 1.2s

Completed:
  Generated: 1,234 embeddings
  Failed: 0
  Duration: 24.7s
  Cost: ~$0.15

✓ All concept embeddings regenerated
```

**Use Cases:**

- **Model Migration** - After switching embedding models
- **Consistency** - Fix corrupted embeddings
- **New Concepts** - Generate for concepts without embeddings
- **Quality Improvement** - Regenerate with better model

---

### user

User management commands (admin only).

**Usage:**
```bash
kg admin user [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `list` | List all users |
| `get <user_id>` | Get user details by ID |
| `create <username>` | Create new user |
| `update <user_id>` | Update user details |
| `delete <user_id>` | Delete user (requires re-authentication) |

#### user list

**Usage:**
```bash
kg admin user list [options]
```

**Output Example:**

```
📋 Users

────────────────────────────────────────────────────────────────────────────────
ID    USERNAME     EMAIL                  ROLE        STATUS    CREATED
────────────────────────────────────────────────────────────────────────────────
1     admin        admin@example.com      admin       active    2024-01-01
2     researcher   researcher@example.com editor      active    2024-01-10
3     viewer       viewer@example.com     viewer      active    2024-01-12
────────────────────────────────────────────────────────────────────────────────

3 users
```

#### user create

**Usage:**
```bash
kg admin user create [options] <username>
```

**Options:**
- `--email <email>` - User email
- `--role <role>` - User role (admin, editor, viewer)
- `--password <password>` - Initial password (prompted if omitted)

**Example:**
```bash
kg admin user create researcher \
  --email researcher@example.com \
  --role editor
```

---

### rbac

Manage role-based access control (ADR-028).

**Usage:**
```bash
kg admin rbac [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `resource` (resources) | Manage resource types |
| `role` (roles) | Manage roles |
| `permission` (permissions) | Manage permissions |
| `assign` | Assign roles to users |

**Example Usage:**

```bash
# List resources
kg admin rbac resource list

# List roles
kg admin rbac role list

# Assign role to user
kg admin rbac assign <user_id> <role_name>
```

---

### embedding

Manage embedding model configuration (ADR-039).

**Usage:**
```bash
kg admin embedding [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `list` | List all embedding configurations |
| `create` | Create new embedding configuration (inactive) |
| `activate <config-id>` | Activate an embedding configuration |
| `reload` | Hot reload embedding model (zero-downtime) |
| `protect <config-id>` | Enable protection flags |
| `unprotect <config-id>` | Disable protection flags |
| `delete <config-id>` | Delete embedding configuration |

**Examples:**

```bash
# List configurations
kg admin embedding list

# Create new configuration
kg admin embedding create \
  --provider openai \
  --model text-embedding-3-large

# Activate configuration
kg admin embedding activate config_123

# Hot reload (zero-downtime)
kg admin embedding reload
```

---

### extraction

Manage AI extraction model configuration (ADR-041).

**Usage:**
```bash
kg admin extraction [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `config` | Show current AI extraction configuration |
| `set` | Update AI extraction configuration |

**Examples:**

```bash
# Show current config
kg admin extraction config

# Update extraction model
kg admin extraction set \
  --provider anthropic \
  --model claude-sonnet-4

# Update OpenAI extraction
kg admin extraction set \
  --provider openai \
  --model gpt-4o
```

---

### keys

Manage API keys for AI providers (ADR-031, ADR-041).

**Usage:**
```bash
kg admin keys [options] [command]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `list` | List API keys with validation status |
| `set <provider>` | Set API key for a provider |
| `delete <provider>` | Delete API key for a provider |

**Examples:**

```bash
# List keys
kg admin keys list

# Set OpenAI key
kg admin keys set openai --key sk-...

# Set Anthropic key
kg admin keys set anthropic --key sk-ant-...

# Delete key
kg admin keys delete openai
```

**Output Example (list):**

```
🔑 API Keys

────────────────────────────────────────────────────────────────────────────────
PROVIDER     STATUS       LAST VALIDATED
────────────────────────────────────────────────────────────────────────────────
openai       ✓ Valid      2024-01-15 14:30
anthropic    ✓ Valid      2024-01-15 14:30
ollama       ✗ Not set    -
────────────────────────────────────────────────────────────────────────────────
```

---

## Common Use Cases

### System Health Check

```bash
# Full status
kg admin status

# Check scheduler
kg admin scheduler status

# Check database
kg database health
```

### Backup Before Major Operation

```bash
# Backup everything
kg admin backup --type full

# List backups
kg admin list-backups

# Proceed with operation
kg admin reset
```

### Migration to New System

```bash
# On old system: backup
kg admin backup --type full --output migration.json

# Transfer file to new system

# On new system: restore
kg admin restore --path /path/to/migration.json
```

### Model Configuration Change

```bash
# Check current config
kg admin extraction config
kg admin embedding list

# Update extraction model
kg admin extraction set --provider anthropic --model claude-sonnet-4

# Update embedding model
kg admin embedding activate new_config_id
kg admin embedding reload

# Regenerate embeddings
kg admin regenerate-embeddings
```

### Clean Development Environment

```bash
# Reset database
kg admin reset

# Verify clean state
kg database stats

# Re-initialize
./scripts/initialize-auth.sh
```

---

## Safety and Best Practices

### Before Destructive Operations

1. **Backup First**
   ```bash
   kg admin backup --type full
   kg admin list-backups  # Verify backup created
   ```

2. **Verify Environment**
   ```bash
   kg admin status
   # Make sure you're on the correct environment
   ```

3. **Check Dependencies**
   - Are there active users?
   - Are jobs running?
   - Is this production?

### After Database Changes

**Always restart API server:**
```bash
./scripts/stop-api.sh
./scripts/start-api.sh
```

**Why?** Connection pools become stale after:
- Database reset
- Database restore
- Schema changes

### Regular Maintenance

```bash
# Weekly: Check scheduler
kg admin scheduler status
kg admin scheduler cleanup

# Monthly: Backup
kg admin backup --type full

# Quarterly: Check user access
kg admin user list
kg admin rbac role list
```

---

## Troubleshooting

### Restore Fails

**Symptom:**
```bash
kg admin restore --file backup.json
# Error: Incompatible backup version
```

**Causes & Solutions:**

1. **Old backup format** - Backup from older version
   - Upgrade backup format (future feature)
   - Or re-ingest documents

2. **Corrupted backup** - File damaged
   ```bash
   # Verify JSON validity
   jq . backup.json > /dev/null
   ```

3. **Insufficient permissions**
   ```bash
   # Check file permissions
   ls -l backup.json
   ```

### Reset Hangs

**Symptom:**
```bash
kg admin reset
# Hangs after confirmation
```

**Cause:** Active connections preventing deletion

**Solution:**
```bash
# Stop API server first
./scripts/stop-api.sh

# Then reset
kg admin reset

# Restart API
./scripts/start-api.sh
```

### Scheduler Not Processing Jobs

**Symptom:**
```bash
kg admin scheduler status
# Workers: 0 active
```

**Solutions:**

1. **Restart API**
   ```bash
   ./scripts/stop-api.sh
   ./scripts/start-api.sh
   ```

2. **Check logs**
   ```bash
   tail -f logs/api_*.log | grep scheduler
   ```

3. **Manual cleanup**
   ```bash
   kg admin scheduler cleanup
   ```

---

## Related Commands

- [`kg database`](../database/) - Database statistics and health
- [`kg job`](../job/) - Job management
- [`kg ontology`](../ontology/) - Ontology management
- [`kg vocabulary`](../vocabulary/) - Vocabulary management

---

## See Also

- [ADR-014: Job Approval Workflow](../../../architecture/ADR-014-job-approval-workflow.md)
- [ADR-028: RBAC Implementation](../../../architecture/ADR-028-role-based-access-control.md)
- [ADR-031: API Key Management](../../../architecture/ADR-031-api-key-management.md)
- [ADR-036: Backup & Restore](../../../architecture/ADR-036-backup-restore-system.md)
- [ADR-039: Embedding Configuration](../../../architecture/ADR-039-embedding-model-configuration.md)
- [ADR-041: Extraction Configuration](../../../architecture/ADR-041-extraction-model-configuration.md)
- [System Administration Guide](../../05-maintenance/administration.md)
- [Troubleshooting](../../05-maintenance/troubleshooting.md)
