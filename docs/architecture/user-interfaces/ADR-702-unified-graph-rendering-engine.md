---
status: Proposed
date: 2026-04-20
updated: 2026-04-20
deciders:
  - aaronsb
  - claude
related:
  - ADR-034
  - ADR-035
  - ADR-078
  - ADR-085
---

# ADR-702: Unified Graph Rendering Engine

## Overview

Replace the three independent graph-rendering stacks in the web app with a single
React Three Fiber (r3f) engine that covers both 2D and 3D projection, both
sprite and polygon node modes, and both CPU and GPU physics, against the same
data shape. One engine, one physics implementation, one widget integration
surface. A force-graph explorer becomes a single plugin with a projection
toggle rather than two plugins with duplicated concerns.

The architectural distinctiveness: **we commit to r3f + instanced GPU rendering
+ GPU-accelerated force simulation as the one path forward for graph
visualization**, and stop shipping two parallel stacks (d3.js for 2D,
`react-force-graph-3d` for 3D). Edges stay line/curve geometry in both
projections — no 3D tubes — with quadratic-bezier support in the line shader
for curved multi-edges as a first-class presentation property from day one.

## Context

### Three rendering stacks today

The web app currently ships three independent paths for rendering graph data:

| Surface | Stack | Physics | Rendering | LOC |
|---|---|---|---|---|
| `ForceGraph2D` | `d3.js` + Canvas | `d3-force` (CPU) | d3 canvas draw commands | ~1840 |
| `ForceGraph3D` | `react-force-graph-3d` wrapper | `d3-force-3d` (CPU) | three.js via wrapper callbacks (`nodeThreeObject`, `linkThreeObject`), `SpriteText`, `Line2` | ~2052 |
| `EmbeddingScatter3D` | raw three.js | static coordinates (no sim) | `Float32Array` position/color buffers on `Points` | ~500 |

These share zero rendering code. Widgets (`NodeInfoBox`, `EdgeInfoBox`,
`ContextMenu`, `StatsPanel`, `Legend`, `PanelStack`) are reused because they
are DOM-level, but every scene, physics implementation, label strategy, and
interaction wiring is reimplemented per surface. Each is ~2000 lines of
integration glue around a different abstraction.

### Performance ceiling

`ForceGraph3D` begins to drop frames at a few hundred nodes. Three compounding
causes, all addressable:

1. **Per-node three.js object.** `nodeThreeObject` creates a `Group + Mesh`
   per node → O(N) draw calls. Instanced rendering → O(1) draw calls.
2. **Per-edge `Line2` geometry.** Each edge is its own geometry and material.
   Indexed `lineSegments` on a shared buffer → O(1) draw calls.
3. **CPU O(N²) physics** on the main thread. `GPUComputationRenderer`
   parallelizes the same math across fragments.

The atlassian-graph reference implementation (same r3f + instancing + GPU
physics stack this ADR adopts) renders 10k+ instanced polygons with 60+ FPS
force simulation on mid-range hardware, with graphs of 25k types / 65k edges
loaded in memory. That's a ~50× performance differential over our current
3D path — well within the range of published comparisons between instanced
and non-instanced WebGL rendering.

### Duplicated axes, rediscovered per surface

Every surface has to rediscover the same decisions:

- Node color palette and theme integration (`categoryColors.ts` is shared, but
  the *application* is per-surface)
- Selection / hover state and signal wiring to `NodeInfoBox` / `EdgeInfoBox`
- Edge filtering (`useGraphStore.filters.visibleEdgeCategories`)
- Touchpoint highlighting for block-query-builder results
- Camera controls, zoom, pan
- Edge label rendering strategy
- Drag / pin interactions

A unified engine collapses these seven surfaces into one.

### The atlassian-graph reference

[`aaronsb/atlassian-graph`](https://github.com/aaronsb/atlassian-graph)
demonstrates the target architecture on a comparable graph shape
(`{name, category, degree}` nodes, `{from, to, label}` edges). The pattern
this ADR ratifies:

- **r3f Canvas as the only surface** — no wrapper library between the app and
  three.js
- **`instancedMesh` nodes** — one draw call for N nodes, per-instance
  matrix + color
- **Indexed `lineSegments` edges** — one draw call for M edges, per-vertex
  color
- **Shared `Float32Array` position buffer** — physics and renderer read/write
  the same memory, no marshaling
- **GPU physics** via `GPUComputationRenderer` (WebGL2 + float render targets)
  with CPU fallback exposing an identical hook API
- **Demand-mode render loop** — `invalidate()` only while the simulation is
  active (`alpha > alphaMin`); idle frames cost nothing
- **Screen-space UI** via `<Html>` overlays — selection caret, hover labels,
  any constant-pixel-size indicators that shouldn't scale with camera distance

### Why this is a single architectural decision, not a refactor

An ADR is warranted because we are committing to a *direction*:

1. All graph visualization in the web app will route through one engine
2. GPU rendering (instanced) and GPU physics (fragment-shader sim) are
   non-negotiable — they are the property that makes 10k-node real-time
   viable
3. 2D and 3D projections are the *same engine*, not the same *styling* — a
   camera mode and a dimensionality mode on the force sim, not separate
   rendering paths
4. Existing per-surface rendering code (d3 2D, react-force-graph-3d wrapper,
   raw three.js scatter) is sunset in favor of the unified engine

This is a one-way decision with downstream implications for plugin authors,
performance expectations, and the scope of future visualization ADRs. Hence
a dedicated ADR rather than a subsection of ADR-034.

---

## Decision

Adopt a **single React Three Fiber rendering engine** for all graph
visualization surfaces in the web app. The engine is parameterized along
three orthogonal internal axes:

| Axis | Values | Default by context |
|---|---|---|
| **Projection** | `2D` (orthographic camera, z-locked sim) / `3D` (perspective camera, full 3D sim) | 2D for dense structural views, 3D for exploratory topology |
| **Node mode** | `sprite` (billboarded textured quad, instanced) / `poly` (instanced icosahedron or similar mesh) | 2D → sprite; 3D → poly |
| **Physics backend** | `CPU` (JavaScript force loop) / `GPU` (`GPUComputationRenderer` fragment-shader sim) | GPU where WebGL2 + `EXT_color_buffer_float` are available; CPU fallback otherwise |

Edges are always **line or curve geometry** in both projections. Straight
edges render as indexed `lineSegments`. Parallel edges between the same node
pair render as quadratic bezier curves via vertex-shader curve tessellation
— implemented from phase 1 as a first-class presentation property, not
deferred.

The public API of the engine is a scene component that accepts the existing
`ExplorerPlugin` `ExplorerProps` shape from ADR-034, emits the existing
selection/hover signal contract, and is wrapped by plugin components that
consume the engine and add surface-specific chrome (settings panel, legend,
node info box, context menu).

### Engine responsibilities

The engine owns:

- Positions buffer (`Float32Array` of length `3N`, always — z is zero in 2D mode)
- Velocities buffer (CPU path) or velocity texture (GPU path)
- Edge index array (`Uint32Array` of length `2M`)
- Force simulation (CPU or GPU, same parameter object)
- Instanced node rendering (polygon or billboarded sprite)
- Edge rendering (straight or bezier, via line shader) with optional
  edge-type coloring (see Plugin surface)
- Arrow-glyph rendering on directed edges, as an instanced-triangle mesh
  anchored to the target end of each edge (togglable per plugin)
- Camera (orthographic or perspective)
- Pointer picking via `instanceId` (uniform across node modes)
- Hidden mask (per-instance visibility, respected by both sim and renderer)
- Selection and hover state emission

The engine does **not** own:

- Data shaping (plugins transform `RawGraphData` → engine-compatible buffers)
- Settings UI (plugins render their own panels)
- Context menus, info boxes, legends (these are DOM components wired via the
  signal contract)
- Theme palette (plugins pass a category-indexed color LUT)
- Category semantics (ontology, edge types, relationship labels are
  plugin-level concerns that show up as string metadata on node / edge records)

### Picking strategy (uniform across node modes)

Both sprite and polygon node modes use `instancedMesh` as the underlying
primitive. Sprite mode is a billboarded textured quad on an instanced mesh
whose vertex shader rotates each instance's quad to face the camera.
This means `instanceId`-based pointer picking works identically for both
modes — r3f's `onPointerOver` / `onClick` handlers fire with a stable
`event.instanceId` regardless of projection or node visual. One selection
code path.

### Edge label strategy

Edge labels (relationship types) render as **distance-culled `<Html>`
overlays**. Only edges whose midpoint is within a configurable world-space
radius of the camera receive a label. Past that radius, the label is
unmounted. This preserves the glanceable relationship-type information
that kg's current 3D explorer shows inline, while bounding the DOM cost at
dense clusters. The same pattern is used for the selection caret marker
(`CaretMarker` in the reference implementation) and hover labels.

`<Html>` overlays render on top of scene depth (no z-sorting against other
3D content). This is acceptable for selection markers — they should be on
top. For edge labels in dense 3D clusters, labels may appear over nodes that
occlude them. This is a documented trade-off, not a bug.

### Scale target

The engine is designed for **10,000-node real-time interaction**. Past that
threshold, the O(N²) repulsion in `GPUComputationRenderer` becomes the
bottleneck. Scaling beyond 10k will require spatial hashing or a Barnes-Hut
approximation; this is explicitly future work, not part of this ADR.

### Plugin surface

Plugins implement the existing `ExplorerPlugin` interface from ADR-034 and
embed the engine component as their scene. The engine exposes:

```ts
interface EngineNode {
  id: string;                // stable key (e.g. kg concept_id)
  label: string;              // human-readable display text
  category: string;           // opaque string; resolved via palette
  degree: number;             // used for size scaling
  pinned?: boolean;
}

interface EngineEdge {
  from: string;
  to: string;
  type: string;               // relationship type; resolved via edgePalette
  weight?: number;
}

interface UnifiedGraphEngineProps {
  nodes: EngineNode[];
  edges: EngineEdge[];
  projection: '2D' | '3D';
  nodeMode: 'sprite' | 'poly';
  physicsBackend?: 'auto' | 'cpu' | 'gpu';
  physics?: Partial<PhysicsParams>;
  hiddenIds?: Set<string>;
  highlightedTypes?: Set<string>;
  highlightedEdges?: Set<string>;
  selectedId?: string | null;
  hoveredId?: string | null;
  palette: (category: string) => string;         // node category → hex
  edgePalette?: (edgeType: string) => string;    // edge type → hex (optional;
                                                 //   falls back to endpoint
                                                 //   gradient if absent)
  showArrows?: boolean;                          // render target-end arrow
                                                 //   glyphs; default true
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  onHide?: (id: string) => void;
  onContextMenu?: (id: string, event: PointerEvent) => void;
}
```

Plugins stay thin: they transform API data into engine-compatible shape,
hold settings state, render the settings panel and widget stack, and pass
through the engine.

---

## Consequences

### Positive

- **One engine, one physics, one rendering path.** Maintenance surface
  shrinks substantially — the three current surfaces total ~4,400 lines
  (`ForceGraph2D` 1840, `ForceGraph3D` 2052, `EmbeddingScatter3D` 529).
  Phase 1 alone takes ~2000 lines off the 3D surface (V2 replaces V1 and
  `react-force-graph-3d` is removed); phases 2 and 3 reduce the remaining
  two stacks. Expected total reduction ~2,000–3,000 lines by phase 3.
- **10k-node real-time interaction** becomes viable for the first time.
  Current 3D hits visible frame drops at a few hundred nodes.
- **2D and 3D share a camera and a sim**, so switching projection mode on
  the same dataset is a single prop change rather than a separate explorer.
- **Edge bezier curves as a first-class property** unlock better
  multigraph visualization from day one, in both 2D and 3D.
- **Uniform picking** across sprite and polygon node modes means selection
  and hover logic is written once and doesn't branch on visual style.
- **`Float32Array` positions buffer** is exportable — enables
  server-computed layouts, snapshot/restore of layouts across sessions,
  precomputed layouts for large graphs.
- **Engine primitives generalize** to the embedding scatter (phase 3) and
  potentially to the document explorer (phase 4), removing the last
  independent three.js stacks.

### Negative

- **WebGL2 + `EXT_color_buffer_float` dependency** for the GPU path. CPU
  fallback exists, but runs the same O(N²) physics on the main thread and
  will not hit the performance target. Older browsers and integrated
  graphics without float-render-target support fall back to CPU.
- **`<Html>` overlays do not z-sort** against scene depth. Edge labels in
  dense clusters can appear over occluding nodes. Documented, not fixable
  without a different label strategy.
- **Shader correctness burden.** `useGpuForceSim.js` encodes the physics
  in GLSL; bugs are harder to diagnose than equivalent JS and benefit from
  a golden-test harness that validates CPU and GPU paths produce
  equivalent layouts on canonical inputs.
- **Migration requires feature parity across ~2000 lines of existing 3D
  explorer code** before cutover. Some battle-tested details
  (edge-label rotation, texture caching, info-box positioning under drag)
  are re-implementation cost. Plugin coexistence (V1 + V2 in registry)
  during migration mitigates the risk of regression during the transition.
- **Loss of abstraction convenience.** `react-force-graph-3d` exposes a
  high-level API (`nodeThreeObject`, `linkLabel`, etc.); r3f + custom
  shaders is lower-level. The trade-off is control and performance for
  verbosity.

### Neutral

- **Existing widgets (`NodeInfoBox`, `EdgeInfoBox`, `ContextMenu`,
  `StatsPanel`, `Legend`, `PanelStack`)** are reused unchanged via the
  signal contract.
- **`ExplorerPlugin` interface from ADR-034** is unchanged. Plugins that
  adopt the engine conform to the same contract as those that don't,
  enabling per-surface incremental migration.
- **`categoryColors.ts` palette** continues to be the source of truth for
  category colors; the engine receives it as an opaque lookup function.
- **Sprite vs. polygon is an internal axis**, not a user-facing setting in
  the default settings panel. Plugins choose sensible defaults
  (2D → sprite, 3D → poly); advanced override can be added later if there
  is demand. This keeps the testable variant count to two (projection
  modes) rather than four (projection × node mode).

---

## Implementation Phases

### Phase 1 — ForceGraph3D V2 (3D projection, GPU physics, polygon nodes, bezier edges)

Register a new `ForceGraph3DV2` explorer plugin alongside the existing
`ForceGraph3D`. V2 uses the unified engine with `projection: '3D'`,
`nodeMode: 'poly'`, `physicsBackend: 'auto'`. Implements the full engine
including:

- Instanced polygon nodes
- Indexed straight edges + bezier curve support in line shader
- GPU force sim with CPU fallback
- Selection, hover, drag-to-reposition, context menu, hide
- Distance-culled `<Html>` edge labels
- Screen-space caret marker for selection
- Integration with existing `NodeInfoBox` / `EdgeInfoBox` / `ContextMenu` /
  `StatsPanel` / `Legend` / `PanelStack` via signal contract
- Theme integration (light/dark), edge-category filter, touchpoint
  highlighting

V1 stays registered. Users pick via the explorer dropdown. Once V2 reaches
full parity and soaks, V1 is removed and `react-force-graph-3d` dep is
dropped.

**Phase-1 merge gate:** before the phase-1 PR merges, a follow-up spike at
kg-scale (1,000+ concepts) must validate the performance target on
kg-shaped data at volume (per spike finding #5). The current spike (52
concepts) validated shape compatibility but not scaling.

### Phase 2 — Add 2D projection

Extend the engine with `projection: '2D'`:

- Orthographic camera
- z-locked force sim (z-component forces clamped to zero)
- Sprite node mode as the default
- Curved bezier multi-edges (the line shader already supports bezier from
  phase 1; 2D just enables it by default for parallel edges)

Ship as either a toggle on the force-graph explorer or as a distinct
`ForceGraph2DV2` plugin sharing the engine. Decision deferred to the
phase 2 start based on UX preference. Retire `ForceGraph2D` (d3) once V2
reaches parity, including whatever curved-edge and label behavior users
depend on today.

### Phase 3 — EmbeddingScatter3D migration

`EmbeddingScatter3D.tsx` already uses raw three.js with `Float32Array`
position and color buffers — closest to the engine pattern. Migrate it to
consume engine primitives (instanced points + optional convex hull overlay),
removing a third independent stack.

### Phase 4 (optional) — Document Explorer adopts engine traits

The document explorer (ADR-085) has a specific radial layout and its own
interaction model. It does not need full engine adoption. It may adopt
specific engine traits à la carte — the palette helper, the signal contract
for widgets, the `CaretMarker` pattern, the distance-culled `<Html>` label
approach — while keeping its custom scene composition. This phase is
optional and opportunistic; no commitment to complete migration.

---

## Alternatives Considered

### Keep d3 for 2D, only replace 3D

Preserves the 2D surface as-is. Avoids short-term migration of d3 canvas
code. **Rejected** because it locks in two rendering stacks indefinitely,
keeps widget integration duplicated, and forecloses the "2D projection
of the same dataset" use case. The unified-engine cost delta between
"replace 3D only" and "replace both" is small because the engine is the
hard part; adding a second camera mode is mechanical.

### Migrate to sigma.js or cytoscape.js

Both are mature graph visualization libraries. **Rejected** for three
reasons: (1) loss of shader control — kg's per-instance attribute needs
(epistemic status, polarity, evidence weight visually encoded) are awkward
in library APIs optimized for generic graphs; (2) additional dependency
weight that duplicates capabilities we already have in three.js; (3)
neither library exposes the GPU-physics-on-shared-buffer pattern that
drives our scaling target. The atlassian-graph reference demonstrates r3f
+ custom shaders reaches the target; adopting a library would trade that
headroom for abstraction we don't need.

### Full custom WebGL (no r3f)

Ultimate control, no framework overhead. **Rejected** because r3f's
demand-mode render loop, declarative scene composition, `<Html>` overlay
pattern, and pointer-event integration are exactly the parts we need,
and re-implementing them has negative ROI. The atlassian-graph reference
already proves r3f is enough.

### Keep `react-force-graph-3d` and just optimize per-node/per-edge callbacks

Attempt to push instancing into `nodeThreeObject` / `linkThreeObject`
callbacks. **Rejected** because `react-force-graph-3d` expects one
three.js object per node/edge; instancing requires inverting that
ownership. The lib also has no path to GPU physics — d3-force-3d runs
on the main thread by design. Forcing optimizations into someone else's
abstraction produces fragile integration; the atlassian-graph path
matches the grain of the tool (r3f + three.js directly).

---

## Open Questions

These are deferred to a later decision, either during implementation or a
follow-up ADR:

1. **Scaling beyond 10k nodes.** Spatial hashing, Barnes-Hut approximation,
   or hierarchical LOD. Picked when a graph genuinely crosses the
   threshold. Not gated by this ADR.
2. **Edge label behavior at extreme density.** Distance-culled `<Html>`
   is the committed default. If dense clusters produce unusable label
   overlap, we consider instanced glyph atlases (always-visible, one
   draw call, higher up-front cost) as a follow-up.
3. **User-facing toggle for sprite vs. polygon nodes in 3D.** Defaults
   stand. If a user asks for billboarded sprites in 3D (for extreme-
   density contexts, say), add as a settings-panel override. Not day-one.
4. **Curved-edge style in 2D multigraphs.** Bezier is committed; exact
   control-point offset heuristic (fan, concentric, alternating sides)
   is a visual-design decision for phase 2.
5. **Exposing `projection` as a runtime toggle vs. separate plugins.**
   Decided at phase 2 start. Trade-off is discoverability (two plugins
   in the dropdown) vs. composability (one plugin with a mode switch).

---

## Validation

Before finalizing this ADR, a validation spike is run: fork the
atlassian-graph `explorer/src/scene/` directory into a local spike
directory, export ~500 real concepts and relationships from kg as static
JSON matching the engine's node/edge shape, swap the schema loader, and
run. This produces empirical evidence that the mechanism carries kg-shaped
data (with kg-specific category names, edge multiplicities, and relationship
types) before the ADR's direction becomes load-bearing for implementation.

Spike findings are added to this section before the ADR moves from Draft
to Accepted.

### Spike results

The spike lives in `spike/unified-3d/` on this branch. It consists of:

- A cloned copy of `aaronsb/atlassian-graph` under `spike/unified-3d/reference/`
- An export script (`export-kg-data.sh`) that pulls concepts and relationships
  from a live kg postgres and writes them to `spike/unified-3d/data/kg-graph.json`
  in the shape the atlassian-graph UI expects (`{nodes, edges, meta}`)
- A drop-in spike server (`spike/unified-3d/spike-server.js`; copied into
  `spike/unified-3d/reference/` at reproduction time so it resolves
  `express` from `reference/node_modules`) that replaces atlassian-graph's
  GraphQL-schema-backed `/api/graph`, `/api/type/:name`, `/api/stats`,
  `/api/categories` endpoints with static reads from the kg export, leaving
  the rest of the reference implementation unchanged.

The reference UI's vite dev server and the spike server both run cleanly and
serve kg data through the atlassian-graph pipeline end-to-end. At the time of
the spike the local kg instance held 52 concepts and 76 relationships.

**Headless verification — passed.** Both servers respond 200 for all
endpoints the UI hits; data round-trips intact with 8 source-document
buckets mapped into the palette's 16 category slots, and 30 distinct
relationship types preserved on the edge records.

**Visual verification — passed (2026-04-20 live session).** Browser session
against `http://localhost:5173` confirmed:

- `GPU` capability badge lit — `GPUComputationRenderer` + WebGL2 + float
  render-target path selected on target hardware. GPU physics works.
- Force simulation settled into a coherent topology with visible high-degree
  hubs (e.g. "Session Narrative System", degree 19).
- Sprite screen-space selection caret (four corner brackets + center ring
  rendered via `<Html center>` at a world position, constant pixel size
  regardless of camera distance) rendered exactly as specified — confirming
  the `CaretMarker` pattern for phase 1.
- Per-instance category colors applied correctly across the 8 buckets;
  palette ramp selector (8-bit VGA, Rainbow, Viridis, Magma, Plasma, Inferno,
  Turbo, Hot, Metal, Cool) all functional.
- Sidebar correctly rendered selected-node detail with the three outgoing
  relationship types (`EVOLVES_INTO`, `INFLUENCES`, `FOCUSES_ON`) as
  collapsed detail rows — confirms edge-type metadata survives to the
  detail surface.

The spike stays in-tree as a reference implementation for phase-1 work.

#### Findings — shape compatibility (positive)

- kg's `Concept` nodes carry `{concept_id, label, ontology_category, degree}`,
  which maps cleanly onto the engine's `{id, displayLabel, category, degree}`
  shape. No lossy conversion.
- Relationships carry `{from, to, type}`, which matches the engine's edge
  record with no adapter layer. The reference pipeline accepted kg-shaped
  records verbatim.
- kg's category system is an open string (real value is frequently
  `"uncategorized"`). For the spike we synthesized category buckets from the
  source-document hash so the palette had visible variety. The engine must
  accept a `(category: string) => hex` palette function rather than a fixed
  enum — already in the plugin surface specified above.

#### Findings — design refinements (surfaced by the spike)

1. **Edges need their own category color, not just endpoint colors.** The
   reference implementation colors every edge with a gradient between its two
   endpoints' category colors. kg has 30 distinct relationship types
   (CONTAINS, IMPLIES, CAUSES, EVOLVES_INTO, CONTRASTS_WITH, …) and these
   carry graph-theoretic meaning that must be visible. **Engine revision:**
   edges take an optional `(edgeType: string) => hex` palette and the line
   shader blends between endpoint-category coloring and edge-type coloring
   based on a per-render flag. Default off (matches atlassian behavior);
   kg force-graph plugin turns it on.

2. **Directed-edge arrows.** kg relationships are semantically directed
   (`A CAUSES B` ≠ `B CAUSES A`). Atlassian edges are also directed but the
   reference implementation renders them as plain undirected lines. **Engine
   revision:** add a per-edge arrow glyph at the target-end of the line or
   curve, rendered via an instanced triangle mesh anchored to edge end-points
   in a geometry shader / vertex attribute. Gated by a plugin prop
   (`showArrows: boolean`, default true for kg).

3. **Node ID vs. display label separation.** kg concept IDs are long
   content-hashed strings (`sha256:720c8_chunk1_4bb27537`, 35+ chars) — great
   for keys, unusable for labels. Atlassian types use `name` as both.
   **Engine revision:** the engine's `EngineNode` shape is `{id, label,
   category, degree}` rather than reusing `name` for both. Already reflected
   in the plugin surface above.

4. **Palette pluggability is non-negotiable.** Atlassian-graph's `palette.jsx`
   hard-codes a 16-category enum with eight named ramps. kg's palette lives
   in `config/categoryColors.ts` and evolves independently. **Engine design:**
   palette is an opaque `(key: string) => hex` function passed in as a prop,
   and the engine performs no category enumeration. No regression.

5. **No change to scale expectations.** The spike's kg dataset is tiny (52
   nodes) — below any instancing or GPU-physics threshold. The scaling claim
   in this ADR rests on atlassian-graph's own demonstration at 500–10k
   instances, not on the spike. A future spike at kg-scale (1k+ concepts)
   should be run before phase 1 PR merges to confirm the performance target
   on kg-shaped data at volume.

6. **Hover label shows raw concept ID.** Live observation: hovering a node
   surfaced `sha256:e5779_chunk1_fab33936` instead of the human-readable
   `label` field. This is the exact symptom of finding #3 — the reference
   engine uses `name` as both key and display value. kg's engine must
   accept `label` separately and thread it through to the `<Html>` overlay
   text. A single-field addition, zero architectural impact.

#### Changes to the ADR driven by the spike

The four "engine revisions" above (edge category coloring, directed arrows,
id/label separation, palette pluggability) are reflected in the plugin
surface description and in the edge rendering discussion. None of them
invalidate the decision or phase sequence. They sharpen the engine API
contract and add a few fields to the per-instance attribute layout for
edges. Phase 1 implementation will need to cover all four from day one
because kg's existing 3D explorer already exhibits all four properties —
losing them in V2 would block cutover.

