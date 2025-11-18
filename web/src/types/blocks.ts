/**
 * Visual Block Builder - Type Definitions
 *
 * Defines the data structures for the drag-and-drop query builder.
 */

import type { Node } from 'reactflow';

// ============================================================================
// Block Types
// ============================================================================

export type BlockType =
  | 'start'
  | 'end'
  // Cypher blocks (generate openCypher)
  | 'search'        // Text contains search
  | 'selectConcept'
  | 'neighborhood'
  | 'pathTo'
  | 'filterOntology'
  | 'filterEdge'
  | 'filterNode'
  | 'and'
  | 'or'
  | 'not'
  | 'limit'
  // Smart blocks (use API calls)
  | 'vectorSearch'  // Semantic search with embeddings
  | 'enrich';

// ============================================================================
// Block Parameters
// ============================================================================

export interface SearchBlockParams {
  query: string;
  similarity: number; // 0.0 - 1.0 (not used in text search, kept for compatibility)
  limit?: number;
}

export interface VectorSearchBlockParams {
  query: string;
  similarity: number; // 0.0 - 1.0 threshold for semantic matching
  limit: number;
}

export interface SelectConceptBlockParams {
  conceptId: string;
  conceptLabel: string;
}

export interface NeighborhoodBlockParams {
  depth: number; // 1-5
  direction: 'outgoing' | 'incoming' | 'both';
  relationshipTypes?: string[]; // Empty = all types
  // ADR-065: Epistemic status filtering
  includeEpistemicStatus?: string[];
  excludeEpistemicStatus?: string[];
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

export interface OntologyFilterBlockParams {
  ontologies?: string[];
}

export interface EdgeFilterBlockParams {
  relationshipTypes?: string[];
}

export interface NodeFilterBlockParams {
  nodeLabels?: string[];
  minConfidence?: number; // 0.0 - 1.0
}

export interface LimitBlockParams {
  count: number;
}

export interface StartBlockParams {
  // No parameters needed for start block
}

export interface EndBlockParams {
  // No parameters needed for end block
}

export interface AndBlockParams {
  // Automatically accepts multiple connections - no manual configuration needed
}

export interface OrBlockParams {
  // Automatically accepts multiple connections - no manual configuration needed
}

export interface NotBlockParams {
  // Pattern to exclude from results
  excludePattern?: string;
  // Property-based exclusion
  excludeProperty?: 'label' | 'ontology';
}

export interface EnrichBlockParams {
  // Options for what to enrich
  fetchOntology: boolean;
  fetchGrounding: boolean;
  fetchSearchTerms: boolean;
}

// ============================================================================
// Block Data
// ============================================================================

export interface BlockData {
  type: BlockType;
  label: string;
  params:
    | StartBlockParams
    | EndBlockParams
    | SearchBlockParams
    | VectorSearchBlockParams
    | SelectConceptBlockParams
    | NeighborhoodBlockParams
    | PathToBlockParams
    | OntologyFilterBlockParams
    | EdgeFilterBlockParams
    | NodeFilterBlockParams
    | AndBlockParams
    | OrBlockParams
    | NotBlockParams
    | LimitBlockParams
    | EnrichBlockParams;
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
