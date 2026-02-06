# ADR-500: GraphProgram Notarization & Cypher Safety Gate

**ADR:** `docs/architecture/query-search/ADR-500-graph-program-dsl-and-ast-architecture.md`
**Spec:** `docs/language/specification.md` (merged PR #294)
**Branch:** TBD
**Status:** Phase 1 complete (language spec, validation rules, 109 executable tests). Phase 2 next.

---

## Context

The `/query/cypher` endpoint accepts raw user-typed Cypher and executes it
directly via `_execute_cypher()` with no write-keyword blocking, no query
complexity bounds, and no path-length caps. Auth is the only gate.

The GraphProgram validator (V010-V016 write keywords, V020-V023 API safety,
V030 variable-length path bounds) exists as an executable spec but isn't wired
into any execution path yet.

**Goal:** Make the validator the mandatory gate for all Cypher execution.
Programs are *notarized* (validated + signed by the server) before execution.
Raw unnotarized Cypher no longer reaches the database.

```
         ┌─────────────────────┐
         │  Little Nicky Nodes │
         │  says: notarize     │
         │  your queries or    │
         │  DETACH DELETE n    │
         │  goes brrr          │
         └─────────────────────┘
```

## Terminology

| Old term | New term | Why |
|----------|----------|-----|
| "blessed" | **notarized** | Industry precedent (Apple notarization). Server verifies safety, stamps it, doesn't modify it. |
| "blessing service" | **notarization service** | Same pattern: submit → check → stamp → execute |

---

## Phase 2a: Cypher Safety Gate ✓ (PR #297)

- [x] `cypher_guard.py` — reuses validator's `_check_cypher_safety`
- [x] Wired on `POST /query/cypher` — write keywords and unbounded paths rejected
- [x] 27 unit tests

## Phase 2b: Notarization Endpoints ✓ (PR #298)

- [x] `POST /programs`, `POST /programs/validate`, `GET /programs/{id}`
- [x] Migration 052, query_definition types updated, router registered
- [x] 20 API tests (including edge cases from review)

## Phase 2c: Client Integration ✓ (PR #299)

- [x] TypeScript AST types (web + CLI)
- [x] Web/CLI API client methods: createProgram(), validateProgram(), getProgram()
- [x] CLI `kg program validate|create|show` commands
- [x] MCP program tool (validate/create/get)
- [ ] Web Cypher editor: validation error display (deferred to UI pass)
- [ ] Web multi-statement: construct GraphProgram from editor (deferred to UI pass)
- [ ] Fix #280 include_grounding inconsistencies (deferred — separate PR)

## Phase 2d: Internal Cypher Audit ✓

Ensure server-side Cypher (routes, workers, facades) also follows safe patterns.
These are trusted internal queries, but defense-in-depth says audit them.

- [x] Audit all `_execute_cypher()` call sites (~30 in routes/queries.py alone)
- [x] Categorize: read-only queries vs write queries (ingestion, graph mutations)
- [x] Write queries: verified only in ingestion/mutation code paths (workers, serializers)
- [x] **CRITICAL FIX**: `POST /database/query` was missing cypher_guard — added safety gate
- [ ] Consider: separate read-only and read-write database connections (future)
- [ ] Document the internal query safety model (future)

## Phase 2e: Rename & Cleanup (partial)

Align naming across spec, code, and docs. Resolve the route/allowlist mismatch.

- [x] Update spec: "blessed" → "notarized" throughout (README.md, lifecycle.md, security.md)
- [x] Update `program_validator.py` docstrings (already uses "notarized")
- [x] Resolve allowlist endpoint names vs actual route paths:
      Decision: **keep as-is**. Allowlist names are internal dispatch identifiers
      for the Phase 3 executor, not HTTP routes. The executor will map these
      logical names to internal function calls directly.
      | Allowlist name | Internal dispatch target | Notes |
      |----------------|------------------------|-------|
      | `/search/concepts` | concept search service | semantic search |
      | `/search/sources` | source search service | passage search |
      | `/concepts/details` | concept details service | single concept |
      | `/concepts/related` | related concepts service | neighborhood |
      | `/concepts/batch` | batch concept retrieval | multi-concept |
      | `/vocabulary/status` | epistemic status service | vocab types |
- [ ] Consolidate `_get_graph_generation()` (#277) — not touched, defer
- [ ] Extract grounding/caching mixin (#278) — not touched, defer
- [ ] Migrate remaining query_facade.py callers (#279) — not touched, defer

---

## Phase 3: Server-Side Execution ✓

- [x] Response models: RawNode, RawLink, WorkingGraph, StepLogEntry, ProgramResult, ProgramExecuteRequest
- [x] `program_operators.py` — pure set-algebra operators (+, -, &, ?, !) with dangling link invariant
- [x] `program_dispatch.py` — CypherOp (AGE result parsing) + ApiOp (6 endpoint handlers)
- [x] `program_executor.py` — async orchestrator with timeout, abort, conditional branching
- [x] `POST /programs/execute` — endpoint (inline or stored program, re-validates, returns ProgramResult)
- [x] 22 operator unit tests, 8 executor unit tests (all pass without Docker)
- [x] Client integration: CLI `kg program execute`, MCP execute/chain/list tools
- [x] MCP syntax guide: tool description + `program/syntax` resource
- [x] Batch execution: `DeckEntry`, `BatchProgramResult`, `initial_w` seeding, `_execute_deck()`
- [x] Program discovery: `GET /programs` list endpoint with search
- [ ] API endpoint tests (extend tests/api/test_programs.py)

## Phase 3b: Agent Guidance Revision (in progress)

**Problem:** Current MCP tool descriptions steer agents toward single-tool-call patterns.
Programs and chains are invisible in all primary guidance surfaces.

**Survey findings (all text in `mcp-server.ts`):**

| Surface | Lines | Issue |
|---------|-------|-------|
| Server guide comment (L99-121) | Lists 6 tools, numbered 1-6 | Zero mention of programs. Agents see tools as the workflow. |
| `search` tool description | "Your ENTRY POINT to the graph" | Steers directly to search → concept → details loop. No mention that programs can compose these. |
| `explore-graph` prompt (L2921-3008) | 4-step workflow | Step 1: search, Step 2: concept connect, Step 3: concept details, Step 4: concept related. Zero mention of programs. |
| All 12 tool descriptions | Each is action-oriented | Every tool says "use this for X". None say "or compose this into a program". |
| `program/syntax` resource | Full reference with examples | Hidden behind a resource read. Agents must proactively discover it. |

**Consequence:** Agents that connect to this MCP server will:
1. Use search → concept → details one-call-at-a-time
2. Never discover that programs exist unless they read the program tool
3. Never discover chaining unless they read the syntax resource
4. Waste tool budget on N individual calls when 1 program could do the same

**Strategy:**
- [x] Rewrite server guide to present three tiers: quick lookups → programs → chains
- [x] Add program guidance to search tool's RECOMMENDED WORKFLOW
- [x] Rewrite explore-graph prompt to teach program-first exploration
- [x] Add cross-references from high-traffic tools (search, concept) to program tool
- [x] Keep program/syntax resource as deep reference (don't inflate tool descriptions)

## Phase 4 (future): Advanced Language Features

- [ ] `$param` substitution — reusable parameterized programs
- [ ] Text DSL parser — human-readable authoring format
- [ ] AST ↔ Blocks round-trip — block editor interop

---

## Related Issues

| Issue | What | Status |
|-------|------|--------|
| #277 | Consolidate `_get_graph_generation()` | Open (refactor) |
| #278 | Extract grounding/caching mixin | Open (refactor) |
| #279 | Migrate query_facade.py callers | Open (refactor) |
| #280 | Client consistency (include_grounding) | Open (3 fixes) |
| #295 | graph_accel generic config | Open (standalone) |
| #296 | graph_accel CI + PGXN | Open (standalone) |
