# kg oauth

> Auto-generated

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
