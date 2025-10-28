# kg config

> Auto-generated

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
