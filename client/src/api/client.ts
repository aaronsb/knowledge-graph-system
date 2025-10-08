/**
 * Knowledge Graph API Client
 *
 * Wraps HTTP calls to the FastAPI server
 */

import axios, { AxiosInstance } from 'axios';
import FormData from 'form-data';
import * as fs from 'fs';
import {
  ApiConfig,
  JobStatus,
  JobSubmitResponse,
  DuplicateJobResponse,
  IngestRequest,
  SearchRequest,
  SearchResponse,
  ConceptDetailsResponse,
  RelatedConceptsRequest,
  RelatedConceptsResponse,
  FindConnectionRequest,
  FindConnectionResponse,
  DatabaseStatsResponse,
  DatabaseInfoResponse,
  DatabaseHealthResponse,
  OntologyListResponse,
  OntologyInfoResponse,
  OntologyFilesResponse,
  OntologyDeleteResponse
} from '../types';

export class KnowledgeGraphClient {
  private client: AxiosInstance;
  private config: ApiConfig;

  constructor(config: ApiConfig) {
    this.config = config;
    this.client = axios.create({
      baseURL: config.baseUrl,
      headers: {
        ...(config.clientId && { 'X-Client-ID': config.clientId }),
        ...(config.apiKey && { 'X-API-Key': config.apiKey }),
      },
    });
  }

  /**
   * Health check
   */
  async health(): Promise<{ status: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  /**
   * Get API info
   */
  async info(): Promise<any> {
    const response = await this.client.get('/');
    return response.data;
  }

  /**
   * Ingest a document file
   */
  async ingestFile(
    filePath: string,
    request: IngestRequest
  ): Promise<JobSubmitResponse | DuplicateJobResponse> {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('ontology', request.ontology);

    if (request.filename) {
      form.append('filename', request.filename);
    }

    if (request.force) {
      form.append('force', 'true');
    }

    if (request.options) {
      if (request.options.target_words !== undefined) {
        form.append('target_words', String(request.options.target_words));
      }
      if (request.options.min_words !== undefined) {
        form.append('min_words', String(request.options.min_words));
      }
      if (request.options.max_words !== undefined) {
        form.append('max_words', String(request.options.max_words));
      }
      if (request.options.overlap_words !== undefined) {
        form.append('overlap_words', String(request.options.overlap_words));
      }
    }

    const response = await this.client.post('/ingest', form, {
      headers: form.getHeaders(),
    });

    return response.data;
  }

  /**
   * Ingest raw text
   */
  async ingestText(
    text: string,
    request: IngestRequest
  ): Promise<JobSubmitResponse | DuplicateJobResponse> {
    const form = new FormData();
    form.append('text', text);
    form.append('ontology', request.ontology);

    if (request.filename) {
      form.append('filename', request.filename);
    }

    if (request.force) {
      form.append('force', 'true');
    }

    if (request.options?.target_words !== undefined) {
      form.append('target_words', String(request.options.target_words));
    }

    if (request.options?.overlap_words !== undefined) {
      form.append('overlap_words', String(request.options.overlap_words));
    }

    const response = await this.client.post('/ingest/text', form, {
      headers: form.getHeaders(),
    });

    return response.data;
  }

  /**
   * Get job status
   */
  async getJob(jobId: string): Promise<JobStatus> {
    const response = await this.client.get(`/jobs/${jobId}`);
    return response.data;
  }

  /**
   * List jobs
   */
  async listJobs(
    status?: string,
    limit: number = 50
  ): Promise<JobStatus[]> {
    const params: any = { limit };
    if (status) {
      params.status = status;
    }

    const response = await this.client.get('/jobs', { params });
    return response.data;
  }

  /**
   * Cancel a job
   */
  async cancelJob(jobId: string): Promise<{ job_id: string; cancelled: boolean; message: string }> {
    const response = await this.client.delete(`/jobs/${jobId}`);
    return response.data;
  }

  /**
   * Poll job until completion
   *
   * @param jobId Job ID to poll
   * @param onProgress Optional callback for progress updates
   * @param pollInterval Poll interval in ms (default: 2000)
   * @returns Final job status
   */
  async pollJob(
    jobId: string,
    onProgress?: (job: JobStatus) => void,
    pollInterval: number = 2000
  ): Promise<JobStatus> {
    while (true) {
      const job = await this.getJob(jobId);

      if (onProgress) {
        onProgress(job);
      }

      // Check if job is terminal
      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        return job;
      }

      // Wait before polling again
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
  }

  // ========== Query Methods ==========

  /**
   * Search for concepts using semantic similarity
   */
  async searchConcepts(request: SearchRequest): Promise<SearchResponse> {
    const response = await this.client.post('/query/search', request);
    return response.data;
  }

  /**
   * Get detailed information about a concept
   */
  async getConceptDetails(conceptId: string): Promise<ConceptDetailsResponse> {
    const response = await this.client.get(`/query/concept/${conceptId}`);
    return response.data;
  }

  /**
   * Find concepts related through graph traversal
   */
  async findRelatedConcepts(request: RelatedConceptsRequest): Promise<RelatedConceptsResponse> {
    const response = await this.client.post('/query/related', request);
    return response.data;
  }

  /**
   * Find shortest paths between two concepts
   */
  async findConnection(request: FindConnectionRequest): Promise<FindConnectionResponse> {
    const response = await this.client.post('/query/connect', request);
    return response.data;
  }

  // ========== Database Methods ==========

  /**
   * Get database statistics
   */
  async getDatabaseStats(): Promise<DatabaseStatsResponse> {
    const response = await this.client.get('/database/stats');
    return response.data;
  }

  /**
   * Get database connection information
   */
  async getDatabaseInfo(): Promise<DatabaseInfoResponse> {
    const response = await this.client.get('/database/info');
    return response.data;
  }

  /**
   * Check database health
   */
  async getDatabaseHealth(): Promise<DatabaseHealthResponse> {
    const response = await this.client.get('/database/health');
    return response.data;
  }

  // ========== Ontology Methods ==========

  /**
   * List all ontologies
   */
  async listOntologies(): Promise<OntologyListResponse> {
    const response = await this.client.get('/ontology/');
    return response.data;
  }

  /**
   * Get ontology information
   */
  async getOntologyInfo(ontologyName: string): Promise<OntologyInfoResponse> {
    const response = await this.client.get(`/ontology/${encodeURIComponent(ontologyName)}`);
    return response.data;
  }

  /**
   * List files in an ontology
   */
  async getOntologyFiles(ontologyName: string): Promise<OntologyFilesResponse> {
    const response = await this.client.get(`/ontology/${encodeURIComponent(ontologyName)}/files`);
    return response.data;
  }

  /**
   * Delete an ontology
   */
  async deleteOntology(
    ontologyName: string,
    force: boolean = false
  ): Promise<OntologyDeleteResponse> {
    const response = await this.client.delete(`/ontology/${encodeURIComponent(ontologyName)}`, {
      params: { force }
    });
    return response.data;
  }
}

/**
 * Create a client from environment variables and config file
 * Priority: CLI flags > env vars > config file > defaults
 */
export function createClientFromEnv(): KnowledgeGraphClient {
  // Lazy load config to avoid circular dependencies
  let config: any = null;
  try {
    const { getConfig } = require('../lib/config');
    config = getConfig();
  } catch (e) {
    // Config not available, use env vars only
  }

  return new KnowledgeGraphClient({
    baseUrl: process.env.KG_API_URL || config?.getApiUrl() || 'http://localhost:8000',
    clientId: process.env.KG_CLIENT_ID || config?.getClientId(),
    apiKey: process.env.KG_API_KEY || config?.getApiKey(),
  });
}
