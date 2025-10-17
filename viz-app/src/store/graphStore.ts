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

  // UI settings
  uiSettings: UISettings;
  setUISettings: (settings: Partial<UISettings>) => void;
  toggleDarkMode: () => void;

  // Search query state
  searchQuery: string;
  setSearchQuery: (query: string) => void;
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
}));
