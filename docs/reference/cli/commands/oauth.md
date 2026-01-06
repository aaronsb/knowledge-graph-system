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
