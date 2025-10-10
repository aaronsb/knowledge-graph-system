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
  FindConnectionBySearchRequest,
  FindConnectionBySearchResponse,
  DatabaseStatsResponse,
  DatabaseInfoResponse,
  DatabaseHealthResponse,
  OntologyListResponse,
  OntologyInfoResponse,
  OntologyFilesResponse,
  OntologyDeleteResponse,
  SystemStatusResponse,
  BackupRequest,
  BackupResponse,
  ListBackupsResponse,
  RestoreRequest,
  RestoreResponse,
  ResetRequest,
  ResetResponse
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

    if (request.auto_approve) {
      form.append('auto_approve', 'true');
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

    if (request.auto_approve) {
      form.append('auto_approve', 'true');
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
   * Get job status (alias for getJob)
   */
  async getJobStatus(jobId: string): Promise<JobStatus> {
    return this.getJob(jobId);
  }

  /**
   * List jobs
   */
  async listJobs(
    status?: string,
    clientId?: string,
    limit: number = 50
  ): Promise<JobStatus[]> {
    const params: any = { limit };
    if (status) {
      params.status = status;
    }
    if (clientId) {
      params.client_id = clientId;
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
   * Approve a job for processing (ADR-014)
   */
  async approveJob(jobId: string): Promise<{ job_id: string; status: string; message: string }> {
    const response = await this.client.post(`/jobs/${jobId}/approve`);
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

      // Check if job is terminal or awaiting approval
      // Stop polling if job needs user action (approval) or is complete
      if (['completed', 'failed', 'cancelled', 'awaiting_approval'].includes(job.status)) {
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

  /**
   * Find shortest paths between concepts using natural language queries
   */
  async findConnectionBySearch(request: FindConnectionBySearchRequest): Promise<FindConnectionBySearchResponse> {
    const response = await this.client.post('/query/connect-by-search', request);
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

  // ========== Admin Methods ==========

  /**
   * Get system status
   */
  async getSystemStatus(): Promise<SystemStatusResponse> {
    const response = await this.client.get('/admin/status');
    return response.data;
  }

  /**
   * List available backup files
   */
  async listBackups(): Promise<ListBackupsResponse> {
    const response = await this.client.get('/admin/backups');
    return response.data;
  }

  /**
   * Create a database backup (ADR-015 Phase 2: Streaming Download)
   *
   * Downloads backup as a stream and saves to specified path.
   * Provides progress callback for tracking download.
   *
   * @param request Backup request (type and optional ontology)
   * @param savePath Where to save the backup file
   * @param onProgress Optional callback for progress updates (bytes downloaded, total bytes, percent)
   * @returns Metadata about the downloaded backup
   */
  async createBackup(
    request: BackupRequest,
    savePath: string,
    onProgress?: (downloaded: number, total: number, percent: number) => void
  ): Promise<{ filename: string; path: string; size: number }> {
    const response = await this.client.post('/admin/backup', request, {
      responseType: 'stream'
    });

    // Extract filename from Content-Disposition header
    const contentDisposition = response.headers['content-disposition'];
    const filenameMatch = contentDisposition?.match(/filename=(.+)/);
    const filename = filenameMatch ? filenameMatch[1] : 'backup.json';

    // Get content length if available
    const totalBytes = parseInt(response.headers['content-length'] || '0', 10);

    // Create write stream
    const writer = fs.createWriteStream(savePath);
    let downloadedBytes = 0;

    // Pipe response to file with progress tracking
    response.data.on('data', (chunk: Buffer) => {
      downloadedBytes += chunk.length;
      if (onProgress && totalBytes > 0) {
        const percent = Math.round((downloadedBytes / totalBytes) * 100);
        onProgress(downloadedBytes, totalBytes, percent);
      }
    });

    // Wait for download to complete
    await new Promise<void>((resolve, reject) => {
      response.data.pipe(writer);
      writer.on('finish', resolve);
      writer.on('error', reject);
      response.data.on('error', reject);
    });

    // Rename file to use server-provided filename if different
    const finalPath = savePath.replace(/[^/]+\.json$/, filename);
    if (finalPath !== savePath && fs.existsSync(savePath)) {
      fs.renameSync(savePath, finalPath);
    }

    return {
      filename,
      path: finalPath,
      size: downloadedBytes
    };
  }

  /**
   * Restore a database backup (ADR-015 Phase 2: Multipart Upload)
   *
   * Uploads backup file as multipart/form-data and queues restore job.
   * Server validates backup, creates checkpoint, then executes restore with progress tracking.
   *
   * @param backupFilePath Path to backup JSON file
   * @param username Username for authentication
   * @param password Password for authentication
   * @param overwrite Whether to overwrite existing data
   * @param handleExternalDeps How to handle external dependencies ('prune', 'stitch', 'defer')
   * @param onUploadProgress Optional callback for upload progress (bytes uploaded, total bytes, percent)
   * @returns Job ID and initial status for polling restore progress
   */
  async restoreBackup(
    backupFilePath: string,
    username: string,
    password: string,
    overwrite: boolean = false,
    handleExternalDeps: string = 'prune',
    onUploadProgress?: (uploaded: number, total: number, percent: number) => void
  ): Promise<{ job_id: string; status: string; message: string; backup_stats: any; integrity_warnings: number }> {
    const form = new FormData();
    form.append('file', fs.createReadStream(backupFilePath));
    form.append('username', username);
    form.append('password', password);
    form.append('overwrite', String(overwrite));
    form.append('handle_external_deps', handleExternalDeps);

    const response = await this.client.post('/admin/restore', form, {
      headers: form.getHeaders(),
      onUploadProgress: (progressEvent) => {
        if (onUploadProgress && progressEvent.total) {
          const uploaded = progressEvent.loaded;
          const total = progressEvent.total;
          const percent = Math.round((uploaded / total) * 100);
          onUploadProgress(uploaded, total, percent);
        }
      }
    });

    return response.data;
  }

  /**
   * Reset database (destructive - requires authentication)
   */
  async resetDatabase(request: ResetRequest): Promise<ResetResponse> {
    const response = await this.client.post('/admin/reset', request);
    return response.data;
  }

  /**
   * Get job scheduler status and statistics (ADR-014)
   */
  async getSchedulerStatus(): Promise<any> {
    const response = await this.client.get('/admin/scheduler/status');
    return response.data;
  }

  /**
   * Manually trigger job scheduler cleanup (ADR-014)
   */
  async triggerSchedulerCleanup(): Promise<any> {
    const response = await this.client.post('/admin/scheduler/cleanup');
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
