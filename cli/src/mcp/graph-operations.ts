/**
 * GraphOperationExecutor - Handles graph CRUD operations for MCP tool
 * ADR-089 Phase 3a refactoring: Extracted from mcp-server.ts handler
 */

import type { KnowledgeGraphClient } from '../api/client';
import type {
  MatchingMode,
  ConceptCRUDResponse,
  EdgeResponse,
  ConceptListCRUDResponse,
  EdgeListResponse,
} from '../types';

// ========== Constants ==========

/**
 * Valid edge categories (server-side validation).
 * Listed here for helpful error messages.
 */
const VALID_CATEGORIES = [
  'logical_truth',
  'causal',
  'structural',
  'temporal',
  'comparative',
  'functional',
  'definitional',
] as const;

/**
 * Enhance error messages for common validation failures.
 */
function enhanceErrorMessage(error: string): string {
  // Check for category validation errors
  if (error.includes('category') && (error.includes('validation') || error.includes('invalid') || error.includes('422'))) {
    return `Invalid category. Valid options: ${VALID_CATEGORIES.join(', ')}`;
  }
  return error;
}

// ========== Type Definitions ==========

/**
 * Entity types for graph operations.
 */
export type GraphEntity = 'concept' | 'edge';

/**
 * Action types for graph operations.
 */
export type GraphAction = 'create' | 'edit' | 'delete' | 'list';

/**
 * Base operation result with status.
 */
export interface OperationResult {
  success: boolean;
  error?: string;
}

/**
 * Result from concept create/edit/delete operations.
 */
export interface ConceptOperationResult extends OperationResult {
  data?: ConceptCRUDResponse & { from_label?: string; to_label?: string };
}

/**
 * Result from edge create/edit/delete operations.
 */
export interface EdgeOperationResult extends OperationResult {
  data?: EdgeResponse & { from_label?: string; to_label?: string };
}

/**
 * Result from concept list operation.
 */
export interface ConceptListResult extends OperationResult {
  data?: ConceptListCRUDResponse;
}

/**
 * Result from edge list operation.
 */
export interface EdgeListResult extends OperationResult {
  data?: EdgeListResponse;
}

/**
 * Parameters for creating a concept.
 */
export interface CreateConceptParams {
  label: string;
  ontology: string;
  description?: string;
  search_terms?: string[];
  matching_mode?: MatchingMode;
}

/**
 * Parameters for creating an edge.
 */
export interface CreateEdgeParams {
  from_concept_id?: string;
  from_label?: string;
  to_concept_id?: string;
  to_label?: string;
  relationship_type: string;
  category?: string;
  confidence?: number;
}

/**
 * Parameters for editing a concept.
 */
export interface EditConceptParams {
  concept_id: string;
  label?: string;
  description?: string;
  search_terms?: string[];
}

/**
 * Parameters for editing an edge.
 */
export interface EditEdgeParams {
  from_concept_id?: string;
  from_label?: string;
  to_concept_id?: string;
  to_label?: string;
  relationship_type: string;
  confidence?: number;
  category?: string;
}

/**
 * Parameters for deleting a concept.
 */
export interface DeleteConceptParams {
  concept_id: string;
  cascade?: boolean;
}

/**
 * Parameters for deleting an edge.
 */
export interface DeleteEdgeParams {
  from_concept_id?: string;
  from_label?: string;
  to_concept_id?: string;
  to_label?: string;
  relationship_type: string;
}

/**
 * Parameters for listing concepts.
 */
export interface ListConceptsParams {
  ontology?: string;
  label_contains?: string;
  creation_method?: string;
  offset?: number;
  limit?: number;
}

/**
 * Parameters for listing edges.
 */
export interface ListEdgesParams {
  from_concept_id?: string;
  from_label?: string;
  to_concept_id?: string;
  to_label?: string;
  relationship_type?: string;
  category?: string;
  source?: string;
  offset?: number;
  limit?: number;
}

/**
 * Queue operation definition.
 */
export interface QueueOperation {
  op: GraphAction;
  entity: GraphEntity;
  // Concept fields
  label?: string;
  ontology?: string;
  description?: string;
  search_terms?: string[];
  matching_mode?: MatchingMode;
  concept_id?: string;
  cascade?: boolean;
  label_contains?: string;
  creation_method?: string;
  // Edge fields
  from_concept_id?: string;
  from_label?: string;
  to_concept_id?: string;
  to_label?: string;
  relationship_type?: string;
  category?: string;
  confidence?: number;
  source?: string;
  // Pagination
  offset?: number;
  limit?: number;
}

/**
 * Result from a single queue operation.
 */
export interface QueueOperationResult {
  index: number;
  status: 'ok' | 'error';
  op: string;
  entity: string;
  // Success fields
  label?: string;
  id?: string;
  relationship?: string;
  count?: number;
  total?: number;
  matched_existing?: boolean;
  concepts?: Array<{ id: string; label: string }>;
  edges?: Array<{ from: string; type: string; to: string }>;
  // Error fields
  error?: string;
}

/**
 * Result from queue execution.
 */
export interface QueueExecutionResult {
  results: QueueOperationResult[];
  stopIndex: number;
  successCount: number;
  errorCount: number;
}

// ========== GraphOperationExecutor Class ==========

/**
 * Executes graph CRUD operations with semantic resolution support.
 */
export class GraphOperationExecutor {
  private client: KnowledgeGraphClient;

  constructor(client: KnowledgeGraphClient) {
    this.client = client;
  }

  /**
   * Resolve a concept label to its ID using semantic search.
   * @param label - The concept label to resolve
   * @returns The concept ID
   * @throws Error if no confident match found
   */
  async resolveConceptByLabel(label: string): Promise<string> {
    // Thresholds: 0.75 accept, 0.6 floor for suggestions.
    // CLI validation.ts uses 0.70 for its own search — intentionally different
    // because graph edits need higher confidence than exploratory search.
    const searchResult = await this.client.searchConcepts({
      query: label,
      limit: 3,
      min_similarity: 0.6,
    });

    if (searchResult.count === 0) {
      throw new Error(
        `No concept found matching label: "${label}". Try creating it first or use a more specific label.`
      );
    }

    const match = searchResult.results[0];
    if (match.score >= 0.75) {
      return match.concept_id;
    }

    // Near-miss: provide "did you mean?" suggestion
    const suggestions = searchResult.results
      .slice(0, 3)
      .map(r => `"${r.label}" (${(r.score * 100).toFixed(1)}%, id: ${r.concept_id})`)
      .join(', ');
    throw new Error(
      `No confident match for "${label}". Did you mean: ${suggestions}? Use concept_id for precise reference.`
    );
  }

  /**
   * Resolve concept ID from params, using label resolution if needed.
   * @param id - Explicit concept ID (optional)
   * @param label - Concept label for resolution (optional)
   * @param fieldName - Name of the field for error messages
   * @param throwOnMissing - Whether to throw if neither ID nor label provided
   * @returns The resolved concept ID or undefined
   */
  async resolveConceptId(
    id: string | undefined,
    label: string | undefined,
    fieldName: string,
    throwOnMissing: boolean = true
  ): Promise<string | undefined> {
    if (id) {
      return id;
    }
    if (label) {
      return await this.resolveConceptByLabel(label);
    }
    if (throwOnMissing) {
      throw new Error(`${fieldName}_concept_id or ${fieldName}_label is required`);
    }
    return undefined;
  }

  /**
   * Resolve concept ID for list operations (silently skip on error).
   */
  async resolveConceptIdForList(
    id: string | undefined,
    label: string | undefined
  ): Promise<string | undefined> {
    if (id) {
      return id;
    }
    if (label) {
      try {
        return await this.resolveConceptByLabel(label);
      } catch {
        // Ignore resolution errors for list - just skip filter
        return undefined;
      }
    }
    return undefined;
  }

  // ========== Create Operations ==========

  async createConcept(params: CreateConceptParams): Promise<ConceptOperationResult> {
    if (!params.label) {
      return { success: false, error: 'label is required for creating a concept' };
    }
    if (!params.ontology) {
      return { success: false, error: 'ontology is required for creating a concept' };
    }

    try {
      const result = await this.client.createConcept({
        label: params.label,
        ontology: params.ontology,
        description: params.description,
        search_terms: params.search_terms,
        matching_mode: params.matching_mode || 'auto',
        creation_method: 'mcp',
      });

      return { success: true, data: result };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  async createEdge(params: CreateEdgeParams): Promise<EdgeOperationResult> {
    if (!params.relationship_type) {
      return { success: false, error: 'relationship_type is required for creating an edge' };
    }

    try {
      const fromId = await this.resolveConceptId(
        params.from_concept_id,
        params.from_label,
        'from'
      );
      const toId = await this.resolveConceptId(
        params.to_concept_id,
        params.to_label,
        'to'
      );

      const result = await this.client.createEdge({
        from_concept_id: fromId!,
        to_concept_id: toId!,
        relationship_type: params.relationship_type,
        category: (params.category || 'logical_truth') as any, // Server validates
        confidence: params.confidence ?? 1.0,
        source: 'api_creation',
      });

      // Enrich result with resolved labels for better output
      const enrichedResult = {
        ...result,
        from_label: params.from_label || fromId,
        to_label: params.to_label || toId,
      };

      return { success: true, data: enrichedResult };
    } catch (err: unknown) {
      const rawError = err instanceof Error ? err.message : String(err);
      return { success: false, error: enhanceErrorMessage(rawError) };
    }
  }

  // ========== List Operations ==========

  async listConcepts(params: ListConceptsParams): Promise<ConceptListResult> {
    try {
      const result = await this.client.listConceptsCRUD({
        ontology: params.ontology,
        label_contains: params.label_contains,
        creation_method: params.creation_method,
        offset: params.offset || 0,
        limit: params.limit || 20,
      });

      return { success: true, data: result };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  async listEdges(params: ListEdgesParams): Promise<EdgeListResult> {
    try {
      const fromId = await this.resolveConceptIdForList(
        params.from_concept_id,
        params.from_label
      );
      const toId = await this.resolveConceptIdForList(
        params.to_concept_id,
        params.to_label
      );

      const result = await this.client.listEdges({
        from_concept_id: fromId,
        to_concept_id: toId,
        relationship_type: params.relationship_type,
        category: params.category,
        source: params.source,
        offset: params.offset || 0,
        limit: params.limit || 20,
      });

      return { success: true, data: result };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  // ========== Edit Operations ==========

  async editConcept(params: EditConceptParams): Promise<ConceptOperationResult> {
    if (!params.concept_id) {
      return { success: false, error: 'concept_id is required for editing a concept' };
    }

    const updateData: { label?: string; description?: string; search_terms?: string[] } = {};
    if (params.label !== undefined) updateData.label = params.label;
    if (params.description !== undefined) updateData.description = params.description;
    if (params.search_terms !== undefined) updateData.search_terms = params.search_terms;

    if (Object.keys(updateData).length === 0) {
      return {
        success: false,
        error: 'At least one field (label, description, or search_terms) must be provided for edit',
      };
    }

    try {
      const result = await this.client.updateConcept(params.concept_id, updateData);
      return { success: true, data: result };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  async editEdge(params: EditEdgeParams): Promise<EdgeOperationResult> {
    try {
      const fromId = await this.resolveConceptId(
        params.from_concept_id,
        params.from_label,
        'from'
      );
      const toId = await this.resolveConceptId(
        params.to_concept_id,
        params.to_label,
        'to'
      );

      if (!params.relationship_type) {
        return { success: false, error: 'relationship_type is required for editing an edge' };
      }

      const updateData: { confidence?: number; category?: string } = {};
      if (params.confidence !== undefined) updateData.confidence = params.confidence;
      if (params.category !== undefined) updateData.category = params.category;

      if (Object.keys(updateData).length === 0) {
        return {
          success: false,
          error: 'At least one field (confidence or category) must be provided for edge edit',
        };
      }

      const result = await this.client.updateEdge(
        fromId!,
        params.relationship_type,
        toId!,
        updateData as any // Server validates category
      );

      const enrichedResult = {
        ...result,
        from_label: params.from_label || fromId,
        to_label: params.to_label || toId,
      };

      return { success: true, data: enrichedResult };
    } catch (err: unknown) {
      const rawError = err instanceof Error ? err.message : String(err);
      return { success: false, error: enhanceErrorMessage(rawError) };
    }
  }

  // ========== Delete Operations ==========

  async deleteConcept(params: DeleteConceptParams): Promise<ConceptOperationResult> {
    if (!params.concept_id) {
      return { success: false, error: 'concept_id is required for deleting a concept' };
    }

    try {
      await this.client.deleteConcept(params.concept_id, params.cascade || false);
      return { success: true, data: { concept_id: params.concept_id } as ConceptCRUDResponse };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  async deleteEdge(params: DeleteEdgeParams): Promise<EdgeOperationResult> {
    try {
      const fromId = await this.resolveConceptId(
        params.from_concept_id,
        params.from_label,
        'from'
      );
      const toId = await this.resolveConceptId(
        params.to_concept_id,
        params.to_label,
        'to'
      );

      if (!params.relationship_type) {
        return { success: false, error: 'relationship_type is required for deleting an edge' };
      }

      await this.client.deleteEdge(fromId!, params.relationship_type, toId!);

      return {
        success: true,
        data: {
          from_concept_id: fromId!,
          to_concept_id: toId!,
          relationship_type: params.relationship_type,
        } as EdgeResponse,
      };
    } catch (err: unknown) {
      const error = err instanceof Error ? err.message : String(err);
      return { success: false, error };
    }
  }

  // ========== Queue Execution ==========

  /**
   * Execute a queue of operations sequentially.
   * @param operations - Array of operations to execute
   * @param continueOnError - Whether to continue after errors
   * @returns Queue execution result with all operation results
   */
  async executeQueue(
    operations: QueueOperation[],
    continueOnError: boolean = true
  ): Promise<QueueExecutionResult> {
    const results: QueueOperationResult[] = [];
    let stopIndex = -1;

    for (let i = 0; i < operations.length; i++) {
      const op = operations[i];

      if (!op.op || !op.entity) {
        results.push({
          index: i + 1,
          status: 'error',
          op: op.op || 'unknown',
          entity: op.entity || 'unknown',
          error: `Operation ${i + 1}: missing 'op' or 'entity'`,
        });
        if (!continueOnError) {
          stopIndex = i;
          break;
        }
        continue;
      }

      try {
        const result = await this.executeSingleOperation(op, i + 1);
        results.push(result);

        if (result.status === 'error' && !continueOnError) {
          stopIndex = i;
          break;
        }
      } catch (err: unknown) {
        const error = err instanceof Error ? err.message : String(err);
        results.push({
          index: i + 1,
          status: 'error',
          op: op.op,
          entity: op.entity,
          error,
        });
        if (!continueOnError) {
          stopIndex = i;
          break;
        }
      }
    }

    return {
      results,
      stopIndex,
      successCount: results.filter((r) => r.status === 'ok').length,
      errorCount: results.filter((r) => r.status === 'error').length,
    };
  }

  /**
   * Execute a single queue operation.
   */
  private async executeSingleOperation(
    op: QueueOperation,
    index: number
  ): Promise<QueueOperationResult> {
    const { op: action, entity } = op;

    // Create concept
    if (action === 'create' && entity === 'concept') {
      if (!op.label || !op.ontology) {
        throw new Error('label and ontology required');
      }
      const result = await this.createConcept({
        label: op.label,
        ontology: op.ontology,
        description: op.description,
        search_terms: op.search_terms,
        matching_mode: op.matching_mode,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'create',
        entity: 'concept',
        label: result.data!.label,
        id: result.data!.concept_id,
        matched_existing: result.data!.matched_existing,
      };
    }

    // Create edge
    if (action === 'create' && entity === 'edge') {
      const result = await this.createEdge({
        from_concept_id: op.from_concept_id,
        from_label: op.from_label,
        to_concept_id: op.to_concept_id,
        to_label: op.to_label,
        relationship_type: op.relationship_type!,
        category: op.category,
        confidence: op.confidence,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'create',
        entity: 'edge',
        relationship: `${op.from_label || result.data!.from_concept_id} -[${op.relationship_type}]-> ${op.to_label || result.data!.to_concept_id}`,
      };
    }

    // List concepts
    if (action === 'list' && entity === 'concept') {
      const result = await this.listConcepts({
        ontology: op.ontology,
        label_contains: op.label_contains,
        creation_method: op.creation_method,
        offset: op.offset,
        limit: op.limit,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'list',
        entity: 'concept',
        count: result.data!.concepts.length,
        total: result.data!.total,
        concepts: result.data!.concepts.map((c) => ({ id: c.concept_id, label: c.label })),
      };
    }

    // List edges
    if (action === 'list' && entity === 'edge') {
      const result = await this.listEdges({
        from_concept_id: op.from_concept_id,
        from_label: op.from_label,
        to_concept_id: op.to_concept_id,
        to_label: op.to_label,
        relationship_type: op.relationship_type,
        category: op.category,
        source: op.source,
        offset: op.offset,
        limit: op.limit,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'list',
        entity: 'edge',
        count: result.data!.edges.length,
        total: result.data!.total,
        edges: result.data!.edges.map((e) => ({
          from: e.from_concept_id,
          type: e.relationship_type,
          to: e.to_concept_id,
        })),
      };
    }

    // Edit concept
    if (action === 'edit' && entity === 'concept') {
      if (!op.concept_id) {
        throw new Error('concept_id required for edit');
      }
      const result = await this.editConcept({
        concept_id: op.concept_id,
        label: op.label,
        description: op.description,
        search_terms: op.search_terms,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'edit',
        entity: 'concept',
        id: result.data!.concept_id,
        label: result.data!.label,
      };
    }

    // Edit edge
    if (action === 'edit' && entity === 'edge') {
      const result = await this.editEdge({
        from_concept_id: op.from_concept_id,
        from_label: op.from_label,
        to_concept_id: op.to_concept_id,
        to_label: op.to_label,
        relationship_type: op.relationship_type!,
        confidence: op.confidence,
        category: op.category,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'edit',
        entity: 'edge',
        relationship: `${op.from_label || result.data!.from_concept_id} -[${op.relationship_type}]-> ${op.to_label || result.data!.to_concept_id}`,
      };
    }

    // Delete concept
    if (action === 'delete' && entity === 'concept') {
      if (!op.concept_id) {
        throw new Error('concept_id required for delete');
      }
      const result = await this.deleteConcept({
        concept_id: op.concept_id,
        cascade: op.cascade,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'delete',
        entity: 'concept',
        id: op.concept_id,
      };
    }

    // Delete edge
    if (action === 'delete' && entity === 'edge') {
      const result = await this.deleteEdge({
        from_concept_id: op.from_concept_id,
        from_label: op.from_label,
        to_concept_id: op.to_concept_id,
        to_label: op.to_label,
        relationship_type: op.relationship_type!,
      });
      if (!result.success) {
        throw new Error(result.error);
      }
      return {
        index,
        status: 'ok',
        op: 'delete',
        entity: 'edge',
        relationship: `${op.from_label || result.data!.from_concept_id} -[${op.relationship_type}]-> ${op.to_label || result.data!.to_concept_id}`,
      };
    }

    throw new Error(`Unknown operation: ${action} ${entity}`);
  }
}
