# CLI Command Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from CLI source code.
> Last updated: 2025-10-28

---

## Commands

- [`health`](#health) - Check API server health
- [`config` (cfg)](#config) - Manage kg CLI configuration
- [`ingest`](#ingest) - Ingest documents into the knowledge graph
- [`search`](#search) - Search for concepts and explore the graph
- [`database` (db)](#database) - Database operations and information
- [`ontology` (onto)](#ontology) - Manage ontologies (knowledge domains)
- [`vocabulary` (vocab)](#vocabulary) - Edge vocabulary management and consolidation (ADR-032)
- [`admin`](#admin) - System administration (status, backup, restore, reset, scheduler, user, rbac, embedding, extraction, keys, regenerate-embeddings)

---

## health

Check API server health

**Usage:**
```bash
kg health [options]
```


## config (cfg)

Manage kg CLI configuration

**Usage:**
```bash
kg config [options]
```

**Subcommands:**

- `get` - Get configuration value(s)
- `set` - Set configuration value
- `delete` - Delete configuration key
- `list` - List all configuration
- `path` - Show configuration file path
- `init` - Initialize configuration file with defaults
- `reset` - Reset configuration to defaults
- `enable-mcp` - Enable an MCP tool
- `disable-mcp` - Disable an MCP tool
- `mcp` - Show MCP tool configuration
- `auto-approve` - Enable/disable auto-approval of jobs (ADR-014)
- `update-secret` - Authenticate and update API secret/key
- `json` - JSON-based configuration operations (machine-friendly)

---

### get

Get configuration value(s)

**Usage:**
```bash
kg get [key]
```

**Arguments:**

- `<key>` - Configuration key (supports dot notation, e.g., "mcp.enabled")

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### set

Set configuration value

**Usage:**
```bash
kg set <key> <value>
```

**Arguments:**

- `<key>` - Configuration key (supports dot notation)
- `<value>` - Value to set (auto-detects JSON arrays/objects)

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

### enable-mcp

Enable an MCP tool

**Usage:**
```bash
kg enable-mcp <tool>
```

**Arguments:**

- `<tool>` - MCP tool name

### disable-mcp

Disable an MCP tool

**Usage:**
```bash
kg disable-mcp <tool>
```

**Arguments:**

- `<tool>` - MCP tool name

### mcp

Show MCP tool configuration

**Usage:**
```bash
kg mcp [tool]
```

**Arguments:**

- `<tool>` - Specific MCP tool name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### auto-approve

Enable/disable auto-approval of jobs (ADR-014)

**Usage:**
```bash
kg auto-approve [value]
```

**Arguments:**

- `<value>` - Enable (true/on/yes) or disable (false/off/no)

### update-secret

Authenticate and update API secret/key

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


## ingest

Ingest documents into the knowledge graph

**Usage:**
```bash
kg ingest [options]
```

**Subcommands:**

- `file` - Ingest a document file
- `directory` - Ingest all matching files from a directory
- `text` - Ingest raw text

---

### file

Ingest a document file

**Usage:**
```bash
kg file <path>
```

**Arguments:**

- `<path>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--filename <name>` | Override filename for tracking | - |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |

### directory

Ingest all matching files from a directory

**Usage:**
```bash
kg directory <dir>
```

**Arguments:**

- `<dir>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name (required unless --directories-as-ontologies) | - |
| `-p, --pattern <patterns...>` | File patterns to match (e.g., *.md *.txt) | `["*.md","*.txt"]` |
| `-r, --recurse` | Recursively scan subdirectories | `false` |
| `-d, --depth <n>` | Maximum recursion depth (number or "all") | `"0"` |
| `--directories-as-ontologies` | Use directory names as ontology names | `false` |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--dry-run` | Show what would be ingested without submitting jobs | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `--overlap-words <n>` | Overlap between chunks | `"200"` |

### text

Ingest raw text

**Usage:**
```bash
kg text <text>
```

**Arguments:**

- `<text>` - Required

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Ontology/collection name | - |
| `-f, --force` | Force re-ingestion even if duplicate | `false` |
| `--no-approve` | Require manual approval before processing (default: auto-approve) | - |
| `--parallel` | Process in parallel (default: serial for clean concept matching) | `false` |
| `--filename <name>` | Filename for tracking | `"text_input"` |
| `--target-words <n>` | Target words per chunk | `"1000"` |
| `-w, --wait` | Wait for job completion (default: submit and exit) | `false` |


## search

Search for concepts and explore the graph

**Usage:**
```bash
kg search [options]
```

**Subcommands:**

- `query` - Search for concepts using natural language
- `details` - Get detailed information about a concept
- `related` - Find concepts related through graph traversal
- `connect` - Find shortest path between two concepts using IDs or semantic phrase matching

---

### query

Search for concepts using natural language

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - Search query text

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum results | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0) | `"0.7"` |
| `--show-evidence` | Show sample evidence quotes from source text | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |

### details

Get detailed information about a concept

**Usage:**
```bash
kg details <concept-id>
```

**Arguments:**

- `<concept-id>` - Concept ID to retrieve

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |

### related

Find concepts related through graph traversal

**Usage:**
```bash
kg related <concept-id>
```

**Arguments:**

- `<concept-id>` - Starting concept ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --depth <number>` | Maximum traversal depth (1-5) | `"2"` |
| `-t, --types <types...>` | Filter by relationship types | - |
| `--json` | Output raw JSON instead of formatted text | - |

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
| `--show-evidence` | Show sample evidence quotes for each concept in paths | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |


## database (db)

Database operations and information

**Usage:**
```bash
kg database [options]
```

**Subcommands:**

- `stats` - Show database statistics
- `info` - Show database connection information
- `health` - Check database health and connectivity

---

### stats

Show database statistics

**Usage:**
```bash
kg stats [options]
```

### info

Show database connection information

**Usage:**
```bash
kg info [options]
```

### health

Check database health and connectivity

**Usage:**
```bash
kg health [options]
```


## ontology (onto)

Manage ontologies (knowledge domains)

**Usage:**
```bash
kg ontology [options]
```

**Subcommands:**

- `list` - List all ontologies
- `info` - Get detailed information about an ontology
- `files` - List files in an ontology
- `rename` - Rename an ontology
- `delete` - Delete an ontology and all its data

---

### list

List all ontologies

**Usage:**
```bash
kg list [options]
```

### info

Get detailed information about an ontology

**Usage:**
```bash
kg info <name>
```

**Arguments:**

- `<name>` - Ontology name

### files

List files in an ontology

**Usage:**
```bash
kg files <name>
```

**Arguments:**

- `<name>` - Ontology name

### rename

Rename an ontology

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

Delete an ontology and all its data

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

Edge vocabulary management and consolidation (ADR-032)

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status and zone
- `list` - List all edge types with statistics
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL)
- `merge` - Manually merge one edge type into another
- `generate-embeddings` - Generate embeddings for vocabulary types
- `category-scores` - Show category similarity scores for a relationship type (ADR-047)
- `refresh-categories` - Refresh category assignments for vocabulary types (ADR-047)

---

### status

Show current vocabulary status and zone

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL)

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

### merge

Manually merge one edge type into another

**Usage:**
```bash
kg merge <deprecated-type> <target-type>
```

**Arguments:**

- `<deprecated-type>` - Edge type to deprecate
- `<target-type>` - Target edge type to merge into

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --reason <text>` | Reason for merge | - |
| `-u, --user <email>` | User performing the merge | `"cli-user"` |

### generate-embeddings

Generate embeddings for vocabulary types

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

Show category similarity scores for a relationship type (ADR-047)

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., ENHANCES)

### refresh-categories

Refresh category assignments for vocabulary types (ADR-047)

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed (default: all active types) | - |


## admin

System administration (status, backup, restore, reset, scheduler, user, rbac, embedding, extraction, keys, regenerate-embeddings)

**Usage:**
```bash
kg admin [options]
```

**Subcommands:**

- `status` - Show system status (Docker, database, environment)
- `backup` - Create a database backup
- `list-backups` - List available backup files from configured directory
- `restore` - Restore a database backup (requires authentication)
- `reset` - Reset database - DESTRUCTIVE (requires authentication)
- `scheduler` - Job scheduler management (ADR-014)
- `regenerate-embeddings` - Regenerate embeddings for concept nodes in the graph
- `user` - User management commands (admin only)
- `rbac` - Manage roles, permissions, and access control (ADR-028)
- `embedding` - Manage embedding model configuration (ADR-039)
- `extraction` - Manage AI extraction model configuration (ADR-041)
- `keys` - Manage API keys for AI providers (ADR-031, ADR-041)

---

### status

Show system status (Docker, database, environment)

**Usage:**
```bash
kg status [options]
```

### backup

Create a database backup

**Usage:**
```bash
kg backup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Backup type: "full" or "ontology" | - |
| `--ontology <name>` | Ontology name (required if type is ontology) | - |
| `--output <filename>` | Custom output filename | - |
| `--format <format>` | Export format: "json" (native, restorable) or "gexf" (Gephi visualization) | `"json"` |

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

### reset

Reset database - DESTRUCTIVE (requires authentication)

**Usage:**
```bash
kg reset [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-logs` | Do not clear log files | - |
| `--no-checkpoints` | Do not clear checkpoint files | - |

### scheduler

Job scheduler management (ADR-014)

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

### regenerate-embeddings

Regenerate embeddings for concept nodes in the graph

**Usage:**
```bash
kg regenerate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--concepts` | Regenerate concept embeddings (default if no options) | `true` |
| `--only-missing` | Only generate for concepts without embeddings | `false` |
| `--ontology <name>` | Limit to specific ontology | - |
| `--limit <n>` | Maximum number of concepts to process (for testing) | - |

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

