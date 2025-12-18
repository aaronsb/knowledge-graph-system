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
  SourceSearchRequest,
  SourceSearchResponse,
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
  OntologyRenameResponse,
  SystemStatusResponse,
  BackupRequest,
  BackupResponse,
  ListBackupsResponse,
  RestoreRequest,
  RestoreResponse,
  ResetRequest,
  ResetResponse,
  ResourceCreate,
  ResourceRead,
  ResourceUpdate,
  RoleCreate,
  RoleRead,
  RoleUpdate,
  PermissionCreate,
  PermissionRead,
  UserRoleAssign,
  UserRoleRead,
  PermissionCheckRequest,
  PermissionCheckResponse
} from '../types';

export class KnowledgeGraphClient {
  private client: AxiosInstance;
  private config: ApiConfig;
  private mcpJwtToken: string | null = null;  // JWT token for MCP server authentication

  constructor(config: ApiConfig) {
    this.config = config;
    this.client = axios.create({
      baseURL: config.baseUrl,
      headers: {
        ...(config.clientId && { 'X-Client-ID': config.clientId }),
        ...(config.apiKey && { 'X-API-Key': config.apiKey }),
      },
    });

    // ADR-054: Add request interceptor for OAuth authentication
    this.client.interceptors.request.use(async (requestConfig) => {
      // Priority 1: Use MCP JWT token if set (for MCP server - legacy)
      if (this.mcpJwtToken) {
        requestConfig.headers.Authorization = `Bearer ${this.mcpJwtToken}`;
        return requestConfig;
      }

      // Priority 2: Get OAuth client credentials from config and fetch fresh access token
      try {
        const { getConfig } = require('../lib/config');
        const { AuthClient } = require('../lib/auth/auth-client');
        const configManager = getConfig();

        // Check for OAuth client credentials (ADR-054)
        const oauthCreds = configManager.getOAuthCredentials();
        if (oauthCreds) {
          // Get fresh access token using client credentials grant
          const authClient = new AuthClient(this.config.baseUrl);
          const tokenResponse = await authClient.getOAuthToken({
            grant_type: 'client_credentials',
            client_id: oauthCreds.client_id,
            client_secret: oauthCreds.client_secret,
            scope: oauthCreds.scopes.join(' ')
          });

          requestConfig.headers.Authorization = `Bearer ${tokenResponse.access_token}`;
        }
      } catch (error) {
        // Config not available or OAuth credentials not found - continue without auth
      }

      return requestConfig;
    });

    // ADR-054: Add response interceptor for 401 errors (invalid OAuth token)
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Check if we have OAuth credentials
          try {
            const { getConfig } = require('../lib/config');
            const configManager = getConfig();

            if (configManager.isAuthenticated()) {
              // User has OAuth credentials but got 401 - client may be revoked
              console.error('\n\x1b[31m❌ Authentication failed\x1b[0m');
              console.error('   Your OAuth credentials may be invalid or revoked.');
              console.error('   Please login again:');
              console.error('     \x1b[36mkg login\x1b[0m\n');
            }
          } catch (e) {
            // Ignore errors from config loading
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Set JWT token for MCP server authentication
   *
   * This allows the MCP server to inject a JWT token obtained via automatic login,
   * making authentication transparent to the AI using the MCP tools.
   *
   * @param token JWT access token from login response
   */
  setMcpJwtToken(token: string | null): void {
    this.mcpJwtToken = token;
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

    if (request.processing_mode) {
      form.append('processing_mode', request.processing_mode);
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

    // ADR-051: Source provenance metadata
    if (request.source_type) {
      form.append('source_type', request.source_type);
    }
    if (request.source_path) {
      form.append('source_path', request.source_path);
    }
    if (request.source_hostname) {
      form.append('source_hostname', request.source_hostname);
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

    if (request.processing_mode) {
      form.append('processing_mode', request.processing_mode);
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
   * Ingest image (ADR-057)
   */
  async ingestImage(
    filePath: string,
    request: IngestRequest & {
      vision_provider?: string;
      vision_model?: string;
    }
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

    if (request.vision_provider) {
      form.append('vision_provider', request.vision_provider);
    }

    if (request.vision_model) {
      form.append('vision_model', request.vision_model);
    }

    if (request.source_type) {
      form.append('source_type', request.source_type);
    }

    if (request.source_path) {
      form.append('source_path', request.source_path);
    }

    if (request.source_hostname) {
      form.append('source_hostname', request.source_hostname);
    }

    const response = await this.client.post('/ingest/image', form, {
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
    limit: number = 50,
    offset: number = 0
  ): Promise<JobStatus[]> {
    const params: any = { limit, offset };
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
   * Clear all jobs (nuclear option - requires confirmation)
   */
  async clearAllJobs(confirm: boolean = false): Promise<{ success: boolean; jobs_deleted: number; message: string }> {
    const response = await this.client.delete('/jobs', {
      params: { confirm }
    });
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
   * Search source text using semantic similarity (ADR-068 Phase 3)
   */
  async searchSources(request: SourceSearchRequest): Promise<SourceSearchResponse> {
    const response = await this.client.post('/query/sources/search', request);
    return response.data;
  }

  /**
   * Get detailed information about a concept
   */
  async getConceptDetails(
    conceptId: string,
    includeGrounding: boolean = false,
    includeDiversity: boolean = false,
    diversityMaxHops: number = 2
  ): Promise<ConceptDetailsResponse> {
    const response = await this.client.get(`/query/concept/${conceptId}`, {
      params: {
        include_grounding: includeGrounding,
        include_diversity: includeDiversity,
        diversity_max_hops: diversityMaxHops
      }
    });
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

  /**
   * Get image for a source node (ADR-057)
   * @param sourceId - Source ID from concept instance
   * @returns Image as Buffer (binary data)
   */
  async getSourceImage(sourceId: string): Promise<Buffer> {
    const response = await this.client.get(`/sources/${sourceId}/image`, {
      responseType: 'arraybuffer',
    });
    return Buffer.from(response.data);
  }

  /**
   * Get image for a source node as base64 string (ADR-057)
   * Useful for MCP server to return images to Claude
   * @param sourceId - Source ID from concept instance
   * @returns Base64-encoded image string
   */
  async getSourceImageBase64(sourceId: string): Promise<string> {
    const buffer = await this.getSourceImage(sourceId);
    return buffer.toString('base64');
  }

  /**
   * List source nodes with optional filtering
   * @param options - Filter and pagination options
   * @returns List of sources with metadata
   */
  async listSources(options: {
    ontology?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{
    sources: Array<{
      source_id: string;
      document: string;
      paragraph: number;
      content_type?: string;
      has_garage_key: boolean;
    }>;
    total: number;
    limit: number;
    offset: number;
  }> {
    const params = new URLSearchParams();
    if (options.ontology) params.append('ontology', options.ontology);
    if (options.limit) params.append('limit', options.limit.toString());
    if (options.offset) params.append('offset', options.offset.toString());

    const response = await this.client.get(`/sources?${params.toString()}`);
    return response.data;
  }

  /**
   * Get original document for a source node (ADR-081)
   * @param sourceId - Source ID from search results or concept details
   * @returns Document content as Buffer (binary data)
   */
  async getSourceDocument(sourceId: string): Promise<Buffer> {
    const response = await this.client.get(`/sources/${sourceId}/document`, {
      responseType: 'arraybuffer',
    });
    return Buffer.from(response.data);
  }

  /**
   * Get source metadata
   * @param sourceId - Source ID
   * @returns Source metadata including garage_key, content_hash, etc.
   */
  async getSourceMetadata(sourceId: string): Promise<{
    source_id: string;
    document: string;
    paragraph: number;
    full_text: string;
    file_path?: string;
    content_type?: string;
    storage_key?: string;
    garage_key?: string;
    content_hash?: string;
    char_offset_start?: number;
    char_offset_end?: number;
    chunk_index?: number;
    has_visual_embedding: boolean;
    has_text_embedding: boolean;
  }> {
    const response = await this.client.get(`/sources/${sourceId}`);
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

  /**
   * Execute a custom cypher query (ADR-048)
   * @param query - openCypher/GQL query string
   * @param params - Optional query parameters
   * @param namespace - Optional namespace: 'concept', 'vocab', or null for raw
   */
  async executeCypherQuery(query: string, params?: Record<string, any>, namespace?: string | null): Promise<any> {
    const response = await this.client.post('/database/query', {
      query,
      params: params || null,
      namespace: namespace === undefined ? null : namespace
    });
    return response.data;
  }

  /**
   * Get all graph metrics counters organized by type (ADR-079)
   */
  async getDatabaseCounters(): Promise<any> {
    const response = await this.client.get('/database/counters');
    return response.data;
  }

  /**
   * Refresh graph metrics counters from current graph state (ADR-079)
   */
  async refreshDatabaseCounters(): Promise<any> {
    const response = await this.client.post('/database/counters/refresh');
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

  /**
   * Rename an ontology
   */
  async renameOntology(
    oldName: string,
    newName: string
  ): Promise<OntologyRenameResponse> {
    const response = await this.client.post(`/ontology/${encodeURIComponent(oldName)}/rename`, {
      new_name: newName
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

  /**
   * Regenerate embeddings for concept nodes in the graph
   */
  async regenerateConceptEmbeddings(params: {
    only_missing?: boolean;
    ontology?: string;
    limit?: number;
  }): Promise<any> {
    const queryParams = new URLSearchParams();
    if (params.only_missing) {
      queryParams.append('only_missing', 'true');
    }
    if (params.ontology) {
      queryParams.append('ontology', params.ontology);
    }
    if (params.limit) {
      queryParams.append('limit', params.limit.toString());
    }

    const url = `/admin/regenerate-concept-embeddings${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await this.client.post(url);
    return response.data;
  }

  /**
   * Unified embedding regeneration for all graph text entities (ADR-068 Phase 4).
   *
   * Regenerate embeddings for concepts, sources, or vocabulary (relationship types).
   * Useful for model migrations, fixing missing/corrupted embeddings, or bulk regeneration.
   */
  async regenerateEmbeddings(params: {
    embedding_type: 'concept' | 'source' | 'vocabulary' | 'all';
    only_missing?: boolean;
    only_incompatible?: boolean;
    ontology?: string;
    limit?: number;
  }): Promise<any> {
    const queryParams = new URLSearchParams();
    queryParams.append('embedding_type', params.embedding_type);

    if (params.only_missing) {
      queryParams.append('only_missing', 'true');
    }
    if (params.only_incompatible) {
      queryParams.append('only_incompatible', 'true');
    }
    if (params.ontology) {
      queryParams.append('ontology', params.ontology);
    }
    if (params.limit) {
      queryParams.append('limit', params.limit.toString());
    }

    const url = `/admin/embedding/regenerate?${queryParams.toString()}`;
    const response = await this.client.post(url);
    return response.data;
  }

  /**
   * Get comprehensive embedding status for all graph text entities.
   *
   * Shows count, percentage, compatibility verification, and hash verification
   * for embeddings across concepts, sources, vocabulary, and images.
   */
  async getEmbeddingStatus(ontology?: string): Promise<any> {
    const queryParams = new URLSearchParams();
    if (ontology) {
      queryParams.append('ontology', ontology);
    }

    const url = `/admin/embedding/status${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await this.client.get(url);
    return response.data;
  }

  // ========== RBAC Methods (ADR-028) ==========

  /**
   * List all registered resource types
   */
  async listResources(): Promise<ResourceRead[]> {
    const response = await this.client.get('/rbac/resources');
    return response.data;
  }

  /**
   * Get a specific resource type
   */
  async getResource(resourceType: string): Promise<ResourceRead> {
    const response = await this.client.get(`/rbac/resources/${resourceType}`);
    return response.data;
  }

  /**
   * Register a new resource type
   */
  async createResource(resource: ResourceCreate): Promise<ResourceRead> {
    const response = await this.client.post('/rbac/resources', resource);
    return response.data;
  }

  /**
   * Update a resource type
   */
  async updateResource(resourceType: string, update: ResourceUpdate): Promise<ResourceRead> {
    const response = await this.client.put(`/rbac/resources/${resourceType}`, update);
    return response.data;
  }

  /**
   * Delete a resource type
   */
  async deleteResource(resourceType: string): Promise<void> {
    await this.client.delete(`/rbac/resources/${resourceType}`);
  }

  /**
   * List all roles
   */
  async listRoles(includeInactive: boolean = false): Promise<RoleRead[]> {
    const response = await this.client.get('/rbac/roles', {
      params: { include_inactive: includeInactive }
    });
    return response.data;
  }

  /**
   * Get a specific role
   */
  async getRole(roleName: string): Promise<RoleRead> {
    const response = await this.client.get(`/rbac/roles/${roleName}`);
    return response.data;
  }

  /**
   * Create a new role
   */
  async createRole(role: RoleCreate): Promise<RoleRead> {
    const response = await this.client.post('/rbac/roles', role);
    return response.data;
  }

  /**
   * Update a role
   */
  async updateRole(roleName: string, update: RoleUpdate): Promise<RoleRead> {
    const response = await this.client.put(`/rbac/roles/${roleName}`, update);
    return response.data;
  }

  /**
   * Delete a role
   */
  async deleteRole(roleName: string): Promise<void> {
    await this.client.delete(`/rbac/roles/${roleName}`);
  }

  /**
   * List permissions (optionally filtered)
   */
  async listPermissions(roleName?: string, resourceType?: string): Promise<PermissionRead[]> {
    const params: any = {};
    if (roleName) params.role_name = roleName;
    if (resourceType) params.resource_type = resourceType;

    const response = await this.client.get('/rbac/permissions', { params });
    return response.data;
  }

  /**
   * Grant a permission to a role
   */
  async createPermission(permission: PermissionCreate): Promise<PermissionRead> {
    const response = await this.client.post('/rbac/permissions', permission);
    return response.data;
  }

  /**
   * Revoke a permission from a role
   */
  async deletePermission(permissionId: number): Promise<void> {
    await this.client.delete(`/rbac/permissions/${permissionId}`);
  }

  /**
   * List role assignments for a user
   */
  async listUserRoles(userId: number): Promise<UserRoleRead[]> {
    const response = await this.client.get(`/rbac/user-roles/${userId}`);
    return response.data;
  }

  /**
   * Assign a role to a user
   */
  async assignUserRole(assignment: UserRoleAssign): Promise<UserRoleRead> {
    const response = await this.client.post('/rbac/user-roles', assignment);
    return response.data;
  }

  /**
   * Revoke a role assignment from a user
   */
  async revokeUserRole(assignmentId: number): Promise<void> {
    await this.client.delete(`/rbac/user-roles/${assignmentId}`);
  }

  /**
   * Check if a user has a specific permission
   */
  async checkPermission(request: PermissionCheckRequest): Promise<PermissionCheckResponse> {
    const response = await this.client.post('/rbac/check-permission', request);
    return response.data;
  }

  // ========== Vocabulary Methods (ADR-032) ==========

  /**
   * Get current vocabulary status
   */
  async getVocabularyStatus(): Promise<any> {
    const response = await this.client.get('/vocabulary/status');
    return response.data;
  }

  /**
   * List all edge types with statistics
   */
  async listEdgeTypes(includeInactive: boolean = false, includeBuiltin: boolean = true): Promise<any> {
    const response = await this.client.get('/vocabulary/types', {
      params: {
        include_inactive: includeInactive,
        include_builtin: includeBuiltin
      }
    });
    return response.data;
  }

  /**
   * Manually add a new edge type (curator action)
   */
  async addEdgeType(request: {
    relationship_type: string;
    category: string;
    description?: string;
    is_builtin?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/types', request);
    return response.data;
  }

  /**
   * Generate vocabulary optimization recommendations
   */
  async getVocabularyRecommendations(): Promise<any> {
    const response = await this.client.get('/vocabulary/recommendations');
    return response.data;
  }

  /**
   * Execute all auto-approved recommendations
   */
  async executeAutoRecommendations(): Promise<any> {
    const response = await this.client.post('/vocabulary/recommendations/execute');
    return response.data;
  }

  /**
   * Get detailed vocabulary analysis
   */
  async getVocabularyAnalysis(): Promise<any> {
    const response = await this.client.get('/vocabulary/analysis');
    return response.data;
  }

  /**
   * Get vocabulary configuration
   */
  async getVocabularyConfig(): Promise<any> {
    const response = await this.client.get('/vocabulary/config');
    return response.data;
  }

  /**
   * Get vocabulary configuration details (admin endpoint)
   */
  async getVocabularyConfigDetail(): Promise<any> {
    const response = await this.client.get('/admin/vocabulary/config');
    return response.data;
  }

  /**
   * Update vocabulary configuration (admin endpoint)
   */
  async updateVocabularyConfig(config: {
    vocab_min?: number;
    vocab_max?: number;
    vocab_emergency?: number;
    pruning_mode?: string;
    aggressiveness_profile?: string;
    auto_expand_enabled?: boolean;
    synonym_threshold_strong?: number;
    synonym_threshold_moderate?: number;
    low_value_threshold?: number;
    consolidation_similarity_threshold?: number;
    updated_by: string;
  }): Promise<any> {
    const response = await this.client.put('/admin/vocabulary/config', config);
    return response.data;
  }

  /**
   * List aggressiveness profiles (admin endpoint)
   */
  async listAggressivenessProfiles(): Promise<any> {
    const response = await this.client.get('/admin/vocabulary/profiles');
    return response.data;
  }

  /**
   * Get specific aggressiveness profile (admin endpoint)
   */
  async getAggressivenessProfile(profileName: string): Promise<any> {
    const response = await this.client.get(`/admin/vocabulary/profiles/${encodeURIComponent(profileName)}`);
    return response.data;
  }

  /**
   * Create custom aggressiveness profile (admin endpoint)
   */
  async createAggressivenessProfile(profile: {
    profile_name: string;
    control_x1: number;
    control_y1: number;
    control_x2: number;
    control_y2: number;
    description: string;
  }): Promise<any> {
    const response = await this.client.post('/admin/vocabulary/profiles', profile);
    return response.data;
  }

  /**
   * Delete custom aggressiveness profile (admin endpoint)
   */
  async deleteAggressivenessProfile(profileName: string): Promise<any> {
    const response = await this.client.delete(`/admin/vocabulary/profiles/${encodeURIComponent(profileName)}`);
    return response.data;
  }

  /**
   * Merge two edge types (curator action)
   */
  async mergeEdgeTypes(request: {
    deprecated_type: string;
    target_type: string;
    performed_by: string;
    reason?: string;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/merge', request);
    return response.data;
  }

  /**
   * Get category similarity scores for a relationship type (ADR-047)
   */
  async getCategoryScores(relationshipType: string): Promise<any> {
    const response = await this.client.get(`/vocabulary/category-scores/${encodeURIComponent(relationshipType)}`);
    return response.data;
  }

  /**
   * Refresh category assignments for vocabulary types (ADR-047)
   */
  async refreshCategories(onlyComputed: boolean = true): Promise<any> {
    const response = await this.client.post('/vocabulary/refresh-categories', {
      only_computed: onlyComputed
    });
    return response.data;
  }

  /**
   * Generate embeddings for vocabulary types (bulk operation)
   */
  async generateVocabularyEmbeddings(
    forceRegenerate: boolean = false,
    onlyMissing: boolean = true
  ): Promise<any> {
    const response = await this.client.post('/vocabulary/generate-embeddings', {
      force_regenerate: forceRegenerate,
      only_missing: onlyMissing
    });
    return response.data;
  }

  /**
   * Run AITL vocabulary consolidation workflow (ADR-032)
   */
  async consolidateVocabulary(request: {
    target_size?: number;
    batch_size?: number;
    auto_execute_threshold?: number;
    dry_run?: boolean;
    prune_unused?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/consolidate', {
      target_size: request.target_size ?? 90,
      batch_size: request.batch_size ?? 1,
      auto_execute_threshold: request.auto_execute_threshold ?? 0.90,
      dry_run: request.dry_run ?? false,
      prune_unused: request.prune_unused ?? true  // Default: prune unused types
    });
    return response.data;
  }

  /**
   * Measure epistemic status for vocabulary types (ADR-065 Phase 2)
   */
  async measureEpistemicStatus(request: {
    sample_size?: number;
    store?: boolean;
    verbose?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/epistemic-status/measure', {
      sample_size: request.sample_size ?? 100,
      store: request.store ?? true,
      verbose: request.verbose ?? false
    });
    return response.data;
  }

  /**
   * List vocabulary types with epistemic status (ADR-065 Phase 2)
   */
  async listEpistemicStatus(statusFilter?: string): Promise<any> {
    const response = await this.client.get('/vocabulary/epistemic-status', {
      params: statusFilter ? { status_filter: statusFilter } : {}
    });
    return response.data;
  }

  /**
   * Get epistemic status for a specific vocabulary type (ADR-065 Phase 2)
   */
  async getEpistemicStatus(relationshipType: string): Promise<any> {
    const response = await this.client.get(`/vocabulary/epistemic-status/${encodeURIComponent(relationshipType)}`);
    return response.data;
  }

  /**
   * Sync missing edge types from graph to vocabulary (ADR-077)
   */
  async syncVocabulary(dryRun: boolean = true): Promise<any> {
    const response = await this.client.post('/vocabulary/sync', {
      dry_run: dryRun
    });
    return response.data;
  }

  // ========== AI Configuration Methods (ADR-039, ADR-041) ==========

  /**
   * Get current embedding configuration (public endpoint)
   */
  async getEmbeddingConfig(): Promise<any> {
    const response = await this.client.get('/embedding/config');
    return response.data;
  }

  /**
   * Get detailed embedding configuration (admin endpoint)
   */
  async getEmbeddingConfigDetail(): Promise<any> {
    const response = await this.client.get('/admin/embedding/config');
    return response.data;
  }

  /**
   * Update embedding configuration (admin endpoint)
   */
  async updateEmbeddingConfig(config: any): Promise<any> {
    const response = await this.client.post('/admin/embedding/config', config);
    return response.data;
  }

  /**
   * Hot reload embedding model (admin endpoint)
   */
  async reloadEmbeddingModel(): Promise<any> {
    const response = await this.client.post('/admin/embedding/config/reload');
    return response.data;
  }

  /**
   * List all embedding configurations (admin endpoint)
   */
  async listEmbeddingConfigs(): Promise<any[]> {
    const response = await this.client.get('/admin/embedding/configs');
    return response.data;
  }

  /**
   * Set protection flags on an embedding config (admin endpoint)
   */
  async protectEmbeddingConfig(configId: number, deleteProtected?: boolean, changeProtected?: boolean): Promise<any> {
    const params: any = {};
    if (deleteProtected !== undefined) params.delete_protected = deleteProtected;
    if (changeProtected !== undefined) params.change_protected = changeProtected;
    const response = await this.client.post(`/admin/embedding/config/${configId}/protect`, null, { params });
    return response.data;
  }

  /**
   * Delete an embedding configuration (admin endpoint)
   */
  async deleteEmbeddingConfig(configId: number): Promise<any> {
    const response = await this.client.delete(`/admin/embedding/config/${configId}`);
    return response.data;
  }

  /**
   * Activate an embedding configuration with automatic protection management (admin endpoint)
   */
  async activateEmbeddingConfig(configId: number, force?: boolean): Promise<any> {
    const params = force ? { force: true } : {};
    const response = await this.client.post(`/admin/embedding/config/${configId}/activate`, null, { params });
    return response.data;
  }

  /**
   * Get current extraction configuration (public endpoint)
   */
  async getExtractionConfig(): Promise<any> {
    const response = await this.client.get('/extraction/config');
    return response.data;
  }

  /**
   * Get detailed extraction configuration (admin endpoint)
   */
  async getExtractionConfigDetail(): Promise<any> {
    const response = await this.client.get('/admin/extraction/config');
    return response.data;
  }

  /**
   * Update extraction configuration (admin endpoint)
   */
  async updateExtractionConfig(config: any): Promise<any> {
    const response = await this.client.post('/admin/extraction/config', config);
    return response.data;
  }

  /**
   * List API keys with validation status (admin endpoint)
   */
  async listApiKeys(): Promise<any[]> {
    const response = await this.client.get('/admin/keys');
    return response.data;
  }

  /**
   * Set API key for a provider (admin endpoint)
   */
  async setApiKey(provider: string, apiKey: string): Promise<any> {
    const formData = new FormData();
    formData.append('api_key', apiKey);

    const response = await this.client.post(`/admin/keys/${provider}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  }

  /**
   * Delete API key for a provider (admin endpoint)
   */
  async deleteApiKey(provider: string): Promise<any> {
    const response = await this.client.delete(`/admin/keys/${provider}`);
    return response.data;
  }

  /**
   * Get similar edge types via embedding similarity (ADR-053)
   */
  async getSimilarTypes(
    relationshipType: string,
    limit: number = 10,
    reverse: boolean = false
  ): Promise<any> {
    const response = await this.client.get(
      `/vocabulary/similar/${encodeURIComponent(relationshipType)}`,
      { params: { limit, reverse } }
    );
    return response.data;
  }

  /**
   * Get detailed vocabulary analysis (ADR-053)
   */
  async analyzeVocabularyType(relationshipType: string): Promise<any> {
    const response = await this.client.get(
      `/vocabulary/analyze/${encodeURIComponent(relationshipType)}`
    );
    return response.data;
  }

  /**
   * Analyze polarity axis between two concept poles (ADR-070)
   */
  async analyzePolarityAxis(request: {
    positive_pole_id: string;
    negative_pole_id: string;
    candidate_ids?: string[];
    auto_discover?: boolean;
    max_candidates?: number;
    max_hops?: number;
    discovery_slot_pct?: number;
    max_workers?: number;
    chunk_size?: number;
    timeout_seconds?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/polarity-axis', request);
    return response.data;
  }

  /**
   * Submit async polarity analysis job with artifact creation (ADR-083)
   */
  async submitPolarityJob(request: {
    positive_pole_id: string;
    negative_pole_id: string;
    candidate_ids?: string[];
    auto_discover?: boolean;
    max_candidates?: number;
    max_hops?: number;
    discovery_slot_pct?: number;
    max_workers?: number;
    chunk_size?: number;
    timeout_seconds?: number;
    create_artifact?: boolean;
  }): Promise<{ job_id: string; status: string; message: string }> {
    const response = await this.client.post('/query/polarity-axis/jobs', request);
    return response.data;
  }

  // ============================================================================
  // Projection Methods (ADR-078)
  // ============================================================================

  /**
   * Get available projection algorithms
   */
  async getProjectionAlgorithms(): Promise<{ available: string[]; default: string }> {
    const response = await this.client.get('/projection/algorithms');
    return response.data;
  }

  /**
   * Get cached projection for an ontology
   */
  async getProjection(ontology: string): Promise<any> {
    const response = await this.client.get(`/projection/${encodeURIComponent(ontology)}`);
    return response.data;
  }

  /**
   * Regenerate projection for an ontology
   */
  async regenerateProjection(ontology: string, options?: {
    force?: boolean;
    algorithm?: 'tsne' | 'umap';
    perplexity?: number;
    center?: boolean;
    include_grounding?: boolean;
    include_diversity?: boolean;
  }): Promise<{ status: string; job_id?: string; message: string; changelist_id?: string }> {
    const response = await this.client.post(
      `/projection/${encodeURIComponent(ontology)}/regenerate`,
      options || {}
    );
    return response.data;
  }

  /**
   * Invalidate (delete) cached projection
   */
  async invalidateProjection(ontology: string): Promise<{ message: string }> {
    const response = await this.client.delete(`/projection/${encodeURIComponent(ontology)}`);
    return response.data;
  }

  // ============================================================================
  // Artifact Methods (ADR-083)
  // ============================================================================

  /**
   * List artifacts with optional filtering
   */
  async listArtifacts(params?: {
    artifact_type?: string;
    representation?: string;
    ontology?: string;
    owner_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<{
    artifacts: any[];
    total: number;
    limit: number;
    offset: number;
  }> {
    const response = await this.client.get('/artifacts', { params });
    return response.data;
  }

  /**
   * Get artifact metadata by ID
   */
  async getArtifact(artifactId: number): Promise<any> {
    const response = await this.client.get(`/artifacts/${artifactId}`);
    return response.data;
  }

  /**
   * Get artifact with full payload
   */
  async getArtifactPayload(artifactId: number): Promise<any> {
    const response = await this.client.get(`/artifacts/${artifactId}/payload`);
    return response.data;
  }

  /**
   * Create a new artifact
   */
  async createArtifact(artifact: {
    artifact_type: string;
    representation: string;
    name?: string;
    parameters: Record<string, any>;
    payload: Record<string, any>;
    metadata?: Record<string, any>;
    ontology?: string;
    concept_ids?: string[];
    expires_at?: string;
    query_definition_id?: number;
  }): Promise<{
    id: number;
    artifact_type: string;
    representation: string;
    name?: string;
    graph_epoch: number;
    storage_location: string;
    garage_key?: string;
    created_at: string;
  }> {
    const response = await this.client.post('/artifacts', artifact);
    return response.data;
  }

  /**
   * Delete an artifact
   */
  async deleteArtifact(artifactId: number): Promise<void> {
    await this.client.delete(`/artifacts/${artifactId}`);
  }

  // ==========================================================================
  // Groups & Grants Methods (ADR-082)
  // ==========================================================================

  /**
   * List groups
   */
  async listGroups(params?: {
    include_system?: boolean;
    include_member_count?: boolean;
  }): Promise<{
    groups: any[];
    total: number;
  }> {
    const response = await this.client.get('/groups', { params });
    return response.data;
  }

  /**
   * Create a group
   */
  async createGroup(group: {
    group_name: string;
    display_name?: string;
    description?: string;
  }): Promise<any> {
    const response = await this.client.post('/groups', group);
    return response.data;
  }

  /**
   * List group members
   */
  async listGroupMembers(groupId: number): Promise<{
    group_id: number;
    group_name: string;
    members: any[];
    total: number;
  }> {
    const response = await this.client.get(`/groups/${groupId}/members`);
    return response.data;
  }

  /**
   * Add member to group
   */
  async addGroupMember(groupId: number, userId: number): Promise<any> {
    const response = await this.client.post(`/groups/${groupId}/members`, { user_id: userId });
    return response.data;
  }

  /**
   * Remove member from group
   */
  async removeGroupMember(groupId: number, userId: number): Promise<void> {
    await this.client.delete(`/groups/${groupId}/members/${userId}`);
  }

  /**
   * Create a resource grant
   */
  async createGrant(grant: {
    resource_type: string;
    resource_id: string;
    principal_type: 'user' | 'group';
    principal_id: number;
    permission: 'read' | 'write' | 'admin';
  }): Promise<any> {
    const response = await this.client.post('/grants', grant);
    return response.data;
  }

  /**
   * List grants for a resource
   */
  async listResourceGrants(resourceType: string, resourceId: string): Promise<{
    grants: any[];
    total: number;
  }> {
    const response = await this.client.get(`/resources/${resourceType}/${resourceId}/grants`);
    return response.data;
  }

  /**
   * Revoke a grant
   */
  async revokeGrant(grantId: number): Promise<void> {
    await this.client.delete(`/grants/${grantId}`);
  }

  // ==========================================================================
  // Query Definitions Methods (ADR-083)
  // ==========================================================================

  /**
   * List query definitions
   */
  async listQueryDefinitions(params?: {
    definition_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    definitions: any[];
    total: number;
    limit: number;
    offset: number;
  }> {
    const response = await this.client.get('/query-definitions', { params });
    return response.data;
  }

  /**
   * Get a query definition by ID
   */
  async getQueryDefinition(definitionId: number): Promise<any> {
    const response = await this.client.get(`/query-definitions/${definitionId}`);
    return response.data;
  }

  /**
   * Create a query definition
   */
  async createQueryDefinition(definition: {
    name: string;
    definition_type: string;
    definition: Record<string, any>;
  }): Promise<any> {
    const response = await this.client.post('/query-definitions', definition);
    return response.data;
  }

  /**
   * Update a query definition
   */
  async updateQueryDefinition(definitionId: number, update: {
    name?: string;
    definition?: Record<string, any>;
  }): Promise<any> {
    const response = await this.client.put(`/query-definitions/${definitionId}`, update);
    return response.data;
  }

  /**
   * Delete a query definition
   */
  async deleteQueryDefinition(definitionId: number): Promise<void> {
    await this.client.delete(`/query-definitions/${definitionId}`);
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
