# CLI Command Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from CLI source code.
> Last updated: 2026-01-31

---

## Commands

- [`health`](#health) - Check API server health and retrieve service information. Verifies the server is running and responsive. Use this as a first diagnostic step before running other commands.
- [`config` (cfg)](#config) - Manage kg CLI configuration settings. Controls API connection, authentication tokens, MCP tool preferences, and job auto-approval. Configuration stored in JSON file (typically ~/.kg/config.json).
- [`login`](#login) - Authenticate with username and password - creates personal OAuth client credentials (required for admin commands)
- [`logout`](#logout) - End authentication session - revokes OAuth client and clears credentials (use --forget to also clear saved username)
- [`oauth`](#oauth) - Manage OAuth clients (list, create for MCP, revoke)
- [`ingest`](#ingest) - Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-014) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.
- [`job` (jobs)](#job) - Manage and monitor ingestion jobs through their lifecycle (pending → approval → processing → completed/failed)
- [`search`](#search) - Search and explore the knowledge graph using vector similarity, graph traversal, and path finding
- [`database` (db)](#database) - Database operations and information. Provides read-only queries for PostgreSQL + Apache AGE database health, statistics, and connection details.
- [`ontology` (onto)](#ontology) - Manage ontologies (knowledge domains). Ontologies are named collections that organize concepts into knowledge domains. Each ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.

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
- `auto-approve` - Enable or disable automatic approval of ingestion jobs. When enabled, jobs skip the cost estimate review step and start processing immediately (ADR-014).
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

Enable or disable automatic approval of ingestion jobs. When enabled, jobs skip the cost estimate review step and start processing immediately (ADR-014).

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


## ingest

Ingest documents into the knowledge graph. Processes documents and extracts concepts, relationships, and evidence. Supports three modes: single file (one document), directory (batch ingest multiple files), and raw text (ingest text directly without a file). All operations create jobs (ADR-014) that can be monitored via "kg job" commands. Workflow: submit → chunk (semantic boundaries ~1000 words with overlap) → create job → optional approval → process (LLM extract, embed concepts, match existing, insert graph) → complete.

**Usage:**
```bash
kg ingest [options]
```

**Subcommands:**

- `file` - Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-014), -w to wait for completion (polls until complete, shows progress).
- `directory` - Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default: text *.md *.txt, images *.png *.jpg *.jpeg *.gif *.webp), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Auto-detects file type: images use vision pipeline (ADR-057), text files use standard extraction. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.
- `text` - Ingest raw text directly without a file. Submits text content as ingestion job, useful for quick testing/prototyping, ingesting programmatically generated text, API/script integration, and processing text from other commands. Can pipe command output via xargs or use multiline text with heredoc syntax. Text is chunked (default 1000 words per chunk) and processed like file ingestion. Use --filename to customize displayed name in ontology files list (default: text_input). Behavior same as file ingestion: auto-approves by default, detects duplicates, supports --wait for synchronous completion.
- `image` - Ingest an image file using multimodal vision AI (ADR-057). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

---

### file

Ingest a single document file. Reads file, chunks text into semantic segments (~1000 words with overlap), submits job, returns job ID. Optionally waits for completion with -w. Supports text files (.txt, .md, .rst), PDF documents (.pdf), and other API-supported formats. By default: auto-approves (starts immediately), uses serial processing (chunks see previous concepts for clean deduplication, slower but higher quality), detects duplicates (file hash checked, returns existing job if found). Use --force to bypass duplicate detection, --parallel for faster processing of large documents (may create duplicate concepts), --no-approve to require manual approval (ADR-014), -w to wait for completion (polls until complete, shows progress).

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

Ingest all matching files from a directory (batch processing). Scans directory for files matching patterns (default: text *.md *.txt, images *.png *.jpg *.jpeg *.gif *.webp), optionally recurses into subdirectories (-r with depth limit), groups files by ontology (single ontology via -o OR auto-create from subdirectory names via --directories-as-ontologies), and submits batch jobs. Auto-detects file type: images use vision pipeline (ADR-057), text files use standard extraction. Use --dry-run to preview what would be ingested without submitting (checks duplicates, shows skip/submit counts). Directory-as-ontology mode: each subdirectory becomes separate ontology named after directory, useful for organizing knowledge domains by folder structure. Examples: "physics/" → "physics" ontology, "chemistry/organic/" → "organic" ontology.

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

Ingest an image file using multimodal vision AI (ADR-057). Converts image to prose description using GPT-4o Vision, generates visual embeddings with Nomic Vision v1.5, then extracts concepts via standard pipeline. Supports PNG, JPEG, GIF, WebP, BMP (max 10MB). Research validated: GPT-4o 100% reliable, Nomic Vision 0.847 clustering quality (27% better than CLIP). See docs/research/vision-testing/

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
| `-s, --status <status>` | Filter by status (pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled) | - |
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
| `-s, --status <status>` | Filter by status (pending|cancelled|completed|failed) | - |
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
kg search [query]
```

**Arguments:**

- `<query>` - Search query (shortcut for: kg search query <term>)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum number of results to return | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0) | `"0.7"` |
| `--json` | Output raw JSON instead of formatted text | - |
| `--save-artifact` | Save result as persistent artifact (ADR-083) | - |

**Subcommands:**

- `query` - Search for concepts using vector similarity (embeddings) - use specific phrases for best results
- `show` (`details`) - Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength
- `related` - Find concepts related through graph traversal (breadth-first search) - groups results by distance
- `connect` - Find shortest path between two concepts using IDs or semantic phrase matching
- `sources` - Search source documents directly using embeddings - returns matched text with related concepts (ADR-068)

---

### query

Search for concepts using vector similarity (embeddings) - use specific phrases for best results

**Usage:**
```bash
kg query <query>
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
| `--no-grounding` | Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results | - |
| `--no-diversity` | Disable semantic diversity calculation (ADR-063 authenticity signal) for faster results | - |
| `--diversity-hops <number>` | Maximum traversal depth for diversity (1-3, default 2) | `"2"` |
| `--download <directory>` | Download images to specified directory instead of displaying inline | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |
| `--save-artifact` | Save result as persistent artifact (ADR-083) | - |

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
| `--no-grounding` | Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results | - |
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
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-065): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-065) | - |
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
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-065): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-065) | - |

### sources

Search source documents directly using embeddings - returns matched text with related concepts (ADR-068)

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


## database (db)

Database operations and information. Provides read-only queries for PostgreSQL + Apache AGE database health, statistics, and connection details.

**Usage:**
```bash
kg database [options]
```

**Subcommands:**

- `stats` - Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.
- `info` - Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.
- `health` - Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.
- `query` - Execute a custom openCypher/GQL query (ADR-048). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept
- `counters` - Show graph metrics counters organized by type (ADR-079). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

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

Execute a custom openCypher/GQL query (ADR-048). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - openCypher/GQL query string

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--namespace <type>` | Namespace for safety: "concept", "vocab", or omit for raw (ADR-048) | - |
| `--params <json>` | Query parameters as JSON string (e.g., '{"min_score": 0.8}') | - |
| `--limit <n>` | Convenience: Append LIMIT to query (overrides query LIMIT) | - |

### counters

Show graph metrics counters organized by type (ADR-079). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

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
- `scores` - Show cached breathing scores for an ontology (or all ontologies). Shows mass, coherence, exposure, and protection scores. Use "kg ontology score <name>" to recompute.
- `score` - Recompute breathing scores for one ontology. Runs mass, coherence, exposure, and protection scoring and caches results.
- `score-all` - Recompute breathing scores for all ontologies. Runs full scoring pipeline and caches results on each Ontology node.
- `candidates` - Show top concepts by degree centrality in an ontology. High-degree concepts are potential promotion candidates — they may warrant their own ontology.
- `affinity` - Show cross-ontology concept overlap. Identifies which other ontologies share concepts with this one, ranked by affinity score.
- `edges` - Show ontology-to-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES). Derived by breathing cycles or created manually.
- `reassign` - Move sources from one ontology to another. Updates s.document and SCOPED_BY edges. Refuses if source ontology is frozen.
- `dissolve` - Dissolve an ontology non-destructively. Moves all sources to the target ontology, then removes the Ontology node. Unlike delete, this preserves all data. Refuses if ontology is pinned or frozen.
- `proposals` - List breathing proposals generated by the breathing cycle. Proposals are promotion or demotion suggestions for ontologies that require human review before execution.
- `proposal` - View or review a specific breathing proposal.
- `breathe` - Trigger a breathing cycle. Scores all ontologies, recomputes centroids, identifies candidates, and generates proposals for review. Use --dry-run to preview candidates without generating proposals.

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

### scores

Show cached breathing scores for an ontology (or all ontologies). Shows mass, coherence, exposure, and protection scores. Use "kg ontology score <name>" to recompute.

**Usage:**
```bash
kg scores [name]
```

**Arguments:**

- `<name>` - Ontology name (omit for all)

### score

Recompute breathing scores for one ontology. Runs mass, coherence, exposure, and protection scoring and caches results.

**Usage:**
```bash
kg score <name>
```

**Arguments:**

- `<name>` - Ontology name

### score-all

Recompute breathing scores for all ontologies. Runs full scoring pipeline and caches results on each Ontology node.

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

Show ontology-to-ontology edges (OVERLAPS, SPECIALIZES, GENERALIZES). Derived by breathing cycles or created manually.

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

List breathing proposals generated by the breathing cycle. Proposals are promotion or demotion suggestions for ontologies that require human review before execution.

**Usage:**
```bash
kg proposals [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--status <status>` | Filter by status: pending, approved, rejected, expired | - |
| `--type <type>` | Filter by type: promotion, demotion | - |
| `--ontology <name>` | Filter by ontology name | - |

### proposal

View or review a specific breathing proposal.

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

### breathe

Trigger a breathing cycle. Scores all ontologies, recomputes centroids, identifies candidates, and generates proposals for review. Use --dry-run to preview candidates without generating proposals.

**Usage:**
```bash
kg breathe [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview candidates without generating proposals | - |
| `--demotion-threshold <threshold>` | Protection score below which to consider demotion | `"0.15"` |
| `--promotion-min-degree <degree>` | Minimum concept degree for promotion candidacy | `"10"` |
| `--max-proposals <count>` | Maximum proposals per cycle | `"5"` |

