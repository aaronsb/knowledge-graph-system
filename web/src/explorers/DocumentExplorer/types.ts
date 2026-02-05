/**
 * DocumentExplorer Types — Multi-Document Concept Graph
 *
 * Query-driven concept graph with document hydration.
 * Three node types: document (golden), query-concept (amber), extended-concept (indigo).
 */

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface DocumentExplorerSettings {
  visual: {
    showLabels: boolean;
    showEdges: boolean;
    nodeSize: number;           // Base size multiplier
  };
  layout: {
    documentSize: number;       // Document node size (20-60)
  };
  interaction: {
    enableZoom: boolean;
    enablePan: boolean;
    highlightOnHover: boolean;
  };
}

export const DEFAULT_SETTINGS: DocumentExplorerSettings = {
  visual: {
    showLabels: true,
    showEdges: true,
    nodeSize: 1.0,
  },
  layout: {
    documentSize: 24,
  },
  interaction: {
    enableZoom: true,
    enablePan: true,
    highlightOnHover: true,
  },
};

export const SLIDER_RANGES = {
  visual: {
    nodeSize: { min: 0.5, max: 2.0, step: 0.1 },
  },
  layout: {
    documentSize: { min: 16, max: 48, step: 4 },
  },
};

// ---------------------------------------------------------------------------
// Graph data
// ---------------------------------------------------------------------------

export type DocNodeType = 'document' | 'query-concept' | 'extended-concept';

/** A node in the multi-document concept graph. */
export interface DocGraphNode {
  id: string;
  label: string;
  type: DocNodeType;
  /** Which documents own this concept (empty for document nodes). */
  documentIds: string[];
  /** Base render size (before settings multiplier). */
  size: number;
}

/** An edge in the graph. */
export interface DocGraphLink {
  source: string;
  target: string;
  /** Relationship type (e.g. IMPLIES) or '__doc_cluster__' for invisible clustering links. */
  type: string;
  /** False for document→concept clustering links (not rendered). */
  visible: boolean;
}

/** Document metadata for the sidebar list. */
export interface DocExplorerDocument {
  id: string;
  label: string;
  ontology: string;
  /** ALL concept IDs for this document (from bulk fetch). */
  conceptIds: string[];
  /** Concept IDs that overlap with the exploration query. */
  queryConceptIds: string[];
}

/** Full data structure for the multi-document concept graph. */
export interface DocumentExplorerData {
  documents: DocExplorerDocument[];
  nodes: DocGraphNode[];
  links: DocGraphLink[];
  /** Global set of concept IDs from the exploration query. */
  queryConceptIds: string[];
}

/** A passage search result from scoped source search. */
export interface PassageSearchResult {
  sourceId: string;
  documentId: string;
  documentFilename: string;
  paragraph: number;
  chunkText: string;
  similarity: number;
  concepts: Array<{ conceptId: string; label: string }>;
}
