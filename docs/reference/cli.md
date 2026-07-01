---
id: 07.004.R
domain: ui
mode: reference
---

# CLI Command Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from CLI source code.
> Last updated: 2026-07-01

---

## Commands

- [`health`](#health) - Check API server health and retrieve service information. Verifies the server is running and responsive. Use this as a first diagnostic step before running other commands.
- [`config` (cfg)](#config) - Manage kg CLI configuration settings. Controls API connection, authentication tokens, MCP tool preferences, and job auto-approval. Configuration stored in JSON file (typically ~/.kg/config.json).
- [`mcp-config`](#mcp-config) - Manage path allowlist for secure file/directory ingestion from MCP server.

Security Model (ADR-408):
- Fail-secure validation (blocked patterns checked first)
- Explicit allowlist (no access without configuration)
- CLI-only management (agent can read, not write)
- Path resolution prevents traversal attacks

Configuration stored in: ~/.config/kg/mcp-allowed-paths.json
- [`ingest`](#ingest) - Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-300) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.
- [`job` (jobs)](#job) - Manage and monitor ingestion jobs through their lifecycle (pending → approval → processing → completed/failed)
- [`search`](#search) - Search and explore the knowledge graph using vector similarity, graph traversal, and path finding
- [`document` (doc)](#document) - Search for documents using semantic similarity and retrieve their content from Garage storage. Documents are aggregated from source chunks, ranked by their best matching chunk similarity (ADR-507).
- [`database` (db)](#database) - Database operations and information for PostgreSQL + Apache AGE: health, statistics, and connection details. Note: `db query` executes arbitrary openCypher (including mutations) and requires database:execute (platform_admin); the stats/info/health reads require database:read (admin).
- [`ontology` (onto)](#ontology) - Manage ontologies (knowledge domains). Ontologies are named collections that organize concepts into knowledge domains. Each ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.
- [`source`](#source) - Retrieve and manage source documents stored in Garage. Source documents are the original files ingested into the knowledge graph, preserved for model evolution and re-extraction (ADR-307).
- [`vocabulary` (vocab)](#vocabulary) - Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-603), and auto-categorization (probabilistic via embeddings - ADR-605). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-810).
- [`concept` (c)](#concept) - Create, list, show, and delete concepts. Concepts are the fundamental nodes in the knowledge graph. When creating concepts, the description is embedded and similarity-matched against existing concepts (same as automatic ingestion). Use matching modes to control duplicate handling.
- [`edge` (e)](#edge) - Create, list, and delete edges between concepts. Edges represent relationships like IMPLIES, SUPPORTS, CONTRADICTS, etc. Use --from/--to with concept IDs or --from-label/--to-label for semantic lookup by label.
- [`batch` (b)](#batch) - Batch operations for creating concepts and edges in a single transaction. Import JSON files that define concepts and their relationships. All operations are atomic - if any item fails, the entire batch is rolled back.
- [`admin`](#admin) - System administration and management - health monitoring, backup/restore, database operations, user/RBAC management, AI model configuration (requires authentication for destructive operations)
- [`polarity`](#polarity) - Analyze bidirectional semantic dimensions between concept poles
- [`projection` (proj)](#projection) - Manage t-SNE/UMAP projections of concept embeddings. Projections reduce high-dimensional embeddings to 3D coordinates for the Embedding Landscape Explorer visualization. Use this to compute, view, and manage projection datasets.
- [`artifact` (art)](#artifact) - Manage artifacts - persistent storage for computed results like polarity analyses, projections, and query results. Each artifact records the graph epoch it was computed at, so the platform can tell you when one has gone stale (the graph changed underneath it) and recompute it on request (ADR-207).

This is the user-facing surface for the results you create. For backend object-storage diagnostics (S3 buckets, stored objects, integrity, retention) see the admin command "kg storage".
- [`group` (grp)](#group) - Manage groups for collaborative access control. Groups allow sharing resources with multiple users. System groups (public, admins) are managed by the platform.
- [`query-def` (qd)](#query-def) - Manage saved query definitions - recipes that can be re-executed to generate artifacts. Supports block diagrams, cypher queries, searches, polarity analyses, and connection paths.
- [`program` (prog)](#program) - Validate, store, and retrieve GraphProgram ASTs (ADR-500). Programs are notarized server-side to ensure safety before execution.
- [`storage`](#storage) - Read-only diagnostics for S3-compatible object storage. List objects, inspect metadata, verify integrity after cascade deletes, and view retention policies. Useful for integration testing and debugging storage behavior.
- [`catalog`](#catalog) - Deterministic, filesystem-like browse of what is stored in the knowledge graph. Walk from ontologies down to documents and concepts, filter by name fragment, and inspect single nodes. Distinct from "kg search" (semantic) and "kg storage" (raw S3 admin). Add --json to any subcommand for machine-readable output.
- [`login`](#login) - Authenticate with username and password - creates personal OAuth client credentials (required for admin commands)
- [`logout`](#logout) - End authentication session - revokes OAuth client and clears credentials (use --forget to also clear saved username)
- [`oauth`](#oauth) - Manage OAuth clients (list, create for MCP, revoke)

---

## health

Check API server health and retrieve service information. Verifies the server is running and responsive. Use this as a first diagnostic step before running other commands.

**Usage:**
```bash
kg health [options]
```


## config (cfg)

Manage kg CLI configuration settings. Controls API connection, authentication tokens, MCP tool preferences, and job auto-approval. Configuration stored in JSON file (typically ~/.kg/config.json).

**Usage:**
```bash
kg config [options]
```

**Subcommands:**

- `get` - Get one or all configuration values. Supports dot notation for nested keys (e.g., "mcp.enabled", "client.id").
- `set` - Set a configuration value. Auto-detects data types (boolean, number, JSON). Use --string to force literal string interpretation.
- `delete` - Delete configuration key
- `list` - List all configuration
- `path` - Show configuration file path
- `init` - Initialize configuration file with defaults
- `reset` - Reset configuration to defaults
- `auto-approve` - Enable or disable automatic approval of ingestion jobs. When enabled, jobs skip the cost estimate review step and start processing immediately (ADR-300).
- `update-secret` - Authenticate with username/password and update the stored API secret or key. Password is never stored; only the resulting authentication token is persisted.
- `json` - JSON-based configuration operations (machine-friendly)

---

### get

Get one or all configuration values. Supports dot notation for nested keys (e.g., "mcp.enabled", "client.id").

**Usage:**
```bash
kg get [key]
```

**Arguments:**

- `<key>` - Configuration key (supports dot notation, e.g., "mcp.enabled"). Omit to show all configuration.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### set

Set a configuration value. Auto-detects data types (boolean, number, JSON). Use --string to force literal string interpretation.

**Usage:**
```bash
kg set <key> <value>
```

**Arguments:**

- `<key>` - Configuration key (supports dot notation, e.g., "apiUrl", "mcp.enabled")
- `<value>` - Value to set (auto-detects JSON arrays/objects, booleans, numbers)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Force parse value as JSON | - |
| `--string` | Force treat value as string (no JSON parsing) | - |
| `--no-test` | Skip API URL validation (for api_url only) | - |

### delete

Delete configuration key

**Usage:**
```bash
kg delete <key>
```

**Arguments:**

- `<key>` - Configuration key to delete

### list

List all configuration

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### path

Show configuration file path

**Usage:**
```bash
kg path [options]
```

### init

Initialize configuration file with defaults

**Usage:**
```bash
kg init [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Overwrite existing configuration | - |

### reset

Reset configuration to defaults

**Usage:**
```bash
kg reset [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-y, --yes` | Skip confirmation | - |

### auto-approve

Enable or disable automatic approval of ingestion jobs. When enabled, jobs skip the cost estimate review step and start processing immediately (ADR-300).

**Usage:**
```bash
kg auto-approve [value]
```

**Arguments:**

- `<value>` - Enable (true/on/yes) or disable (false/off/no). Omit to show current status.

### update-secret

Authenticate with username/password and update the stored API secret or key. Password is never stored; only the resulting authentication token is persisted.

**Usage:**
```bash
kg update-secret [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --username <username>` | Username (will prompt if not provided) | - |

### json

JSON-based configuration operations (machine-friendly)

**Usage:**
```bash
kg json [options]
```

**Subcommands:**

- `get` - Get entire configuration as JSON
- `set` - Set configuration from JSON (full or partial)
- `dto` - Output configuration template/schema

---

#### get

Get entire configuration as JSON

**Usage:**
```bash
kg get [options]
```

#### set

Set configuration from JSON (full or partial)

**Usage:**
```bash
kg set <json>
```

**Arguments:**

- `<json>` - JSON string or path to JSON file

#### dto

Output configuration template/schema

**Usage:**
```bash
kg dto [options]
```


## mcp-config

Manage path allowlist for secure file/directory ingestion from MCP server.

Security Model (ADR-408):
- Fail-secure validation (blocked patterns checked first)
- Explicit allowlist (no access without configuration)
- CLI-only management (agent can read, not write)
- Path resolution prevents traversal attacks

Configuration stored in: ~/.config/kg/mcp-allowed-paths.json

**Usage:**
```bash
kg mcp-config [options]
```

**Subcommands:**

- `init-allowlist` - Initialize allowlist with safe defaults
- `allow-dir` - Add allowed directory
- `remove-dir` - Remove allowed directory
- `allow-pattern` - Add allowed file pattern
- `remove-pattern` - Remove allowed file pattern
- `block-pattern` - Add blocked file pattern (security)
- `unblock-pattern` - Remove blocked file pattern
- `show-allowlist` - Show current allowlist configuration
- `test-path` - Test if a path would be allowed
- `oauth` - Create OAuth client for MCP server

---

### init-allowlist

Initialize allowlist with safe defaults

**Usage:**
```bash
kg init-allowlist [options]
```

### allow-dir

Add allowed directory

**Usage:**
```bash
kg allow-dir <directory>
```

**Arguments:**

- `<directory>` - Directory path (supports ~ and glob patterns like ~/Projects/*/docs)

### remove-dir

Remove allowed directory

**Usage:**
```bash
kg remove-dir <directory>
```

**Arguments:**

- `<directory>` - Directory path to remove

### allow-pattern

Add allowed file pattern

**Usage:**
```bash
kg allow-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Glob pattern (e.g., "**/*.md", "**/*.png")

### remove-pattern

Remove allowed file pattern

**Usage:**
```bash
kg remove-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Pattern to remove

### block-pattern

Add blocked file pattern (security)

**Usage:**
```bash
kg block-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Glob pattern to block (e.g., "**/.env*", "**/*.key")

### unblock-pattern

Remove blocked file pattern

**Usage:**
```bash
kg unblock-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Pattern to unblock

### show-allowlist

Show current allowlist configuration

**Usage:**
```bash
kg show-allowlist [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### test-path

Test if a path would be allowed

**Usage:**
```bash
kg test-path <path>
```

**Arguments:**

- `<path>` - File or directory path to test

### oauth

Create OAuth client for MCP server

**Usage:**
```bash
kg oauth [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Custom client name | - |


## ingest

Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-300) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.

**Usage:**
```bash
kg ingest [options]
```

**Subcommands:**

- `file` - Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-300), -w to wait for completion (polls until complete, shows progress).
- `directory` - Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default: text *.md *.txt, images *.png *.jpg *.jpeg *.gif *.webp), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Auto-detects file type: images use vision pipeline (ADR-305), text files use standard extraction. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.
- `text` - Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.
- `image` - Ingest an image file using multimodal vision AI (ADR-305). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

---

### file

Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-300), -w to wait for completion (polls until complete, shows progress).

**Usage:**
```bash
kg file <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (named collection or knowledge domain) | - |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses hash check, creates new job) | `false` |
| `--no-approve` | Require manual approval before processing (job enters awaiting_approval state, must approve via "kg job approve <id>"). Default: auto-approve. | - |
| `--parallel` | Process in parallel (all chunks simultaneously, chunks don't see each other, may duplicate concepts, faster). Default: serial (sequential, cleaner deduplication, recommended). | `false` |
| `--filename <name>` | Override filename for tracking (displayed in ontology files list) | - |
| `--target-words <n>` | Target words per chunk (actual may vary based on natural boundaries, range 500-2000 typically effective) | `"1000"` |
| `--overlap-words <n>` | Word overlap between chunks (provides context continuity, helps LLM understand cross-chunk relationships) | `"200"` |
| `-w, --wait` | Wait for job completion (polls status, shows progress, returns final results). Default: submit and exit (returns immediately with job ID, monitor via "kg job status <id>"). | `false` |

### directory

Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default: text *.md *.txt, images *.png *.jpg *.jpeg *.gif *.webp), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Auto-detects file type: images use vision pipeline (ADR-305), text files use standard extraction. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.

**Usage:**
```bash
kg directory <dir>
```

**Arguments:**

- `<dir>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required unless --directories-as-ontologies). Single ontology receives all files. | - |
| `-p, --pattern <patterns...>` | File patterns to match (glob patterns). Text and image extensions supported. | `["*.md","*.txt","*.png","*.jpg","*.jpeg","*.gif","*.webp","*.bmp"]` |
| `-r, --recurse` | Enable recursive scanning of subdirectories. MUST combine with --depth. Examples: "--recurse --depth 1" (one level), "--recurse --depth 2" (two levels), "--recurse --depth all" (unlimited). Default depth is 0 (current dir only). | `false` |
| `-d, --depth <n>` | Maximum recursion depth (use with --recurse). 0=current dir only (default), 1=one level deep, 2=two levels, "all"=unlimited depth. WITHOUT --recurse, only current directory is scanned. | `"0"` |
| `--directories-as-ontologies` | Use directory names as ontology names (auto-creates ontologies from folder structure, cannot be combined with -o) | `false` |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses hash check for all files) | `false` |
| `--dry-run` | Show what would be ingested without submitting jobs (validates files, checks duplicates, displays skip/submit counts, cancels test jobs) | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (faster but may create duplicate concepts) | `false` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |

### text

Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.

**Usage:**
```bash
kg text <text>
```

**Arguments:**

- `<text>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (named collection or knowledge domain) | - |
| `-f, --force` | Force re-ingestion even if duplicate (bypasses content hash check) | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (faster but may create duplicate concepts) | `false` |
| `--filename <name>` | Filename for tracking (displayed in ontology files list, temporary path context) | `"text_input"` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `-w, --wait` | Wait for job completion (polls until complete, shows progress). Default: submit and exit. | `false` |

### image

Ingest an image file using multimodal vision AI (ADR-305). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

**Usage:**
```bash
kg image <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing. Default: auto-approve. | - |
| `--vision-provider <provider>` | Vision provider: openai (default), anthropic, ollama | `"openai"` |
| `--vision-model <model>` | Vision model name (optional, uses provider default) | - |
| `--filename <name>` | Override filename for tracking | - |
| `-w, --wait` | Wait for job completion | `false` |


## job (jobs)

Manage and monitor ingestion jobs through their lifecycle (pending → approval → processing → completed/failed)

**Usage:**
```bash
kg job [options]
```

**Subcommands:**

- `status` - Get detailed status information for a job (progress, costs, errors) - use --watch to poll until completion
- `list` - List recent jobs with optional filtering by status or user - includes subcommands for common filters
- `approve` - Approve jobs for processing (ADR-300 approval workflow) - single job, batch pending, or filter by status
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

Approve jobs for processing (ADR-300 approval workflow) - single job, batch pending, or filter by status

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


## search

Search and explore the knowledge graph using vector similarity, graph traversal, and path finding

**Usage:**
```bash
kg search [options]
```

**Subcommands:**

- `query` - Search for concepts using vector similarity (embeddings) - use specific phrases for best results
- `show` (`details`) - Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength
- `related` - Find concepts related through graph traversal (breadth-first search) - groups results by distance
- `connect` - Find shortest path between two concepts using IDs or semantic phrase matching
- `sources` - Search source documents directly using embeddings - returns matched text with related concepts (ADR-812)

---

### query

Search for concepts using vector similarity (embeddings) - use specific phrases for best results

**Usage:**
```bash
kg query [query]
```

**Arguments:**

- `<query>` - Natural language search query (2-3 words work best)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum number of results to return | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0, default 0.7=70%, lower to 0.5 for broader matches) | `"0.7"` |
| `--no-evidence` | Hide evidence quotes (shown by default) | - |
| `--no-images` | Hide inline image display (shown by default if chafa installed) | - |
| `--no-grounding` | Disable grounding strength calculation (ADR-808 probabilistic truth convergence) for faster results | - |
| `--no-diversity` | Disable semantic diversity calculation (ADR-503 authenticity signal) for faster results | - |
| `--diversity-hops <number>` | Maximum traversal depth for diversity (1-3, default 2) | `"2"` |
| `--download <directory>` | Download images to specified directory instead of displaying inline | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |
| `--save-artifact` | Save result as persistent artifact (ADR-116) | - |

### show (details)

Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength

**Usage:**
```bash
kg show <concept-id>
```

**Arguments:**

- `<concept-id>` - Concept ID to retrieve (from search results)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-grounding` | Disable grounding strength calculation (ADR-808 probabilistic truth convergence) for faster results | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### related

Find concepts related through graph traversal (breadth-first search) - groups results by distance

**Usage:**
```bash
kg related <concept-id>
```

**Arguments:**

- `<concept-id>` - Starting concept ID for traversal

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --depth <number>` | Maximum traversal depth in hops (1-2 fast, 3-4 moderate, 5 slow) | `"2"` |
| `-t, --types <types...>` | Filter by relationship types (IMPLIES, ENABLES, SUPPORTS, etc. - see kg vocab list) | - |
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-610): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-610) | - |
| `--no-grounding` | Disable grounding strength calculation (ADR-808 probabilistic truth convergence) for faster results | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### connect

Find shortest path between two concepts using IDs or semantic phrase matching

**Usage:**
```bash
kg connect <from> <to>
```

**Arguments:**

- `<from>` - Starting concept (exact ID or descriptive phrase - e.g., "licensing issues" not "licensing")
- `<to>` - Target concept (exact ID or descriptive phrase - use 2-3 word phrases for best results)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--max-hops <number>` | Maximum path length | `"5"` |
| `--min-similarity <number>` | Semantic similarity threshold for phrase matching (default 50% - lower for broader matches) | `"0.5"` |
| `--no-evidence` | Hide evidence quotes (shown by default) | - |
| `--no-images` | Hide inline image display (shown by default if chafa installed) | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--download <directory>` | Download images to specified directory instead of displaying inline | - |
| `--json` | Output raw JSON instead of formatted text | - |
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-610): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-610) | - |

### sources

Search source documents directly using embeddings - returns matched text with related concepts (ADR-812)

**Usage:**
```bash
kg sources <query>
```

**Arguments:**

- `<query>` - Search query text (searches source embeddings, not concept embeddings)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum number of sources to return | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0, default 0.7) | `"0.7"` |
| `-o, --ontology <name>` | Filter by ontology/document name | - |
| `--no-concepts` | Hide concepts extracted from matched sources (shown by default) | - |
| `--no-full-text` | Hide full source text (shown by default) | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |


## document (doc)

Search for documents using semantic similarity and retrieve their content from Garage storage. Documents are aggregated from source chunks, ranked by their best matching chunk similarity (ADR-507).

**Usage:**
```bash
kg document [options]
```

**Subcommands:**

- `search` - Find documents that match a query using semantic search. Results show documents ranked by their best matching chunk similarity. Use --details to show full concept information for the top result.
- `list` - List all documents (DocumentMeta nodes) in the knowledge graph. Filter by ontology to see documents from specific collections.
- `show` - Retrieve and display the full content of a document from Garage storage. Shows the original document text plus source chunks created during ingestion.
- `concepts` - Show all concepts extracted from a specific document. Displays concept names, IDs, and the source chunks where they appear. Use --details for full concept information including evidence and relationships.

---

### search

Find documents that match a query using semantic search. Results show documents ranked by their best matching chunk similarity. Use --details to show full concept information for the top result.

**Usage:**
```bash
kg search <query>
```

**Arguments:**

- `<query>` - Search query (natural language)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology name | - |
| `-s, --min-similarity <n>` | Minimum similarity threshold (0-1) | `"0.5"` |
| `-l, --limit <n>` | Maximum results | `"20"` |
| `-d, --details` | Show full concept details for top result | - |
| `-j, --json` | Output raw JSON | - |

### list

List all documents (DocumentMeta nodes) in the knowledge graph. Filter by ontology to see documents from specific collections.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology name (partial match) | - |
| `-l, --limit <n>` | Maximum documents to return | `"50"` |
| `--offset <n>` | Skip N documents (pagination) | `"0"` |
| `-j, --json` | Output raw JSON | - |

### show

Retrieve and display the full content of a document from Garage storage. Shows the original document text plus source chunks created during ingestion.

**Usage:**
```bash
kg show <document-id>
```

**Arguments:**

- `<document-id>` - Document ID (e.g., sha256:abc123...)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --chunks` | Show source chunks instead of full document | - |
| `-j, --json` | Output raw JSON | - |

### concepts

Show all concepts extracted from a specific document. Displays concept names, IDs, and the source chunks where they appear. Use --details for full concept information including evidence and relationships.

**Usage:**
```bash
kg concepts <document-id>
```

**Arguments:**

- `<document-id>` - Document ID (e.g., sha256:abc123...)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --details` | Show full concept details (evidence, relationships, grounding) | - |
| `-j, --json` | Output raw JSON | - |


## database (db)

Database operations and information for PostgreSQL + Apache AGE: health, statistics, and connection details. Note: `db query` executes arbitrary openCypher (including mutations) and requires database:execute (platform_admin); the stats/info/health reads require database:read (admin).

**Usage:**
```bash
kg database [options]
```

**Subcommands:**

- `stats` - Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.
- `info` - Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.
- `health` - Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.
- `query` - Execute a custom openCypher/GQL query (ADR-606). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept
- `counters` - Show graph metrics counters organized by type (ADR-114). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

---

### stats

Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.

**Usage:**
```bash
kg stats [options]
```

### info

Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.

**Usage:**
```bash
kg info [options]
```

### health

Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.

**Usage:**
```bash
kg health [options]
```

### query

Execute a custom openCypher/GQL query (ADR-606). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - openCypher/GQL query string

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--namespace <type>` | Namespace for safety: "concept", "vocab", or omit for raw (ADR-606) | - |
| `--params <json>` | Query parameters as JSON string (e.g., '{"min_score": 0.8}') | - |
| `--limit <n>` | Convenience: Append LIMIT to query (overrides query LIMIT) | - |

### counters

Show graph metrics counters organized by type (ADR-114). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

**Usage:**
```bash
kg counters [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--refresh` | Refresh counters from current graph state before displaying | - |


## ontology (onto)

Manage ontologies (knowledge domains). Ontologies are named collections that organize concepts into knowledge domains. Each ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.

**Usage:**
```bash
kg ontology [options]
```

**Subcommands:**

- `list` - List all ontologies in the knowledge graph. Shows a table with ontology name, file count, chunk count, and concept count. Use this to get a bird's-eye view of all knowledge domains, verify ingestion results, and understand how knowledge is distributed.
- `info` - Get detailed information about a specific ontology. Shows statistics (files, chunks, concepts, evidence, relationships) and lists all source files. Use this to understand ontology composition, verify expected files are present, and troubleshoot ingestion issues.
- `files` - List files in a specific ontology with per-file statistics (chunks and concepts). Shows which files contributed most concepts and helps identify files that may need re-ingestion. Original file paths are preserved, though temporary paths may appear for text-based ingestion.
- `create` - Create an ontology before ingesting any documents (ADR-200: directed growth). This pre-creates the Ontology graph node with an embedding, making the ontology discoverable in the vector space immediately. Useful for planning knowledge domains before populating them.
- `lifecycle` - Change ontology lifecycle state (ADR-200 Phase 2). States: active (normal), pinned (immune to demotion), frozen (read-only — rejects ingest and rename).
- `rename` - Rename an ontology while preserving all its data (concepts, sources, relationships). This is a non-destructive operation useful for reorganization, archiving old ontologies, fixing typos, or improving clarity. Atomic transaction ensures all-or-nothing updates. Requires confirmation unless -y flag is used.
- `delete` - Delete an ontology and ALL its data (concepts, sources, evidence instances, relationships). This is a DESTRUCTIVE operation that CANNOT BE UNDONE. Use this to remove test data, delete old projects, or free up space. Requires --force flag for confirmation. Consider alternatives: rename to add "Archive" suffix, or export data first (future feature).
- `tombstones` - Manage ontology tombstones (operator-delete markers that block re-ingestion into a deleted name)
- `scores` - Show cached annealing scores for an ontology (or all ontologies). Shows mass, coherence, exposure, and protection scores. Use "kg ontology score <name>" to recompute.
- `score` - Recompute annealing scores for one ontology. Runs mass, coherence, exposure, and protection scoring and caches results.
- `score-all` - Recompute annealing scores for all ontologies. Runs full scoring pipeline and caches results on each Ontology node.
- `candidates` - Show top concepts by degree centrality in an ontology. High-degree concepts are potential promotion candidates — they may warrant their own ontology.
- `affinity` - Show cross-ontology concept overlap. Identifies which other ontologies share concepts with this one, ranked by affinity score.
- `edges` - Show ontology-to-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES). Derived by annealing cycles or created manually.
- `reassign` - Move sources from one ontology to another. Updates s.document and SCOPED_BY edges. Refuses if source ontology is frozen.
- `dissolve` - Dissolve an ontology non-destructively. Moves all sources to the target ontology, then removes the Ontology node. Unlike delete, this preserves all data. Refuses if ontology is pinned or frozen.
- `proposals` - List annealing proposals generated by the annealing cycle (ADR-206). Each proposal is one of CLEAVE / DISSOLVE / MERGE / RENAME / NO_ACTION / ESCALATE / ADJUST_CONTROL — the six ontology actions plus the Opus-tier control-tuning meta-action.
- `proposal` - View or review a specific annealing proposal.
- `anneal` - Trigger a annealing cycle. Scores all ontologies, recomputes centroids, identifies candidates, and generates proposals for review. Use --dry-run to preview candidates without generating proposals.

---

### list

List all ontologies in the knowledge graph. Shows a table with ontology name, file count, chunk count, and concept count. Use this to get a bird's-eye view of all knowledge domains, verify ingestion results, and understand how knowledge is distributed.

**Usage:**
```bash
kg list [options]
```

### info

Get detailed information about a specific ontology. Shows statistics (files, chunks, concepts, evidence, relationships) and lists all source files. Use this to understand ontology composition, verify expected files are present, and troubleshoot ingestion issues.

**Usage:**
```bash
kg info <name>
```

**Arguments:**

- `<name>` - Ontology name

### files

List files in a specific ontology with per-file statistics (chunks and concepts). Shows which files contributed most concepts and helps identify files that may need re-ingestion. Original file paths are preserved, though temporary paths may appear for text-based ingestion.

**Usage:**
```bash
kg files <name>
```

**Arguments:**

- `<name>` - Ontology name

### create

Create an ontology before ingesting any documents (ADR-200: directed growth). This pre-creates the Ontology graph node with an embedding, making the ontology discoverable in the vector space immediately. Useful for planning knowledge domains before populating them.

**Usage:**
```bash
kg create <name>
```

**Arguments:**

- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --description <text>` | What this knowledge domain covers | - |

### lifecycle

Change ontology lifecycle state (ADR-200 Phase 2). States: active (normal), pinned (immune to demotion), frozen (read-only — rejects ingest and rename).

**Usage:**
```bash
kg lifecycle <name> <state>
```

**Arguments:**

- `<name>` - Ontology name
- `<state>` - Target state: active, pinned, or frozen

### rename

Rename an ontology while preserving all its data (concepts, sources, relationships). This is a non-destructive operation useful for reorganization, archiving old ontologies, fixing typos, or improving clarity. Atomic transaction ensures all-or-nothing updates. Requires confirmation unless -y flag is used.

**Usage:**
```bash
kg rename <old-name> <new-name>
```

**Arguments:**

- `<old-name>` - Current ontology name
- `<new-name>` - New ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-y, --yes` | Skip confirmation prompt | - |

### delete

Delete an ontology and ALL its data (concepts, sources, evidence instances, relationships). This is a DESTRUCTIVE operation that CANNOT BE UNDONE. Use this to remove test data, delete old projects, or free up space. Requires --force flag for confirmation. Consider alternatives: rename to add "Archive" suffix, or export data first (future feature).

**Usage:**
```bash
kg delete <name>
```

**Arguments:**

- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation and force deletion | - |
| `--keep-tombstone` | Leave the deletion tombstone in place, deliberately blocking re-ingestion into this name until it is recreated (default: delete clears its own tombstone so the name is immediately re-ingestable) | - |

### tombstones

Manage ontology tombstones (operator-delete markers that block re-ingestion into a deleted name)

**Usage:**
```bash
kg tombstones [options]
```

**Subcommands:**

- `list` - List all ontology tombstones
- `flush` - Clear ALL ontology tombstones, unblocking re-ingestion into every deleted name
- `clear` - Clear the tombstone for a single ontology name

---

#### list

List all ontology tombstones

**Usage:**
```bash
kg list [options]
```

#### flush

Clear ALL ontology tombstones, unblocking re-ingestion into every deleted name

**Usage:**
```bash
kg flush [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | - |

#### clear

Clear the tombstone for a single ontology name

**Usage:**
```bash
kg clear <name>
```

**Arguments:**

- `<name>` - Ontology name

### scores

Show cached annealing scores for an ontology (or all ontologies). Shows mass, coherence, exposure, and protection scores. Use "kg ontology score <name>" to recompute.

**Usage:**
```bash
kg scores [name]
```

**Arguments:**

- `<name>` - Ontology name (omit for all)

### score

Recompute annealing scores for one ontology. Runs mass, coherence, exposure, and protection scoring and caches results.

**Usage:**
```bash
kg score <name>
```

**Arguments:**

- `<name>` - Ontology name

### score-all

Recompute annealing scores for all ontologies. Runs full scoring pipeline and caches results on each Ontology node.

**Usage:**
```bash
kg score-all [options]
```

### candidates

Show top concepts by degree centrality in an ontology. High-degree concepts are potential promotion candidates — they may warrant their own ontology.

**Usage:**
```bash
kg candidates <name>
```

**Arguments:**

- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <n>` | Max concepts | `"20"` |

### affinity

Show cross-ontology concept overlap. Identifies which other ontologies share concepts with this one, ranked by affinity score.

**Usage:**
```bash
kg affinity <name>
```

**Arguments:**

- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <n>` | Max ontologies | `"10"` |

### edges

Show ontology-to-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES). Derived by annealing cycles or created manually.

**Usage:**
```bash
kg edges <name>
```

**Arguments:**

- `<name>` - Ontology name

### reassign

Move sources from one ontology to another. Updates s.document and SCOPED_BY edges. Refuses if source ontology is frozen.

**Usage:**
```bash
kg reassign <from>
```

**Arguments:**

- `<from>` - Source ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--to <target>` | Target ontology name | - |
| `--source-ids <ids...>` | Source IDs to move | - |

### dissolve

Dissolve an ontology non-destructively. Moves all sources to the target ontology, then removes the Ontology node. Unlike delete, this preserves all data. Refuses if ontology is pinned or frozen.

**Usage:**
```bash
kg dissolve <name>
```

**Arguments:**

- `<name>` - Ontology to dissolve

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--into <target>` | Target ontology to receive sources | - |

### proposals

List annealing proposals generated by the annealing cycle (ADR-206). Each proposal is one of CLEAVE / DISSOLVE / MERGE / RENAME / NO_ACTION / ESCALATE / ADJUST_CONTROL — the six ontology actions plus the Opus-tier control-tuning meta-action.

**Usage:**
```bash
kg proposals [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--status <status>` | Filter by status: pending, approved, rejected, expired, executing, executed, failed | - |
| `--type <type>` | Filter by verb: CLEAVE, DISSOLVE, MERGE, RENAME, NO_ACTION, ESCALATE, ADJUST_CONTROL (legacy: promotion, demotion) | - |
| `--ontology <name>` | Filter by ontology name | - |

### proposal

View or review a specific annealing proposal.

**Usage:**
```bash
kg proposal <id>
```

**Arguments:**

- `<id>` - Proposal ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--approve` | Approve this proposal | - |
| `--reject` | Reject this proposal | - |
| `--notes <notes>` | Review notes | - |

### anneal

Trigger a annealing cycle. Scores all ontologies, recomputes centroids, identifies candidates, and generates proposals for review. Use --dry-run to preview candidates without generating proposals.

**Usage:**
```bash
kg anneal [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview candidates without generating proposals | - |
| `--demotion-threshold <threshold>` | Protection score below which to consider demotion | `"0.15"` |
| `--promotion-min-degree <degree>` | Minimum concept degree for promotion candidacy | `"10"` |
| `--max-proposals <count>` | Maximum proposals per cycle | `"5"` |


## source

Retrieve and manage source documents stored in Garage. Source documents are the original files ingested into the knowledge graph, preserved for model evolution and re-extraction (ADR-307).

**Usage:**
```bash
kg source [options]
```

**Subcommands:**

- `list` - List source nodes (chunks) in the graph. Sources are chunks of ingested documents. Filter by ontology name to see sources from specific documents.
- `get` - Download the original source document from Garage storage. This returns the complete document as it was before chunking, not individual chunks. Useful for verification, re-processing, or archival. Output goes to stdout by default (for piping) or to a file with -o.
- `info` - Display metadata for a source node including document name, paragraph number, content type, garage_key, and embedding status.

---

### list

List source nodes (chunks) in the graph. Sources are chunks of ingested documents. Filter by ontology name to see sources from specific documents.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology/document name (partial match) | - |
| `-l, --limit <n>` | Maximum sources to return | `"50"` |
| `--offset <n>` | Skip N sources (pagination) | `"0"` |
| `-j, --json` | Output raw JSON | - |

### get

Download the original source document from Garage storage. This returns the complete document as it was before chunking, not individual chunks. Useful for verification, re-processing, or archival. Output goes to stdout by default (for piping) or to a file with -o.

**Usage:**
```bash
kg get <source-id>
```

**Arguments:**

- `<source-id>` - Source ID (e.g., sha256:abc123_chunk1)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output <file>` | Save to file instead of stdout | - |
| `-m, --metadata` | Show source metadata instead of content | - |

### info

Display metadata for a source node including document name, paragraph number, content type, garage_key, and embedding status.

**Usage:**
```bash
kg info <source-id>
```

**Arguments:**

- `<source-id>` - Source ID


## vocabulary (vocab)

Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-603), and auto-categorization (probabilistic via embeddings - ADR-605). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-810).

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-603), aggressiveness, and thresholds.
- `list` - List all edge types with statistics, categories, and confidence scores (ADR-605).
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-603). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations.
- `merge` - Manually merge one edge type into another. Redirects all edges from deprecated type to target type.
- `generate-embeddings` - Generate vector embeddings for vocabulary types (required for consolidation and categorization).
- `category-scores` - Show category similarity scores for a specific relationship type (ADR-605).
- `refresh-categories` - Refresh category assignments for vocabulary types using latest embeddings (ADR-605, ADR-608).
- `search` - Search for vocabulary terms by natural language query. Useful when creating edges to find the best relationship type.
- `similar` - Find similar edge types via embedding similarity (ADR-608). Shows types with highest cosine similarity - useful for synonym detection and consolidation.
- `opposite` - Find opposite (least similar) edge types via embedding similarity (ADR-608). Shows types with lowest cosine similarity.
- `analyze` - Detailed analysis of vocabulary type for quality assurance (ADR-608). Shows category fit and potential miscategorization.
- `config` - Show or update vocabulary configuration. No args: display config. With args: update properties (e.g., "kg vocab config vocab_max 275").
- `profiles` - Manage aggressiveness profiles (Bezier curves for consolidation behavior)
- `epistemic-status` - Epistemic status classification for vocabulary types (ADR-610). Shows knowledge validation state based on grounding patterns.
- `sync` - Sync missing edge types from graph to vocabulary (ADR-611). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

---

### status

Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-603), aggressiveness, and thresholds.

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics, categories, and confidence scores (ADR-605).

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |
| `--sort <fields>` | Sort by comma-separated fields: edges, type, conf, grounding, category, status (default: edges) | - |
| `--json` | Output as JSON for programmatic use | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-603). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations.

**Usage:**
```bash
kg consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `"90"` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `"0.90"` |
| `--dry-run` | Preview candidates without executing (no merges, no pruning) | - |
| `--no-prune-unused` | Skip pruning vocabulary types with 0 uses | - |

### merge

Manually merge one edge type into another. Redirects all edges from deprecated type to target type.

**Usage:**
```bash
kg merge <deprecated-type> <target-type>
```

**Arguments:**

- `<deprecated-type>` - Edge type to deprecate (becomes inactive)
- `<target-type>` - Target edge type to merge into (receives all edges)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --reason <text>` | Reason for merge (audit trail) | - |
| `-u, --user <email>` | User performing the merge | `"cli-user"` |

### generate-embeddings

Generate vector embeddings for vocabulary types (required for consolidation and categorization).

**Usage:**
```bash
kg generate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Regenerate ALL embeddings regardless of existing state | - |
| `--all` | Process all active types (not just missing) | - |

### category-scores

Show category similarity scores for a specific relationship type (ADR-605).

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., CAUSES, ENABLES)

### refresh-categories

Refresh category assignments for vocabulary types using latest embeddings (ADR-605, ADR-608).

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed | - |

### search

Search for vocabulary terms by natural language query. Useful when creating edges to find the best relationship type.

**Usage:**
```bash
kg search <query>
```

**Arguments:**

- `<query>` - Natural language search term (e.g., "prevents", "leads to", "causes")

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-20) | `"5"` |
| `--json` | Output as JSON for scripting | - |

### similar

Find similar edge types via embedding similarity (ADR-608). Shows types with highest cosine similarity - useful for synonym detection and consolidation.

**Usage:**
```bash
kg similar <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., IMPLIES)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-100) | `"10"` |

### opposite

Find opposite (least similar) edge types via embedding similarity (ADR-608). Shows types with lowest cosine similarity.

**Usage:**
```bash
kg opposite <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., IMPLIES)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-100) | `"5"` |

### analyze

Detailed analysis of vocabulary type for quality assurance (ADR-608). Shows category fit and potential miscategorization.

**Usage:**
```bash
kg analyze <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., STORES)

### config

Show or update vocabulary configuration. No args: display config. With args: update properties (e.g., "kg vocab config vocab_max 275").

**Usage:**
```bash
kg config [properties]
```

**Arguments:**

- `<properties>` - Property assignments: key value [key value...]

### profiles

Manage aggressiveness profiles (Bezier curves for consolidation behavior)

**Usage:**
```bash
kg profiles [options]
```

**Subcommands:**

- `list` - List all aggressiveness profiles including builtin (8 predefined) and custom profiles. Shows profile name, control points, description, and builtin flag.
- `show` - Show details for a specific aggressiveness profile including Bezier parameters and timestamps.
- `create` - Create a custom aggressiveness profile with Bezier curve parameters.
- `delete` - Delete a custom aggressiveness profile. Cannot delete builtin profiles.

---

#### list

List all aggressiveness profiles including builtin (8 predefined) and custom profiles. Shows profile name, control points, description, and builtin flag.

**Usage:**
```bash
kg list [options]
```

#### show

Show details for a specific aggressiveness profile including Bezier parameters and timestamps.

**Usage:**
```bash
kg show <name>
```

**Arguments:**

- `<name>` - Profile name

#### create

Create a custom aggressiveness profile with Bezier curve parameters.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Profile name (3-50 chars) | - |
| `--x1 <n>` | First control point X (0.0-1.0) | - |
| `--y1 <n>` | First control point Y (-2.0 to 2.0) | - |
| `--x2 <n>` | Second control point X (0.0-1.0) | - |
| `--y2 <n>` | Second control point Y (-2.0 to 2.0) | - |
| `--description <desc>` | Profile description (min 10 chars) | - |

#### delete

Delete a custom aggressiveness profile. Cannot delete builtin profiles.

**Usage:**
```bash
kg delete <name>
```

**Arguments:**

- `<name>` - Profile name to delete

### epistemic-status

Epistemic status classification for vocabulary types (ADR-610). Shows knowledge validation state based on grounding patterns.

**Usage:**
```bash
kg epistemic-status [options]
```

**Subcommands:**

- `list` - List all vocabulary types with their epistemic status classifications and statistics.
- `show` - Show detailed epistemic status for a specific vocabulary type.
- `measure` - Run epistemic status measurement for all vocabulary types (ADR-610).

---

#### list

List all vocabulary types with their epistemic status classifications and statistics.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--status <status>` | Filter by status: WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, POORLY_GROUNDED, CONTRADICTED, HISTORICAL, INSUFFICIENT_DATA | - |

#### show

Show detailed epistemic status for a specific vocabulary type.

**Usage:**
```bash
kg show <type>
```

**Arguments:**

- `<type>` - Relationship type to show (e.g., IMPLIES, SUPPORTS)

#### measure

Run epistemic status measurement for all vocabulary types (ADR-610).

**Usage:**
```bash
kg measure [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--sample-size <n>` | Edges to sample per type (default: 100) | `100` |
| `--no-store` | Run measurement without storing to database | - |
| `--verbose` | Include detailed statistics in output | - |

### sync

Sync missing edge types from graph to vocabulary (ADR-611). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

**Usage:**
```bash
kg sync [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview missing types without syncing (default) | `true` |
| `--execute` | Actually sync missing types to vocabulary | `false` |
| `--json` | Output as JSON for scripting | - |


## concept (c)

Create, list, show, and delete concepts. Concepts are the fundamental nodes in the knowledge graph. When creating concepts, the description is embedded and similarity-matched against existing concepts (same as automatic ingestion). Use matching modes to control duplicate handling.

**Usage:**
```bash
kg concept [options]
```

**Subcommands:**

- `list` - List concepts with optional filters. Shows concept ID, label, ontology, and creation method.
- `show` - Show detailed information about a concept by ID.
- `create` - Create a new concept. Description is embedded and similarity-matched against existing concepts.
- `delete` - Delete a concept by ID. Requires --force flag or interactive confirmation.

---

### list

List concepts with optional filters. Shows concept ID, label, ontology, and creation method.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--ontology <name>` | Filter by ontology | - |
| `--label <text>` | Filter by label (contains) | - |
| `--creation-method <method>` | Filter by creation method (cli, mcp, api, llm_extraction, import) | - |
| `--limit <n>` | Maximum results (default: 50) | `"50"` |
| `--offset <n>` | Pagination offset | `"0"` |
| `--json` | Output as JSON | - |

### show

Show detailed information about a concept by ID.

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Concept ID (e.g., c_abc123)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### create

Create a new concept. Description is embedded and similarity-matched against existing concepts.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--label <name>` | Concept label (required) | - |
| `--ontology <name>` | Target ontology (required) | - |
| `--description <text>` | Concept description (used for embedding match) | - |
| `--search-terms <terms>` | Comma-separated search terms | - |
| `--matching-mode <mode>` | auto|force_create|match_only (default: auto) | `"auto"` |
| `--json` | Output as JSON | - |
| `-i, --interactive` | Guided wizard mode | - |
| `-y, --yes` | Skip confirmation prompts | - |

### delete

Delete a concept by ID. Requires --force flag or interactive confirmation.

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Concept ID to delete

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--cascade` | Also delete orphaned synthetic sources | - |
| `-f, --force` | Skip confirmation | - |
| `--json` | Output as JSON | - |


## edge (e)

Create, list, and delete edges between concepts. Edges represent relationships like IMPLIES, SUPPORTS, CONTRADICTS, etc. Use --from/--to with concept IDs or --from-label/--to-label for semantic lookup by label.

**Usage:**
```bash
kg edge [options]
```

**Subcommands:**

- `list` - List edges with optional filters.
- `create` - Create an edge between two concepts.
- `delete` - Delete an edge by its composite key (from, type, to).

---

### list

List edges with optional filters.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--from <id>` | Filter by source concept ID | - |
| `--to <id>` | Filter by target concept ID | - |
| `--type <type>` | Filter by relationship type | - |
| `--category <cat>` | Filter by category | - |
| `--limit <n>` | Maximum results (default: 50) | `"50"` |
| `--offset <n>` | Pagination offset | `"0"` |
| `--json` | Output as JSON | - |

### create

Create an edge between two concepts.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--from <id>` | Source concept ID | - |
| `--to <id>` | Target concept ID | - |
| `--from-label <text>` | Source concept (search by label) | - |
| `--to-label <text>` | Target concept (search by label) | - |
| `--type <type>` | Relationship type (e.g., IMPLIES, SUPPORTS) | - |
| `--category <cat>` | Relationship category (auto-inferred if omitted) | - |
| `--confidence <n>` | Confidence score 0-1 (default: 1.0) | `"1.0"` |
| `--create-vocab` | Create vocabulary term if it does not exist | - |
| `--json` | Output as JSON | - |
| `-i, --interactive` | Guided wizard mode | - |
| `-y, --yes` | Skip confirmation prompts | - |

### delete

Delete an edge by its composite key (from, type, to).

**Usage:**
```bash
kg delete <from> <type> <to>
```

**Arguments:**

- `<from>` - Source concept ID
- `<type>` - Relationship type
- `<to>` - Target concept ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | - |
| `--json` | Output as JSON | - |


## batch (b)

Batch operations for creating concepts and edges in a single transaction. Import JSON files that define concepts and their relationships. All operations are atomic - if any item fails, the entire batch is rolled back.

**Usage:**
```bash
kg batch [options]
```

**Subcommands:**

- `create` - Import a batch JSON file to create concepts and edges atomically. The JSON must contain ontology, concepts array, and optional edges array. All operations succeed or all are rolled back.
- `template` - Output a template batch JSON file to stdout. Redirect to a file to customize.

---

### create

Import a batch JSON file to create concepts and edges atomically. The JSON must contain ontology, concepts array, and optional edges array. All operations succeed or all are rolled back.

**Usage:**
```bash
kg create <file>
```

**Arguments:**

- `<file>` - Path to batch JSON file

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output result as JSON | - |
| `--dry-run` | Validate without creating (not yet implemented) | - |

### template

Output a template batch JSON file to stdout. Redirect to a file to customize.

**Usage:**
```bash
kg template [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--with-edges` | Include example edges in template | - |


## admin

System administration and management - health monitoring, backup/restore, database operations, user/RBAC management, AI model configuration (requires authentication for destructive operations)

**Usage:**
```bash
kg admin [options]
```

**Subcommands:**

- `status` - Show comprehensive system health status (Docker containers, database connections, environment configuration, job scheduler)
- `backup` - Create database backup (ADR-712) - full system or per-ontology, in restorable JSON or Gephi GEXF format
- `list-backups` - List available backup files from configured directory
- `restore` - Restore a database backup (uses OAuth authentication)
- `verify-backup` - Validate a backup file without restoring it (runs the server-side oracle)
- `scheduler` - Job scheduler management (ADR-300 job queue) - monitor worker status, cleanup stale jobs
- `workers` - Worker lane management (ADR-100) - monitor slot utilization, queue depth, active jobs
- `user` - User management commands (admin only)
- `rbac` - Manage roles, permissions, and access control (ADR-404)
- `embedding` - Manage embedding profiles (text + image model configuration)
- `extraction` - Manage AI extraction model configuration (ADR-805)
- `vision` - Manage the vision (image->prose) provider (ADR-802)
- `keys` - Manage API keys for AI providers (ADR-405, ADR-805)

---

### status

Show comprehensive system health status (Docker containers, database connections, environment configuration, job scheduler)

**Usage:**
```bash
kg status [options]
```

### backup

Create database backup (ADR-712) - full system or per-ontology, in restorable JSON or Gephi GEXF format

**Usage:**
```bash
kg backup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Backup type: "full" (entire graph) or "ontology" (single namespace) | - |
| `--ontology <name>` | Ontology name (required if --type ontology) | - |
| `--output <filename>` | Custom output filename (auto-generated if not specified) | - |
| `--format <format>` | Export format: "archive" (tar.gz with documents, default), "json" (graph only), or "gexf" (Gephi visualization) | `"archive"` |

### list-backups

List available backup files from configured directory

**Usage:**
```bash
kg list-backups [options]
```

### restore

Restore a database backup (uses OAuth authentication)

**Usage:**
```bash
kg restore [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--file <name>` | Backup filename (from configured directory) | - |
| `--path <path>` | Custom backup file path (overrides configured directory) | - |
| `--mode <mode>` | Restore merge mode: "idempotent" (default; MERGE-by-id, clone into empty), "adjacent" (independent copy, fresh ids), or "integration" (attach concepts to existing graph by similarity) | `"idempotent"` |
| `--epoch <epoch>` | Epoch reconciliation: "simple" (default; one restore event) or "faithful" (replay the backup's history; clone-only — requires --mode idempotent into an empty target) | `"simple"` |
| `--confirm` | Confirm restore operation (required for non-interactive use) | `false` |

### verify-backup

Validate a backup file without restoring it (runs the server-side oracle)

**Usage:**
```bash
kg verify-backup [file]
```

**Arguments:**

- `<file>` - Path to a backup .tar.gz or .json (omit to pick from the backup directory)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--file <name>` | Backup filename from the configured backup directory | - |

### scheduler

Job scheduler management (ADR-300 job queue) - monitor worker status, cleanup stale jobs

**Usage:**
```bash
kg scheduler [options]
```

**Subcommands:**

- `status` - Show job scheduler status and configuration
- `cleanup` - Manually trigger scheduler cleanup (cancels expired jobs, deletes old jobs)

---

#### status

Show job scheduler status and configuration

**Usage:**
```bash
kg status [options]
```

#### cleanup

Manually trigger scheduler cleanup (cancels expired jobs, deletes old jobs)

**Usage:**
```bash
kg cleanup [options]
```

### workers

Worker lane management (ADR-100) - monitor slot utilization, queue depth, active jobs

**Usage:**
```bash
kg workers [options]
```

**Subcommands:**

- `lanes` - Show worker lane configuration and utilization

---

#### lanes

Show worker lane configuration and utilization

**Usage:**
```bash
kg lanes [options]
```

**Subcommands:**

- `set` - Update a worker lane (slots, poll interval, stale timeout, enable/disable)

---

##### set

Update a worker lane (slots, poll interval, stale timeout, enable/disable)

**Usage:**
```bash
kg set <lane>
```

**Arguments:**

- `<lane>` - Lane name (e.g. interactive, maintenance, system)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--max-slots <n>` | Max concurrent jobs in this lane (0–16) | - |
| `--poll-interval <ms>` | Poll interval in milliseconds (500–120000) | - |
| `--stale-timeout <min>` | Stale job timeout in minutes (5–1440) | - |
| `--enable` | Enable the lane | - |
| `--disable` | Disable the lane | - |

### user

User management commands (admin only)

**Usage:**
```bash
kg user [options]
```

**Subcommands:**

- `list` - List all users
- `get` - Get user details by ID
- `create` - Create new user
- `update` - Update user details
- `delete` - Delete user (requires re-authentication)

---

#### list

List all users

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--role <role>` | Filter by role (read_only, contributor, curator, admin) | - |
| `--skip <n>` | Skip first N users (pagination) | `"0"` |
| `--limit <n>` | Limit results (default: 50) | `"50"` |

#### get

Get user details by ID

**Usage:**
```bash
kg get <user_id>
```

**Arguments:**

- `<user_id>` - Required

#### create

Create new user

**Usage:**
```bash
kg create <username>
```

**Arguments:**

- `<username>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--role <role>` | User role (read_only, contributor, curator, admin) | - |
| `-p, --password <password>` | Password (prompts if not provided) | - |

#### update

Update user details

**Usage:**
```bash
kg update <user_id>
```

**Arguments:**

- `<user_id>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--role <role>` | Change user role | - |
| `-p, --password [password]` | Change password (prompts if no value provided) | - |
| `--disable` | Disable user account | - |
| `--enable` | Enable user account | - |

#### delete

Delete user (requires re-authentication)

**Usage:**
```bash
kg delete <user_id>
```

**Arguments:**

- `<user_id>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--yes` | Skip confirmation prompt | - |

### rbac

Manage roles, permissions, and access control (ADR-404)

**Usage:**
```bash
kg rbac [options]
```

**Subcommands:**

- `resource` (`resources`, `res`) - Manage resource types
- `role` (`roles`) - Manage roles
- `permission` (`permissions`, `perm`) - Manage permissions
- `assign` - Assign roles to users

---

#### resource (resources, res)

Manage resource types

**Usage:**
```bash
kg resource [options]
```

**Subcommands:**

- `list` - List all registered resource types
- `create` - Register a new resource type

---

##### list

List all registered resource types

**Usage:**
```bash
kg list [options]
```

##### create

Register a new resource type

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Resource type name | - |
| `-a, --actions <actions...>` | Available actions (space-separated) | - |
| `-d, --description <desc>` | Resource description | - |
| `-p, --parent <parent>` | Parent resource type | - |
| `-s, --scoping` | Enable instance scoping | `false` |

#### role (roles)

Manage roles

**Usage:**
```bash
kg role [options]
```

**Subcommands:**

- `list` - List all roles
- `show` - Show role details
- `create` - Create a new role
- `delete` - Delete a role

---

##### list

List all roles

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--all` | Include inactive roles | `false` |

##### show

Show role details

**Usage:**
```bash
kg show <role>
```

**Arguments:**

- `<role>` - Required

##### create

Create a new role

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Role name (e.g., data_scientist) | - |
| `-d, --display <display>` | Display name | - |
| `--description <desc>` | Role description | - |
| `-p, --parent <parent>` | Parent role to inherit from | - |

##### delete

Delete a role

**Usage:**
```bash
kg delete <role>
```

**Arguments:**

- `<role>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Skip confirmation | `false` |

#### permission (permissions, perm)

Manage permissions

**Usage:**
```bash
kg permission [options]
```

**Subcommands:**

- `list` - List permissions
- `grant` - Grant a permission to a role
- `revoke` - Revoke a permission (use permission ID from list)

---

##### list

List permissions

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --role <role>` | Filter by role name | - |
| `-t, --resource-type <type>` | Filter by resource type | - |

##### grant

Grant a permission to a role

**Usage:**
```bash
kg grant [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --role <role>` | Role name | - |
| `-t, --resource-type <type>` | Resource type | - |
| `-a, --action <action>` | Action (read, write, delete, etc.) | - |
| `-s, --scope <scope>` | Scope type (global, instance, filter) | `"global"` |
| `--scope-id <id>` | Scope ID for instance scoping | - |
| `--deny` | Create explicit deny (default is grant) | `false` |

##### revoke

Revoke a permission (use permission ID from list)

**Usage:**
```bash
kg revoke <permission-id>
```

**Arguments:**

- `<permission-id>` - Required

#### assign

Assign roles to users

**Usage:**
```bash
kg assign [options]
```

**Subcommands:**

- `list` - List role assignments for a user
- `add` - Assign a role to a user
- `remove` - Remove a role assignment (use assignment ID from list)

---

##### list

List role assignments for a user

**Usage:**
```bash
kg list <user-id>
```

**Arguments:**

- `<user-id>` - Required

##### add

Assign a role to a user

**Usage:**
```bash
kg add [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --user-id <id>` | User ID | - |
| `-r, --role <role>` | Role name | - |
| `-s, --scope <scope>` | Scope type (global, workspace, ontology, etc.) | `"global"` |
| `--scope-id <id>` | Scope ID (e.g., workspace ID) | - |

##### remove

Remove a role assignment (use assignment ID from list)

**Usage:**
```bash
kg remove <assignment-id>
```

**Arguments:**

- `<assignment-id>` - Required

### embedding

Manage embedding profiles (text + image model configuration)

**Usage:**
```bash
kg embedding [options]
```

**Subcommands:**

- `list` - List all embedding profiles
- `create` - Create a new embedding profile (inactive)
- `export` - Export an embedding profile as JSON
- `activate` - Activate an embedding profile (with automatic protection)
- `reload` - Hot reload embedding model (zero-downtime)
- `protect` - Enable protection flags on an embedding profile
- `unprotect` - Disable protection flags on an embedding profile
- `delete` - Delete an embedding profile
- `status` - Show comprehensive embedding coverage across all graph text entities with hash verification
- `regenerate` - Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-812 Phase 4) - useful after changing embedding model or repairing missing embeddings

---

#### list

List all embedding profiles

**Usage:**
```bash
kg list [options]
```

#### create

Create a new embedding profile (inactive)

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Profile name | - |
| `--vector-space <tag>` | Vector space compatibility tag | - |
| `--multimodal` | Text model handles both text and image | `false` |
| `--provider <provider>` | Text provider: local or openai (shorthand for --text-provider) | - |
| `--model <model>` | Text model name (shorthand for --text-model) | - |
| `--dimensions <dims>` | Text embedding dimensions (shorthand for --text-dimensions) | - |
| `--precision <precision>` | Text precision: float16 or float32 | - |
| `--text-provider <provider>` | Text provider: local or openai | - |
| `--text-model <model>` | Text model name | - |
| `--text-dimensions <dims>` | Text embedding dimensions | - |
| `--text-loader <loader>` | Text loader: sentence-transformers, transformers, api | - |
| `--text-revision <rev>` | Text model revision/commit hash | - |
| `--text-trust-remote-code` | Trust remote code for text model | `false` |
| `--image-provider <provider>` | Image provider | - |
| `--image-model <model>` | Image model name | - |
| `--image-dimensions <dims>` | Image embedding dimensions | - |
| `--image-loader <loader>` | Image loader: sentence-transformers, transformers, api | - |
| `--image-revision <rev>` | Image model revision/commit hash | - |
| `--image-trust-remote-code` | Trust remote code for image model | `false` |
| `--text-query-prefix <prefix>` | Text prefix for search queries (e.g. "search_query: ") | - |
| `--text-document-prefix <prefix>` | Text prefix for document ingestion (e.g. "search_document: ") | - |
| `--device <device>` | Device: cpu, cuda, mps | - |
| `--memory <mb>` | Max memory in MB | - |
| `--threads <n>` | Number of threads | - |
| `--batch-size <n>` | Batch size | - |
| `--from-json <file>` | Import profile from JSON file | - |

#### export

Export an embedding profile as JSON

**Usage:**
```bash
kg export <profile-id>
```

**Arguments:**

- `<profile-id>` - Profile ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--profile-only` | Strip metadata (id, timestamps) | `false` |

#### activate

Activate an embedding profile (with automatic protection)

**Usage:**
```bash
kg activate <config-id>
```

**Arguments:**

- `<config-id>` - Profile ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Force activation even with dimension mismatch (dangerous!) | - |

#### reload

Hot reload embedding model (zero-downtime)

**Usage:**
```bash
kg reload [options]
```

#### protect

Enable protection flags on an embedding profile

**Usage:**
```bash
kg protect <config-id>
```

**Arguments:**

- `<config-id>` - Profile ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--delete` | Enable delete protection | - |
| `--change` | Enable change protection | - |

#### unprotect

Disable protection flags on an embedding profile

**Usage:**
```bash
kg unprotect <config-id>
```

**Arguments:**

- `<config-id>` - Profile ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--delete` | Disable delete protection | - |
| `--change` | Disable change protection | - |

#### delete

Delete an embedding profile

**Usage:**
```bash
kg delete <config-id>
```

**Arguments:**

- `<config-id>` - Profile ID

#### status

Show comprehensive embedding coverage across all graph text entities with hash verification

**Usage:**
```bash
kg status [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--ontology <name>` | Limit status to specific ontology namespace | - |

#### regenerate

Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-812 Phase 4) - useful after changing embedding model or repairing missing embeddings

**Usage:**
```bash
kg regenerate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Type of embeddings to regenerate: concept, source, vocabulary, all | - |
| `--only-missing` | Only generate for entities without embeddings (skip existing) - applies to concept and source types | `false` |
| `--only-incompatible` | Only regenerate embeddings with mismatched model/dimensions (for model migrations) | `false` |
| `--ontology <name>` | Limit regeneration to specific ontology namespace - applies to concept and source types | - |
| `--limit <n>` | Maximum number of entities to process (useful for testing/batching) | - |
| `--status` | Show embedding status before regeneration (diagnostic mode) | `false` |

### extraction

Manage AI extraction model configuration (ADR-805)

**Usage:**
```bash
kg extraction [options]
```

**Subcommands:**

- `config` - Show current AI extraction configuration
- `set` - Update AI extraction configuration

---

#### config

Show current AI extraction configuration

**Usage:**
```bash
kg config [options]
```

#### set

Update AI extraction configuration

**Usage:**
```bash
kg set [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--provider <provider>` | Provider: openai, anthropic, ollama, or vllm | - |
| `--model <model>` | Model name (e.g., gpt-4o, mistral:7b-instruct) | - |
| `--vision` | Enable vision support | - |
| `--no-vision` | Disable vision support | - |
| `--json-mode` | Enable JSON mode | - |
| `--no-json-mode` | Disable JSON mode | - |
| `--max-tokens <n>` | Max tokens | - |
| `--base-url <url>` | Base URL for local providers (e.g., http://localhost:11434) | - |
| `--temperature <n>` | Sampling temperature 0.0-1.0 (default: 0.1) | - |
| `--top-p <n>` | Nucleus sampling threshold 0.0-1.0 (default: 0.9) | - |
| `--gpu-layers <n>` | GPU layers: -1=auto, 0=CPU only, >0=specific count | - |
| `--num-threads <n>` | CPU threads for inference (default: 4) | - |
| `--thinking-mode <mode>` | Thinking mode: off, low, medium, high (Ollama 0.12.x+) | - |

### vision

Manage the vision (image->prose) provider (ADR-802)

**Usage:**
```bash
kg vision [options]
```

**Subcommands:**

- `config` - Show the effective vision (image->prose) provider/model
- `providers` - List providers and whether they have a vision-capable catalog model
- `set` - Set/activate the vision (image->prose) provider

---

#### config

Show the effective vision (image->prose) provider/model

**Usage:**
```bash
kg config [options]
```

#### providers

List providers and whether they have a vision-capable catalog model

**Usage:**
```bash
kg providers [options]
```

#### set

Set/activate the vision (image->prose) provider

**Usage:**
```bash
kg set [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--provider <provider>` | Provider: openai, anthropic, ollama, openrouter, llamacpp | - |
| `--model <model>` | Vision model id (optional; resolved from the catalog when omitted) | - |
| `--max-tokens <n>` | Max output tokens for image description | - |
| `--temperature <n>` | Sampling temperature 0.0-1.0 | - |
| `--no-activate` | Persist the provider config without making it the active vision provider | - |

### keys

Manage API keys for AI providers (ADR-405, ADR-805)

**Usage:**
```bash
kg keys [options]
```

**Subcommands:**

- `list` - List API keys with validation status
- `set` - Set API key for a provider (validates before storing)
- `delete` - Delete API key for a provider

---

#### list

List API keys with validation status

**Usage:**
```bash
kg list [options]
```

#### set

Set API key for a provider (validates before storing)

**Usage:**
```bash
kg set <provider>
```

**Arguments:**

- `<provider>` - Provider name (openai or anthropic)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--key <key>` | API key (will prompt if not provided) | - |

#### delete

Delete API key for a provider

**Usage:**
```bash
kg delete <provider>
```

**Arguments:**

- `<provider>` - Provider name (openai or anthropic)


## polarity

Analyze bidirectional semantic dimensions between concept poles

**Usage:**
```bash
kg polarity [options]
```

**Subcommands:**

- `analyze` - Project concepts onto axis formed by two opposing poles (e.g., Modern ↔ Traditional)

---

### analyze

Project concepts onto axis formed by two opposing poles (e.g., Modern ↔ Traditional)

**Usage:**
```bash
kg analyze [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--positive <concept-id>` | Positive pole concept ID | - |
| `--negative <concept-id>` | Negative pole concept ID | - |
| `--candidates <ids...>` | Specific concept IDs to project (space-separated) | - |
| `--no-auto-discover` | Disable auto-discovery of related concepts | - |
| `--max-candidates <number>` | Maximum candidates for auto-discovery | `"20"` |
| `--max-hops <number>` | Maximum graph hops for auto-discovery (1-3) | `"1"` |
| `--discovery-mode <mode>` | Discovery strategy: conservative (pure degree), balanced (80/20 - DEFAULT), novelty (pure random) | `"balanced"` |
| `--discovery-pct <number>` | Custom discovery percentage (0.0-1.0, overrides --discovery-mode) | - |
| `--max-workers <number>` | Maximum parallel workers for 2-hop queries | `"8"` |
| `--chunk-size <number>` | Concepts per worker chunk | `"20"` |
| `--timeout <number>` | Wall-clock timeout in seconds | `"120"` |
| `--save-artifact` | Save result as persistent artifact (uses async job) | - |
| `--json` | Output raw JSON instead of formatted text | - |


## projection (proj)

Manage t-SNE/UMAP projections of concept embeddings. Projections reduce high-dimensional embeddings to 3D coordinates for the Embedding Landscape Explorer visualization. Use this to compute, view, and manage projection datasets.

**Usage:**
```bash
kg projection [options]
```

**Subcommands:**

- `list` - List projection status for all ontologies. Shows which ontologies have cached projections and their statistics.
- `info` - Get detailed projection info for an ontology
- `regenerate` - Compute or recompute projection for an ontology
- `invalidate` - Delete cached projection for an ontology
- `data` - Get full projection data as JSON (for visualization pipelines)
- `algorithms` - List available projection algorithms

---

### list

List projection status for all ontologies. Shows which ontologies have cached projections and their statistics.

**Usage:**
```bash
kg list [options]
```

### info

Get detailed projection info for an ontology

**Usage:**
```bash
kg info <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

### regenerate

Compute or recompute projection for an ontology

**Usage:**
```bash
kg regenerate <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name, "all" (each separately), or "global" (all together)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Force recomputation even if cached | - |
| `-a, --algorithm <algo>` | Algorithm: tsne or umap | `"tsne"` |
| `-p, --perplexity <n>` | t-SNE perplexity (5-100) | `"30"` |
| `--center` | Center embeddings before projection (fixes meatball artifact, default: true) | - |
| `--no-center` | Disable embedding centering | - |
| `--grounding` | Include grounding strength | - |
| `--diversity` | Include diversity scores (slower) | - |
| `--save-artifact` | Save result as persistent artifact (ADR-116) | - |

### invalidate

Delete cached projection for an ontology

**Usage:**
```bash
kg invalidate <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

### data

Get full projection data as JSON (for visualization pipelines)

**Usage:**
```bash
kg data <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output <file>` | Write to file instead of stdout | - |
| `--pretty` | Pretty-print JSON output | - |

### algorithms

List available projection algorithms

**Usage:**
```bash
kg algorithms [options]
```


## artifact (art)

Manage artifacts - persistent storage for computed results like polarity analyses, projections, and query results. Each artifact records the graph epoch it was computed at, so the platform can tell you when one has gone stale (the graph changed underneath it) and recompute it on request (ADR-207).

This is the user-facing surface for the results you create. For backend object-storage diagnostics (S3 buckets, stored objects, integrity, retention) see the admin command "kg storage".

**Usage:**
```bash
kg artifact [options]
```

**Subcommands:**

- `list` - List your artifacts. Shows metadata without payloads for efficiency. Filter by type, representation, or ontology.
- `show` - Show artifact metadata by ID. Does not include the payload - use "payload" command for that.
- `payload` - Get artifact with full payload. For large artifacts stored in Garage, this fetches from object storage.
- `create` - Create a test artifact (for API validation). Creates a simple artifact with provided parameters.
- `delete` - Delete an artifact. Removes both database record and any Garage-stored payload.
- `regenerate` (`regen`) - Recompute a stale artifact from its stored parameters (ADR-207). Enqueues an auto-approved job; the result is saved as a NEW artifact and the original is preserved. Supported types: polarity_analysis, projection.
- `cleanup` - Remove stale artifacts in bulk — those whose graph epoch is behind the current graph (ADR-207). Previews by default; pass --force to delete. Regeneratable types can be recomputed afterward with "kg artifact regenerate".

---

### list

List your artifacts. Shows metadata without payloads for efficiency. Filter by type, representation, or ontology.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Filter by artifact type (polarity_analysis, projection, etc.) | - |
| `-r, --representation <rep>` | Filter by representation/source (cli, polarity_explorer, etc.) | - |
| `-o, --ontology <name>` | Filter by ontology | - |
| `-l, --limit <n>` | Maximum artifacts to return | `"20"` |
| `--offset <n>` | Skip N artifacts (for pagination) | `"0"` |
| `-v, --verbose` | Show storage tier (inline/garage) — an implementation detail hidden by default | - |
| `-j, --json` | Output raw JSON instead of formatted table | - |

### show

Show artifact metadata by ID. Does not include the payload - use "payload" command for that.

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Show storage tier (inline/garage) — an implementation detail hidden by default | - |

### payload

Get artifact with full payload. For large artifacts stored in Garage, this fetches from object storage.

**Usage:**
```bash
kg payload <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-j, --json` | Output raw JSON payload only | - |

### create

Create a test artifact (for API validation). Creates a simple artifact with provided parameters.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Artifact type (polarity_analysis, projection, query_result, etc.) | - |
| `-n, --name <name>` | Human-readable name | - |
| `-o, --ontology <name>` | Associated ontology | - |
| `--payload <json>` | JSON payload (default: simple test payload) | `"{\"test\": true, \"created_via\": \"cli\"}"` |

### delete

Delete an artifact. Removes both database record and any Garage-stored payload.

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation prompt | - |

### regenerate (regen)

Recompute a stale artifact from its stored parameters (ADR-207). Enqueues an auto-approved job; the result is saved as a NEW artifact and the original is preserved. Supported types: polarity_analysis, projection.

**Usage:**
```bash
kg regenerate <id>
```

**Arguments:**

- `<id>` - Artifact ID

### cleanup

Remove stale artifacts in bulk — those whose graph epoch is behind the current graph (ADR-207). Previews by default; pass --force to delete. Regeneratable types can be recomputed afterward with "kg artifact regenerate".

**Usage:**
```bash
kg cleanup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Only clean up artifacts of this type | - |
| `-o, --ontology <name>` | Only clean up artifacts in this ontology | - |
| `-f, --force` | Actually delete (default is a dry-run preview) | - |


## group (grp)

Manage groups for collaborative access control. Groups allow sharing resources with multiple users. System groups (public, admins) are managed by the platform.

**Usage:**
```bash
kg group [options]
```

**Subcommands:**

- `list` - List all groups
- `members` - List members of a group
- `create` - Create a new group (admin only)
- `add-member` - Add a user to a group (admin only)
- `remove-member` - Remove a user from a group (admin only)

---

### list

List all groups

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-system` | Exclude system groups (public, admins) | - |

### members

List members of a group

**Usage:**
```bash
kg members <group-id>
```

**Arguments:**

- `<group-id>` - Group ID

### create

Create a new group (admin only)

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Group name (unique identifier) | - |
| `-d, --display <name>` | Display name | - |
| `--description <text>` | Group description | - |

### add-member

Add a user to a group (admin only)

**Usage:**
```bash
kg add-member <group-id> <user-id>
```

**Arguments:**

- `<group-id>` - Group ID
- `<user-id>` - User ID to add

### remove-member

Remove a user from a group (admin only)

**Usage:**
```bash
kg remove-member <group-id> <user-id>
```

**Arguments:**

- `<group-id>` - Group ID
- `<user-id>` - User ID to remove


## query-def (qd)

Manage saved query definitions - recipes that can be re-executed to generate artifacts. Supports block diagrams, cypher queries, searches, polarity analyses, and connection paths.

**Usage:**
```bash
kg query-def [options]
```

**Subcommands:**

- `list` - List query definitions
- `show` - Show a query definition
- `create` - Create a query definition
- `delete` - Delete a query definition

---

### list

List query definitions

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Filter by type (block_diagram, cypher, search, polarity, connection) | - |
| `-l, --limit <n>` | Maximum to return | `"20"` |

### show

Show a query definition

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Definition ID

### create

Create a query definition

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Definition name | - |
| `-t, --type <type>` | Type: block_diagram, cypher, search, polarity, connection | - |
| `-d, --definition <json>` | Definition as JSON | - |

### delete

Delete a query definition

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Definition ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | - |


## program (prog)

Validate, store, and retrieve GraphProgram ASTs (ADR-500). Programs are notarized server-side to ensure safety before execution.

**Usage:**
```bash
kg program [options]
```

**Subcommands:**

- `validate` - Validate a program without storing it (dry run)
- `create` - Notarize and store a program
- `show` - Show a notarized program
- `execute` - Execute a program server-side

---

### validate

Validate a program without storing it (dry run)

**Usage:**
```bash
kg validate <file>
```

**Arguments:**

- `<file>` - JSON file path (use - for stdin)

### create

Notarize and store a program

**Usage:**
```bash
kg create <file>
```

**Arguments:**

- `<file>` - JSON file path (use - for stdin)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Program name | - |

### show

Show a notarized program

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Program ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output raw JSON | - |

### execute

Execute a program server-side

**Usage:**
```bash
kg execute <source>
```

**Arguments:**

- `<source>` - Program ID (number) or JSON file path (use - for stdin)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output raw JSON | - |
| `--log-only` | Show only the execution log, not the graph | - |


## storage

Read-only diagnostics for S3-compatible object storage. List objects, inspect metadata, verify integrity after cascade deletes, and view retention policies. Useful for integration testing and debugging storage behavior.

**Usage:**
```bash
kg storage [options]
```

**Subcommands:**

- `health` - Check storage backend connectivity and bucket accessibility
- `stats` - Show storage usage statistics by category (sources, images, projections, artifacts)
- `list` - List objects in storage with optional prefix filter. Examples: kg storage list --prefix sources/ --limit 20
- `inspect` - Inspect metadata for a single object without downloading content. Use the full S3 key from "kg storage list".
- `integrity` - Cross-reference S3 objects against graph nodes. Finds orphaned objects (in S3 but not graph) and missing objects (in graph but not S3). Essential for verifying cascade deletes.
- `retention` - Show current retention policy configuration for each storage category

---

### health

Check storage backend connectivity and bucket accessibility

**Usage:**
```bash
kg health [options]
```

### stats

Show storage usage statistics by category (sources, images, projections, artifacts)

**Usage:**
```bash
kg stats [options]
```

### list

List objects in storage with optional prefix filter. Examples: kg storage list --prefix sources/ --limit 20

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-p, --prefix <prefix>` | S3 key prefix filter (e.g. sources/, images/My_Ontology/) | - |
| `-l, --limit <n>` | Maximum objects to return | `50` |
| `-o, --offset <n>` | Number of objects to skip | `0` |

### inspect

Inspect metadata for a single object without downloading content. Use the full S3 key from "kg storage list".

**Usage:**
```bash
kg inspect <key>
```

**Arguments:**

- `<key>` - S3 object key (e.g. sources/My_Ontology/abc123.md)

### integrity

Cross-reference S3 objects against graph nodes. Finds orphaned objects (in S3 but not graph) and missing objects (in graph but not S3). Essential for verifying cascade deletes.

**Usage:**
```bash
kg integrity [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--ontology <name>` | Scope check to a specific ontology | - |
| `--category <type>` | Storage category: sources, images | `"sources"` |

### retention

Show current retention policy configuration for each storage category

**Usage:**
```bash
kg retention [options]
```


## catalog

Deterministic, filesystem-like browse of what is stored in the knowledge graph. Walk from ontologies down to documents and concepts, filter by name fragment, and inspect single nodes. Distinct from "kg search" (semantic) and "kg storage" (raw S3 admin). Add --json to any subcommand for machine-readable output.

**Usage:**
```bash
kg catalog [options]
```

**Subcommands:**

- `ls` - List children of a node, or root ontologies if no id given
- `stat` - Show full metadata for a single catalog node

---

### ls

List children of a node, or root ontologies if no id given

**Usage:**
```bash
kg ls [id]
```

**Arguments:**

- `<id>` - Parent node id (ontology or document). Omit to list ontologies.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-k, --kind <kind>` | Parent kind hint (ontology|document) if id is ambiguous | - |
| `-q, --query <fragment>` | Filter children by case-insensitive name fragment | - |
| `-s, --sort <field>` | Sort: name | child_count | created | `"name"` |
| `-l, --limit <n>` | Max results | `"100"` |
| `-o, --offset <n>` | Pagination offset | `"0"` |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### stat

Show full metadata for a single catalog node

**Usage:**
```bash
kg stat <id>
```

**Arguments:**

- `<id>` - Node id (ontology_id, document_id, or concept_id)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-k, --kind <kind>` | Disambiguate kind if id collides across kinds | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |


## login

Authenticate with username and password - creates personal OAuth client credentials (required for admin commands)

**Usage:**
```bash
kg login [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --username <username>` | Username (will prompt if not provided - can be saved for future logins) | - |
| `-p, --password <password>` | Password (will prompt if not provided - for scripted/non-interactive use) | - |
| `-f, --force` | Replace existing credentials (use after platform redeploy) | - |
| `--remember-username` | Save username for future logins (default in non-interactive mode) | - |
| `--no-remember-username` | Do not save username | - |


## logout

End authentication session - revokes OAuth client and clears credentials (use --forget to also clear saved username)

**Usage:**
```bash
kg logout [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--forget` | Also forget saved username (requires username prompt on next login) | - |


## oauth

Manage OAuth clients (list, create for MCP, revoke)

**Usage:**
```bash
kg oauth [options]
```

**Subcommands:**

- `clients` (`list`) - List your personal OAuth clients
- `create` - Create OAuth client for external tools (MCP, FUSE, scripts)
- `create-mcp` - Create OAuth client for MCP server (alias for: create --for mcp)
- `revoke` - Revoke an OAuth client

---

### clients (list)

List your personal OAuth clients

**Usage:**
```bash
kg clients [options]
```

### create

Create OAuth client for external tools (MCP, FUSE, scripts)

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Custom client name | - |
| `--for <target>` | Target: mcp, fuse, or generic (shows appropriate setup instructions) | - |

### create-mcp

Create OAuth client for MCP server (alias for: create --for mcp)

**Usage:**
```bash
kg create-mcp [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Custom client name | - |

### revoke

Revoke an OAuth client

**Usage:**
```bash
kg revoke <client-id>
```

**Arguments:**

- `<client-id>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Force revocation even if it's your current CLI client | - |

