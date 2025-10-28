# kg vocabulary

> Auto-generated

## vocabulary (vocab)

Edge vocabulary management and consolidation (ADR-032)

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status and zone
- `list` - List all edge types with statistics
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL)
- `merge` - Manually merge one edge type into another
- `generate-embeddings` - Generate embeddings for vocabulary types
- `category-scores` - Show category similarity scores for a relationship type (ADR-047)
- `refresh-categories` - Refresh category assignments for vocabulary types (ADR-047)

---

### status

Show current vocabulary status and zone

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL)

**Usage:**
```bash
kg consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `"90"` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `"0.90"` |
| `--dry-run` | Evaluate candidates without executing merges | - |
| `--auto` | Auto-execute high confidence merges (AITL mode) | - |

### merge

Manually merge one edge type into another

**Usage:**
```bash
kg merge <deprecated-type> <target-type>
```

**Arguments:**

- `<deprecated-type>` - Edge type to deprecate
- `<target-type>` - Target edge type to merge into

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --reason <text>` | Reason for merge | - |
| `-u, --user <email>` | User performing the merge | `"cli-user"` |

### generate-embeddings

Generate embeddings for vocabulary types

**Usage:**
```bash
kg generate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Regenerate ALL embeddings regardless of existing state | - |
| `--all` | Process all active types (not just missing) | - |

### category-scores

Show category similarity scores for a relationship type (ADR-047)

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., ENHANCES)

### refresh-categories

Refresh category assignments for vocabulary types (ADR-047)

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed (default: all active types) | - |
