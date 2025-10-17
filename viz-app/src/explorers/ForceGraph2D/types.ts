/**
 * Force-Directed 2D Graph Explorer - Type Definitions
 */

import type { GraphData } from '../../types/graph';

export type ColorMode = 'ontology' | 'degree' | 'centrality';
export type LayoutAlgorithm = 'force' | 'circular' | 'grid';

export interface ForceGraph2DSettings {
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
    colorBy: ColorMode;
    showLabels: boolean;
    showArrows: boolean;
    nodeSize: number; // Base node size multiplier (0.5-3)
    linkWidth: number; // Base link width (0.5-5)
  };

  // Interaction
  interaction: {
    enableDrag: boolean;
    enableZoom: boolean;
    enablePan: boolean;
    highlightNeighbors: boolean;
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
    charge: -300,
    linkDistance: 80,
    gravity: 0.1,
    friction: 0.9,
  },
  visual: {
    colorBy: 'ontology',
    showLabels: true,
    showArrows: true,
    nodeSize: 1,
    linkWidth: 1,
  },
  interaction: {
    enableDrag: true,
    enableZoom: true,
    enablePan: true,
    highlightNeighbors: true,
  },
  filters: {
    relationshipTypes: [],
    ontologies: [],
    minConfidence: 0,
  },
  layout: 'force',
};
