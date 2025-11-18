/**
 * Block Diagram Store - Persistence for visual block query diagrams
 *
 * Currently uses localStorage, designed to be swappable with API calls
 * when account-based persistence is implemented.
 */

import { create } from 'zustand';
import type { Node, Edge } from 'reactflow';
import type { BlockData } from '../types/blocks';

// Serializable diagram format
export interface SavedDiagram {
  id: string;
  name: string;
  description?: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  nodes: Node<BlockData>[];
  edges: Edge[];
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
}

interface BlockDiagramStore {
  // Current diagram identity
  currentDiagramId: string | null;
  currentDiagramName: string | null;
  hasUnsavedChanges: boolean;

  // Working canvas state (persists across view switches)
  workingNodes: Node<BlockData>[];
  workingEdges: Edge[];

  // Actions
  setCurrentDiagram: (id: string | null, name: string | null) => void;
  setHasUnsavedChanges: (hasChanges: boolean) => void;
  setWorkingCanvas: (nodes: Node<BlockData>[], edges: Edge[]) => void;
  clearWorkingCanvas: () => void;

  // Persistence operations (localStorage for now, API in future)
  saveDiagram: (name: string, nodes: Node<BlockData>[], edges: Edge[], description?: string) => string;
  loadDiagram: (id: string) => SavedDiagram | null;
  listDiagrams: () => DiagramMetadata[];
  deleteDiagram: (id: string) => boolean;
  renameDiagram: (id: string, newName: string) => boolean;

  // File operations
  exportToFile: (nodes: Node<BlockData>[], edges: Edge[], name: string) => void;
  importFromFile: (file: File) => Promise<SavedDiagram | null>;
}

const STORAGE_KEY_PREFIX = 'kg-block-diagram-';
const DIAGRAMS_LIST_KEY = 'kg-block-diagrams-list';
const CURRENT_VERSION = 1;

// Helper to generate unique IDs
const generateId = () => `diagram-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Helper to get diagrams list from localStorage
const getDiagramsList = (): string[] => {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem(DIAGRAMS_LIST_KEY);
  return stored ? JSON.parse(stored) : [];
};

// Helper to update diagrams list
const updateDiagramsList = (ids: string[]) => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(DIAGRAMS_LIST_KEY, JSON.stringify(ids));
};

export const useBlockDiagramStore = create<BlockDiagramStore>((set, get) => ({
  currentDiagramId: null,
  currentDiagramName: null,
  hasUnsavedChanges: false,
  workingNodes: [],
  workingEdges: [],

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

  saveDiagram: (name, nodes, edges, description) => {
    if (typeof window === 'undefined') return '';

    const { currentDiagramId } = get();
    const now = new Date().toISOString();

    // Check if we're updating existing or creating new
    let id = currentDiagramId;
    let createdAt = now;

    if (id) {
      // Load existing to preserve createdAt
      const existing = localStorage.getItem(STORAGE_KEY_PREFIX + id);
      if (existing) {
        const parsed = JSON.parse(existing);
        createdAt = parsed.createdAt;
      }
    } else {
      id = generateId();
    }

    const diagram: SavedDiagram = {
      id,
      name,
      description,
      version: CURRENT_VERSION,
      createdAt,
      updatedAt: now,
      nodes,
      edges,
    };

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY_PREFIX + id, JSON.stringify(diagram));

    // Update diagrams list if new
    const list = getDiagramsList();
    if (!list.includes(id)) {
      list.unshift(id); // Add to front (most recent first)
      updateDiagramsList(list);
    }

    // Update current state
    set({ currentDiagramId: id, currentDiagramName: name, hasUnsavedChanges: false });

    return id;
  },

  loadDiagram: (id) => {
    if (typeof window === 'undefined') return null;

    const stored = localStorage.getItem(STORAGE_KEY_PREFIX + id);
    if (!stored) return null;

    try {
      const diagram = JSON.parse(stored) as SavedDiagram;
      set({ currentDiagramId: id, currentDiagramName: diagram.name, hasUnsavedChanges: false });
      return diagram;
    } catch {
      return null;
    }
  },

  listDiagrams: () => {
    if (typeof window === 'undefined') return [];

    const ids = getDiagramsList();
    const diagrams: DiagramMetadata[] = [];

    for (const id of ids) {
      const stored = localStorage.getItem(STORAGE_KEY_PREFIX + id);
      if (stored) {
        try {
          const diagram = JSON.parse(stored) as SavedDiagram;
          diagrams.push({
            id: diagram.id,
            name: diagram.name,
            description: diagram.description,
            createdAt: diagram.createdAt,
            updatedAt: diagram.updatedAt,
            nodeCount: diagram.nodes.length,
            edgeCount: diagram.edges.length,
          });
        } catch {
          // Skip invalid entries
        }
      }
    }

    return diagrams;
  },

  deleteDiagram: (id) => {
    if (typeof window === 'undefined') return false;

    localStorage.removeItem(STORAGE_KEY_PREFIX + id);

    const list = getDiagramsList().filter(diagId => diagId !== id);
    updateDiagramsList(list);

    // Clear current if we deleted the active diagram
    const { currentDiagramId } = get();
    if (currentDiagramId === id) {
      set({ currentDiagramId: null, currentDiagramName: null, hasUnsavedChanges: false });
    }

    return true;
  },

  renameDiagram: (id, newName) => {
    if (typeof window === 'undefined') return false;

    const stored = localStorage.getItem(STORAGE_KEY_PREFIX + id);
    if (!stored) return false;

    try {
      const diagram = JSON.parse(stored) as SavedDiagram;
      diagram.name = newName;
      diagram.updatedAt = new Date().toISOString();
      localStorage.setItem(STORAGE_KEY_PREFIX + id, JSON.stringify(diagram));

      // Update current name if this is the active diagram
      const { currentDiagramId } = get();
      if (currentDiagramId === id) {
        set({ currentDiagramName: newName });
      }

      return true;
    } catch {
      return false;
    }
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
            id: generateId(),
            name: imported.name || file.name.replace('.json', ''),
            description: imported.description,
            version: imported.version || CURRENT_VERSION,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            nodes: imported.nodes,
            edges: imported.edges,
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
}));
