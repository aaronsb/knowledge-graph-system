/**
 * React Query Hooks for Graph Data
 *
 * Provides hooks for fetching and managing graph data with caching,
 * loading states, and automatic refetching.
 */

import { useMemo } from 'react';
import { useQuery, useQueries, useQueryClient } from '@tanstack/react-query';
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
    // ADR-065: Epistemic status filtering
    includeEpistemicStatus?: string[];
    excludeEpistemicStatus?: string[];
  }
) {
  return useQuery({
    queryKey: [
      'subgraph',
      conceptId,
      options?.depth,
      options?.relationshipTypes,
      options?.limit,
      options?.includeEpistemicStatus,
      options?.excludeEpistemicStatus,
    ],
    queryFn: async () => {
      if (!conceptId) throw new Error('Concept ID is required');

      const response = await apiClient.getSubgraph({
        center_concept_id: conceptId,
        depth: options?.depth,
        relationship_types: options?.relationshipTypes,
        limit: options?.limit,
        // ADR-065: Epistemic status filtering
        include_epistemic_status: options?.includeEpistemicStatus,
        exclude_epistemic_status: options?.excludeEpistemicStatus,
      });

      // Return raw API data (transformation happens in explorer-specific dataTransformer)
      return { nodes: response.nodes, links: response.links };
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
  const minLength = options?.minQueryLength ?? 2; // Default: require 2+ characters
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
 * Find path between two concepts (uses /viz/graph/path endpoint)
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

        // Return raw API data
        return { nodes: Array.from(allNodes.values()), links: allLinks };
      }

      return { nodes: [], links: [] };
    },
    enabled: options?.enabled !== false && !!fromId && !!toId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Find connection between two concepts (uses /query/connect endpoint)
 * Uses ID-based search - no embedding generation needed
 */
export function useFindConnection(
  fromId: string | null,
  toId: string | null,
  options?: {
    maxHops?: number;
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: ['connection', fromId, toId, options?.maxHops],
    queryFn: async () => {
      if (!fromId || !toId) throw new Error('Both concept IDs are required');

      const response = await apiClient.findConnection({
        from_id: fromId,
        to_id: toId,
        max_hops: options?.maxHops,
      });

      // Convert paths to graph format, filtering to Concept nodes only.
      // graph_accel traverses ALL vertices (Concept, Source, Ontology).
      // Source/Ontology nodes have empty IDs and aren't useful for visualization.
      // We collapse intermediate hops into direct Concept-to-Concept edges.
      if (response.paths && response.paths.length > 0) {
        const allNodes = new Map();
        const linkSet = new Set<string>();
        const allLinks: any[] = [];

        response.paths.forEach((path: any) => {
          // Extract only Concept nodes (non-empty ID)
          const conceptNodes: any[] = [];
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

          // Add Concept nodes
          conceptNodes.forEach((node: any) => {
            if (!allNodes.has(node.id)) {
              allNodes.set(node.id, {
                concept_id: node.id,
                label: node.label,
                description: node.description,
                ontology: 'default',
                grounding_strength: node.grounding_strength,
              });
            }
          });

          // Build edges between consecutive Concept nodes
          for (let i = 0; i < conceptNodes.length - 1; i++) {
            const fromId = conceptNodes[i].id;
            const toId = conceptNodes[i + 1].id;
            // Use the first meaningful relationship type from collapsed hops
            const rels = conceptRelTypes[i + 1];
            const relType = rels.find(r => r !== 'APPEARS' && r !== 'SCOPED_BY') || rels[0] || 'CONNECTED';
            const linkKey = `${fromId}-${relType}-${toId}`;
            if (!linkSet.has(linkKey)) {
              linkSet.add(linkKey);
              allLinks.push({
                from_id: fromId,
                to_id: toId,
                relationship_type: relType,
              });
            }
          }
        });

        return { nodes: Array.from(allNodes.values()), links: allLinks };
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
 * Enrich path nodes with neighborhood context.
 * Fetches subgraphs around each node in parallel and merges results.
 *
 * Performance guards:
 * - Enrichment depth capped at 2
 * - Skipped if more than 50 nodes
 */
export function usePathEnrichment(
  nodeIds: string[],
  depth: number,
  options?: { enabled?: boolean }
) {
  const enrichDepth = Math.min(depth, 2);
  const shouldEnrich =
    options?.enabled !== false &&
    enrichDepth > 0 &&
    nodeIds.length > 0 &&
    nodeIds.length <= 50;

  const queries = useQueries({
    queries: shouldEnrich
      ? nodeIds.map((id) => ({
          queryKey: ['subgraph', id, enrichDepth],
          queryFn: async () => {
            const response = await apiClient.getSubgraph({
              center_concept_id: id,
              depth: enrichDepth,
            });
            return { nodes: response.nodes, links: response.links };
          },
          staleTime: 5 * 60 * 1000,
        }))
      : [],
  });

  const isLoading = queries.some((q) => q.isLoading);
  const isSuccess = queries.length > 0 && queries.every((q) => q.isSuccess);

  // Use dataUpdatedAt timestamps to create a stable memo dependency
  const dataVersion = queries.map((q) => q.dataUpdatedAt).join(',');

  const data = useMemo(() => {
    if (!isSuccess) return null;

    const allNodes = new Map<string, any>();
    const linkKeys = new Set<string>();
    const allLinks: any[] = [];

    queries.forEach((q) => {
      if (q.data) {
        const result = q.data as { nodes: any[]; links: any[] };
        result.nodes.forEach((n: any) => {
          const id = n.concept_id || n.id;
          if (id && !allNodes.has(id)) allNodes.set(id, n);
        });
        result.links.forEach((l: any) => {
          const from = l.from_id || l.source;
          const to = l.to_id || l.target;
          const type = l.relationship_type || l.type || '';
          const key = `${from}-${type}-${to}`;
          if (!linkKeys.has(key)) {
            linkKeys.add(key);
            allLinks.push(l);
          }
        });
      }
    });

    return allNodes.size > 0
      ? { nodes: Array.from(allNodes.values()), links: allLinks }
      : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuccess, dataVersion]);

  return { data, isLoading };
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
