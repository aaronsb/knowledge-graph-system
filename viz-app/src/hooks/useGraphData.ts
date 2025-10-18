/**
 * React Query Hooks for Graph Data
 *
 * Provides hooks for fetching and managing graph data with caching,
 * loading states, and automatic refetching.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { transformForD3 } from '../utils/graphTransform';

/**
 * Fetch subgraph centered on a concept
 */
export function useSubgraph(
  conceptId: string | null,
  options?: {
    depth?: number;
    relationshipTypes?: string[];
    limit?: number;
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: ['subgraph', conceptId, options?.depth, options?.relationshipTypes, options?.limit],
    queryFn: async () => {
      if (!conceptId) throw new Error('Concept ID is required');

      const response = await apiClient.getSubgraph({
        center_concept_id: conceptId,
        depth: options?.depth,
        relationship_types: options?.relationshipTypes,
        limit: options?.limit,
      });

      // Transform API data to D3 format
      return transformForD3(response.nodes, response.links);
    },
    enabled: options?.enabled !== false && !!conceptId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Search concepts by query
 */
export function useSearchConcepts(
  query: string,
  options?: {
    limit?: number;
    minSimilarity?: number;
    offset?: number;
    enabled?: boolean;
    minQueryLength?: number;
  }
) {
  const minLength = options?.minQueryLength ?? 3; // Default: require 3+ characters
  const trimmedQuery = query?.trim() || '';
  const hasMinLength = trimmedQuery.length >= minLength;

  return useQuery({
    queryKey: ['search', query, options?.limit, options?.minSimilarity, options?.offset],
    queryFn: async () => {
      if (!hasMinLength) {
        return { results: [], total: 0 };
      }

      return await apiClient.searchConcepts({
        query: trimmedQuery,
        limit: options?.limit,
        min_similarity: options?.minSimilarity,
        offset: options?.offset,
      });
    },
    enabled: options?.enabled !== false && hasMinLength,
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchOnWindowFocus: false, // Don't refetch when user switches browser tabs
    refetchOnReconnect: false, // Don't refetch on network reconnect
  });
}

/**
 * Get concept details
 */
export function useConceptDetails(conceptId: string | null, enabled = true) {
  return useQuery({
    queryKey: ['concept', conceptId],
    queryFn: async () => {
      if (!conceptId) throw new Error('Concept ID is required');
      return await apiClient.getConceptDetails(conceptId);
    },
    enabled: enabled && !!conceptId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Find path between two concepts
 */
export function useFindPath(
  fromId: string | null,
  toId: string | null,
  options?: {
    maxHops?: number;
    algorithm?: 'shortest' | 'all_simple' | 'weighted';
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: ['path', fromId, toId, options?.maxHops, options?.algorithm],
    queryFn: async () => {
      if (!fromId || !toId) throw new Error('Both concept IDs are required');

      const response = await apiClient.findPath({
        from_id: fromId,
        to_id: toId,
        max_hops: options?.maxHops,
        algorithm: options?.algorithm,
      });

      // Transform paths to graph format
      if (response.paths && response.paths.length > 0) {
        const allNodes = new Map();
        const allLinks: any[] = [];

        response.paths.forEach((path: any) => {
          path.nodes.forEach((node: any) => {
            allNodes.set(node.concept_id, node);
          });
          path.edges.forEach((edge: any) => {
            allLinks.push(edge);
          });
        });

        return transformForD3(Array.from(allNodes.values()), allLinks);
      }

      return { nodes: [], links: [] };
    },
    enabled: options?.enabled !== false && !!fromId && !!toId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Compare two ontologies
 */
export function useCompareOntologies(
  ontologyA: string | null,
  ontologyB: string | null,
  enabled = true
) {
  return useQuery({
    queryKey: ['compare', ontologyA, ontologyB],
    queryFn: async () => {
      if (!ontologyA || !ontologyB) {
        throw new Error('Both ontology names are required');
      }

      return await apiClient.compareOntologies({
        ontology_a: ontologyA,
        ontology_b: ontologyB,
      });
    },
    enabled: enabled && !!ontologyA && !!ontologyB,
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

/**
 * Get graph timeline
 */
export function useTimeline(
  ontology: string | null,
  options?: {
    startDate?: string;
    endDate?: string;
    granularity?: 'day' | 'week' | 'month';
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: ['timeline', ontology, options?.startDate, options?.endDate, options?.granularity],
    queryFn: async () => {
      if (!ontology) throw new Error('Ontology name is required');

      return await apiClient.getTimeline({
        ontology,
        start_date: options?.startDate,
        end_date: options?.endDate,
        granularity: options?.granularity,
      });
    },
    enabled: options?.enabled !== false && !!ontology,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Prefetch subgraph for a concept
 * Useful for preloading data when hovering over nodes
 */
export function usePrefetchSubgraph() {
  const queryClient = useQueryClient();

  return (conceptId: string, depth = 1) => {
    queryClient.prefetchQuery({
      queryKey: ['subgraph', conceptId, depth],
      queryFn: async () => {
        const response = await apiClient.getSubgraph({
          center_concept_id: conceptId,
          depth,
        });
        return transformForD3(response.nodes, response.links);
      },
      staleTime: 5 * 60 * 1000,
    });
  };
}
