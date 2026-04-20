# Spike: Unified 3D Rendering Engine — kg-shaped Validation

This spike is the empirical validation cited in
[ADR-702](../../docs/architecture/user-interfaces/ADR-702-unified-graph-rendering-engine.md).
It pipes real kg concept data through the `aaronsb/atlassian-graph`
reference rendering stack (r3f + instanced nodes + GPU physics) to prove
kg's data shape carries through the proposed engine without adapters.

## What's here

| File | Purpose |
|---|---|
| `export-kg-data.sh` | Pulls `Concept` nodes and relationships from the running kg postgres and writes `data/kg-graph.json` in the engine's expected `{nodes, edges, meta}` shape |
| `spike-server.js` | Minimal drop-in replacement for atlassian-graph's `explorer-server.js`. Serves `/api/graph`, `/api/type/:name`, `/api/stats`, `/api/categories` from the static kg export |
| `data/kg-graph.json` | **Not committed** — regenerate with `export-kg-data.sh` |
| `reference/` | **Not committed** — `git clone` the atlassian-graph repo per the reproduction steps |

## Reproduce

```bash
# From repo root:

# 1. Platform must be running so the export can query postgres
./operator.sh start

# 2. Clone the reference implementation
git clone --depth=1 https://github.com/aaronsb/atlassian-graph.git \
    spike/unified-3d/reference

# 3. Install reference deps (root for express; explorer for vite + r3f)
npm --prefix spike/unified-3d/reference install
npm --prefix spike/unified-3d/reference/explorer install

# 4. Export kg data
spike/unified-3d/export-kg-data.sh

# 5. Drop the spike server into the reference so it finds express
cp spike/unified-3d/spike-server.js spike/unified-3d/reference/spike-server.js

# 6. Run spike server (:4000) and vite dev (:5173)
node spike/unified-3d/reference/spike-server.js &
npm --prefix spike/unified-3d/reference/explorer run dev &

# 7. Open http://localhost:5173
```

## What the spike demonstrates

**Headless verification — passing.** All UI-facing endpoints respond 200
with valid JSON. kg's `{concept_id, label, ontology_category, degree}`
shape round-trips through the engine's `{id, label, category, degree}`
contract. kg's 30+ relationship types preserve intact on edge records.

**Visual verification — requires a browser session.** Expected per the
atlassian-graph reference: sphere-distributed instanced icosahedron nodes
colored by palette, indexed line-segment edges, force sim that settles
within seconds, r3f pointer picking for selection/hover/right-click-hide.

## Findings

Four design refinements surfaced — all incorporated into ADR-702:

1. **Edge coloring by edge-type**, not just endpoint category — kg
   relationship semantics (CAUSES, IMPLIES, CONTRASTS_WITH) carry meaning
   atlassian's gradient-by-endpoint-category loses
2. **Directed-edge arrow glyphs** — atlassian renders edges as plain lines;
   kg relationships are semantically directed
3. **Separate `id` and `label` fields** — kg uses long content-hashed
   IDs; atlassian conflates name and key
4. **Palette as opaque function** — atlassian hard-codes 16 categories;
   kg categories are an open string set

None invalidate the ADR's direction. They sharpen the plugin surface
contract and require phase-1 implementation to cover all four from day one.

## Lifecycle

Reference material for phase-1 implementation. Once ForceGraph3D V2 ships
and reaches parity, the spike can be removed. Until then it's the empirical
anchor the ADR cites.
