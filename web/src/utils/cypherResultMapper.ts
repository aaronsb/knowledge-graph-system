/**
 * Result Mappers
 *
 * Maps query results to the canonical raw graph format used by the store
 * (rawGraphData). Two mappers:
 *
 * - mapCypherResultToRawGraph: Legacy AGE internal ID → concept_id translation
 * - mapWorkingGraphToRawGraph: GraphProgram WorkingGraph → RawGraphData (no ID
 *   translation needed since WorkingGraph already uses concept_id keys)
 */

import type { WorkingGraph } from '../types/program';

export interface CypherResultNode {
  id: string;
  label: string;
  properties?: {
    concept_id?: string;
    ontology?: string;
    search_terms?: string[];
    grounding_strength?: number;
    [key: string]: unknown;
  };
}

export interface CypherResultRelationship {
  from_id: string;
  to_id: string;
  type: string;
  properties?: {
    category?: string;
    [key: string]: unknown;
  };
  confidence?: number;
}

export interface CypherQueryResult {
  nodes?: CypherResultNode[];
  relationships?: CypherResultRelationship[];
  row_count?: number;
}

export interface RawGraphNode {
  concept_id: string;
  label: string;
  ontology?: string;
  description?: string;
  search_terms?: string[];
  grounding_strength?: number;
  diversity_score?: number;
  evidence_count?: number;
}

export interface RawGraphLink {
  from_id: string;
  to_id: string;
  relationship_type: string;
  category?: string;
  confidence?: number;
  grounding_strength?: number;
}

/** Canonical shape for raw graph data throughout the store and pipeline */
export interface RawGraphData {
  nodes: RawGraphNode[];
  links: RawGraphLink[];
}

// --- AGE Path Result Types ---

/** A node in an AGE path result (concept or empty relationship placeholder) */
export interface PathResultNode {
  id: string;
  label: string;
  description?: string;
  grounding_strength?: number;
  confidence_level?: string;
  diversity_score?: number;
}

/** AGE path result with interleaved nodes and relationship type strings */
export interface PathResult {
  nodes: PathResultNode[];
  relationships: string[];
  hops?: number;
}

/**
 * Map a Cypher query result (with AGE internal IDs) to the canonical
 * raw graph format expected by mergeRawGraphData / subtractRawGraphData.
 */
export function mapCypherResultToRawGraph(result: CypherQueryResult): {
  nodes: RawGraphNode[];
  links: RawGraphLink[];
} {
  // Build AGE internal ID → concept_id map
  const internalToConceptId = new Map<string, string>();
  (result.nodes || []).forEach((n) => {
    const conceptId = n.properties?.concept_id || n.id;
    internalToConceptId.set(n.id, conceptId);
  });

  const nodes: RawGraphNode[] = (result.nodes || []).map((n) => ({
    concept_id: n.properties?.concept_id || n.id,
    label: n.label,
    ontology: n.properties?.ontology || 'default',
    search_terms: n.properties?.search_terms || [],
    grounding_strength: n.properties?.grounding_strength,
  }));

  const links: RawGraphLink[] = (result.relationships || [])
    .filter((r) => {
      // Drop links whose endpoints aren't in the result node set —
      // AGE internal IDs would leak through and crash d3 forceLink.
      return internalToConceptId.has(r.from_id) && internalToConceptId.has(r.to_id);
    })
    .map((r) => ({
      from_id: internalToConceptId.get(r.from_id)!,
      to_id: internalToConceptId.get(r.to_id)!,
      relationship_type: r.type,
      category: r.properties?.category,
      confidence: r.confidence,
    }));

  return { nodes, links };
}

/**
 * Extract graph data from an AGE path result.
 *
 * AGE path results interleave concept nodes with empty placeholder nodes
 * (relationship slots). This function filters to real concept nodes,
 * infers the relationship type between consecutive nodes, and returns
 * canonical raw graph format plus the ordered concept node IDs (useful
 * for path animation and enrichment).
 */
export function extractGraphFromPath(path: PathResult): {
  nodes: RawGraphNode[];
  links: RawGraphLink[];
  conceptNodeIds: string[];
} {
  const conceptNodes: PathResultNode[] = [];
  const conceptRelTypes: string[][] = [];
  let pendingRels: string[] = [];

  for (let i = 0; i < path.nodes.length; i++) {
    const node = path.nodes[i];
    if (node.id && node.id !== '') {
      conceptNodes.push(node);
      conceptRelTypes.push(pendingRels);
      pendingRels = [];
    }
    if (i < path.relationships.length) {
      pendingRels.push(path.relationships[i]);
    }
  }

  const nodes: RawGraphNode[] = conceptNodes.map((node) => ({
    concept_id: node.id,
    label: node.label,
    description: node.description,
    ontology: 'default',
    grounding_strength: node.grounding_strength,
  }));

  const links: RawGraphLink[] = [];
  for (let i = 0; i < conceptNodes.length - 1; i++) {
    const rels = conceptRelTypes[i + 1];
    const relType = rels.find(r => r !== 'APPEARS' && r !== 'SCOPED_BY') || rels[0] || 'CONNECTED';
    links.push({
      from_id: conceptNodes[i].id,
      to_id: conceptNodes[i + 1].id,
      relationship_type: relType,
    });
  }

  return { nodes, links, conceptNodeIds: conceptNodes.map(n => n.id) };
}

/**
 * Map a GraphProgram WorkingGraph to the canonical raw graph format.
 *
 * WorkingGraph nodes already use concept_id as identity — no AGE internal
 * ID translation needed. Properties like grounding_strength and search_terms
 * are extracted from the properties bag into flat fields.
 */
export function mapWorkingGraphToRawGraph(wg: WorkingGraph): RawGraphData {
  const nodes: RawGraphNode[] = wg.nodes.map((n) => ({
    concept_id: n.concept_id,
    label: n.label,
    ontology: n.ontology ?? 'default',
    description: n.description ?? undefined,
    search_terms: (n.properties.search_terms as string[] | undefined) ?? [],
    grounding_strength: n.properties.grounding_strength as number | undefined,
    diversity_score: n.properties.diversity_score as number | undefined,
    evidence_count: n.properties.evidence_count as number | undefined,
  }));

  const links: RawGraphLink[] = wg.links.map((l) => ({
    from_id: l.from_id,
    to_id: l.to_id,
    relationship_type: l.relationship_type,
    category: l.category ?? undefined,
    confidence: l.confidence ?? undefined,
    grounding_strength: l.properties.grounding_strength as number | undefined,
  }));

  return { nodes, links };
}
