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
   * Uses the /query/related endpoint to fetch related concepts
   */
  async getSubgraph(params: {
    center_concept_id: string;
    depth?: number;
    relationship_types?: string[];
    limit?: number;
  }): Promise<SubgraphResponse> {
    const response = await this.client.post<any>('/query/related', {
      concept_id: params.center_concept_id,
      max_depth: params.depth || 2,
      relationship_types: params.relationship_types,
    });

    // Transform the /query/related response to SubgraphResponse format
    // The response has: { concept_id, max_depth, count, results: [...] }
    // We need to convert it to { nodes, links }

    const relatedConcepts = response.data.results || [];

    // Fetch the center concept details
    const centerResponse = await this.client.get(`/query/concept/${params.center_concept_id}`);
    const centerConcept = centerResponse.data;

    // Build nodes array
    const nodes = [
      {
        concept_id: centerConcept.concept_id,
        label: centerConcept.label,
        ontology: 'default', // We'll need to add ontology info
        search_terms: centerConcept.search_terms || [],
      },
      ...relatedConcepts.map((rc: any) => ({
        concept_id: rc.concept_id,
        label: rc.label,
        ontology: 'default',
        search_terms: [],
      })),
    ];

    // Build links array from relationships in center concept
    const links = centerConcept.relationships?.map((rel: any) => ({
      from_id: centerConcept.concept_id,
      to_id: rel.to_id,
      relationship_type: rel.rel_type,
      confidence: rel.confidence,
    })) || [];

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
   * Get concept details
   */
  async getConceptDetails(concept_id: string): Promise<any> {
    const response = await this.client.get(`/query/concept/${concept_id}`);
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new APIClient();
