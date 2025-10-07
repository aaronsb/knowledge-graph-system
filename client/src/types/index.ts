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
  sources_created?: number;
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
}

export interface JobStatus {
  job_id: string;
  job_type: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress?: JobProgress;
  result?: JobResult;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  content_hash?: string;
  ontology?: string;
  client_id?: string;
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
  options?: IngestionOptions;
}

export interface ApiConfig {
  baseUrl: string;
  clientId?: string;
  apiKey?: string;
}
