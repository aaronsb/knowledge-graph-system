# kg admin

> Auto-generated

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
- `restore` - Restore a database backup (uses OAuth authentication)
- `scheduler` - Job scheduler management (ADR-014 job queue) - monitor worker status, cleanup stale jobs
- `workers` - Worker lane management (ADR-100) - monitor slot utilization, queue depth, active jobs
- `user` - User management commands (admin only)
- `rbac` - Manage roles, permissions, and access control (ADR-028)
- `embedding` - Manage embedding profiles (text + image model configuration)
- `extraction` - Manage AI extraction model configuration (ADR-041)
- `vision` - Manage the vision (image->prose) provider (ADR-802)
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
| `--merge` | Merge into existing ontology if it exists (default: error if ontology exists) | `false` |
| `--deps <action>` | How to handle external dependencies: prune, stitch, defer | `"prune"` |
| `--confirm` | Confirm restore operation (required for non-interactive use) | `false` |

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
- `regenerate` - Regenerate vector embeddings for all graph text entities: concepts, sources, vocabulary (ADR-068 Phase 4) - useful after changing embedding model or repairing missing embeddings

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
