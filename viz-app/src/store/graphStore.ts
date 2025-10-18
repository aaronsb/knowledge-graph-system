/**
 * Graph Store - Zustand State Management
 *
 * Manages application state for graph visualization including:
 * - Selected explorer type
 * - Graph data and filters
 * - UI settings
 * - Node/edge selection
 */

import { create } from 'zustand';
import type { VisualizationType } from '../types/explorer';
import type { GraphData } from '../types/graph';

interface GraphFilters {
  relationshipTypes: string[];
  ontologies: string[];
  minConfidence: number;
}

interface UISettings {
  showLabels: boolean;
  showLegend: boolean;
  darkMode: boolean;
  highlightNeighbors: boolean;
}

// Search parameters - describes WHAT to query, not HOW to query it
// SearchBar sets these, App.tsx reacts to them
export type SearchMode = 'concept' | 'neighborhood' | 'path' | null;
export type QueryMode = 'smart-search' | 'block-builder' | 'cypher-editor';

export interface SearchParams {
  mode: SearchMode;

  // Concept mode
  conceptId?: string;

  // Neighborhood mode
  centerConceptId?: string;
  depth?: number; // Also used for path enrichment

  // Path mode
  fromConceptId?: string;
  toConceptId?: string;
  maxHops?: number;

  // Shared parameters
  loadMode?: 'clean' | 'add'; // Replace graph or add to existing
}

interface GraphStore {
  // Explorer selection
  selectedExplorer: VisualizationType;
  setSelectedExplorer: (type: VisualizationType) => void;

  // Graph data
  graphData: GraphData | null;
  setGraphData: (data: GraphData | null) => void;

  // Filters
  filters: GraphFilters;
  setFilters: (filters: Partial<GraphFilters>) => void;
  resetFilters: () => void;

  // Selection state
  selectedNodes: Set<string>;
  selectedEdges: Set<string>;
  setSelectedNodes: (nodes: string[]) => void;
  setSelectedEdges: (edges: string[]) => void;
  clearSelection: () => void;

  // Focused node (center of exploration)
  focusedNodeId: string | null;
  setFocusedNodeId: (nodeId: string | null) => void;

  // Navigation history ("You Are Here" feature)
  originNodeId: string | null; // The node that was clicked to get here
  navigationHistory: string[]; // Stack of previous focused nodes
  historyIndex: number; // Current position in history
  setOriginNodeId: (nodeId: string | null) => void;
  navigateToNode: (nodeId: string) => void; // Updates focus + history
  navigateBack: () => void;
  navigateForward: () => void;

  // UI settings
  uiSettings: UISettings;
  setUISettings: (settings: Partial<UISettings>) => void;
  toggleDarkMode: () => void;

  // Search query state
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // Search parameters
  similarityThreshold: number; // 0.0 - 1.0, used for Follow Concept and searches
  setSimilarityThreshold: (threshold: number) => void;

  // Search params - what to query (SearchBar sets these, App.tsx reacts)
  searchParams: SearchParams;
  setSearchParams: (params: SearchParams) => void;
  clearSearchParams: () => void;

  // Query mode - UI mode for querying (smart-search, block-builder, cypher-editor)
  queryMode: QueryMode;
  setQueryMode: (mode: QueryMode) => void;
}

const defaultFilters: GraphFilters = {
  relationshipTypes: [],
  ontologies: [],
  minConfidence: 0.0,
};

const defaultUISettings: UISettings = {
  showLabels: true,
  showLegend: true,
  darkMode: false,
  highlightNeighbors: true,
};

const defaultSearchParams: SearchParams = {
  mode: null,
  loadMode: 'clean',
};

export const useGraphStore = create<GraphStore>((set) => ({
  // Explorer selection
  selectedExplorer: 'force-2d',
  setSelectedExplorer: (type) => set({ selectedExplorer: type }),

  // Graph data
  graphData: null,
  setGraphData: (data) => set({ graphData: data }),

  // Filters
  filters: defaultFilters,
  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    })),
  resetFilters: () => set({ filters: defaultFilters }),

  // Selection state
  selectedNodes: new Set(),
  selectedEdges: new Set(),
  setSelectedNodes: (nodes) => set({ selectedNodes: new Set(nodes) }),
  setSelectedEdges: (edges) => set({ selectedEdges: new Set(edges) }),
  clearSelection: () =>
    set({ selectedNodes: new Set(), selectedEdges: new Set() }),

  // Focused node
  focusedNodeId: null,
  setFocusedNodeId: (nodeId) => set({ focusedNodeId: nodeId }),

  // Navigation history
  originNodeId: null,
  navigationHistory: [],
  historyIndex: -1,
  setOriginNodeId: (nodeId) => set({ originNodeId: nodeId }),

  navigateToNode: (nodeId) =>
    set((state) => {
      // Truncate forward history and add new entry
      const newHistory = state.navigationHistory.slice(0, state.historyIndex + 1);
      newHistory.push(nodeId);
      return {
        focusedNodeId: nodeId,
        originNodeId: nodeId,
        navigationHistory: newHistory,
        historyIndex: newHistory.length - 1,
      };
    }),

  navigateBack: () =>
    set((state) => {
      if (state.historyIndex > 0) {
        const newIndex = state.historyIndex - 1;
        const nodeId = state.navigationHistory[newIndex];
        return {
          focusedNodeId: nodeId,
          historyIndex: newIndex,
        };
      }
      return state;
    }),

  navigateForward: () =>
    set((state) => {
      if (state.historyIndex < state.navigationHistory.length - 1) {
        const newIndex = state.historyIndex + 1;
        const nodeId = state.navigationHistory[newIndex];
        return {
          focusedNodeId: nodeId,
          historyIndex: newIndex,
        };
      }
      return state;
    }),

  // UI settings
  uiSettings: defaultUISettings,
  setUISettings: (newSettings) =>
    set((state) => ({
      uiSettings: { ...state.uiSettings, ...newSettings },
    })),
  toggleDarkMode: () =>
    set((state) => ({
      uiSettings: {
        ...state.uiSettings,
        darkMode: !state.uiSettings.darkMode,
      },
    })),

  // Search query
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  // Search parameters
  similarityThreshold: 0.5, // Default to 50%
  setSimilarityThreshold: (threshold) => set({ similarityThreshold: threshold }),

  // Search params
  searchParams: defaultSearchParams,
  setSearchParams: (params) => set({ searchParams: params }),
  clearSearchParams: () => set({ searchParams: defaultSearchParams }),

  // Query mode
  queryMode: 'smart-search',
  setQueryMode: (mode) => set({ queryMode: mode }),
}));
