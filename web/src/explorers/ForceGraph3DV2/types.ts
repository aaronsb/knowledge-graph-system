/**
 * ForceGraph3D V2 — Type Definitions
 *
 * Built on the unified rendering engine described in ADR-702.
 * Engine shape: {EngineNode[], EngineEdge[]} with kg-specific properties
 * from spike findings (separate id/label, edge-type palette, directed
 * arrows).
 */

import type { APIGraphNode, APIGraphLink } from '../../types/graph';
import type { NodeColorMode } from '../common';

export type { NodeColorMode };

/** A node as consumed by the unified rendering engine.  @verified c17bbeb9 */
export interface EngineNode {
  /** Stable key (e.g. kg concept_id). Used for identity and picking. */
  id: string;
  /** Human-readable display text. Separate from id per spike finding #3. */
  label: string;
  /** Opaque string; resolved via the palette prop. */
  category: string;
  /** Used for size scaling. */
  degree: number;
  /** Whether the engine should hold this node's position against the sim. */
  pinned?: boolean;
  /** Full API payload passed through so widgets can read without re-fetch. */
  source?: APIGraphNode;
}

/** An edge as consumed by the unified rendering engine.  @verified c17bbeb9 */
export interface EngineEdge {
  /** Source node id. */
  from: string;
  /** Target node id. */
  to: string;
  /** Relationship type (e.g. "IMPLIES"); resolved via the edgePalette prop. */
  type: string;
  /** Optional weight, may drive line thickness or arrow size. */
  weight?: number;
  /** Full API payload passed through. */
  source?: APIGraphLink;
}

/** Data shape the V2 explorer plugin consumes.  @verified c17bbeb9 */
export interface ForceGraph3DV2Data {
  nodes: EngineNode[];
  edges: EngineEdge[];
}

export type PhysicsBackend = 'auto' | 'cpu' | 'gpu';
export type EdgeColorMode = 'endpoint' | 'type';

/** Runtime settings for the V2 explorer plugin.  @verified c17bbeb9 */
export interface ForceGraph3DV2Settings {
  physics: {
    enabled: boolean;
    repulsion: number;
    attraction: number;
    centerGravity: number;
    damping: number;
    backend: PhysicsBackend;
  };

  visual: {
    showArrows: boolean;
    /** Persistent edge-type labels on edges. */
    showLabels: boolean;
    /** Persistent node labels above each node. */
    showNodeLabels: boolean;
    nodeColorBy: NodeColorMode;
    edgeColorBy: EdgeColorMode;
    labelVisibilityRadius: number;
    nodeSize: number;
  };

  interaction: {
    enableDrag: boolean;
    enableZoom: boolean;
    enablePan: boolean;
    highlightNeighbors: boolean;
  };
}

export const DEFAULT_SETTINGS: ForceGraph3DV2Settings = {
  physics: {
    enabled: true,
    repulsion: 120,
    attraction: 0.04,
    centerGravity: 0.004,
    damping: 0.93,
    backend: 'auto',
  },
  visual: {
    showArrows: true,
    showLabels: true,
    showNodeLabels: true,
    nodeColorBy: 'ontology',
    edgeColorBy: 'type',
    labelVisibilityRadius: 250,
    nodeSize: 1.0,
  },
  interaction: {
    enableDrag: true,
    enableZoom: true,
    enablePan: true,
    highlightNeighbors: true,
  },
};

export const SLIDER_RANGES = {
  physics: {
    repulsion: { min: 20, max: 500, step: 5 },
    attraction: { min: 0, max: 0.2, step: 0.005 },
    centerGravity: { min: 0, max: 0.05, step: 0.001 },
    damping: { min: 0.5, max: 0.99, step: 0.01 },
  },
  visual: {
    labelVisibilityRadius: { min: 50, max: 1000, step: 10 },
    nodeSize: { min: 0.3, max: 3, step: 0.1 },
  },
};
