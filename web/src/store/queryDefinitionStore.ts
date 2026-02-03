/**
 * Query Definition Store - Zustand State Management (ADR-083)
 *
 * Manages query definitions for reusable saved queries.
 * Query definitions store the parameters needed to regenerate artifacts.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '../api/client';
import type {
  QueryDefinition,
  QueryDefinitionCreateRequest,
} from '../types/artifacts';

/**
 * Query definition store state
 */
interface QueryDefinitionStoreState {
  // Query definitions (keyed by ID for O(1) lookup)
  definitions: Record<number, QueryDefinition>;

  // List of definition IDs in display order
  definitionIds: number[];

  // Loading state
  isLoading: boolean;
  error: string | null;

  // Last fetch timestamp
  lastFetchedAt: string | null;

  // Pagination info
  total: number;
  hasMore: boolean;
}

interface QueryDefinitionStoreActions {
  // Load query definitions from API
  loadDefinitions: (params?: {
    definition_type?: string;
    refresh?: boolean;
    limit?: number;
    offset?: number;
  }) => Promise<void>;

  // Create a new query definition
  createDefinition: (definition: QueryDefinitionCreateRequest) => Promise<QueryDefinition | null>;

  // Update a query definition
  updateDefinition: (
    id: number,
    updates: Partial<QueryDefinitionCreateRequest>
  ) => Promise<QueryDefinition | null>;

  // Delete a query definition
  deleteDefinition: (id: number) => Promise<boolean>;

  // Get definition by ID
  getDefinition: (id: number) => QueryDefinition | null;

  // Clear all definitions (local state only)
  clearDefinitions: () => void;

  // Clear error state
  clearError: () => void;
}

type QueryDefinitionStore = QueryDefinitionStoreState & QueryDefinitionStoreActions;

export const useQueryDefinitionStore = create<QueryDefinitionStore>()(
  persist(
    (set, get) => ({
      // Initial state
      definitions: {},
      definitionIds: [],
      isLoading: false,
      error: null,
      lastFetchedAt: null,
      total: 0,
      hasMore: false,

      // Load definitions from API
      loadDefinitions: async (params) => {
        const { refresh = false, limit = 50, offset = 0, ...filters } = params || {};

        set({ isLoading: true, error: null });

        try {
          const response = await apiClient.listQueryDefinitions({
            ...filters,
            limit,
            offset,
          });

          // Build definitions map
          const newDefinitions: Record<number, QueryDefinition> = {};
          const newIds: number[] = [];

          for (const def of response.definitions) {
            newDefinitions[def.id] = def;
            newIds.push(def.id);
          }

          if (refresh || offset === 0) {
            // Replace definitions
            set({
              definitions: newDefinitions,
              definitionIds: newIds,
              total: response.total,
              hasMore: offset + response.definitions.length < response.total,
              lastFetchedAt: new Date().toISOString(),
              isLoading: false,
            });
          } else {
            // Append for pagination
            const existing = get().definitions;
            const existingIds = get().definitionIds;
            set({
              definitions: { ...existing, ...newDefinitions },
              definitionIds: [...existingIds, ...newIds],
              total: response.total,
              hasMore: offset + response.definitions.length < response.total,
              isLoading: false,
            });
          }
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Failed to load query definitions';
          set({ isLoading: false, error: message });
        }
      },

      // Create definition
      createDefinition: async (definition) => {
        set({ isLoading: true, error: null });

        try {
          const created = await apiClient.createQueryDefinition(definition);

          // Add to store (prepend to show newest first)
          // The create response omits `definition` and `metadata` — merge from the request
          const existing = get().definitions;
          const existingIds = get().definitionIds;
          const full = {
            ...created,
            definition: definition.definition,
            metadata: definition.metadata || null,
            owner_id: null,
          };

          set({
            definitions: { ...existing, [created.id]: full },
            definitionIds: [created.id, ...existingIds],
            total: get().total + 1,
            isLoading: false,
          });

          return full as any;
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Failed to create query definition';
          set({ isLoading: false, error: message });
          return null;
        }
      },

      // Update definition
      updateDefinition: async (id, updates) => {
        try {
          const updated = await apiClient.updateQueryDefinition(id, updates);

          // Update in store
          set({
            definitions: {
              ...get().definitions,
              [id]: updated,
            },
          });

          return updated;
        } catch (e: unknown) {
          const message = e instanceof Error ? e.message : 'Failed to update query definition';
          set({ error: message });
          return null;
        }
      },

      // Delete definition
      deleteDefinition: async (id) => {
        try {
          await apiClient.deleteQueryDefinition(id);

          // Remove from store
          const { [id]: _, ...remaining } = get().definitions;
          const filteredIds = get().definitionIds.filter((defId) => defId !== id);

          set({
            definitions: remaining,
            definitionIds: filteredIds,
            total: get().total - 1,
          });

          return true;
        } catch (e) {
          console.error('Failed to delete query definition:', e);
          return false;
        }
      },

      // Get definition by ID
      getDefinition: (id) => {
        return get().definitions[id] || null;
      },

      // Clear all definitions (local state only)
      clearDefinitions: () => {
        set({
          definitions: {},
          definitionIds: [],
          total: 0,
          hasMore: false,
          lastFetchedAt: null,
        });
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'kg-query-definitions-storage',
      // Only persist data, not loading state
      partialize: (state) => ({
        definitions: state.definitions,
        definitionIds: state.definitionIds,
        lastFetchedAt: state.lastFetchedAt,
        total: state.total,
      }),
    }
  )
);
