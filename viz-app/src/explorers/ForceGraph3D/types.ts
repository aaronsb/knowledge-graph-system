/**
 * Force-Directed 3D Graph Explorer - Type Definitions
 */

import type { GraphData } from '../../types/graph';

export type NodeColorMode = 'ontology' | 'degree' | 'centrality';
export type EdgeColorMode = 'category' | 'confidence' | 'uniform';
export type LayoutAlgorithm = 'force' | 'circular' | 'grid';

export interface ForceGraph3DSettings {
  // Physics simulation
  physics: {
    enabled: boolean;
    charge: number; // Repulsion strength (-100 to -1000)
    linkDistance: number; // Target link distance (10-200)
    gravity: number; // Center gravity (0-1)
    friction: number; // Velocity decay (0-1)
  };

  // Visual appearance
  visual: {
    nodeColorBy: NodeColorMode;
    edgeColorBy: EdgeColorMode;
    showLabels: boolean;
    showArrows: boolean;
    showGrid: boolean;
    showShadows: boolean; // 3D-style shadows and highlights
    nodeSize: number; // Base node size multiplier (0.5-3)
    linkWidth: number; // Base link width (0.5-5)
  };

  // Interaction
  interaction: {
    enableDrag: boolean;
    enableZoom: boolean;
    enablePan: boolean;
    highlightNeighbors: boolean;
    showOriginNode: boolean; // "You Are Here" highlighting
  };

  // Filters
  filters: {
    relationshipTypes: string[];
    ontologies: string[];
    minConfidence: number; // 0-1
  };

  // Layout
  layout: LayoutAlgorithm;
}

export interface ForceGraph3DData extends GraphData {
  // Already has nodes and links
}

export const DEFAULT_SETTINGS: ForceGraph3DSettings = {
  physics: {
    enabled: true,
    charge: -300,
    linkDistance: 80,
    gravity: 0.1,
    friction: 0.9,
  },
  visual: {
    nodeColorBy: 'ontology',
    edgeColorBy: 'category',
    showLabels: true, // Enabled by default for better readability
    showArrows: true,
    showGrid: true,
    showShadows: false, // Disabled by default for performance
    nodeSize: 1,
    linkWidth: 1,
  },
  interaction: {
    enableDrag: true,
    enableZoom: true,
    enablePan: true,
    highlightNeighbors: true,
    showOriginNode: true,
  },
  filters: {
    relationshipTypes: [],
    ontologies: [],
    minConfidence: 0,
  },
  layout: 'force',
};
