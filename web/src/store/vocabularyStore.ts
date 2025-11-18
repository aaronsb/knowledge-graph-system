/**
 * Vocabulary Store - Relationship Type Categories
 *
 * Manages vocabulary metadata including relationship categories,
 * confidence scores, and color mappings.
 */

import { create } from 'zustand';

export interface VocabularyType {
  relationship_type: string;
  category: string;
  category_confidence: number;
  category_ambiguous: boolean;
  is_active: boolean;
  edge_count: number;
}

interface VocabularyStore {
  // Vocabulary data
  types: VocabularyType[];
  typesMap: Map<string, VocabularyType>; // relationship_type -> metadata

  // Loading state
  isLoading: boolean;
  error: string | null;
  lastFetched: Date | null;

  // Actions
  setTypes: (types: VocabularyType[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Helpers
  getCategory: (relationshipType: string) => string | null;
  getConfidence: (relationshipType: string) => number | null;
  isAmbiguous: (relationshipType: string) => boolean;
}

export const useVocabularyStore = create<VocabularyStore>((set, get) => ({
  // Initial state
  types: [],
  typesMap: new Map(),
  isLoading: false,
  error: null,
  lastFetched: null,

  // Actions
  setTypes: (types) => {
    const typesMap = new Map(
      types.map(type => [type.relationship_type, type])
    );
    set({
      types,
      typesMap,
      lastFetched: new Date(),
      error: null,
    });
  },

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error, isLoading: false }),

  // Helpers
  getCategory: (relationshipType) => {
    // Try exact match first
    let type = get().typesMap.get(relationshipType);

    // If not found, try case-insensitive match
    if (!type && relationshipType) {
      const lowerType = relationshipType.toLowerCase();
      for (const [key, value] of get().typesMap.entries()) {
        if (key.toLowerCase() === lowerType) {
          type = value;
          break;
        }
      }
    }

    return type?.category ?? null;
  },

  getConfidence: (relationshipType) => {
    // Try exact match first
    let type = get().typesMap.get(relationshipType);

    // If not found, try case-insensitive match
    if (!type && relationshipType) {
      const lowerType = relationshipType.toLowerCase();
      for (const [key, value] of get().typesMap.entries()) {
        if (key.toLowerCase() === lowerType) {
          type = value;
          break;
        }
      }
    }

    return type?.category_confidence ?? null;
  },

  isAmbiguous: (relationshipType) => {
    // Try exact match first
    let type = get().typesMap.get(relationshipType);

    // If not found, try case-insensitive match
    if (!type && relationshipType) {
      const lowerType = relationshipType.toLowerCase();
      for (const [key, value] of get().typesMap.entries()) {
        if (key.toLowerCase() === lowerType) {
          type = value;
          break;
        }
      }
    }

    return type?.category_ambiguous ?? false;
  },
}));
