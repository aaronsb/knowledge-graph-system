# kg search

> Auto-generated

## search

Search and explore the knowledge graph using vector similarity, graph traversal, and path finding

**Usage:**
```bash
kg search [options]
```

**Subcommands:**

- `query` - Search for concepts using vector similarity (embeddings) - use specific phrases for best results
- `details` - Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength
- `related` - Find concepts related through graph traversal (breadth-first search) - groups results by distance
- `connect` - Find shortest path between two concepts using IDs or semantic phrase matching
- `sources` - Search source documents directly using embeddings - returns matched text with related concepts (ADR-068)

---

### query

Search for concepts using vector similarity (embeddings) - use specific phrases for best results

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - Natural language search query (2-3 words work best)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum number of results to return | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0, default 0.7=70%, lower to 0.5 for broader matches) | `"0.7"` |
| `--no-evidence` | Hide evidence quotes (shown by default) | - |
| `--no-images` | Hide inline image display (shown by default if chafa installed) | - |
| `--no-grounding` | Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results | - |
| `--no-diversity` | Disable semantic diversity calculation (ADR-063 authenticity signal) for faster results | - |
| `--diversity-hops <number>` | Maximum traversal depth for diversity (1-3, default 2) | `"2"` |
| `--download <directory>` | Download images to specified directory instead of displaying inline | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### details

Get comprehensive details for a concept: all evidence, relationships, sources, and grounding strength

**Usage:**
```bash
kg details <concept-id>
```

**Arguments:**

- `<concept-id>` - Concept ID to retrieve (from search results)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-grounding` | Disable grounding strength calculation (ADR-044 probabilistic truth convergence) for faster results | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### related

Find concepts related through graph traversal (breadth-first search) - groups results by distance

**Usage:**
```bash
kg related <concept-id>
```

**Arguments:**

- `<concept-id>` - Starting concept ID for traversal

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --depth <number>` | Maximum traversal depth in hops (1-2 fast, 3-4 moderate, 5 slow) | `"2"` |
| `-t, --types <types...>` | Filter by relationship types (IMPLIES, ENABLES, SUPPORTS, etc. - see kg vocab list) | - |
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-065): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-065) | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### connect

Find shortest path between two concepts using IDs or semantic phrase matching

**Usage:**
```bash
kg connect <from> <to>
```

**Arguments:**

- `<from>` - Starting concept (exact ID or descriptive phrase - e.g., "licensing issues" not "licensing")
- `<to>` - Target concept (exact ID or descriptive phrase - use 2-3 word phrases for best results)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--max-hops <number>` | Maximum path length | `"5"` |
| `--min-similarity <number>` | Semantic similarity threshold for phrase matching (default 50% - lower for broader matches) | `"0.5"` |
| `--no-evidence` | Hide evidence quotes (shown by default) | - |
| `--no-images` | Hide inline image display (shown by default if chafa installed) | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--download <directory>` | Download images to specified directory instead of displaying inline | - |
| `--json` | Output raw JSON instead of formatted text | - |
| `--include-epistemic <statuses...>` | Only include relationships with these epistemic statuses (ADR-065): AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL | - |
| `--exclude-epistemic <statuses...>` | Exclude relationships with these epistemic statuses (ADR-065) | - |

### sources

Search source documents directly using embeddings - returns matched text with related concepts (ADR-068)

**Usage:**
```bash
kg sources <query>
```

**Arguments:**

- `<query>` - Search query text (searches source embeddings, not concept embeddings)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum number of sources to return | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0, default 0.7) | `"0.7"` |
| `-o, --ontology <name>` | Filter by ontology/document name | - |
| `--no-concepts` | Hide concepts extracted from matched sources (shown by default) | - |
| `--no-full-text` | Hide full source text (shown by default) | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |
