/**
 * Artifact Types (ADR-083)
 *
 * TypeScript types for artifact persistence system.
 */

// Valid artifact types (from API model)
export type ArtifactType =
  | 'polarity_analysis'
  | 'projection'
  | 'query_result'
  | 'graph_subgraph'
  | 'vocabulary_analysis'
  | 'epistemic_measurement'
  | 'consolidation_result'
  | 'search_result'
  | 'connection_path'
  | 'report'
  | 'stats_snapshot';

// Valid representation sources (from API model)
export type Representation =
  | 'polarity_explorer'
  | 'embedding_landscape'
  | 'block_builder'
  | 'edge_explorer'
  | 'vocabulary_chord'
  | 'force_graph_2d'
  | 'force_graph_3d'
  | 'document_explorer'
  | 'report_workspace'
  | 'cli'
  | 'mcp_server'
  | 'api_direct';

/**
 * Artifact metadata (without payload)
 */
export interface ArtifactMetadata {
  id: number;
  artifact_type: ArtifactType;
  representation: Representation;
  name: string | null;
  owner_id: number | null;
  graph_epoch: number;
  is_fresh: boolean;
  created_at: string;
  expires_at: string | null;
  parameters: Record<string, unknown>;
  metadata: Record<string, unknown> | null;
  ontology: string | null;
  concept_ids: string[] | null;
  query_definition_id: number | null;
  has_inline_result: boolean;
  garage_key: string | null;
}

/**
 * Artifact with full payload
 */
export interface ArtifactWithPayload extends ArtifactMetadata {
  payload: Record<string, unknown>;
}

/**
 * List artifacts response
 */
export interface ArtifactListResponse {
  artifacts: ArtifactMetadata[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Create artifact request
 */
export interface ArtifactCreateRequest {
  artifact_type: ArtifactType;
  representation: Representation;
  name?: string;
  parameters: Record<string, unknown>;
  payload: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  ontology?: string;
  concept_ids?: string[];
  expires_at?: string;
  query_definition_id?: number;
}

/**
 * Create artifact response
 */
export interface ArtifactCreateResponse {
  id: number;
  artifact_type: ArtifactType;
  representation: Representation;
  name: string | null;
  graph_epoch: number;
  storage_location: 'inline' | 'garage';
  garage_key: string | null;
  created_at: string;
}

/**
 * Regenerate artifact response
 */
export interface ArtifactRegenerateResponse {
  job_id: string;
  status: string;
  message: string;
}

/**
 * Query definition (ADR-083)
 */
export interface QueryDefinition {
  id: number;
  name: string;
  definition_type: string;
  definition: Record<string, unknown>;
  owner_id: number | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown> | null;
}

/**
 * Query definition list response
 */
export interface QueryDefinitionListResponse {
  definitions: QueryDefinition[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Create query definition request
 */
export interface QueryDefinitionCreateRequest {
  name: string;
  definition_type: string;
  definition: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
