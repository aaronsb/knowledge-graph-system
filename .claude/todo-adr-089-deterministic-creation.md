# ADR-089: Deterministic Node/Edge Creation

**Status:** Phase 1a complete (PR #213), Phase 1b complete (PR #215), Phase 2 CLI in progress

## Overview

Enable direct creation/editing of graph nodes and edges without going through the LLM ingest pipeline. Supports manual curation, agent-driven knowledge building, and foreign graph import.

---

## Phase 1a: Core CRUD ✅ (PR #213)

The foundation - individual entity operations.

### Concept CRUD ✅
- [x] POST /concepts - Create concept
- [x] GET /concepts - List concepts (with filters)
- [x] GET /concepts/{id} - Get concept
- [x] PATCH /concepts/{id} - Update concept
- [x] DELETE /concepts/{id} - Delete concept (with cascade option)

### Edge CRUD ✅
- [x] POST /edges - Create edge
- [x] GET /edges - List edges (with filters)
- [x] PATCH /edges/{from}/{type}/{to} - Update edge
- [x] DELETE /edges/{from}/{type}/{to} - Delete edge

### Supporting Infrastructure ✅
- [x] Synthetic Source node creation for manual concepts
- [x] Embedding generation integration (unified worker)
- [x] `creation_method` property tracking
- [x] Input validation (Pydantic models)
- [x] Matching modes (auto/force_create/match_only)
- [x] Cascade delete for orphaned synthetic sources

### Permissions ✅
- [x] ~~OAuth scopes: kg:read, kg:write, kg:edit~~ → Harmonized to RBAC
- [x] RBAC permissions: graph:read, graph:create, graph:write, graph:delete
- [x] Permission enforcement on all mutation endpoints
- [x] Migration 040: graph_crud_permissions.sql

---

## Phase 1b: Batch Operations ✅ (PR #215)

Bulk creation with transactional semantics.

### Batch Operations ✅
- [x] POST /graph/batch - Batch create concepts/edges
- [x] Transaction semantics (all-or-nothing rollback)
- [x] Edge label resolution (same-batch references)

### Permissions ✅
- [x] ~~kg:import scope~~ → graph:import RBAC permission enforcement

### Observability ✅
- [x] Audit logging for batch operations
- [x] Audit logging for create concept/edge (route-level)

---

## Import Spec: Batch Format

The batch endpoint **is** our import spec. Foreign formats transform to this:

```json
{
  "ontology": "my-ontology",
  "matching_mode": "auto",
  "creation_method": "import",
  "concepts": [
    {"label": "Concept A", "description": "...", "search_terms": ["alt term"]},
    {"label": "Concept B", "description": "..."}
  ],
  "edges": [
    {
      "from_label": "Concept A",
      "to_label": "Concept B",
      "relationship_type": "IMPLIES",
      "confidence": 0.9,
      "category": "logical_truth"
    }
  ]
}
```

Foreign importers (Neo4j, RDF, CSV, etc.) are just **transformers** that convert their format to this spec.

---

## Phase 1c: Foreign Format Transformers (deferred)

CLI/library tools that convert external formats to batch spec.

### Transformers
- [ ] `kg import neo4j <file.cypher>` - Neo4j dump to batch
- [ ] `kg import csv <nodes.csv> <edges.csv>` - CSV to batch
- [ ] `kg import jsonld <file.jsonld>` - JSON-LD/RDF to batch

### Additional
- [ ] graph_editor role definition
- [ ] Audit logging for update/delete endpoints

---

## Phase 2: Clients

All use the same API from Phase 1. See `.claude/adr-089-phase2-cli-design.md` for UX decisions.

### CLI Concept Commands (`cli/src/cli/concept.ts`) ✅
- [x] `kg concept create` - Non-interactive with flags, `-i` for wizard
- [x] `kg concept list` - List with filters, `--json` output
- [x] `kg concept show <id>` - Show details, `--json` output
- [x] `kg concept delete <id>` - With `--force` or `-i` confirm
- [x] API client methods in `cli/src/api/client.ts`
- [x] TypeScript interfaces in `cli/src/types/index.ts`

### CLI Edge Commands (`cli/src/cli/edge.ts`) ✅
- [x] `kg edge create` - Non-interactive with flags, `-i` for wizard
- [x] `kg edge list` - List with filters, `--json` output
- [x] `kg edge delete <from> <type> <to>` - Delete edge
- [x] `--from-label` / `--to-label` for semantic concept lookup

### CLI Vocabulary (`cli/src/cli/vocabulary/similarity.ts`) ✅
- [x] `kg vocab search <term>` - Similarity search against edge vocabulary

### CLI Batch Import (`cli/src/cli/batch.ts`) ✅
- [x] `kg batch create <file>` - Import batch JSON file
- [x] `kg batch template` - Output template JSON

### Shared Validation (`cli/src/lib/validation.ts`) ✅
- [x] `validateOntology(name)` - Check ontology exists
- [x] `validateConceptId(id)` - Check concept ID exists
- [x] `validateVocabTerm(term, createIfMissing)` - Check/create vocab
- [x] `resolveConceptByLabel(label)` - Semantic concept lookup
- [x] `validateEdgeCreation(from, to, type, opts)` - Full edge validation
- [x] Reuse for both interactive and non-interactive modes

### Interactive Utilities (`cli/src/lib/interactive.ts`) ✅
- [x] `textInput` - Basic text input with default
- [x] `selectOption` - Number-based selection menu
- [x] `multiLineInput` - Multi-line (Ctrl+D to finish)
- [x] `buildConceptDiagram` - ASCII diagram builder
- [x] `confirmYesNo` / `confirmAction` - Confirmation prompts
- [x] `withSpinner` - Async operation spinner
- [ ] Full Tab-to-select input (deferred - current UX is functional)

### MCP (`cli/src/mcp-server.ts`)
- [ ] Add create/update/delete/list actions to concept tool
- [ ] Semantic ID resolution (query instead of ID)
- [ ] Scope validation before execution

### Web Workstation
- [ ] Concept creation/editing forms
- [ ] LLM-assisted drafting UI

### FUSE Filesystem
- [ ] Mount concepts as JSON files
- [ ] Edit-via-save → PATCH
- [ ] Create file → POST
- [ ] Delete file → DELETE

---

## Documentation (post-implementation)

Once Phase 2 is complete and tested:

- [ ] Move `.claude/adr-089-phase2-cli-design.md` → `docs/architecture/ADR-089-cli-mcp.md`
- [ ] Update `docs/architecture/ARCHITECTURE_DECISIONS.md` index
- [ ] Consider additional reference docs:
  - `ADR-089-batch-format.md` - Import spec/DTO format
  - `ADR-089-interactive-ux.md` - Tab/Enter/Esc interaction model
- [ ] Archive or delete working docs from `.claude/`

---

## Future

- [ ] RDF/JSON-LD, GraphML, CSV importers
- [ ] Subgraph templates
- [ ] Concept merging
- [ ] Import rollback
- [ ] Ontology-level permission delegation

---

## Key Design Decisions

1. **Synthetic Sources** - Manual concepts get placeholder Source nodes for provenance
2. **Matching modes** - `auto` (dedupe), `force_create` (always new), `match_only` (link or fail)
3. **Free thinking** - Creators emit concepts without topology knowledge; matching handles integration
4. **Shared codebase** - CLI and MCP share implementation

---

## Session Log

### 2026-01-25
- Created ADR-089 draft on research branch
- Documented foreign graph import, permissions, free thinking pattern
- Moved ADR to ingestion-content category
- Started implementation branch `adr-089-deterministic-graph-editing`
- Architecture decision: NO new workers, reuse existing:
  - AGEClient.create_concept_node() for graph operations
  - AGEClient.create_concept_relationship() with source="api_creation"
  - EmbeddingWorker for embedding generation
- New thin layers: ConceptService, EdgeService (orchestration only)
- Implemented concept and edge CRUD routes with OAuth scope enforcement
- Fixed testing infrastructure (imports, container mounts, auth mocking)
- Created 52 passing tests for concepts and edges
- PR #213 created and code review completed
- Addressed review issues: cascade delete, public method, scope tests
- Phase 1b: Implemented batch operations (POST /graph/batch)
- Created BatchService with transaction support and label→ID mapping
- Created AuditService for kg_logs.audit_trail logging
- Added audit logging to batch and individual CRUD endpoints
- 15 new tests for batch operations
- PR #215 created and merged
- Phase 2 CLI design documented in `.claude/adr-089-phase2-cli-design.md`
- Key UX decisions:
  - Non-interactive as default, `-i` for guided wizard
  - `--json` output for piping/scripting
  - Gradient of control: auto → semi → manual
  - ASCII diagram confirmation before commit
  - JSON export option for deferred ingestion
  - `kg vocab search` for similarity-based vocabulary discovery

### 2026-01-26
- Continued Phase 2 CLI implementation from previous session
- Completed all CLI commands: concept, edge, batch, vocab search
- Created validation module (`cli/src/lib/validation.ts`)
- Created interactive utilities (`cli/src/lib/interactive.ts`)
- Registered commands in `cli/src/cli/commands.ts`
- **Auth harmonization**: Removed `kg:*` OAuth scopes, now uses RBAC
  - `require_scope("kg:read")` → `require_permission("graph", "read")`
  - Created migration 040_graph_crud_permissions.sql
  - Updated concepts.py, edges.py, graph.py routes
- Fixed bug: EdgeResponse.created_by int→str conversion
- All CLI commands tested and working against local platform
