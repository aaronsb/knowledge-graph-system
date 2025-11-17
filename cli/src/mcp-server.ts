#!/usr/bin/env node
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
} from './mcp/formatters.js';
import * as fs from 'fs';
import * as path from 'path';

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
    version: '0.1.0',
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
        description: `Search for concepts using semantic similarity. Your ENTRY POINT to the graph.

RETURNS RICH DATA FOR EACH CONCEPT:
- Grounding strength (-1.0 to 1.0): Reliability/contradiction score
- Diversity score: Conceptual richness (% of diverse connections)
- Authenticated diversity: Support vs contradiction indicator (✅✓⚠❌)
- Evidence samples: Quoted text from source documents
- Image indicators: Visual evidence when available
- Document sources: Where concepts originated

RECOMMENDED WORKFLOW: After search, use concept (action: "connect") to find HOW concepts relate - this reveals narrative flows and cause/effect chains that individual searches cannot show. Connection paths are often more valuable than isolated concepts.

Use 2-3 word phrases (e.g., "linear thinking patterns").`,
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")',
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
              enum: ['list', 'info', 'files', 'delete'],
              description: 'Operation: "list" (all ontologies), "info" (details), "files" (source files), "delete" (remove)',
            },
            ontology_name: {
              type: 'string',
              description: 'Ontology name (required for info, files, delete)',
            },
            force: {
              type: 'boolean',
              description: 'Confirm deletion (required for delete)',
              default: false,
            },
          },
          required: ['action'],
        },
      },
      {
        name: 'job',
        description: 'Manage ingestion jobs: get status, list jobs, approve, or cancel. Use action parameter to specify operation.',
        inputSchema: {
          type: 'object',
          properties: {
            action: {
              type: 'string',
              enum: ['status', 'list', 'approve', 'cancel'],
              description: 'Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job)',
            },
            job_id: {
              type: 'string',
              description: 'Job ID (required for status, approve, cancel)',
            },
            status: {
              type: 'string',
              description: 'Filter by status for list (pending, awaiting_approval, running, completed, failed)',
            },
            limit: {
              type: 'number',
              description: 'Max jobs to return for list (default: 50)',
              default: 50,
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
        description: 'Retrieve original image for a source node (ADR-057). Use when evidence has image metadata. Enables visual verification and refinement loop.',
        inputSchema: {
          type: 'object',
          properties: {
            source_id: {
              type: 'string',
              description: 'Source ID from evidence (has_image=true)',
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
        const limit = toolArgs.limit as number || 10;
        const min_similarity = toolArgs.min_similarity as number || DEFAULT_SEARCH_SIMILARITY;
        const offset = toolArgs.offset as number || 0;

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

      case 'concept': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'details': {
            const includeGrounding = toolArgs.include_grounding !== false;
            const result = await client.getConceptDetails(
              toolArgs.concept_id as string,
              includeGrounding
            );

            const formattedText = formatConceptDetails(result);

            return {
              content: [{ type: 'text', text: formattedText }],
            };
          }

          case 'related': {
            const result = await client.findRelatedConcepts({
              concept_id: toolArgs.concept_id as string,
              max_depth: toolArgs.max_depth as number || DEFAULT_MAX_DEPTH,
              relationship_types: toolArgs.relationship_types as string[] | undefined,
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
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'info': {
            const result = await client.getOntologyInfo(toolArgs.ontology_name as string);
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
            };
          }

          case 'files': {
            const result = await client.getOntologyFiles(toolArgs.ontology_name as string);
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
            return {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
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
                text: `Retrieved image for source: ${source_id}\n\nThis image was extracted from the knowledge graph. You can now:\n1. Compare the image to the extracted concepts to verify accuracy\n2. Create a new description if you notice anything that was missed\n3. Use kg ingest text to create a refined description that will be associated with this image\n\nThis creates an emergent refinement loop: visual verification → new description → concept association → improved graph understanding.`,
              },
            ],
          };
        } catch (error: any) {
          if (error.response?.status === 404) {
            throw new Error(`Source ${source_id} not found or is not an image source. Only image sources have retrievable images.`);
          } else if (error.response?.status === 400) {
            throw new Error(`Source ${source_id} is not an image (content_type != 'image')`);
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
