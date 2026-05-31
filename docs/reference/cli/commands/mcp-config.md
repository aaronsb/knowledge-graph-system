# kg mcp-config

> Auto-generated

## mcp-config

Manage path allowlist for secure file/directory ingestion from MCP server.

Security Model (ADR-062):
- Fail-secure validation (blocked patterns checked first)
- Explicit allowlist (no access without configuration)
- CLI-only management (agent can read, not write)
- Path resolution prevents traversal attacks

Configuration stored in: ~/.config/kg/mcp-allowed-paths.json

**Usage:**
```bash
kg mcp-config [options]
```

**Subcommands:**

- `init-allowlist` - Initialize allowlist with safe defaults
- `allow-dir` - Add allowed directory
- `remove-dir` - Remove allowed directory
- `allow-pattern` - Add allowed file pattern
- `remove-pattern` - Remove allowed file pattern
- `block-pattern` - Add blocked file pattern (security)
- `unblock-pattern` - Remove blocked file pattern
- `show-allowlist` - Show current allowlist configuration
- `test-path` - Test if a path would be allowed
- `oauth` - Create OAuth client for MCP server

---

### init-allowlist

Initialize allowlist with safe defaults

**Usage:**
```bash
kg init-allowlist [options]
```

### allow-dir

Add allowed directory

**Usage:**
```bash
kg allow-dir <directory>
```

**Arguments:**

- `<directory>` - Directory path (supports ~ and glob patterns like ~/Projects/*/docs)

### remove-dir

Remove allowed directory

**Usage:**
```bash
kg remove-dir <directory>
```

**Arguments:**

- `<directory>` - Directory path to remove

### allow-pattern

Add allowed file pattern

**Usage:**
```bash
kg allow-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Glob pattern (e.g., "**/*.md", "**/*.png")

### remove-pattern

Remove allowed file pattern

**Usage:**
```bash
kg remove-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Pattern to remove

### block-pattern

Add blocked file pattern (security)

**Usage:**
```bash
kg block-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Glob pattern to block (e.g., "**/.env*", "**/*.key")

### unblock-pattern

Remove blocked file pattern

**Usage:**
```bash
kg unblock-pattern <pattern>
```

**Arguments:**

- `<pattern>` - Pattern to unblock

### show-allowlist

Show current allowlist configuration

**Usage:**
```bash
kg show-allowlist [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### test-path

Test if a path would be allowed

**Usage:**
```bash
kg test-path <path>
```

**Arguments:**

- `<path>` - File or directory path to test

### oauth

Create OAuth client for MCP server

**Usage:**
```bash
kg oauth [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Custom client name | - |
