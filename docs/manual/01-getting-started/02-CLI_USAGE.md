# kg CLI Usage Guide

> **Purpose:** Comprehensive guide to all CLI commands, usage patterns, and command-line interface design.

## Command Structure Overview

The `kg` CLI provides two complementary command styles (ADR-029):

1. **Domain-Noun Commands** (Primary): `kg <noun> <verb>` - e.g., `kg job list`, `kg ontology delete "Name"`
2. **Unix-Verb Shortcuts** (Secondary): `kg <verb> <noun>` - e.g., `kg ls job`, `kg rm ontology "Name"`

Both styles delegate to the same underlying commands and produce identical results.

### Command Syntax

```
kg [global-options] <command> [subcommand] [options] [arguments]
```

### Global Options
- `--api-url <url>` - Override API base URL (default: http://localhost:8000)
- `--client-id <id>` - Client ID for multi-tenancy (env: KG_CLIENT_ID)

### Command Naming Convention

Commands use **singular** names with optional **aliases** for convenience:

- `kg job` (alias: `jobs`) - Manage ingestion jobs
- `kg ontology` (alias: `onto`) - Manage ontologies
- `kg database` (alias: `db`) - Database operations
- `kg config` (alias: `cfg`) - Configuration management

**Examples:**
```bash
kg job list          # Singular (primary)
kg jobs list         # Plural alias (backward compatible)
kg onto list         # Short alias
```

### User-Configurable Aliases (ADR-029)

Users can define custom command aliases in their config:

```bash
kg config set aliases.cat '["bat"]'
```

This allows `kg bat config` to work alongside `kg cat config` for users with shell conflicts.

---

## Unix Verb Router (ADR-029)

Unix-style shortcuts for common operations:

### `kg ls <resource>`
List resources using Unix-familiar syntax.

**Examples:**
```bash
kg ls job              # → kg job list
kg ls ontology         # → kg ontology list
kg ls backup           # → kg admin list-backups
```

### `kg cat <resource> [id]`
Display resource details (like Unix `cat`).

**Examples:**
```bash
kg cat config          # → kg config list (show all config)
kg cat config api_url  # → kg config get api_url
kg cat job             # → kg job list (show all jobs)
kg cat job job_xyz     # → kg job status job_xyz
kg cat concept abc-123 # → kg search details abc-123
```

### `kg rm <resource> <id>`
Remove or delete resources.

**Examples:**
```bash
kg rm job job_abc          # → kg job cancel job_abc
kg rm ontology "My Docs"   # → kg ontology delete "My Docs"
```

### `kg stat <resource> [id]`
Show status or statistics.

**Examples:**
```bash
kg stat database       # → kg database stats
kg stat job job_abc    # → kg job status job_abc
```

---

## 1. Health Command

**Command:** `kg health`

**Purpose:** Check API server health

**States:**
- ✅ API healthy → display health info + API info
- ❌ API unhealthy → error message, exit(1)

**Flow:**
```
kg health
  → GET /health
  → GET /info
  → Display results
```

---

## 2. Config Commands

**Command:** `kg config <subcommand>` (alias: `cfg`)

**Unix Shortcuts:**
```bash
kg cat config          # List all config (→ kg config list)
kg cat config api_url  # Show specific key (→ kg config get api_url)
```

### 2.1 `kg config get [key]`

**Purpose:** Get configuration value(s)

**Options:**
- `--json` - Output as JSON

**States:**
- No key → Show all config (formatted or JSON)
- With key → Show specific key value
- Key not found → Error, exit(1)

**Flow:**
```
kg config get
  → Load ~/.kg/config.json
  → Display all config

kg config get username
  → Load config
  → Get "username" value
  → Display
```

### 2.2 `kg config set <key> <value>`

**Purpose:** Set configuration value

**Options:**
- `--json` - Force parse value as JSON
- `--string` - Force treat value as string (no JSON parsing)

**Auto-Detection:**
- Values starting with `[` or `{` are automatically parsed as JSON
- Values `true`/`false` are parsed as booleans
- Numeric values are parsed as numbers
- Other values are stored as strings

**States:**
- Valid key/value → Set and confirm
- Invalid JSON (with --json flag or auto-detected) → Error, exit(1)

**Flow:**
```
kg config set username alice
  → Load config
  → Auto-detect: string value
  → Set username = "alice"
  → Save config
  → Confirm

kg config set aliases.cat '["bat"]'
  → Auto-detect: JSON array (starts with [)
  → Parse as JSON
  → Set aliases.cat = ["bat"]
  → Save config
```

### 2.3 `kg config delete <key>`

**Purpose:** Delete configuration key

**States:**
- Key exists → Delete and confirm
- Key doesn't exist → Still succeeds (idempotent)

### 2.4 `kg config list`

**Purpose:** List all configuration

**Options:**
- `--json` - Output as JSON

**States:**
- Has config → Display formatted list
- Empty config → Display empty structure

### 2.5 `kg config path`

**Purpose:** Show configuration file path

**States:**
- Always succeeds → Display path

### 2.6 `kg config init`

**Purpose:** Initialize configuration file with defaults

**Options:**
- `-f, --force` - Overwrite existing

**States:**
- No config → Create with defaults
- Config exists, no --force → Warning, exit(0)
- Config exists, with --force → Overwrite with defaults

### 2.7 `kg config reset`

**Purpose:** Reset configuration to defaults

**Options:**
- `-y, --yes` - Skip confirmation

**States:**
- With --yes → Reset immediately
- Without --yes → Prompt for confirmation
  - User confirms (y) → Reset
  - User cancels (n/other) → Exit(0)

### 2.8 `kg config auto-approve [value]`

**Purpose:** Enable/disable auto-approval of jobs (ADR-014)

**States:**
- No value → Show current status
- Value = true/on/yes/enable/enabled/1 → Enable auto-approve
- Value = false/off/no/disable/disabled/0 → Disable auto-approve
- Invalid value → Error, exit(1)

### 2.9 `kg config enable-mcp <tool>`

**Purpose:** Enable an MCP tool

### 2.10 `kg config disable-mcp <tool>`

**Purpose:** Disable an MCP tool

### 2.11 `kg config mcp [tool]`

**Purpose:** Show MCP tool configuration

**Options:**
- `--json` - Output as JSON

### 2.12 `kg config update-secret`

**Purpose:** Authenticate and update API secret/key

**Options:**
- `-u, --username <username>` - Username

**States:**
- ⚠️ **NOT IMPLEMENTED** - Placeholder only

---

## 3. Ingest Commands

**Command:** `kg ingest <subcommand>`

### 3.1 `kg ingest file <path>`

**Purpose:** Ingest a document file

**Options:**
- `-o, --ontology <name>` - **REQUIRED** - Ontology/collection name
- `-f, --force` - Force re-ingestion even if duplicate (default: false)
- `-y, --yes` - Auto-approve job, skip approval step (default: false)
- `--filename <name>` - Override filename for tracking
- `--target-words <n>` - Target words per chunk (default: 1000)
- `--overlap-words <n>` - Overlap between chunks (default: 200)
- `--no-wait` - Submit and exit (don't wait for completion)

**States:**
1. File validation
   - File not found → Error, exit(1)
   - File exists → Continue

2. Job submission
   - Duplicate detected → Show duplicate info, exit(0)
   - New job → Submit job

3. Wait behavior
   - With --wait (default) → Poll job with progress
   - With --no-wait → Return immediately with job ID

**Flow:**
```
kg ingest file doc.txt -o "My Ontology"
  → Validate file exists
  → POST /ingest (multipart/form-data)
  → Check for duplicate
    → If duplicate: Display info, exit
    → If new: Continue
  → If --wait (default):
      → Poll job with progress spinner
      → Display final result
  → If --no-wait:
      → Display job ID and exit immediately
```

### 3.2 `kg ingest text <text>`

**Purpose:** Ingest raw text

**Options:**
- `-o, --ontology <name>` - **REQUIRED**
- `-f, --force` - Force re-ingestion
- `-y, --yes` - Auto-approve job
- `--filename <name>` - Filename for tracking (default: "text_input")
- `--target-words <n>` - Target words per chunk (default: 1000)
- `--no-wait` - Submit and exit

**States:**
- Same as `kg ingest file` above

---

## 4. Job Commands

**Command:** `kg job <subcommand>` (alias: `jobs`)

**Unix Shortcuts:**
```bash
kg cat job             # List all jobs (→ kg job list)
kg cat job <id>        # Show job status (→ kg job status <id>)
kg ls job              # List all jobs (→ kg job list)
kg stat job <id>       # Show job status (→ kg job status <id>)
kg rm job <id>         # Cancel job (→ kg job cancel <id>)
```

### 4.1 `kg job status <job-id>`

**Purpose:** Get job status

**Options:**
- `-w, --watch` - Watch job until completion

**States:**
- Job found, no --watch → Display status once
- Job found, with --watch → Poll until completion
- Job not found → Error, exit(1)

**Flow:**
```
kg job status job_123 --watch
  → GET /jobs/{job_id}
  → Poll every 2s until status ∈ {completed, failed, cancelled}
  → Display progress in real-time
  → Display final result
```

### 4.2 `kg job list`

**Purpose:** List recent jobs

**Options:**
- `-s, --status <status>` - Filter by status
- `-c, --client <client-id>` - Filter by client ID
- `-l, --limit <n>` - Maximum jobs to return (default: 20)

**States:**
- No jobs → "No jobs found"
- Has jobs → Display table

**Flow:**
```
kg job list
  → GET /jobs?limit=20
  → Build table with columns:
      [Job ID, Client, Status, Ontology, Created, Progress]
  → Display table
```

### 4.3 `kg job list pending`

**Purpose:** List jobs awaiting approval

**Options:**
- `-c, --client <client-id>`
- `-l, --limit <n>` (default: 20)

### 4.4 `kg job list approved`

**Purpose:** List approved jobs (queued or processing)

### 4.5 `kg job list done`

**Purpose:** List completed jobs

### 4.6 `kg job list failed`

**Purpose:** List failed jobs

### 4.7 `kg job list cancelled`

**Purpose:** List cancelled jobs

### 4.8 `kg job approve <job-id-or-filter>`

**Purpose:** Approve a job or all jobs matching filter

**Options:**
- `-c, --client <client-id>` - Filter by client ID (for batch operations)

**States:**
- Starts with "job_" → Single job approval
  - Job found → Approve, display status
  - Job not found → Error, exit(1)
- Filter keyword (pending, awaiting, approved, etc.) → Batch approval
  - Find jobs matching filter
  - Approve each job
  - Display summary (approved count, failed count)

### 4.9 `kg job cancel <job-id-or-filter>`

**Purpose:** Cancel a job or all jobs matching filter

**Options:**
- `-c, --client <client-id>` - Filter by client ID

**States:**
- Same pattern as approve above

---

## 5. Search Commands

**Command:** `kg search <subcommand>`

### 5.1 `kg search query <query>`

**Purpose:** Search for concepts using natural language

**Arguments:**
- `<query>` - Search query text

**Options:**
- `-l, --limit <number>` - Maximum results (default: 10)
- `--min-similarity <number>` - Minimum similarity score 0.0-1.0 (default: 0.7)

**States:**
- Results found → Display list with scores
- No results → Display "Found 0 concepts"

**Flow:**
```
kg search query "recursive thinking"
  → POST /search/concepts
      { query: "recursive thinking", limit: 10, min_similarity: 0.7 }
  → Display results with:
      - Concept label
      - ID
      - Similarity score (colored)
      - Documents
      - Evidence count
```

### 5.2 `kg search details <concept-id>`

**Purpose:** Get detailed information about a concept

**Arguments:**
- `<concept-id>` - Concept ID to retrieve

**States:**
- Concept found → Display full details
- Concept not found → Error, exit(1)

**Flow:**
```
kg search details concept_abc123
  → GET /concepts/{concept_id}
  → Display:
      - Label, ID, search terms
      - Evidence instances (quotes)
      - Relationships
```

### 5.3 `kg search related <concept-id>`

**Purpose:** Find concepts related through graph traversal

**Arguments:**
- `<concept-id>` - Starting concept ID

**Options:**
- `-d, --depth <number>` - Maximum traversal depth 1-5 (default: 2)
- `-t, --types <types...>` - Filter by relationship types

**States:**
- Related concepts found → Display grouped by distance
- No related concepts → Display "Found 0 concepts"

**Flow:**
```
kg search related concept_abc123 --depth 3
  → POST /search/related
      { concept_id: "concept_abc123", max_depth: 3 }
  → Display results grouped by distance:
      Distance 1:
        • Concept A (path: IMPLIES)
      Distance 2:
        • Concept B (path: IMPLIES → SUPPORTS)
```

### 5.4 `kg search connect <from> <to>`

**Purpose:** Find shortest path between two concepts

**Arguments:**
- `<from>` - Starting concept (ID or search phrase)
- `<to>` - Target concept (ID or search phrase)

**Options:**
- `--max-hops <number>` - Maximum path length (default: 5)

**States:**
- Auto-detection:
  - Contains `-` or `_` → Treat as concept ID
  - Otherwise → Treat as natural language query
- Both IDs → Use ID-based search (POST /search/connect)
- At least one query → Use search-based (POST /search/connect-by-search)
- Path found → Display all paths with hops
- No path found → "No connection found within N hops"

**Flow:**
```
kg search connect "linear thinking" "recursive depth"
  → Auto-detect: both are queries (no hyphens)
  → POST /search/connect-by-search
      { from_query: "linear thinking", to_query: "recursive depth", max_hops: 5 }
  → Match concepts
  → Find paths
  → Display paths with relationships
```

---

## 6. Database Commands

**Command:** `kg database <subcommand>` (alias: `kg db`)

### 6.1 `kg database stats`

**Purpose:** Show database statistics

**States:**
- Connected → Display stats
  - Nodes (Concepts, Sources, Instances)
  - Relationships (Total, By Type)
- Not connected → Error, exit(1)

**Flow:**
```
kg database stats
  → GET /database/stats
  → Display:
      Nodes:
        Concepts: 150
        Sources: 45
        Instances: 320
      Relationships:
        Total: 89
        By Type:
          IMPLIES: 30
          SUPPORTS: 25
          ...
```

### 6.2 `kg database info`

**Purpose:** Show database connection information

**States:**
- Connected → Display connection details (URI, user, version, edition)
- Not connected → Display error details

### 6.3 `kg database health`

**Purpose:** Check database health and connectivity

**States:**
- Healthy → Display "✓ HEALTHY"
- Degraded → Display "⚠ DEGRADED" with warnings
- Unhealthy → Display "✗ UNHEALTHY" with errors

---

## 7. Ontology Commands

**Command:** `kg ontology <subcommand>` (alias: `onto`)

### 7.1 `kg ontology list`

**Purpose:** List all ontologies

**States:**
- No ontologies → "⚠ No ontologies found"
- Has ontologies → Display list with stats
  - Files, Chunks, Concepts per ontology

### 7.2 `kg ontology info <name>`

**Purpose:** Get detailed information about an ontology

**Arguments:**
- `<name>` - Ontology name

**States:**
- Ontology found → Display full info
  - Statistics (files, chunks, concepts, evidence, relationships)
  - File list
- Ontology not found → Error, exit(1)

### 7.3 `kg ontology files <name>`

**Purpose:** List files in an ontology

**Arguments:**
- `<name>` - Ontology name

**States:**
- Files found → Display list with counts (chunks, concepts per file)
- No files → "No files found"

### 7.4 `kg ontology delete <name>`

**Purpose:** Delete an ontology and all its data

**Arguments:**
- `<name>` - Ontology name

**Options:**
- `-f, --force` - Skip confirmation and force deletion

**States:**
- No --force → Display warning and require --force flag, exit(0)
- With --force → Delete and display results
  - Sources deleted count
  - Orphaned concepts cleaned count

**Flow:**
```
kg ontology delete "Test Ontology"
  → Display warning
  → Exit (requires --force)

kg ontology delete "Test Ontology" --force
  → DELETE /ontology/{name}?force=true
  → Display deletion results
```

---

## 8. Admin Commands

**Command:** `kg admin <subcommand>`

### 8.1 `kg admin status`

**Purpose:** Show system status (Docker, database, environment)

**States:**
- All components healthy → Display all green ✓
- Some components unhealthy → Display mixed status

**Flow:**
```
kg admin status
  → GET /admin/system-status
  → Display:
      Docker:
        ✓ PostgreSQL container running
      Database Connection:
        ✓ Connected to PostgreSQL + AGE
      Database Statistics:
        Concepts: 150, Sources: 45, ...
      Python Environment:
        ✓ Virtual environment exists
      Configuration:
        ✓ .env file exists
        ✓ ANTHROPIC_API_KEY: configured
```

### 8.2 `kg admin backup`

**Purpose:** Create a database backup

**Options:**
- `--type <type>` - Backup type: "full" or "ontology"
- `--ontology <name>` - Ontology name (required if type is ontology)
- `--output <filename>` - Custom output filename

**States:**
- Interactive mode (no options):
  - Prompt: "1) Full database backup" or "2) Specific ontology backup"
  - If ontology: Prompt for ontology name
- Non-interactive mode:
  - Validate options
  - Download backup

**Flow:**
```
kg admin backup --type full
  → POST /admin/backup
      { backup_type: "full" }
  → Download with progress bar
  → Save to configured backup directory
  → Display results (filename, path, size)
```

### 8.3 `kg admin list-backups`

**Purpose:** List available backup files from configured directory

**States:**
- Backup dir doesn't exist → Display message
- No backups → Display "No backups found"
- Has backups → Display list (newest first)
  - Filename, size, created date

### 8.4 `kg admin restore`

**Purpose:** Restore a database backup (requires authentication)

**Options:**
- `--file <name>` - Backup filename (from configured directory)
- `--path <path>` - Custom backup file path
- `--overwrite` - Overwrite existing data (default: false)
- `--deps <action>` - Handle external dependencies: prune, stitch, defer (default: prune)

**States:**
1. File selection:
   - --path → Use custom path
   - --file → Use configured directory + filename
   - Neither → Interactive selection from configured directory

2. File validation:
   - File not found → Error, exit(1)
   - File exists → Continue

3. Authentication:
   - Get username from config or prompt
   - Prompt for password (hidden input)
   - Username not configured → Error, exit(1)
   - No password → Error, exit(1)

4. Upload backup:
   - Upload with progress bar
   - Display backup stats if available
   - Display integrity warnings if any

5. Restore job tracking (ADR-018):
   - Try SSE streaming for real-time progress
   - Fall back to polling if SSE fails
   - Display multi-line progress bars for stages:
     - Creating checkpoint backup
     - Loading backup file
     - Restoring concepts
     - Restoring sources
     - Restoring instances
     - Restoring relationships

6. Final status:
   - Completed → Display restore statistics
   - Failed → Display error, check rollback

**Flow:**
```
kg admin restore --file backup_2024-10-09.json
  → Validate file exists
  → Prompt for authentication
  → POST /admin/restore (multipart/form-data)
      + username, password, overwrite, deps
  → Upload with progress
  → Get job_id
  → Track job with SSE (or polling fallback)
  → Display multi-line progress
  → Display final results
```

### 8.5 `kg admin reset`

**Purpose:** Reset database - DESTRUCTIVE (requires authentication)

**Options:**
- `--no-logs` - Do not clear log files
- `--no-checkpoints` - Do not clear checkpoint files

**States:**
1. Confirmation:
   - Prompt user to type "yes" to confirm
   - User types "yes" → Continue
   - User types anything else → Exit(0)

2. Authentication:
   - Get username from config
   - Prompt for password
   - Validate inputs

3. Reset operation:
   - Displays schema validation results
   - Displays warnings if any

**Flow:**
```
kg admin reset
  → Display warnings
  → Prompt: Type "yes" to confirm
  → POST /admin/reset
      { username, password, confirm: true, clear_logs, clear_checkpoints }
  → Display schema validation
  → Display warnings
```

### 8.6 `kg admin scheduler status`

**Purpose:** Show job scheduler status and configuration

**States:**
- Scheduler running → Display "✓ Running"
- Scheduler not running → Display "✗ Not running"

**Flow:**
```
kg admin scheduler status
  → GET /admin/scheduler/status
  → Display:
      Scheduler: ✓ Running
      Configuration:
        Cleanup Interval: 3600s (1.0h)
        Approval Timeout: 24h
        ...
      Job Statistics:
        awaiting_approval: 2
        completed: 50
        ...
```

### 8.7 `kg admin scheduler cleanup`

**Purpose:** Manually trigger scheduler cleanup

**Flow:**
```
kg admin scheduler cleanup
  → POST /admin/scheduler/cleanup
  → Display cleanup results
```

---

## 9. Authentication Commands

> **Note:** Detailed authentication documentation is in [01-AUTHENTICATION.md](../04-security-and-access/01-AUTHENTICATION.md) (ADR-054: OAuth 2.0)

The Knowledge Graph System uses OAuth 2.0 client credentials for authentication. All authenticated commands automatically handle token refresh.

### 9.1 `kg login`

**Command:** `kg login [options]`

**Purpose:** Authenticate and create personal OAuth client credentials

**Options:**
- `-u, --username <username>` - Username (will prompt if not provided)

**Flow:**
```
kg login
  → Prompt for username (if not provided or saved)
  → Prompt for password (hidden input)
  → POST /auth/oauth/clients/personal
  → Save OAuth client credentials to ~/.kg/config.json
  → Display success message with client info
```

**What it does:**
- Authenticates with username/password
- Creates a long-lived OAuth client (client_id + client_secret)
- Stores OAuth credentials locally (NOT the password)
- Future API requests use OAuth client credentials grant

**Example:**
```bash
kg login

# Output:
# Username: admin
# Password: ********
#
# ✓ Creating personal OAuth client credentials...
# ✓ Login successful
#
# Logged in as: admin (role: admin)
# OAuth Client: kg-cli-admin-20251102
# Scopes: read:*, write:*
```

### 9.2 `kg logout`

**Command:** `kg logout [options]`

**Purpose:** Revoke OAuth client and clear credentials

**Options:**
- `--forget` - Also forget saved username

**Flow:**
```
kg logout
  → Get OAuth client credentials from config
  → DELETE /auth/oauth/clients/personal/{client_id}
  → Remove OAuth credentials from config
  → Display success message
```

**What it does:**
- Revokes the OAuth client at the server (invalidates credentials)
- Clears local OAuth credentials from config
- Optionally clears saved username (with `--forget`)

**Example:**
```bash
kg logout

# Output:
# ✓ OAuth client revoked
# ✓ Logged out successfully
```

### 9.3 `kg oauth` - OAuth Client Management

**Command:** `kg oauth <subcommand>`

**Purpose:** Manage personal OAuth clients (list, create for MCP, revoke)

#### 9.3.1 `kg oauth clients` (alias: `kg oauth list`)

**Purpose:** List all personal OAuth clients

**Flow:**
```
kg oauth clients
  → GET /auth/oauth/clients/personal
  → Display table of OAuth clients
```

**Example:**
```bash
kg oauth clients

# Output:
# Personal OAuth Clients
#
# Client ID                 Name                 Scopes          Created              Status
# ────────────────────────────────────────────────────────────────────────────────────────────
# kg-cli-admin-20251102     kg CLI (admin)       read:*, write:* 2 hours ago          ✓ Active
# kg-mcp-server-admin       kg MCP Server (a...  read:*, write:* 1 day ago            ✓ Active
```

#### 9.3.2 `kg oauth create-mcp`

**Purpose:** Create OAuth client for MCP server and display ready-to-paste config

**Options:**
- `--name <name>` - Custom client name (default: "kg MCP Server (username)")

**Flow:**
```
kg oauth create-mcp
  → POST /auth/oauth/clients/personal/new
  → Display OAuth credentials
  → Display Claude Desktop config (ready to paste)
  → Display claude CLI command
```

**Example:**
```bash
kg oauth create-mcp

# Output:
# 🔐 Creating OAuth client for MCP server...
#
# ✅ OAuth client created successfully!
#
# ════════════════════════════════════════════════════════════════════════════════
# CLAUDE DESKTOP CONFIG
# ════════════════════════════════════════════════════════════════════════════════
#
# Add this to your Claude Desktop config:
#
#   "knowledge-graph": {
#     "command": "kg-mcp-server",
#     "env": {
#       "KG_OAUTH_CLIENT_ID": "kg-mcp-server-admin-20251102",
#       "KG_OAUTH_CLIENT_SECRET": "oauth_secret_abc123...",
#       "KG_API_URL": "http://localhost:8000"
#     }
#   }
#
# ⚠️  IMPORTANT:
#   • Keep these credentials secure!
#   • Client secret is shown only once
#   • To revoke: kg oauth revoke kg-mcp-server-admin-20251102
```

#### 9.3.3 `kg oauth revoke <client-id>`

**Purpose:** Revoke an OAuth client

**Options:**
- `--force` - Force revocation even if it's your current CLI client

**Flow:**
```
kg oauth revoke <client-id>
  → Check if revoking current CLI client
  → DELETE /auth/oauth/clients/personal/{client_id}
  → Display success message
  → If current CLI client: clear config and logout
```

**Example:**
```bash
# Revoke MCP server client
kg oauth revoke kg-mcp-server-admin-20251102

# Output:
# 🗑️  Revoking OAuth client kg-mcp-server-admin-20251102...
#
# ✅ OAuth client revoked successfully!

# Try to revoke current CLI client (protected)
kg oauth revoke kg-cli-admin-20251102

# Output:
# ⚠️  Warning: This is your current CLI OAuth client
#    Client ID: kg-cli-admin-20251102
#    Revoking this will log you out.
#
#    To proceed, use: kg oauth revoke kg-cli-admin-20251102 --force
#    Or use: kg logout
```

---
