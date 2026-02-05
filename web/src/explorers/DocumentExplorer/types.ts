/**
 * DocumentExplorer Types
 *
 * Force-directed concept cloud visualization for a single document (ADR-085).
 */

export interface DocumentExplorerSettings {
  visual: {
    showLabels: boolean;
    nodeSize: number;           // Base size multiplier
  };
  layout: {
    centerSize: number;         // Document node size (20-60)
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
    nodeSize: 1.0,
  },
  layout: {
    centerSize: 30,
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
    centerSize: { min: 20, max: 60, step: 5 },
  },
};

/** A concept node in the document cloud. */
export interface ConceptNode {
  id: string;
  label: string;
  // Force simulation positions (mutable by d3)
  x?: number;
  y?: number;
}

/** An edge between two concepts. */
export interface ConceptLink {
  source: string;
  target: string;
  type: string;
}

/** Data for the document concept cloud visualization. */
export interface DocumentExplorerData {
  /** The document being explored. */
  document: {
    id: string;
    label: string;
    ontology: string;
  };
  /** All concepts extracted from this document. */
  concepts: ConceptNode[];
  /** Inter-concept edges (concept↔concept relationships). */
  links: ConceptLink[];
  /** Concept IDs that matched the exploration query (for two-tone coloring). */
  queryConceptIds: string[];
}
