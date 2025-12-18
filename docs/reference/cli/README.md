# CLI Command Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from CLI source code.
> Last updated: 2025-12-18

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
- [`vocabulary` (vocab)](#vocabulary) - Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).
- [`admin`](#admin) - System administration and management - health monitoring, backup/restore, database operations, user/RBAC management, AI model configuration (requires authentication for destructive operations)

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
- `create-mcp` - Create OAuth client for MCP server and display config
- `revoke` - Revoke an OAuth client

---

### clients (list)

List your personal OAuth clients

**Usage:**
```bash
kg clients [options]
```

### create-mcp

Create OAuth client for MCP server and display config

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
- `clear` - Clear ALL jobs from database - DESTRUCTIVE operation requiring --confirm flag (use for dev/testing cleanup)

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

### clear

Clear ALL jobs from database - DESTRUCTIVE operation requiring --confirm flag (use for dev/testing cleanup)

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

**Subcommands:**

- `query` - Search for concepts using vector similarity (embeddings) - use specific phrases for best results
- `details` - Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength
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

### details

Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength

**Usage:**
```bash
kg details <concept-id>
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
- `rename` - Rename an ontology while preserving all its data (concepts, sources, relationships). This is a non-destructive operation useful for reorganization, archiving old ontologies, fixing typos, or improving clarity. Atomic transaction ensures all-or-nothing updates. Requires confirmation unless -y flag is used.
- `delete` - Delete an ontology and ALL its data (concepts, sources, evidence instances, relationships). This is a DESTRUCTIVE operation that CANNOT BE UNDONE. Use this to remove test data, delete old projects, or free up space. Requires --force flag for confirmation. Consider alternatives: rename to add "Archive" suffix, or export data first (future feature).

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


## vocabulary (vocab)

Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness (growth above minimum), and thresholds. Shows breakdown of builtin types, custom types, and categories. Use this to monitor vocabulary health, check zone before consolidation, track growth over time, and trigger consolidation workflows when needed.
- `list` - List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), GROUNDING (epistemic status avg_grounding), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) prune unused types (default). Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.
- `merge` - Manually merge one edge type into another for consolidation or correction. Validates both types exist, redirects all edges from deprecated type to target type, marks deprecated type as inactive, records audit trail (reason, user, timestamp), and preserves edge provenance. This is a non-destructive, atomic operation useful for manual consolidation, fixing misnamed types from extraction, bulk scripted operations, and targeted category cleanup. Safety: edges preserved, atomic transaction, audit trail for compliance, can be reviewed in inactive types list.
- `generate-embeddings` - Generate vector embeddings for vocabulary types (required for consolidation and categorization). Identifies types without embeddings, generates embeddings using configured embedding model, stores embeddings for similarity comparison, and enables consolidation and auto-categorization. Use after fresh install (bootstrap vocabulary embeddings), after ingestion introduces new custom types, when switching embedding models (regenerate), or for inconsistency fixes (force regeneration if corrupted). Performance: ~100-200ms per embedding (OpenAI), ~20-50ms per embedding (local models), parallel generation (batches of 10).
- `category-scores` - Show category similarity scores for a specific relationship type (ADR-047). Displays assigned category, confidence score (calculated as max_score/second_max_score * 100), ambiguous flag (set when runner-up within 20% of winner), runner-up category if ambiguous, and similarity to all category seeds (0-100%) sorted by similarity with visual bar chart. Use this to verify auto-categorization makes sense, debug low confidence assignments, understand why confidence is low, resolve ambiguity between close categories, and audit all types for misassignments.
- `refresh-categories` - Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053). As of ADR-053, new edge types are automatically categorized during ingestion, so this command is primarily needed when category seeds change. Use when category seed definitions are updated (seeds currently defined in code, future: database-configurable), after embedding model changes, or for migrating pre-ADR-053 uncategorized types. This is a non-destructive operation (doesn't affect edges), preserves manual assignments, and records audit trail per type.
- `similar` - Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation. Use --limit to control results (1-100, default 10). Similar types with high similarity (>0.90) are strong merge candidates for vocabulary consolidation (ADR-052).
- `opposite` - Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity - useful for understanding semantic range and antonyms. Use --limit to control results (1-100, default 5).
- `analyze` - Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit, similar types in same/other categories, and detects potential miscategorization. Use this to verify auto-categorization accuracy and identify types that may need reclassification.
- `config` - Show or update vocabulary configuration. No args: display config table. With args: update properties directly using database key names (e.g., "kg vocab config vocab_max 275 vocab_emergency 350"). Property names shown in config table.
- `config-update` - [DEPRECATED: Use `kg vocab config <property> <value>` instead] Update vocabulary configuration settings. Supports updating multiple properties at once including thresholds (min, max, emergency), pruning mode (naive, hitl, aitl), aggressiveness profile, synonym thresholds, auto-expand setting, and consolidation threshold. Changes are persisted to database and take effect immediately. Use this for runtime threshold adjustments, switching pruning modes, changing aggressiveness profiles, tuning synonym detection, and enabling/disabling auto-expand.
- `profiles` - List all aggressiveness profiles including builtin profiles (8 predefined Bezier curves) and custom profiles (user-created curves). Shows profile name, control points (x1, y1, x2, y2 for cubic Bezier), description, and builtin flag. Use this to view available profiles for configuration, review custom profiles, understand Bezier curve parameters, and identify profiles for deletion. Builtin profiles: linear, ease, ease-in, ease-out, ease-in-out, aggressive (recommended), gentle, exponential.
- `profiles-show` - Show details for a specific aggressiveness profile including full Bezier curve parameters, description, builtin status, and timestamps. Use this to inspect profile details before using, verify control point values, understand profile behavior, and check creation/update times.
- `profiles-create` - Create a custom aggressiveness profile with Bezier curve parameters. Profiles control how aggressively vocabulary consolidation operates as size approaches thresholds. Bezier curve defined by two control points (x1, y1) and (x2, y2) where X is normalized vocabulary size (0.0-1.0) and Y is aggressiveness multiplier. Use this to create deployment-specific curves, experiment with consolidation behavior, tune for specific vocabulary growth patterns, and optimize for production workloads. Cannot overwrite builtin profiles.
- `profiles-delete` - Delete a custom aggressiveness profile. Removes the profile permanently from the database. Cannot delete builtin profiles (protected by database trigger). Use this to remove unused custom profiles, clean up experimental curves, and maintain profile list. Safety: builtin profiles cannot be deleted, atomic operation, immediate effect.
- `epistemic-status` - Epistemic status classification for vocabulary types (ADR-065 Phase 2). Shows knowledge validation state based on grounding patterns: WELL_GROUNDED (avg >0.8, well-established), MIXED_GROUNDING (0.15-0.8, variable validation), WEAK_GROUNDING (0.0-0.15, emerging evidence), POORLY_GROUNDED (-0.5-0.0, uncertain), CONTRADICTED (<-0.5, refuted), HISTORICAL (temporal vocabulary), INSUFFICIENT_DATA (<3 measurements). Results are temporal measurements that change as graph evolves. Use for filtering relationships by epistemic reliability, identifying contested knowledge, tracking knowledge validation trends, and curating high-confidence vs exploratory subgraphs.
- `sync` - Sync missing edge types from graph to vocabulary (ADR-077). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

---

### status

Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness (growth above minimum), and thresholds. Shows breakdown of builtin types, custom types, and categories. Use this to monitor vocabulary health, check zone before consolidation, track growth over time, and trigger consolidation workflows when needed.

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), GROUNDING (epistemic status avg_grounding), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |
| `--sort <fields>` | Sort by comma-separated fields: edges, type, conf, grounding, category, status (case-insensitive). Default: edges (descending) | - |
| `--json` | Output as JSON for programmatic use | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) prune unused types (default). Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.

**Usage:**
```bash
kg consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `"90"` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `"0.90"` |
| `--dry-run` | Evaluate candidates without executing merges | - |
| `--auto` | Auto-execute high confidence merges (AITL mode) | - |
| `--no-prune-unused` | Skip pruning vocabulary types with 0 uses (default: prune enabled) | - |

### merge

Manually merge one edge type into another for consolidation or correction. Validates both types exist, redirects all edges from deprecated type to target type, marks deprecated type as inactive, records audit trail (reason, user, timestamp), and preserves edge provenance. This is a non-destructive, atomic operation useful for manual consolidation, fixing misnamed types from extraction, bulk scripted operations, and targeted category cleanup. Safety: edges preserved, atomic transaction, audit trail for compliance, can be reviewed in inactive types list.

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

Generate vector embeddings for vocabulary types (required for consolidation and categorization). Identifies types without embeddings, generates embeddings using configured embedding model, stores embeddings for similarity comparison, and enables consolidation and auto-categorization. Use after fresh install (bootstrap vocabulary embeddings), after ingestion introduces new custom types, when switching embedding models (regenerate), or for inconsistency fixes (force regeneration if corrupted). Performance: ~100-200ms per embedding (OpenAI), ~20-50ms per embedding (local models), parallel generation (batches of 10).

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

Show category similarity scores for a specific relationship type (ADR-047). Displays assigned category, confidence score (calculated as max_score/second_max_score * 100), ambiguous flag (set when runner-up within 20% of winner), runner-up category if ambiguous, and similarity to all category seeds (0-100%) sorted by similarity with visual bar chart. Use this to verify auto-categorization makes sense, debug low confidence assignments, understand why confidence is low, resolve ambiguity between close categories, and audit all types for misassignments.

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., CAUSES, ENABLES)

### refresh-categories

Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053). As of ADR-053, new edge types are automatically categorized during ingestion, so this command is primarily needed when category seeds change. Use when category seed definitions are updated (seeds currently defined in code, future: database-configurable), after embedding model changes, or for migrating pre-ADR-053 uncategorized types. This is a non-destructive operation (doesn't affect edges), preserves manual assignments, and records audit trail per type.

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed (excludes manual assignments) | - |

### similar

Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation. Use --limit to control results (1-100, default 10). Similar types with high similarity (>0.90) are strong merge candidates for vocabulary consolidation (ADR-052).

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

Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity - useful for understanding semantic range and antonyms. Use --limit to control results (1-100, default 5).

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

Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit, similar types in same/other categories, and detects potential miscategorization. Use this to verify auto-categorization accuracy and identify types that may need reclassification.

**Usage:**
```bash
kg analyze <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., STORES)

### config

Show or update vocabulary configuration. No args: display config table. With args: update properties directly using database key names (e.g., "kg vocab config vocab_max 275 vocab_emergency 350"). Property names shown in config table.

**Usage:**
```bash
kg config [properties]
```

**Arguments:**

- `<properties>` - Property assignments: key value [key value...]

### config-update

[DEPRECATED: Use `kg vocab config <property> <value>` instead] Update vocabulary configuration settings. Supports updating multiple properties at once including thresholds (min, max, emergency), pruning mode (naive, hitl, aitl), aggressiveness profile, synonym thresholds, auto-expand setting, and consolidation threshold. Changes are persisted to database and take effect immediately. Use this for runtime threshold adjustments, switching pruning modes, changing aggressiveness profiles, tuning synonym detection, and enabling/disabling auto-expand.

**Usage:**
```bash
kg config-update [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--min <n>` | Minimum vocabulary size (e.g., 30) | - |
| `--max <n>` | Maximum vocabulary size (e.g., 225-275) | - |
| `--emergency <n>` | Emergency threshold (e.g., 300-400) | - |
| `--mode <mode>` | Pruning mode: naive, hitl, aitl | - |
| `--profile <name>` | Aggressiveness profile name | - |
| `--auto-expand` | Enable automatic expansion | - |
| `--no-auto-expand` | Disable automatic expansion | - |
| `--synonym-strong <n>` | Strong synonym threshold (0.7-1.0) | - |
| `--synonym-moderate <n>` | Moderate synonym threshold (0.5-0.9) | - |
| `--low-value <n>` | Low value score threshold (0.0-10.0) | - |
| `--consolidation-threshold <n>` | Auto-merge threshold (0.5-1.0) | - |

### profiles

List all aggressiveness profiles including builtin profiles (8 predefined Bezier curves) and custom profiles (user-created curves). Shows profile name, control points (x1, y1, x2, y2 for cubic Bezier), description, and builtin flag. Use this to view available profiles for configuration, review custom profiles, understand Bezier curve parameters, and identify profiles for deletion. Builtin profiles: linear, ease, ease-in, ease-out, ease-in-out, aggressive (recommended), gentle, exponential.

**Usage:**
```bash
kg profiles [options]
```

### profiles-show

Show details for a specific aggressiveness profile including full Bezier curve parameters, description, builtin status, and timestamps. Use this to inspect profile details before using, verify control point values, understand profile behavior, and check creation/update times.

**Usage:**
```bash
kg profiles-show <name>
```

**Arguments:**

- `<name>` - Profile name

### profiles-create

Create a custom aggressiveness profile with Bezier curve parameters. Profiles control how aggressively vocabulary consolidation operates as size approaches thresholds. Bezier curve defined by two control points (x1, y1) and (x2, y2) where X is normalized vocabulary size (0.0-1.0) and Y is aggressiveness multiplier. Use this to create deployment-specific curves, experiment with consolidation behavior, tune for specific vocabulary growth patterns, and optimize for production workloads. Cannot overwrite builtin profiles.

**Usage:**
```bash
kg profiles-create [options]
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

### profiles-delete

Delete a custom aggressiveness profile. Removes the profile permanently from the database. Cannot delete builtin profiles (protected by database trigger). Use this to remove unused custom profiles, clean up experimental curves, and maintain profile list. Safety: builtin profiles cannot be deleted, atomic operation, immediate effect.

**Usage:**
```bash
kg profiles-delete <name>
```

**Arguments:**

- `<name>` - Profile name to delete

### epistemic-status

Epistemic status classification for vocabulary types (ADR-065 Phase 2). Shows knowledge validation state based on grounding patterns: WELL_GROUNDED (avg >0.8, well-established), MIXED_GROUNDING (0.15-0.8, variable validation), WEAK_GROUNDING (0.0-0.15, emerging evidence), POORLY_GROUNDED (-0.5-0.0, uncertain), CONTRADICTED (<-0.5, refuted), HISTORICAL (temporal vocabulary), INSUFFICIENT_DATA (<3 measurements). Results are temporal measurements that change as graph evolves. Use for filtering relationships by epistemic reliability, identifying contested knowledge, tracking knowledge validation trends, and curating high-confidence vs exploratory subgraphs.

**Usage:**
```bash
kg epistemic-status [options]
```

**Subcommands:**

- `list` - List all vocabulary types with their epistemic status classifications and statistics. Shows TYPE, STATUS (color-coded), AVG GROUNDING (reliability score), SAMPLED (edges analyzed), and MEASURED AT (timestamp). Filter by status using --status flag. Sorted by highest grounding first. Use for overview of epistemic landscape, finding high-confidence types for critical queries, identifying contested/contradictory types needing review, and tracking temporal evolution of knowledge validation.
- `show` - Show detailed epistemic status for a specific vocabulary type including full grounding statistics, measurement timestamp, and rationale. Displays classification (WELL_GROUNDED/MIXED_GROUNDING/etc.), average grounding (reliability), standard deviation (consistency), min/max range (outliers), sample sizes (measurement scope), total edges (population), and measurement timestamp (temporal context). Use for deep-diving on specific types, understanding classification rationale, verifying measurement quality, and tracking individual type evolution.
- `measure` - Run epistemic status measurement for all vocabulary types (ADR-065 Phase 2). Samples edges (default 100 per type), calculates grounding dynamically for target concepts (bounded recursion), classifies epistemic patterns (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL), and optionally stores results to VocabType nodes. Measurement is temporal and observer-dependent - results change as graph evolves. Use --sample-size to control precision vs speed (larger samples = more accurate but slower), --no-store for analysis without persistence, --verbose for detailed statistics. This enables Phase 2 query filtering via GraphQueryFacade.match_concept_relationships().

---

#### list

List all vocabulary types with their epistemic status classifications and statistics. Shows TYPE, STATUS (color-coded), AVG GROUNDING (reliability score), SAMPLED (edges analyzed), and MEASURED AT (timestamp). Filter by status using --status flag. Sorted by highest grounding first. Use for overview of epistemic landscape, finding high-confidence types for critical queries, identifying contested/contradictory types needing review, and tracking temporal evolution of knowledge validation.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--status <status>` | Filter by status: WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, POORLY_GROUNDED, CONTRADICTED, HISTORICAL, INSUFFICIENT_DATA | - |

#### show

Show detailed epistemic status for a specific vocabulary type including full grounding statistics, measurement timestamp, and rationale. Displays classification (WELL_GROUNDED/MIXED_GROUNDING/etc.), average grounding (reliability), standard deviation (consistency), min/max range (outliers), sample sizes (measurement scope), total edges (population), and measurement timestamp (temporal context). Use for deep-diving on specific types, understanding classification rationale, verifying measurement quality, and tracking individual type evolution.

**Usage:**
```bash
kg show <type>
```

**Arguments:**

- `<type>` - Relationship type to show (e.g., IMPLIES, SUPPORTS)

#### measure

Run epistemic status measurement for all vocabulary types (ADR-065 Phase 2). Samples edges (default 100 per type), calculates grounding dynamically for target concepts (bounded recursion), classifies epistemic patterns (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL), and optionally stores results to VocabType nodes. Measurement is temporal and observer-dependent - results change as graph evolves. Use --sample-size to control precision vs speed (larger samples = more accurate but slower), --no-store for analysis without persistence, --verbose for detailed statistics. This enables Phase 2 query filtering via GraphQueryFacade.match_concept_relationships().

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

Sync missing edge types from graph to vocabulary (ADR-077). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

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


## admin

System administration and management - health monitoring, backup/restore, database operations, user/RBAC management, AI model configuration (requires authentication for destructive operations)

**Usage:**
```bash
kg admin [options]
```

**Subcommands:**

- `status` - Show comprehensive system health status (Docker containers, database connections, environment configuration, job scheduler)
- `backup` - Create database backup (ADR-036) - full system or per-ontology, in restorable JSON or Gephi GEXF format
- `list-backups` - List available backup files from configured directory
- `restore` - Restore a database backup (requires authentication)
- `scheduler` - Job scheduler management (ADR-014 job queue) - monitor worker status, cleanup stale jobs
- `user` - User management commands (admin only)
- `rbac` - Manage roles, permissions, and access control (ADR-028)
- `embedding` - Manage embedding model configuration (ADR-039)
- `extraction` - Manage AI extraction model configuration (ADR-041)
- `keys` - Manage API keys for AI providers (ADR-031, ADR-041)

---

### status

Show comprehensive system health status (Docker containers, database connections, environment configuration, job scheduler)

**Usage:**
```bash
kg status [options]
```

### backup

Create database backup (ADR-036) - full system or per-ontology, in restorable JSON or Gephi GEXF format

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
| `--format <format>` | Export format: "json" (native, restorable) or "gexf" (Gephi visualization - not restorable) | `"json"` |

### list-backups

List available backup files from configured directory

**Usage:**
```bash
kg list-backups [options]
```

### restore

Restore a database backup (requires authentication)

**Usage:**
```bash
kg restore [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--file <name>` | Backup filename (from configured directory) | - |
| `--path <path>` | Custom backup file path (overrides configured directory) | - |
| `--merge` | Merge into existing ontology if it exists (default: error if ontology exists) | `false` |
| `--deps <action>` | How to handle external dependencies: prune, stitch, defer | `"prune"` |

### scheduler

Job scheduler management (ADR-014 job queue) - monitor worker status, cleanup stale jobs

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

Manage roles, permissions, and access control (ADR-028)

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

Manage embedding model configuration (ADR-039)

**Usage:**
```bash
kg embedding [options]
```

**Subcommands:**

- `list` - List all embedding configurations
- `create` - Create a new embedding configuration (inactive)
- `activate` - Activate an embedding configuration (with automatic protection)
- `reload` - Hot reload embedding model (zero-downtime)
- `protect` - Enable protection flags on an embedding configuration
- `unprotect` - Disable protection flags on an embedding configuration
- `delete` - Delete an embedding configuration
- `status` - Show comprehensive embedding coverage across all graph text entities with hash verification
- `regenerate` - Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-068 Phase 4) - useful after changing embedding model or repairing missing embeddings

---

#### list

List all embedding configurations

**Usage:**
```bash
kg list [options]
```

#### create

Create a new embedding configuration (inactive)

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--provider <provider>` | Provider: local or openai | - |
| `--model <model>` | Model name | - |
| `--dimensions <dims>` | Embedding dimensions | - |
| `--precision <precision>` | Precision: float16, float32, int8 | - |
| `--device <device>` | Device: cpu, cuda, mps | - |
| `--memory <mb>` | Max memory in MB | - |
| `--threads <n>` | Number of threads | - |
| `--batch-size <n>` | Batch size | - |

#### activate

Activate an embedding configuration (with automatic protection)

**Usage:**
```bash
kg activate <config-id>
```

**Arguments:**

- `<config-id>` - Configuration ID

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

Enable protection flags on an embedding configuration

**Usage:**
```bash
kg protect <config-id>
```

**Arguments:**

- `<config-id>` - Configuration ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--delete` | Enable delete protection | - |
| `--change` | Enable change protection | - |

#### unprotect

Disable protection flags on an embedding configuration

**Usage:**
```bash
kg unprotect <config-id>
```

**Arguments:**

- `<config-id>` - Configuration ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--delete` | Disable delete protection | - |
| `--change` | Disable change protection | - |

#### delete

Delete an embedding configuration

**Usage:**
```bash
kg delete <config-id>
```

**Arguments:**

- `<config-id>` - Configuration ID

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

Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-068 Phase 4) - useful after changing embedding model or repairing missing embeddings

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

Manage AI extraction model configuration (ADR-041)

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

### keys

Manage API keys for AI providers (ADR-031, ADR-041)

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

