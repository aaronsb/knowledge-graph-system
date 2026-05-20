---
status: Draft
date: 2026-05-19
deciders:
  - aaronsb
  - claude
related: [28, 46, 82, 200, 203, 204, 700, 701]
---

# ADR-703: Ontology Lifecycle Administration Interface

## Context

ADR-200 ("Annealing Ontologies") established a self-organizing knowledge graph:
ontologies are graph nodes that grow, get promoted from concept clusters, and get
demoted back into the primordial pool when they fail to accumulate mass. A
background **annealing worker** runs on an epoch heartbeat — it scores every
ontology, identifies promotion and demotion candidates, asks an LLM for judgment
on borderline cases, and produces proposals.

**The loop is already live — and already autonomous.** As of migration 053
(commit `03ceef5b`, 2026-02-08) the `annealing_options.automation_level` key
defaults to `autonomous`. Every annealing cycle auto-approves and dispatches
*every* proposal it generates. This is a structural mutation of the graph —
Source nodes get re-scoped, Ontology nodes get created and destroyed — happening
on a heartbeat, unattended.

Two problems follow from that:

**1. Autonomous mode is blunt.** The worker knows exactly two behaviours:
`autonomous` (auto-approve everything) and `hitl` (wait for a human). There is no
confidence gate, no graduated middle tier, no adaptive pressure, and no
structural safety net. Five open issues describe the refinements that make
autonomy *trustworthy* rather than merely *automatic*:

| Layer | Issue | Gap | Verified state |
|-------|-------|-----|----------------|
| Graduated automation | #250 AITL | A middle tier — auto-approve only high-confidence proposals, human reviews exceptions | Worker has no `aitl` branch; only `autonomous`/`hitl` |
| Graduated automation | #251 Autonomous safety bounds | Consecutive-cycle demotion gate, high-confidence promotion gate | `_auto_approve_and_dispatch()` approves all proposals unconditionally |
| Adaptive control | #249 Bezier ecological pressure | Dynamic `demotion_threshold` / `promotion_min_degree` driven by the ecological ratio | `annealing_manager.py` carries the comment *"Threshold feedback is deferred (#249)"* — thresholds are static |
| Execution fidelity | #252 Per-source affinity routing | Route each source in a dying ontology to its own best-affinity target | `proposal_executor.execute_demotion()` calls `dissolve_ontology()` with a single absorption target |
| Execution fidelity | #241 Integrity worker | Detect and heal structural edge misuse (LLM emitting `SCOPED_BY`/`APPEARS` as semantic edges) | No structural-edge integrity worker exists |

These five are not five separate features. They are one body of work — the
unfinished half of ADR-200 Phase 4 — and they have a dependency order:

```
   #252 (per-source routing) ──┐
                               ├──→ #250 (AITL) ──→ #251 (autonomous safety bounds)
   #249 (Bezier feedback) ─────┘                          │
                                                          ↓
   #241 (integrity worker) ───────────────────────→  safety net
                          (load-bearing once the loop acts without review)
```

The architecture for all five is *already decided* in ADR-200 Phase 4
(graduated automation table, ecological ratio, Section 8 demotion routing,
Design Principle 6 edge-agnostic lifecycle). They are implementation tasks, not
new architectural decisions. This ADR does not re-decide them.

**2. The loop is invisible.** This is the genuinely new problem, and the reason
for this ADR. An autonomous process is restructuring the graph today, and the
only window into it is the CLI. There is no way for an operator to *see* the
lifecycle — what was promoted, what is queued for demotion, what the ecological
ratio is doing, whether automation is even on. The CLI carries the *manual* and
*review* controls (`kg ontology anneal`, `proposals`, `proposal --approve`,
`scores`, `lifecycle`) but **not** the *automation-policy* controls: there is no
CLI surface for `automation_level`, no `auto_execute_min_score`, no ecological
pressure tuning, and no integrity check. The web workstation has no ontology
lifecycle surface at all.

ADR-701 ("Vocabulary Administration Interface") faced the structurally identical
problem for the vocabulary subsystem — a sophisticated self-regulating system
reachable only through the CLI — and resolved it with a dedicated Admin entry.
The annealing lifecycle is the direct sibling (ADR-200 Design Principle 4:
self-similarity across scale) and warrants the same treatment.

## Decision

Add an **Ontology Lifecycle** administration surface to the web workstation that
makes the annealing loop visible and controllable, and close the CLI
automation-policy gap so both surfaces stay at parity. The five backend issues
(#241, #249, #250, #251, #252) are the feature substrate; this ADR governs how
that substrate is *surfaced and operated*.

### 1. New top-level Admin entry

Add a sidebar entry under the existing Admin category, mirroring ADR-701:

```
Admin
  ├── Administration       (existing: Account, Users, Roles, System)
  ├── Vocabulary           (ADR-701: /admin/vocabulary)
  └── Ontology Lifecycle   (new:      /admin/ontology-lifecycle)
```

Route: `/admin/ontology-lifecycle`. This is **not** an explorer plugin. Explorers
(`web/src/explorers/`, `registerExplorer()`) render graph data shapes; this is an
operational control panel. It follows the non-explorer admin-page pattern used by
`/admin` and `/admin/vocabulary` — a full-page tabbed layout under
`web/src/components/admin/`.

### 2. Tab structure

Tabs are organized by operator intent. Each maps to one or more of the five
backend issues:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Ontology Lifecycle                                                  │
├────────────┬───────────┬──────────────┬───────────┬─────────────────┤
│ Dashboard  │ Proposals │  Automation  │  Ecology  │   Integrity     │
└────────────┴───────────┴──────────────┴───────────┴─────────────────┘
```

#### Dashboard Tab — lifecycle at a glance (landing view)

The single-screen answer to "what is the annealing loop doing to my graph?"

- **Automation badge** — large, colored status: `HITL` / `AITL` / `AUTONOMOUS`,
  with last-cycle timestamp and next-cycle epoch estimate.
- **Population cards** — named ontologies vs primordial pool size, total
  concepts, average concepts per ontology.
- **Ecological gauge** — current ecological ratio against the target band, with
  a directional indicator (promotion pressure rising / absorption pressure
  rising). See the Ecology tab for the full curve.
- **Recent cycles** — last N annealing cycles: proposals generated, auto-approved,
  executed, rejected.
- **Pending review count** — proposals awaiting human attention (HITL backlog or
  AITL low-confidence exceptions), with a deep link to the Proposals tab.
- **Integrity alert count** — structural-edge violations detected since last
  heal, deep-linked to the Integrity tab.

Data sources: `GET /ontology/` (population), `GET /ontology/proposals`, the new
`GET /ontology/annealing/status` and `GET /ontology/annealing/ecology`
endpoints (see §4), and the ADR-203 graph epoch event log for cycle history.

#### Proposals Tab — the annealing queue

The review workbench. Surfaces #250 and #251.

- **Queue table** — every proposal: type (promotion / demotion), target,
  confidence score, status (`pending` / `approved` / `rejected` / `executed`),
  reviewer (`annealing_worker` for auto-approved vs a username), cycle epoch.
  Filterable by status, type, ontology — parity with `kg ontology proposals`.
- **Proposal detail panel** — LLM reasoning, scores that triggered it, and for
  **demotion** proposals the **per-source routing plan** (#252): a table showing
  each source in the dying ontology and its computed best-affinity destination,
  including sources returning to the primordial pool. This is where #252's
  correctness work becomes legible to an operator.
- **Review actions** — approve / reject with notes, gated by RBAC (§6). In AITL
  mode this tab is where the human handles the low-confidence exception set.
- **Consecutive-cycle indicator** (#251) — for demotion proposals, how many
  consecutive cycles this ontology has been proposed for demotion against the
  `demotion_consecutive_cycles` gate.

Data sources: `GET /ontology/proposals`, `GET /ontology/proposals/{id}`,
`POST /ontology/proposals/{id}/review`, and the new
`GET /ontology/proposals/{id}/routing-plan` (see §4).

#### Automation Tab — the policy controls

Where an operator sets *how much* autonomy to grant. Surfaces #250 and #251.

- **Automation level selector** — `HITL` / `AITL` / `Autonomous`, written to
  `annealing_options.automation_level`. Changing it shows a plain-language
  description of what the loop will do at that level.
- **AITL / Autonomous thresholds** — `auto_execute_min_score` (the confidence
  gate, #250), `demotion_consecutive_cycles` (the demotion hysteresis gate,
  #251), promotion high-confidence threshold (#251).
- **Safety bounds** — explicit, read-only confirmation that pinned and frozen
  ontologies are never auto-demoted (#251 — redundant with lifecycle checks but
  surfaced so operators can see the guarantee).
- **Cycle cadence** — epoch heartbeat interval and the enable/disable switch
  already present in `annealing_options`.

Data sources: the new `GET`/`PUT /ontology/annealing/config` (see §4).

#### Ecology Tab — adaptive pressure (#249)

Makes the ecological feedback loop visible. ADR-701 named the underlying
problem "curve blindness": a Bezier curve defined by four floats is a visual
concept trapped in a text interface. The same applies here.

- **Ecological ratio chart** — total concepts, total ontologies, average per
  ontology, plotted against the target band over recent epochs.
- **Pressure curve editor** — the Bezier control points (ADR-046 infrastructure,
  reused) that map ecological ratio to `demotion_threshold` and
  `promotion_min_degree`. Rendered as an editable curve, not four numeric fields.
- **Effective-threshold preview** — given the current ratio, the thresholds the
  next cycle will actually use, so operators see cascading effects before saving.

Data sources: `GET /ontology/annealing/ecology`, `GET`/`PUT` on the ecological
pressure profile within `annealing_options`.

#### Integrity Tab — structural guard (#241)

Surfaces the graph integrity worker.

- **Violations table** — structural edge names (`SCOPED_BY`, `APPEARS`,
  `EVIDENCED_BY`, `FROM_SOURCE`) found connecting wrong node types, and
  structural names appearing as VocabType nodes (ADR-204 node-type pollution).
- **Run check** — trigger detection on demand (detection is safe; available
  before healing ships).
- **Healing log** — replacements made (illegal structural edge → `SIMILAR_TO`
  at low confidence), VocabType nodes removed, each logged as a warning per the
  #241 design.

Data sources: the new `POST /ontology/integrity/check` and
`GET /ontology/integrity/report` (see §4).

### 3. CLI parity additions

The CLI already carries the manual and review controls. It is **missing** the
automation-policy and integrity controls this ADR introduces. To keep the two
surfaces at parity (a project norm — every web control has a CLI equivalent),
add:

| New CLI command | Purpose | Backing |
|-----------------|---------|---------|
| `kg ontology automation [--level hitl\|aitl\|autonomous]` | Get/set `automation_level` and AITL/autonomous thresholds | #250, #251 |
| `kg ontology ecology` | Show ecological ratio and effective thresholds | #249 |
| `kg ontology integrity [--check] [--heal]` | Run structural-edge detection (and, once available, healing) | #241 |

The existing `kg ontology anneal`, `proposals`, `proposal`, `scores`,
`lifecycle`, `reassign`, `dissolve`, `candidates`, `affinity`, `edges` commands
are unchanged.

### 4. New API endpoints

ADR-200 already exposes ~26 ontology endpoints (list, info, lifecycle, scores,
candidates, affinity, edges, proposals, proposals review, annealing-cycle,
reassign, dissolve). The lifecycle surface needs a small number of additions:

| Endpoint | Purpose |
|----------|---------|
| `GET /ontology/annealing/status` | Automation level, last/next cycle, recent-cycle summary — powers the Dashboard. |
| `GET` / `PUT /ontology/annealing/config` | Read/write `annealing_options` (automation level, thresholds, safety bounds, cadence). |
| `GET /ontology/annealing/ecology` | Ecological ratio, target band, Bezier pressure profile, effective thresholds. |
| `GET /ontology/proposals/{id}/routing-plan` | Per-source affinity routing plan for a demotion proposal (#252). |
| `POST /ontology/integrity/check` | Run structural-edge detection (#241). |
| `GET /ontology/integrity/report` | Latest detections and healing log (#241). |

### 5. State management

A new Zustand store, `ontologyLifecycleStore`, parallel to `vocabularyStore`:

```typescript
interface OntologyLifecycleStore {
  // Data
  status: AnnealingStatus | null;
  proposals: AnnealingProposal[];
  config: AnnealingConfig | null;
  ecology: EcologySnapshot | null;
  integrityReport: IntegrityReport | null;

  // View state
  currentTab: 'dashboard' | 'proposals' | 'automation' | 'ecology' | 'integrity';
  proposalFilter: ProposalFilter;

  // Actions
  loadStatus(): Promise<void>;
  loadProposals(filter?: ProposalFilter): Promise<void>;
  reviewProposal(id: string, decision: 'approve' | 'reject', notes?: string): Promise<void>;
  loadConfig(): Promise<void>;
  updateConfig(patch: Partial<AnnealingConfig>): Promise<void>;
  loadEcology(): Promise<void>;
  runIntegrityCheck(): Promise<void>;
}
```

### 6. Permissions

The interface respects the existing three-tier model (ADR-028 RBAC, ADR-082
grants):

| Action | Minimum capability |
|--------|-------------------|
| View any lifecycle tab | `ontologies:read` |
| Approve / reject a proposal | `ontologies:write` |
| Change automation level, thresholds, ecological profile | `ontologies:write` (admin-class) |
| Run integrity check | `ontologies:write` |
| Trigger integrity healing | `ontologies:admin` |

`authStore.hasPermission()` gates UI affordances — controls a user cannot use
are disabled, not shown-then-rejected. Changing the automation level is a
high-consequence action (it governs unattended graph mutation); the Automation
tab confirms the change explicitly.

### 7. Relationship to ADR-700 (Ontology Explorer)

ADR-700 and this ADR both touch ontologies and both expose state and actions.
The boundary:

- **ADR-700 Ontology Explorer** — browse and *curate* ontologies as
  **collections**: the landscape (treemap / bubble pack), per-ontology detail
  (documents, concepts, internal subgraph), cross-ontology bridges, and CRUD
  (create / rename / delete). It answers *"what is in my graph and how do the
  domains relate?"*
- **ADR-703 Ontology Lifecycle Administration** — *operate* the annealing
  **process**: the proposals queue, automation policy, ecological pressure,
  integrity. It answers *"what is the autonomous loop doing, and is it safe?"*

The explorer is a knowledge-navigation surface under `/explore`; the lifecycle
interface is an operational surface under `/admin`. They cross-link — an
ontology row in either surface deep-links to the other — but neither owns the
other's concerns. Lifecycle *state* read-outs (e.g. `lifecycle_state`) appear in
both because both legitimately display them; lifecycle *transitions driven by
annealing* belong solely to ADR-703.

## Consequences

### Positive

- An autonomous process that mutates the graph unattended becomes observable —
  operators can finally see what the annealing loop is doing.
- The five backend issues stop being five disconnected enhancements: each becomes
  a tab or panel in one coherent operator experience, with a shared mental model.
- Graduated automation (HITL → AITL → autonomous) becomes a deliberate operator
  choice with visible consequences, instead of a default buried in a migration.
- CLI and web stay at parity; the automation-policy gap in the CLI is closed.
- Reuses established patterns wholesale — ADR-701's Admin-entry structure,
  ADR-046's Bezier curve infrastructure, ADR-028/082 permission gating.

### Negative

- Adds six API endpoints and a new Zustand store — more surface to maintain.
- The interface is only as useful as the backend issues are complete; the
  Automation and Ecology tabs are thin until #250/#251 and #249 land.
- Five tabs make this a moderately complex admin surface, comparable to ADR-701.
- The Ecology tab's Bezier editor is non-trivial UI work for a feature (#249)
  that is itself still deferred.

### Neutral

- This ADR governs *surfacing and operating* the annealing lifecycle; it does
  not re-decide the annealing architecture, which ADR-200 Phase 4 already owns.
- The five backend issues remain ADR-200 Phase 4 implementation tasks. A
  tracking epic linking them is advisable but is a project-management artifact,
  not an architectural one.
- The interface degrades gracefully: each tab renders against whatever backend
  exists, so it can ship incrementally as the issues land.

## Alternatives Considered

### A. Add a lifecycle view to the ADR-700 Ontology Explorer

Make annealing a fourth view inside the Ontology Explorer, alongside Overview,
Detail, and Bridge.

**Rejected because:** it conflates two mental models. The explorer is a
knowledge-navigation surface — "what is in my graph." Lifecycle administration is
an operations surface — "is the autonomous process safe." ADR-701 set the
precedent by giving the vocabulary subsystem its own Admin entry rather than
folding it into an explorer; the annealing subsystem is the direct sibling and
warrants the same separation. Operators reach for `/admin`, not `/explore`, when
they want to govern a background worker.

### B. Add an "Annealing" tab to the existing System admin tab

Put the controls inside the current `/admin` System tab.

**Rejected because:** the System tab is already ~884 lines covering AI
extraction, API keys, and embedding profiles (per ADR-701's own analysis). The
annealing lifecycle — five intent-distinct tabs, a Bezier editor, a proposals
workbench — is far too deep to be a section inside another tab. ADR-701 rejected
the identical option for the same reason.

### C. Leave it CLI-only

Extend the CLI to cover automation policy and integrity, and ship no web surface.

**Rejected because:** it does not address the core problem. The annealing loop
is autonomous-by-default *now*; non-CLI operators have zero visibility into a
process restructuring their graph. Visibility for a running autonomous system is
not a convenience — it is a safety requirement. The CLI additions in §3 are
necessary but not sufficient.

### D. One combined "Phase 4b" backend ADR plus the issues

Write a db-domain ADR consolidating the five issues' backend work.

**Rejected because:** ADR-200 Phase 4 already decides that architecture — the
graduated automation table, the ecological ratio, Section 8 demotion routing,
Design Principle 6. A new backend ADR would restate existing decisions, which
this project's discipline explicitly discourages. The five issues are
implementation tasks under decisions that already exist. The only *new*
architectural decision is the administration surface — and an interface decision
belongs in the `ui` domain, as a sibling of ADR-700 and ADR-701.

## Implementation Notes

**MVP (shipped):** The first increment lands as a single **"Ontology" tab inside
the existing `AdminDashboard`** (alongside Account / Users / Roles / System) —
not yet the dedicated `/admin/ontology-lifecycle` route. It surfaces loop
health, the read-only durable configuration, and the proposals queue with
approve/reject controls, backed by one new endpoint, `GET
/ontology/annealing/status`. This delivers the insight surface against today's
backend with zero routing changes. The interface graduates to its own route and
the full five-tab structure (§2) as the remaining tabs accrete — the §2 layout
is the target state, the tab is increment one.

The interface ships incrementally; each tab renders against whatever backend is
present. The recommended order follows the backend dependency graph:

1. **#252 (per-source affinity routing)** — lowest-risk backend fix; improves
   every demotion regardless of automation level. Surfaces in the Proposals tab
   routing-plan panel.
2. **Dashboard + Proposals tabs** — buildable today against existing endpoints
   (`GET /ontology/`, `GET /ontology/proposals`). Delivers visibility into the
   already-running autonomous loop first — the most urgent gap.
3. **#241 (integrity worker)** — detection-only first (safe, no graph
   mutation), surfaced in the Integrity tab; healing follows once autonomous
   execution is hardened. Worker and UI alerts panel ship together.
4. **#249 (Bezier ecological feedback)** — backend feedback loop, then the
   Ecology tab curve editor.
5. **#250 (AITL)** then **#251 (autonomous safety bounds)** — the Automation
   tab's controls become meaningful as these land, in dependency order.
6. **CLI parity commands** (§3) land alongside their corresponding backend
   issue, not as a separate pass.

The integrity worker (#241) is treated here rather than in ADR-200 because its
operator-facing half — detection reporting and the healing log — is part of this
interface; ADR-200 Design Principle 6 already establishes the edge-agnostic
principle the worker enforces.

## Related ADRs

- **ADR-200** — Annealing Ontologies (the lifecycle this interface operates;
  Phase 4 owns the backend architecture for all five issues)
- **ADR-700** — Ontology Explorer (sibling surface; see §7 for the boundary)
- **ADR-701** — Vocabulary Administration Interface (the pattern this ADR
  follows: a dedicated Admin entry for a self-regulating subsystem)
- **ADR-046** — Bezier curve aggressiveness profiles (reused for #249 ecological
  pressure)
- **ADR-203** — Graph Epoch Event Log (annealing cycle history for the Dashboard)
- **ADR-204** — Node Type representation (structural-name VocabType pollution
  that #241 detects)
- **ADR-028** — Dynamic RBAC (permission model for lifecycle actions)
- **ADR-082** — User scoping & grants (resource-level ontology ownership)
