# kg config json

JSON-based configuration operations for machine-friendly workflows.

## Usage

```bash
kg config json [options] [command]
```

## Description

The `json` subcommand provides machine-friendly JSON-based operations for configuration management. This is ideal for:
- Automation scripts
- Configuration backups and restores
- Programmatic configuration management
- CI/CD pipelines

Unlike the human-friendly commands (`get`, `set`, `list`), these commands work exclusively with JSON input/output.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `get` | Get entire configuration as JSON | [↓](#get) |
| `set <json>` | Set configuration from JSON (full or partial) | [↓](#set) |
| `dto` | Output configuration template/schema | [↓](#dto) |

---

## Subcommand Details

### get

Get the entire configuration as JSON.

**Usage:**
```bash
kg config json get
```

**Output Example:**
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

**Examples:**
```bash
# Save configuration to file
kg config json get > config-backup.json

# View specific value with jq
kg config json get | jq '.apiUrl'
```

---

### set

Set configuration from JSON (full or partial).

**Usage:**
```bash
kg config json set <json>
```

Accepts either:
- **Full configuration:** Replaces entire config
- **Partial configuration:** Merges with existing config

**Examples:**

**Full Configuration:**
```bash
kg config json set '{
  "apiUrl": "https://api.example.com",
  "clientId": "tenant-123",
  "apiKey": "secret-key",
  "autoApprove": true,
  "mcp": {
    "enabled": {
      "search": true,
      "ingest": false
    }
  }
}'
```

**Partial Configuration:**
```bash
# Update just API URL
kg config json set '{"apiUrl": "https://new-api.com"}'

# Update multiple values
kg config json set '{
  "apiUrl": "https://api.example.com",
  "autoApprove": true
}'
```

**From File:**
```bash
# Restore from backup
kg config json set "$(cat config-backup.json)"

# Use with pipes
cat config-template.json | jq '.apiUrl = "https://prod.api.com"' | xargs -0 kg config json set
```

---

### dto

Output configuration template/schema showing all available keys and types.

**Usage:**
```bash
kg config json dto
```

**Output Example:**
```json
{
  "apiUrl": "string",
  "clientId": "string | null",
  "apiKey": "string | null",
  "autoApprove": "boolean",
  "mcp": {
    "enabled": {
      "<tool-name>": "boolean"
    }
  }
}
```

This is useful for:
- Understanding the configuration structure
- Generating configuration templates
- Documentation
- Validation

**Examples:**
```bash
# Generate template
kg config json dto > config-template.json

# View schema
kg config json dto | jq
```

---

## Common Use Cases

### Configuration Backup and Restore

```bash
# Backup
kg config json get > config-$(date +%Y%m%d).json

# Restore
kg config json set "$(cat config-20240115.json)"
```

### Environment-Specific Configuration

```bash
# Development
kg config json set '{
  "apiUrl": "http://localhost:8000",
  "autoApprove": true
}'

# Staging
kg config json set '{
  "apiUrl": "https://staging-api.example.com",
  "autoApprove": false
}'

# Production
kg config json set '{
  "apiUrl": "https://api.example.com",
  "clientId": "prod-tenant",
  "autoApprove": false
}'
```

### Scripted Configuration

```bash
#!/bin/bash

# Generate config programmatically
CONFIG=$(jq -n \
  --arg api "$API_URL" \
  --arg client "$CLIENT_ID" \
  --arg key "$API_KEY" \
  '{
    apiUrl: $api,
    clientId: $client,
    apiKey: $key,
    autoApprove: false
  }')

# Apply configuration
kg config json set "$CONFIG"
```

### Configuration Migration

```bash
# Export from old server
ssh old-server "kg config json get" > old-config.json

# Transform configuration
jq '.apiUrl = "https://new-server.com"' old-config.json > new-config.json

# Import to new server
kg config json set "$(cat new-config.json)"
```

### Validation

```bash
# Get current config
CURRENT=$(kg config json get)

# Get template
TEMPLATE=$(kg config json dto)

# Validate structure (using external tool)
echo "$CURRENT" | validate-json --schema "$TEMPLATE"
```

---

## JSON Schema

The configuration follows this structure:

```typescript
{
  apiUrl: string;           // API base URL
  clientId?: string | null;  // Multi-tenancy client ID
  apiKey?: string | null;    // Authentication key
  autoApprove: boolean;     // Auto-approve jobs (ADR-014)
  mcp: {
    enabled: {
      [toolName: string]: boolean;  // MCP tool enable/disable
    }
  }
}
```

---

## Error Handling

### Invalid JSON

```bash
$ kg config json set 'invalid json'
Error: Invalid JSON: Unexpected token i in JSON at position 0
```

### Missing Required Fields

Partial updates are allowed, but a full replacement must include all required fields:

```bash
# Valid - partial update
kg config json set '{"apiUrl": "https://new-api.com"}'

# Valid - full config with all fields
kg config json set '{
  "apiUrl": "https://api.com",
  "clientId": null,
  "apiKey": null,
  "autoApprove": false,
  "mcp": {"enabled": {}}
}'
```

---

## Related Commands

- [`kg config`](../) - Human-friendly configuration commands
- [`kg config get`](../#get) - Get individual values
- [`kg config set`](../#set) - Set individual values
- [`kg config path`](../#path) - Show config file location

---

## See Also

- [Configuration Guide](../../../02-configuration/)
- [Automation Guide](../../../03-integration/automation.md)
- [CI/CD Integration](../../../03-integration/cicd.md)
