---
pattern: ForceGraph2D|ForceGraph3D|OrbitControls|MapControls|drei|@react-three|explorer.*plugin|force.?graph|3d.?view|2d.?view|orthographic|perspective.*camera
files: web/src/explorers/
description: Force-graph explorer plugins (2D/3D) — R3F camera/controls choices and the d3 ForceGraph2D interaction reference
vocabulary: explorer force graph 2d 3d three r3f orbit map controls camera pan zoom rotate context menu interaction projection
scope: agent, subagent
---
# Force-Graph Explorers Way

Explorer plugins live in `web/src/explorers/`. The force-graph explorer
(`web/src/explorers/ForceGraph/`) is built on the unified R3F engine
(ADR-702); projection ('2D' / '3D') is a user-facing setting on the
plugin, and the engine dispatches camera, drag plane, and sim axis
count from it.

## Interaction Model (carried over from the retired d3 ForceGraph2D)

The d3-based `ForceGraph2D` plugin (retired in Phase C) established the
2D interaction defaults this codebase keeps. The unified engine's 2D
projection matches them, and any future 2D-style explorer should too:

| Input | Action |
|-------|--------|
| Left-click drag on canvas | Pan view |
| Right-click on node | Context menu |
| Right-click on background | Background context menu |
| Scroll wheel | Zoom |

Left-pan, right-context is the reference. If you find yourself with a
different default, that's the bug, not a feature.

## R3F Top-Down 2D: OrbitControls, Not MapControls

When using R3F (`@react-three/fiber` + `drei`) for a top-down 2D
projection — orthographic camera at `+Z` looking down `-Z` over a
`z=0` layout plane — pick `<OrbitControls enableRotate={false}>`,
not `<MapControls>`.

MapControls' default `screenSpacePanning=false` assumes a Y-up
ground-plane model. Vertical pan ends up along world-Z (perpendicular
to the screen) and the view doesn't move. OrbitControls defaults
`screenSpacePanning=true` and pans along the camera's screen-aligned
up axis — what a top-down ortho camera actually wants.

To match the d3 interaction model on top:

```tsx
<OrbitControls
  makeDefault
  enableRotate={false}
  enableZoom={enableZoom}
  enablePan={enablePan}
  mouseButtons={{
    LEFT: THREE.MOUSE.PAN,
    MIDDLE: THREE.MOUSE.DOLLY,
    // RIGHT mapped to ROTATE but gated off via enableRotate=false —
    // leaves right-click un-consumed so the wrapper div's onContextMenu
    // can open the explorer's context menu.
    RIGHT: THREE.MOUSE.ROTATE,
  }}
/>
```

## Projection-Aware Labels in 2D

3D edge labels orient along the edge direction (readable from any
camera angle). In 2D the camera is locked so edge-aligned labels
become tilted or upside-down. When `projection === '2D'`, use a
screen-aligned basis (world X/Y/Z) for edge labels so text always
reads left-to-right.

Distance-culling labels in 2D also needs a tweak: the orthographic
camera is z-locked at a fixed offset from the layout plane, so `dz`
is constant >> any sensible `visibilityRadius`. Cull on XY-plane
distance only — `visibilityRadius` then means "world units from the
viewport centre".

## WebGL Feature Support: State It Empirically

Driver support for WebGL features varies (Mesa, ANGLE, Metal, …).
When commenting on features like `LineBasicMaterial.linewidth`, state
the empirical situation plus the spec — not the worst case:

> "Honoured by drivers that support it; the WebGL spec doesn't
> require widths > 1, so effect varies by platform."

Not:

> "Clamped to 1px on most drivers."

The first lets the next reader test on their platform and trust the
comment. The second overclaims and ages badly the moment someone runs
on a driver that does honour it.

## Reference

- ADR-702 (`docs/architecture/user-interfaces/ADR-702-unified-graph-rendering-engine.md`) — the unified-engine commitment
- ADR-034 — the ExplorerPlugin contract every explorer follows
- `web/src/explorers/ForceGraph/scene/` — engine primitives (Scene, Nodes, Edges, Arrows, NodeLabels, EdgeLabels, useSim, useForceSim, useGpuForceSim, useDragHandler)
