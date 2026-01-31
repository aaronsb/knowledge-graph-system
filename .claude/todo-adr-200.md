# ADR-200: Breathing Ontologies — Implementation Tracker

**ADR:** `docs/architecture/database-schema/ADR-200-breathing-ontologies-self-organizing-knowledge-graph-structure.md`
**Branch:** `main` (all phases merged)
**Started:** 2026-01-29
**Status:** Phases 1-3b complete (PRs #237, #238, #239, #240, #246). Next: Phase 5 or Phase 4.

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
- [x] Phase 2: `ontologies:write` action added in migration 045 for `PUT /ontology/{name}/lifecycle`

---

## Phase 2: Lifecycle States, Write-Access Control & Owner Provenance

**Branch:** `adr-200-phase-2`
**Plan:** `~/.claude/plans/enumerated-booping-whistle.md`

### Lifecycle state semantics

| State | Ingest | Rename | Delete | Demotion (Phase 3+) |
|-------|--------|--------|--------|---------------------|
| `active` | yes | yes | yes | eligible |
| `pinned` | yes | yes | yes | **immune** |
| `frozen` | **no** | **no** | yes | immune |

`pinned` has no enforcement in Phase 2 — marker for Phase 3's breathing worker.

### Frozen semantics — source boundary protection

Concepts are **global** (not scoped to ontologies). Freezing protects the ontology's *source boundary*, not concepts themselves.

- **Blocked:** ingesting INTO frozen ontology (new Sources), renaming it
- **Not blocked:** cross-ontology edges pointing at concepts in frozen ontologies, concept-level relationships (IMPLIES/SUPPORTS/CONTRADICTS), reads/queries
- **Fallback principle:** if future pipeline logic ever needs to create a concept within a frozen ontology, fall back to the requesting (active) ontology instead of failing

### Tasks

- [x] **Migration 045** — `schema/migrations/045_ontology_lifecycle_permissions.sql`
  - [x] Add `write` to `ontologies` resource `available_actions` array
  - [x] Grant `ontologies:write` to curator, admin, platform_admin
  - [x] Follow migration 040 pattern (WHERE NOT EXISTS idempotency)

- [x] **AGE client lifecycle methods** — `api/app/lib/age_client.py`
  - [x] `update_ontology_lifecycle(name, new_state)` — SET lifecycle_state, validate {active, pinned, frozen}
  - [x] `is_ontology_frozen(name)` — convenience check, False for nonexistent

- [x] **Owner provenance** — `created_by` on Ontology nodes
  - [x] `created_by: Optional[str]` param on `create_ontology_node()` + `ensure_ontology_exists()`
  - [x] Route: `POST /ontology/` passes `current_user.username`
  - [x] Worker: passes `job_data.get('username')`
  - [x] Models: `created_by` field on `OntologyNodeResponse`, `OntologyItem`

- [x] **Pydantic models** — `api/app/models/ontology.py`
  - [x] `LifecycleState` enum: active | pinned | frozen
  - [x] `OntologyLifecycleRequest(state: LifecycleState)`
  - [x] `OntologyLifecycleResponse(ontology, previous_state, new_state, success)`

- [x] **PUT /ontology/{name}/lifecycle route** — `api/app/routes/ontology.py`
  - [x] `require_permission("ontologies", "write")`
  - [x] 404 if not found, idempotent no-op if already in target state
  - [x] Log transition with username

- [x] **Frozen enforcement** — two-layer
  - [x] Layer 1 (routes): `POST /ingest` + `POST /ingest/text` check target ontology → 403
  - [x] Layer 2 (worker): after `ensure_ontology_exists()`, check lifecycle → fail job
  - [x] Rename: check lifecycle before proceeding → 403
  - [x] Cross-ontology concept matching UNAFFECTED by frozen state

- [x] **CLI & MCP**
  - [x] Types: `LifecycleState`, `OntologyLifecycleResponse`, `created_by` fields
  - [x] Client: `updateOntologyLifecycle(name, state)` method
  - [x] CLI: `kg ontology lifecycle <name> <state>` subcommand, `Created By` in info
  - [x] MCP: `lifecycle` action on ontology tool

- [x] **Tests** — 58 passed (35 existing + 23 new)
  - [x] Unit: `TestUpdateOntologyLifecycle`, `TestIsOntologyFrozen`, `created_by` in create
  - [x] Route: lifecycle 200/404/422/no-op/401, frozen rename 403, created_by in node response
  - [x] Route: frozen ingest text 403, frozen ingest file 403 (+ AGEClient.close() assertion)

### Implementation order & dependencies

```
1. Migration 045          (standalone)        ─┐
2. AGE client methods     (standalone)        ─┤
3. Owner provenance       (depends on 2)       │
4. Pydantic models        (standalone)        ─┤─→ 9. Update tracker (final)
5. PUT lifecycle route    (depends on 2, 4)    │
6. Frozen enforcement     (depends on 2)       │
7. CLI & MCP              (depends on 5)       │
8. Tests                  (alongside each)    ─┘
```

### Files touched

| File | Change |
|------|--------|
| `schema/migrations/045_ontology_lifecycle_permissions.sql` | **NEW** |
| `api/app/lib/age_client.py` | +2 methods, `created_by` param |
| `api/app/models/ontology.py` | enum + 2 models + `created_by` fields |
| `api/app/routes/ontology.py` | PUT endpoint + frozen check in rename |
| `api/app/routes/ingest.py` | frozen checks (2 spots) |
| `api/app/workers/ingestion_worker.py` | frozen check + `created_by` passthrough |
| `cli/src/types/index.ts` | types |
| `cli/src/api/client.ts` | client method |
| `cli/src/cli/ontology.ts` | subcommand + info display |
| `cli/src/mcp-server.ts` | lifecycle action |
| `tests/unit/lib/test_age_client_ontology.py` | ~55 lines |
| `tests/api/test_ontology_routes.py` | ~70 lines |

---

## Phase 3a: Breathing Control Surface (Scoring & Manual Controls)

**Branch:** `adr-200-phase-3a`
**Depends on:** Phases 1-2 (all plumbing and controls available)
**Approach:** Build controls first, prove manually, then automate. The breathing worker is just automation of a manual process.

### Scoring Algorithms — COMPLETE

- [x] **Mass scoring** — Michaelis-Menten saturation of ontology statistics
  - `api/app/lib/ontology_scorer.py:calculate_mass()` — composite/50 normalization, k=2.0
  - Output: mass_score 0.0–1.0 on Ontology node

- [x] **Coherence scoring** — mean pairwise cosine similarity of concept embeddings
  - `api/app/lib/ontology_scorer.py:calculate_coherence()` — Gini-Simpson pattern from ADR-063
  - Sampled to 100 concepts for large ontologies
  - Output: coherence_score 0.0–1.0 on Ontology node

- [x] **Exposure calculation** — epoch delta with adjacency weighting
  - `api/app/lib/ontology_scorer.py:calculate_exposure()` — half-life 50 epochs + affinity weighting
  - Output: raw_exposure, weighted_exposure on Ontology node

- [x] **Protection scoring** — composite: sigmoid(mass × coherence) - exposure pressure
  - `api/app/lib/ontology_scorer.py:calculate_protection()` — can go negative for severely failing
  - Output: protection_score on Ontology node

### Read Controls — COMPLETE

- [x] `get_ontology_stats(name)` — concept/source/file/evidence/relationship counts
- [x] `get_concept_degree_ranking(name, limit)` — top concepts by degree centrality
- [x] `get_cross_ontology_affinity(name, limit)` — shared concept overlap between ontologies
- [x] `get_all_ontology_scores()` — cached scores from all Ontology nodes
- [x] `get_current_epoch()` — global epoch from graph_metrics
- [x] `get_ontology_concept_embeddings(name, limit)` — for coherence calculation

### Write Controls — COMPLETE

- [x] `update_ontology_scores(name, mass, coherence, protection, epoch)` — cache scores on node
- [x] `reassign_sources(source_ids, from, to)` — THE key primitive for demotion
  - Updates s.document, deletes old SCOPED_BY, creates new SCOPED_BY
  - Batched in chunks of 50, refuses frozen source ontology
- [x] `dissolve_ontology(name, target)` — non-destructive demotion (move then remove node)
  - Refuses pinned or frozen, moves all sources first
- [x] `batch_create_scoped_by_edges(source_ids, ontology_name)` — bulk SCOPED_BY creation

### API Routes — COMPLETE (7 endpoints)

| Method | Path | Permission |
|--------|------|------------|
| GET | `/ontology/{name}/scores` | CurrentUser |
| POST | `/ontology/{name}/scores` | ontologies:write |
| POST | `/ontology/scores` | ontologies:write |
| GET | `/ontology/{name}/candidates` | CurrentUser |
| GET | `/ontology/{name}/affinity` | CurrentUser |
| POST | `/ontology/{name}/reassign` | ontologies:write |
| POST | `/ontology/{name}/dissolve` | ontologies:write |

### CLI — COMPLETE (7 subcommands)

- [x] `kg ontology scores [name]` — show cached scores (one or all)
- [x] `kg ontology score <name>` — recompute scores for one
- [x] `kg ontology score-all` — recompute all scores
- [x] `kg ontology candidates <name>` — top concepts by degree
- [x] `kg ontology affinity <name>` — cross-ontology overlap
- [x] `kg ontology reassign <from> --to <target> --source-ids <ids...>`
- [x] `kg ontology dissolve <name> --into <target>`

### MCP — COMPLETE (7 actions)

- [x] `scores`, `score`, `score_all`, `candidates`, `affinity`, `reassign`, `dissolve`

### Tests — 115 passed (58 existing + 57 new)

- [x] Unit: OntologyScorer — mass, coherence, exposure, protection, cosine similarity
- [x] Unit: AGE client — stats, ranking, affinity, cached scores, update scores, reassign, dissolve
- [x] Route: GET/POST scores (200, 404), POST score-all, candidates (200, 404), affinity
- [x] Route: reassign (200, 403 frozen, 404), dissolve (200, 403 pinned, 404)

### Files

| File | Change |
|------|--------|
| `api/app/lib/ontology_scorer.py` | **NEW** — scoring algorithms |
| `api/app/lib/age_client.py` | +12 methods (6 read, 4 write, 2 helper) |
| `api/app/models/ontology.py` | +11 models |
| `api/app/routes/ontology.py` | +7 endpoints |
| `cli/src/types/index.ts` | +8 interfaces |
| `cli/src/api/client.ts` | +7 client methods |
| `cli/src/cli/ontology.ts` | +7 subcommands |
| `cli/src/mcp-server.ts` | +7 actions |
| `tests/unit/lib/test_ontology_scorer.py` | **NEW** — 29 tests |
| `tests/unit/lib/test_age_client_ontology.py` | +15 test classes |
| `tests/api/test_ontology_routes.py` | +7 test classes |

---

## Phase 3b: Breathing Worker (Proposals & Automation) — COMPLETE

**Branch:** `adr-200-phase-3b` (PR #246, merged 2026-01-30)
**Code review fixes:** PR #246 findings 1-8 addressed, merged
**Depends on:** Phase 3a (all controls available and manually proven)
**Pattern:** Same as `kg vocab consolidate` — graph traversal → scoring → LLM judgment → proposals

The worker automates what can now be done manually via the Phase 3a control surface.

### Worker Architecture

- [x] **Background job registration** — `ontology_breathing` worker type in job system
  - Heartbeat tied to epoch counter (graph_metrics), not wall-clock time
  - `BreathingLauncher` fires after configurable epoch interval (default: 5)
  - Atomic epoch claim via `UPDATE...WHERE...RETURNING` (TOCTOU fix, PR #246 review)

### Candidate Identification

- [x] **Promotion candidates** — high-degree concepts not yet ontologies
  - Uses Phase 3a: `get_concept_degree_ranking()` + `score_ontology()`
  - LLM evaluates borderline: "nucleus (should promote) or crossroads (should stay)?"
  - Neighbor context fetched via Cypher for richer LLM evaluation

- [x] **Demotion candidates** — low-protection ontologies
  - Uses Phase 3a: `score_all_ontologies()` + `get_cross_ontology_affinity()`
  - Skip pinned and frozen ontologies

### Proposal System

- [x] **Proposal storage** — `kg_api.breathing_proposals` table (migration 046)
  - Structured recommendations with mass/coherence/protection scores
  - 7-day expiry, status: pending/approved/rejected/expired
- [x] **Review interface** — CLI: `kg ontology proposals` / `approve` / `reject`
- [x] **API routes** — GET/POST proposals CRUD + `POST /ontology/breathing-cycle`
- [x] **MCP actions** — `proposals`, `proposal_review`, `breathing_cycle`

### LLM Evaluator

- [x] `api/app/lib/breathing_evaluator.py` — multi-provider (OpenAI, Anthropic, Ollama)
  - Promotion judgment: nucleus vs crossroads
  - Demotion judgment: absorb vs revive
  - `asyncio.to_thread()` for sync LLM calls in async context (PR #246 review)

### Centroid Recomputation

- [x] `api/app/lib/ontology_scorer.py:recompute_centroid()` — mass-weighted top-K centroid
  - Hysteresis: skip update if cosine similarity > 0.99
  - Runs as part of breathing cycle before candidate evaluation

### Files

| File | Change |
|------|--------|
| `schema/migrations/046_breathing_proposals.sql` | **NEW** — proposals table |
| `api/app/lib/breathing_evaluator.py` | **NEW** — LLM evaluation prompts |
| `api/app/services/breathing_manager.py` | **NEW** — cycle orchestration |
| `api/app/workers/breathing_worker.py` | **NEW** — job worker |
| `api/app/launchers/breathing.py` | **NEW** — epoch-driven trigger |
| `api/app/lib/ontology_scorer.py` | +centroid recomputation |
| `api/app/models/ontology.py` | +proposal models |
| `api/app/routes/ontology.py` | +4 proposal/cycle endpoints |
| `cli/src/cli/ontology.ts` | +5 proposal/breathe subcommands |
| `cli/src/mcp-server.ts` | +3 actions |
| `api/app/workers/ingestion_worker.py` | +launcher hook after epoch |
| `tests/unit/lib/test_breathing_evaluator.py` | **NEW** |
| `tests/manual/test_breathing_controls.sh` | **NEW** — 36 integration tests |

### Tests — 36 integration + 14 unit

- [x] Shell integration: `test_breathing_controls.sh` — 36 passed, 0 failed
- [x] Unit: `test_breathing_evaluator.py` — 14 tests (mock LLM responses, prompt construction)

---

## Phase 5: Ontology-to-Ontology Edges (Materialized Relationships)

**Branch:** `adr-200-phase-5`
**Depends on:** Phase 3 (scoring discovers what this phase materializes)
**Resequenced:** Phase 5 runs before Phase 4 because scoring (Phase 3) traverses cross-ontology bridges as part of its analysis. This phase materializes what scoring discovers into persistent edges. Phase 4's automated execution then uses these edges for routing.

Phase 5 is NOT a prerequisite for Phase 3 — the raw cross-ontology affinity data is already traversable from existing `:SCOPED_BY` infrastructure edges (not vocabulary). But materializing it gives Phase 4 a precomputed map.

- [ ] **Derived edges** — breathing worker emits as side effect of scoring
  - OVERLAPS: significant % of A's concepts also appear in B's sources
  - SPECIALIZES: A's concepts are a coherent subset of B's concept space
  - GENERALIZES: inverse of SPECIALIZES
  - Source property: `source: 'breathing_worker'`, epoch stamped

- [ ] **Explicit override edges** — human/AI declared
  - Same edge types, `source: 'manual'` or `source: 'ai'`
  - Explicit edges take precedence over derived when conflicting

- [ ] **Edge refresh** — recalculated each breathing cycle
  - Stale derived edges removed if no longer supported by concept data
  - Explicit edges persist unless manually removed

- [ ] **Integration** — ADR-700 Ontology Explorer bridge view, Phase 4 demotion routing

---

## Phase 4: Automated Promotion & Demotion (Execution)

**Branch:** `adr-200-phase-4`
**Depends on:** Phase 3 (proposals) + Phase 5 (materialized edges for routing)
**Pattern:** Graduated automation — HITL → AITL → autonomous

Converts worker from proposal-only (Phase 3) to proposal-and-execute.

- [ ] **Promotion execution** — on approved proposal
  - `create_ontology_node()` with anchor concept's name/embedding
  - `(:Ontology)-[:ANCHORED_BY]->(:Concept)` edge
  - Reassign first-order concept sources: batch `:SCOPED_BY` + `s.document` updates
  - Eventually consistent (same pattern as vocab consolidation merge)
  - `created_by: 'breathing_worker'`

- [ ] **Demotion execution** — on approved proposal
  - Route sources to highest-affinity candidate (Phase 5 OVERLAPS edges, or affinity query fallback)
  - Sources with no clear affinity → primordial pool
  - Remove `:Ontology` node; anchor concept survives
  - **No deletion, only movement**

- [ ] **Ecological ratio tracking**
  - Target: `ontology_count = f(total_concepts, desired_concepts_per_ontology)`
  - When primordial pool too large → increase promotion pressure
  - When ontologies too small → increase absorption pressure
  - Bezier curve profiles (reuse ADR-046 aggressiveness infrastructure)

- [ ] **Graduated automation levels**
  - [x] HITL: worker proposes, human approves — **operational in Phase 3b**
    - Ingest → epoch increment → launcher fires → breathing cycle → proposals → human review via CLI/MCP
  - [ ] AITL: worker proposes, LLM evaluates, human reviews exceptions
  - [ ] Autonomous: high-confidence proposals auto-execute within safety bounds
  - Safety: never auto-demote pinned/frozen, require multiple consecutive cycles for demotion

---

## Deferred (Not Phased Yet)

- [ ] Web UI: display lifecycle state in ontology views (primitive UI, low priority)
- [ ] Web UI: create ontology (deferred to ADR-700 Ontology Explorer)
- [ ] Meta-ontologies: can ontologies group into higher-order structures? (open question in ADR)

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
| 2026-01-30 | Frozen = source boundary protection, not concept isolation | Concepts are global; freezing blocks new Sources scoped to the ontology, not cross-ontology edges pointing at its concepts |
| 2026-01-30 | Fallback principle for frozen ontologies | If pipeline ever needs to create within a frozen ontology, fall back to requesting (active) ontology rather than failing |
| 2026-01-30 | AGEClient try/finally in ingest routes (code review) | Pre-existing resource leak pattern; fixed in our code with try/finally + close() |
| 2026-01-30 | Migration 045 updates `available_actions` array | Code review caught missing UPDATE to `kg_auth.resources` — added idempotent SET |
| 2026-01-30 | Phase 3 split into 3a (controls) + 3b (automation) | Build controls first, prove manually, then automate — same approach as vocab consolidate |
| 2026-01-30 | Coherence = mean similarity (not 1-diversity) | High coherence = tight domain. Plan said 1-diversity but mean similarity is more intuitive |
| 2026-01-30 | Exposure half-life 50 epochs | Balances new vs old ontologies — after 50 ingestions, exposure = 0.5 |
| 2026-01-30 | Reassign batched in 50s, frozen check on source | Key primitive for demotion; refuses moving FROM frozen ontologies |
| 2026-01-30 | Edge-agnostic SCOPED_BY queries for lifecycle | Phase 3a queries use `(c:Concept)-->(s:Source)-[:SCOPED_BY]->(o:Ontology)` — lifecycle depends only on the SCOPED_BY infrastructure edge, not on vocabulary or ingestion plumbing edge names like APPEARS |
| 2026-01-30 | SCOPED_BY added to SYSTEM_TYPES exclusion set | Infrastructure edges should not appear in vocabulary discovery or epistemic measurement |
| 2026-01-30 | Structural edge misuse tracked as future work (#241) | LLMs could generate SCOPED_BY as vocabulary — detection in integrity checker, healing via SIMILAR_TO replacement at low confidence |
| 2026-01-30 | Atomic epoch claim in breathing launcher (PR #246 review) | TOCTOU race: `UPDATE...WHERE counter diff >= N RETURNING` instead of read-then-write |
| 2026-01-30 | asyncio.to_thread for sync LLM calls (PR #246 review) | breathing_evaluator calls sync provider SDK; wrapping avoids blocking event loop |
| 2026-01-30 | Centroid hysteresis threshold 0.99 cosine | Skip embedding update if drift is negligible — avoids unnecessary writes |
| 2026-01-31 | Comprehensive Cypher injection hardening (PR #247) | Parameterized all f-string Cypher queries in routes layer; added regex validation for relationship type names that can't use $params in openCypher pattern syntax |
