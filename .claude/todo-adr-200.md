# ADR-200: Breathing Ontologies — Implementation Tracker

**ADR:** `docs/architecture/database-schema/ADR-200-breathing-ontologies-self-organizing-knowledge-graph-structure.md`
**Branch:** `adr-200-client-exposure` (prev: `adr-200-phase-1` → merged PR #237)
**Started:** 2026-01-29
**Status:** Phase 1 Internal Box merged. Client Exposure in progress.

---

## Phase 1: Internal Box (No Client Contract Changes)

The goal: `:Ontology` nodes and `:SCOPED_BY` edges exist in the graph, maintained by internal code. All existing API responses, CLI output, and MCP tool results stay identical. Clients don't know anything changed.

### Schema

- [x] **Migration 044** — `schema/migrations/044_ontology_graph_nodes.sql`
  - [x] Create `:Ontology` nodes from `SELECT DISTINCT s.document` in existing graph
  - [x] Set properties: `ontology_id` (UUID), `name`, `creation_epoch`, `lifecycle_state = 'active'`
  - [x] Create `:SCOPED_BY` edges from every Source to its corresponding Ontology
  - [x] Handle empty graph case (no sources yet)

- [x] **Update init.cypher** — `schema/init.cypher`
  - [x] Add unique constraint on `Ontology.ontology_id`
  - [x] Add unique constraint on `Ontology.name`
  - [x] Add index on `Ontology.name`
  - [x] Add vector index for Ontology embeddings (1536-dim, cosine, same space as concepts)

### AGE Client

- [x] **New methods in `api/app/lib/age_client.py`** (no changes to existing method signatures)
  - [x] `create_ontology_node(name, description=None, embedding=None, ...)` — CREATE pattern
  - [x] `get_ontology_node(name)` — fetch by name, return all properties
  - [x] `list_ontology_nodes()` — return all Ontology nodes with properties
  - [x] `delete_ontology_node(name)` — DETACH DELETE the node
  - [x] `rename_ontology_node(old_name, new_name)` — SET name property
  - [x] `create_scoped_by_edge(source_id, ontology_name)` — Source→Ontology edge (MERGE)
  - [x] `ensure_ontology_exists(name)` — get-or-create for ingestion use
  - [x] `update_ontology_embedding(name, embedding)` — SET embedding on existing node

### Ingestion Pipeline

- [x] **Ingestion worker** — `api/app/workers/ingestion_worker.py`
  - [x] At job start: call `ensure_ontology_exists(ontology)` to upsert Ontology node
  - [x] After DocumentMeta: create `SCOPED_BY` edges for all source_ids
  - [x] Generate ontology embedding at creation time (name-based, via provider)
  - [x] Guard: skip embedding if provider is None
  - [x] Verify: existing `s.document` writes are untouched

### Existing Route Internals (append-only changes)

- [x] **Delete route** — `api/app/routes/ontology.py` DELETE handler
  - [x] Add `delete_ontology_node(name)` at end of cascade chain
  - [x] Response shape unchanged — same cleanup stats

- [x] **Rename route** — `api/app/routes/ontology.py` POST rename handler
  - [x] Add `rename_ontology_node(old, new)` alongside existing `SET s.document` query
  - [x] Response shape unchanged

### Ontology Embeddings

- [x] **Embedding generation** — name-based at creation time
  - [x] Name-based embedding at creation time (embed `"{name}"` or `"{name}: {description}"`)
  - [ ] Centroid recomputation as background job after ingest completes (deferred — Phase 2+)
  - [x] Reuse existing embedding provider config (same as concepts)
  - [x] Store on Ontology node `embedding` property

### Validation

- [x] Existing API responses unchanged (MCP ontology list/info — same shapes)
- [x] `kg ontology list` output identical (same columns: Ontology, Files, Chunks, Concepts)
- [x] MCP `ontology` tool results identical
- [x] Ingest a test document — both `s.document` AND `:SCOPED_BY` created
- [x] Delete an ontology — Ontology node removed, SCOPED_BY edges cleaned
- [x] Rename — node name updated alongside `s.document`
- [x] Migration idempotent — re-run with data produces no duplicates

---

## Phase 1: Client Exposure (Surface New Data to Consumers)

After the internal box is solid, expose the richer data model. Full commit to graph-node architecture — no fallback to string-only ontologies.

### Existing Surface Area (pre-ADR-200)

Discovered during codebase exploration:

| Component | list | info | files | delete | rename | create |
|-----------|------|------|-------|--------|--------|--------|
| API routes | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| CLI (`kg ontology`) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| TS API client | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| MCP tool | ✅ | ✅ | ✅ | ✅ | ❌ gap | — |
| Web frontend | ✅ | — | — | — | — | — |
| FUSE driver | (dirs) | — | — | — | — | — |

Key files: `api/app/models/ontology.py` (6 models), `api/app/routes/ontology.py` (5 endpoints), `cli/src/cli/ontology.ts` (5 subcommands), `cli/src/mcp-server.ts` (ontology tool, 4 actions), `cli/src/types/index.ts` (TS types), `web/src/types/ingest.ts` + `web/src/api/client.ts`

### API (additive changes only)

- [x] **Models** — `api/app/models/ontology.py`
  - [x] Add fields to `OntologyItem`: `ontology_id`, `lifecycle_state`, `creation_epoch`, `has_embedding`
  - [x] Add `OntologyNodeResponse` model for graph-node endpoint
  - [x] Add `OntologyCreateRequest` model (name, description)

- [x] **New endpoints** — `api/app/routes/ontology.py`
  - [x] `POST /ontology/` — create ontology explicitly (directed growth, before any ingest)
  - [x] `GET /ontology/{name}/node` — return Ontology graph node properties
  - [x] No facade wiring needed — routes follow existing pattern

- [x] **Extended existing responses**
  - [x] `GET /ontology/` — graph nodes are source of truth, includes empty ontologies (directed growth)
  - [x] `GET /ontology/{name}` — includes `node` object with full graph node properties

### CLI

- [x] Update TypeScript types in `cli/src/types/index.ts` (`OntologyNodeResponse` + enriched `OntologyItem`)
- [x] Add client methods in `cli/src/api/client.ts` (`createOntology`, `getOntologyNode`)
- [x] `kg ontology list` — shows `State` column (lifecycle_state)
- [x] `kg ontology info <name>` — shows `Graph Node` section (ID, state, epoch, embedding, description, search terms)
- [x] `kg ontology create <name> [--description]` — new subcommand

### MCP Server

- [x] `ontology` tool — new response fields pass through (JSON)
- [x] Add `create` action to ontology tool
- [x] Add `rename` action (fixed pre-existing gap)
- [x] Updated tool description with new action enum

### Web Frontend

- [x] Update `OntologyItem` type in `web/src/types/ingest.ts` (optional fields for backward compat)
- [x] Web API client unchanged — enriched response flows through `listOntologies()`
- [ ] Ontology list/selector views — display lifecycle state where shown (deferred — UI is primitive)
- [ ] Create ontology UI deferred to ADR-700 Ontology Explorer

### FUSE Driver

- [x] Reviewed `fuse/kg_fuse/filesystem.py` — no changes needed
- [x] FUSE lists ontologies as directories using only the `ontology` name field
- [x] New graph node properties are available but not consumed by the filesystem layer

### RBAC Permissions

- [x] Verified: `ontologies` resource already has `read`, `create`, `delete` actions (migration 028)
- [x] `POST /ontology/` uses `ontologies:create` — already granted to curator+
- [x] GET endpoints use `CurrentUser` only — no permission check needed
- [x] No new migration required for client exposure phase
- [ ] Phase 2: may need `write`/`update` action for `PUT /ontology/{name}/lifecycle`

---

## Later Phases (Not This Branch)

Tracked here for awareness. Each gets its own branch + todo.

### Phase 2: Lifecycle States & Directed Growth
- `lifecycle_state` property: active | pinned | frozen
- `PUT /ontology/{name}/lifecycle` endpoint
- Frozen ontologies reject new SCOPED_BY during ingestion
- Pinned ontologies exempt from demotion

### Phase 3: Breathing Worker
- New background worker: `ontology_breathing_worker`
- Mass scoring (degree centrality aggregation)
- Coherence scoring (diversity of internal concepts)
- Exposure calculation (weighted epoch delta)
- Promotion candidate ranking
- Proposal generation (stored as recommendations)

### Phase 4: Automated Promotion & Demotion
- Execute approved promotions (create Ontology, link anchor, reassign sources)
- Execute approved demotions (reassign by edge affinity, remove Ontology)
- Ecological ratio tracking
- Bezier curve profiles for promotion/demotion pressure
- Graduated automation: HITL → AITL → autonomous

### Phase 5: Ontology-to-Ontology Edges
- Derive inter-ontology edges from cross-ontology bridges
- OVERLAPS, SPECIALIZES, GENERALIZES edge types
- Explicit override edges
- Bridge view integration (ADR-700)

---

## Dev Notes

**API auth for manual testing:** Config lives at `~/.config/kg/config.json` (`kg config path`). Uses OAuth client credentials flow — get a token first, then use it.

```bash
KG_URL=$(jq -r '.api_url' ~/.config/kg/config.json)
CLIENT_ID=$(jq -r '.auth.oauth_client_id' ~/.config/kg/config.json)
CLIENT_SECRET=$(jq -r '.auth.oauth_client_secret' ~/.config/kg/config.json)

# Get bearer token via OAuth
KG_TOKEN=$(curl -s -X POST "$KG_URL/auth/oauth/token" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET" \
  | jq -r '.access_token')

# Example: hit ontology endpoint directly
curl -s -H "Authorization: Bearer $KG_TOKEN" "$KG_URL/ontology/" | python3 -m json.tool
```

---

## Decision Log

Record adjustments, surprises, and deviations from the ADR as we implement.

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-29 | Internal box first, client exposure second | Minimize disruption — existing contracts stay stable |
| 2026-01-30 | SCOPED_BY edges created after DocumentMeta, not per-chunk | Simpler — source_ids list already assembled at that point |
| 2026-01-30 | Ontology embedding: name-based at creation, centroid deferred | New ontologies have no concepts yet; centroid needs data |
| 2026-01-30 | All ADR-200 additions are non-fatal (try/except with warning) | s.document path remains functional if Ontology node ops fail |
| 2026-01-30 | Added `update_ontology_embedding` method (not in original plan) | Needed separate from create — embedding generated after node exists |
| 2026-01-30 | Full commit to graph-node architecture — no string fallback | User directive: no "fallback" to string-only ontologies |
| 2026-01-30 | MCP rename action is a pre-existing gap to fix | Discovered during codebase exploration — CLI has it, MCP doesn't |
| 2026-01-30 | List endpoint: graph nodes are source of truth | Empty ontologies (directed growth) now appear in list — Source-only ontologies still included as fallback |
| 2026-01-30 | FUSE needs no changes for client exposure | FUSE only uses ontology name for directory listing — ignores graph node properties |
