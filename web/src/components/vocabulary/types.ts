/**
 * Types for Vocabulary Explorer components (ADR-077)
 */

export interface EdgeTypeData {
  relationship_type: string;
  category: string;
  edge_count: number;
  is_builtin: boolean;
  is_active: boolean;
  category_confidence?: number;
  category_ambiguous?: boolean;
  epistemic_status?: string;
  avg_grounding?: number;
}

export interface CategoryStats {
  category: string;
  totalTypes: number;
  activeTypes: number;
  totalEdges: number;
  builtinTypes: number;
  customTypes: number;
}

export interface CategoryFlow {
  source: string;
  target: string;
  count: number;
}

export interface VocabularyStats {
  totalTypes: number;
  activeTypes: number;
  builtinTypes: number;
  customTypes: number;
  totalEdges: number;
  categories: CategoryStats[];
  edgeTypes: EdgeTypeData[];
}

export type ViewMode = 'chord' | 'radial' | 'matrix';
