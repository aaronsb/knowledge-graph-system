#!/usr/bin/env -S node --use-system-ca
/**
 * Knowledge Graph MCP Server
 *
 * Standalone MCP server exposing knowledge graph operations as MCP tools.
 * Reuses the existing API client and types from the CLI.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { createClientFromEnv, KnowledgeGraphClient } from './api/client.js';
import { AuthClient } from './lib/auth/auth-client.js';
import { McpAllowlistManager } from './lib/mcp-allowlist.js';
import {
  formatSearchResults,
  formatConceptDetails,
  formatConnectionPaths,
  formatRelatedConcepts,
  formatJobStatus,
  formatJobList,
  formatInspectFileResult,
  formatIngestFileResult,
  formatIngestDirectoryResult,
  formatDatabaseStats,
  formatDatabaseInfo,
  formatDatabaseHealth,
  formatSystemStatus,
  formatApiHealth,
  formatMcpAllowedPaths,
  formatEpistemicStatusList,
  formatEpistemicStatusDetails,
  formatEpistemicStatusMeasurement,
  formatSourceSearchResults,
  formatPolarityAxisResults,
  formatDocumentSearchResults,
  formatDocumentList,
  formatDocumentContent,
  formatDocumentConcepts,
  formatDocumentConceptsDetailed,
  formatGraphConceptResult,
  formatGraphEdgeResult,
  formatGraphConceptList,
  formatGraphEdgeList,
  formatGraphBatchResult,
  formatGraphQueueResult,
  formatOntologyList,
  formatOntologyInfo,
  formatOntologyScores,
  formatOntologyEdges,
  formatOntologyAffinity,
  formatProposalList,
  formatProposalDetail,
  formatAnnealingCycleResult,
} from './mcp/formatters/index.js';
import {
  GraphOperationExecutor,
  type QueueOperation,
} from './mcp/graph-operations.js';
import * as fs from 'fs';
import * as path from 'path';
import pkg from '../package.json';

/**
 * Default parameters for graph queries (ADR-048 Query Safety)
 *
 * These defaults balance performance and result quality:
 * - Higher thresholds (0.75+) prevent expensive full-graph scans
 * - Lower max_hops (3) prevent exponential traversal explosion
 * - Adjust based on graph size and performance characteristics
 */
const DEFAULT_SEARCH_SIMILARITY = 0.7;  // Search tool minimum similarity
const DEFAULT_SEMANTIC_THRESHOLD = 0.75; // Connect queries semantic matching
const DEFAULT_MAX_HOPS = 3;              // Maximum path traversal depth
const DEFAULT_MAX_DEPTH = 2;             // Related concepts neighborhood depth

// Create server instance
const server = new Server(
  {
    name: 'knowledge-graph-server',
    version: pkg.version,
  },
  {
    capabilities: {
      tools: {},
      prompts: {},
      resources: {},
    },
  }
);

/**
 * Knowledge Graph Server - Exploration Guide
 *
 * This system transforms documents into semantic concept graphs with multi-dimensional scoring:
 * - Grounding strength (-1.0 to 1.0): Reliability/contradiction score
 * - Diversity score (0-100%): Conceptual richness and connection breadth
 * - Authenticated diversity (✅✓⚠❌): Directional quality combining grounding + diversity
 *
 * Explore by:
 * 1. search - Find entry points (returns all scores + evidence samples)
 * 2. concept - Work with concepts (details, related, connections)
 * 3. ontology - Manage ontologies (list, info, files, delete)
 * 4. job - Manage jobs (status, list, approve, cancel)
 * 5. ingest - Ingest content (text, inspect-file, file, directory)
 * 6. source - Retrieve source images for visual verification
 *
 * Resources provide fresh data on-demand without consuming tool budget:
 * - database/stats, database/info, database/health
 * - system/status, api/health
 *
 * Use high grounding + high diversity to find reliable, central concepts.
 * Negative grounding often shows the most interesting problems/contradictions.
 */

// OAuth access token storage for authenticated session (ADR-054)
let oauthAccessToken: string | null = null;
let tokenRefreshTimer: NodeJS.Timeout | null = null;

/**
 * Get OAuth access token using client credentials grant (ADR-054)
 * Returns the token and expiry time in milliseconds
 */
async function getOAuthAccessToken(): Promise<{ token: string; expiresInMs: number } | null> {
  const clientId = process.env.KG_OAUTH_CLIENT_ID;
  const clientSecret = process.env.KG_OAUTH_CLIENT_SECRET;
  const apiUrl = process.env.KG_API_URL || 'http://localhost:8000';

  if (!clientId || !clientSecret) {
    console.error('[MCP Auth] Missing OAuth credentials: KG_OAUTH_CLIENT_ID and KG_OAUTH_CLIENT_SECRET required');
    return null;
  }

  try {
    const authClient = new AuthClient(apiUrl);
    const tokenResponse = await authClient.getOAuthToken({
      grant_type: 'client_credentials',
      client_id: clientId,
      client_secret: clientSecret,
      scope: 'read:* write:*'
    });

    const expiresInMs = tokenResponse.expires_in * 1000;
    const expiryTime = new Date(Date.now() + expiresInMs);

    console.error(`[MCP Auth] Successfully authenticated with OAuth client`);
    console.error(`[MCP Auth] Client ID: ${clientId}`);
    console.error(`[MCP Auth] Token expires at ${expiryTime.toISOString()}`);

    return {
      token: tokenResponse.access_token,
      expiresInMs
    };
  } catch (error: any) {
    console.error(`[MCP Auth] Failed to get OAuth token: ${error.message}`);
    return null;
  }
}

/**
 * Schedule automatic token refresh before expiry
 * Refreshes 5 minutes before the token expires
 */
function scheduleTokenRefresh(expiresInMs: number): void {
  // Clear existing timer if any
  if (tokenRefreshTimer) {
    clearTimeout(tokenRefreshTimer);
  }

  // Refresh 5 minutes (300000ms) before expiry, or halfway through if token life < 10 minutes
  const refreshBeforeMs = Math.min(300000, expiresInMs / 2);
  const refreshInMs = expiresInMs - refreshBeforeMs;

  console.error(`[MCP Auth] Token refresh scheduled in ${Math.round(refreshInMs / 1000 / 60)} minutes`);

  tokenRefreshTimer = setTimeout(async () => {
    console.error('[MCP Auth] Refreshing OAuth access token...');

    const result = await getOAuthAccessToken();
    if (result) {
      oauthAccessToken = result.token;

      // Update the token in the client
      if (client) {
        client.setMcpJwtToken(result.token);
      }

      // Schedule next refresh
      scheduleTokenRefresh(result.expiresInMs);
    } else {
      console.error('[MCP Auth] Token refresh failed! Operations may fail with 401 errors.');
      console.error('[MCP Auth] Please restart the MCP server or check OAuth credentials.');
    }
  }, refreshInMs);
}

/**
 * Initialize OAuth authentication using client credentials (ADR-054)
 *
 * Requires KG_OAUTH_CLIENT_ID and KG_OAUTH_CLIENT_SECRET environment variables.
 * This allows the MCP server to authenticate transparently without
 * the AI being aware of authentication requirements.
 */
async function initializeAuth(): Promise<void> {
  const clientId = process.env.KG_OAUTH_CLIENT_ID;
  const clientSecret = process.env.KG_OAUTH_CLIENT_SECRET;

  if (clientId && clientSecret) {
    const result = await getOAuthAccessToken();

    if (result) {
      oauthAccessToken = result.token;
      scheduleTokenRefresh(result.expiresInMs);
    } else {
      console.error('[MCP Auth] The MCP server will operate without authentication.');
      console.error('[MCP Auth] Some operations may fail with 401 errors.');
    }
  } else {
    console.error('[MCP Auth] No OAuth credentials provided (KG_OAUTH_CLIENT_ID/KG_OAUTH_CLIENT_SECRET).');
    console.error('[MCP Auth] The MCP server will operate without authentication.');
    console.error('[MCP Auth] To authenticate:');
    console.error('[MCP Auth]   1. Create a personal OAuth client: kg login');
    console.error('[MCP Auth]   2. Copy client credentials from ~/.config/kg/config.json');
    console.error('[MCP Auth]   3. Add to Claude Desktop config as KG_OAUTH_CLIENT_ID and KG_OAUTH_CLIENT_SECRET');
  }
}

/**
 * Create an authenticated API client
 * If we have an OAuth access token, inject it into the client (ADR-054)
 */
function createAuthenticatedClient(): KnowledgeGraphClient {
  const client = createClientFromEnv();

  // If we have an OAuth access token, set it on the client
  if (oauthAccessToken) {
    client.setMcpJwtToken(oauthAccessToken);
  }

  return client;
}

// Client instance - will be initialized in main() before server starts
let client: KnowledgeGraphClient;

/**
 * Tool Definitions
 *
 * Consolidated from 22 tools to 6 tools + 5 resources (ADR-013)
 */

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'search',
        description: `Search for concepts, source passages, or documents using semantic similarity. Your ENTRY POINT to the graph.

CONCEPT SEARCH (type: "concepts", default) - Find concepts by semantic similarity:
- Grounding strength (-1.0 to 1.0): Reliability/contradiction score
- Diversity score: Conceptual richness (% of diverse connections)
- Authenticated diversity: Support vs contradiction indicator (✅✓⚠❌)
- Evidence samples: Quoted text from source documents
- Image indicators: Visual evidence when available
- Document sources: Where concepts originated

SOURCE SEARCH (type: "sources") - Find source text passages directly (ADR-068):
- Searches source document embeddings, not concept embeddings
- Returns matched text chunks with character offsets for highlighting
- Shows concepts extracted from those passages
- Useful for RAG workflows and finding original context

DOCUMENT SEARCH (type: "documents") - Find documents by semantic similarity (ADR-084):
- Searches at document level (aggregates source chunks)
- Returns documents ranked by best matching chunk similarity
- Shows concepts extracted from each document
- Use with document tool for content retrieval

RECOMMENDED WORKFLOW: After search, use concept (action: "connect") to find HOW concepts relate - this reveals narrative flows and cause/effect chains that individual searches cannot show. Connection paths are often more valuable than isolated concepts.

Use 2-3 word phrases (e.g., "linear thinking patterns").`,
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")',
            },
            type: {
              type: 'string',
              enum: ['concepts', 'sources', 'documents'],
              description: 'Search type: "concepts" (default), "sources" (passage search), or "documents" (document-level search)',
              default: 'concepts',
            },
            limit: {
              type: 'number',
              description: 'Maximum number of results to return (default: 10, max: 100)',
              default: 10,
            },
            min_similarity: {
              type: 'number',
              description: 'Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)',
              default: 0.7,
            },
            offset: {
              type: 'number',
              description: 'Number of results to skip for pagination (default: 0)',
              default: 0,
            },
            ontology: {
              type: 'string',
              description: 'Filter by ontology/document name (sources only)',
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'concept',
        description: `Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts).

PERFORMANCE CRITICAL: For "connect" action, use threshold >= 0.75 to avoid database overload. Lower thresholds create exponentially larger searches that can hang for minutes. Start with threshold=0.8, max_hops=3, then adjust if needed.`,
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['details', 'related', 'connect'],
              description: 'Operation: "details" (get ALL evidence), "related" (explore neighborhood), "connect" (find paths)',
            },
            // For details and related
            concept_id: {
              type: 'string',
              description: 'Concept ID (required for details, related)',
            },
            include_grounding: {
              type: 'boolean',
              description: 'Include grounding_strength (default: true)',
              default: true,
            },
            include_diversity: {
              type: 'boolean',
              description: 'Include diversity metrics for details action (default: false, adds ~100-500ms)',
              default: false,
            },
            diversity_max_hops: {
              type: 'number',
              description: 'Max hops for diversity calculation (default: 2)',
              default: 2,
            },
            truncate_evidence: {
              type: 'boolean',
              description: 'Truncate evidence full_text context to 200 chars (default: true for token efficiency). Set false for complete context.',
              default: true,
            },
            // For related
            max_depth: {
              type: 'number',
              description: 'Max traversal depth for related (1-5, default: 2)',
              default: 2,
            },
            relationship_types: {
              type: 'array',
              items: { type: 'string' },
              description: 'Filter relationships (e.g., ["SUPPORTS", "CONTRADICTS"])',
            },
            // ADR-065: Epistemic status filtering (for related and connect)
            include_epistemic_status: {
              type: 'array',
              items: { type: 'string' },
              description: 'Only include relationships with these epistemic statuses (e.g., ["AFFIRMATIVE", "CONTESTED"])',
            },
            exclude_epistemic_status: {
              type: 'array',
              items: { type: 'string' },
              description: 'Exclude relationships with these epistemic statuses (e.g., ["HISTORICAL", "INSUFFICIENT_DATA"])',
            },
            // For connect
            connection_mode: {
              type: 'string',
              enum: ['exact', 'semantic'],
              description: 'Connection mode: "exact" (IDs) or "semantic" (phrases)',
              default: 'semantic',
            },
            from_id: {
              type: 'string',
              description: 'Starting concept ID (for exact mode)',
            },
            to_id: {
              type: 'string',
              description: 'Target concept ID (for exact mode)',
            },
            from_query: {
              type: 'string',
              description: 'Starting phrase (for semantic mode, 2-3 words)',
            },
            to_query: {
              type: 'string',
              description: 'Target phrase (for semantic mode, 2-3 words)',
            },
            max_hops: {
              type: 'number',
              description: 'Max path length (default: 3). WARNING: Values >5 combined with threshold <0.75 can cause severe performance issues.',
              default: 3,
            },
            threshold: {
              type: 'number',
              description: 'Similarity threshold for semantic mode (default: 0.75). PERFORMANCE GUIDE: 0.85+ = precise/fast, 0.75-0.84 = balanced, 0.60-0.74 = exploratory/SLOW, <0.60 = DANGEROUS (can hang database for minutes)',
              default: 0.75,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'ontology',
        description: 'Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.',
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['list', 'info', 'files', 'create', 'rename', 'delete', 'lifecycle', 'scores', 'score', 'score_all', 'candidates', 'affinity', 'edges', 'reassign', 'dissolve', 'proposals', 'proposal_review', 'annealing_cycle'],
              description: 'Operation: "list" (all ontologies), "info" (details), "files" (source files), "create" (new ontology), "rename" (change name), "delete" (remove), "lifecycle" (set state), "scores" (cached scores), "score" (recompute one), "score_all" (recompute all), "candidates" (top concepts), "affinity" (cross-ontology overlap), "edges" (ontology-to-ontology edges), "reassign" (move sources), "dissolve" (non-destructive demotion), "proposals" (list annealing proposals), "proposal_review" (approve/reject proposal), "annealing_cycle" (trigger annealing cycle)',
            },
            ontology_name: {
              type: 'string',
              description: 'Ontology name (required for info, files, create, rename, delete)',
            },
            description: {
              type: 'string',
              description: 'What this knowledge domain covers (for create action)',
            },
            new_name: {
              type: 'string',
              description: 'New ontology name (required for rename action)',
            },
            lifecycle_state: {
              type: 'string',
              enum: ['active', 'pinned', 'frozen'],
              description: 'Target lifecycle state (required for lifecycle action)',
            },
            force: {
              type: 'boolean',
              description: 'Confirm deletion (required for delete)',
              default: false,
            },
            target_ontology: {
              type: 'string',
              description: 'Target ontology for reassign/dissolve actions',
            },
            source_ids: {
              type: 'array',
              items: { type: 'string' },
              description: 'Source IDs to move (for reassign action)',
            },
            limit: {
              type: 'number',
              description: 'Max results for candidates/affinity (default: 20/10)',
            },
            proposal_id: {
              type: 'number',
              description: 'Proposal ID (for proposal_review action)',
            },
            status: {
              type: 'string',
              enum: ['pending', 'approved', 'rejected', 'executing', 'executed', 'failed'],
              description: 'Filter proposals by status, or review status (approved/rejected)',
            },
            proposal_type: {
              type: 'string',
              enum: ['promotion', 'demotion'],
              description: 'Filter proposals by type',
            },
            notes: {
              type: 'string',
              description: 'Review notes (for proposal_review action)',
            },
            dry_run: {
              type: 'boolean',
              description: 'Preview candidates without proposals (for annealing_cycle)',
              default: false,
            },
            demotion_threshold: {
              type: 'number',
              description: 'Protection score below which to consider demotion (default: 0.15)',
            },
            promotion_min_degree: {
              type: 'number',
              description: 'Minimum concept degree for promotion candidacy (default: 10)',
            },
            max_proposals: {
              type: 'number',
              description: 'Maximum proposals per annealing cycle (default: 5)',
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'job',
        description: 'Manage ingestion jobs: get status, list jobs, approve, cancel, delete, or cleanup. Use action parameter to specify operation.',
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['status', 'list', 'approve', 'cancel', 'delete', 'cleanup'],
              description: 'Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job), "delete" (permanently delete single job), "cleanup" (delete jobs matching filters)',
            },
            job_id: {
              type: 'string',
              description: 'Job ID (required for status, approve, cancel, delete)',
            },
            status: {
              type: 'string',
              description: 'Filter by status for list/cleanup (pending, awaiting_approval, running, completed, failed)',
            },
            limit: {
              type: 'number',
              description: 'Max jobs to return for list (default: 50)',
              default: 50,
            },
            force: {
              type: 'boolean',
              description: 'Force delete even if job is processing (for delete action)',
              default: false,
            },
            system_only: {
              type: 'boolean',
              description: 'Only delete system/scheduled jobs (for cleanup action)',
              default: false,
            },
            older_than: {
              type: 'string',
              description: 'Delete jobs older than duration: 1h, 24h, 7d, 30d (for cleanup action)',
            },
            job_type: {
              type: 'string',
              description: 'Filter by job type for cleanup (ingestion, epistemic_remeasurement, projection, etc)',
            },
            dry_run: {
              type: 'boolean',
              description: 'Preview what would be deleted without deleting (for cleanup, default: true)',
              default: true,
            },
            confirm: {
              type: 'boolean',
              description: 'Confirm deletion - set to true to actually delete (for cleanup action)',
              default: false,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'ingest',
        description: 'Ingest content into the knowledge graph: submit text, inspect files, ingest files, or ingest directories. Use action parameter to specify operation.',
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['text', 'inspect-file', 'file', 'directory'],
              description: 'Operation: "text" (raw text), "inspect-file" (validate), "file" (ingest files), "directory" (ingest directory)',
            },
            // For text action
            text: {
              type: 'string',
              description: 'Text content to ingest (required for text action)',
            },
            // For all actions except inspect-file
            ontology: {
              type: 'string',
              description: 'Ontology name (required for text/file/directory, optional for directory - defaults to dir name)',
            },
            // For text action
            filename: {
              type: 'string',
              description: 'Optional filename for source tracking (text action)',
            },
            processing_mode: {
              type: 'string',
              enum: ['serial', 'parallel'],
              description: 'Processing mode (text action, default: serial)',
              default: 'serial',
            },
            target_words: {
              type: 'number',
              description: 'Words per chunk (text action, default: 1000)',
              default: 1000,
            },
            overlap_words: {
              type: 'number',
              description: 'Overlap between chunks (text action, default: 200)',
              default: 200,
            },
            // For file/directory/inspect-file actions
            path: {
              description: 'File/directory path (required for inspect-file/file/directory). For file action: single path string OR array for batch',
              oneOf: [
                { type: 'string' },
                { type: 'array', items: { type: 'string' } }
              ],
            },
            // For file/directory actions
            auto_approve: {
              type: 'boolean',
              description: 'Auto-approve processing (file/directory actions, default: true)',
              default: true,
            },
            force: {
              type: 'boolean',
              description: 'Force re-ingestion (file/directory actions, default: false)',
              default: false,
            },
            // For directory action
            recursive: {
              type: 'boolean',
              description: 'Process subdirectories recursively (directory action, default: false)',
              default: false,
            },
            limit: {
              type: 'number',
              description: 'Number of files to show per page (directory action, default: 10)',
              default: 10,
            },
            offset: {
              type: 'number',
              description: 'Number of files to skip for pagination (directory action, default: 0)',
              default: 0,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'source',
        description: `Retrieve original source content (text or image) for a source node (ADR-057).

For IMAGE sources: Returns the image for visual verification
For TEXT sources: Returns full_text content with metadata (document, paragraph, offsets)

Use when you need to:
- Verify extracted concepts against original source
- Get the full context of a text passage
- Retrieve images for visual analysis
- Check character offsets for highlighting`,
        inputSchema: {
          type: 'object',
          properties: {
            source_id: {
              type: 'string',
              description: 'Source ID from evidence or search results',
            },
          },
          required: ['source_id'],
        },
      },
      {
        name: 'epistemic_status',
        description: `Vocabulary epistemic status classification (ADR-065 Phase 2). Knowledge validation state for relationship types.

Three actions available:
- "list": List all vocabulary types with epistemic status classifications (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL/INSUFFICIENT_DATA/UNCLASSIFIED)
- "show": Get detailed status for a specific relationship type
- "measure": Run measurement to calculate epistemic status for all types (admin operation)

EPISTEMIC STATUS CLASSIFICATIONS:
- AFFIRMATIVE: High avg grounding >0.8 (well-established knowledge)
- CONTESTED: Mixed grounding 0.2-0.8 (debated/mixed validation)
- CONTRADICTORY: Low grounding <-0.5 (contradicted knowledge)
- HISTORICAL: Temporal vocabulary (detected by name)
- INSUFFICIENT_DATA: <3 successful measurements
- UNCLASSIFIED: Doesn't fit known patterns

Use for filtering relationships by epistemic reliability, identifying contested knowledge areas, and curating high-confidence vs exploratory subgraphs.`,
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['list', 'show', 'measure'],
              description: 'Operation: "list" (all types), "show" (specific type), "measure" (run measurement)',
            },
            // For list action
            status_filter: {
              type: 'string',
              description: 'Filter by status for list action: AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL, INSUFFICIENT_DATA, UNCLASSIFIED',
            },
            // For show action
            relationship_type: {
              type: 'string',
              description: 'Relationship type to show (required for show action, e.g., "IMPLIES", "SUPPORTS")',
            },
            // For measure action
            sample_size: {
              type: 'number',
              description: 'Edges to sample per type for measure action (default: 100)',
              default: 100,
            },
            store: {
              type: 'boolean',
              description: 'Store results to database for measure action (default: true)',
              default: true,
            },
            verbose: {
              type: 'boolean',
              description: 'Include detailed statistics for measure action (default: false)',
              default: false,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'analyze_polarity_axis',
        description: `Analyze bidirectional semantic dimension (polarity axis) between two concept poles (ADR-070).

Projects concepts onto an axis formed by opposing semantic poles (e.g., Modern ↔ Traditional, Centralized ↔ Distributed). Returns:
- Axis quality and magnitude (semantic distinctness)
- Concept positions along the axis (-1 to +1)
- Direction distribution (positive/neutral/negative)
- Grounding correlation patterns
- Statistical analysis of projections

PERFORMANCE: Direct query pattern, ~2-3 seconds execution time.

Use Cases:
- Explore conceptual spectrums and gradients
- Identify position-grounding correlation patterns
- Discover concepts balanced between opposing ideas
- Map semantic dimensions in the knowledge graph`,
        inputSchema: {
          type: 'object',
          properties: {
            positive_pole_id: {
              type: 'string',
              description: 'Concept ID for positive pole (e.g., ID for "Modern")',
            },
            negative_pole_id: {
              type: 'string',
              description: 'Concept ID for negative pole (e.g., ID for "Traditional")',
            },
            candidate_ids: {
              type: 'array',
              items: { type: 'string' },
              description: 'Specific concept IDs to project onto axis (optional)',
            },
            auto_discover: {
              type: 'boolean',
              description: 'Auto-discover related concepts if candidate_ids not provided (default: true)',
              default: true,
            },
            max_candidates: {
              type: 'number',
              description: 'Maximum candidates for auto-discovery (default: 20, max: 100)',
              default: 20,
            },
            max_hops: {
              type: 'number',
              description: 'Maximum graph hops for auto-discovery (1-3, default: 1)',
              default: 1,
            },
          },
          required: ['positive_pole_id', 'negative_pole_id'],
        },
      },
      {
        name: 'artifact',
        description: `Manage saved artifacts (ADR-083). Artifacts persist computed results like search results, projections, and polarity analyses for later recall.

Three actions available:
- "list": List artifacts with optional filtering by type, representation, or ontology
- "show": Get artifact metadata by ID (without payload)
- "payload": Get artifact with full payload (for reusing stored analysis)

Use artifacts to:
- Recall previously computed analyses without re-running expensive queries
- Share analysis results across sessions
- Track analysis history with parameters and timestamps
- Check freshness (is_fresh indicates if graph has changed since artifact creation)`,
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['list', 'show', 'payload'],
              description: 'Operation: "list" (list artifacts), "show" (metadata only), "payload" (full result)',
            },
            // For show and payload
            artifact_id: {
              type: 'number',
              description: 'Artifact ID (required for show, payload)',
            },
            // For list filtering
            artifact_type: {
              type: 'string',
              description: 'Filter by type: search_result, projection, polarity_analysis, query_result, etc.',
            },
            representation: {
              type: 'string',
              description: 'Filter by source: cli, mcp_server, polarity_explorer, embedding_landscape, etc.',
            },
            ontology: {
              type: 'string',
              description: 'Filter by associated ontology name',
            },
            limit: {
              type: 'number',
              description: 'Max artifacts to return for list (default: 20)',
              default: 20,
            },
            offset: {
              type: 'number',
              description: 'Number to skip for pagination (default: 0)',
              default: 0,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'document',
        description: `Work with documents: list all, show content, or get concepts (ADR-084).

Three actions available:
- "list": List all documents with optional ontology filter
- "show": Retrieve document content from Garage storage
- "concepts": Get all concepts extracted from a document

Documents are aggregated from source chunks and stored in Garage (S3-compatible storage).
Use search tool with type="documents" to find documents semantically.`,
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['list', 'show', 'concepts'],
              description: 'Operation: "list" (all documents), "show" (content), "concepts" (extracted concepts)',
            },
            // For show and concepts
            document_id: {
              type: 'string',
              description: 'Document ID (required for show, concepts). Format: sha256:...',
            },
            // For concepts action
            include_details: {
              type: 'boolean',
              description: 'Include full concept details (evidence, relationships, grounding) in one call. Default: false for lightweight list.',
              default: false,
            },
            // For list
            ontology: {
              type: 'string',
              description: 'Filter by ontology name (for list)',
            },
            limit: {
              type: 'number',
              description: 'Max documents to return for list (default: 50)',
              default: 50,
            },
            offset: {
              type: 'number',
              description: 'Number to skip for pagination (default: 0)',
              default: 0,
            },
          },
          required: ['action'],
        },
      },
      // ADR-089 Phase 3a: Graph CRUD Tool
      {
        name: 'graph',
        description: `Create, edit, delete, and list concepts and edges in the knowledge graph (ADR-089).

This tool provides deterministic graph editing without going through the LLM ingest pipeline.
Use for manual curation, agent-driven knowledge building, and precise graph manipulation.

**Actions:**
- "create": Create a new concept or edge
- "edit": Update an existing concept or edge
- "delete": Delete a concept or edge
- "list": List concepts or edges with filters

**Entity Types:**
- "concept": Knowledge graph concepts (nodes)
- "edge": Relationships between concepts

**Matching Modes (for create):**
- "auto": Link to existing if match found, create if not (default)
- "force_create": Always create new, even if similar exists
- "match_only": Only link to existing, error if no match

**Semantic Resolution:**
- Use \`from_label\`/\`to_label\` to reference concepts by name instead of ID
- Resolution uses vector similarity (85% threshold) to find matching concepts

**Examples:**
- Create concept: \`{action: "create", entity: "concept", label: "CAP Theorem", ontology: "distributed-systems"}\`
- Create edge: \`{action: "create", entity: "edge", from_label: "CAP Theorem", to_label: "Partition Tolerance", relationship_type: "REQUIRES"}\`
- List concepts: \`{action: "list", entity: "concept", ontology: "distributed-systems"}\`
- Delete concept: \`{action: "delete", entity: "concept", concept_id: "c_abc123"}\`

**Queue Mode** (batch multiple operations in one call):
\`\`\`json
{
  "action": "queue",
  "operations": [
    {"op": "create", "entity": "concept", "label": "A", "ontology": "test"},
    {"op": "create", "entity": "concept", "label": "B", "ontology": "test"},
    {"op": "create", "entity": "edge", "from_label": "A", "to_label": "B", "relationship_type": "IMPLIES"}
  ]
}
\`\`\`
Queue executes sequentially, stops on first error (unless continue_on_error=true). Max 20 operations.`,
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['create', 'edit', 'delete', 'list', 'queue'],
              description: 'Operation to perform. Use "queue" to batch multiple operations.',
            },
            entity: {
              type: 'string',
              enum: ['concept', 'edge'],
              description: 'Entity type (required for create/edit/delete/list, not for queue)',
            },
            // Queue fields
            operations: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  op: { type: 'string', enum: ['create', 'edit', 'delete', 'list'], description: 'Operation' },
                  entity: { type: 'string', enum: ['concept', 'edge'] },
                  label: { type: 'string' },
                  ontology: { type: 'string' },
                  description: { type: 'string' },
                  search_terms: { type: 'array', items: { type: 'string' } },
                  matching_mode: { type: 'string', enum: ['auto', 'force_create', 'match_only'] },
                  concept_id: { type: 'string' },
                  from_concept_id: { type: 'string' },
                  to_concept_id: { type: 'string' },
                  from_label: { type: 'string' },
                  to_label: { type: 'string' },
                  relationship_type: { type: 'string' },
                  category: { type: 'string' },
                  confidence: { type: 'number' },
                  limit: { type: 'number' },
                  offset: { type: 'number' },
                  cascade: { type: 'boolean' },
                },
                required: ['op', 'entity'],
              },
              description: 'Array of operations for queue action (max 20). Each has op, entity, and action-specific fields.',
            },
            continue_on_error: {
              type: 'boolean',
              description: 'For queue: continue executing after errors (default: false, stop on first error)',
              default: false,
            },
            // Concept fields
            label: {
              type: 'string',
              description: 'Concept label (required for create concept)',
            },
            ontology: {
              type: 'string',
              description: 'Ontology/namespace (required for create concept, optional filter for list)',
            },
            description: {
              type: 'string',
              description: 'Concept description (optional)',
            },
            search_terms: {
              type: 'array',
              items: { type: 'string' },
              description: 'Alternative search terms for the concept',
            },
            matching_mode: {
              type: 'string',
              enum: ['auto', 'force_create', 'match_only'],
              description: 'How to handle similar existing concepts (default: auto)',
              default: 'auto',
            },
            // Edge fields
            from_concept_id: {
              type: 'string',
              description: 'Source concept ID (for edge create/delete)',
            },
            to_concept_id: {
              type: 'string',
              description: 'Target concept ID (for edge create/delete)',
            },
            from_label: {
              type: 'string',
              description: 'Source concept by label (semantic resolution)',
            },
            to_label: {
              type: 'string',
              description: 'Target concept by label (semantic resolution)',
            },
            relationship_type: {
              type: 'string',
              description: 'Edge relationship type (e.g., IMPLIES, SUPPORTS, CONTRADICTS)',
            },
            category: {
              type: 'string',
              enum: ['logical_truth', 'causal', 'structural', 'temporal', 'comparative', 'functional', 'definitional'],
              description: 'Semantic category of the relationship (default: structural)',
              default: 'structural',
            },
            confidence: {
              type: 'number',
              description: 'Edge confidence 0.0-1.0 (default: 1.0)',
              default: 1.0,
            },
            // Identifiers for edit/delete
            concept_id: {
              type: 'string',
              description: 'Concept ID (for edit/delete concept)',
            },
            // List filters
            label_contains: {
              type: 'string',
              description: 'Filter concepts by label substring (for list)',
            },
            creation_method: {
              type: 'string',
              description: 'Filter by creation method (for list)',
            },
            source: {
              type: 'string',
              description: 'Filter edges by source (for list)',
            },
            // Pagination
            limit: {
              type: 'number',
              description: 'Max results to return (default: 20)',
              default: 20,
            },
            offset: {
              type: 'number',
              description: 'Number to skip for pagination (default: 0)',
              default: 0,
            },
            // Delete option
            cascade: {
              type: 'boolean',
              description: 'For concept delete: also delete orphaned synthetic sources (default: false)',
              default: false,
            },
          },
          required: ['action'],
        },
      },
    ],
  };
});

// List available resources
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'database/stats',
        name: 'Database Statistics',
        description: 'Concept counts, relationship counts, ontology statistics',
        mimeType: 'application/json'
      },
      {
        uri: 'database/info',
        name: 'Database Information',
        description: 'PostgreSQL version, Apache AGE extension details',
        mimeType: 'application/json'
      },
      {
        uri: 'database/health',
        name: 'Database Health',
        description: 'Database connection status, graph availability',
        mimeType: 'application/json'
      },
      {
        uri: 'system/status',
        name: 'System Status',
        description: 'Job scheduler status, resource usage',
        mimeType: 'application/json'
      },
      {
        uri: 'api/health',
        name: 'API Health',
        description: 'API server health and timestamp',
        mimeType: 'application/json'
      },
      {
        uri: 'mcp/allowed-paths',
        name: 'MCP File Access Allowlist',
        description: 'Path allowlist configuration for secure file/directory ingestion (ADR-062)',
        mimeType: 'application/json'
      }
    ]
  };
});

// Read resource handler
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  try {
    switch (uri) {
      case 'database/stats': {
        const result = await client.getDatabaseStats();
        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatDatabaseStats(result)
          }]
        };
      }

      case 'database/info': {
        const result = await client.getDatabaseInfo();
        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatDatabaseInfo(result)
          }]
        };
      }

      case 'database/health': {
        const result = await client.getDatabaseHealth();
        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatDatabaseHealth(result)
          }]
        };
      }

      case 'system/status': {
        const result = await client.getSystemStatus();
        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatSystemStatus(result)
          }]
        };
      }

      case 'api/health': {
        const result = await client.health();
        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatApiHealth(result)
          }]
        };
      }

      case 'mcp/allowed-paths': {
        const manager = new McpAllowlistManager();
        const config = manager.getConfig();

        if (!config) {
          return {
            contents: [{
              uri,
              mimeType: 'text/plain',
              text: formatMcpAllowedPaths({
                configured: false,
                message: 'Allowlist not initialized. Run: kg mcp-config init-allowlist',
                hint: 'Initialize with default safe patterns for .md, .txt, .pdf, .png, .jpg files'
              })
            }]
          };
        }

        return {
          contents: [{
            uri,
            mimeType: 'text/plain',
            text: formatMcpAllowedPaths({
              configured: true,
              version: config.version,
              allowed_directories: config.allowed_directories,
              allowed_patterns: config.allowed_patterns,
              blocked_patterns: config.blocked_patterns,
              max_file_size_mb: config.max_file_size_mb,
              max_files_per_directory: config.max_files_per_directory,
              config_path: manager.getAllowlistPath()
            })
          }]
        };
      }

      default:
        throw new Error(`Unknown resource: ${uri}`);
    }
  } catch (error: any) {
    throw new Error(`Failed to read resource ${uri}: ${error.message}`);
  }
});

/**
 * Helper: Segment long paths for better readability
 *
 * Paths longer than 5 hops are chunked into segments of 5 hops each.
 * This makes them much easier to read and understand.
 */
function segmentPath(path: any): any {
  if (!path.hops || path.hops <= 5) {
    return {
      totalHops: path.hops,
      segmented: false,
      nodes: path.nodes,
      relationships: path.relationships,
    };
  }

  // Chunk into segments of 5 hops
  const segments = [];
  const chunkSize = 5;
  const nodes = path.nodes || [];
  const relationships = path.relationships || [];

  for (let i = 0; i < nodes.length; i += chunkSize) {
    segments.push({
      nodes: nodes.slice(i, Math.min(i + chunkSize + 1, nodes.length)),
      relationships: relationships.slice(i, Math.min(i + chunkSize, relationships.length)),
      segment: Math.floor(i / chunkSize) + 1,
      totalSegments: Math.ceil(nodes.length / chunkSize),
    });
  }

  return {
    totalHops: path.hops,
    segmented: true,
    segments,
  };
}

// Call tool handler with consolidated routing
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const toolArgs = args || {};

  try {
    switch (name) {
      case 'search': {
        const query = toolArgs.query as string;
        const searchType = toolArgs.type as string || 'concepts';
        const limit = toolArgs.limit as number || 10;
        const min_similarity = toolArgs.min_similarity as number || DEFAULT_SEARCH_SIMILARITY;
        const offset = toolArgs.offset as number || 0;
        const ontology = toolArgs.ontology as string | undefined;

        if (searchType === 'sources') {
          // ADR-068 Phase 5: Source text search
          const result = await client.searchSources({
            query,
            limit,
            min_similarity,
            ontology,
            include_concepts: true,
            include_full_text: true,
          });

          const formattedText = formatSourceSearchResults(result);

          return {
            content: [{ type: 'text', text: formattedText }],
          };
        } else if (searchType === 'documents') {
          // ADR-084: Document search
          const result = await client.searchDocuments({
            query,
            limit,
            min_similarity,
            ontology,
          });

          // Add query to result for formatting
          const resultWithQuery = { ...result, query };
          const formattedText = formatDocumentSearchResults(resultWithQuery);

          return {
            content: [{ type: 'text', text: formattedText }],
          };
        } else {
          // Default: Concept search
          const result = await client.searchConcepts({
            query,
            limit,
            min_similarity,
            offset,
            include_grounding: true,
            include_evidence: true,
            include_diversity: true,
            diversity_max_hops: 2,
          });

          const formattedText = formatSearchResults(result);

          return {
            content: [{ type: 'text', text: formattedText }],
          };
        }
      }

      case 'concept': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'details': {
            const includeGrounding = toolArgs.include_grounding !== false;
            const includeDiversity = toolArgs.include_diversity === true;
            const diversityMaxHops = toolArgs.diversity_max_hops as number || 2;
            const truncateEvidence = toolArgs.truncate_evidence !== false; // Default true

            const result = await client.getConceptDetails(
              toolArgs.concept_id as string,
              includeGrounding,
              includeDiversity,
              diversityMaxHops
            );

            const formattedText = formatConceptDetails(result, truncateEvidence);

            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'related': {
            const result = await client.findRelatedConcepts({
              concept_id: toolArgs.concept_id as string,
              max_depth: toolArgs.max_depth as number || DEFAULT_MAX_DEPTH,
              relationship_types: toolArgs.relationship_types as string[] | undefined,
              // ADR-065: Epistemic status filtering
              include_epistemic_status: toolArgs.include_epistemic_status as string[] | undefined,
              exclude_epistemic_status: toolArgs.exclude_epistemic_status as string[] | undefined,
            });

            const formattedText = formatRelatedConcepts(result);

            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'connect': {
            const mode = toolArgs.connection_mode as string || 'semantic';

            if (mode === 'exact') {
              const result = await client.findConnection({
                from_id: toolArgs.from_id as string,
                to_id: toolArgs.to_id as string,
                max_hops: toolArgs.max_hops as number || DEFAULT_MAX_HOPS,
                include_grounding: true,
                include_evidence: true,
                // ADR-065: Epistemic status filtering
                include_epistemic_status: toolArgs.include_epistemic_status as string[] | undefined,
                exclude_epistemic_status: toolArgs.exclude_epistemic_status as string[] | undefined,
              });

              // Segment long paths for readability
              if (result.paths && result.paths.length > 0) {
                result.paths = result.paths.map(segmentPath);
              }

              return {
                content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
              };
            } else {
              const result = await client.findConnectionBySearch({
                from_query: toolArgs.from_query as string,
                to_query: toolArgs.to_query as string,
                max_hops: toolArgs.max_hops as number || DEFAULT_MAX_HOPS,
                threshold: toolArgs.threshold as number || DEFAULT_SEMANTIC_THRESHOLD,
                include_grounding: true,
                include_evidence: true,
                // ADR-065: Epistemic status filtering
                include_epistemic_status: toolArgs.include_epistemic_status as string[] | undefined,
                exclude_epistemic_status: toolArgs.exclude_epistemic_status as string[] | undefined,
              });

              const formattedText = formatConnectionPaths(result);

              return {
                content: [{ type: 'text', text: formattedText }],
              };
            }
          }

          default:
            throw new Error(`Unknown concept action: ${action}`);
        }
      }

      case 'ontology': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'list': {
            const result = await client.listOntologies();
            return {
              content: [{ type: 'text', text: formatOntologyList(result) }],
            };
          }

          case 'info': {
            const result = await client.getOntologyInfo(toolArgs.ontology_name as string);
            return {
              content: [{ type: 'text', text: formatOntologyInfo(result) }],
            };
          }

          case 'files': {
            const result = await client.getOntologyFiles(toolArgs.ontology_name as string);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'create': {
            const result = await client.createOntology(
              toolArgs.ontology_name as string,
              (toolArgs.description as string) || ''
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'rename': {
            const result = await client.renameOntology(
              toolArgs.ontology_name as string,
              toolArgs.new_name as string
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'lifecycle': {
            const result = await client.updateOntologyLifecycle(
              toolArgs.ontology_name as string,
              toolArgs.lifecycle_state as any
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'delete': {
            const result = await client.deleteOntology(
              toolArgs.ontology_name as string,
              toolArgs.force as boolean || false
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          // ADR-200 Phase 3a: Scoring & Annealing Control Surface

          case 'scores': {
            const result = await client.getOntologyScores(toolArgs.ontology_name as string);
            return {
              content: [{ type: 'text', text: formatOntologyScores(result) }],
            };
          }

          case 'score': {
            const result = await client.computeOntologyScores(toolArgs.ontology_name as string);
            return {
              content: [{ type: 'text', text: formatOntologyScores(result) }],
            };
          }

          case 'score_all': {
            const result = await client.computeAllOntologyScores();
            return {
              content: [{ type: 'text', text: formatOntologyScores(result) }],
            };
          }

          case 'candidates': {
            const result = await client.getOntologyCandidates(
              toolArgs.ontology_name as string,
              (toolArgs.limit as number) || 20
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'affinity': {
            const result = await client.getOntologyAffinity(
              toolArgs.ontology_name as string,
              (toolArgs.limit as number) || 10
            );
            return {
              content: [{ type: 'text', text: formatOntologyAffinity(result) }],
            };
          }

          case 'edges': {
            const result = await client.getOntologyEdges(
              toolArgs.ontology_name as string
            );
            return {
              content: [{ type: 'text', text: formatOntologyEdges(result) }],
            };
          }

          case 'reassign': {
            const result = await client.reassignSources(
              toolArgs.ontology_name as string,
              toolArgs.target_ontology as string,
              toolArgs.source_ids as string[]
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'dissolve': {
            const result = await client.dissolveOntology(
              toolArgs.ontology_name as string,
              toolArgs.target_ontology as string
            );
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'proposals': {
            const result = await client.listProposals({
              status: toolArgs.status as string | undefined,
              proposal_type: toolArgs.proposal_type as string | undefined,
              ontology: toolArgs.ontology_name as string | undefined,
              limit: toolArgs.limit as number | undefined,
            });
            return {
              content: [{ type: 'text', text: formatProposalList(result) }],
            };
          }

          case 'proposal_review': {
            const reviewStatus = toolArgs.status as 'approved' | 'rejected';
            if (!reviewStatus || !['approved', 'rejected'].includes(reviewStatus)) {
              throw new Error('proposal_review requires status: "approved" or "rejected"');
            }
            const result = await client.reviewProposal(
              toolArgs.proposal_id as number,
              reviewStatus,
              toolArgs.notes as string | undefined,
            );
            return {
              content: [{ type: 'text', text: formatProposalDetail(result) }],
            };
          }

          case 'annealing_cycle': {
            const result = await client.triggerAnnealingCycle({
              dry_run: toolArgs.dry_run as boolean | undefined,
              demotion_threshold: toolArgs.demotion_threshold as number | undefined,
              promotion_min_degree: toolArgs.promotion_min_degree as number | undefined,
              max_proposals: toolArgs.max_proposals as number | undefined,
            });
            return {
              content: [{ type: 'text', text: formatAnnealingCycleResult(result) }],
            };
          }

          default:
            throw new Error(`Unknown ontology action: ${action}`);
        }
      }

      case 'job': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'status': {
            const result = await client.getJobStatus(toolArgs.job_id as string);
            const formattedText = formatJobStatus(result);
            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'list': {
            const result = await client.listJobs(
              toolArgs.status as string | undefined,
              undefined,
              toolArgs.limit as number || 50
            );
            const formattedText = formatJobList(result);
            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'approve': {
            const result = await client.approveJob(toolArgs.job_id as string);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'cancel': {
            const result = await client.cancelJob(toolArgs.job_id as string);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'delete': {
            const result = await client.deleteJob(toolArgs.job_id as string, {
              purge: true,
              force: toolArgs.force as boolean || false
            });
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'cleanup': {
            const result = await client.deleteJobs({
              dryRun: toolArgs.dry_run !== false && !toolArgs.confirm,
              confirm: toolArgs.confirm as boolean || false,
              status: toolArgs.status as string | undefined,
              system: toolArgs.system_only as boolean || false,
              olderThan: toolArgs.older_than as string | undefined,
              jobType: toolArgs.job_type as string | undefined
            });

            let output = '';
            if (result.dry_run) {
              output = `## Cleanup Preview (dry run)\n\n`;
              output += `Jobs matching filters: ${result.jobs_to_delete}\n\n`;
              if (result.jobs && result.jobs.length > 0) {
                output += `| Job ID | Type | Status | Created |\n`;
                output += `|--------|------|--------|--------|\n`;
                for (const job of result.jobs.slice(0, 20)) {
                  output += `| ${job.job_id.substring(0, 16)} | ${job.job_type} | ${job.status} | ${job.created_at} |\n`;
                }
                if (result.jobs.length > 20) {
                  output += `\n... and ${result.jobs.length - 20} more\n`;
                }
              }
              output += `\nTo delete, use confirm: true`;
            } else {
              output = `## Cleanup Complete\n\n`;
              output += `Jobs deleted: ${result.jobs_deleted}\n`;
              output += `\n${result.message}`;
            }

            return {
              content: [{ type: 'text', text: output }],
            };
          }

          default:
            throw new Error(`Unknown job action: ${action}`);
        }
      }

      case 'ingest': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'text': {
            const result = await client.ingestText(toolArgs.text as string, {
              ontology: toolArgs.ontology as string,
              filename: toolArgs.filename as string | undefined,
              auto_approve: toolArgs.auto_approve !== undefined ? toolArgs.auto_approve as boolean : true,
              force: toolArgs.force as boolean || false,
              processing_mode: toolArgs.processing_mode as 'serial' | 'parallel' || 'serial',
              options: {
                target_words: toolArgs.target_words as number || 1000,
                overlap_words: toolArgs.overlap_words as number || 200,
              },
              source_type: 'mcp',
            });
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'inspect-file': {
            const filePath = toolArgs.path as string;

            if (!filePath) {
              throw new Error('path is required');
            }

            // Validate against allowlist
            const manager = new McpAllowlistManager();
            const validation = manager.validatePath(filePath);

            // Expand tilde and resolve path
            const expandedPath = filePath.startsWith('~')
              ? path.join(process.env.HOME || '', filePath.slice(1))
              : filePath;
            const absolutePath = path.resolve(expandedPath);

            const result: any = {
              path: absolutePath,
              validation: {
                allowed: validation.allowed,
                reason: validation.reason,
                hint: validation.hint,
              },
            };

            // Get file metadata if exists
            if (fs.existsSync(absolutePath)) {
              try {
                const stats = fs.statSync(absolutePath);
                const sizeMB = stats.size / (1024 * 1024);

                result.exists = true;
                result.metadata = {
                  size_bytes: stats.size,
                  size_mb: parseFloat(sizeMB.toFixed(2)),
                  type: stats.isFile() ? 'file' : stats.isDirectory() ? 'directory' : 'other',
                  modified: stats.mtime.toISOString(),
                  permissions: {
                    readable: fs.constants.R_OK && true,
                    writable: fs.constants.W_OK && true,
                  },
                };

                // Detect mime type from extension
                const ext = path.extname(absolutePath).toLowerCase();
                const mimeTypes: Record<string, string> = {
                  '.md': 'text/markdown',
                  '.txt': 'text/plain',
                  '.pdf': 'application/pdf',
                  '.png': 'image/png',
                  '.jpg': 'image/jpeg',
                  '.jpeg': 'image/jpeg',
                };
                result.metadata.mime_type = mimeTypes[ext] || 'application/octet-stream';
                result.metadata.is_image = ext in { '.png': 1, '.jpg': 1, '.jpeg': 1 };
              } catch (error: any) {
                result.exists = true;
                result.error = `Failed to read metadata: ${error.message}`;
              }
            } else {
              result.exists = false;
            }

            return {
              content: [
                {
                  type: 'text',
                  text: formatInspectFileResult(result),
                },
              ],
            };
          }

          case 'file': {
            const pathArg = toolArgs.path;
            const ontology = toolArgs.ontology as string;
            const auto_approve = toolArgs.auto_approve !== false;
            const force = toolArgs.force === true;

            if (!pathArg || !ontology) {
              throw new Error('path and ontology are required');
            }

            // Support both single path and array of paths
            const paths = Array.isArray(pathArg) ? pathArg : [pathArg];

            if (paths.length === 0) {
              throw new Error('At least one file path is required');
            }

            const manager = new McpAllowlistManager();
            const results: any[] = [];
            const errors: any[] = [];

            // Process each file
            for (const filePath of paths) {
              try {
                // Validate against allowlist
                const validation = manager.validatePath(filePath);

                if (!validation.allowed) {
                  errors.push({
                    file: filePath,
                    error: `File not allowed: ${validation.reason}. ${validation.hint || ''}`,
                  });
                  continue;
                }

                // Expand and resolve path
                const expandedPath = filePath.startsWith('~')
                  ? path.join(process.env.HOME || '', filePath.slice(1))
                  : filePath;
                const absolutePath = path.resolve(expandedPath);

                if (!fs.existsSync(absolutePath)) {
                  errors.push({
                    file: absolutePath,
                    error: 'File not found',
                  });
                  continue;
                }

                const stats = fs.statSync(absolutePath);
                if (!stats.isFile()) {
                  errors.push({
                    file: absolutePath,
                    error: 'Path is not a file',
                  });
                  continue;
                }

                // Detect if image
                const ext = path.extname(absolutePath).toLowerCase();
                const isImage = ['.png', '.jpg', '.jpeg'].includes(ext);

                const filename = path.basename(absolutePath);

                // Use unified ingestFile endpoint (same as CLI)
                // Backend automatically detects file type and routes appropriately
                const jobResponse = await client.ingestFile(absolutePath, {
                  ontology,
                  filename,
                  auto_approve,
                  force,
                });

                results.push({
                  status: 'job_id' in jobResponse ? 'submitted' : 'duplicate',
                  job_id: 'job_id' in jobResponse ? jobResponse.job_id : undefined,
                  duplicate_job_id: 'existing_job_id' in jobResponse ? jobResponse.existing_job_id : undefined,
                  file: absolutePath,
                  type: isImage ? 'image' : 'text',
                  size_bytes: stats.size,
                  ontology,
                });
              } catch (error: any) {
                errors.push({
                  file: filePath,
                  error: error.message,
                });
              }
            }

            // Return batch result if multiple files, single result otherwise
            const result = paths.length > 1 ? {
              batch: true,
              ontology,
              total_files: paths.length,
              successful: results.length,
              failed: errors.length,
              results,
              errors: errors.length > 0 ? errors : undefined,
            } : results[0] || errors[0];

            return {
              content: [
                {
                  type: 'text',
                  text: formatIngestFileResult(result),
                },
              ],
            };
          }

          case 'directory': {
            const dirPath = toolArgs.path as string;
            const ontology = toolArgs.ontology as string | undefined;
            const recursive = toolArgs.recursive === true;
            const auto_approve = toolArgs.auto_approve !== false;
            const force = toolArgs.force === true;
            const limit = (toolArgs.limit as number) || 10;
            const offset = (toolArgs.offset as number) || 0;

            if (!dirPath) {
              throw new Error('path is required');
            }

            // Expand and resolve path
            const expandedPath = dirPath.startsWith('~')
              ? path.join(process.env.HOME || '', dirPath.slice(1))
              : dirPath;
            const absolutePath = path.resolve(expandedPath);

            if (!fs.existsSync(absolutePath)) {
              throw new Error(`Directory not found: ${absolutePath}`);
            }

            const stats = fs.statSync(absolutePath);
            if (!stats.isDirectory()) {
              throw new Error(`Path is not a directory: ${absolutePath}. Use action 'file' for files.`);
            }

            // Auto-name ontology from directory if not provided
            const finalOntology = ontology || path.basename(absolutePath);

            // Validate directory against allowlist
            const manager = new McpAllowlistManager();
            const dirValidation = manager.validateDirectory(absolutePath);

            if (!dirValidation.allowed) {
              throw new Error(`Directory not allowed: ${dirValidation.reason}. ${dirValidation.hint || ''}`);
            }

            // Collect files
            const files: string[] = [];
            const skipped: string[] = [];

            function scanDirectory(dir: string) {
              const entries = fs.readdirSync(dir, { withFileTypes: true });

              for (const entry of entries) {
                const fullPath = path.join(dir, entry.name);

                if (entry.isDirectory() && recursive) {
                  scanDirectory(fullPath);
                } else if (entry.isFile()) {
                  // Validate each file
                  const fileValidation = manager.validatePath(fullPath);
                  if (fileValidation.allowed) {
                    files.push(fullPath);
                  } else {
                    skipped.push(fullPath);
                  }
                }
              }
            }

            scanDirectory(absolutePath);

            // Apply pagination
            const paginatedFiles = files.slice(offset, offset + limit);

            // TODO: Implement batch ingestion
            // For now, return summary with pagination
            const result = {
              status: 'not_implemented',
              message: 'Batch directory ingestion not yet implemented',
              directory: absolutePath,
              ontology: finalOntology,
              files_found: files.length,
              files_skipped: skipped.length,
              next_phase: 'Phase 3 - Batch ingestion implementation',
              files: paginatedFiles,
              pagination: {
                offset,
                limit,
                total: files.length,
                has_more: offset + limit < files.length,
              },
            };

            return {
              content: [
                {
                  type: 'text',
                  text: formatIngestDirectoryResult(result),
                },
              ],
            };
          }

          default:
            throw new Error(`Unknown ingest action: ${action}`);
        }
      }

      case 'source': {
        const source_id = toolArgs.source_id as string;

        if (!source_id) {
          throw new Error('source_id is required');
        }

        try {
          // First get metadata to determine content type
          const metadata = await client.getSourceMetadata(source_id);

          if (metadata.content_type === 'image') {
            // Image source - return the image
            const base64Image = await client.getSourceImageBase64(source_id);

            return {
              content: [
                {
                  type: 'image',
                  data: base64Image,
                  mimeType: 'image/jpeg',
                },
                {
                  type: 'text',
                  text: `Retrieved image for source: ${source_id}\n\nDocument: ${metadata.document}\nParagraph: ${metadata.paragraph}\n\nThis image was extracted from the knowledge graph. You can:\n1. Compare the image to extracted concepts to verify accuracy\n2. Create a new description if something was missed\n3. Use ingest action to add refined descriptions`,
                },
              ],
            };
          } else {
            // Text source - return metadata with full_text
            const lines = [
              `📄 Source: ${source_id}`,
              '',
              `Document: ${metadata.document}`,
              `Paragraph: ${metadata.paragraph}`,
              `Content Type: ${metadata.content_type || 'text'}`,
              '',
            ];

            if (metadata.char_offset_start !== undefined && metadata.char_offset_end !== undefined) {
              lines.push(`Character Range: ${metadata.char_offset_start}-${metadata.char_offset_end}`);
            }

            if (metadata.file_path) {
              lines.push(`File Path: ${metadata.file_path}`);
            }

            lines.push('', '--- Full Text ---', '', metadata.full_text || '(no text content)');

            return {
              content: [{ type: 'text', text: lines.join('\n') }],
            };
          }
        } catch (error: any) {
          if (error.response?.status === 404) {
            throw new Error(`Source ${source_id} not found`);
          }
          throw error;
        }
      }

      case 'epistemic_status': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'list': {
            const statusFilter = toolArgs.status_filter as string | undefined;
            const result = await client.listEpistemicStatus(statusFilter);
            const output = formatEpistemicStatusList(result);

            return {
              content: [{ type: 'text', text: output }],
            };
          }

          case 'show': {
            const relationshipType = toolArgs.relationship_type as string;
            if (!relationshipType) {
              throw new Error('relationship_type is required for show action');
            }

            const result = await client.getEpistemicStatus(relationshipType);
            const output = formatEpistemicStatusDetails(result);

            return {
              content: [{ type: 'text', text: output }],
            };
          }

          case 'measure': {
            const sampleSize = (toolArgs.sample_size as number) || 100;
            const store = (toolArgs.store as boolean) !== false;
            const verbose = (toolArgs.verbose as boolean) || false;

            const result = await client.measureEpistemicStatus({
              sample_size: sampleSize,
              store: store,
              verbose: verbose,
            });

            const output = formatEpistemicStatusMeasurement(result);

            return {
              content: [{ type: 'text', text: output }],
            };
          }

          default:
            throw new Error(`Unknown epistemic_status action: ${action}`);
        }
      }

      case 'analyze_polarity_axis': {
        const result = await client.analyzePolarityAxis({
          positive_pole_id: toolArgs.positive_pole_id as string,
          negative_pole_id: toolArgs.negative_pole_id as string,
          candidate_ids: toolArgs.candidate_ids as string[] | undefined,
          auto_discover: toolArgs.auto_discover !== false,
          max_candidates: (toolArgs.max_candidates as number) || 20,
          max_hops: (toolArgs.max_hops as number) || 2,
        });

        const formattedText = formatPolarityAxisResults(result);

        return {
          content: [{ type: 'text', text: formattedText }],
        };
      }

      case 'artifact': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'list': {
            const result = await client.listArtifacts({
              artifact_type: toolArgs.artifact_type as string | undefined,
              representation: toolArgs.representation as string | undefined,
              ontology: toolArgs.ontology as string | undefined,
              limit: (toolArgs.limit as number) || 20,
              offset: (toolArgs.offset as number) || 0,
            });

            // Format artifact list for readability
            const lines = [
              `📦 Artifacts (${result.total} total, showing ${result.artifacts.length})`,
              '',
            ];

            if (result.artifacts.length === 0) {
              lines.push('No artifacts found.');
            } else {
              for (const artifact of result.artifacts) {
                const freshness = artifact.is_fresh ? '✓ Fresh' : '⚠ Stale';
                lines.push(`[${artifact.id}] ${artifact.artifact_type} - ${artifact.name || '(unnamed)'}`);
                lines.push(`    Representation: ${artifact.representation}`);
                lines.push(`    ${freshness} (epoch: ${artifact.graph_epoch})`);
                if (artifact.ontology) {
                  lines.push(`    Ontology: ${artifact.ontology}`);
                }
                lines.push(`    Created: ${artifact.created_at}`);
                lines.push('');
              }
            }

            if (result.total > result.offset + result.artifacts.length) {
              lines.push(`Use offset=${result.offset + result.limit} to see more.`);
            }

            return {
              content: [{ type: 'text', text: lines.join('\n') }],
            };
          }

          case 'show': {
            const artifactId = toolArgs.artifact_id as number;
            if (!artifactId) {
              throw new Error('artifact_id is required for show action');
            }

            const result = await client.getArtifact(artifactId);

            // Format artifact metadata
            const lines = [
              `📦 Artifact ${result.id}`,
              '',
              `Type: ${result.artifact_type}`,
              `Representation: ${result.representation}`,
              `Name: ${result.name || '(unnamed)'}`,
              `Owner ID: ${result.owner_id}`,
              '',
              `Freshness: ${result.is_fresh ? '✓ Fresh' : '⚠ Stale (graph changed)'}`,
              `Graph Epoch: ${result.graph_epoch}`,
              '',
              `Created: ${result.created_at}`,
              result.expires_at ? `Expires: ${result.expires_at}` : '',
              result.ontology ? `Ontology: ${result.ontology}` : '',
              '',
              'Parameters:',
              JSON.stringify(result.parameters, null, 2),
            ].filter(Boolean);

            return {
              content: [{ type: 'text', text: lines.join('\n') }],
            };
          }

          case 'payload': {
            const artifactId = toolArgs.artifact_id as number;
            if (!artifactId) {
              throw new Error('artifact_id is required for payload action');
            }

            const result = await client.getArtifactPayload(artifactId);

            // Return full artifact with payload
            const lines = [
              `📦 Artifact ${result.id} (${result.artifact_type})`,
              `Freshness: ${result.is_fresh ? '✓ Fresh' : '⚠ Stale'}`,
              '',
              'Payload:',
              JSON.stringify(result.payload, null, 2),
            ];

            return {
              content: [{ type: 'text', text: lines.join('\n') }],
            };
          }

          default:
            throw new Error(`Unknown artifact action: ${action}`);
        }
      }

      case 'document': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'list': {
            const result = await client.listDocuments({
              ontology: toolArgs.ontology as string | undefined,
              limit: (toolArgs.limit as number) || 50,
              offset: (toolArgs.offset as number) || 0,
            });

            const formattedText = formatDocumentList(result);
            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'show': {
            const documentId = toolArgs.document_id as string;
            if (!documentId) {
              throw new Error('document_id is required for show action');
            }

            const result = await client.getDocumentContent(documentId);
            const formattedText = formatDocumentContent(result);
            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'concepts': {
            const documentId = toolArgs.document_id as string;
            if (!documentId) {
              throw new Error('document_id is required for concepts action');
            }

            const includeDetails = toolArgs.include_details === true;
            const result = await client.getDocumentConcepts(documentId);

            if (includeDetails) {
              // Fetch full details for each unique concept
              const uniqueConceptIds = [...new Set(result.concepts.map((c: any) => c.concept_id))];
              const conceptDetails: any[] = [];

              for (const conceptId of uniqueConceptIds) {
                try {
                  const details = await client.getConceptDetails(conceptId, true);
                  conceptDetails.push(details);
                } catch (err: any) {
                  conceptDetails.push({
                    concept_id: conceptId,
                    label: `(failed to load: ${err.message})`,
                    error: true,
                  });
                }
              }

              const formattedText = formatDocumentConceptsDetailed(result, conceptDetails);
              return {
                content: [{ type: 'text', text: formattedText }],
              };
            } else {
              const formattedText = formatDocumentConcepts(result);
              return {
                content: [{ type: 'text', text: formattedText }],
              };
            }
          }

          default:
            throw new Error(`Unknown document action: ${action}`);
        }
      }

      // ADR-089 Phase 3a: Graph CRUD Tool Handler (Refactored)
      case 'graph': {
        const action = toolArgs.action as string;
        const entity = toolArgs.entity as string;

        // Entity required for all actions except queue
        if (action !== 'queue' && !entity) {
          throw new Error('entity is required (concept or edge)');
        }

        // Create executor instance for this request
        const executor = new GraphOperationExecutor(client);

        switch (action) {
          case 'create': {
            if (entity === 'concept') {
              const result = await executor.createConcept({
                label: toolArgs.label as string,
                ontology: toolArgs.ontology as string,
                description: toolArgs.description as string | undefined,
                search_terms: toolArgs.search_terms as string[] | undefined,
                matching_mode: toolArgs.matching_mode as 'auto' | 'force_create' | 'match_only' | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphConceptResult(result.data, 'create') }],
              };
            } else if (entity === 'edge') {
              const result = await executor.createEdge({
                from_concept_id: toolArgs.from_concept_id as string | undefined,
                from_label: toolArgs.from_label as string | undefined,
                to_concept_id: toolArgs.to_concept_id as string | undefined,
                to_label: toolArgs.to_label as string | undefined,
                relationship_type: toolArgs.relationship_type as string,
                category: toolArgs.category as string | undefined,
                confidence: toolArgs.confidence as number | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphEdgeResult(result.data, 'create') }],
              };
            } else {
              throw new Error(`Unknown entity type: ${entity}`);
            }
          }

          case 'list': {
            if (entity === 'concept') {
              const result = await executor.listConcepts({
                ontology: toolArgs.ontology as string | undefined,
                label_contains: toolArgs.label_contains as string | undefined,
                creation_method: toolArgs.creation_method as string | undefined,
                offset: toolArgs.offset as number | undefined,
                limit: toolArgs.limit as number | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphConceptList(result.data) }],
              };
            } else if (entity === 'edge') {
              const result = await executor.listEdges({
                from_concept_id: toolArgs.from_concept_id as string | undefined,
                from_label: toolArgs.from_label as string | undefined,
                to_concept_id: toolArgs.to_concept_id as string | undefined,
                to_label: toolArgs.to_label as string | undefined,
                relationship_type: toolArgs.relationship_type as string | undefined,
                category: toolArgs.category as string | undefined,
                source: toolArgs.source as string | undefined,
                offset: toolArgs.offset as number | undefined,
                limit: toolArgs.limit as number | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphEdgeList(result.data) }],
              };
            } else {
              throw new Error(`Unknown entity type: ${entity}`);
            }
          }

          case 'edit': {
            if (entity === 'concept') {
              const result = await executor.editConcept({
                concept_id: toolArgs.concept_id as string,
                label: toolArgs.label as string | undefined,
                description: toolArgs.description as string | undefined,
                search_terms: toolArgs.search_terms as string[] | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphConceptResult(result.data, 'edit') }],
              };
            } else if (entity === 'edge') {
              const result = await executor.editEdge({
                from_concept_id: toolArgs.from_concept_id as string | undefined,
                from_label: toolArgs.from_label as string | undefined,
                to_concept_id: toolArgs.to_concept_id as string | undefined,
                to_label: toolArgs.to_label as string | undefined,
                relationship_type: toolArgs.relationship_type as string,
                confidence: toolArgs.confidence as number | undefined,
                category: toolArgs.category as string | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphEdgeResult(result.data, 'edit') }],
              };
            } else {
              throw new Error(`Unknown entity type: ${entity}`);
            }
          }

          case 'delete': {
            if (entity === 'concept') {
              const result = await executor.deleteConcept({
                concept_id: toolArgs.concept_id as string,
                cascade: toolArgs.cascade as boolean | undefined,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphConceptResult(result.data, 'delete') }],
              };
            } else if (entity === 'edge') {
              const result = await executor.deleteEdge({
                from_concept_id: toolArgs.from_concept_id as string | undefined,
                from_label: toolArgs.from_label as string | undefined,
                to_concept_id: toolArgs.to_concept_id as string | undefined,
                to_label: toolArgs.to_label as string | undefined,
                relationship_type: toolArgs.relationship_type as string,
              });
              if (!result.success) throw new Error(result.error);
              return {
                content: [{ type: 'text', text: formatGraphEdgeResult(result.data, 'delete') }],
              };
            } else {
              throw new Error(`Unknown entity type: ${entity}`);
            }
          }

          case 'queue': {
            const operations = toolArgs.operations as QueueOperation[];
            const continueOnError = toolArgs.continue_on_error === true;

            if (!operations || !Array.isArray(operations)) {
              throw new Error('operations array is required for queue action');
            }
            if (operations.length === 0) {
              throw new Error('operations array cannot be empty');
            }
            if (operations.length > 20) {
              throw new Error(`Queue too large: ${operations.length} operations (max 20)`);
            }

            const queueResult = await executor.executeQueue(operations, continueOnError);
            const formattedOutput = formatGraphQueueResult(queueResult, operations.length);

            return {
              content: [{ type: 'text', text: formattedOutput }],
            };
          }

          default:
            throw new Error(`Unknown graph action: ${action}. Use: create, edit, delete, list, or queue`);
        }
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              error: error.message,
              details: error.response?.data || error.toString(),
            },
            null,
            2
          ),
        },
      ],
      isError: true,
    };
  }
});

/**
 * Prompt Handlers - Provide exploration guidance
 */
server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return {
    prompts: [
      {
        name: 'explore-graph',
        description: 'Learn how to explore the knowledge graph effectively',
      },
    ],
  };
});

server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name } = request.params;

  if (name === 'explore-graph') {
    return {
      messages: [
        {
          role: 'user',
          content: {
            type: 'text',
            text: `How should I explore this knowledge graph?`,
          },
        },
        {
          role: 'assistant',
          content: {
            type: 'text',
            text: `# Knowledge Graph Exploration Guide

This system transforms documents into semantic concept graphs with grounding strength (reliability scores) and evidence (quoted text).

## Exploration Workflow:

1. **search** - Your entry point. Find concepts by semantic similarity.
   - Returns RICH DATA:
     * Grounding strength: Reliability score (-1.0 to 1.0)
     * Diversity score: % showing conceptual richness
     * Authenticated diversity: Support/contradiction indicator (✅✓⚠❌)
     * Evidence samples: Quoted text from sources
     * Image indicators: Visual evidence available
   - Use 2-3 word phrases (e.g., "configuration management", "licensing issues")

2. **concept (action: connect)** - **PRIORITIZE THIS** - Discover HOW concepts connect.
   - This is often MORE VALUABLE than isolated concept details
   - Trace problem→solution chains, cause/effect relationships
   - See grounding + evidence at each step in the path
   - Reveals narrative flow through ideas
   - **PERFORMANCE CRITICAL**: Start with threshold=0.8, max_hops=3
   - Lower thresholds exponentially increase query time (0.6 = slow, <0.6 = very slow)

3. **concept (action: details)** - See the complete picture for any concept.
   - Returns: ALL quoted evidence + relationships
   - IMPORTANT: Contradicted concepts (negative grounding) are VALUABLE - they show problems/outdated approaches
   - Use this after finding interesting concepts via search or connect

4. **concept (action: related)** - Explore neighborhoods.
   - Find what's nearby in the concept graph
   - Discover clusters and themes
   - Use depth=1-2 for neighbors, 3-4 for broader exploration

## Resources (Fresh Data):

Use MCP resources for quick status checks without consuming tool budget:
- **database/stats** - Concept counts, relationships, ontologies
- **database/info** - PostgreSQL version, AGE extension
- **database/health** - Connection status
- **system/status** - Job scheduler, resource usage
- **api/health** - API server status

## Understanding the Scores:

**Grounding Strength (-1.0 to 1.0)** - Reliability/Contradiction
- **Positive (>0.7)**: Well-supported, reliable concept
- **Moderate (0.3-0.7)**: Mixed evidence, use with caution
- **Negative (<0)**: Contradicted or presented as a problem
- **Contradicted (-1.0)**: Often the most interesting - shows pain points!

**Diversity Score (0-100%)** - Conceptual Richness
- High diversity: Concept connects to many different related concepts
- Shows breadth of connections in the knowledge graph
- Higher scores indicate more interconnected, central concepts

**Authenticated Diversity (✅✓⚠❌)** - Directional Quality
- ✅ Diverse support: Strong positive evidence across many connections
- ✓ Some support: Moderate positive evidence
- ⚠ Weak contradiction: Some conflicting evidence
- ❌ Diverse contradiction: Strong negative evidence across connections
- Combines grounding with diversity to show reliability + breadth

## How to Use the Scores:

**High Grounding + High Diversity** → Central, well-established concepts
- These are reliable anchor points for exploration
- Good starting points for connection queries

**High Grounding + Low Diversity** → Specialized, focused concepts
- Domain-specific, niche ideas with strong support
- May be isolated or newly added

**Low/Negative Grounding + High Diversity** → Controversial or evolving concepts
- Contested ideas with multiple perspectives
- Often the most interesting for understanding debates

**Authenticated Diversity** → Quick quality check
- Use ✅ results confidently
- Investigate ⚠ and ❌ results for contradictions and problems

## Pro Tips:
- **Connection queries first**: After search, immediately explore HOW concepts connect - this reveals causality and narrative
- Use diversity scores to find central vs. peripheral concepts
- Start broad with search, then drill down with concept details
- Contradicted concepts reveal what DIDN'T work - goldmines for learning
- Connection paths tell stories - follow the evidence chain
- Use resources for quick status checks instead of tools
- **Performance**: Keep threshold >= 0.75 for connect queries to avoid slow/hung queries`,
          },
        },
      ],
    };
  }

  throw new Error(`Unknown prompt: ${name}`);
});

/**
 * Start the MCP server
 */
async function main() {
  // Initialize authentication before starting server
  await initializeAuth();
  client = createAuthenticatedClient();

  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is used for MCP protocol)
  console.error('Knowledge Graph MCP Server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
