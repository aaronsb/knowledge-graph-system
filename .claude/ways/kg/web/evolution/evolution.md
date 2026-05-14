---
pattern: unified.?engine|v1.?v2|v2.?v1|transitional|legacy.*route|redirect.*route|promot(e|ion).*canonical|cosmetic|polish|backwards.?compat|engine.*converge|retire.*explorer
files: web/src/explorers/|web/src/views/|web/src/components/layout/
description: Engineering judgement for web refactors — engine convergence over polish, scrub transitional V1/V2 framing post-promotion, skip redirects for never-public routes
vocabulary: evolution refactor unified engine convergence v1 v2 transitional canonical promote polish redirect deprecation
scope: agent, subagent
---
# Web Evolution Way

Notes for navigating web refactors — especially the unified force-graph
engine evolution (ADR-702) and similar transitional work where two
implementations coexist for a while before one wins.

## Engine Convergence Before Polish

When working toward a unified engine (e.g., one force-graph plugin
serving 2D + 3D + future projections), prefer architectural
unification over visual polish. Cosmetic items defer until the engine
has converged.

- Don't bikeshed colors, easing, or chrome while the API surface is
  still moving — that work will be rewritten when the engine settles.
- If a polish idea is worth keeping, file a GitHub issue and link it.
  Memory entries and design notes accumulate; issues close when work
  lands.
- "Does this belong in the eventual unified engine?" is the test for
  whether to port a feature now during transition. Yes → add once;
  both 2D and 3D get it for free. That's the architectural leverage
  ADR-702 is buying — take it.

## Drop Transitional Framing Post-Promotion

When a `V2` (or `-experimental`, `-next`, etc.) variant gets promoted
to canonical, scrub the historical framing in the same PR or the
follow-up:

- On-canvas labels like "ForceGraph3D V2" → drop the suffix.
- Comments like `// V1 has X / V2 has Y` → either delete or rewrite as
  unconditional behaviour.
- File/symbol names that carry the suffix (`*V2.tsx`, `V2SettingsPanel`)
  → rename when the V1 is removed.

Once promoted, the V1/V2 distinction is anachronistic. Readers
arriving fresh have no V1 to compare against, and the lingering
language slows them down.

## Skip Redirects for Never-Public Routes

Transitional routes that were never publicly stable — `/explore/3d-v2`,
`/foo-experimental`, anything with a development-only suffix — don't
need redirect shims when they're folded into the canonical route.
There are no bookmarks to honour. Dead redirect code is just dead code.

Add redirects only when the source URL was actually shipped to users
or referenced in external docs.

## When Two Plugins Share One Component

During the coexistence window of a unified-engine migration, two
explorer plugin entries can share the same component but differ in
`config` (id, name, icon) and `defaultSettings`. Use a small factory:

```ts
function createForceGraphPlugin(
  type: VisualizationType,
  name: string,
  description: string,
  icon: ComponentType<{ className?: string }>,
  projection: Projection,
): ExplorerPlugin<Data, Settings> {
  return {
    config: { id: type, type, name, description, icon, requiredDataShape: 'graph' },
    component: ForceGraph3D,
    settingsPanel: SettingsPanel,
    dataTransformer: transformForEngine,
    defaultSettings: { ...DEFAULT_SETTINGS, projection },
  };
}
```

This is the transitional shape — once the legacy variant retires, the
factory collapses to a single plugin with the projection toggle as the
user-facing affordance.

## Reference

- ADR-702 (`docs/architecture/user-interfaces/ADR-702-unified-graph-rendering-engine.md`)
- PR #363 — action-layer unification (style for atomic multi-commit
  refactor PRs)
- PR #365 — Phase A: V1-3D retirement
- PR #366 — Phase B: 2D projection + parity controls
