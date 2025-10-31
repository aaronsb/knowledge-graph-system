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

    // ADR-027: Add request interceptor for JWT authentication
    this.client.interceptors.request.use((requestConfig) => {
      // Priority 1: Use MCP JWT token if set (for MCP server)
      if (this.mcpJwtToken) {
        requestConfig.headers.Authorization = `Bearer ${this.mcpJwtToken}`;
        return requestConfig;
      }

      // Priority 2: Try to get JWT token from config (via ConfigManager for CLI)
      try {
        const { getConfig } = require('../lib/config');
        const configManager = getConfig();
        const tokenInfo = configManager.getAuthToken();

        if (tokenInfo && configManager.isAuthenticated()) {
          // Add JWT token to Authorization header (takes precedence over API key)
          requestConfig.headers.Authorization = `Bearer ${tokenInfo.access_token}`;
        }
      } catch (error) {
        // Config not available or token not found - that's ok, continue without auth
      }

      return requestConfig;
    });

    // ADR-027: Add response interceptor for 401 errors (expired token)
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Check if we have an expired token
          try {
            const { getConfig } = require('../lib/config');
            const configManager = getConfig();

            if (configManager.getAuthToken()) {
              // User has a token but it's expired or invalid
              console.error('\n\x1b[31m❌ Authentication expired or invalid\x1b[0m');
              console.error('   Your session has expired. Please login again:');
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
   * Get detailed information about a concept
   */
  async getConceptDetails(
    conceptId: string,
    includeGrounding: boolean = false
  ): Promise<ConceptDetailsResponse> {
    const response = await this.client.get(`/query/concept/${conceptId}`, {
      params: { include_grounding: includeGrounding }
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
