/**
 * DocumentExplorer Types
 *
 * Radial visualization of document→concept relationships with
 * spreading activation decay (ADR-085).
 */

export interface DocumentExplorerSettings {
  visual: {
    maxHops: 1 | 2 | 3;
    decayFactor: number;        // 0.5-0.9, default 0.7
    minOpacity: number;         // 0.2-0.5, default 0.2
    showLabels: boolean;
    colorBy: 'grounding' | 'ontology';
    nodeSize: number;           // Base size multiplier
  };
  layout: {
    ringRadius: number;         // Distance between rings (50-200)
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
    maxHops: 2,
    decayFactor: 0.7,
    minOpacity: 0.2,
    showLabels: true,
    colorBy: 'grounding',
    nodeSize: 1.0,
  },
  layout: {
    ringRadius: 120,
    centerSize: 40,
  },
  interaction: {
    enableZoom: true,
    enablePan: true,
    highlightOnHover: true,
  },
};

export const SLIDER_RANGES = {
  visual: {
    decayFactor: { min: 0.5, max: 0.9, step: 0.05 },
    minOpacity: { min: 0.1, max: 0.5, step: 0.05 },
    nodeSize: { min: 0.5, max: 2.0, step: 0.1 },
  },
  layout: {
    ringRadius: { min: 50, max: 200, step: 10 },
    centerSize: { min: 20, max: 60, step: 5 },
  },
};

// Data structures for the visualization
export interface DocumentNode {
  id: string;
  type: 'document';
  label: string;
  ontology: string;
  conceptCount: number;
}

export interface ConceptNode {
  id: string;
  type: 'concept';
  label: string;
  ontology: string;
  hop: number;
  grounding_strength: number;
  grounding_display?: string;
  instanceCount: number;
  // Fixed positions for radial layout
  fx?: number;
  fy?: number;
  // Parent concept ID (for tree structure)
  parentId?: string;
}

// Tree node for hierarchical layout
export interface ConceptTreeNode {
  id: string;
  type: 'concept' | 'document';
  label: string;
  ontology: string;
  hop: number;
  grounding_strength: number;
  grounding_display?: string;
  instanceCount?: number;
  children: ConceptTreeNode[];
  // Computed by d3.tree layout
  x?: number;  // angle in radians
  y?: number;  // radius
  fx?: number; // cartesian x
  fy?: number; // cartesian y
}

export interface ConceptLink {
  source: string;
  target: string;
  type: string;           // Relationship type
  confidence?: number;
}

export interface DocumentExplorerData {
  document: DocumentNode;
  concepts: ConceptNode[];
  links: ConceptLink[];
  // Tree structure for radial tidy tree layout
  treeRoot?: ConceptTreeNode;
}
