/**
 * Data transformer — RawGraphData → ForceGraph3DV2Data
 *
 * Converts the store's raw node/link records into the engine's
 * {EngineNode[], EngineEdge[]} shape. Degree is computed here (not in the
 * engine) so the engine can treat it as an opaque size input and not
 * recompute per-frame.
 */

import type { RawGraphData } from '../../utils/cypherResultMapper';
import type { EngineNode, EngineEdge, ForceGraph3DV2Data } from './types';

/** Transform store graph data to the engine's node/edge shape.  @verified c17bbeb9 */
export function transformForEngine(apiData: RawGraphData): ForceGraph3DV2Data {
  const apiNodes = apiData.nodes || [];
  const apiLinks = apiData.links || [];

  // Compute degree once. Undirected — each relationship counts at both ends
  // so high-degree hubs stand out regardless of edge direction.
  const degree = new Map<string, number>();
  for (const link of apiLinks) {
    degree.set(link.from_id, (degree.get(link.from_id) ?? 0) + 1);
    degree.set(link.to_id, (degree.get(link.to_id) ?? 0) + 1);
  }

  const nodes: EngineNode[] = apiNodes.map((n) => ({
    id: n.concept_id,
    label: n.label || n.concept_id,
    category: n.ontology || 'Unknown',
    degree: degree.get(n.concept_id) ?? 0,
    source: n,
  }));

  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges: EngineEdge[] = apiLinks
    .filter((l) => nodeIds.has(l.from_id) && nodeIds.has(l.to_id))
    .map((l) => ({
      from: l.from_id,
      to: l.to_id,
      type: l.relationship_type,
      source: l,
    }));

  return { nodes, edges };
}
