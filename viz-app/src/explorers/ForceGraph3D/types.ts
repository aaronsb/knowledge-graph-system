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

  // Camera controls (3D-specific)
  camera: {
    lockRoll: boolean;   // Lock camera roll axis (keep upright relative to ground)
    lockPitch: boolean;  // Lock camera pitch axis (prevent looking up/down)
    lockYaw: boolean;    // Lock camera yaw axis (prevent rotating left/right)
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
    charge: -650,        // Stronger repulsion for 3D space
    linkDistance: 130,   // Longer links for better 3D depth perception
    gravity: 0.10,
    friction: 0.9,
  },
  visual: {
    nodeColorBy: 'ontology',
    edgeColorBy: 'category',
    showLabels: true, // Enabled by default for better readability
    showArrows: true,
    showGrid: true,
    showShadows: false, // Disabled by default for performance
    nodeSize: 0.40,      // Smaller default due to volume scaling (radius³)
    linkWidth: 1.0,
    nodeLabelSize: 12,
    edgeLabelSize: 16,   // Larger text for better readability in 3D space
  },
  interaction: {
    enableDrag: true,
    enableZoom: true,
    enablePan: true,
    highlightNeighbors: true,
    showOriginNode: true,
  },
  camera: {
    lockRoll: true,   // Lock roll by default to prevent disorienting tilting
    lockPitch: false, // Allow looking up/down
    lockYaw: false,   // Allow rotating around graph
  },
  filters: {
    relationshipTypes: [],
    ontologies: [],
    minConfidence: 0,
  },
  layout: 'force',
};

// Slider range configurations for 3D graph
// 3D uses tighter nodeSize range due to volume-based sizing (radius³)
export const SLIDER_RANGES = {
  physics: {
    charge: { min: -1000, max: -100, step: 50 },
    linkDistance: { min: 10, max: 200, step: 10 },
    gravity: { min: 0, max: 1, step: 0.05 },
  },
  visual: {
    nodeSize: { min: 0.1, max: 1.5, step: 0.05 },  // Tighter range for 3D volume scaling
    linkWidth: { min: 0.5, max: 5, step: 0.1 },
    nodeLabelSize: { min: 6, max: 20, step: 1 },
    edgeLabelSize: { min: 6, max: 20, step: 1 },
  },
};
