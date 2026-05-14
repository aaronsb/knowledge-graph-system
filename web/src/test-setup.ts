/**
 * Vitest setup — runs once before any test module is imported.
 *
 * Why: vitest's `environment: 'jsdom'` provides a window with localStorage,
 * but Zustand's `persist` middleware captures `localStorage` as the storage
 * adapter at *store creation time*. When the store module is imported
 * before jsdom's globals are wired onto `globalThis`, `localStorage` reads
 * as `undefined` and persist quietly captures `undefined` — every later
 * `setItem` then throws "Cannot read properties of undefined" inside
 * Zustand. Module import order varies enough across environments
 * (host vs. dev container) that the race is real, not theoretical.
 *
 * Fix: install an in-memory shim *before* any test module loads (this file
 * is registered as a setupFile, which vitest runs first). If jsdom did
 * provide `localStorage` we'd skip the shim.
 */

if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>();
  // Storage is a structural type; the shim only needs to satisfy the
  // surface Zustand persist actually touches (getItem / setItem / removeItem).
  globalThis.localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => {
      store.clear();
    },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
}
