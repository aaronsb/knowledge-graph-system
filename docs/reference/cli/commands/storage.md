# kg storage

> Auto-generated

## storage

Read-only diagnostics for S3-compatible object storage. List objects, inspect metadata, verify integrity after cascade deletes, and view retention policies. Useful for integration testing and debugging storage behavior.

**Usage:**
```bash
kg storage [options]
```

**Subcommands:**

- `health` - Check storage backend connectivity and bucket accessibility
- `stats` - Show storage usage statistics by category (sources, images, projections, artifacts)
- `list` - List objects in storage with optional prefix filter. Examples: kg storage list --prefix sources/ --limit 20
- `inspect` - Inspect metadata for a single object without downloading content. Use the full S3 key from "kg storage list".
- `integrity` - Cross-reference S3 objects against graph nodes. Finds orphaned objects (in S3 but not graph) and missing objects (in graph but not S3). Essential for verifying cascade deletes.
- `retention` - Show current retention policy configuration for each storage category

---

### health

Check storage backend connectivity and bucket accessibility

**Usage:**
```bash
kg health [options]
```

### stats

Show storage usage statistics by category (sources, images, projections, artifacts)

**Usage:**
```bash
kg stats [options]
```

### list

List objects in storage with optional prefix filter. Examples: kg storage list --prefix sources/ --limit 20

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-p, --prefix <prefix>` | S3 key prefix filter (e.g. sources/, images/My_Ontology/) | - |
| `-l, --limit <n>` | Maximum objects to return | `50` |
| `-o, --offset <n>` | Number of objects to skip | `0` |

### inspect

Inspect metadata for a single object without downloading content. Use the full S3 key from "kg storage list".

**Usage:**
```bash
kg inspect <key>
```

**Arguments:**

- `<key>` - S3 object key (e.g. sources/My_Ontology/abc123.md)

### integrity

Cross-reference S3 objects against graph nodes. Finds orphaned objects (in S3 but not graph) and missing objects (in graph but not S3). Essential for verifying cascade deletes.

**Usage:**
```bash
kg integrity [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--ontology <name>` | Scope check to a specific ontology | - |
| `--category <type>` | Storage category: sources, images | `"sources"` |

### retention

Show current retention policy configuration for each storage category

**Usage:**
```bash
kg retention [options]
```
