/**
 * CatalogExplorer Types (ADR-501)
 *
 * The Catalog Explorer is a tree/folder browse of the ontology -> document ->
 * concept hierarchy. Unlike the graph explorers it is self-fetching: it pulls
 * each level from /catalog on demand rather than transforming a preloaded
 * rawGraphData blob (mirrors DocumentExplorer's workspace-driven model).
 */

export interface CatalogExplorerSettings {
  /** Show child-count badges next to ontology/document rows. */
  showCounts: boolean;
  /** Sort order passed through to /catalog/children. */
  sort: 'name' | 'child_count' | 'created';
}

export const DEFAULT_SETTINGS: CatalogExplorerSettings = {
  showCounts: true,
  sort: 'name',
};

/** The explorer self-fetches, so its data prop is unused — kept for the
 *  ExplorerPlugin contract. */
export type CatalogExplorerData = Record<string, never>;
