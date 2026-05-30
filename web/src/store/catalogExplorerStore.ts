/**
 * Catalog Explorer Session Store (ADR-501)
 *
 * Holds the lazy-expanded tree state for the Catalog Explorer so a browse
 * session survives navigating away and back. Mirrors documentExplorerStore:
 * in-memory (survives mount/unmount within a session) but NOT persisted to
 * localStorage — the catalog is a projection of a graph that autonomous
 * annealing (ADR-200) reorganizes, so a stale expanded-tree snapshot would
 * go wrong the moment the graph changes. The durable record is the graph
 * itself; we re-fetch each level on demand.
 *
 * The tree is keyed by node id. `childrenByParent` caches the children we've
 * already fetched for an expanded node; `expanded` tracks which nodes are
 * open. The root listing (ontologies) is cached under the ROOT_KEY sentinel.
 */

import { create } from 'zustand';
import type { CatalogNode } from '../types/catalog';

/** Sentinel parent key for the root (ontology) level. */
export const CATALOG_ROOT_KEY = '__root__';

interface CatalogExplorerStore {
  /** Children fetched per parent id (or CATALOG_ROOT_KEY for ontologies). */
  childrenByParent: Record<string, CatalogNode[]>;
  /** Total child count per parent, for "showing N of M" affordances. */
  totalByParent: Record<string, number>;
  /** Which node ids are currently expanded in the tree. */
  expanded: Record<string, boolean>;
  /** Parent ids whose children are currently being fetched. */
  loading: Record<string, boolean>;
  /** The currently-selected node (drives the detail panel). */
  selected: CatalogNode | null;
  /** Active name-fragment filter applied to listings. */
  filter: string;
  /** True if the last listing was served from a lagging index. */
  stale: boolean;

  setChildren: (parentKey: string, nodes: CatalogNode[], total: number) => void;
  setExpanded: (nodeId: string, open: boolean) => void;
  setLoading: (parentKey: string, loading: boolean) => void;
  setSelected: (node: CatalogNode | null) => void;
  setFilter: (filter: string) => void;
  setStale: (stale: boolean) => void;
  /** Drop all cached children/expansion — used when the filter changes or on
   *  an explicit refresh, so the next render re-fetches against the graph. */
  reset: () => void;
}

export const useCatalogExplorerStore = create<CatalogExplorerStore>((set) => ({
  childrenByParent: {},
  totalByParent: {},
  expanded: {},
  loading: {},
  selected: null,
  filter: '',
  stale: false,

  setChildren: (parentKey, nodes, total) =>
    set((s) => ({
      childrenByParent: { ...s.childrenByParent, [parentKey]: nodes },
      totalByParent: { ...s.totalByParent, [parentKey]: total },
    })),
  setExpanded: (nodeId, open) =>
    set((s) => ({ expanded: { ...s.expanded, [nodeId]: open } })),
  setLoading: (parentKey, loading) =>
    set((s) => ({ loading: { ...s.loading, [parentKey]: loading } })),
  setSelected: (selected) => set({ selected }),
  setFilter: (filter) => set({ filter }),
  setStale: (stale) => set({ stale }),
  reset: () =>
    set({
      childrenByParent: {},
      totalByParent: {},
      expanded: {},
      loading: {},
      selected: null,
      stale: false,
    }),
}));
