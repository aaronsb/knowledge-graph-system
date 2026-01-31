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
  // Artifact-producing jobs (ADR-083)
  artifact_id?: number;
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
  ontology?: string; // Filter results to concepts from this ontology only
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
  // Epistemic confidence (grounding × confidence two-dimensional model)
  confidence_level?: string; // 'confident', 'tentative', 'insufficient'
  confidence_score?: number; // Numeric confidence (0.0 to 1.0) - nonlinear saturation reflecting evidence richness
  grounding_display?: string; // Combined label: 'Well-supported', 'Unexplored', 'Contested', etc.
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

// Source Search types (ADR-068 Phase 3)
export interface SourceSearchRequest {
  query: string;
  limit?: number;
  min_similarity?: number;
  ontology?: string;
  include_concepts?: boolean;
  include_full_text?: boolean;
}

export interface SourceConcept {
  concept_id: string;
  label: string;
  description?: string;
  instance_quote: string;
}

export interface SourceChunk {
  chunk_text: string;
  start_offset: number;
  end_offset: number;
  chunk_index: number;
  similarity: number;
}

export interface SourceSearchResult {
  source_id: string;
  document: string;
  paragraph: number;
  similarity: number;
  is_stale: boolean;
  matched_chunk: SourceChunk;
  full_text?: string;
  concepts: SourceConcept[];
}

export interface SourceSearchResponse {
  query: string;
  count: number;
  results: SourceSearchResult[];
  threshold_used: number;
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
  // Epistemic confidence (grounding × confidence two-dimensional model)
  confidence_level?: string; // 'confident', 'tentative', 'insufficient'
  confidence_score?: number; // Numeric confidence (0.0 to 1.0) - nonlinear saturation reflecting evidence richness
  grounding_display?: string; // Combined label: 'Well-supported', 'Unexplored', 'Contested', etc.
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
  // Epistemic confidence (grounding × confidence two-dimensional model)
  confidence_level?: string; // 'confident', 'tentative', 'insufficient'
  confidence_score?: number; // Numeric confidence (0.0 to 1.0)
  grounding_display?: string; // Combined label: 'Well-supported', 'Unexplored', 'Contested', etc.
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

// ADR-200 Phase 2: Ontology lifecycle states
export type LifecycleState = 'active' | 'pinned' | 'frozen';

export interface OntologyItem {
  ontology: string;
  source_count: number;
  file_count: number;
  concept_count: number;
  // ADR-200: Graph node properties
  ontology_id?: string;
  lifecycle_state?: string;
  creation_epoch?: number;
  has_embedding?: boolean;
  created_by?: string;
}

export interface OntologyListResponse {
  count: number;
  ontologies: OntologyItem[];
}

// ADR-200: Ontology graph node response
export interface OntologyNodeResponse {
  ontology_id: string;
  name: string;
  description: string;
  lifecycle_state: string;
  creation_epoch: number;
  has_embedding: boolean;
  search_terms: string[];
  created_by?: string;
}

// ADR-200 Phase 2: Lifecycle state change
export interface OntologyLifecycleResponse {
  ontology: string;
  previous_state: string;
  new_state: string;
  success: boolean;
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
  // ADR-200: Graph node properties
  node?: OntologyNodeResponse;
}

export interface OntologyFileInfo {
  file_path: string;
  chunk_count: number;
  concept_count: number;
  source_ids: string[];
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

// ADR-200 Phase 3a: Scoring & Breathing Control Surface

export interface OntologyStats {
  ontology: string;
  concept_count: number;
  source_count: number;
  file_count: number;
  evidence_count: number;
  internal_relationship_count: number;
  cross_ontology_relationship_count: number;
}

export interface OntologyScores {
  ontology: string;
  mass_score: number;
  coherence_score: number;
  raw_exposure: number;
  weighted_exposure: number;
  protection_score: number;
  last_evaluated_epoch: number;
}

export interface OntologyScoresResponse {
  count: number;
  global_epoch: number;
  scores: OntologyScores[];
}

export interface ConceptDegreeRanking {
  concept_id: string;
  label: string;
  degree: number;
  in_degree: number;
  out_degree: number;
}

export interface ConceptDegreeResponse {
  ontology: string;
  count: number;
  concepts: ConceptDegreeRanking[];
}

export interface AffinityResult {
  other_ontology: string;
  shared_concept_count: number;
  total_concepts: number;
  affinity_score: number;
}

export interface AffinityResponse {
  ontology: string;
  count: number;
  affinities: AffinityResult[];
}

export interface ReassignResponse {
  from_ontology: string;
  to_ontology: string;
  sources_reassigned: number;
  success: boolean;
  error?: string;
}

export interface DissolveResponse {
  dissolved_ontology: string;
  sources_reassigned: number;
  ontology_node_deleted: boolean;
  reassignment_targets: string[];
  success: boolean;
  error?: string;
}

// ========== ADR-200 Phase 5: Ontology-to-Ontology Edges ==========

export interface OntologyEdge {
  from_ontology: string;
  to_ontology: string;
  edge_type: string;
  score: number;
  shared_concept_count: number;
  computed_at_epoch: number;
  source: string;
  direction: string;
}

export interface OntologyEdgesResponse {
  ontology: string;
  count: number;
  edges: OntologyEdge[];
}

// ========== ADR-200 Phase 3b: Breathing Proposals ==========

export interface BreathingProposal {
  id: number;
  proposal_type: string;
  ontology_name: string;
  anchor_concept_id?: string;
  target_ontology?: string;
  reasoning: string;
  mass_score?: number;
  coherence_score?: number;
  protection_score?: number;
  status: string;
  created_at: string;
  created_at_epoch: number;
  reviewed_at?: string;
  reviewed_by?: string;
  reviewer_notes?: string;
}

export interface BreathingProposalListResponse {
  proposals: BreathingProposal[];
  count: number;
}

export interface BreathingCycleResult {
  proposals_generated: number;
  demotion_candidates: number;
  promotion_candidates: number;
  scores_updated: number;
  centroids_updated: number;
  edges_created: number;
  edges_deleted: number;
  cycle_epoch: number;
  dry_run: boolean;
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
  format?: 'archive' | 'json' | 'gexf';  // Export format: archive (tar.gz with documents, default), json (graph only), or gexf (Gephi visualization)
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

// Projection Types (ADR-078)
export interface ProjectionAlgorithmsResponse {
  available: string[];
  default: string;
}

export interface ProjectionConcept {
  concept_id: string;
  label: string;
  x: number;
  y: number;
  z: number;
  grounding_strength?: number | null;
  diversity_score?: number | null;
  diversity_related_count?: number | null;
}

export interface ProjectionParameters {
  n_components: number;
  perplexity?: number | null;
  n_neighbors?: number | null;
  min_dist?: number | null;
}

export interface ProjectionStatistics {
  concept_count: number;
  computation_time_ms: number;
  embedding_dims: number;
  grounding_range?: number[] | null;
  diversity_range?: number[] | null;
}

export interface ProjectionDataset {
  ontology: string;
  changelist_id: string;
  algorithm: string;
  parameters: ProjectionParameters;
  computed_at: string;
  concepts: ProjectionConcept[];
  statistics: ProjectionStatistics;
}

export interface ProjectionRegenerateRequest {
  force?: boolean;
  algorithm?: 'tsne' | 'umap';
  n_components?: number;
  perplexity?: number;
  n_neighbors?: number;
  min_dist?: number;
  include_grounding?: boolean;
  include_diversity?: boolean;
}

export interface ProjectionRegenerateResponse {
  status: 'queued' | 'skipped' | 'computed';
  job_id?: string | null;
  message: string;
  changelist_id?: string | null;
}

// ========== Concept CRUD Types (ADR-089) ==========

/**
 * How to handle potential duplicates when creating concepts.
 * - auto: Match existing concepts by embedding similarity, create if no match
 * - force_create: Always create new concept, skip matching
 * - match_only: Only link to existing concept, fail if no match found
 */
export type MatchingMode = 'auto' | 'force_create' | 'match_only';

/**
 * How this concept was created (provenance tracking).
 */
export type CreationMethod = 'api' | 'cli' | 'mcp' | 'workstation' | 'import' | 'llm_extraction';

/**
 * Request to create a new concept.
 */
export interface ConceptCreate {
  label: string;
  ontology: string;
  description?: string;
  search_terms?: string[];
  matching_mode?: MatchingMode;
  creation_method?: CreationMethod;
}

/**
 * Request to update an existing concept (partial update).
 */
export interface ConceptUpdate {
  label?: string;
  description?: string;
  search_terms?: string[];
}

/**
 * Response containing concept details.
 */
export interface ConceptCRUDResponse {
  concept_id: string;
  label: string;
  description?: string;
  search_terms: string[];
  ontology?: string;
  creation_method?: string;
  has_embedding: boolean;
  matched_existing: boolean;
}

/**
 * Response containing a list of concepts.
 */
export interface ConceptListCRUDResponse {
  concepts: ConceptCRUDResponse[];
  total: number;
  offset: number;
  limit: number;
}

// ========== Edge CRUD Types (ADR-089) ==========

/**
 * How this edge was created (provenance tracking).
 */
export type EdgeSource = 'api_creation' | 'human_curation' | 'llm_extraction' | 'import';

/**
 * Semantic category of the relationship (ADR-022).
 */
export type RelationshipCategory =
  | 'logical_truth'
  | 'causal'
  | 'structural'
  | 'temporal'
  | 'comparative'
  | 'functional'
  | 'definitional';

/**
 * Request to create a new edge between concepts.
 */
export interface EdgeCreate {
  from_concept_id: string;
  to_concept_id: string;
  relationship_type: string;
  category?: RelationshipCategory;
  confidence?: number;
  source?: EdgeSource;
}

/**
 * Request to update an existing edge (partial update).
 */
export interface EdgeUpdate {
  relationship_type?: string;
  category?: RelationshipCategory;
  confidence?: number;
}

/**
 * Response containing edge details.
 */
export interface EdgeResponse {
  edge_id: string;
  from_concept_id: string;
  to_concept_id: string;
  relationship_type: string;
  category: string;
  confidence: number;
  source: string;
  created_at?: string;
  created_by?: string;
}

/**
 * Response containing a list of edges.
 */
export interface EdgeListResponse {
  edges: EdgeResponse[];
  total: number;
  offset: number;
  limit: number;
}

// ========== Batch Types (ADR-089 Phase 1b) ==========

/**
 * Concept definition for batch creation.
 */
export interface BatchConceptCreate {
  label: string;
  description?: string;
  search_terms?: string[];
}

/**
 * Edge definition for batch creation.
 * References concepts by label (not ID) to allow referencing
 * concepts created in the same batch request.
 */
export interface BatchEdgeCreate {
  from_label: string;
  to_label: string;
  relationship_type: string;
  category?: RelationshipCategory;
  confidence?: number;
}

/**
 * Request to batch create concepts and edges.
 */
export interface BatchCreateRequest {
  ontology: string;
  matching_mode?: MatchingMode;
  creation_method?: CreationMethod;
  concepts?: BatchConceptCreate[];
  edges?: BatchEdgeCreate[];
}

/**
 * Result for a single item in the batch.
 */
export interface BatchItemResult {
  label: string;
  status: 'created' | 'matched' | 'error';
  id?: string;
  error?: string;
}

/**
 * Response from batch creation.
 */
export interface BatchCreateResponse {
  concepts_created: number;
  concepts_matched: number;
  edges_created: number;
  errors: string[];
  concept_results: BatchItemResult[];
  edge_results: BatchItemResult[];
}
