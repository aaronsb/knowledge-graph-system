# kg vocabulary

> Auto-generated

## vocabulary (vocab)

Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness, and thresholds.
- `list` - List all edge types with statistics, categories, and confidence scores (ADR-047).
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations.
- `merge` - Manually merge one edge type into another. Redirects all edges from deprecated type to target type.
- `generate-embeddings` - Generate vector embeddings for vocabulary types (required for consolidation and categorization).
- `category-scores` - Show category similarity scores for a specific relationship type (ADR-047).
- `refresh-categories` - Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053).
- `search` - Search for vocabulary terms by natural language query. Useful when creating edges to find the best relationship type.
- `similar` - Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation.
- `opposite` - Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity.
- `analyze` - Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit and potential miscategorization.
- `config` - Show or update vocabulary configuration. No args: display config. With args: update properties (e.g., "kg vocab config vocab_max 275").
- `profiles` - Manage aggressiveness profiles (Bezier curves for consolidation behavior)
- `epistemic-status` - Epistemic status classification for vocabulary types (ADR-065). Shows knowledge validation state based on grounding patterns.
- `sync` - Sync missing edge types from graph to vocabulary (ADR-077). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

---

### status

Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness, and thresholds.

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics, categories, and confidence scores (ADR-047).

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |
| `--sort <fields>` | Sort by comma-separated fields: edges, type, conf, grounding, category, status (default: edges) | - |
| `--json` | Output as JSON for programmatic use | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations.

**Usage:**
```bash
kg consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `"90"` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `"0.90"` |
| `--dry-run` | Preview candidates without executing (no merges, no pruning) | - |
| `--no-prune-unused` | Skip pruning vocabulary types with 0 uses | - |

### merge

Manually merge one edge type into another. Redirects all edges from deprecated type to target type.

**Usage:**
```bash
kg merge <deprecated-type> <target-type>
```

**Arguments:**

- `<deprecated-type>` - Edge type to deprecate (becomes inactive)
- `<target-type>` - Target edge type to merge into (receives all edges)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --reason <text>` | Reason for merge (audit trail) | - |
| `-u, --user <email>` | User performing the merge | `"cli-user"` |

### generate-embeddings

Generate vector embeddings for vocabulary types (required for consolidation and categorization).

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

Show category similarity scores for a specific relationship type (ADR-047).

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., CAUSES, ENABLES)

### refresh-categories

Refresh category assignments for vocabulary types using latest embeddings (ADR-047, ADR-053).

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed | - |

### search

Search for vocabulary terms by natural language query. Useful when creating edges to find the best relationship type.

**Usage:**
```bash
kg search <query>
```

**Arguments:**

- `<query>` - Natural language search term (e.g., "prevents", "leads to", "causes")

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-20) | `"5"` |
| `--json` | Output as JSON for scripting | - |

### similar

Find similar edge types via embedding similarity (ADR-053). Shows types with highest cosine similarity - useful for synonym detection and consolidation.

**Usage:**
```bash
kg similar <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., IMPLIES)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-100) | `"10"` |

### opposite

Find opposite (least similar) edge types via embedding similarity (ADR-053). Shows types with lowest cosine similarity.

**Usage:**
```bash
kg opposite <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., IMPLIES)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit <n>` | Number of results to return (1-100) | `"5"` |

### analyze

Detailed analysis of vocabulary type for quality assurance (ADR-053). Shows category fit and potential miscategorization.

**Usage:**
```bash
kg analyze <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., STORES)

### config

Show or update vocabulary configuration. No args: display config. With args: update properties (e.g., "kg vocab config vocab_max 275").

**Usage:**
```bash
kg config [properties]
```

**Arguments:**

- `<properties>` - Property assignments: key value [key value...]

### profiles

Manage aggressiveness profiles (Bezier curves for consolidation behavior)

**Usage:**
```bash
kg profiles [options]
```

**Subcommands:**

- `list` - List all aggressiveness profiles including builtin (8 predefined) and custom profiles. Shows profile name, control points, description, and builtin flag.
- `show` - Show details for a specific aggressiveness profile including Bezier parameters and timestamps.
- `create` - Create a custom aggressiveness profile with Bezier curve parameters.
- `delete` - Delete a custom aggressiveness profile. Cannot delete builtin profiles.

---

#### list

List all aggressiveness profiles including builtin (8 predefined) and custom profiles. Shows profile name, control points, description, and builtin flag.

**Usage:**
```bash
kg list [options]
```

#### show

Show details for a specific aggressiveness profile including Bezier parameters and timestamps.

**Usage:**
```bash
kg show <name>
```

**Arguments:**

- `<name>` - Profile name

#### create

Create a custom aggressiveness profile with Bezier curve parameters.

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--name <name>` | Profile name (3-50 chars) | - |
| `--x1 <n>` | First control point X (0.0-1.0) | - |
| `--y1 <n>` | First control point Y (-2.0 to 2.0) | - |
| `--x2 <n>` | Second control point X (0.0-1.0) | - |
| `--y2 <n>` | Second control point Y (-2.0 to 2.0) | - |
| `--description <desc>` | Profile description (min 10 chars) | - |

#### delete

Delete a custom aggressiveness profile. Cannot delete builtin profiles.

**Usage:**
```bash
kg delete <name>
```

**Arguments:**

- `<name>` - Profile name to delete

### epistemic-status

Epistemic status classification for vocabulary types (ADR-065). Shows knowledge validation state based on grounding patterns.

**Usage:**
```bash
kg epistemic-status [options]
```

**Subcommands:**

- `list` - List all vocabulary types with their epistemic status classifications and statistics.
- `show` - Show detailed epistemic status for a specific vocabulary type.
- `measure` - Run epistemic status measurement for all vocabulary types (ADR-065).

---

#### list

List all vocabulary types with their epistemic status classifications and statistics.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--status <status>` | Filter by status: WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, POORLY_GROUNDED, CONTRADICTED, HISTORICAL, INSUFFICIENT_DATA | - |

#### show

Show detailed epistemic status for a specific vocabulary type.

**Usage:**
```bash
kg show <type>
```

**Arguments:**

- `<type>` - Relationship type to show (e.g., IMPLIES, SUPPORTS)

#### measure

Run epistemic status measurement for all vocabulary types (ADR-065).

**Usage:**
```bash
kg measure [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--sample-size <n>` | Edges to sample per type (default: 100) | `100` |
| `--no-store` | Run measurement without storing to database | - |
| `--verbose` | Include detailed statistics in output | - |

### sync

Sync missing edge types from graph to vocabulary (ADR-077). Discovers edge types used in the graph but not registered in vocabulary table/VocabType nodes. Use --dry-run first to preview, then --execute to sync.

**Usage:**
```bash
kg sync [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview missing types without syncing (default) | `true` |
| `--execute` | Actually sync missing types to vocabulary | `false` |
| `--json` | Output as JSON for scripting | - |
