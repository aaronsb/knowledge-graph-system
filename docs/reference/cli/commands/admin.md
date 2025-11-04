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
- `restore` - Restore a database backup (requires authentication)
- `scheduler` - Job scheduler management (ADR-014 job queue) - monitor worker status, cleanup stale jobs
- `regenerate-embeddings` - Regenerate vector embeddings for concept nodes in the graph (useful after changing embedding model or repairing missing embeddings)
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

### regenerate-embeddings

Regenerate vector embeddings for concept nodes in the graph (useful after changing embedding model or repairing missing embeddings)

**Usage:**
```bash
kg regenerate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--concepts` | Regenerate concept embeddings (default if no options specified) | `true` |
| `--only-missing` | Only generate for concepts without embeddings (skip existing) | `false` |
| `--ontology <name>` | Limit regeneration to specific ontology namespace | - |
| `--limit <n>` | Maximum number of concepts to process (useful for testing/batching) | - |

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
