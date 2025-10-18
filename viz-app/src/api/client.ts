/**
 * REST API Client
 *
 * Communicates with the Knowledge Graph System API at localhost:8000
 */

import axios, { type AxiosInstance } from 'axios';
import type { SubgraphResponse } from '../types/graph';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000, // 30 seconds
    });
  }

  /**
   * Get subgraph centered on a concept
   * Fetches related concepts and ALL relationships between them
   */
  async getSubgraph(params: {
    center_concept_id: string;
    depth?: number;
    relationship_types?: string[];
    limit?: number;
  }): Promise<SubgraphResponse> {
    // Step 1: Fetch related concepts
    const response = await this.client.post<any>('/query/related', {
      concept_id: params.center_concept_id,
      max_depth: params.depth || 1, // Use depth 1 for better performance
      relationship_types: params.relationship_types,
    });

    const relatedConcepts = response.data.results || [];

    // Step 2: Collect all concept IDs (center + related)
    const allConceptIds = [
      params.center_concept_id,
      ...relatedConcepts.map((rc: any) => rc.concept_id)
    ];

    // Step 3: Fetch details for all concepts in parallel
    const conceptDetailsPromises = allConceptIds.map(id =>
      this.client.get(`/query/concept/${id}`).then(r => r.data).catch(() => null)
    );

    const allConceptDetails = (await Promise.all(conceptDetailsPromises)).filter(Boolean);

    // Step 4: Build nodes array
    const nodes = allConceptDetails.map((concept: any) => ({
      concept_id: concept.concept_id,
      label: concept.label,
      ontology: 'default',
      search_terms: concept.search_terms || [],
    }));

    // Step 5: Build links array from ALL concepts' relationships
    // Only include links where both source and target are in our node set
    const nodeIdSet = new Set(allConceptIds);
    const links: any[] = [];
    const seenEdges = new Set<string>(); // Deduplicate edges

    allConceptDetails.forEach((concept: any) => {
      if (concept.relationships) {
        concept.relationships.forEach((rel: any) => {
          // Only include if target is in our subgraph
          if (nodeIdSet.has(rel.to_id)) {
            const edgeKey = `${concept.concept_id}->${rel.to_id}-${rel.rel_type}`;
            if (!seenEdges.has(edgeKey)) {
              seenEdges.add(edgeKey);
              links.push({
                from_id: concept.concept_id,
                to_id: rel.to_id,
                relationship_type: rel.rel_type,
                confidence: rel.confidence,
              });
            }
          }
        });
      }
    });

    return {
      nodes,
      links,
      stats: {
        node_count: nodes.length,
        edge_count: links.length,
      },
    };
  }

  /**
   * Find paths between two concepts
   */
  async findPath(params: {
    from_id: string;
    to_id: string;
    max_hops?: number;
    algorithm?: 'shortest' | 'all_simple' | 'weighted';
  }): Promise<any> {
    const response = await this.client.get('/viz/graph/path', {
      params,
    });
    return response.data;
  }

  /**
   * Compare two ontologies
   */
  async compareOntologies(params: {
    ontology_a: string;
    ontology_b: string;
  }): Promise<any> {
    const response = await this.client.get('/viz/ontology/compare', {
      params,
    });
    return response.data;
  }

  /**
   * Get graph timeline evolution
   */
  async getTimeline(params: {
    ontology: string;
    start_date?: string;
    end_date?: string;
    granularity?: 'day' | 'week' | 'month';
  }): Promise<any> {
    const response = await this.client.get('/viz/graph/timeline', {
      params,
    });
    return response.data;
  }

  /**
   * Get adjacency matrix for concepts
   */
  async getAdjacencyMatrix(concept_ids: string[]): Promise<any> {
    const response = await this.client.get('/viz/graph/matrix', {
      params: {
        concept_ids: concept_ids.join(','),
      },
    });
    return response.data;
  }

  /**
   * Search concepts by query
   */
  async searchConcepts(params: {
    query: string;
    limit?: number;
    min_similarity?: number;
    offset?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/search', params);
    return response.data;
  }

  /**
   * Search concepts by embedding (for Follow Concept functionality)
   * Uses concept's existing embedding to find similar concepts
   */
  async searchByEmbedding(params: {
    embedding: number[];
    limit?: number;
    min_similarity?: number;
    offset?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/search', {
      embedding: params.embedding,
      limit: params.limit,
      min_similarity: params.min_similarity,
      offset: params.offset,
    });
    return response.data;
  }

  /**
   * Get concept details
   */
  async getConceptDetails(concept_id: string): Promise<any> {
    const response = await this.client.get(`/query/concept/${concept_id}`);
    return response.data;
  }

  /**
   * Find paths between two concepts using semantic phrase matching
   */
  async findConnectionBySearch(params: {
    from_query: string;
    to_query: string;
    max_hops?: number;
    threshold?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/connect-by-search', params);
    return response.data;
  }

  /**
   * Get related concepts (neighborhood)
   */
  async getRelatedConcepts(params: {
    concept_id: string;
    max_depth?: number;
    relationship_types?: string[];
  }): Promise<any> {
    const response = await this.client.post('/query/related', params);
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new APIClient();
