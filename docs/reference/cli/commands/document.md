# kg document

> Auto-generated

## document (doc)

Search for documents using semantic similarity and retrieve their content from Garage storage. Documents are aggregated from source chunks, ranked by their best matching chunk similarity (ADR-084).

**Usage:**
```bash
kg document [options]
```

**Subcommands:**

- `search` - Find documents that match a query using semantic search. Results show documents ranked by their best matching chunk similarity. Use --details to show full concept information for the top result.
- `list` - List all documents (DocumentMeta nodes) in the knowledge graph. Filter by ontology to see documents from specific collections.
- `show` - Retrieve and display the full content of a document from Garage storage. Shows the original document text plus source chunks created during ingestion.
- `concepts` - Show all concepts extracted from a specific document. Displays concept names, IDs, and the source chunks where they appear. Use --details for full concept information including evidence and relationships.

---

### search

Find documents that match a query using semantic search. Results show documents ranked by their best matching chunk similarity. Use --details to show full concept information for the top result.

**Usage:**
```bash
kg search <query>
```

**Arguments:**

- `<query>` - Search query (natural language)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology name | - |
| `-s, --min-similarity <n>` | Minimum similarity threshold (0-1) | `"0.5"` |
| `-l, --limit <n>` | Maximum results | `"20"` |
| `-d, --details` | Show full concept details for top result | - |
| `-j, --json` | Output raw JSON | - |

### list

List all documents (DocumentMeta nodes) in the knowledge graph. Filter by ontology to see documents from specific collections.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --ontology <name>` | Filter by ontology name (partial match) | - |
| `-l, --limit <n>` | Maximum documents to return | `"50"` |
| `--offset <n>` | Skip N documents (pagination) | `"0"` |
| `-j, --json` | Output raw JSON | - |

### show

Retrieve and display the full content of a document from Garage storage. Shows the original document text plus source chunks created during ingestion.

**Usage:**
```bash
kg show <document-id>
```

**Arguments:**

- `<document-id>` - Document ID (e.g., sha256:abc123...)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --chunks` | Show source chunks instead of full document | - |
| `-j, --json` | Output raw JSON | - |

### concepts

Show all concepts extracted from a specific document. Displays concept names, IDs, and the source chunks where they appear. Use --details for full concept information including evidence and relationships.

**Usage:**
```bash
kg concepts <document-id>
```

**Arguments:**

- `<document-id>` - Document ID (e.g., sha256:abc123...)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --details` | Show full concept details (evidence, relationships, grounding) | - |
| `-j, --json` | Output raw JSON | - |
