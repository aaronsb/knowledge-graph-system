# kg concept

> Auto-generated

## concept (c)

Create, list, show, and delete concepts. Concepts are the fundamental nodes in the knowledge graph. When creating concepts, the description is embedded and similarity-matched against existing concepts (same as automatic ingestion). Use matching modes to control duplicate handling.

**Usage:**
```bash
kg concept [options]
```

**Subcommands:**

- `list` - List concepts with optional filters. Shows concept ID, label, ontology, and creation method.
- `show` - Show detailed information about a concept by ID.
- `create` - Create a new concept. Description is embedded and similarity-matched against existing concepts.
- `delete` - Delete a concept by ID. Requires --force flag or interactive confirmation.

---

### list

List concepts with optional filters. Shows concept ID, label, ontology, and creation method.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--ontology <name>` | Filter by ontology | - |
| `--label <text>` | Filter by label (contains) | - |
| `--creation-method <method>` | Filter by creation method (cli, mcp, api, llm_extraction, import) | - |
| `--limit <n>` | Maximum results (default: 50) | `"50"` |
| `--offset <n>` | Pagination offset | `"0"` |
| `--json` | Output as JSON | - |

### show

Show detailed information about a concept by ID.

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Concept ID (e.g., c_abc123)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output as JSON | - |

### create

Create a new concept. Description is embedded and similarity-matched against existing concepts.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--label <name>` | Concept label (required) | - |
| `--ontology <name>` | Target ontology (required) | - |
| `--description <text>` | Concept description (used for embedding match) | - |
| `--search-terms <terms>` | Comma-separated search terms | - |
| `--matching-mode <mode>` | auto|force_create|match_only (default: auto) | `"auto"` |
| `--json` | Output as JSON | - |
| `-i, --interactive` | Guided wizard mode | - |
| `-y, --yes` | Skip confirmation prompts | - |

### delete

Delete a concept by ID. Requires --force flag or interactive confirmation.

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Concept ID to delete

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--cascade` | Also delete orphaned synthetic sources | - |
| `-f, --force` | Skip confirmation | - |
| `--json` | Output as JSON | - |
