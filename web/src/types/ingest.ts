/**
 * Ingestion Types
 *
 * Types matching the REST API for document ingestion.
 * Supports file upload, text ingestion, and image ingestion (ADR-057).
 */

import type { JobResult, JobAnalysis } from './jobs';

// Chunking options for document processing
export interface IngestionOptions {
  target_words?: number;   // Default: 1000
  min_words?: number;
  max_words?: number;
  overlap_words?: number;  // Default: 200
}

// Base request fields shared across ingest types
export interface IngestRequestBase {
  ontology: string;
  filename?: string;
  force?: boolean;           // Bypass duplicate detection
  auto_approve?: boolean;    // ADR-014: Skip approval step
  processing_mode?: 'serial' | 'parallel';
  // ADR-051: Source provenance metadata
  source_type?: 'file' | 'stdin' | 'mcp' | 'api' | 'web';
  source_path?: string;
  source_hostname?: string;
}

// File ingestion request
export interface IngestFileRequest extends IngestRequestBase {
  options?: IngestionOptions;
}

// Text ingestion request
export interface IngestTextRequest extends IngestRequestBase {
  text: string;
  options?: IngestionOptions;
}

// Image ingestion request (ADR-057)
export interface IngestImageRequest extends IngestRequestBase {
  vision_provider?: 'openai' | 'anthropic' | 'ollama';
  vision_model?: string;
}

// Job submission response (success case)
export interface JobSubmitResponse {
  job_id: string;
  status: string;
  content_hash: string;
  position?: number;
  message?: string;
}

// Duplicate detection response
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

// Union type for ingest response (can be either)
export type IngestResponse = JobSubmitResponse | DuplicateJobResponse;

// Helper type guard
export function isDuplicateResponse(response: IngestResponse): response is DuplicateJobResponse {
  return 'duplicate' in response && response.duplicate === true;
}

// Ontology types (for selector)
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

// File validation
export const SUPPORTED_TEXT_EXTENSIONS = ['.txt', '.md', '.rst', '.pdf'];
export const SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'];
export const MAX_FILE_SIZE_MB = 10;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

export function isImageFile(filename: string): boolean {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return SUPPORTED_IMAGE_EXTENSIONS.includes(ext);
}

export function isTextFile(filename: string): boolean {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return SUPPORTED_TEXT_EXTENSIONS.includes(ext);
}

export function isSupportedFile(filename: string): boolean {
  return isImageFile(filename) || isTextFile(filename);
}
