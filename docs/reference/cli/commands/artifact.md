# kg artifact

> Auto-generated

## artifact (art)

Manage artifacts - persistent storage for computed results like polarity analyses, projections, and query results. Artifacts support multi-tier storage: small payloads inline in PostgreSQL, large payloads in Garage S3. Each artifact tracks its graph_epoch for freshness detection.

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
| `-j, --json` | Output raw JSON instead of formatted table | - |

### show

Show artifact metadata by ID. Does not include the payload - use "payload" command for that.

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Artifact ID

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
