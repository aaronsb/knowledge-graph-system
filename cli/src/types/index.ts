/**
 * TypeScript types matching the FastAPI Pydantic models
 */

export interface JobProgress {
  stage: string;
  chunks_total?: number;
  chunks_processed?: number;
  percent?: number;
  current_chunk?: number;
  concepts_created?: number;
  concepts_linked?: number;  // Existing concepts reused (hit rate)
  sources_created?: number;
  instances_created?: number;
  relationships_created?: number;
  // Restore-specific progress fields (ADR-015 Phase 2)
  items_total?: number;  // Total items to restore (concepts, sources, etc.)
  items_processed?: number;  // Items processed so far
  message?: string;  // Progress message
}

export interface JobCost {
  extraction: string;
  embeddings: string;
  total: string;
  extraction_model?: string;
  embedding_model?: string;
}

export interface JobStats {
  chunks_processed: number;
  sources_created: number;
  concepts_created: number;
  concepts_linked: number;
  instances_created: number;
  relationships_created: number;
  extraction_tokens: number;
  embedding_tokens: number;
}

export interface JobResult {
  status: string;
  stats?: JobStats;
  cost?: JobCost;
  ontology?: string;
  filename?: string;
  chunks_processed?: number;
  message?: string;
  // Restore-specific result fields (ADR-015 Phase 2)
  restore_stats?: {
    concepts: number;
    sources: number;
    instances: number;
    relationships: number;
  };
  checkpoint_created?: boolean;
  checkpoint_deleted?: boolean;
  temp_file_cleaned?: boolean;
}

export interface JobStatus {
  job_id: string;
  job_type: string;
  status: 'pending' | 'awaiting_approval' | 'approved' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  user_id?: number;  // User ID who submitted the job (from kg_auth.users)
  username?: string;  // Username who submitted the job
  progress?: JobProgress;
  result?: JobResult;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  content_hash?: string;
  ontology?: string;
  client_id?: string;  // DEPRECATED: kept for backwards compatibility, use user_id instead
  processing_mode?: string;  // Serial or parallel processing
  analysis?: any;  // Pre-ingestion analysis (ADR-014)
  approved_at?: string;
  approved_by?: string;
  expires_at?: string;
  // ADR-051: Source provenance metadata
  filename?: string;
  source_type?: string;
  source_path?: string;
  source_hostname?: string;
}

export interface JobSubmitResponse {
  job_id: string;
  status: string;
  content_hash: string;
  position?: number;
  message?: string;
}

export interface DuplicateJobResponse {
  duplicate: true;
  existing_job_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  result?: JobResult;
  message: string;
  use_force?: string;
}

export interface IngestionOptions {
  target_words?: number;
  min_words?: number;
  max_words?: number;
  overlap_words?: number;
}

export interface IngestRequest {
  ontology: string;
  filename?: string;
  force?: boolean;
  auto_approve?: boolean;  // ADR-014: Skip approval step
  processing_mode?: string;  // Serial or parallel processing
  options?: IngestionOptions;
  // ADR-051: Source provenance metadata
  source_type?: string;      // "file" | "stdin" | "mcp" | "api"
  source_path?: string;       // Full filesystem path (file ingestion only)
  source_hostname?: string;   // Hostname where ingestion initiated
}

export interface ApiConfig {
  baseUrl: string;
  clientId?: string;
  apiKey?: string;
}

// Query types
export interface SearchRequest {
  query: string;
  limit?: number;
  min_similarity?: number;
  offset?: number; // Pagination offset
  include_evidence?: boolean; // Include sample evidence instances (quotes from source text)
  include_grounding?: boolean; // Include grounding strength (ADR-044: probabilistic truth score)
  include_diversity?: boolean; // Include semantic diversity (ADR-063: authenticity signal)
  diversity_max_hops?: number; // Maximum traversal depth for diversity (1-3, default 2)
}

export interface ConceptSearchResult {
  concept_id: string;
  label: string;
  description?: string; // Factual 1-2 sentence definition of the concept
  score: number;
  documents: string[];
  evidence_count: number;
  grounding_strength?: number; // ADR-044: Grounding strength (-1.0 to 1.0)
  diversity_score?: number; // ADR-063: Semantic diversity (0.0 to 1.0)
  diversity_related_count?: number; // Number of related concepts analyzed for diversity
  authenticated_diversity?: number; // ADR-044 + ADR-063: sign(grounding) × diversity
  sample_evidence?: ConceptInstance[]; // Sample evidence instances when include_evidence=true
}

export interface SearchResponse {
  query: string;
  count: number;
  results: ConceptSearchResult[];
  below_threshold_count?: number;
  suggested_threshold?: number;
  threshold_used?: number;
  offset?: number; // Pagination offset used
}

export interface ConceptInstance {
  quote: string;
  document: string;
  paragraph: number;
  source_id: string;
  full_text?: string; // Full chunk text for grounding
  // ADR-057: Image metadata
  content_type?: string; // 'image' for image sources, 'text' or null for text
  has_image?: boolean; // True if source has associated image
  image_uri?: string; // URI to retrieve image: /api/sources/{source_id}/image
  minio_object_key?: string; // MinIO object key (internal use)
}

export interface ConceptRelationship {
  to_id: string;
  to_label: string;
  rel_type: string;
  confidence?: number;
}

export interface ConceptDetailsResponse {
  concept_id: string;
  label: string;
  description?: string; // Factual 1-2 sentence definition of the concept
  search_terms: string[];
  documents: string[];
  instances: ConceptInstance[];
  relationships: ConceptRelationship[];
  grounding_strength?: number; // ADR-044: Grounding strength (-1.0 to 1.0)
  diversity_score?: number; // ADR-063: Semantic diversity (0.0 to 1.0)
  diversity_related_count?: number; // Number of related concepts analyzed for diversity
  authenticated_diversity?: number; // ADR-044 + ADR-063: sign(grounding) × diversity
}

export interface RelatedConceptsRequest {
  concept_id: string;
  relationship_types?: string[];
  max_depth?: number;
  // ADR-065: Epistemic status filtering
  include_epistemic_status?: string[]; // Filter to only include relationships with these epistemic statuses
  exclude_epistemic_status?: string[]; // Exclude relationships with these epistemic statuses
}

export interface RelatedConcept {
  concept_id: string;
  label: string;
  distance: number;
  path_types: string[];
}

export interface RelatedConceptsResponse {
  concept_id: string;
  max_depth: number;
  count: number;
  results: RelatedConcept[];
}

export interface FindConnectionRequest {
  from_id: string;
  to_id: string;
  max_hops?: number;
  include_evidence?: boolean; // Include sample evidence instances for each concept in paths
  include_grounding?: boolean; // Include grounding strength for each concept in paths (ADR-044)
  // ADR-065: Epistemic status filtering
  include_epistemic_status?: string[]; // Filter to only include relationships with these epistemic statuses
  exclude_epistemic_status?: string[]; // Exclude relationships with these epistemic statuses
}

export interface PathNode {
  id: string;
  label: string;
  description?: string; // Factual 1-2 sentence definition
  grounding_strength?: number; // ADR-044: Grounding strength (-1.0 to 1.0)
  diversity_score?: number; // ADR-063: Diversity score (0.0 to 1.0)
  diversity_related_count?: number; // ADR-063: Number of related concepts
  authenticated_diversity?: number; // ADR-063: Authenticated diversity
  sample_evidence?: ConceptInstance[]; // Sample evidence instances when include_evidence=true
}

export interface ConnectionPath {
  nodes: PathNode[];
  relationships: string[];
  hops: number;
}

export interface FindConnectionResponse {
  from_id: string;
  to_id: string;
  max_hops: number;
  count: number;
  paths: ConnectionPath[];
}

export interface FindConnectionBySearchRequest {
  from_query: string;
  to_query: string;
  max_hops?: number;
  threshold?: number;
  include_evidence?: boolean; // Include sample evidence instances for each concept in paths
  include_grounding?: boolean; // Include grounding strength for each concept in paths (ADR-044)
  // ADR-065: Epistemic status filtering
  include_epistemic_status?: string[]; // Filter to only include relationships with these epistemic statuses
  exclude_epistemic_status?: string[]; // Exclude relationships with these epistemic statuses
}

export interface FindConnectionBySearchResponse {
  from_query: string;
  to_query: string;
  from_concept?: PathNode;
  to_concept?: PathNode;
  from_similarity?: number;
  to_similarity?: number;
  from_suggested_threshold?: number;
  to_suggested_threshold?: number;
  from_near_misses?: number;
  to_near_misses?: number;
  max_hops: number;
  count: number;
  paths: ConnectionPath[];
}

// Database types
export interface MetricCounter {
  counter: number;
  delta: number;
  last_measured_at?: string | null;
}

export interface DatabaseStatsResponse {
  nodes: {
    concepts: number;
    sources: number;
    instances: number;
  };
  relationships: {
    total: number;
    by_type: Array<{ rel_type: string; count: number }>;
  };
  metrics?: {
    vocabulary_change_counter?: MetricCounter;
    epistemic_measurement_counter?: MetricCounter;
    [key: string]: MetricCounter | undefined;
  };
}

export interface DatabaseInfoResponse {
  uri: string;
  user: string;
  connected: boolean;
  version?: string;
  edition?: string;
  error?: string;
}

export interface DatabaseHealthResponse {
  status: string;
  responsive: boolean;
  checks: Record<string, any>;
  error?: string;
}

// Ontology types
export interface OntologyItem {
  ontology: string;
  source_count: number;
  file_count: number;
  concept_count: number;
}

export interface OntologyListResponse {
  count: number;
  ontologies: OntologyItem[];
}

export interface OntologyInfoResponse {
  ontology: string;
  statistics: {
    source_count: number;
    file_count: number;
    concept_count: number;
    instance_count: number;
    relationship_count: number;
  };
  files: string[];
}

export interface OntologyFileInfo {
  file_path: string;
  chunk_count: number;
  concept_count: number;
}

export interface OntologyFilesResponse {
  ontology: string;
  count: number;
  files: OntologyFileInfo[];
}

export interface OntologyDeleteResponse {
  ontology: string;
  deleted: boolean;
  sources_deleted: number;
  orphaned_concepts_deleted: number;
  error?: string;
}

export interface OntologyRenameResponse {
  old_name: string;
  new_name: string;
  sources_updated: number;
  success: boolean;
  error?: string;
}

// ========== Admin Types ==========

export interface DockerStatus {
  running: boolean;
  container_name?: string;
  status?: string;
  ports?: string;
}

export interface DatabaseConnection {
  connected: boolean;
  uri: string;
  error?: string;
}

export interface DatabaseStatsAdmin {
  concepts: number;
  sources: number;
  instances: number;
  relationships: number;
}

export interface PythonEnvironment {
  venv_exists: boolean;
  python_version?: string;
}

export interface ConfigurationStatus {
  env_exists: boolean;
  anthropic_key_configured: boolean;
  openai_key_configured: boolean;
}

export interface SystemStatusResponse {
  docker: DockerStatus;
  database_connection: DatabaseConnection;
  database_stats?: DatabaseStatsAdmin;
  python_env: PythonEnvironment;
  configuration: ConfigurationStatus;
  neo4j_browser_url?: string;
  bolt_url?: string;
}

export interface BackupRequest {
  backup_type: 'full' | 'ontology';
  ontology_name?: string;
  output_filename?: string;
  format?: 'json' | 'gexf';  // Export format: json (native, restorable) or gexf (Gephi visualization)
}

export interface BackupIntegrityAssessment {
  external_dependencies_count: number;
  warnings_count: number;
  issues_count: number;
  has_external_deps: boolean;
  details: Record<string, any>;
}

export interface BackupResponse {
  success: boolean;
  backup_file: string;
  file_size_mb: number;
  statistics: Record<string, number>;
  integrity_assessment?: BackupIntegrityAssessment;
  message: string;
}

export interface BackupInfo {
  filename: string;
  path: string;
  size_mb: number;
  created: string;
}

export interface ListBackupsResponse {
  backups: BackupInfo[];
  backup_dir: string;
  count: number;
}

export interface RestoreRequest {
  username: string;
  password: string;
  backup_file: string;
  overwrite?: boolean;
  handle_external_deps?: 'prune' | 'stitch' | 'defer';
}

export interface RestoreResponse {
  success: boolean;
  restored_counts: Record<string, number>;
  warnings: string[];
  message: string;
  external_deps_handled?: string;
}

export interface ResetRequest {
  username: string;
  password: string;
  confirm: boolean;
  clear_logs?: boolean;
  clear_checkpoints?: boolean;
}

export interface SchemaValidation {
  constraints_count: number;
  vector_index_exists: boolean;
  node_count: number;
  schema_test_passed: boolean;
}

export interface ResetResponse {
  success: boolean;
  schema_validation: SchemaValidation;
  message: string;
  warnings: string[];
}

// ========== RBAC Types (ADR-028) ==========

// Resource Types
export interface ResourceCreate {
  resource_type: string;
  description?: string;
  parent_type?: string;
  available_actions: string[];
  supports_scoping?: boolean;
  metadata?: Record<string, any>;
}

export interface ResourceRead {
  resource_type: string;
  description?: string;
  parent_type?: string;
  available_actions: string[];
  supports_scoping: boolean;
  metadata: Record<string, any>;
  registered_at: string;
  registered_by?: string;
}

export interface ResourceUpdate {
  description?: string;
  available_actions?: string[];
  supports_scoping?: boolean;
  metadata?: Record<string, any>;
}

// Role Types
export interface RoleCreate {
  role_name: string;
  display_name: string;
  description?: string;
  parent_role?: string;
  metadata?: Record<string, any>;
}

export interface RoleRead {
  role_name: string;
  display_name: string;
  description?: string;
  is_builtin: boolean;
  is_active: boolean;
  parent_role?: string;
  created_at: string;
  created_by?: number;
  metadata: Record<string, any>;
}

export interface RoleUpdate {
  display_name?: string;
  description?: string;
  parent_role?: string;
  is_active?: boolean;
  metadata?: Record<string, any>;
}

// Permission Types
export interface PermissionCreate {
  role_name: string;
  resource_type: string;
  action: string;
  scope_type?: string;
  scope_id?: string;
  scope_filter?: Record<string, any>;
  granted?: boolean;
}

export interface PermissionRead {
  id: number;
  role_name: string;
  resource_type: string;
  action: string;
  scope_type: string;
  scope_id?: string;
  scope_filter?: Record<string, any>;
  granted: boolean;
  inherited_from?: string;
  created_at: string;
  created_by?: number;
}

// User Role Assignment Types
export interface UserRoleAssign {
  user_id: number;
  role_name: string;
  scope_type?: string;
  scope_id?: string;
  expires_at?: string;
}

export interface UserRoleRead {
  id: number;
  user_id: number;
  role_name: string;
  scope_type?: string;
  scope_id?: string;
  assigned_at: string;
  assigned_by?: number;
  expires_at?: string;
}

// Permission Check Types
export interface PermissionCheckRequest {
  user_id: number;
  resource_type: string;
  action: string;
  resource_id?: string;
  resource_context?: Record<string, any>;
}

export interface PermissionCheckResponse {
  allowed: boolean;
  reason?: string;
}

// ========== AI Configuration Types (ADR-039, ADR-041) ==========

// Embedding Configuration
export interface EmbeddingConfigResponse {
  provider: string;
  model: string;
  dimensions: number;
  precision?: string;
  config_id: number;
  supports_browser?: boolean;
  resource_allocation?: {
    max_memory_mb: number;
    num_threads: number;
    device: string;
    batch_size: number;
  };
}

export interface EmbeddingConfigDetail {
  id: number;
  provider: string;
  model_name: string;
  dimensions: number;
  precision?: string;
  supports_browser?: boolean;
  max_memory_mb?: number;
  num_threads?: number;
  device?: string;
  batch_size?: number;
  created_at: string;
  updated_at: string;
  updated_by?: string;
  active: boolean;
}

export interface UpdateEmbeddingConfigRequest {
  provider: string;
  model_name: string;
  dimensions: number;
  precision?: string;
  supports_browser?: boolean;
  max_memory_mb?: number;
  num_threads?: number;
  device?: string;
  batch_size?: number;
  updated_by?: string;
}

export interface UpdateEmbeddingConfigResponse {
  success: boolean;
  message: string;
  config_id: number;
  reload_required: boolean;
}

// Extraction Configuration
export interface ExtractionConfigResponse {
  provider: string;
  model: string;
  supports_vision: boolean;
  supports_json_mode: boolean;
  max_tokens: number;
  config_id: number;
}

export interface ExtractionConfigDetail {
  id: number;
  provider: string;
  model_name: string;
  supports_vision: boolean;
  supports_json_mode: boolean;
  max_tokens?: number;
  created_at: string;
  updated_at: string;
  updated_by?: string;
  active: boolean;
}

export interface UpdateExtractionConfigRequest {
  provider: string;
  model_name: string;
  supports_vision?: boolean;
  supports_json_mode?: boolean;
  max_tokens?: number;
  updated_by?: string;
}

export interface UpdateExtractionConfigResponse {
  success: boolean;
  message: string;
  config_id: number;
  reload_required: boolean;
}

// API Key Management
export interface ApiKeyInfo {
  provider: string;
  configured: boolean;
  updated_at?: string;
  validation_status?: 'valid' | 'invalid' | 'untested';
  last_validated_at?: string;
  validation_error?: string;
  masked_key?: string;
}

export interface SetApiKeyRequest {
  provider: string;
  api_key: string;
}

export interface SetApiKeyResponse {
  status: string;
  message: string;
  provider: string;
  validation_status: string;
}

export interface DeleteApiKeyResponse {
  status: string;
  message: string;
  provider: string;
}
