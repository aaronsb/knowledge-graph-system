# kg query-def

> Auto-generated

## query-def (qd)

Manage saved query definitions - recipes that can be re-executed to generate artifacts. Supports block diagrams, cypher queries, searches, polarity analyses, and connection paths.

**Usage:**
```bash
kg query-def [options]
```

**Subcommands:**

- `list` - List query definitions
- `show` - Show a query definition
- `create` - Create a query definition
- `delete` - Delete a query definition

---

### list

List query definitions

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Filter by type (block_diagram, cypher, search, polarity, connection) | - |
| `-l, --limit <n>` | Maximum to return | `"20"` |

### show

Show a query definition

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Definition ID

### create

Create a query definition

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Definition name | - |
| `-t, --type <type>` | Type: block_diagram, cypher, search, polarity, connection | - |
| `-d, --definition <json>` | Definition as JSON | - |

### delete

Delete a query definition

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Definition ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | - |
