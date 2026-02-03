/**
 * Cypher Result Mapper
 *
 * Maps Apache AGE Cypher query results to the canonical raw graph format
 * used by the store (rawGraphData). Handles the AGE internal ID → concept_id
 * mapping that's required because AGE returns its own vertex IDs, not
 * the concept_ids stored in node properties.
 *
 * Used by both the Cypher editor (SearchBar) and saved query replay (ExplorerView).
 */

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

  const links: RawGraphLink[] = (result.relationships || []).map((r) => ({
    from_id: internalToConceptId.get(r.from_id) || r.from_id,
    to_id: internalToConceptId.get(r.to_id) || r.to_id,
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
