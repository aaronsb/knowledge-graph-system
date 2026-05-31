# kg artifact

> Auto-generated

## artifact (art)

Manage artifacts - persistent storage for computed results like polarity analyses, projections, and query results. Each artifact records the graph epoch it was computed at, so the platform can tell you when one has gone stale (the graph changed underneath it) and recompute it on request (ADR-207).

This is the user-facing surface for the results you create. For backend object-storage diagnostics (S3 buckets, stored objects, integrity, retention) see the admin command "kg storage".

**Usage:**
```bash
kg artifact [options]
```

**Subcommands:**

- `list` - List your artifacts. Shows metadata without payloads for efficiency. Filter by type, representation, or ontology.
- `show` - Show artifact metadata by ID. Does not include the payload - use "payload" command for that.
- `payload` - Get artifact with full payload. For large artifacts stored in Garage, this fetches from object storage.
- `create` - Create a test artifact (for API validation). Creates a simple artifact with provided parameters.
- `delete` - Delete an artifact. Removes both database record and any Garage-stored payload.
- `regenerate` (`regen`) - Recompute a stale artifact from its stored parameters (ADR-207). Enqueues an auto-approved job; the result is saved as a NEW artifact and the original is preserved. Supported types: polarity_analysis, projection.
- `cleanup` - Remove stale artifacts in bulk — those whose graph epoch is behind the current graph (ADR-207). Previews by default; pass --force to delete. Regeneratable types can be recomputed afterward with "kg artifact regenerate".

---

### list

List your artifacts. Shows metadata without payloads for efficiency. Filter by type, representation, or ontology.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Filter by artifact type (polarity_analysis, projection, etc.) | - |
| `-r, --representation <rep>` | Filter by representation/source (cli, polarity_explorer, etc.) | - |
| `-o, --ontology <name>` | Filter by ontology | - |
| `-l, --limit <n>` | Maximum artifacts to return | `"20"` |
| `--offset <n>` | Skip N artifacts (for pagination) | `"0"` |
| `-v, --verbose` | Show storage tier (inline/garage) — an implementation detail hidden by default | - |
| `-j, --json` | Output raw JSON instead of formatted table | - |

### show

Show artifact metadata by ID. Does not include the payload - use "payload" command for that.

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Show storage tier (inline/garage) — an implementation detail hidden by default | - |

### payload

Get artifact with full payload. For large artifacts stored in Garage, this fetches from object storage.

**Usage:**
```bash
kg payload <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-j, --json` | Output raw JSON payload only | - |

### create

Create a test artifact (for API validation). Creates a simple artifact with provided parameters.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Artifact type (polarity_analysis, projection, query_result, etc.) | - |
| `-n, --name <name>` | Human-readable name | - |
| `-o, --ontology <name>` | Associated ontology | - |
| `--payload <json>` | JSON payload (default: simple test payload) | `"{\"test\": true, \"created_via\": \"cli\"}"` |

### delete

Delete an artifact. Removes both database record and any Garage-stored payload.

**Usage:**
```bash
kg delete <id>
```

**Arguments:**

- `<id>` - Artifact ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation prompt | - |

### regenerate (regen)

Recompute a stale artifact from its stored parameters (ADR-207). Enqueues an auto-approved job; the result is saved as a NEW artifact and the original is preserved. Supported types: polarity_analysis, projection.

**Usage:**
```bash
kg regenerate <id>
```

**Arguments:**

- `<id>` - Artifact ID

### cleanup

Remove stale artifacts in bulk — those whose graph epoch is behind the current graph (ADR-207). Previews by default; pass --force to delete. Regeneratable types can be recomputed afterward with "kg artifact regenerate".

**Usage:**
```bash
kg cleanup [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --type <type>` | Only clean up artifacts of this type | - |
| `-o, --ontology <name>` | Only clean up artifacts in this ontology | - |
| `-f, --force` | Actually delete (default is a dry-run preview) | - |
