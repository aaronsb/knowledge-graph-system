/**
 * Shared node-coloring computation for graph explorers.
 *
 * Callers feed `mode` from settings.visual.nodeColorBy and consume the
 * returned Map<id, color> to drive the instanced color buffer on the
 * unified r3f engine. Inputs are minimal-shape adapters so the helper
 * can also serve future explorers that share the engine but carry their
 * own node/edge shape.
 */

import * as d3 from 'd3';

/** Node-color dimension. */
export type NodeColorMode = 'ontology' | 'degree' | 'centrality';

export interface NodeColorInput {
  id: string;
  /** Color used in 'ontology' mode and as fallback. Typically the palette
   *  result for the node's category/ontology. */
  fallbackColor: string;
}

export interface EdgeColorInput {
  sourceId: string;
  targetId: string;
}

/** Compute per-node colors for the given mode.  @verified e05014ea */
export function computeNodeColors(
  nodes: NodeColorInput[],
  edges: EdgeColorInput[],
  mode: NodeColorMode,
): Map<string, string> {
  const colors = new Map<string, string>();

  if (mode === 'ontology') {
    for (const n of nodes) colors.set(n.id, n.fallbackColor);
    return colors;
  }

  // Degree and centrality both derive from edge-incidence counts. Centrality
  // currently uses degree as a proxy (matches 2D's behavior at lines
  // 311-327 of ForceGraph2D.tsx); a true centrality measure can replace
  // this without changing the call site.
  const degrees = new Map<string, number>();
  for (const e of edges) {
    degrees.set(e.sourceId, (degrees.get(e.sourceId) || 0) + 1);
    degrees.set(e.targetId, (degrees.get(e.targetId) || 0) + 1);
  }
  const maxDegree = Math.max(1, ...Array.from(degrees.values()));
  const interpolator = mode === 'degree' ? d3.interpolateViridis : d3.interpolatePlasma;
  const scale = d3.scaleSequential(interpolator).domain([0, maxDegree]);

  for (const n of nodes) {
    colors.set(n.id, scale(degrees.get(n.id) || 0));
  }
  return colors;
}
