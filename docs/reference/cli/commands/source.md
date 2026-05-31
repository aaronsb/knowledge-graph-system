# kg source

> Auto-generated

## source

Retrieve and manage source documents stored in Garage. Source documents are the original files ingested into the knowledge graph, preserved for model evolution and re-extraction (ADR-081).

**Usage:**
```bash
kg source [options]
```

**Subcommands:**

- `list` - List source nodes (chunks) in the graph. Sources are chunks of ingested documents. Filter by ontology name to see sources from specific documents.
- `get` - Download the original source document from Garage storage. This returns the complete document as it was before chunking, not individual chunks. Useful for verification, re-processing, or archival. Output goes to stdout by default (for piping) or to a file with -o.
- `info` - Display metadata for a source node including document name, paragraph number, content type, garage_key, and embedding status.

---

### list

List source nodes (chunks) in the graph. Sources are chunks of ingested documents. Filter by ontology name to see sources from specific documents.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology/document name (partial match) | - |
| `-l, --limit <n>` | Maximum sources to return | `"50"` |
| `--offset <n>` | Skip N sources (pagination) | `"0"` |
| `-j, --json` | Output raw JSON | - |

### get

Download the original source document from Garage storage. This returns the complete document as it was before chunking, not individual chunks. Useful for verification, re-processing, or archival. Output goes to stdout by default (for piping) or to a file with -o.

**Usage:**
```bash
kg get <source-id>
```

**Arguments:**

- `<source-id>` - Source ID (e.g., sha256:abc123_chunk1)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output <file>` | Save to file instead of stdout | - |
| `-m, --metadata` | Show source metadata instead of content | - |

### info

Display metadata for a source node including document name, paragraph number, content type, garage_key, and embedding status.

**Usage:**
```bash
kg info <source-id>
```

**Arguments:**

- `<source-id>` - Source ID
