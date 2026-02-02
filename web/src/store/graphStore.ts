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
  visibleEdgeCategories: Set<string>; // Track which edge categories are visible
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

  // Graph data (raw API format - cached to avoid re-fetching)
  rawGraphData: { nodes: any[]; links: any[] } | null;
  setRawGraphData: (data: { nodes: any[]; links: any[] } | null) => void;
  // Merge new data into existing graph (deduplicating nodes by concept_id, links by from+type+to)
  mergeRawGraphData: (data: { nodes: any[]; links: any[] }) => void;

  // Graph data (transformed for current explorer)
  graphData: GraphData | null;
  setGraphData: (data: GraphData | null) => void;

  // Filters
  filters: GraphFilters;
  setFilters: (filters: Partial<GraphFilters>) => void;
  resetFilters: () => void;
  toggleEdgeCategoryVisibility: (category: string) => void;
  setAllEdgeCategoriesVisible: (categories: string[], visible: boolean) => void;

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
  destinationNodeId: string | null; // The target node for path analysis
  navigationHistory: string[]; // Stack of previous focused nodes
  historyIndex: number; // Current position in history
  setOriginNodeId: (nodeId: string | null) => void;
  setDestinationNodeId: (nodeId: string | null) => void;
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

  // Block builder expanded state
  blockBuilderExpanded: boolean;
  setBlockBuilderExpanded: (expanded: boolean) => void;

  // Polarity Explorer state (ADR-070)
  polarityState: {
    selectedPositivePole: { concept_id: string; label: string; description?: string } | null;
    selectedNegativePole: { concept_id: string; label: string; description?: string } | null;
    analysisHistory: Array<{
      id: string;
      timestamp: number;
      positivePoleLabel: string;
      negativePoleLabel: string;
      result: any; // PolarityAxisResponse type
    }>;
    selectedAnalysisId: string | null;
    maxCandidates: number;
    maxHops: number;
    minSimilarity: number; // Similarity threshold for pole search
    autoDiscover: boolean;
    activeTab: string;
  };
  setPolarityState: (state: Partial<GraphStore['polarityState']>) => void;
  addPolarityAnalysis: (analysis: GraphStore['polarityState']['analysisHistory'][0]) => void;
  removePolarityAnalysis: (id: string) => void;
  clearPolarityHistory: () => void;
}

const defaultFilters: GraphFilters = {
  relationshipTypes: [],
  ontologies: [],
  minConfidence: 0.0,
  visibleEdgeCategories: new Set(), // Start with all visible (empty set = show all)
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

  // Graph data (raw API data - cached)
  rawGraphData: null,
  setRawGraphData: (data) => set({ rawGraphData: data }),
  mergeRawGraphData: (data) =>
    set((state) => {
      const current = state.rawGraphData;
      if (!current || !current.nodes || current.nodes.length === 0) {
        return { rawGraphData: data };
      }

      const existingNodeIds = new Set(current.nodes.map((n: any) => n.id || n.concept_id));
      const newNodes = (data.nodes || []).filter(
        (n: any) => !existingNodeIds.has(n.id || n.concept_id)
      );

      const existingLinkKeys = new Set(
        current.links.map((l: any) => {
          const from = l.from_id || l.source?.id || l.source;
          const to = l.to_id || l.target?.id || l.target;
          const type = l.relationship_type || l.type || '';
          return `${from}-${type}-${to}`;
        })
      );
      const newLinks = (data.links || []).filter((l: any) => {
        const from = l.from_id || l.source?.id || l.source;
        const to = l.to_id || l.target?.id || l.target;
        const type = l.relationship_type || l.type || '';
        return !existingLinkKeys.has(`${from}-${type}-${to}`);
      });

      return {
        rawGraphData: {
          nodes: [...current.nodes, ...newNodes],
          links: [...current.links, ...newLinks],
        },
      };
    }),

  // Graph data (transformed)
  graphData: null,
  setGraphData: (data) => set({ graphData: data }),

  // Filters
  filters: defaultFilters,
  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    })),
  resetFilters: () => set({ filters: defaultFilters }),

  // Toggle edge category visibility
  toggleEdgeCategoryVisibility: (category) =>
    set((state) => {
      const newVisible = new Set(state.filters.visibleEdgeCategories);
      if (newVisible.has(category)) {
        newVisible.delete(category);
      } else {
        newVisible.add(category);
      }
      return {
        filters: {
          ...state.filters,
          visibleEdgeCategories: newVisible,
        },
      };
    }),

  // Set all edge categories visible/invisible
  setAllEdgeCategoriesVisible: (categories, visible) =>
    set((state) => ({
      filters: {
        ...state.filters,
        visibleEdgeCategories: visible ? new Set(categories) : new Set(),
      },
    })),

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
  destinationNodeId: null,
  navigationHistory: [],
  historyIndex: -1,
  setOriginNodeId: (nodeId) => set({ originNodeId: nodeId }),
  setDestinationNodeId: (nodeId) => set({ destinationNodeId: nodeId }),

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

  // Block builder expanded
  blockBuilderExpanded: true,
  setBlockBuilderExpanded: (expanded) => set({ blockBuilderExpanded: expanded }),

  // Polarity Explorer state (ADR-070)
  polarityState: {
    selectedPositivePole: null,
    selectedNegativePole: null,
    analysisHistory: [],
    selectedAnalysisId: null,
    maxCandidates: 20,
    maxHops: 3, // Increased from 1 - BFS optimization (ADR-076) makes higher hops practical
    minSimilarity: 0.6, // Similarity threshold for pole search
    autoDiscover: true,
    activeTab: 'search',
  },
  setPolarityState: (newState) =>
    set((state) => ({
      polarityState: { ...state.polarityState, ...newState },
    })),
  addPolarityAnalysis: (analysis) =>
    set((state) => ({
      polarityState: {
        ...state.polarityState,
        analysisHistory: [analysis, ...state.polarityState.analysisHistory],
        selectedAnalysisId: analysis.id,
      },
    })),
  removePolarityAnalysis: (id) =>
    set((state) => {
      const newHistory = state.polarityState.analysisHistory.filter((a) => a.id !== id);
      return {
        polarityState: {
          ...state.polarityState,
          analysisHistory: newHistory,
          // If we're removing the selected analysis, deselect it
          selectedAnalysisId: state.polarityState.selectedAnalysisId === id
            ? null
            : state.polarityState.selectedAnalysisId,
        },
      };
    }),
  clearPolarityHistory: () =>
    set((state) => ({
      polarityState: {
        ...state.polarityState,
        analysisHistory: [],
        selectedAnalysisId: null,
      },
    })),
}));
