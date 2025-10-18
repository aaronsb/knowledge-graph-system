/**
 * Visual Block Builder - Type Definitions
 *
 * Defines the data structures for the drag-and-drop query builder.
 */

import type { Node } from 'reactflow';

// ============================================================================
// Block Types
// ============================================================================

export type BlockType = 'search' | 'selectConcept' | 'neighborhood' | 'pathTo' | 'filter' | 'limit';

// ============================================================================
// Block Parameters
// ============================================================================

export interface SearchBlockParams {
  query: string;
  similarity: number; // 0.0 - 1.0
  limit?: number;
}

export interface SelectConceptBlockParams {
  conceptId: string;
  conceptLabel: string;
}

export interface NeighborhoodBlockParams {
  depth: number; // 1-5
  direction: 'outgoing' | 'incoming' | 'both';
  relationshipTypes?: string[]; // Empty = all types
}

export interface PathToBlockParams {
  targetType: 'search' | 'concept';
  // If targetType = 'search'
  targetQuery?: string;
  targetSimilarity?: number;
  // If targetType = 'concept'
  targetConceptId?: string;
  targetConceptLabel?: string;
  // Common
  maxHops: number; // 1-10
}

export interface FilterBlockParams {
  ontologies?: string[];
  relationshipTypes?: string[];
  minConfidence?: number; // 0.0 - 1.0
}

export interface LimitBlockParams {
  count: number;
}

// ============================================================================
// Block Data
// ============================================================================

export interface BlockData {
  type: BlockType;
  label: string;
  params: SearchBlockParams | SelectConceptBlockParams | NeighborhoodBlockParams | PathToBlockParams | FilterBlockParams | LimitBlockParams;
}

// ============================================================================
// React Flow Node Type
// ============================================================================

export type BlockNode = Node<BlockData>;

// ============================================================================
// Compiled Query
// ============================================================================

export interface CompiledQuery {
  cypher: string;
  errors: string[];
  warnings: string[];
}
