---
status: Draft
date: 2026-01-29
deciders:
  - aaronsb
  - claude
related: [22, 25, 26, 32, 46, 47, 52, 53, 65, 77, 100, 200, 206, 703]
---

# ADR-701: Vocabulary Administration Interface

## Context

The vocabulary system is a **self-regulating agentic cycle**, structurally the
twin of ontology annealing (ADR-200). Relationship types grow from LLM
extraction (ADR-601), are auto-categorized via embeddings (ADR-605), scored by
grounding contribution (ADR-604), classified by epistemic status (ADR-610), and
periodically **consolidated** — the expansion/consolidation "dreaming" cycle of
ADR-607, driven by zone pressure (ADR-603: COMFORT/WATCH/DANGER/EMERGENCY) and
an AITL consolidation worker that produces merge proposals. This is a loop that
restructures the vocabulary on a heartbeat, much as the annealing worker
restructures ontologies.

Two facts frame this ADR:

**1. The vocabulary cycle is already live — and already surfaced everywhere
except the web.** All vocabulary management happens through the CLI (`kg vocab`
— 20 subcommands) or ~20 REST endpoints. The backend is mature: schema, workers,
and endpoints for status/zones, types, profiles, config, consolidation, and
epistemic measurement all exist (see *Backend Alignment Verification*). The web
workstation has no vocabulary administration surface at all — only
`vocabularyStore.ts` (explorer color coding) and `OntologyFilterBlock` (query
filter).

**2. Its sibling cycle just got a web surface — and a pattern to follow.**
ADR-703 ("Ontology Lifecycle Administration Interface") faced the structurally
identical problem for ontology annealing: a self-regulating loop reachable only
through the CLI. ADR-703 resolved it with an **operational cohort** in the Admin
panel — the live `Ontology` tab in `AdminDashboard` (loop health / ecological
pressure / read-only config / proposals queue) — shipped as an MVP tab first,
with a dedicated `/admin/ontology-lifecycle` route as the deferred target state.
The vocabulary cycle is the direct sibling (ADR-200 Design Principle 4:
self-similarity across scale) and warrants **the same cohort, the same shape,
the same incremental path.**

> **Revision note (2026-05).** This ADR was originally drafted (2026-01-29) as a
> six-tab, dedicated-route interface (Dashboard / Types / Profiles / Config /
> Health / Merge) — before the ADR-703 OntologyTab pattern existed. That design
> was over-scoped for a first increment: it led with a draggable Bézier curve
> editor and chord diagrams rather than the operating loop. This revision
> reframes the ADR around **parity with the ontology lifecycle cohort**, leads
> with a lean MVP tab, and demotes the rich six-tab design to a clearly-deferred
> target state. The backend verification below is unchanged and still valid.

## Decision

Surface the vocabulary consolidation cycle in the web workstation as a
**first-class agentic-cycle cohort**, mirroring the ontology lifecycle interface
(ADR-703). Ship it the same way ADR-703 shipped: an MVP tab in the existing
`AdminDashboard` first, graduating to a dedicated route as richer surfaces
accrete.

### 1. MVP — a "Vocabulary" tab in Administration, cohort to "Ontology"

Add a `Vocabulary` tab to the existing `AdminDashboard` (alongside Account /
Users / Roles / System / **Ontology**), as the **direct cohort to the Ontology
tab**. It reuses the OntologyTab structure (`web/src/components/admin/`,
`components.tsx` shared `Section`/`InfoCard`/`StatusBadge`), so the two cycles
read as siblings. Four panels map one-to-one onto the OntologyTab cohort:

| Vocabulary panel (MVP) | Mirrors OntologyTab panel | Data source |
|------------------------|---------------------------|-------------|
| **Consolidation Loop** — pruning mode (Naive/HITL/AITL), enable state, last/next run, pending merge proposals, vocab size, "Run consolidation" | Annealing Loop | `GET /vocabulary/status`, consolidation worker status |
| **Vocabulary Pressure** — zone badge (COMFORT/WATCH/DANGER/EMERGENCY), aggressiveness curve with current-position marker, effective aggressiveness | Ecological Pressure | `GET /vocabulary/status` (zone, size, thresholds, profile) |
| **Configuration** — durable vocabulary config (thresholds, profile, pruning mode), **read-only here — adjust via `kg vocab` CLI** | Configuration (`annealing_options`) | `GET /admin/vocabulary/config` |
| **Actions** — job-dispatch triggers for the four worker operations (consolidate / refresh categories / remeasure epistemic / generate embeddings); fire-and-poll, toast the `job_id` | Annealing Loop's "Run cycle" trigger | `POST /vocabulary/jobs {kind}` (new), job-status polling |

The MVP is **present-information plus triggers** — it surfaces state and
*dispatches jobs*, but does **not** review/approve individual proposals
(per-proposal merge approval is deferred to the target-state Merge tab).

This is **not** an explorer plugin (explorers visualize graph *data*; this
operates the vocabulary *cycle* — the Edge Explorer, ADR-611, already covers
visualization). It follows the non-explorer admin pattern of the Ontology tab.

The aggressiveness curve renders read-only in the MVP (the CLI already produces
an ASCII version; the web shows the real curve with the current-position
marker). Interactive curve *editing* is target-state, below.

### 1a. Vocabulary operations dispatch as jobs (parity with annealing)

The vocabulary subsystem predates the database-driven job system (ADR-100). Its
four worker operations — `vocab_consolidate`, `vocab_refresh`,
`epistemic_remeasurement`, `vocab_embedding` — already run as **jobs** when
fired *automatically* by their launchers (hysteresis / cron), but their *manual*
HTTP entry points (`POST /vocabulary/consolidate`, `/refresh-categories`,
`/epistemic-status/measure`, `/generate-embeddings`) execute **synchronously
inside the request** — a pre-jobs legacy. Ontology annealing, by contrast,
triggers a job (`POST /ontology/annealing-cycle` → `queue.enqueue(...)`).

To reach parity, manual vocabulary triggers move onto the job model. Add a
single unified dispatch endpoint:

```
POST /vocabulary/jobs   { "kind": "consolidate" | "refresh" | "remeasure" | "embed", ...params }
  → queue.enqueue(job_type=<worker for kind>, job_data=...) ; auto-approve ; return { job_id }
```

This mirrors `/ontology/annealing-cycle` exactly (enqueue + auto-approve, client
polls job status — ADR-100), reuses the four existing workers unchanged, and is
gated `vocabulary:write`. One endpoint, four kinds — minimal new surface, no
collision with the existing synchronous endpoints (which remain for the CLI and
for callers that want inline results). The synchronous endpoints are **not**
wired to the UI: a button must not block on an LLM consolidation, and dispatch
is what gives the operation job-queue visibility.

This is the only backend addition the MVP requires; the read panels
(Consolidation Loop, Vocabulary Pressure, Configuration) consume endpoints that
already exist.

### 2. Target state — dedicated route with richer tabs (deferred)

As the cohort proves out, graduate to a dedicated `/admin/vocabulary` route with
the fuller tab set the original draft described. These are **deferred target
state**, not MVP scope, and should accrete one at a time the way ADR-703's tabs
do:

- **Types** — sortable/filterable table of all relationship types with a detail
  panel (category scores, similar/opposite types, QA analysis, epistemic
  detail). Data: `GET /vocabulary/types`, `/category-scores/{type}`,
  `/similar/{type}`, `/analyze/{type}`, `/epistemic-status/{type}`.
- **Profiles** — interactive Bézier curve editor for aggressiveness profiles
  (draggable control points replacing numeric CLI input). The single most
  complex UI element; deferred precisely because it is not load-bearing for
  operating the loop. Data: `GET/POST/DELETE /admin/vocabulary/profiles`.
- **Config (interactive)** — threshold sliders with live zone/aggressiveness
  preview, addressing configuration coupling. Promotes the MVP's read-only
  Configuration panel to editable. Data: `PUT /admin/vocabulary/config`.
- **Health** — epistemic status diagnostics: classification table, distribution,
  anomaly highlights, category-flow chord diagram, sync detection. Data:
  `GET/POST /vocabulary/epistemic-status`, `/category-flows`, `/sync`.
- **Merge (full)** — the consolidation workbench with comparison, deferral, and
  persisted review state (see the *Consolidation Review Is Stateless* gap).

The MVP's four panels become the route's landing "Dashboard"; the rest are the
progressive-disclosure tabs.

### 3. CLI parity

The CLI already carries the full vocabulary surface (`kg vocab status`, `list`,
`consolidate`, `merge`, `similar`, `analyze`, profiles, config, epistemic), so
the web MVP needs no new CLI commands — it is catching the CLI up, not the
reverse. The read-only Configuration panel directs operators to `kg vocab` for
mutation. One nuance follows from §1a: the web Actions panel *dispatches jobs*,
whereas the existing CLI verbs (`kg vocab consolidate`, etc.) still run
*synchronously*. Giving those CLI verbs an optional job-dispatch flag (so both
surfaces enqueue identically) is a sensible follow-up but is not MVP-blocking —
the synchronous CLI path remains valid.

### 4. Permission model

Reuses existing RBAC (ADR-404 / ADR-410), parallel to ADR-703's ontology gates:

| Action | Minimum capability |
|--------|-------------------|
| View the Vocabulary tab / any panel | `vocabulary:read` |
| Approve/reject a consolidation proposal, run consolidation, trigger merge | `vocabulary:write` |
| Edit profiles / mutate config (target-state interactive tabs) | `vocabulary_config:write` |

The tab requires `vocabulary:read` to appear; `hasPermission()` disables
(not hides-then-rejects) controls a user cannot use.

### 5. Component architecture

MVP — one tab component mirroring `OntologyTab.tsx`:

```
web/src/components/admin/
├── VocabularyTab.tsx              # MVP: 4-panel cohort (loop/pressure/config/proposals)
└── VocabularyPressurePanel.tsx    # mirrors AnnealingPressurePanel.tsx (read-only curve)
```

Registered in `AdminDashboard.tsx` exactly like the Ontology tab: add
`'vocabulary'` to the `TabType` union (`types.ts`), a permission-gated
`TabButton`, and a conditional render. A `vocabularyAdminStore` (Zustand,
parallel to `ontologyLifecycleStore`) holds status/config/proposals; it may
extend or sit beside the existing `vocabularyStore` (explorer coloring).

Target-state route components (`VocabularyDashboard.tsx`, `TypesTab.tsx`,
`ProfilesTab.tsx`, `BezierCurveEditor.tsx`, `HealthTab.tsx`, `MergeTab.tsx`)
land with their respective deferred tabs.

## Backend Alignment Verification

The database schema, API endpoints, and worker implementations were audited
against the UI's expectations. The vocabulary backend has been built
incrementally across 8+ ADRs and ~10 migrations. This section documents what's
confirmed working and the two gaps that affect only the deferred Merge tab.

### Confirmed: Schema Supports All UI Features

| Schema Component | Table / Location | Status |
|-----------------|------------------|--------|
| Relationship types (24 columns) | `kg_api.relationship_vocabulary` | Complete — includes category scoring, epistemic fields, embeddings |
| Configuration (11 keys) | `kg_api.vocabulary_config` | Seeded — vocab_min/max/emergency, thresholds, pruning mode, profile name |
| Aggressiveness profiles | `kg_api.aggressiveness_profiles` | 8 builtin profiles seeded (Migration 017) with `control_x1/y1/x2/y2` columns |
| Merge audit trail | `kg_api.vocabulary_history` | Complete — action, performed_by, target_type, reason, zone, vocab_size_before/after |
| Synonym clusters | `kg_api.synonym_clusters` | Complete — cluster_id, member_types, similarity, merge_recommended flag |
| Pruning recommendations | `kg_api.pruning_recommendations` | Complete — status (pending/approved/rejected/executed), reviewer_notes, expires_at |
| Staleness counters | `public.graph_metrics` | Complete — vocabulary_change_counter with delta tracking |
| Graph vocabulary nodes | Apache AGE `:VocabType` | Complete — epistemic_status, epistemic_stats, epistemic_measured_at stored as node properties |
| Graph category nodes | Apache AGE `:VocabCategory` | Complete — `:IN_CATEGORY` relationships from VocabType |

### Confirmed: API Endpoints Cover All UI Needs

All ~20 vocabulary endpoints verified present and functional:

- **Status**: `GET /vocabulary/status` — vocab size, zone, aggressiveness, builtin/custom/category counts, thresholds. Powers the MVP's Consolidation Loop and Vocabulary Pressure panels directly.
- **Profiles**: `GET/POST/DELETE /admin/vocabulary/profiles` — Bézier control points accepted with validation (x: 0.0–1.0, y: -2.0–2.0). Profile creation, listing, deletion all work. Builtin profiles protected.
- **Config**: `GET`/`PUT /admin/vocabulary/config` — Supports all 11 parameters as optional partial updates. Returns computed zone/aggressiveness after update (enables live preview).
- **Types**: `GET /vocabulary/types` — Returns `EdgeTypeListResponse` with active/builtin/custom counts and full `EdgeTypeInfo` per type including category scoring and epistemic status.
- **Category flows**: `GET /vocabulary/category-flows` — Returns inter-category chord diagram matrix. Ready for visualization.
- **Merge**: `POST /vocabulary/merge` — Creates audit trail in `vocabulary_history` via `AGEClient.merge_edge_types()`.
- **Consolidation**: `POST /vocabulary/consolidate` — AITL workflow returns auto_executed, needs_review, rejected lists.
- **Epistemic**: `GET/POST /vocabulary/epistemic-status` — Measurement, listing, and per-type detail all functional.
- **Sync**: `POST /vocabulary/sync` — Dry-run capable, returns missing/synced/failed lists.

### Confirmed: Workers and Scheduled Jobs Operational

| Worker | File | Trigger |
|--------|------|---------|
| `vocab_consolidate_worker` | `api/app/workers/vocab_consolidate_worker.py` | VocabConsolidationLauncher (inactive ratio > 20%) |
| `vocab_refresh_worker` | `api/app/workers/vocab_refresh_worker.py` | CategoryRefreshLauncher |
| `epistemic_remeasurement_worker` | `api/app/workers/epistemic_remeasurement_worker.py` | EpistemicRemeasurementLauncher (change counter delta ≥ threshold) |

All three workers are registered in `main.py` and integrated with the job queue
system. The epistemic remeasurement runs on a cron schedule (`0 * * * *` —
hourly) with hysteresis via the graph_metrics delta mechanism. The consolidation
worker is the vocabulary analog of the annealing worker — the loop the MVP's
Consolidation Loop panel observes.

### Gap (Merge tab only): Consolidation Review Is Stateless

The AITL consolidation endpoint (`POST /vocabulary/consolidate`) returns
`needs_review` items in the HTTP response, but **does not persist them**. If the
user navigates away after running consolidation, deferred review items are lost.

The schema exists — `kg_api.pruning_recommendations` has a `status` column
(pending/approved/rejected/executed) with `reviewed_by`, `reviewer_notes`, and
`expires_at` — but the consolidation code path does not write to it. The correct
long-term fix is to persist recommendations to that table (no schema change
needed). This affects only the deferred full Merge tab, not the MVP.

### Gap (Merge tab only): Prune and Deprecate Execution Are Stubbed

`VocabularyManager._execute_prune()` and `._execute_deprecate()`
(vocabulary_manager.py lines ~1091-1150) contain TODO placeholders. Merge
execution works fully, but hard-delete pruning and formal deprecation are
incomplete. **Consistent with the platform's append-only / no-destructive-delete
posture (ADR-203, ADR-206), the UI should never expose a hard-delete action.**
Unused-type cleanup uses **deactivation** (`is_active = false`), which works
today — types are deprecated, never destroyed, preserving the epistemic trail.

### MVP Requires Zero Backend Changes

The MVP cohort (Consolidation Loop / Vocabulary Pressure / read-only
Configuration / Proposals) consumes only endpoints that already exist. The two
gaps above are scoped entirely to the deferred full Merge tab.

## Consequences

### Positive

- The vocabulary consolidation cycle becomes observable in the web workstation,
  reading as the direct sibling of the ontology annealing cycle — one mental
  model, two scales (ADR-200 self-similarity).
- The MVP ships against today's backend with zero backend changes and minimal UI
  (one tab mirroring OntologyTab) — fast path to value.
- The interface degrades gracefully and accretes incrementally, exactly as
  ADR-703 does; each deferred tab renders against whatever backend exists.
- Non-CLI operators can finally see vocabulary zone/pressure and review
  consolidation proposals without terminal access.
- Reuses established patterns wholesale — OntologyTab cohort, `AdminDashboard`
  tab registration, ADR-604 Bézier infrastructure (for the deferred Profiles
  tab), ADR-404/082 permission gating.

### Negative

- Two surfaces (the ontology and vocabulary cohorts) now share a maintenance
  burden; changes to the shared admin `components.tsx` affect both.
- The deferred Profiles tab's interactive Bézier editor remains non-trivial UI
  work — but it is explicitly out of MVP scope, which removes it from the
  critical path.
- The full Merge tab depends on the two backend gaps above; until they land,
  consolidation review is best-effort (component state) and pruning is
  deactivation-only.

### Neutral

- The MVP stays inside `AdminDashboard`; the dedicated `/admin/vocabulary` route
  is deferred until the richer tabs justify it (mirrors ADR-703's MVP→route
  graduation).
- A `vocabularyAdminStore` may extend or sit beside the existing
  `vocabularyStore` (explorer coloring vs admin state).
- New RBAC resources (`vocabulary:read/write`, `vocabulary_config:read/write`)
  need registration if not already present.
- The category-flow chord diagram (deferred Health tab) could be shared with the
  Edge Explorer (ADR-611).

## Alternatives Considered

### A. Add a Vocabulary section to the System tab

Put vocabulary management as another collapsible `<Section>` inside the existing
System tab.

**Rejected because:** the System tab is already ~884 lines (AI extraction, API
keys, embedding profiles). The vocabulary cycle deserves its own cohort, peer to
the Ontology tab — not a section buried inside an unrelated tab. ADR-703 rejected
the identical option for the annealing cohort.

### B. Build as an explorer plugin

Register vocabulary management as an explorer alongside Force Graph, Document
Explorer, etc.

**Rejected because:** vocabulary administration *operates a cycle*; explorers
*visualize data*. The Edge Explorer (ADR-611) already handles vocabulary
visualization. ADR-703 drew the same boundary for ontologies (operate at
`/admin`, explore at `/explore`).

### C. Lead with the dedicated six-tab route (the original 2026-01 draft)

Ship the full `/admin/vocabulary` route with six intent-based tabs as the first
increment.

**Rejected because:** over-scoped for increment one, and it led with the wrong
thing — a draggable Bézier editor and chord diagrams instead of the operating
loop. It also predated the OntologyTab cohort pattern, so the two sibling cycles
would not have rhymed. The six-tab design survives as **deferred target state**
(§2); the MVP cohort (§1) is increment one, matching ADR-703's MVP→route path.

### D. One combined "vocabulary + ontology lifecycle" admin surface

Fold both cycles into a single lifecycle admin page.

**Rejected because:** they are distinct subsystems with distinct vocabularies,
proposals, and configuration. ADR-703 keeps the ontology cohort its own tab;
this ADR keeps vocabulary its own tab. They *rhyme* via a shared cohort shape and
cross-link, but neither owns the other.

## Implementation Notes

**MVP (increment one):** a single `Vocabulary` tab in `AdminDashboard`, peer to
the `Ontology` tab, with the four-panel cohort (§1): Consolidation Loop,
Vocabulary Pressure (read-only curve), read-only Configuration, Proposals queue.
Backed entirely by existing endpoints — zero backend changes. Mirror
`OntologyTab.tsx` / `AnnealingPressurePanel.tsx` structure and the
`AdminDashboard` tab-registration steps.

Recommended order, mirroring ADR-703's incremental graduation:

1. **MVP cohort tab** — the four panels above. Delivers vocabulary-cycle
   visibility against today's backend first; the most urgent gap.
2. **Types tab** — buildable today against `GET /vocabulary/types`; promotes the
   tab toward the dedicated route.
3. **Interactive Config** — promote the read-only Configuration panel to editable
   (`PUT /admin/vocabulary/config`) with live zone preview.
4. **Profiles tab** — the Bézier curve editor (ADR-604 infrastructure). Deferred;
   not load-bearing for operating the loop.
5. **Health tab** — epistemic diagnostics and category-flow chord diagram.
6. **Full Merge tab** — depends on the two backend gaps (persisted review,
   deactivation-only cleanup) landing first.

Graduate from the `AdminDashboard` tab to the dedicated `/admin/vocabulary`
route once tabs 2–6 justify the space — the §1 cohort becomes the route's
landing Dashboard.

## Related ADRs

- **ADR-200** — Annealing Ontologies (the sibling cycle; this ADR is its
  vocabulary-scale twin — Design Principle 4, self-similarity across scale)
- **ADR-206** — Closed-vocabulary annealing actions & epistemic ledger
  (append-only / no-destructive-delete posture this interface honors)
- **ADR-703** — Ontology Lifecycle Administration Interface (the cohort pattern,
  MVP→route path, and permission model this ADR mirrors)
- **ADR-100** — Database-driven job dispatch (the queue the §1a unified
  `/vocabulary/jobs` endpoint enqueues onto; parity with `/ontology/annealing-cycle`)
- **ADR-607** — Vocabulary Expansion-Consolidation Cycle (the "dreaming" loop
  this interface operates)
- **ADR-603** — Automatic edge vocabulary expansion with zones (COMFORT/WATCH/
  DANGER/EMERGENCY pressure surfaced in the Vocabulary Pressure panel)
- **ADR-600** — Original 30-type taxonomy (the vocabulary this interface manages)
- **ADR-601** — Dynamic relationship vocabulary (capture and expansion model)
- **ADR-602** — Autonomous vocabulary curation (AITL consolidation workflow)
- **ADR-604** — Grounding-aware vocabulary management & Bézier profiles (scoring
  model; curve infrastructure for the deferred Profiles tab)
- **ADR-605** — Probabilistic vocabulary categorization (category confidence)
- **ADR-608** — Vocabulary embedding similarity (similar/opposite detection)
- **ADR-610** — Epistemic status classification (health measurement model)
- **ADR-611** — Vocabulary explorers (visualization complement — explores data;
  this ADR operates the cycle)
