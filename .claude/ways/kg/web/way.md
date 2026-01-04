---
match: regex
pattern: web/src/|Zustand|React.*component|useStore
files: web/src/
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

```bash
cd web && npm run build  # Check for TypeScript errors
./operator.sh restart web
```

## API-First with localStorage Fallback

Stores save to API first, fall back to localStorage:
- Requires OAuth login for database persistence
- localStorage serves as cache and offline fallback
