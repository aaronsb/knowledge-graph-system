/**
 * REST API Client
 *
 * Communicates with the Knowledge Graph System API at localhost:8000
 * Automatically includes OAuth Bearer token in requests
 */

import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import type { SubgraphResponse } from '../types/graph';
import { getAuthState } from '../lib/auth/oauth-utils';

// API configuration - runtime config takes precedence over build-time env vars
// This enables CDN deployment without rebuilding
const API_BASE_URL = window.APP_CONFIG?.apiUrl || import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

    // Add auth interceptor to automatically include Bearer token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const authState = getAuthState();
        if (authState && authState.access_token) {
          config.headers.Authorization = `Bearer ${authState.access_token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );
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
    // ADR-065: Epistemic status filtering
    include_epistemic_status?: string[];
    exclude_epistemic_status?: string[];
  }): Promise<SubgraphResponse> {
    // Step 1: Fetch related concepts
    const response = await this.client.post<any>('/query/related', {
      concept_id: params.center_concept_id,
      max_depth: params.depth || 1, // Use depth 1 for better performance
      relationship_types: params.relationship_types,
      // ADR-065: Epistemic status filtering
      include_epistemic_status: params.include_epistemic_status,
      exclude_epistemic_status: params.exclude_epistemic_status,
    });

    const relatedConcepts = response.data.results || [];

    // Step 2: Collect all concept IDs (center + related)
    const allConceptIds = [
      params.center_concept_id,
      ...relatedConcepts.map((rc: any) => rc.concept_id)
    ];

    // Step 3: Fetch details for all concepts in parallel (with grounding)
    const conceptDetailsPromises = allConceptIds.map(id =>
      this.client.get(`/query/concept/${id}`, {
        params: { include_grounding: true }
      }).then(r => r.data).catch(() => null)
    );

    const allConceptDetails = (await Promise.all(conceptDetailsPromises)).filter(Boolean);

    // Step 4: Build nodes array (with grounding strength)
    const nodes = allConceptDetails.map((concept: any) => ({
      concept_id: concept.concept_id,
      label: concept.label,
      ontology: concept.documents?.[0] || 'Unknown', // Use first document as ontology
      search_terms: concept.search_terms || [],
      grounding_strength: concept.grounding_strength, // -1.0 to +1.0
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
                // ADR-065: Vocabulary epistemic status metadata
                category: rel.category,
                avg_grounding: rel.avg_grounding,
                epistemic_status: rel.epistemic_status,
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
    const response = await this.client.get(`/query/concept/${concept_id}`, {
      params: {
        include_grounding: true,
        include_diversity: true,
        diversity_max_hops: 2
      }
    });
    return response.data;
  }

  /**
   * Find paths between two concepts using exact concept IDs
   * No embedding generation needed - uses stored graph structure
   */
  async findConnection(params: {
    from_id: string;
    to_id: string;
    max_hops?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/connect', params, {
      timeout: 120000, // 2 minutes for complex path searches
    });
    return response.data;
  }

  /**
   * Find paths between two concepts using semantic phrase matching
   * Generates embeddings for text queries - use findConnection() if you already have concept IDs
   * Note: Path searches can be slow - uses extended 120s timeout
   */
  async findConnectionBySearch(params: {
    from_query: string;
    to_query: string;
    max_hops?: number;
    threshold?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/connect-by-search', params, {
      timeout: 120000, // 2 minutes for complex path searches
    });
    return response.data;
  }

  /**
   * Execute a raw openCypher query
   * For advanced users who want full control over graph queries
   */
  async executeCypherQuery(params: {
    query: string;
    limit?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/cypher', params, {
      timeout: 60000, // 1 minute timeout for custom queries
    });
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

  /**
   * Get vocabulary types with categories and confidence scores
   */
  async getVocabularyTypes(params?: {
    include_inactive?: boolean;
    include_builtin?: boolean;
  }): Promise<any> {
    const response = await this.client.get('/vocabulary/types', {
      params: {
        include_inactive: params?.include_inactive ?? false,
        include_builtin: params?.include_builtin ?? true,
      },
    });
    return response.data;
  }

  /**
   * Refresh vocabulary category assignments
   * Recomputes probabilistic categories based on embeddings
   */
  async refreshVocabularyCategories(params?: {
    only_computed?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/refresh-categories', {
      only_computed: params?.only_computed ?? true,
    });
    return response.data;
  }

  /**
   * Get image for a source node (ADR-057)
   * @param sourceId - Source ID from concept instance
   * @returns Image URL (blob URL for display)
   */
  async getSourceImageUrl(sourceId: string): Promise<string> {
    const response = await this.client.get(`/sources/${sourceId}/image`, {
      responseType: 'blob',
    });
    // Create blob URL for display in <img> tags
    return URL.createObjectURL(response.data);
  }

  /**
   * Search source text passages using embeddings (ADR-068 Phase 5)
   * Searches source document chunks directly, not concepts
   */
  async searchSources(params: {
    query: string;
    limit?: number;
    min_similarity?: number;
    ontology?: string;
    include_concepts?: boolean;
    include_full_text?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/query/sources/search', params);
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new APIClient();
