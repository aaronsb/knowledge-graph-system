/**
 * Job Types
 *
 * Types matching the REST API responses for job management.
 * Based on ADR-014 approval workflow.
 */

// Job status values following the ADR-014 lifecycle
export type JobStatusValue =
  | 'pending'           // Initial state, analysis running
  | 'awaiting_approval' // Analysis complete, requires user approval
  | 'approved'          // User approved, waiting to process
  | 'queued'            // Legacy state (same as approved)
  | 'processing'        // Currently running (legacy/SQLite name)
  | 'running'           // Currently running (PostgreSQL name)
  | 'completed'         // Successfully finished
  | 'failed'            // Error occurred
  | 'cancelled';        // User cancelled or expired

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
  // Restore-specific progress fields
  items_total?: number;
  items_processed?: number;
  message?: string;
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

// Pre-ingestion analysis (ADR-014)
export interface CostEstimate {
  extraction: {
    model: string;
    tokens_low: number;
    tokens_high: number;
    cost_low: number;
    cost_high: number;
  };
  embeddings: {
    model: string;
    concepts_low: number;
    concepts_high: number;
    cost_low: number;
    cost_high: number;
  };
  total: {
    cost_low: number;
    cost_high: number;
  };
}

export interface FileStats {
  filename: string;
  size_human: string;
  word_count: number;
  estimated_chunks: number;
}

export interface JobAnalysis {
  file_stats?: FileStats;
  cost_estimate?: CostEstimate;
  warnings?: string[];
}

export interface JobStatus {
  job_id: string;
  job_type: string;
  status: JobStatusValue;
  user_id?: number;
  username?: string;
  progress?: JobProgress;
  result?: JobResult;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  content_hash?: string;
  ontology?: string;
  processing_mode?: string;
  analysis?: JobAnalysis;
  approved_at?: string;
  approved_by?: string;
  expires_at?: string;
  // ADR-051: Source provenance metadata
  filename?: string;
  source_type?: string;
  source_path?: string;
  source_hostname?: string;
}

export interface JobApproveResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobCancelResponse {
  job_id: string;
  cancelled: boolean;
  message: string;
}

export interface JobsClearResponse {
  success: boolean;
  jobs_deleted: number;
  message: string;
}

// Delete single job response
export interface JobDeleteResponse {
  job_id: string;
  deleted?: boolean;
  cancelled?: boolean;
  message: string;
}

// Bulk delete with filters
export interface JobsDeleteFilters {
  status?: string;
  system?: boolean;
  olderThan?: string;  // '1h', '24h', '7d', '30d'
  jobType?: string;
}

export interface JobsDeleteResponse {
  success?: boolean;
  dry_run?: boolean;
  jobs_deleted?: number;
  jobs_to_delete?: number;
  jobs?: Array<{
    job_id: string;
    job_type: string;
    status: string;
    ontology: string | null;
    created_at: string;
  }>;
  filters?: Record<string, unknown>;
  message: string;
}

// SSE Event types for streaming
export interface JobProgressEvent {
  stage: string;
  percent?: number;
  chunks_processed?: number;
  chunks_total?: number;
  concepts_created?: number;
  concepts_linked?: number;
  relationships_created?: number;
}

export interface JobCompletedEvent {
  status: string;
  stats?: JobStats;
  cost?: JobCost;
}

export interface JobFailedEvent {
  error: string;
}

// List filters
export interface JobListFilters {
  status?: JobStatusValue;
  user_id?: number;
  limit?: number;
  offset?: number;
}
