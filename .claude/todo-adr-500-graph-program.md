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

## Phase 2a: Cypher Safety Gate (secure the front door)

Wire the existing validator checks as a guard on `/query/cypher` so raw
Cypher can no longer write to the graph or trigger unbounded traversals.
No new endpoints — just defense.

- [ ] Extract Cypher safety checks from `program_validator.py` into a
      reusable `cypher_guard.py` module (write-keyword scan, path-length
      cap, sanitization)
- [ ] Wire `cypher_guard` as a dependency/middleware on `POST /query/cypher`
- [ ] Reject queries containing write keywords (CREATE, SET, DELETE, MERGE,
      REMOVE, DROP) with clear error messages
- [ ] Reject queries with unbounded variable-length paths (`[*]`, `[*3..]`)
- [ ] Add escape hatch: admin-only flag to bypass guard (for migrations/maintenance)
- [ ] Tests: write-keyword rejection, path-length rejection, clean queries pass
- [ ] Verify all existing web UI query patterns still work through the gate

## Phase 2b: Notarization Endpoints (ADR-500 Phase 2)

Server-side validation, storage, and retrieval of notarized programs.

- [ ] `POST /programs` — validate + store → return ID + notarized program
- [ ] `POST /programs/validate` — dry-run validation (no store)
- [ ] `GET /programs/{id}` — retrieve a notarized program
- [ ] Migration 052: add 'program' to `valid_definition_type` CHECK constraint
- [ ] Update `query_definition.py`: add 'program' to `DEFINITION_TYPES`
- [ ] Register programs router in `main.py`
- [ ] Tests: create, validate, retrieve, auth, ownership

## Phase 2c: Client Integration

Update all clients to use notarized programs or validated Cypher.

- [ ] TypeScript types (`web/src/types/program.ts`) — mirror Python AST models
- [ ] Web API client methods: `createProgram()`, `getProgram()`, `validateProgram()`
- [ ] Web Cypher editor: submit through validation gate, show errors inline
- [ ] Web multi-statement queries: construct GraphProgram, notarize, execute
- [ ] CLI: `kg program create`, `kg program validate`, `kg program run`
- [ ] MCP: program tools for agent use
- [ ] Fix #280 inconsistencies (include_grounding on related/connect) as part of this pass

## Phase 2d: Internal Cypher Audit

Ensure server-side Cypher (routes, workers, facades) also follows safe patterns.
These are trusted internal queries, but defense-in-depth says audit them.

- [ ] Audit all `_execute_cypher()` call sites (~30 in routes/queries.py alone)
- [ ] Categorize: read-only queries vs write queries (ingestion, graph mutations)
- [ ] Write queries: verify they only exist in ingestion/mutation code paths
- [ ] Consider: separate read-only and read-write database connections
- [ ] Document the internal query safety model

## Phase 2e: Rename & Cleanup

Align naming across spec, code, and docs. Resolve the route/allowlist mismatch.

- [ ] Update spec: "blessed" → "notarized" throughout
- [ ] Update `program_validator.py` docstrings
- [ ] Resolve allowlist endpoint names vs actual route paths:
      | Allowlist name | Actual route | Decision |
      |----------------|-------------|----------|
      | `/search/concepts` | `POST /query/search` | ? |
      | `/search/sources` | `POST /query/sources/search` | ? |
      | `/concepts/details` | `GET /query/concept/{id}` | ? |
      | `/concepts/related` | `POST /query/related` | ? |
- [ ] Decide: aliased routes, or update allowlist to match reality?
- [ ] Consolidate `_get_graph_generation()` (#277) if touched
- [ ] Extract grounding/caching mixin (#278) if touched
- [ ] Migrate remaining query_facade.py callers (#279) if natural

---

## Phase 3 (future): Server-Side Execution

- [ ] `POST /programs/{id}/execute` — run notarized program server-side
- [ ] Eliminates N+1 client round-trips
- [ ] Enables headless agent execution

## Phase 4 (future): Advanced Language Features

- [ ] `ConditionalOp` — branching logic in programs
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
