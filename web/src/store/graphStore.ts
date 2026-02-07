/**
 * Graph Store - Zustand State Management
 *
 * Manages application state for graph visualization including:
 * - Selected explorer type
 * - Graph data and filters
 * - UI settings
 * - Node/edge selection
 * - Exploration session tracking (ordered Cypher statement log)
 *
 * The exploration session records each graph action as a step with an additive (+)
 * or subtractive (-) operator and its equivalent Cypher statement. This enables:
 * - Persistence across refresh (localStorage)
 * - Saving named explorations as replayable query sets
 * - Exporting to the Cypher editor for viewing/editing
 * - Sharing explorations as copy/pasteable Cypher
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { VisualizationType } from '../types/explorer';
import type { GraphData } from '../types/graph';
import type { RawGraphData, RawGraphNode, RawGraphLink } from '../utils/cypherResultMapper';

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

// Search parameters — parameter-presence model where mode is derived, not declared.
// SearchBar sets these, ExplorerView reacts to them.
/** Active query authoring mode in the search bar.  @verified 7b5be48d */
export type QueryMode = 'smart-search' | 'block-builder' | 'cypher-editor';

/** Parameter-presence model for graph queries; mode is derived, not declared.  @verified 7b5be48d */
export interface SearchParams {
  // Primary concept (always present for any search)
  primaryConceptId?: string;
  primaryConceptLabel?: string;

  // Neighborhood depth (1 = immediate neighbors, >1 = deeper expansion)
  depth: number;

  // Destination concept (presence triggers path mode)
  destinationConceptId?: string;
  destinationConceptLabel?: string;

  // Path parameters (only relevant when destination is set)
  maxHops: number;

  // Load behavior
  loadMode: 'clean' | 'add';
}

/** Derived query mode: idle (no primary), explore (neighborhood), or path (A→B).  @verified 7b5be48d */
export type DerivedMode = 'idle' | 'explore' | 'path';

/** Derive the query mode from which SearchParams fields are populated.  @verified 7b5be48d */
export function deriveMode(params: SearchParams): DerivedMode {
  if (!params.primaryConceptId) return 'idle';
  if (params.destinationConceptId) return 'path';
  return 'explore';
}

// --- Exploration Session Types ---
//
// All query modes (smart search, block editor, Cypher editor) compile to the
// same intermediate representation: an ordered array of { op, cypher } pairs.
// This is the "query program" — saved, loaded, and replayed uniformly.
//
// Smart search generates steps automatically from UI actions.
// Block editor compiles visual blocks into steps.
// Cypher editor lets the user write +/- prefixed statements directly.
// generateCypher() serializes a session to text; parseCypherStatements() parses it back.

/** The type of graph action performed */
export type ExplorationAction = 'explore' | 'follow' | 'add-adjacent' | 'load-path' | 'cypher';

/** Set algebra operator: additive (+) merges results, subtractive (-) removes them */
export type ExplorationOp = '+' | '-';

/**
 * A single step in an exploration session.
 *
 * Each step records one intentional graph action — a discrete thought in the
 * user's exploration sequence. The step includes both the semantic description
 * (action, concept, depth) and the equivalent Cypher statement for replay.
 */
export interface ExplorationStep {
  /** Unique step identifier */
  id: string;
  /** When this step was performed */
  timestamp: number;
  /** What kind of action was taken */
  action: ExplorationAction;
  /** Whether this step adds to or removes from the graph */
  op: ExplorationOp;
  /** The equivalent Cypher statement for this action */
  cypher: string;

  /** Primary concept ID (not applicable for raw cypher steps) */
  conceptId?: string;
  /** Human-readable concept label (or Cypher snippet for raw cypher steps) */
  conceptLabel?: string;
  /** Neighborhood traversal depth */
  depth?: number;

  /** Destination concept ID (path mode only) */
  destinationConceptId?: string;
  /** Destination concept label (path mode only) */
  destinationConceptLabel?: string;
  /** Maximum hops for path search (path mode only) */
  maxHops?: number;
}

/**
 * An exploration session — an ordered list of steps that together define
 * a graph query. The sequence mirrors how the user actually explored.
 * Replay executes steps in order, applying +/- operators.
 */
export interface ExplorationSession {
  /** Unique session identifier */
  id: string;
  /** User-provided name (null until saved) */
  name: string | null;
  /** When the session started */
  createdAt: number;
  /** Ordered list of exploration steps */
  steps: ExplorationStep[];
}

const createEmptySession = (): ExplorationSession => ({
  id: crypto.randomUUID(),
  name: null,
  createdAt: Date.now(),
  steps: [],
});

interface GraphStore {
  // Explorer selection
  selectedExplorer: VisualizationType;
  setSelectedExplorer: (type: VisualizationType) => void;

  // Graph data (raw API format - cached to avoid re-fetching, persisted to localStorage)
  rawGraphData: RawGraphData | null;
  /** Replace raw graph data entirely (clean load) */
  setRawGraphData: (data: RawGraphData | null) => void;
  /** Merge new data into existing graph, deduplicating by concept_id / link key */
  mergeRawGraphData: (data: RawGraphData) => void;
  /** Remove matching nodes and their connected links from the graph (subtractive operator) */
  subtractRawGraphData: (data: RawGraphData) => void;

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
    pendingAnalysis: boolean; // Set by "Send to Polarity" to auto-run on mount
  };
  setPolarityState: (state: Partial<GraphStore['polarityState']>) => void;
  addPolarityAnalysis: (analysis: GraphStore['polarityState']['analysisHistory'][0]) => void;
  removePolarityAnalysis: (id: string) => void;
  clearPolarityHistory: () => void;

  // Exploration session — ordered list of graph actions with +/- operators
  /** Current exploration session (persisted to localStorage) */
  explorationSession: ExplorationSession;
  /** Record a new step in the exploration session */
  addExplorationStep: (step: Omit<ExplorationStep, 'id' | 'timestamp'>) => void;
  /** Remove the last step from the session */
  undoLastStep: () => void;
  /** Clear the session and graph data, starting fresh */
  clearExploration: () => void;
  /** Reset session only (keeps graph data intact) — used when loading saved queries */
  resetExplorationSession: () => void;
  /** Set a name for the current exploration (for saving) */
  setExplorationName: (name: string) => void;

  /** Bridge for pushing generated Cypher scripts to the editor (consumed by SearchBar) */
  cypherEditorContent: string | null;
  setCypherEditorContent: (content: string | null) => void;
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
  depth: 1,
  maxHops: 5,
  loadMode: 'clean',
};

/** Central Zustand store for graph state, exploration session, and UI settings.  @verified 7b5be48d */
export const useGraphStore = create<GraphStore>()(
  persist(
    (set) => ({
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

      const existingNodeIds = new Set(current.nodes.map((n) => n.concept_id));
      const newNodes = (data.nodes || []).filter(
        (n) => !existingNodeIds.has(n.concept_id)
      );

      const existingLinkKeys = new Set(
        current.links.map((l) => `${l.from_id}-${l.relationship_type}-${l.to_id}`)
      );
      const newLinks = (data.links || []).filter((l) => {
        return !existingLinkKeys.has(`${l.from_id}-${l.relationship_type}-${l.to_id}`);
      });

      return {
        rawGraphData: {
          nodes: [...current.nodes, ...newNodes],
          links: [...current.links, ...newLinks],
        },
      };
    }),

  subtractRawGraphData: (data) =>
    set((state) => {
      const current = state.rawGraphData;
      if (!current || !current.nodes || current.nodes.length === 0) {
        return {};
      }

      // Build set of node IDs to remove
      const removeNodeIds = new Set(
        (data.nodes || []).map((n) => n.concept_id)
      );

      // Remove matching nodes
      const remainingNodes = current.nodes.filter(
        (n) => !removeNodeIds.has(n.concept_id)
      );

      // Remove links that reference removed nodes
      const remainingNodeIds = new Set(
        remainingNodes.map((n) => n.concept_id)
      );
      const remainingLinks = current.links.filter((l) => {
        return remainingNodeIds.has(l.from_id) && remainingNodeIds.has(l.to_id);
      });

      return {
        rawGraphData: {
          nodes: remainingNodes,
          links: remainingLinks,
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
    pendingAnalysis: false,
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

  // Exploration session
  explorationSession: createEmptySession(),

  addExplorationStep: (stepData) =>
    set((state) => ({
      explorationSession: {
        ...state.explorationSession,
        steps: [
          ...state.explorationSession.steps,
          {
            ...stepData,
            id: crypto.randomUUID(),
            timestamp: Date.now(),
          },
        ],
      },
    })),

  undoLastStep: () =>
    set((state) => ({
      explorationSession: {
        ...state.explorationSession,
        steps: state.explorationSession.steps.slice(0, -1),
      },
    })),

  clearExploration: () =>
    set({
      explorationSession: createEmptySession(),
      rawGraphData: null,
      graphData: null,
    }),

  resetExplorationSession: () =>
    set({ explorationSession: createEmptySession() }),

  cypherEditorContent: null,
  setCypherEditorContent: (content) => set({ cypherEditorContent: content }),

  setExplorationName: (name) =>
    set((state) => ({
      explorationSession: {
        ...state.explorationSession,
        name,
      },
    })),
    }),
    {
      name: 'kg-graph-exploration',
      partialize: (state) => ({
        rawGraphData: state.rawGraphData,
        explorationSession: state.explorationSession,
        similarityThreshold: state.similarityThreshold,
      }),
    }
  )
);
