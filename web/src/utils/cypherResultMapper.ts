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
  ontology: string;
  search_terms: string[];
  grounding_strength?: number;
}

export interface RawGraphLink {
  from_id: string;
  to_id: string;
  relationship_type: string;
  category?: string;
  confidence?: number;
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
