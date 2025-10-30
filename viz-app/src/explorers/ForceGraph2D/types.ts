/**
 * Force-Directed 2D Graph Explorer - Type Definitions
 */

import type { GraphData } from '../../types/graph';

export type NodeColorMode = 'ontology' | 'degree' | 'centrality';
export type EdgeColorMode = 'category' | 'confidence' | 'uniform';
export type LayoutAlgorithm = 'force' | 'circular' | 'grid';

export interface ForceGraph2DSettings {
  // Physics simulation
  physics: {
    enabled: boolean;
    charge: number; // Repulsion strength (-100 to -1000)
    linkDistance: number; // Target link distance (10-400)
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
    nodeLabelSize: number; // Node label font size (6-20px)
    edgeLabelSize: number; // Edge label font size (6-20px)
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

export interface ForceGraph2DData extends GraphData {
  // Already has nodes and links
}

export const DEFAULT_SETTINGS: ForceGraph2DSettings = {
  physics: {
    enabled: true,
    charge: -750,        // Strong repulsion for clear spacing in 2D
    linkDistance: 200,   // Longer links for better graph layout
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
    nodeSize: 1.9,       // Larger nodes for better visibility
    linkWidth: 1.0,
    nodeLabelSize: 12,
    edgeLabelSize: 12,   // Consistent with node labels in 2D plane
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

// Slider range configurations for 2D graph
export const SLIDER_RANGES = {
  physics: {
    charge: { min: -1000, max: -100, step: 50 },
    linkDistance: { min: 10, max: 400, step: 10 },  // Extended range for larger graphs
    gravity: { min: 0, max: 1, step: 0.05 },
  },
  visual: {
    nodeSize: { min: 0.5, max: 3, step: 0.1 },
    linkWidth: { min: 0.5, max: 5, step: 0.1 },
    nodeLabelSize: { min: 6, max: 20, step: 1 },
    edgeLabelSize: { min: 6, max: 20, step: 1 },     // Smaller range for 2D (everything at same viewing distance)
  },
};
