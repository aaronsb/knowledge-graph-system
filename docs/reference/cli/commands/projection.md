# kg projection

> Auto-generated

## projection (proj)

Manage t-SNE/UMAP projections of concept embeddings. Projections reduce high-dimensional embeddings to 3D coordinates for the Embedding Landscape Explorer visualization. Use this to compute, view, and manage projection datasets.

**Usage:**
```bash
kg projection [options]
```

**Subcommands:**

- `list` - List projection status for all ontologies. Shows which ontologies have cached projections and their statistics.
- `info` - Get detailed projection info for an ontology
- `regenerate` - Compute or recompute projection for an ontology
- `invalidate` - Delete cached projection for an ontology
- `data` - Get full projection data as JSON (for visualization pipelines)
- `algorithms` - List available projection algorithms

---

### list

List projection status for all ontologies. Shows which ontologies have cached projections and their statistics.

**Usage:**
```bash
kg list [options]
```

### info

Get detailed projection info for an ontology

**Usage:**
```bash
kg info <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

### regenerate

Compute or recompute projection for an ontology

**Usage:**
```bash
kg regenerate <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name, "all" (each separately), or "global" (all together)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Force recomputation even if cached | - |
| `-a, --algorithm <algo>` | Algorithm: tsne or umap | `"tsne"` |
| `-p, --perplexity <n>` | t-SNE perplexity (5-100) | `"30"` |
| `--center` | Center embeddings before projection (fixes meatball artifact, default: true) | - |
| `--no-center` | Disable embedding centering | - |
| `--grounding` | Include grounding strength | - |
| `--diversity` | Include diversity scores (slower) | - |
| `--save-artifact` | Save result as persistent artifact (ADR-083) | - |

### invalidate

Delete cached projection for an ontology

**Usage:**
```bash
kg invalidate <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

### data

Get full projection data as JSON (for visualization pipelines)

**Usage:**
```bash
kg data <ontology>
```

**Arguments:**

- `<ontology>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output <file>` | Write to file instead of stdout | - |
| `--pretty` | Pretty-print JSON output | - |

### algorithms

List available projection algorithms

**Usage:**
```bash
kg algorithms [options]
```
