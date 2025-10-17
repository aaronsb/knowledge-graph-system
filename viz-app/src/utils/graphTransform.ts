/**
 * Graph Data Transformation
 *
 * Transforms API graph data to D3/Three.js visualization formats.
 */

import * as d3 from 'd3';
import type {
  APIGraphNode,
  APIGraphLink,
  D3Node,
  D3Link,
  GraphData,
  Node3D,
  Link3D,
  Graph3DData,
} from '../types/graph';

/**
 * Get color for relationship category
 */
function getLinkColor(category?: string): string {
  const colors: Record<string, string> = {
    logical: '#3b82f6', // blue
    evidential: '#22c55e', // green
    structural: '#a855f7', // purple
    temporal: '#f59e0b', // amber
    default: '#6b7280', // gray
  };

  return colors[category || 'default'] || colors.default;
}

/**
 * Transform API data to D3 2D format
 */
export function transformForD3(
  apiNodes: APIGraphNode[],
  apiLinks: APIGraphLink[]
): GraphData {
  // Create color scale for ontologies
  const ontologies = [...new Set(apiNodes.map(n => n.ontology))];
  const colorScale = d3.scaleOrdinal(d3.schemeCategory10).domain(ontologies);

  // Transform nodes
  const nodes: D3Node[] = apiNodes.map(node => ({
    id: node.concept_id,
    label: node.label,
    group: node.ontology,
    size: 10, // Will be updated with degree
    color: colorScale(node.ontology),
  }));

  // Transform links
  const links: D3Link[] = apiLinks.map(link => ({
    source: link.from_id,
    target: link.to_id,
    type: link.relationship_type,
    value: link.confidence || 1.0,
    color: getLinkColor(link.category),
  }));

  // Calculate node degrees and update sizes
  const degrees = new Map<string, number>();
  links.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;

    degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
    degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
  });

  nodes.forEach(node => {
    const degree = degrees.get(node.id) || 1;
    // Logarithmic scaling for node size (5-30 range)
    node.size = Math.max(5, Math.min(30, 5 + Math.log(degree + 1) * 5));
  });

  return { nodes, links };
}

/**
 * Transform API data to Three.js 3D format
 */
export function transformFor3D(
  apiNodes: APIGraphNode[],
  apiLinks: APIGraphLink[]
): Graph3DData {
  // Start with 2D transform
  const { nodes: nodes2d, links: links2d } = transformForD3(apiNodes, apiLinks);

  // Convert to 3D nodes
  const nodes: Node3D[] = nodes2d.map(node => ({
    ...node,
    z: 0, // Will be positioned by force simulation
  }));

  // Convert to 3D links
  const links: Link3D[] = links2d.map(link => ({
    ...link,
  }));

  return { nodes, links };
}

/**
 * Filter graph data by relationship types
 */
export function filterByRelationshipType(
  data: GraphData,
  types: string[]
): GraphData {
  const filteredLinks = data.links.filter(link => types.includes(link.type));

  // Get all node IDs that are connected by filtered links
  const connectedNodeIds = new Set<string>();
  filteredLinks.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;
    connectedNodeIds.add(sourceId);
    connectedNodeIds.add(targetId);
  });

  // Filter nodes to only include connected ones
  const filteredNodes = data.nodes.filter(node => connectedNodeIds.has(node.id));

  return {
    nodes: filteredNodes,
    links: filteredLinks,
  };
}

/**
 * Get neighbors of a node
 */
export function getNeighbors(nodeId: string, links: D3Link[]): Set<string> {
  const neighbors = new Set<string>();

  links.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;

    if (sourceId === nodeId) {
      neighbors.add(targetId);
    }
    if (targetId === nodeId) {
      neighbors.add(sourceId);
    }
  });

  return neighbors;
}

/**
 * Find hub nodes (high degree centrality)
 */
export function findHubNodes(data: GraphData, topN: number = 10): D3Node[] {
  // Calculate degrees
  const degrees = new Map<string, number>();

  data.links.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;

    degrees.set(sourceId, (degrees.get(sourceId) || 0) + 1);
    degrees.set(targetId, (degrees.get(targetId) || 0) + 1);
  });

  // Sort nodes by degree
  const sortedNodes = [...data.nodes].sort((a, b) => {
    const degreeA = degrees.get(a.id) || 0;
    const degreeB = degrees.get(b.id) || 0;
    return degreeB - degreeA;
  });

  return sortedNodes.slice(0, topN);
}
