# kg edge

> Auto-generated

## edge (e)

Create, list, and delete edges between concepts. Edges represent relationships like IMPLIES, SUPPORTS, CONTRADICTS, etc. Use --from/--to with concept IDs or --from-label/--to-label for semantic lookup by label.

**Usage:**
```bash
kg edge [options]
```

**Subcommands:**

- `list` - List edges with optional filters.
- `create` - Create an edge between two concepts.
- `delete` - Delete an edge by its composite key (from, type, to).

---

### list

List edges with optional filters.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--from <id>` | Filter by source concept ID | - |
| `--to <id>` | Filter by target concept ID | - |
| `--type <type>` | Filter by relationship type | - |
| `--category <cat>` | Filter by category | - |
| `--limit <n>` | Maximum results (default: 50) | `"50"` |
| `--offset <n>` | Pagination offset | `"0"` |
| `--json` | Output as JSON | - |

### create

Create an edge between two concepts.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--from <id>` | Source concept ID | - |
| `--to <id>` | Target concept ID | - |
| `--from-label <text>` | Source concept (search by label) | - |
| `--to-label <text>` | Target concept (search by label) | - |
| `--type <type>` | Relationship type (e.g., IMPLIES, SUPPORTS) | - |
| `--category <cat>` | Relationship category (auto-inferred if omitted) | - |
| `--confidence <n>` | Confidence score 0-1 (default: 1.0) | `"1.0"` |
| `--create-vocab` | Create vocabulary term if it does not exist | - |
| `--json` | Output as JSON | - |
| `-i, --interactive` | Guided wizard mode | - |
| `-y, --yes` | Skip confirmation prompts | - |

### delete

Delete an edge by its composite key (from, type, to).

**Usage:**
```bash
kg delete <from> <type> <to>
```

**Arguments:**

- `<from>` - Source concept ID
- `<type>` - Relationship type
- `<to>` - Target concept ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation | - |
| `--json` | Output as JSON | - |
