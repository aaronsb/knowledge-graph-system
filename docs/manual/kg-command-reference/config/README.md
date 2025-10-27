# kg config

Manage kg CLI configuration settings.

## Usage

```bash
kg config|cfg [options] [command]
```

**Alias:** `cfg`

## Description

The `config` command manages the kg CLI configuration file, which stores API connection settings, authentication tokens, MCP tool preferences, and other persistent settings.

Configuration is stored in a JSON file (typically `~/.kg/config.json`) and can be managed through both human-friendly commands (`get`, `set`, `list`) and machine-friendly JSON operations (`json` subcommands).

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

### Basic Configuration Management

| Command | Description | Doc |
|---------|-------------|-----|
| `get [key]` | Get configuration value(s) | [↓](#get) |
| `set <key> <value>` | Set configuration value | [↓](#set) |
| `delete <key>` | Delete configuration key | [↓](#delete) |
| `list` | List all configuration | [↓](#list) |
| `path` | Show configuration file path | [↓](#path) |
| `init` | Initialize configuration file with defaults | [↓](#init) |
| `reset` | Reset configuration to defaults | [↓](#reset) |

### MCP Tool Configuration

| Command | Description | Doc |
|---------|-------------|-----|
| `enable-mcp <tool>` | Enable an MCP tool | [↓](#enable-mcp) |
| `disable-mcp <tool>` | Disable an MCP tool | [↓](#disable-mcp) |
| `mcp [tool]` | Show MCP tool configuration | [↓](#mcp) |

### Job Approval

| Command | Description | Doc |
|---------|-------------|-----|
| `auto-approve [value]` | Enable/disable auto-approval of jobs (ADR-014) | [↓](#auto-approve) |

### Authentication

| Command | Description | Doc |
|---------|-------------|-----|
| `update-secret` | Authenticate and update API secret/key | [↓](#update-secret) |

### JSON Operations

| Command | Description | Doc |
|---------|-------------|-----|
| `json` | JSON-based configuration operations (machine-friendly) | [json/](./json/) |

## Command Tree

```
kg config (cfg)
├── get [key]
├── set <key> <value>
├── delete <key>
├── list
├── path
├── init
├── reset
├── enable-mcp <tool>
├── disable-mcp <tool>
├── mcp [tool]
├── auto-approve [value]
├── update-secret
└── json
    ├── get
    ├── set <json>
    └── dto
```

---

## Subcommand Details

### get

Get one or all configuration values.

**Usage:**
```bash
kg config get [key]
```

**Examples:**
```bash
# Get all configuration
kg config get

# Get specific value
kg config get apiUrl
kg config get client.id
```

---

### set

Set a configuration value.

**Usage:**
```bash
kg config set <key> <value>
```

**Examples:**
```bash
# Set API URL
kg config set apiUrl https://api.example.com

# Set client ID
kg config set client.id my-tenant
```

---

### delete

Delete a configuration key.

**Usage:**
```bash
kg config delete <key>
```

**Examples:**
```bash
kg config delete apiKey
```

---

### list

List all configuration keys and values.

**Usage:**
```bash
kg config list [options]
```

**Examples:**
```bash
kg config list
```

---

### path

Show the path to the configuration file.

**Usage:**
```bash
kg config path
```

**Output Example:**
```
/home/user/.kg/config.json
```

---

### init

Initialize configuration file with default values.

**Usage:**
```bash
kg config init [options]
```

Creates the configuration file if it doesn't exist and populates it with default values.

---

### reset

Reset configuration to defaults, removing all custom settings.

**Usage:**
```bash
kg config reset [options]
```

**Warning:** This will delete all custom configuration. Use with caution.

---

### enable-mcp

Enable an MCP tool.

**Usage:**
```bash
kg config enable-mcp <tool>
```

**Examples:**
```bash
kg config enable-mcp search
kg config enable-mcp ingest
```

---

### disable-mcp

Disable an MCP tool.

**Usage:**
```bash
kg config disable-mcp <tool>
```

**Examples:**
```bash
kg config disable-mcp search
```

---

### mcp

Show MCP tool configuration status.

**Usage:**
```bash
kg config mcp [options] [tool]
```

**Examples:**
```bash
# Show all MCP tools
kg config mcp

# Show specific tool
kg config mcp search
```

---

### auto-approve

Enable or disable automatic approval of ingestion jobs.

**Usage:**
```bash
kg config auto-approve [value]
```

**Values:**
- `true` / `on` / `yes` - Enable auto-approval
- `false` / `off` / `no` - Disable auto-approval
- No value - Toggle current setting

**Examples:**
```bash
# Enable auto-approval
kg config auto-approve true

# Disable auto-approval
kg config auto-approve false

# Toggle
kg config auto-approve
```

**Context:** ADR-014 introduced an approval workflow for ingestion jobs to review cost estimates before processing. Auto-approve bypasses this step.

---

### update-secret

Authenticate with username/password and update the stored API secret or key.

**Usage:**
```bash
kg config update-secret [options]
```

Prompts for username and password, then stores the authentication token in the configuration.

---

## JSON Operations

For machine-friendly configuration operations, see the [`json` subcommand documentation](./json/).

---

## Configuration File

### Location

Default: `~/.kg/config.json`

Can be overridden with `KG_CONFIG_PATH` environment variable.

### Structure

```json
{
  "apiUrl": "http://localhost:8000",
  "clientId": null,
  "apiKey": null,
  "autoApprove": false,
  "mcp": {
    "enabled": {
      "search": true,
      "ingest": true
    }
  }
}
```

### Configuration Keys

| Key | Type | Description | Default |
|-----|------|-------------|---------|
| `apiUrl` | string | API base URL | `http://localhost:8000` |
| `clientId` | string | Client ID for multi-tenancy | `null` |
| `apiKey` | string | API authentication key | `null` |
| `autoApprove` | boolean | Auto-approve ingestion jobs | `false` |
| `mcp.enabled.<tool>` | boolean | MCP tool enabled status | varies |

---

## Common Use Cases

### Initial Setup

```bash
# View current config
kg config list

# Set API URL for remote server
kg config set apiUrl https://kg-api.example.com

# Authenticate and store token
kg config update-secret
```

### Multi-Tenant Setup

```bash
# Set client ID
kg config set clientId tenant-123

# Verify
kg config get clientId
```

### Development vs Production

```bash
# Development
kg config set apiUrl http://localhost:8000

# Production
kg config set apiUrl https://api.production.com
```

### Export/Import Configuration

```bash
# Export
kg config json get > config-backup.json

# Import
kg config json set "$(cat config-backup.json)"
```

---

## Related Commands

- [`kg health`](../health/) - Verify API connectivity
- [`kg login`](../auth/#login) - Authenticate with username/password
- [`kg admin`](../admin/) - System administration

---

## See Also

- [Configuration Guide](../../02-configuration/)
- [Authentication](../../04-security-and-access/)
- [MCP Integration](../../03-integration/mcp.md)
