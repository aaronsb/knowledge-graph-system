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
import {
  formatSearchResults,
  formatConceptDetails,
  formatConnectionPaths,
  formatRelatedConcepts,
  formatJobStatus,
} from './mcp/formatters.js';

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
 * This system transforms documents into semantic concept graphs. Explore by:
 * 1. search - Find entry points (returns grounding + evidence samples)
 * 2. concept - Work with concepts (details, related, connections)
 * 3. ontology - Manage ontologies (list, info, files, delete)
 * 4. job - Manage jobs (status, list, approve, cancel)
 * 5. ingest - Submit text for concept extraction
 * 6. source - Retrieve source images for visual verification
 *
 * Resources provide fresh data on-demand without consuming tool budget:
 * - database/stats, database/info, database/health
 * - system/status, api/health
 *
 * Grounding strength (-1.0 to 1.0) shows concept reliability. Negative = contradicted/problem.
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
        description: `Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: concept (details, related, connect), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").`,
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
        description: 'Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts). Use action parameter to specify operation.',
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
              description: 'Max path length (default: 5)',
              default: 5,
            },
            threshold: {
              type: 'number',
              description: 'Similarity threshold for semantic mode (default: 0.5)',
              default: 0.5,
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
        description: 'Submit text content for concept extraction. Chunks text, extracts concepts using LLM, and adds them to the specified ontology. Returns job ID for tracking.',
        inputSchema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: 'Text content to ingest',
            },
            ontology: {
              type: 'string',
              description: 'Ontology name (e.g., "Project Documentation", "Research Notes")',
            },
            filename: {
              type: 'string',
              description: 'Optional filename for source tracking',
            },
            auto_approve: {
              type: 'boolean',
              description: 'Auto-approve processing (default: true)',
              default: true,
            },
            force: {
              type: 'boolean',
              description: 'Force re-ingestion (default: false)',
              default: false,
            },
            processing_mode: {
              type: 'string',
              enum: ['serial', 'parallel'],
              description: 'Processing mode (default: serial)',
              default: 'serial',
            },
            target_words: {
              type: 'number',
              description: 'Words per chunk (default: 1000)',
              default: 1000,
            },
            overlap_words: {
              type: 'number',
              description: 'Overlap between chunks (default: 200)',
              default: 200,
            },
          },
          required: ['text', 'ontology'],
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
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'database/info': {
        const result = await client.getDatabaseInfo();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'database/health': {
        const result = await client.getDatabaseHealth();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'system/status': {
        const result = await client.getSystemStatus();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'api/health': {
        const result = await client.health();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
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
        const min_similarity = toolArgs.min_similarity as number || 0.7;
        const offset = toolArgs.offset as number || 0;

        const result = await client.searchConcepts({
          query,
          limit,
          min_similarity,
          offset,
          include_grounding: true,
          include_evidence: true,
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
              max_depth: toolArgs.max_depth as number || 2,
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
                max_hops: toolArgs.max_hops as number || 5,
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
                max_hops: toolArgs.max_hops as number || 5,
                threshold: toolArgs.threshold as number || 0.5,
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
   - Returns: Grounding strength + sample evidence
   - Use 2-3 word phrases (e.g., "configuration management", "licensing issues")

2. **concept (action: details)** - See the complete picture for any concept.
   - Returns: ALL quoted evidence + relationships
   - IMPORTANT: Contradicted concepts (negative grounding) are VALUABLE - they show problems/outdated approaches

3. **concept (action: connect)** - Discover HOW concepts connect.
   - Trace problem→solution chains
   - See grounding + evidence at each step in the path
   - Reveals narrative flow through ideas

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

## Grounding Strength (-1.0 to 1.0):
- **Positive (>0.7)**: Well-supported, reliable concept
- **Moderate (0.3-0.7)**: Mixed evidence, use with caution
- **Negative (<0)**: Contradicted or presented as a problem
- **Contradicted (-1.0)**: Often the most interesting - shows pain points!

## Pro Tips:
- Start broad with search, then drill down with concept details
- Contradicted concepts reveal what DIDN'T work - goldmines for learning
- Connection paths tell stories - follow the evidence chain
- Use resources for quick status checks instead of tools`,
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
