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
  progress?: JobProgress;
  result?: JobResult;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  content_hash?: string;
  ontology?: string;
  client_id?: string;
  processing_mode?: string;  // Serial or parallel processing
  analysis?: any;  // Pre-ingestion analysis (ADR-014)
  approved_at?: string;
  approved_by?: string;
  expires_at?: string;
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
}

export interface ConceptSearchResult {
  concept_id: string;
  label: string;
  score: number;
  documents: string[];
  evidence_count: number;
}

export interface SearchResponse {
  query: string;
  count: number;
  results: ConceptSearchResult[];
  below_threshold_count?: number;
  suggested_threshold?: number;
  threshold_used?: number;
}

export interface ConceptInstance {
  quote: string;
  document: string;
  paragraph: number;
  source_id: string;
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
  search_terms: string[];
  documents: string[];
  instances: ConceptInstance[];
  relationships: ConceptRelationship[];
}

export interface RelatedConceptsRequest {
  concept_id: string;
  relationship_types?: string[];
  max_depth?: number;
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
}

export interface PathNode {
  id: string;
  label: string;
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
