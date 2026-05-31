# kg batch

> Auto-generated

## batch (b)

Batch operations for creating concepts and edges in a single transaction. Import JSON files that define concepts and their relationships. All operations are atomic - if any item fails, the entire batch is rolled back.

**Usage:**
```bash
kg batch [options]
```

**Subcommands:**

- `create` - Import a batch JSON file to create concepts and edges atomically. The JSON must contain ontology, concepts array, and optional edges array. All operations succeed or all are rolled back.
- `template` - Output a template batch JSON file to stdout. Redirect to a file to customize.

---

### create

Import a batch JSON file to create concepts and edges atomically. The JSON must contain ontology, concepts array, and optional edges array. All operations succeed or all are rolled back.

**Usage:**
```bash
kg create <file>
```

**Arguments:**

- `<file>` - Path to batch JSON file

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output result as JSON | - |
| `--dry-run` | Validate without creating (not yet implemented) | - |

### template

Output a template batch JSON file to stdout. Redirect to a file to customize.

**Usage:**
```bash
kg template [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--with-edges` | Include example edges in template | - |
