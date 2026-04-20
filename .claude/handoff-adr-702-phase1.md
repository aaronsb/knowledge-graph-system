# ADR-702 Phase 1 — Session Handoff

Continuation notes for the next working session on the unified-rendering-engine
implementation. Pick up from here.

## Status snapshot

- **Branch**: `feat/unified-3d-renderer`, 25 commits ahead of `main`
- **Last commit**: `e05014ea` — edge-category fallback fix (V1/V2 parity)
- **ADR**: `docs/architecture/user-interfaces/ADR-702-unified-graph-rendering-engine.md`
  (merged to main, status Proposed)
- **V2 explorer route**: `/explore/3d-v2` (sidebar: "3D Force Graph (V2)")

## What's done (M1–M5)

All M1–M5 tasks complete. See commits 9bdfaa32 → e05014ea for the full
chain. Milestone coverage:

| Milestone | Scope | Key commits |
|---|---|---|
| M1 scaffold + scene | Plugin skeleton, r3f Canvas, InstancedMesh nodes + indexed-line edges, kg category palette | 9bdfaa32, c19e85fc |
| M2 physics | CPU sim (useForceSim) + GPU sim (useGpuForceSim via GPUComputationRenderer), module-scope useSim dispatcher with capability detection | c0b6d963, 23207aa6 |
| M3 rendering refinements | Bezier multi-edges with per-bundle perpendicular-plane rotation, instanced-cone arrow glyphs at target ends, edge-type palette prop | 6c947a44, later commits |
| M4 interaction | InstancedMesh pointer picking, CaretMarker + node hover label (screen-space overlays), distance-culled Html edge labels, drag-to-pin + right-click hide | dc38c42a and siblings |
| M5 widgets + panels | Shared ContextMenu via buildContextMenuItems, NodeInfoBox on select (follows node), Legend + StatsPanel + Reports button in PanelStack, theme-aware canvas from explorerTheme.canvas3D, edge-category filter from graphStore, V2-shape settings panel with live physics tuning | c165ca2d, a47eeec1, e00aa7e9, e4393d16, d15c3dc2, e05014ea |

## What remains (M6)

Three tasks. All are independent of M1–M5 code but build on it.

### #20 — Benchmark harness

Scope: measure rendering + sim frame time of V2 on fixtures at 100, 1k, 5k,
10k nodes, each with plausible edge density. Output: in-page results table
+ copyable CSV.

Where it lives: `web/src/explorers/ForceGraph3DV2/bench/` (new dir). Add a
route like `/bench/v2` or a button inside V2's settings panel.

What to measure per scale:

- Sim step time (walltime per useFrame pass)
- Renderer frame time (time from invalidate() to paint — can approximate
  with a pre-useFrame + post-useFrame performance.now() bracket, though
  GPU-path's per-frame readback adds noise)
- Observed FPS at steady state (sim settled)
- Observed FPS during interaction (simulate camera rotation or drag)
- Memory footprint (performance.memory.usedJSHeapSize snapshot if Chrome,
  else skip)

Implementation notes:

- Synthetic graph generator: N random nodes + M random edges, distributed
  into K synthetic categories so the edge palette has variety. A reusable
  helper under `bench/synthesizer.ts` so #21 can scale to real-kg shapes.
- Run each fixture for ~5 seconds with a warm-up phase (skip first 30
  frames). Sample frame times, compute min/avg/p50/p95/p99.
- Build the UI as a standalone page; a minimal `<BenchRun>` component that
  walks the fixture list, shows per-fixture progress, and a results table
  at the end.
- Export CSV via a "Copy CSV" button. Format: `scale,mean_frame_ms,p95_frame_ms,fps_steady,fps_interact,sim_step_ms,backend`.

### #21 — 1k-concept scale spike (ADR merge gate)

Scope: run the benchmark harness (or spiritual equivalent) against real
kg data at ≥1k concepts. This is the pre-merge gate cited in ADR-702
Phase 1 and finding #5 from the spike.

Two paths to the 1k dataset:

- **Ingest real content**: use the platform to ingest a larger corpus
  until the graph crosses 1k concepts, then query a subgraph.
- **Synthetic with kg shape**: extend `spike/unified-3d/export-kg-data.sh`
  to pull whatever the postgres has, pad it programmatically if needed,
  or generate synthetic concepts in the kg schema and ingest them.

Numbers to report in the phase-1 PR description:

- Target: **60 fps interactive at 1k nodes with GPU sim**. CPU fallback
  accepted at the 100–500 range.
- If target missed: either raise the scale ceiling language in the ADR
  or add Barnes-Hut / spatial-hashing work to M6 before cutover.

### #22 — Cutover

Scope: flip V2 from parallel-coexisting to default, remove V1, drop its
dependencies.

Mechanical steps:

1. In `web/src/App.tsx`, point `/explore/3d` to V2 (`explorerType="force-3d-v2"`).
   Or: swap V2's registry key to `'force-3d'` and delete the V1 registration.
2. Remove the sidebar's "3D Force Graph (V2)" item from `AppLayout.tsx`.
3. Delete `web/src/explorers/ForceGraph3D/` (the whole V1 3D plugin dir).
4. Drop `react-force-graph-3d` and `three-spritetext` from `web/package.json`;
   run `npm install` (both host AND inside the kg-web-dev container).
5. Remove V1 3D imports from `web/src/explorers/index.ts` and the
   `VisualizationType` enum (either keep `'force-3d-v2'` as the 3D ID,
   or rename it back to `'force-3d'` and delete `'force-3d-v2'`).
6. Update ExplorerView's settings-panel switch — remove the V2 special
   case once V1 is gone. Probably easiest: make `explorerPlugin.settingsPanel`
   the default, leave V1 2D using GraphSettingsPanel.
7. `tsc -b` (production build, stricter than dev) to catch any stale imports.
8. Update ADR-702 status from Proposed → Accepted and add the scale-spike
   results. Close the tracking issue(s) if any.

## Deferred / known gaps

Things V2 doesn't have yet, called out so they don't become surprises:

- **Touchpoint highlighting** — ADR-702 calls it out as a planned input,
  but V1 doesn't emit it either. Wait until the block-query-builder flow
  surfaces touchpoints through `ExplorerProps` before wiring V2.
- **Background right-click context menu** — V1 shows a background variant
  (travel / polarity between origin+destination). V2 only emits
  onContextMenu when a node is under the cursor. Add a handler on the
  Canvas element itself (not inside Scene) for empty-canvas right-clicks.
- **Camera travel** — V1 3D has `travelAlongPath` + ring markers for
  origin/destination. V2 skipped these (r3f camera-tween isn't wired).
  Follow-up task once the context-menu path-travel option is needed.
- **EdgeInfoBox on edge select** — V2 doesn't have edge pointer picking
  yet. V1 does. If users want per-edge detail panels, implement edge
  instance picking (each edge's indexed-line-segment range maps back to
  an edge record via a lookup table).
- **Reheat / Simmer / Freeze sim controls** — the sim hook exposes these
  via simHandleRef but no UI button surfaces them yet. Would go in the
  V2 settings panel or an on-canvas overlay next to the sim-backend badge.
- **Drag-pin persistence** — drag-to-pin currently auto-releases on
  pointer-up. A "keep pinned" toggle + "Unpin All" button (already in
  context menu) would let users shape layouts manually.

## Dev environment reminders

- **Web front end HMR works cleanly** — edits reload without container
  restart. Use `docker logs kg-web-dev` for compile/runtime errors.
- **Adding npm deps**: install in both host `web/` AND inside the
  `kg-web-dev` container, then restart the container so vite re-optimizes.
  See `~/.claude/projects/.../memory/feedback_web_npm_container_sync.md`
  for the exact commands.
- **Type check before each commit**: `npx tsc --noEmit` in `web/` —
  tsc catches V1/V2 shape mismatches that runtime would surface as
  "cannot read property 'X' of undefined".

## How to resume

1. Pull the branch: `git checkout feat/unified-3d-renderer`
2. Start the platform if not running: `./operator.sh start`
3. Open `/explore/3d-v2` in a browser, confirm V2 still renders
4. Pick up at task #20. First file to write:
   `web/src/explorers/ForceGraph3DV2/bench/synthesizer.ts`
5. Decide before writing the benchmark UI: standalone route
   (`/bench/v2`) vs button inside V2's settings panel. Standalone is
   easier to iterate on without re-rendering the main explorer.

## Pointers

- ADR: `docs/architecture/user-interfaces/ADR-702-unified-graph-rendering-engine.md`
- Spike (reference only, not a runnable part of V2): `spike/unified-3d/`
- V2 source: `web/src/explorers/ForceGraph3DV2/`
- V1 3D source (to be deleted in #22): `web/src/explorers/ForceGraph3D/`
- Shared widgets: `web/src/explorers/common/`
- Plugin contract: `web/src/types/explorer.ts` (ADR-034)
