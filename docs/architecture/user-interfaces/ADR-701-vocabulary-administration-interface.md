---
status: Draft
date: 2026-01-29
deciders:
  - aaronsb
  - claude
related: [22, 25, 26, 46, 47, 53, 65, 77]
---

# ADR-701: Vocabulary Administration Interface

## Context

The vocabulary system is one of the platform's most sophisticated subsystems. It manages a dynamic, self-regulating set of relationship types that grow from LLM extraction, are categorized probabilistically via embeddings (ADR-047), scored by grounding contribution (ADR-046), classified by epistemic status (ADR-065), and consolidated through AI-assisted workflows (ADR-026). Tuning vocabulary parameters directly affects extraction quality, graph coherence, and system performance.

Today, all vocabulary management happens through the CLI (`kg vocab` — 20 subcommands across 8 modules) or raw API calls (~20 REST endpoints). The web workstation has no vocabulary administration UI. The only web-side vocabulary awareness is `vocabularyStore.ts` (explorer color coding) and `OntologyFilterBlock` (query builder filter).

This creates several problems:

1. **Accessibility barrier.** Non-CLI users cannot see vocabulary health, adjust parameters, or respond to zone alerts (WATCH/DANGER/EMERGENCY). Vocabulary tuning requires terminal comfort and memorizing command options.

2. **Curve blindness.** Aggressiveness profiles are defined by Bezier control points (x1, y1, x2, y2) — four floating point values that map to a curve shape. In the CLI, users set these numerically and see an ASCII approximation. This is a fundamentally visual concept trapped in a text interface.

3. **Consolidation friction.** The AITL (AI-in-the-Loop) consolidation workflow produces merge recommendations with confidence scores. In the CLI, reviewing these is sequential and stateless — you cannot compare candidates, defer decisions, or return to a partially-reviewed batch.

4. **Epistemic opacity.** Grounding measurements and epistemic classifications (WELL_GROUNDED through CONTRADICTED) are powerful data consistency signals, but the CLI presents them as flat tables. Trends, distributions, and anomalies are not visible.

5. **Configuration coupling.** The 12 vocabulary config parameters interact — changing `vocab_max` shifts the zone, which changes effective aggressiveness, which changes consolidation behavior. In the CLI these are adjusted one at a time with no preview of cascading effects.

Meanwhile, the existing Admin dashboard (`/admin`) has four tabs (Account, Users, Roles, System). The System tab is already 884 lines handling AI extraction, API keys, and embedding profiles. Vocabulary management is too deep to fit as another section there.

## Decision

### 1. Add "Vocabulary" as a Top-Level Admin Entry

Add a new sidebar entry under the Admin category:

```
Admin
  ├── Administration    (existing: Account, Users, Roles, System)
  └── Vocabulary        (new: dedicated vocabulary management)
```

Route: `/admin/vocabulary`

This gives vocabulary its own full-page layout with room for multiple tabs and rich visualizations, rather than competing for space inside the existing System tab. The pattern mirrors how explorers each get dedicated workspace — vocabulary management deserves equivalent treatment given its complexity.

### 2. Tab Structure

The vocabulary interface organizes into tabs by user intent:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Vocabulary                                                          │
├───────────┬──────────┬───────────┬────────────┬──────────┬──────────┤
│ Dashboard │  Types   │ Profiles  │   Config   │  Health  │  Merge   │
└───────────┴──────────┴───────────┴────────────┴──────────┴──────────┘
```

#### Dashboard Tab

At-a-glance vocabulary health. The landing view.

- **Zone indicator** — Large, colored status badge (GREEN / WATCH / DANGER / EMERGENCY) with vocabulary size and threshold context (`142 types — max 150, emergency 200`).
- **Summary cards** — Builtin vs custom count, active vs inactive, categories in use, last consolidation timestamp.
- **Category distribution** — Bar or donut chart showing type counts per category (causation, logical, evidential, etc.) with confidence coloring (high/medium/low).
- **Epistemic distribution** — Classification breakdown (WELL_GROUNDED, MIXED, WEAK, CONTRADICTED, INSUFFICIENT_DATA) as a stacked bar or pie.
- **Staleness indicator** — Graph change counter delta since last measurement, with a "Remeasure" button if stale.
- **Recent activity** — Last N vocabulary changes (merges, additions, category reassignments).

Data sources: `GET /vocabulary/status`, `GET /vocabulary/types`, `GET /vocabulary/epistemic-status`

#### Types Tab

The workhorse. Browse, search, filter, and inspect all relationship types.

- **Table view** — Sortable columns: type name, category, edge count, confidence, grounding (avg), epistemic status, active/builtin flags. Filterable by category, status, active/inactive.
- **Type detail panel** — Click a row to expand or open a side panel showing:
  - Category assignment with confidence score and similarity breakdown (bar chart of scores against all 11 categories, from `GET /vocabulary/category-scores/{type}`).
  - Similar types (top 5 by embedding similarity, from `GET /vocabulary/similar/{type}`).
  - Opposite types (least similar, from `GET /vocabulary/similar/{type}?reverse=true`).
  - QA analysis (miscategorization warnings, from `GET /vocabulary/analyze/{type}`).
  - Epistemic detail (grounding stats: avg, std, min, max, sample size).
  - Quick actions: merge into another type, toggle active/inactive, refresh category.
- **Search** — Natural language search across vocabulary (`GET /vocabulary/similar/{type}` with query mode).
- **Bulk actions** — Multi-select for batch category refresh or deactivation.

Data sources: `GET /vocabulary/types`, `GET /vocabulary/category-scores/{type}`, `GET /vocabulary/similar/{type}`, `GET /vocabulary/analyze/{type}`, `GET /vocabulary/epistemic-status/{type}`

#### Profiles Tab

Visual Bezier curve editor for aggressiveness profiles. This is where graphical controls replace numeric CLI input.

- **Profile list** — All profiles (8 builtin + custom) as cards. Each shows a small curve thumbnail, name, and whether it's the active profile. Click to select.
- **Curve editor** — The selected profile's Bezier curve rendered on a canvas:
  - X-axis: normalized vocabulary utilization (0% to 100% of range).
  - Y-axis: aggressiveness output (0.0 to 1.0, potentially overshooting to ~1.5 with aggressive profiles).
  - **Draggable control point handles** (P1 and P2) — Drag to reshape the curve. Values update in real-time. The start point (0,0) and end point (1,1) are fixed; the two control points define the curve character.
  - **Current position marker** — A dot on the curve showing where the vocabulary currently sits (based on current size vs min/max), with the effective aggressiveness value labeled.
  - **Zone bands** — Background colored bands showing comfort/watch/merge/emergency zones along the X-axis.
- **Profile metadata** — Name, description, created/updated timestamps, builtin flag.
- **Actions** — Create new profile (set name, description, drag points or enter values), duplicate existing, delete custom profiles. Activate a profile (updates `aggressiveness_profile` in config).

Data sources: `GET /admin/vocabulary/profiles`, `GET /admin/vocabulary/profiles/{name}`, `POST /admin/vocabulary/profiles`, `DELETE /admin/vocabulary/profiles/{name}`, `PUT /admin/vocabulary/config` (to activate)

#### Config Tab

All vocabulary configuration parameters with live preview of effects.

- **Threshold sliders** — `vocab_min`, `vocab_max`, `vocab_emergency` as range sliders on a shared number line. Dragging one shows how the zone boundaries shift. Current vocabulary size marked as a reference point.
- **Pruning mode** — Radio selector: Naive / HITL / AITL, with description of each mode's behavior.
- **Similarity thresholds** — `synonym_threshold_strong` and `synonym_threshold_moderate` as sliders with visual indicator of what "strong" vs "moderate" similarity means (example pairs at each threshold).
- **Other parameters** — `low_value_threshold`, `consolidation_similarity_threshold`, `auto_expand_enabled` toggle, `embedding_model` selector.
- **Live preview panel** — As parameters are adjusted, show computed effects: new zone classification, new aggressiveness score, estimated types that would qualify for pruning at new thresholds. This addresses the "configuration coupling" problem — users see cascading effects before saving.
- **Save / Reset** — Explicit save with diff summary of what changed. Reset to last saved state.

Data sources: `GET /admin/vocabulary/config`, `PUT /admin/vocabulary/config`, `GET /vocabulary/status` (for live preview)

#### Health Tab

Epistemic status and data consistency — the diagnostic view.

- **Measurement controls** — Run epistemic measurement with configurable sample size. Progress indicator during measurement. Last measurement timestamp and staleness delta.
- **Classification table** — All types with epistemic status, sortable and filterable. Color-coded: green (WELL_GROUNDED), yellow (MIXED), orange (WEAK), red (CONTRADICTED), gray (INSUFFICIENT_DATA), blue (HISTORICAL).
- **Distribution chart** — Stacked bar or sunburst showing classification counts. Trend over time if multiple measurements exist.
- **Anomaly highlights** — Flag types where epistemic status and category confidence disagree (e.g., high-confidence category assignment but CONTRADICTED grounding), or where status changed since last measurement. These are the "conflicts or problems with data consistency" that need attention.
- **Category flow diagram** — Chord diagram from `GET /vocabulary/category-flows` showing inter-category edge flow patterns. Reveals whether categories are well-separated or bleeding into each other.
- **Sync status** — Missing types detected in graph but not in vocabulary table. One-click sync with dry-run preview.

Data sources: `POST /vocabulary/epistemic-status/measure`, `GET /vocabulary/epistemic-status`, `GET /vocabulary/category-flows`, `POST /vocabulary/sync`

#### Merge Tab

AITL consolidation workflow and manual merge operations.

- **Consolidation launcher** — Target vocabulary size slider (30-200), auto-execute threshold slider (0.0-1.0), dry-run toggle. "Run Consolidation" button.
- **Recommendation review** — Results displayed as three groups:
  - **Auto-executed** (confidence ≥ threshold) — Already merged, shown for audit. Expandable to see reasoning.
  - **Needs review** (medium confidence) — Cards with source type, target type, similarity score, LLM reasoning. Approve/reject buttons per recommendation. Batch approve/reject.
  - **Rejected** (low confidence or directional inverse) — Shown for transparency.
- **Manual merge** — Select source type and target type from dropdowns (with similarity score preview). Reason text field (audit trail). Execute with confirmation showing affected edge count.
- **Merge history** — Log of past merges with who, when, why, and how many edges moved. Enables audit and potential rollback investigation.
- **Unused type pruning** — List of types with zero edges. Bulk deactivate with confirmation.

Data sources: `POST /vocabulary/consolidate`, `POST /vocabulary/merge`, `GET /vocabulary/types` (for unused detection)

### 3. Permission Model

Vocabulary administration uses existing RBAC resources:

| Tab | Read Permission | Write Permission |
|-----|-----------------|------------------|
| Dashboard | `vocabulary:read` | — |
| Types | `vocabulary:read` | `vocabulary:write` (toggle active, refresh categories) |
| Profiles | `vocabulary_config:read` | `vocabulary_config:write` (create/delete/activate profiles) |
| Config | `vocabulary_config:read` | `vocabulary_config:write` (update parameters) |
| Health | `vocabulary:read` | `vocabulary:write` (run measurements, sync) |
| Merge | `vocabulary:read` | `vocabulary:write` (execute merges, consolidation) |

The sidebar entry itself requires `vocabulary:read` to appear. Tabs without write permission show data read-only with action buttons hidden.

### 4. Component Architecture

```
web/src/components/admin/vocabulary/
├── VocabularyDashboard.tsx       # Route component, tab orchestration
├── DashboardTab.tsx              # Health overview
├── TypesTab.tsx                  # Type browser + detail panel
├── ProfilesTab.tsx               # Bezier curve editor
├── BezierCurveEditor.tsx         # Reusable curve canvas component
├── ConfigTab.tsx                 # Parameter form with live preview
├── HealthTab.tsx                 # Epistemic status + diagnostics
├── MergeTab.tsx                  # Consolidation workflow
├── components.tsx                # Shared vocabulary UI components
├── types.ts                     # TypeScript interfaces
└── index.ts                     # Exports
```

New store (or extend existing `vocabularyStore`):

```typescript
interface VocabularyAdminStore {
  // Status
  status: VocabStatus | null;
  loadStatus(): Promise<void>;

  // Types
  types: EdgeTypeInfo[];
  loadTypes(opts?: { inactive?: boolean }): Promise<void>;

  // Profiles
  profiles: AggressivenessProfile[];
  activeProfile: string;
  loadProfiles(): Promise<void>;

  // Config
  config: VocabularyConfig | null;
  loadConfig(): Promise<void>;
  updateConfig(updates: Partial<VocabularyConfig>): Promise<void>;

  // Epistemic
  epistemicStatuses: EpistemicStatusInfo[];
  loadEpistemicStatuses(): Promise<void>;
  runMeasurement(sampleSize: number): Promise<void>;
}
```

### 5. Sidebar Integration

In `AppLayout.tsx`, add a new `SidebarItem` under the Admin category:

```typescript
{
  icon: Waypoints,  // lucide-react — represents connected vocabulary
  label: 'Vocabulary',
  description: 'Edge types, profiles, health',
  path: '/admin/vocabulary',
  requiredPermission: { resource: 'vocabulary', action: 'read' },
}
```

Route in `App.tsx`:
```typescript
<Route path="/admin/vocabulary" element={<VocabularyDashboard />} />
```

## Backend Alignment Verification

Before committing to this interface design, the database schema, API endpoints, and worker implementations were audited against the UI's expectations. The vocabulary backend has been built incrementally across 8+ ADRs and ~10 migrations. This section documents what's confirmed working, what has gaps, and what the UI must account for.

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

- **Profiles**: `GET/POST/DELETE /admin/vocabulary/profiles` — Bezier control points accepted with validation (x: 0.0–1.0, y: -2.0–2.0). Profile creation, listing, deletion all work. Builtin profiles protected.
- **Config**: `PUT /admin/vocabulary/config` — Supports all 11 parameters as optional partial updates. Returns computed zone/aggressiveness after update (enables live preview).
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

All three workers are registered in `main.py` and integrated with the job queue system. The epistemic remeasurement runs on a cron schedule (`0 * * * *` — hourly) with hysteresis via the graph_metrics delta mechanism.

### Gap: Consolidation Review Is Stateless

The AITL consolidation endpoint (`POST /vocabulary/consolidate`) returns `needs_review` items in the HTTP response, but **does not persist them** for later retrieval. If the user navigates away from the Merge tab after running consolidation, deferred review items are lost.

The schema infrastructure exists — `kg_api.pruning_recommendations` has a `status` column (pending/approved/rejected/executed) with `reviewed_by`, `reviewer_notes`, and `expires_at` fields — but the consolidation code path does not write to this table.

**UI implication for Merge tab:** Phase 3 should either:
- (a) Hold consolidation results in component state and warn users that navigating away loses unreviewed items, or
- (b) Require a backend change to persist recommendations to `pruning_recommendations` so they survive page navigation. This table is already designed for exactly this purpose — it just needs wiring.

Option (b) is the correct long-term fix and should be addressed during Phase 3 implementation. The table schema requires no changes.

### Gap: Prune and Deprecate Execution Are Stubbed

`VocabularyManager._execute_prune()` and `._execute_deprecate()` (vocabulary_manager.py lines ~1091-1150) contain TODO placeholders. Merge execution works fully, but hard-delete pruning and formal deprecation workflows are incomplete.

**UI implication for Merge tab:** The "Unused type pruning" section should use **deactivation** (set `is_active = false`) rather than deletion. This works today via the existing type update pathway. The UI should not expose a "permanently delete" action until the backend prune execution is implemented.

### No Backend Changes Required for MVP

Phases 1 and 2 (Dashboard, Types, Profiles, Config) require **zero backend changes**. All API endpoints, schema, and workers are in place. The two gaps above affect only Phase 3 (Merge tab), and both have viable workarounds until backend work catches up.

## Consequences

### Positive

- Vocabulary tuning becomes accessible to non-CLI users — the primary audience for the web workstation
- Bezier curve editing transforms from "set four numbers" to "drag a curve shape" — a natural fit for the inherently visual aggressiveness model
- Consolidation review becomes a batch workflow with comparison and deferral, instead of sequential CLI prompts
- Live preview in Config eliminates trial-and-error parameter adjustment
- Epistemic health gets a proper diagnostic view, making data consistency problems discoverable rather than hidden
- Category flow visualization (already has API support) gets a permanent home
- Backend verification confirms Phases 1-2 require zero backend changes — all API endpoints, schema, and workers are already in place

### Negative

- Adds a second admin route (`/admin/vocabulary`), breaking the single-dashboard pattern. This is intentional — the alternative (cramming into System tab) was evaluated and rejected.
- The Bezier curve editor (`BezierCurveEditor.tsx`) is a non-trivial interactive canvas component — likely the most complex single UI element in the admin section.
- The Merge tab's AITL workflow involves async job execution and polling, which adds state management complexity. Additionally, consolidation review is currently stateless on the backend — the `pruning_recommendations` table exists but isn't wired to the consolidation endpoint, so Phase 3 needs either client-side state management with navigation warnings or a backend fix to persist recommendations.
- Unused type pruning is limited to deactivation (set `is_active = false`) because backend prune/deprecate execution is stubbed. Hard deletion requires backend completion before the UI can expose it.
- Six tabs is a lot. If user testing shows overwhelm, Dashboard + Types + Profiles could be the initial set, with Health and Merge as progressive disclosure.

### Neutral

- Requires extending `VisualizationType` or admin routing, but not the explorer plugin system (this is admin, not an explorer)
- The `vocabularyStore` may need extension or a parallel `vocabularyAdminStore` to hold admin-specific state (config, profiles, epistemic data) separately from explorer state (type metadata for coloring)
- New RBAC resources (`vocabulary:read/write`, `vocabulary_config:read/write`) need registration in the resource registry if not already present
- The category flow chord diagram component could be shared with the Edge Explorer (ADR-077) if both use the same `GET /vocabulary/category-flows` endpoint

## Alternatives Considered

### A. Add a Vocabulary Section to the System Tab

Put vocabulary management as another collapsible `<Section>` inside the existing System tab.

**Rejected because:** The System tab is already 884 lines with three major sections (AI extraction, API keys, embedding profiles). Vocabulary management has 6 distinct concern areas and needs interactive visualizations (curve editor, chord diagram, consolidation workflow). Cramming this in would make System tab unmaintainable and the UI cramped. The depth of vocabulary management warrants dedicated space.

### B. Build as an Explorer Plugin

Register vocabulary management as an explorer in the workstation, alongside Force Graph, Document Explorer, etc.

**Rejected because:** Vocabulary management is an administrative function, not a data exploration function. Explorers visualize graph data; vocabulary admin configures how the graph is built. Placing it in the explorer registry would confuse the mental model (explorers are for understanding data, admin is for tuning the system). The Edge Explorer (ADR-077) already handles vocabulary *visualization* — this ADR handles vocabulary *administration*.

### C. Standalone Page Outside Admin

Create `/vocabulary-admin` as a top-level route, not nested under Admin.

**Rejected because:** Vocabulary configuration is an administrative concern. Users expect admin functions grouped together. A standalone route fragments the admin experience and complicates sidebar organization.

### D. Fewer Tabs with Denser Layout

Combine Dashboard + Health into one tab, Types + Merge into another, Profiles + Config into a third. Three tabs total.

**Not rejected, but deferred.** This is a valid simplification if six tabs proves overwhelming. The tab structure proposed here maps one concern per tab, which is clearest for documentation and initial implementation. Consolidation can happen after user testing reveals actual navigation patterns.

## Implementation Notes

### Phase 1: Foundation + Dashboard + Types

- Create route, sidebar entry, tab skeleton
- Dashboard tab with zone status, summary cards, category/epistemic distribution charts
- Types tab with sortable/filterable table and detail panel
- Read-only — no write actions yet

### Phase 2: Profiles + Config

- Bezier curve editor component (canvas-based, draggable control points)
- Profile list, selection, create/delete
- Config form with threshold sliders and live zone preview

### Phase 3: Health + Merge

- Epistemic measurement controls and classification table
- Category flow chord diagram
- Sync detection and execution
- AITL consolidation launcher and recommendation review
- Manual merge workflow with audit trail

## Related ADRs

- **ADR-022** — Original 30-type taxonomy (the vocabulary this interface manages)
- **ADR-025** — Dynamic relationship vocabulary (capture and expansion model)
- **ADR-026** — Autonomous vocabulary curation (AITL consolidation workflow)
- **ADR-046** — Grounding-aware vocabulary management (scoring model)
- **ADR-047** — Probabilistic vocabulary categorization (category confidence system)
- **ADR-053** — Vocabulary embedding similarity (similar/opposite type detection)
- **ADR-065** — Epistemic status classification (health measurement model)
- **ADR-077** — Vocabulary explorers (visualization complement — explores data; this ADR administers configuration)
