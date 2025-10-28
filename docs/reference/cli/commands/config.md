# kg config

> Auto-generated

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
- `enable-mcp` - Enable an MCP tool
- `disable-mcp` - Disable an MCP tool
- `mcp` - Show MCP tool configuration status. Lists all MCP tools with enabled/disabled status and descriptions. Specify a tool name to see details for that tool.
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

Show MCP tool configuration status. Lists all MCP tools with enabled/disabled status and descriptions. Specify a tool name to see details for that tool.

**Usage:**
```bash
kg mcp [tool]
```

**Arguments:**

- `<tool>` - Specific MCP tool name (optional). Omit to show all MCP tools.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

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
