/**
 * Catalog browse types (ADR-501)
 *
 * Mirror of the API's CatalogNode DTO. Shared by the web client and the
 * Catalog Explorer. The hierarchy is fixed and self-describing via `kind`:
 * ontology -> document -> concept.
 */

export type CatalogKind = 'ontology' | 'document' | 'concept';

/** A single node in the catalog hierarchy. */
export interface CatalogNode {
  kind: CatalogKind;
  id: string;
  name: string;
  parent_id?: string | null;
  child_count?: number | null;
  content_type?: string | null;
  properties: Record<string, any>;
}

/** Paginated listing of a node's children (GET /catalog/children). */
export interface CatalogChildrenResponse {
  parent_id?: string | null;
  parent_kind?: CatalogKind | null;
  child_kind: CatalogKind;
  nodes: CatalogNode[];
  total: number;
  limit: number;
  offset: number;
  query?: string | null;
  stale: boolean;
}

/** Single node with full metadata (GET /catalog/node/{id}). */
export interface CatalogNodeResponse extends CatalogNode {
  graph_epoch?: number | null;
  indexed_at?: string | null;
}
