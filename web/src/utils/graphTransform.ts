/**
 * Graph Data Transformation
 *
 * Transforms API graph data to D3/Three.js visualization formats.
 */

import * as d3 from 'd3';
import { useVocabularyStore } from '../store/vocabularyStore';
import { getCategoryColor } from '../config/categoryColors';
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
 * Transform API data to D3 2D format
 * Automatically enriches links with vocabulary category data
 */
export function transformForD3(
  apiNodes: APIGraphNode[],
  apiLinks: APIGraphLink[]
): GraphData {
  // Get vocabulary data from store
  const vocabStore = useVocabularyStore.getState();

  // Create color scale for ontologies using equidistant points on a color ramp
  const ontologies = [...new Set(apiNodes.map(n => n.ontology))].sort();
  const colorScale = d3.scaleOrdinal<string>()
    .domain(ontologies)
    .range(ontologies.map((_, i) => {
      // Distribute ontologies evenly across the Turbo color ramp [0, 1]
      // Avoid extreme ends (0.1 to 0.9) for better visibility
      const t = ontologies.length === 1 ? 0.5 : 0.1 + (i / (ontologies.length - 1)) * 0.8;
      return d3.interpolateTurbo(t);
    }));

  // Transform nodes (with grounding strength)
  const nodes: D3Node[] = apiNodes.map(node => ({
    id: node.concept_id,
    label: node.label,
    group: node.ontology,
    size: 10, // Will be updated with degree
    color: colorScale(node.ontology),
    grounding: node.grounding_strength, // -1.0 to +1.0
  }));

  // Transform links - enrich with vocabulary data from store
  const links: D3Link[] = apiLinks.map(link => {
    // Look up category from vocabulary store
    let category = vocabStore.getCategory(link.relationship_type);

    if (!category) {
      // If vocabulary lookup failed, check if API provided category
      category = link.category;
    }

    if (!category || category === 'default') {
      // If still no category, group under "Uncategorized" instead of individual types
      // This keeps the legend cleaner and indicates these need categorization
      category = 'Uncategorized';
    }

    const categoryConfidence = vocabStore.getConfidence(link.relationship_type) || 1.0;

    return {
      source: link.from_id,
      target: link.to_id,
      type: link.relationship_type,
      value: categoryConfidence, // Use category confidence for visualization
      color: getCategoryColor(category),
      category, // Store category for info boxes
    };
  });

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
 * Filter graph data by edge categories
 * Hides edges with invisible categories AND their target nodes
 * (keeps source nodes as they may have other visible connections)
 */
export function filterByEdgeCategory(
  data: GraphData,
  visibleCategories: Set<string>
): GraphData {
  // If empty set, show all (default state)
  if (visibleCategories.size === 0) {
    return data;
  }

  // Filter links to only include visible categories
  const filteredLinks = data.links.filter(link =>
    visibleCategories.has(link.category || 'default')
  );

  // Get all node IDs that have ANY connections (visible or not)
  const allConnectedNodeIds = new Set<string>();
  data.links.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;
    allConnectedNodeIds.add(sourceId);
    allConnectedNodeIds.add(targetId);
  });

  // Get node IDs that have visible connections
  const visiblyConnectedNodeIds = new Set<string>();
  filteredLinks.forEach(link => {
    const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
    const targetId = typeof link.target === 'string' ? link.target : link.target.id;
    visiblyConnectedNodeIds.add(sourceId);
    visiblyConnectedNodeIds.add(targetId);
  });

  // Keep nodes that either:
  // 1. Have visible connections, or
  // 2. Have no connections at all (isolated nodes from additive loading)
  const filteredNodes = data.nodes.filter(node =>
    visiblyConnectedNodeIds.has(node.id) || !allConnectedNodeIds.has(node.id)
  );

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
