/**
 * REST API Client
 *
 * Communicates with the Knowledge Graph System API at localhost:8000
 * Automatically includes OAuth Bearer token in requests
 */

import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import type { SubgraphResponse } from '../types/graph';
import type {
  JobStatus,
  JobListFilters,
  JobApproveResponse,
  JobCancelResponse,
  JobsClearResponse,
  JobProgressEvent,
  JobCompletedEvent,
  JobFailedEvent,
} from '../types/jobs';
import type {
  IngestFileRequest,
  IngestTextRequest,
  IngestResponse,
  OntologyListResponse,
} from '../types/ingest';
import { getAuthState } from '../lib/auth/oauth-utils';

// API configuration - runtime config takes precedence over build-time env vars
// This enables CDN deployment without rebuilding
export const API_BASE_URL = window.APP_CONFIG?.apiUrl || import.meta.env.VITE_API_URL || 'http://localhost:8000';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000, // 30 seconds
    });

    // Add auth interceptor to automatically include Bearer token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const authState = getAuthState();
        if (authState && authState.access_token) {
          config.headers.Authorization = `Bearer ${authState.access_token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get subgraph centered on a concept
   * Fetches related concepts and ALL relationships between them
   */
  async getSubgraph(params: {
    center_concept_id: string;
    depth?: number;
    relationship_types?: string[];
    limit?: number;
    // ADR-065: Epistemic status filtering
    include_epistemic_status?: string[];
    exclude_epistemic_status?: string[];
  }): Promise<SubgraphResponse> {
    // Step 1: Fetch related concepts
    const response = await this.client.post<any>('/query/related', {
      concept_id: params.center_concept_id,
      max_depth: params.depth || 1, // Use depth 1 for better performance
      relationship_types: params.relationship_types,
      // ADR-065: Epistemic status filtering
      include_epistemic_status: params.include_epistemic_status,
      exclude_epistemic_status: params.exclude_epistemic_status,
    });

    const relatedConcepts = response.data.results || [];

    // Step 2: Collect all concept IDs (center + related)
    const allConceptIds = [
      params.center_concept_id,
      ...relatedConcepts.map((rc: any) => rc.concept_id)
    ];

    // Step 3: Fetch details for all concepts in parallel (with grounding)
    const conceptDetailsPromises = allConceptIds.map(id =>
      this.client.get(`/query/concept/${id}`, {
        params: { include_grounding: true }
      }).then(r => r.data).catch(() => null)
    );

    const allConceptDetails = (await Promise.all(conceptDetailsPromises)).filter(Boolean);

    // Step 4: Build nodes array (with grounding strength)
    const nodes = allConceptDetails.map((concept: any) => ({
      concept_id: concept.concept_id,
      label: concept.label,
      ontology: concept.documents?.[0] || 'Unknown', // Use first document as ontology
      search_terms: concept.search_terms || [],
      grounding_strength: concept.grounding_strength, // -1.0 to +1.0
    }));

    // Step 5: Build links array from ALL concepts' relationships
    // Only include links where both source and target are in our node set
    const nodeIdSet = new Set(allConceptIds);
    const links: any[] = [];
    const seenEdges = new Set<string>(); // Deduplicate edges

    allConceptDetails.forEach((concept: any) => {
      if (concept.relationships) {
        concept.relationships.forEach((rel: any) => {
          // Only include if target is in our subgraph
          if (nodeIdSet.has(rel.to_id)) {
            const edgeKey = `${concept.concept_id}->${rel.to_id}-${rel.rel_type}`;
            if (!seenEdges.has(edgeKey)) {
              seenEdges.add(edgeKey);
              links.push({
                from_id: concept.concept_id,
                to_id: rel.to_id,
                relationship_type: rel.rel_type,
                confidence: rel.confidence,
                // ADR-065: Vocabulary epistemic status metadata
                category: rel.category,
                avg_grounding: rel.avg_grounding,
                epistemic_status: rel.epistemic_status,
              });
            }
          }
        });
      }
    });

    return {
      nodes,
      links,
      stats: {
        node_count: nodes.length,
        edge_count: links.length,
      },
    };
  }

  /**
   * Find paths between two concepts
   */
  async findPath(params: {
    from_id: string;
    to_id: string;
    max_hops?: number;
    algorithm?: 'shortest' | 'all_simple' | 'weighted';
  }): Promise<any> {
    const response = await this.client.get('/viz/graph/path', {
      params,
    });
    return response.data;
  }

  /**
   * Compare two ontologies
   */
  async compareOntologies(params: {
    ontology_a: string;
    ontology_b: string;
  }): Promise<any> {
    const response = await this.client.get('/viz/ontology/compare', {
      params,
    });
    return response.data;
  }

  /**
   * Get graph timeline evolution
   */
  async getTimeline(params: {
    ontology: string;
    start_date?: string;
    end_date?: string;
    granularity?: 'day' | 'week' | 'month';
  }): Promise<any> {
    const response = await this.client.get('/viz/graph/timeline', {
      params,
    });
    return response.data;
  }

  /**
   * Get adjacency matrix for concepts
   */
  async getAdjacencyMatrix(concept_ids: string[]): Promise<any> {
    const response = await this.client.get('/viz/graph/matrix', {
      params: {
        concept_ids: concept_ids.join(','),
      },
    });
    return response.data;
  }

  /**
   * Search concepts by query
   */
  async searchConcepts(params: {
    query: string;
    limit?: number;
    min_similarity?: number;
    offset?: number;
  }): Promise<import('../types/polarity').ConceptSearchResponse> {
    const response = await this.client.post<import('../types/polarity').ConceptSearchResponse>(
      '/query/search',
      params
    );
    return response.data;
  }

  /**
   * Search concepts by embedding (for Follow Concept functionality)
   * Uses concept's existing embedding to find similar concepts
   */
  async searchByEmbedding(params: {
    embedding: number[];
    limit?: number;
    min_similarity?: number;
    offset?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/search', {
      embedding: params.embedding,
      limit: params.limit,
      min_similarity: params.min_similarity,
      offset: params.offset,
    });
    return response.data;
  }

  /**
   * Get concept details
   */
  async getConceptDetails(concept_id: string): Promise<any> {
    const response = await this.client.get(`/query/concept/${concept_id}`, {
      params: {
        include_grounding: true,
        include_diversity: true,
        diversity_max_hops: 2
      }
    });
    return response.data;
  }

  /**
   * Find paths between two concepts using exact concept IDs
   * No embedding generation needed - uses stored graph structure
   */
  async findConnection(params: {
    from_id: string;
    to_id: string;
    max_hops?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/connect', params, {
      timeout: 120000, // 2 minutes for complex path searches
    });
    return response.data;
  }

  /**
   * Find paths between two concepts using semantic phrase matching
   * Generates embeddings for text queries - use findConnection() if you already have concept IDs
   * Note: Path searches can be slow - uses extended 120s timeout
   */
  async findConnectionBySearch(params: {
    from_query: string;
    to_query: string;
    max_hops?: number;
    threshold?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/connect-by-search', params, {
      timeout: 120000, // 2 minutes for complex path searches
    });
    return response.data;
  }

  /**
   * Execute a raw openCypher query
   * For advanced users who want full control over graph queries
   */
  async executeCypherQuery(params: {
    query: string;
    limit?: number;
  }): Promise<any> {
    const response = await this.client.post('/query/cypher', params, {
      timeout: 60000, // 1 minute timeout for custom queries
    });
    return response.data;
  }

  /**
   * Get related concepts (neighborhood)
   */
  async getRelatedConcepts(params: {
    concept_id: string;
    max_depth?: number;
    relationship_types?: string[];
  }): Promise<any> {
    const response = await this.client.post('/query/related', params);
    return response.data;
  }

  /**
   * Get vocabulary types with categories and confidence scores
   */
  async getVocabularyTypes(params?: {
    include_inactive?: boolean;
    include_builtin?: boolean;
  }): Promise<any> {
    const response = await this.client.get('/vocabulary/types', {
      params: {
        include_inactive: params?.include_inactive ?? false,
        include_builtin: params?.include_builtin ?? true,
      },
    });
    return response.data;
  }

  /**
   * Refresh vocabulary category assignments
   * Recomputes probabilistic categories based on embeddings
   */
  async refreshVocabularyCategories(params?: {
    only_computed?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/vocabulary/refresh-categories', {
      only_computed: params?.only_computed ?? true,
    });
    return response.data;
  }

  /**
   * Get image for a source node (ADR-057)
   * @param sourceId - Source ID from concept instance
   * @returns Image URL (blob URL for display)
   */
  async getSourceImageUrl(sourceId: string): Promise<string> {
    const response = await this.client.get(`/sources/${sourceId}/image`, {
      responseType: 'blob',
    });
    // Create blob URL for display in <img> tags
    return URL.createObjectURL(response.data);
  }

  /**
   * Search source text passages using embeddings (ADR-068 Phase 5)
   * Searches source document chunks directly, not concepts
   */
  async searchSources(params: {
    query: string;
    limit?: number;
    min_similarity?: number;
    ontology?: string;
    include_concepts?: boolean;
    include_full_text?: boolean;
  }): Promise<any> {
    const response = await this.client.post('/query/sources/search', params);
    return response.data;
  }

  /**
   * Analyze polarity axis between two concept poles (ADR-070)
   * Projects concepts onto bidirectional semantic dimension
   */
  async analyzePolarityAxis(params: {
    positive_pole_id: string;
    negative_pole_id: string;
    candidate_ids?: string[];
    auto_discover?: boolean;
    max_candidates?: number;
    max_hops?: number;
  }): Promise<import('../types/polarity').PolarityAxisResponse> {
    const response = await this.client.post<import('../types/polarity').PolarityAxisResponse>(
      '/query/polarity-axis',
      params,
      {
        timeout: 30000, // 30 seconds for analysis
      }
    );
    return response.data;
  }

  // ============================================================
  // INGESTION METHODS
  // ============================================================

  /**
   * Ingest a file (multipart upload)
   * Returns job submission response or duplicate detection response
   */
  async ingestFile(file: File, request: IngestFileRequest): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('ontology', request.ontology);

    if (request.filename) formData.append('filename', request.filename);
    if (request.force) formData.append('force', 'true');
    if (request.auto_approve !== undefined) formData.append('auto_approve', String(request.auto_approve));
    if (request.processing_mode) formData.append('processing_mode', request.processing_mode);
    if (request.source_type) formData.append('source_type', request.source_type);
    if (request.source_path) formData.append('source_path', request.source_path);
    if (request.source_hostname) formData.append('source_hostname', request.source_hostname);

    // Chunking options
    if (request.options?.target_words) formData.append('target_words', String(request.options.target_words));
    if (request.options?.overlap_words) formData.append('overlap_words', String(request.options.overlap_words));
    if (request.options?.min_words) formData.append('min_words', String(request.options.min_words));
    if (request.options?.max_words) formData.append('max_words', String(request.options.max_words));

    const response = await this.client.post<IngestResponse>('/ingest', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 1 minute for upload
    });
    return response.data;
  }

  /**
   * Ingest raw text directly
   */
  async ingestText(request: IngestTextRequest): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('text', request.text);
    formData.append('ontology', request.ontology);

    if (request.filename) formData.append('filename', request.filename);
    if (request.force) formData.append('force', 'true');
    if (request.auto_approve !== undefined) formData.append('auto_approve', String(request.auto_approve));
    if (request.processing_mode) formData.append('processing_mode', request.processing_mode);

    if (request.options?.target_words) formData.append('target_words', String(request.options.target_words));

    const response = await this.client.post<IngestResponse>('/ingest/text', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 30000,
    });
    return response.data;
  }

  /**
   * List available ontologies
   */
  async listOntologies(): Promise<OntologyListResponse> {
    const response = await this.client.get<OntologyListResponse>('/ontology/');
    return response.data;
  }

  // ============================================================
  // JOB MANAGEMENT METHODS
  // ============================================================

  /**
   * Get job status by ID
   */
  async getJob(jobId: string): Promise<JobStatus> {
    const response = await this.client.get<JobStatus>(`/jobs/${jobId}`);
    return response.data;
  }

  /**
   * List jobs with optional filtering
   */
  async listJobs(filters?: JobListFilters): Promise<JobStatus[]> {
    const response = await this.client.get<JobStatus[]>('/jobs', {
      params: {
        status: filters?.status,
        user_id: filters?.user_id,
        limit: filters?.limit ?? 50,
        offset: filters?.offset ?? 0,
      },
    });
    return response.data;
  }

  /**
   * Approve a job for processing (ADR-014)
   */
  async approveJob(jobId: string): Promise<JobApproveResponse> {
    const response = await this.client.post<JobApproveResponse>(`/jobs/${jobId}/approve`);
    return response.data;
  }

  /**
   * Cancel a job
   */
  async cancelJob(jobId: string): Promise<JobCancelResponse> {
    const response = await this.client.delete<JobCancelResponse>(`/jobs/${jobId}`);
    return response.data;
  }

  /**
   * Clear all jobs (admin operation)
   */
  async clearAllJobs(): Promise<JobsClearResponse> {
    const response = await this.client.delete<JobsClearResponse>('/jobs', {
      params: { confirm: true },
    });
    return response.data;
  }

  /**
   * Stream job progress via Server-Sent Events
   * Returns cleanup function to close connection
   */
  streamJobProgress(
    jobId: string,
    callbacks: {
      onProgress?: (event: JobProgressEvent) => void;
      onCompleted?: (event: JobCompletedEvent) => void;
      onFailed?: (event: JobFailedEvent) => void;
      onError?: (error: Error) => void;
    }
  ): () => void {
    const authState = getAuthState();
    const token = authState?.access_token;

    // Build URL with auth token as query param (SSE doesn't support headers)
    const url = new URL(`${API_BASE_URL}/jobs/${jobId}/stream`);
    if (token) {
      url.searchParams.set('token', token);
    }

    const eventSource = new EventSource(url.toString());

    eventSource.addEventListener('progress', (e) => {
      try {
        const data = JSON.parse(e.data) as JobProgressEvent;
        callbacks.onProgress?.(data);
      } catch (err) {
        console.error('Failed to parse progress event:', err);
      }
    });

    eventSource.addEventListener('completed', (e) => {
      try {
        const data = JSON.parse(e.data) as JobCompletedEvent;
        callbacks.onCompleted?.(data);
        eventSource.close();
      } catch (err) {
        console.error('Failed to parse completed event:', err);
      }
    });

    eventSource.addEventListener('failed', (e) => {
      try {
        const data = JSON.parse(e.data) as JobFailedEvent;
        callbacks.onFailed?.(data);
        eventSource.close();
      } catch (err) {
        console.error('Failed to parse failed event:', err);
      }
    });

    eventSource.addEventListener('cancelled', () => {
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      callbacks.onError?.(new Error('SSE connection error'));
      eventSource.close();
    };

    // Return cleanup function
    return () => {
      eventSource.close();
    };
  }

  /**
   * Poll job status until completion (fallback for SSE)
   * Returns final job status
   */
  async pollJobUntilComplete(
    jobId: string,
    callbacks?: {
      onProgress?: (job: JobStatus) => void;
      intervalMs?: number;
    }
  ): Promise<JobStatus> {
    const interval = callbacks?.intervalMs ?? 2000;
    const terminalStates = ['completed', 'failed', 'cancelled'];

    while (true) {
      const job = await this.getJob(jobId);
      callbacks?.onProgress?.(job);

      if (terminalStates.includes(job.status)) {
        return job;
      }

      await new Promise(resolve => setTimeout(resolve, interval));
    }
  }

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.client.get<{ status: string }>('/health');
    return response.data;
  }

  // ============================================================
  // ADMIN / OAUTH CLIENT MANAGEMENT
  // ============================================================

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<{
    id: number;
    username: string;
    role: string;
    created_at: string;
    last_login: string | null;
    disabled: boolean;
  }> {
    const response = await this.client.get('/users/me');
    return response.data;
  }

  /**
   * Get current user's effective permissions (ADR-074)
   * Returns role info and a 'can' map for easy permission checking
   */
  async getCurrentUserPermissions(): Promise<{
    role: string;
    role_hierarchy: string[];
    permissions: Array<{
      resource: string;
      action: string;
      scope_type: string;
      granted: boolean;
    }>;
    can: Record<string, boolean>;
  }> {
    const response = await this.client.get('/users/me/permissions');
    return response.data;
  }

  /**
   * List all users (admin or authenticated users can view)
   */
  async listUsers(params?: { limit?: number; offset?: number }): Promise<{
    users: Array<{
      id: number;
      username: string;
      role: string;
      created_at: string;
      last_login: string | null;
      disabled: boolean;
    }>;
    total: number;
    skip: number;
    limit: number;
  }> {
    const response = await this.client.get('/users', { params });
    return response.data;
  }

  /**
   * Create a new user (admin only)
   */
  async createUser(params: {
    username: string;
    password: string;
    role: string;
  }): Promise<{
    id: number;
    username: string;
    role: string;
    created_at: string;
    last_login: string | null;
    disabled: boolean;
  }> {
    const response = await this.client.post('/users', params);
    return response.data;
  }

  /**
   * Update a user (admin only)
   */
  async updateUser(
    userId: number,
    params: {
      password?: string;
      role?: string;
      disabled?: boolean;
    }
  ): Promise<{
    id: number;
    username: string;
    role: string;
    created_at: string;
    last_login: string | null;
    disabled: boolean;
  }> {
    const response = await this.client.put(`/users/${userId}`, params);
    return response.data;
  }

  /**
   * Delete a user (admin only)
   */
  async deleteUser(userId: number): Promise<void> {
    await this.client.delete(`/users/${userId}`);
  }

  /**
   * Reset a user's password (admin only)
   */
  async resetUserPassword(
    userId: number,
    newPassword: string
  ): Promise<{
    success: boolean;
    message: string;
  }> {
    const response = await this.client.post(`/users/${userId}/reset-password`, {
      new_password: newPassword,
    });
    return response.data;
  }

  /**
   * Get user's own OAuth clients (personal clients)
   */
  async getMyOAuthClients(): Promise<Array<{
    client_id: string;
    client_name: string;
    client_type: string;
    created_at: string;
    last_used: string | null;
    token_count?: number;
  }>> {
    const response = await this.client.get('/auth/oauth/clients/personal');
    // API returns { clients: [...], total: int }
    return response.data.clients || [];
  }

  /**
   * Create a new personal OAuth client
   * Uses form-data as required by the endpoint
   */
  async createPersonalOAuthClient(params: {
    client_name: string;
  }): Promise<{
    client_id: string;
    client_secret: string;
    client_name: string;
  }> {
    // Use URLSearchParams for form data (FastAPI Form() accepts both)
    const formData = new URLSearchParams();
    formData.append('client_name', params.client_name);

    const response = await this.client.post('/auth/oauth/clients/personal/new', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  }

  /**
   * Delete a personal OAuth client
   */
  async deletePersonalOAuthClient(clientId: string): Promise<void> {
    await this.client.delete(`/auth/oauth/clients/personal/${clientId}`);
  }

  /**
   * Rotate secret for a personal OAuth client
   * Returns new credentials (secret shown only once)
   */
  async rotatePersonalOAuthClientSecret(clientId: string): Promise<{
    client_id: string;
    client_name: string | null;
    client_secret: string;
    rotated_at: string;
  }> {
    const response = await this.client.post(`/auth/oauth/clients/personal/${clientId}/rotate-secret`);
    return response.data;
  }

  /**
   * Get system status (admin)
   */
  async getSystemStatus(): Promise<{
    database: {
      connected: boolean;
      postgres_version?: string;
      age_version?: string;
    };
    jobs: {
      pending: number;
      running: number;
      completed: number;
      failed: number;
    };
    storage?: {
      connected: boolean;
      bucket_count?: number;
    };
    uptime_seconds?: number;
  }> {
    const response = await this.client.get('/admin/status');
    return response.data;
  }

  /**
   * List all OAuth clients (admin)
   */
  async listAllOAuthClients(params?: {
    client_type?: string;
    owner_id?: number;
    include_disabled?: boolean;
  }): Promise<Array<{
    client_id: string;
    client_name: string;
    client_type: string;
    owner_id: number | null;
    owner_username: string | null;
    created_at: string;
    last_used: string | null;
    disabled: boolean;
  }>> {
    const response = await this.client.get('/auth/oauth/clients', { params });
    // API returns { clients: [...], total: int }
    return response.data.clients || [];
  }

  /**
   * Delete any OAuth client (admin)
   */
  async deleteOAuthClient(clientId: string): Promise<void> {
    await this.client.delete(`/auth/oauth/clients/${clientId}`);
  }

  /**
   * Get scheduler status (admin)
   */
  async getSchedulerStatus(): Promise<{
    jobs_by_status: Record<string, number>;
    last_cleanup: string | null;
    next_cleanup: string | null;
  }> {
    const response = await this.client.get('/admin/scheduler/status');
    return response.data;
  }

  /**
   * Get database statistics
   * Response format: { nodes: { Concept, Source, Instance }, relationships: { total, by_type } }
   */
  async getDatabaseStats(): Promise<{
    nodes: { Concept?: number; Source?: number; Instance?: number };
    relationships: { total?: number; by_type?: Array<{ rel_type: string; count: number }> };
    metrics?: Record<string, unknown>;
  }> {
    const response = await this.client.get('/database/stats');
    return response.data;
  }

  // ============================================================
  // RBAC MANAGEMENT (ADR-074)
  // ============================================================

  /**
   * List all roles
   */
  async listRoles(): Promise<Array<{
    role_name: string;
    display_name: string;
    description: string | null;
    is_builtin: boolean;
    is_active: boolean;
    parent_role: string | null;
    created_at: string;
    created_by: string | null;
    metadata: Record<string, unknown>;
  }>> {
    const response = await this.client.get('/rbac/roles');
    return response.data;
  }

  /**
   * Get role details including permissions
   */
  async getRole(roleName: string): Promise<{
    role_name: string;
    display_name: string;
    description: string | null;
    is_builtin: boolean;
    is_active: boolean;
    parent_role: string | null;
    created_at: string;
    created_by: string | null;
    metadata: Record<string, unknown>;
  }> {
    const response = await this.client.get(`/rbac/roles/${roleName}`);
    return response.data;
  }

  /**
   * Create a new custom role
   */
  async createRole(params: {
    role_name: string;
    display_name: string;
    description?: string;
    parent_role?: string;
    metadata?: Record<string, unknown>;
  }): Promise<{
    role_name: string;
    display_name: string;
    description: string | null;
    is_builtin: boolean;
    is_active: boolean;
    parent_role: string | null;
    created_at: string;
    created_by: string | null;
    metadata: Record<string, unknown>;
  }> {
    const response = await this.client.post('/rbac/roles', params);
    return response.data;
  }

  /**
   * Update a role
   */
  async updateRole(
    roleName: string,
    params: {
      display_name?: string;
      description?: string;
      parent_role?: string | null;
      is_active?: boolean;
      metadata?: Record<string, unknown>;
    }
  ): Promise<{
    role_name: string;
    display_name: string;
    description: string | null;
    is_builtin: boolean;
    is_active: boolean;
    parent_role: string | null;
    created_at: string;
    created_by: string | null;
    metadata: Record<string, unknown>;
  }> {
    const response = await this.client.put(`/rbac/roles/${roleName}`, params);
    return response.data;
  }

  /**
   * Delete a custom role (builtin roles cannot be deleted)
   */
  async deleteRole(roleName: string): Promise<void> {
    await this.client.delete(`/rbac/roles/${roleName}`);
  }

  /**
   * List all resources
   */
  async listResources(): Promise<Array<{
    resource_type: string;
    description: string | null;
    parent_type: string | null;
    available_actions: string[];
    supports_scoping: boolean;
    metadata: Record<string, unknown>;
    registered_at: string;
    registered_by: string | null;
  }>> {
    const response = await this.client.get('/rbac/resources');
    return response.data;
  }

  /**
   * Get resource details
   */
  async getResource(resourceType: string): Promise<{
    resource_type: string;
    description: string | null;
    parent_type: string | null;
    available_actions: string[];
    supports_scoping: boolean;
    metadata: Record<string, unknown>;
    registered_at: string;
    registered_by: string | null;
  }> {
    const response = await this.client.get(`/rbac/resources/${resourceType}`);
    return response.data;
  }

  /**
   * List permissions (optionally filtered by role)
   */
  async listPermissions(params?: {
    role_name?: string;
    resource_type?: string;
  }): Promise<Array<{
    id: number;
    role_name: string;
    resource_type: string;
    action: string;
    scope_type: string;
    scope_id: string | null;
    scope_filter: Record<string, unknown> | null;
    granted: boolean;
    inherited_from: string | null;
    created_at: string;
    created_by: string | null;
  }>> {
    const response = await this.client.get('/rbac/permissions', { params });
    return response.data;
  }

  /**
   * Grant a permission to a role
   */
  async grantPermission(params: {
    role_name: string;
    resource_type: string;
    action: string;
    scope_type?: string;
    scope_id?: string;
    scope_filter?: Record<string, unknown>;
    granted?: boolean;
  }): Promise<{
    id: number;
    role_name: string;
    resource_type: string;
    action: string;
    scope_type: string;
    scope_id: string | null;
    scope_filter: Record<string, unknown> | null;
    granted: boolean;
    inherited_from: string | null;
    created_at: string;
    created_by: string | null;
  }> {
    const response = await this.client.post('/rbac/permissions', {
      ...params,
      scope_type: params.scope_type || 'global',
      granted: params.granted ?? true,
    });
    return response.data;
  }

  /**
   * Revoke a permission (delete by ID)
   */
  async revokePermission(permissionId: number): Promise<void> {
    await this.client.delete(`/rbac/permissions/${permissionId}`);
  }

  /**
   * Get effective permissions for a role (including inherited)
   */
  async getRoleEffectivePermissions(roleName: string): Promise<Array<{
    resource_type: string;
    action: string;
    scope_type: string;
    granted: boolean;
    inherited_from: string | null;
  }>> {
    // Get permissions filtered by role
    const permissions = await this.listPermissions({ role_name: roleName });
    return permissions.map(p => ({
      resource_type: p.resource_type,
      action: p.action,
      scope_type: p.scope_type,
      granted: p.granted,
      inherited_from: p.inherited_from,
    }));
  }
}

// Export singleton instance
export const apiClient = new APIClient();
