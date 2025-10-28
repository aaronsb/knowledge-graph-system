# kg search

> Auto-generated

## search

Search for concepts and explore the graph

**Usage:**
```bash
kg search [options]
```

**Subcommands:**

- `query` - Search for concepts using natural language
- `details` - Get detailed information about a concept
- `related` - Find concepts related through graph traversal
- `connect` - Find shortest path between two concepts using IDs or semantic phrase matching

---

### query

Search for concepts using natural language

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - Search query text

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-l, --limit <number>` | Maximum results | `"10"` |
| `--min-similarity <number>` | Minimum similarity score (0.0-1.0) | `"0.7"` |
| `--show-evidence` | Show sample evidence quotes from source text | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |

### details

Get detailed information about a concept

**Usage:**
```bash
kg details <concept-id>
```

**Arguments:**

- `<concept-id>` - Concept ID to retrieve

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |

### related

Find concepts related through graph traversal

**Usage:**
```bash
kg related <concept-id>
```

**Arguments:**

- `<concept-id>` - Starting concept ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-d, --depth <number>` | Maximum traversal depth (1-5) | `"2"` |
| `-t, --types <types...>` | Filter by relationship types | - |
| `--json` | Output raw JSON instead of formatted text | - |

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
| `--show-evidence` | Show sample evidence quotes for each concept in paths | - |
| `--no-grounding` | Disable grounding strength calculation (faster) | - |
| `--json` | Output raw JSON instead of formatted text | - |
