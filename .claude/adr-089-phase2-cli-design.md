# ADR-089 Phase 2: CLI Design Decisions

**Date**: 2025-01-25
**Status**: Implementation Notes
**Context**: Phase 2 of ADR-089 adds CLI/MCP clients for deterministic graph editing

## Command Structure

```
kg concept create [flags]      # Non-interactive with flags, or -i for wizard
kg concept list [--ontology]   # List concepts, supports --json
kg concept show <id>           # Show concept details, supports --json
kg concept delete <id>         # Delete concept (requires --force or -i to confirm)

kg edge create [flags]         # Non-interactive with flags, or -i for wizard
kg edge list [filters]         # List edges, supports --json
kg edge delete <from> <type> <to>  # Delete edge

kg vocab search <term>         # Similarity search against edge vocabulary

kg batch create <file>         # Import batch JSON file
```

### Non-Interactive as Default

`kg concept create` and `kg edge create` are non-interactive by default:
- Follows standard CLI conventions
- Running without required flags shows help guidance
- Scripts work predictably without unexpected prompts
- Add `--interactive` or `-i` for guided wizard mode

```bash
# Non-interactive (scripting)
kg concept create --label "ML" --ontology ai --description "..."

# Interactive (guided wizard)
kg concept create --interactive
kg concept create -i
```

### Output Modes

- **Default**: Human-readable formatted output
- **`--json`**: Machine-readable JSON, suitable for piping

```bash
kg concept list --ontology ai --json | jq '.concepts[].concept_id'
```

## Control Law Model (Fly-by-Wire Analogy)

Like aircraft fly-by-wire systems, the CLI provides graduated control while **always protecting graph integrity**. No mode allows invalid graph operations - the "envelope protection" is always active.

| Law | Mode | User Control | System Protection |
|-----|------|--------------|-------------------|
| **Auto** | `kg ingest` | Ontology only | LLM decides concepts, edges, vocab |
| **Normal** | `kg concept create` (default) | Label, description, ontology | Similarity matching, vocab validation, duplicate prevention |
| **Direct** | `kg concept create --matching-mode force_create` | Full steering | Still validates IDs exist, vocab valid, graph integrity |

### Auto (Autopilot)
```bash
kg ingest --ontology ai document.pdf
```
- LLM extracts concepts, relationships, evidence
- System handles all matching and edge creation
- User provides input, system decides structure

### Normal Law (Assisted Manual)
```bash
kg concept create --label "ML" --description "learns from data" --ontology ai
```
- User defines concept, system similarity-matches
- Near-duplicate? Links to existing, adds evidence
- Edge vocab validated against known types
- System prevents accidental duplication

### Direct Law (Full Manual)
```bash
kg concept create --label "ML" --ontology ai --matching-mode force_create
kg edge create --from c_abc --to c_def --type NEW_RELATION --create-vocab
```
- User has maximum steering authority
- Can force-create despite matches
- Can create new vocabulary terms
- **But**: Still can't reference non-existent concept IDs, create malformed edges, or violate graph schema

### Envelope Protection (Always On)

Regardless of control law, these protections cannot be bypassed:

```
┌─────────────────────────────────────────────────────────┐
│  PROTECTED (all modes)                                  │
│  ─────────────────────                                  │
│  ✗ Cannot reference non-existent concept IDs            │
│  ✗ Cannot create edges without valid from/to concepts   │
│  ✗ Cannot create malformed relationship types           │
│  ✗ Cannot violate graph schema constraints              │
│  ✗ Cannot create orphaned nodes (no ontology)           │
└─────────────────────────────────────────────────────────┘
```

The stick physically can't move outside the envelope.

## Interactive Flow: Concept Creation

Activated with `--interactive` or `-i` flag:

```
$ kg concept create -i

📝 Create New Concept
─────────────────────

Ontology: [user types or selects]
Label: [user types]
Description: [user types]

Evidence (Ctrl+D to finish, Ctrl+C to cancel):
> [multi-line input]

Connect to existing concepts?
  ○ Let graph auto-attach (recommended)
  ○ Choose manually
  ○ No connections
```

## Interactive Flow: Edge Vocabulary Selection

When user selects "Choose manually":

```
Search for concept to connect: neural networks
  1. Neural Networks (c_def456) - 92% match
  2. Deep Neural Networks (c_ghi789) - 85% match
  3. Artificial Neural Networks (c_jkl012) - 81% match

Select [1-3]: 1

Relationship type: leads to
  1. ENABLES (87% similar)
  2. IMPLIES (82% similar)
  3. SUPPORTS (79% similar)
  4. [+] Create new vocabulary term
  0. [↺] Try another search

Select [0-4]: 1*

[asterisk marks selection, Enter to proceed]
```

## Confirmation with ASCII Diagram

Before committing, show what will be created:

```
┌──────────────────────┐
│  Machine Learning    │
│  (new concept)       │
└──────────┬───────────┘
           │
           │ ENABLES
           ▼
┌──────────────────────┐
│  Neural Networks     │
│  (c_def456)          │
└──────────────────────┘

[A]ccept  [R]eject  [J]SON export
```

### JSON Export Option

When user selects JSON export:
- Prompt for filename (default: `./concept-{timestamp}.json`)
- Emit valid BatchCreateRequest format
- User can ingest later with `kg batch import <file>`

```json
{
  "ontology": "ai-concepts",
  "concepts": [
    {
      "label": "Machine Learning",
      "description": "...",
      "search_terms": []
    }
  ],
  "edges": [
    {
      "from_label": "Machine Learning",
      "to_label": "Neural Networks",
      "relationship_type": "ENABLES"
    }
  ]
}
```

## Interactive Input Controls

Field input with optional selector support:

| Key | Context | Action |
|-----|---------|--------|
| **Tab** | Empty/populated field | Open selector (search/list) |
| **Enter** | In selector | Populate field (don't advance) |
| **Enter** | On populated field | Advance to next field |
| **Esc** | On field | Clear field |
| **Esc** | In selector | Close selector, keep field data |

### Flow Example

```
Ontology: [cursor here]
          ↓ user presses Tab
┌─────────────────────────┐
│  1. ai-concepts         │
│  2. philosophy          │
│  3. machine-learning    │
│  [type to filter...]    │
└─────────────────────────┘
          ↓ user presses Enter on #1
Ontology: ai-concepts     ← field populated, cursor stays
          ↓ user presses Tab again (to change)
┌─────────────────────────┐
│  1. ai-concepts ✓       │
│  ...                    │
└─────────────────────────┘
          ↓ user presses Esc (keep selection)
Ontology: ai-concepts     ← unchanged
          ↓ user presses Enter (advance)
Label: [cursor moves here]
```

### Selector Behaviors

- **Ontology field**: Tab shows list of existing ontologies
- **Concept search**: Tab shows similarity search results for typed text
- **Vocabulary**: Tab shows similarity-matched vocab types for typed text
- **Free text fields** (label, description): Tab does nothing (no selector)

---

## Evidence Input

Use custom multi-line input (not external editor):
- Stays in-terminal, no $EDITOR dependency
- Clear instructions: `Ctrl+D to finish, Ctrl+C to cancel`
- Line numbers optional

```
Evidence (Ctrl+D to finish, Ctrl+C to cancel):
> Machine learning is a subset of artificial
> intelligence that enables systems to learn
> from data without being explicitly programmed.
> [Ctrl+D]
```

## Vocabulary Search

New command: `kg vocab search <term>`

```bash
$ kg vocab search "prevents"

Edge Vocabulary Search: "prevents"
──────────────────────────────────
  1. PREVENTS (100% match)
  2. INHIBITS (89% similar)
  3. BLOCKS (85% similar)
  4. CONTRADICTS (72% similar)
  5. LIMITS (68% similar)

Use: kg edge create --type PREVENTS ...
```

Uses existing vocabulary embedding similarity endpoint.

## Validation Strategy

**Core principle**: Interactive and non-interactive share the same validation code. The CLI reuses the same matching/upsert logic as automatic ingestion.

### Concept Matching (via description embedding)

When creating a concept, the **description is embedded** and similarity-matched against existing concepts:

```
User provides: --label "ML" --description "A subset of AI that learns from data"
                                    ↓
                          Generate embedding
                                    ↓
                    Similarity search against existing concepts
                                    ↓
              ┌─────────────────────────────────────────┐
              │  Match found (>threshold)?              │
              │                                         │
              │  matching_mode=auto (default):          │
              │    → Link to existing, add evidence     │
              │                                         │
              │  matching_mode=force_create:            │
              │    → Create new despite match           │
              │                                         │
              │  matching_mode=match_only:              │
              │    → Link if match, error if not        │
              └─────────────────────────────────────────┘
```

This is identical to how automatic ingestion works. If a near-match exists:
- **Don't duplicate** the concept
- **Add evidence** (the description becomes a Source node)
- **Return** the matched concept ID with `matched_existing: true`

### Non-Interactive Validation (Strict)

Non-interactive mode must validate everything upfront since there's no user to correct mistakes:

| Input | Valid | Invalid | Resolution |
|-------|-------|---------|------------|
| `--ontology foo` | Ontology exists | Ontology doesn't exist | Error (or `--create-ontology` flag) |
| `--connect-to c_abc123` | Concept ID exists | ID doesn't exist | Error |
| `--type IMPLIES` | Vocab term exists | Term doesn't exist | Error |
| `--type NEW_TERM --create-vocab` | N/A | N/A | Create new vocab term |
| `--type IMPLIES --create-vocab` | Term exists | N/A | Warning: "IMPLIES exists, reusing" |

### Edge Vocabulary Flags

```bash
# Use existing vocab (error if not found)
kg edge create --from c_abc --to c_def --type IMPLIES

# Create new vocab term (error if invalid format)
kg edge create --from c_abc --to c_def --type CAUSES_DELAY --create-vocab

# Create new vocab term (warning if already exists, reuses it)
kg edge create --from c_abc --to c_def --type IMPLIES --create-vocab
# ⚠ Warning: Vocabulary term 'IMPLIES' already exists, reusing
```

### Concept ID Validation

When connecting to existing concepts:

```bash
# Valid - concept exists
kg edge create --from c_abc123 --to c_def456 --type IMPLIES
# ✓ Created edge

# Invalid - concept doesn't exist
kg edge create --from c_invalid --to c_def456 --type IMPLIES
# ✗ Error: Concept 'c_invalid' not found

# By label (semantic lookup) - searches for best match
kg edge create --from-label "Machine Learning" --to-label "Neural Networks" --type IMPLIES
# ✓ Resolved: c_abc123 → c_def456
# ✓ Created edge
```

### Interactive Mode Validation

Same validation, but **live feedback** as user progresses:

```
Label: Machine Learning
Description: A subset of AI that learns from data

Checking for similar concepts...
  ⚠ Found similar: "Machine Learning" (c_abc123) - 94% match

  What would you like to do?
    1. Link to existing (add your description as evidence)
    2. Create new anyway (force_create)
    3. Edit description and re-check
```

### Shared Validation Code

```
cli/src/lib/validation.ts
├── validateOntology(name) → exists | error
├── validateConceptId(id) → exists | error
├── validateVocabTerm(term, createIfMissing) → exists | created | error
├── matchConcept(description, mode) → matched | created | error
└── validateEdge(from, to, type, createVocab) → valid | errors[]
```

Both interactive wizard and flag-based creation call the same validators.

## Reusability

This design informs three interfaces:
1. **CLI** (`cli/src/cli/`) - Primary implementation
2. **MCP** (`cli/src/mcp/`) - Same logic, different I/O
3. **Web Workstation** (`web/src/`) - Same patterns, React UI

All share TypeScript codebase. Core logic in shared modules.

## Files to Create/Modify

### New Files
- `cli/src/cli/concept.ts` - Concept CRUD commands
- `cli/src/cli/edge.ts` - Edge CRUD commands
- `cli/src/cli/vocab.ts` - Vocabulary search (or extend existing)
- `cli/src/lib/interactive.ts` - Shared interactive utilities
  - Multi-line input
  - Selection menus
  - ASCII diagrams
  - Confirmation prompts

### Modify
- `cli/src/api/client.ts` - Add concept/edge API methods
- `cli/src/types/index.ts` - Add TypeScript interfaces
- `cli/src/cli/commands.ts` - Register new commands

## Help Output (No Flags)

### kg concept create

```
$ kg concept create

Error: Missing required options

Usage: kg concept create [options]

Create a new concept in the knowledge graph. Description is embedded and
similarity-matched against existing concepts (same as automatic ingestion).

Required:
  --label <name>        Concept label
  --ontology <name>     Target ontology

Optional:
  --description <text>  Concept description (used for embedding match)
  --search-terms <t>    Comma-separated search terms
  --matching-mode <m>   auto|force_create|match_only (default: auto)
  --json                Output as JSON
  -i, --interactive     Guided wizard mode
  -y, --yes             Skip confirmation prompts

Examples:
  kg concept create --label "Machine Learning" --ontology ai
  kg concept create --label "ML" --description "learns from data" --ontology ai
  kg concept create -i                    # Interactive wizard
  kg concept create --label ML --ontology ai --json > out.json
```

### kg edge create

```
$ kg edge create

Error: Missing required options

Usage: kg edge create [options]

Create an edge between two concepts.

Required (by ID):
  --from <concept_id>   Source concept ID
  --to <concept_id>     Target concept ID
  --type <vocab_term>   Relationship type (must exist, or use --create-vocab)

Required (by label - semantic lookup):
  --from-label <text>   Source concept (searches by label)
  --to-label <text>     Target concept (searches by label)
  --type <vocab_term>   Relationship type

Optional:
  --category <cat>      Relationship category (auto-inferred if omitted)
  --confidence <0-1>    Confidence score (default: 1.0)
  --create-vocab        Create vocab term if it doesn't exist
  --json                Output as JSON
  -i, --interactive     Guided wizard mode
  -y, --yes             Skip confirmation prompts

Examples:
  kg edge create --from c_abc --to c_def --type IMPLIES
  kg edge create --from-label "ML" --to-label "Neural Networks" --type ENABLES
  kg edge create --from c_abc --to c_def --type CAUSES_DELAY --create-vocab
  kg edge create -i                       # Interactive wizard
```

## Open Questions

1. ~~Should `kg concept create` with all flags skip interactive entirely?~~
   - Resolved: Yes, non-interactive is default. Use `-i` for wizard.

2. Batch import command name: `kg batch import` or `kg import`?
   - Proposal: `kg batch create` (matches API endpoint)

3. Should evidence creation spawn a Source node immediately, or defer?
   - Proposal: Create Source node as part of concept creation (atomic)
