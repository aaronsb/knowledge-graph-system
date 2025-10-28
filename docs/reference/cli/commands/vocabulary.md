# kg vocabulary

> Auto-generated

## vocabulary (vocab)

Edge vocabulary management and consolidation. Manages relationship types between concepts including builtin types (30 predefined), custom types (LLM-extracted from documents), categories (semantic groupings), consolidation (AI-assisted merging via AITL - ADR-032), and auto-categorization (probabilistic via embeddings - ADR-047). Features zone-based management (GREEN/WATCH/DANGER/EMERGENCY) and LLM-determined relationship direction (ADR-049).

**Usage:**
```bash
kg vocabulary [options]
```

**Subcommands:**

- `status` - Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness (growth above minimum), and thresholds. Shows breakdown of builtin types, custom types, and categories. Use this to monitor vocabulary health, check zone before consolidation, track growth over time, and trigger consolidation workflows when needed.
- `list` - List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.
- `consolidate` - AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) iterate until target reached. Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.
- `merge` - Manually merge one edge type into another for consolidation or correction. Validates both types exist, redirects all edges from deprecated type to target type, marks deprecated type as inactive, records audit trail (reason, user, timestamp), and preserves edge provenance. This is a non-destructive, atomic operation useful for manual consolidation, fixing misnamed types from extraction, bulk scripted operations, and targeted category cleanup. Safety: edges preserved, atomic transaction, audit trail for compliance, can be reviewed in inactive types list.
- `generate-embeddings` - Generate vector embeddings for vocabulary types (required for consolidation and categorization). Identifies types without embeddings, generates embeddings using configured embedding model, stores embeddings for similarity comparison, and enables consolidation and auto-categorization. Use after fresh install (bootstrap vocabulary embeddings), after ingestion introduces new custom types, when switching embedding models (regenerate), or for inconsistency fixes (force regeneration if corrupted). Performance: ~100-200ms per embedding (OpenAI), ~20-50ms per embedding (local models), parallel generation (batches of 10).
- `category-scores` - Show category similarity scores for a specific relationship type (ADR-047). Displays assigned category, confidence score (calculated as max_score/second_max_score * 100), ambiguous flag (set when runner-up within 20% of winner), runner-up category if ambiguous, and similarity to all category seeds (0-100%) sorted by similarity with visual bar chart. Use this to verify auto-categorization makes sense, debug low confidence assignments, understand why confidence is low, resolve ambiguity between close categories, and audit all types for misassignments.
- `refresh-categories` - Refresh category assignments for vocabulary types using latest embeddings (ADR-047). Identifies types needing category refresh, recalculates similarity to all category seeds, assigns best-matching category, updates confidence scores, and flags ambiguous assignments. Use after embedding model changes (recalculate with new model), category definition updates (refresh after changing seed terms), periodic maintenance (quarterly review), or quality improvement (re-evaluate low confidence). This is a non-destructive operation (doesn't affect edges), preserves manual assignments, and records audit trail per type.

---

### status

Show current vocabulary status including size, zone (GREEN/WATCH/DANGER/EMERGENCY per ADR-032), aggressiveness (growth above minimum), and thresholds. Shows breakdown of builtin types, custom types, and categories. Use this to monitor vocabulary health, check zone before consolidation, track growth over time, and trigger consolidation workflows when needed.

**Usage:**
```bash
kg status [options]
```

### list

List all edge types with statistics, categories, and confidence scores (ADR-047). Shows TYPE (colored by semantic), CATEGORY (composition, causation, logical, etc.), CONF (confidence score with ⚠ for ambiguous), EDGES (usage count), STATUS (active ✓), and [B] flag for builtin types. Use this for vocabulary overview, finding consolidation candidates, reviewing auto-categorization accuracy, identifying unused types, and auditing quality.

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | - |
| `--no-builtin` | Exclude builtin types | - |

### consolidate

AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop, ADR-032). Analyzes vocabulary via embeddings, identifies similar pairs above threshold, presents merge recommendations with confidence, and executes or prompts based on mode. Workflow: 1) analyze vocabulary, 2) identify candidates, 3) present recommendations, 4) execute or prompt, 5) apply merges (deprecate source, redirect edges), 6) iterate until target reached. Modes: interactive (default, prompts each), dry-run (shows candidates without executing), AITL auto (auto-executes high confidence). Threshold guidelines: 0.95+ very conservative, 0.90-0.95 balanced AITL, 0.85-0.90 aggressive requires review, <0.85 very aggressive manual review.

**Usage:**
```bash
kg consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `"90"` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `"0.90"` |
| `--dry-run` | Evaluate candidates without executing merges | - |
| `--auto` | Auto-execute high confidence merges (AITL mode) | - |

### merge

Manually merge one edge type into another for consolidation or correction. Validates both types exist, redirects all edges from deprecated type to target type, marks deprecated type as inactive, records audit trail (reason, user, timestamp), and preserves edge provenance. This is a non-destructive, atomic operation useful for manual consolidation, fixing misnamed types from extraction, bulk scripted operations, and targeted category cleanup. Safety: edges preserved, atomic transaction, audit trail for compliance, can be reviewed in inactive types list.

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

Generate vector embeddings for vocabulary types (required for consolidation and categorization). Identifies types without embeddings, generates embeddings using configured embedding model, stores embeddings for similarity comparison, and enables consolidation and auto-categorization. Use after fresh install (bootstrap vocabulary embeddings), after ingestion introduces new custom types, when switching embedding models (regenerate), or for inconsistency fixes (force regeneration if corrupted). Performance: ~100-200ms per embedding (OpenAI), ~20-50ms per embedding (local models), parallel generation (batches of 10).

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

Show category similarity scores for a specific relationship type (ADR-047). Displays assigned category, confidence score (calculated as max_score/second_max_score * 100), ambiguous flag (set when runner-up within 20% of winner), runner-up category if ambiguous, and similarity to all category seeds (0-100%) sorted by similarity with visual bar chart. Use this to verify auto-categorization makes sense, debug low confidence assignments, understand why confidence is low, resolve ambiguity between close categories, and audit all types for misassignments.

**Usage:**
```bash
kg category-scores <type>
```

**Arguments:**

- `<type>` - Relationship type to analyze (e.g., CAUSES, ENABLES)

### refresh-categories

Refresh category assignments for vocabulary types using latest embeddings (ADR-047). Identifies types needing category refresh, recalculates similarity to all category seeds, assigns best-matching category, updates confidence scores, and flags ambiguous assignments. Use after embedding model changes (recalculate with new model), category definition updates (refresh after changing seed terms), periodic maintenance (quarterly review), or quality improvement (re-evaluate low confidence). This is a non-destructive operation (doesn't affect edges), preserves manual assignments, and records audit trail per type.

**Usage:**
```bash
kg refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with category_source=computed (excludes manual assignments) | - |
