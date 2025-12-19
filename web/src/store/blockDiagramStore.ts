/**
 * Block Diagram Store - Persistence for visual block query diagrams (ADR-083)
 *
 * Uses query_definitions API for persistence with localStorage as cache/fallback.
 * Designed for account-based persistence with offline support.
 */

import { create } from 'zustand';
import type { Node, Edge } from 'reactflow';
import type { BlockData } from '../types/blocks';
import { apiClient } from '../api/client';

// Serializable diagram format
export interface SavedDiagram {
  id: string;  // API uses number, but we store as string for compatibility
  name: string;
  description?: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  nodes: Node<BlockData>[];
  edges: Edge[];
  // API-specific fields
  queryDefinitionId?: number;
  isSynced?: boolean;
}

// Metadata for listing (without full node/edge data)
export interface DiagramMetadata {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  nodeCount: number;
  edgeCount: number;
  queryDefinitionId?: number;
  isSynced?: boolean;
}

interface BlockDiagramStore {
  // Current diagram identity
  currentDiagramId: string | null;
  currentDiagramName: string | null;
  hasUnsavedChanges: boolean;

  // Working canvas state (persists across view switches)
  workingNodes: Node<BlockData>[];
  workingEdges: Edge[];

  // Diagrams cache
  diagrams: DiagramMetadata[];
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentDiagram: (id: string | null, name: string | null) => void;
  setHasUnsavedChanges: (hasChanges: boolean) => void;
  setWorkingCanvas: (nodes: Node<BlockData>[], edges: Edge[]) => void;
  clearWorkingCanvas: () => void;

  // Persistence operations (async, API-first with localStorage fallback)
  saveDiagram: (name: string, nodes: Node<BlockData>[], edges: Edge[], description?: string, forceNew?: boolean) => Promise<string>;
  loadDiagram: (id: string) => Promise<SavedDiagram | null>;
  listDiagrams: () => Promise<DiagramMetadata[]>;
  deleteDiagram: (id: string) => Promise<boolean>;
  renameDiagram: (id: string, newName: string) => Promise<boolean>;

  // Synchronous versions for backward compatibility (use cache)
  listDiagramsSync: () => DiagramMetadata[];

  // File operations
  exportToFile: (nodes: Node<BlockData>[], edges: Edge[], name: string) => void;
  importFromFile: (file: File) => Promise<SavedDiagram | null>;

  // Migration
  migrateFromLocalStorage: () => Promise<number>;
}

const STORAGE_KEY_PREFIX = 'kg-block-diagram-';
const DIAGRAMS_LIST_KEY = 'kg-block-diagrams-list';
const CURRENT_VERSION = 1;

// Helper to generate unique IDs (for local-only diagrams)
const generateLocalId = () => `local-diagram-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Helper to get diagrams list from localStorage
const getLocalDiagramsList = (): string[] => {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem(DIAGRAMS_LIST_KEY);
  return stored ? JSON.parse(stored) : [];
};

// Helper to update diagrams list in localStorage
const updateLocalDiagramsList = (ids: string[]) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(DIAGRAMS_LIST_KEY, JSON.stringify(ids));
};

// Helper to save diagram to localStorage
const saveToLocalStorage = (diagram: SavedDiagram) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_PREFIX + diagram.id, JSON.stringify(diagram));
  const list = getLocalDiagramsList();
  if (!list.includes(diagram.id)) {
    list.unshift(diagram.id);
    updateLocalDiagramsList(list);
  }
};

// Helper to load diagram from localStorage
const loadFromLocalStorage = (id: string): SavedDiagram | null => {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(STORAGE_KEY_PREFIX + id);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as SavedDiagram;
  } catch {
    return null;
  }
};

// Helper to delete from localStorage
const deleteFromLocalStorage = (id: string) => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY_PREFIX + id);
  const list = getLocalDiagramsList().filter(diagId => diagId !== id);
  updateLocalDiagramsList(list);
};

export const useBlockDiagramStore = create<BlockDiagramStore>((set, get) => ({
  currentDiagramId: null,
  currentDiagramName: null,
  hasUnsavedChanges: false,
  workingNodes: [],
  workingEdges: [],
  diagrams: [],
  isLoading: false,
  error: null,

  setCurrentDiagram: (id, name) => {
    set({ currentDiagramId: id, currentDiagramName: name, hasUnsavedChanges: false });
  },

  setHasUnsavedChanges: (hasChanges) => {
    set({ hasUnsavedChanges: hasChanges });
  },

  setWorkingCanvas: (nodes, edges) => {
    set({ workingNodes: nodes, workingEdges: edges });
  },

  clearWorkingCanvas: () => {
    set({
      workingNodes: [],
      workingEdges: [],
      currentDiagramId: null,
      currentDiagramName: null,
      hasUnsavedChanges: false
    });
  },

  saveDiagram: async (name, nodes, edges, description, forceNew = false) => {
    const { currentDiagramId } = get();
    const now = new Date().toISOString();

    // Determine if updating or creating
    let existingDiagram: SavedDiagram | null = null;
    if (!forceNew && currentDiagramId) {
      existingDiagram = await get().loadDiagram(currentDiagramId);
    }

    try {
      // Try API first
      if (existingDiagram?.queryDefinitionId) {
        // Update existing query definition
        const updated = await apiClient.updateQueryDefinition(
          existingDiagram.queryDefinitionId,
          {
            name,
            definition: { nodes, edges, version: CURRENT_VERSION },
            metadata: { description, nodeCount: nodes.length, edgeCount: edges.length },
          }
        );

        const diagram: SavedDiagram = {
          id: currentDiagramId!,
          name: updated.name,
          description,
          version: CURRENT_VERSION,
          createdAt: existingDiagram.createdAt,
          updatedAt: updated.updated_at,
          nodes,
          edges,
          queryDefinitionId: updated.id,
          isSynced: true,
        };

        saveToLocalStorage(diagram);
        set({ currentDiagramId: diagram.id, currentDiagramName: name, hasUnsavedChanges: false });
        await get().listDiagrams(); // Refresh list
        return diagram.id;
      } else {
        // Create new query definition
        const created = await apiClient.createQueryDefinition({
          name,
          definition_type: 'block_diagram',
          definition: { nodes, edges, version: CURRENT_VERSION },
          metadata: { description, nodeCount: nodes.length, edgeCount: edges.length },
        });

        const diagram: SavedDiagram = {
          id: `api-${created.id}`,
          name: created.name,
          description,
          version: CURRENT_VERSION,
          createdAt: created.created_at,
          updatedAt: created.updated_at,
          nodes,
          edges,
          queryDefinitionId: created.id,
          isSynced: true,
        };

        saveToLocalStorage(diagram);
        set({ currentDiagramId: diagram.id, currentDiagramName: name, hasUnsavedChanges: false });
        await get().listDiagrams(); // Refresh list
        return diagram.id;
      }
    } catch (err) {
      console.warn('Failed to save to API, using localStorage:', err);

      // Fallback to localStorage-only
      const id = forceNew ? generateLocalId() : (currentDiagramId || generateLocalId());
      const createdAt = existingDiagram?.createdAt || now;

      const diagram: SavedDiagram = {
        id,
        name,
        description,
        version: CURRENT_VERSION,
        createdAt,
        updatedAt: now,
        nodes,
        edges,
        isSynced: false,
      };

      saveToLocalStorage(diagram);
      set({ currentDiagramId: id, currentDiagramName: name, hasUnsavedChanges: false });
      await get().listDiagrams(); // Refresh list
      return id;
    }
  },

  loadDiagram: async (id) => {
    // Check localStorage cache first
    const cached = loadFromLocalStorage(id);
    if (cached) {
      set({ currentDiagramId: id, currentDiagramName: cached.name, hasUnsavedChanges: false });
      return cached;
    }

    // Try API if it looks like an API ID
    if (id.startsWith('api-')) {
      try {
        const queryDefId = parseInt(id.replace('api-', ''));
        const def = await apiClient.getQueryDefinition(queryDefId);
        const definition = def.definition as { nodes: Node<BlockData>[]; edges: Edge[]; version?: number };

        const diagram: SavedDiagram = {
          id,
          name: def.name,
          description: (def.metadata as any)?.description,
          version: definition.version || CURRENT_VERSION,
          createdAt: def.created_at,
          updatedAt: def.updated_at,
          nodes: definition.nodes,
          edges: definition.edges,
          queryDefinitionId: def.id,
          isSynced: true,
        };

        // Cache in localStorage
        saveToLocalStorage(diagram);
        set({ currentDiagramId: id, currentDiagramName: diagram.name, hasUnsavedChanges: false });
        return diagram;
      } catch (err) {
        console.error('Failed to load diagram from API:', err);
        return null;
      }
    }

    return null;
  },

  listDiagrams: async () => {
    set({ isLoading: true, error: null });

    const diagrams: DiagramMetadata[] = [];

    try {
      // Get API diagrams
      const response = await apiClient.listQueryDefinitions({
        definition_type: 'block_diagram',
        limit: 100,
      });

      for (const def of response.definitions) {
        const meta = def.metadata as { description?: string; nodeCount?: number; edgeCount?: number } | null;
        diagrams.push({
          id: `api-${def.id}`,
          name: def.name,
          description: meta?.description,
          createdAt: def.created_at,
          updatedAt: def.updated_at,
          nodeCount: meta?.nodeCount || 0,
          edgeCount: meta?.edgeCount || 0,
          queryDefinitionId: def.id,
          isSynced: true,
        });
      }
    } catch (err) {
      console.warn('Failed to fetch diagrams from API:', err);
    }

    // Also get local-only diagrams
    const localIds = getLocalDiagramsList();
    for (const id of localIds) {
      // Skip if already in API list
      if (diagrams.some(d => d.id === id)) continue;

      const stored = loadFromLocalStorage(id);
      if (stored && !stored.queryDefinitionId) {
        diagrams.push({
          id: stored.id,
          name: stored.name,
          description: stored.description,
          createdAt: stored.createdAt,
          updatedAt: stored.updatedAt,
          nodeCount: stored.nodes.length,
          edgeCount: stored.edges.length,
          isSynced: false,
        });
      }
    }

    // Sort by updatedAt (most recent first)
    diagrams.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

    set({ diagrams, isLoading: false });
    return diagrams;
  },

  listDiagramsSync: () => {
    return get().diagrams;
  },

  deleteDiagram: async (id) => {
    const diagram = await get().loadDiagram(id);

    // Delete from API if synced
    if (diagram?.queryDefinitionId) {
      try {
        await apiClient.deleteQueryDefinition(diagram.queryDefinitionId);
      } catch (err) {
        console.error('Failed to delete from API:', err);
        return false;
      }
    }

    // Delete from localStorage
    deleteFromLocalStorage(id);

    // Clear current if we deleted the active diagram
    const { currentDiagramId } = get();
    if (currentDiagramId === id) {
      set({ currentDiagramId: null, currentDiagramName: null, hasUnsavedChanges: false });
    }

    await get().listDiagrams(); // Refresh list
    return true;
  },

  renameDiagram: async (id, newName) => {
    const diagram = await get().loadDiagram(id);
    if (!diagram) return false;

    // Update API if synced
    if (diagram.queryDefinitionId) {
      try {
        await apiClient.updateQueryDefinition(diagram.queryDefinitionId, { name: newName });
      } catch (err) {
        console.error('Failed to rename in API:', err);
        return false;
      }
    }

    // Update localStorage
    diagram.name = newName;
    diagram.updatedAt = new Date().toISOString();
    saveToLocalStorage(diagram);

    // Update current name if this is the active diagram
    const { currentDiagramId } = get();
    if (currentDiagramId === id) {
      set({ currentDiagramName: newName });
    }

    await get().listDiagrams(); // Refresh list
    return true;
  },

  exportToFile: (nodes, edges, name) => {
    const diagram: Omit<SavedDiagram, 'id'> = {
      name,
      version: CURRENT_VERSION,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes,
      edges,
    };

    const blob = new Blob([JSON.stringify(diagram, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `${name.replace(/[^a-z0-9]/gi, '-').toLowerCase()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  importFromFile: async (file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const content = e.target?.result as string;
          const imported = JSON.parse(content);

          // Validate structure
          if (!imported.nodes || !Array.isArray(imported.nodes) ||
              !imported.edges || !Array.isArray(imported.edges)) {
            console.error('Invalid diagram file: missing nodes or edges');
            resolve(null);
            return;
          }

          // Create a new diagram from imported data
          const diagram: SavedDiagram = {
            id: generateLocalId(),
            name: imported.name || file.name.replace('.json', ''),
            description: imported.description,
            version: imported.version || CURRENT_VERSION,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            nodes: imported.nodes,
            edges: imported.edges,
            isSynced: false,
          };

          resolve(diagram);
        } catch (error) {
          console.error('Failed to parse diagram file:', error);
          resolve(null);
        }
      };

      reader.onerror = () => {
        console.error('Failed to read file');
        resolve(null);
      };

      reader.readAsText(file);
    });
  },

  migrateFromLocalStorage: async () => {
    const localIds = getLocalDiagramsList();
    let migrated = 0;

    for (const id of localIds) {
      const diagram = loadFromLocalStorage(id);
      if (diagram && !diagram.queryDefinitionId) {
        try {
          // Create in API
          const created = await apiClient.createQueryDefinition({
            name: diagram.name,
            definition_type: 'block_diagram',
            definition: { nodes: diagram.nodes, edges: diagram.edges, version: diagram.version },
            metadata: { description: diagram.description, nodeCount: diagram.nodes.length, edgeCount: diagram.edges.length },
          });

          // Update local record with API ID
          diagram.queryDefinitionId = created.id;
          diagram.isSynced = true;
          saveToLocalStorage(diagram);
          migrated++;
        } catch (err) {
          console.error(`Failed to migrate diagram ${id}:`, err);
        }
      }
    }

    await get().listDiagrams(); // Refresh list
    return migrated;
  },
}));
