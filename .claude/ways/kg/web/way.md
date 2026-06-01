---
pattern: \bweb\b|frontend|Zustand|React.*component|Next\.js
files: web/src/
description: React frontend with Zustand state management, explorer plugins, and API-first persistence
vocabulary: web frontend react zustand component store view explorer vite typescript ui
scope: agent, subagent
---
# Web Way

## Structure

```
web/src/
├── components/
│   ├── shared/          # Reusable (IconRailPanel, SearchBar)
│   ├── polarity/        # Polarity explorer
│   ├── blocks/          # Block diagram editor
│   └── ...
├── store/               # Zustand stores
│   ├── graphStore.ts
│   ├── reportStore.ts
│   ├── artifactStore.ts
│   └── ...
├── api/
│   └── client.ts        # REST API client
├── views/               # Route views
└── explorers/           # Explorer plugins
```

## Zustand Patterns

```typescript
// Store with persist
export const useMyStore = create<MyStore>()(
  persist(
    (set, get) => ({
      // state and actions
    }),
    { name: 'storage-key' }
  )
);
```

## After Web Changes

`kg-web-dev` runs Vite with HMR — code changes hot-reload automatically.
No container restart needed in dev mode. See `kg/devmode/way.md`.

```bash
cd web && npx tsc --noEmit  # Check for TypeScript errors (run anytime)
cd web && npm test           # Run the vitest suite
```

Restart `kg-web-dev` only when changing build config (vite.config.ts,
package.json, tsconfig*.json) — those aren't watched by HMR.

## API-First with localStorage Fallback

Stores save to API first, fall back to localStorage:
- Requires OAuth login for database persistence
- localStorage serves as cache and offline fallback

## Control UI: Show State, Don't Imply It

<!-- epistemic: heuristic -->

An action-labeled button (e.g. "Freeze") is ambiguous about *current* state —
does "Freeze" mean it's frozen, or that clicking freezes it? For admin/control
toggles, render an explicit status indicator (an Active/Frozen pill) next to
the bare action verb, so the user reads the current state directly instead of
inferring it from the button label.
