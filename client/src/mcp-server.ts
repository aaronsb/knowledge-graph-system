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
    },
  }
);

/**
 * Knowledge Graph Server - Exploration Guide
 *
 * This system transforms documents into semantic concept graphs. Explore by:
 * 1. search_concepts - Find entry points (returns grounding + evidence samples)
 * 2. get_concept_details - See ALL evidence (even contradicted concepts are valuable!)
 * 3. find_connection_by_search - Trace problem→solution paths, discover narratives
 * 4. find_related_concepts - Explore neighborhoods and clusters
 *
 * Grounding strength (-1.0 to 1.0) shows concept reliability. Negative = contradicted/problem.
 */

// JWT token storage for authenticated session
let jwtToken: string | null = null;
let tokenRefreshTimer: NodeJS.Timeout | null = null;

/**
 * Perform login and get JWT token
 * Returns the token and expiry time in milliseconds
 */
async function performLogin(): Promise<{ token: string; expiresInMs: number } | null> {
  const username = process.env.KG_USERNAME;
  const password = process.env.KG_PASSWORD;
  const apiUrl = process.env.KG_API_URL || 'http://localhost:8000';

  if (!username || !password) {
    return null;
  }

  try {
    const authClient = new AuthClient(apiUrl);
    const loginResponse = await authClient.login({ username, password });

    const expiresInMs = loginResponse.expires_in * 1000;
    const expiryTime = new Date(Date.now() + expiresInMs);

    console.error(`[MCP Auth] Successfully authenticated as ${username}`);
    console.error(`[MCP Auth] Token expires at ${expiryTime.toISOString()}`);

    return {
      token: loginResponse.access_token,
      expiresInMs
    };
  } catch (error: any) {
    console.error(`[MCP Auth] Failed to authenticate: ${error.message}`);
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
    console.error('[MCP Auth] Refreshing authentication token...');

    const result = await performLogin();
    if (result) {
      jwtToken = result.token;

      // Update the token in the client
      if (client) {
        client.setMcpJwtToken(result.token);
      }

      // Schedule next refresh
      scheduleTokenRefresh(result.expiresInMs);
    } else {
      console.error('[MCP Auth] Token refresh failed! Operations may fail with 401 errors.');
      console.error('[MCP Auth] Please restart the MCP server to re-authenticate.');
    }
  }, refreshInMs);
}

/**
 * Automatically login if username/password provided in environment
 * This allows the MCP server to authenticate transparently without
 * the AI being aware of authentication requirements.
 */
async function initializeAuth(): Promise<void> {
  const username = process.env.KG_USERNAME;
  const password = process.env.KG_PASSWORD;

  if (username && password) {
    const result = await performLogin();

    if (result) {
      jwtToken = result.token;
      scheduleTokenRefresh(result.expiresInMs);
    } else {
      console.error('[MCP Auth] The MCP server will operate without authentication.');
      console.error('[MCP Auth] Some operations may fail with 401 errors.');
    }
  } else {
    console.error('[MCP Auth] No credentials provided (KG_USERNAME/KG_PASSWORD).');
    console.error('[MCP Auth] The MCP server will operate without authentication.');
  }
}

/**
 * Create an authenticated API client
 * If we have a JWT token from login, inject it into the client
 */
function createAuthenticatedClient(): KnowledgeGraphClient {
  const client = createClientFromEnv();

  // If we have a JWT token, set it on the client
  if (jwtToken) {
    client.setMcpJwtToken(jwtToken);
  }

  return client;
}

// Client instance - will be initialized in main() before server starts
let client: KnowledgeGraphClient;

/**
 * Tool Definitions
 *
 * Each tool wraps a method from the KnowledgeGraphClient,
 * reusing the same types and API calls as the CLI.
 */

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // ========== Search & Query Tools ==========
      {
        name: 'search_concepts',
        description: `Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: get_concept_details (all evidence), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").`,
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
        name: 'get_concept_details',
        description: `Retrieve ALL evidence (quoted text) and relationships for a concept. Use to see the complete picture: ALL quotes, source locations, SUPPORTS/CONTRADICTS relationships. Contradicted concepts (negative grounding) are VALUABLE - show problems/outdated approaches.`,
        inputSchema: {
          type: 'object',
          properties: {
            concept_id: {
              type: 'string',
              description: 'The unique concept identifier (from search results or graph traversal)',
            },
            include_grounding: {
              type: 'boolean',
              description: 'Include grounding_strength calculation (ADR-044: probabilistic truth convergence). Default: true. Set to false only for faster queries when grounding not needed.',
              default: true,
            },
          },
          required: ['concept_id'],
        },
      },
      {
        name: 'find_related_concepts',
        description: `Explore concept neighborhood. Discovers what's connected and how (SUPPORTS, CONTRADICTS, ENABLES). Returns concepts grouped by distance. Use depth=1-2 for neighbors, 3-4 for broader exploration.`,
        inputSchema: {
          type: 'object',
          properties: {
            concept_id: {
              type: 'string',
              description: 'Starting concept ID for traversal',
            },
            max_depth: {
              type: 'number',
              description: 'Maximum traversal depth in hops (1-5, default: 2). Depth 1-2 is fast, 3-4 moderate, 5 can be slow.',
              default: 2,
            },
            relationship_types: {
              type: 'array',
              items: { type: 'string' },
              description: 'Optional filter for specific relationship types (e.g., ["IMPLIES", "SUPPORTS", "CONTRADICTS"])',
            },
          },
          required: ['concept_id'],
        },
      },
      {
        name: 'find_connection',
        description: 'Find shortest paths between two concepts using exact concept IDs. Uses graph traversal to find up to 5 shortest paths. For semantic phrase matching, use find_connection_by_search instead.',
        inputSchema: {
          type: 'object',
          properties: {
            from_id: {
              type: 'string',
              description: 'Starting concept ID (exact match required)',
            },
            to_id: {
              type: 'string',
              description: 'Target concept ID (exact match required)',
            },
            max_hops: {
              type: 'number',
              description: 'Maximum path length to search (1-10 hops, default: 5)',
              default: 5,
            },
          },
          required: ['from_id', 'to_id'],
        },
      },
      {
        name: 'find_connection_by_search',
        description: `Discover HOW concepts connect. Find paths between ideas, trace problem→solution chains, see grounding+evidence at each step. Returns narrative flow through the graph. Use 2-3 word phrases (e.g., "licensing issues", "AGE benefits").`,
        inputSchema: {
          type: 'object',
          properties: {
            from_query: {
              type: 'string',
              description: 'Semantic phrase for starting concept (use specific 2-3 word phrases for best results)',
            },
            to_query: {
              type: 'string',
              description: 'Semantic phrase for target concept (use specific 2-3 word phrases)',
            },
            max_hops: {
              type: 'number',
              description: 'Maximum path length to search (default: 5)',
              default: 5,
            },
            threshold: {
              type: 'number',
              description: 'Minimum similarity threshold 0.0-1.0 (default: 0.5 for 50%, lower to 0.3-0.4 for weaker matches)',
              default: 0.5,
            },
          },
          required: ['from_query', 'to_query'],
        },
      },

      // ========== Database Tools ==========
      {
        name: 'get_database_stats',
        description: 'Get database statistics including total counts of concepts, sources, instances, relationships, and ontologies. Useful for understanding graph size and structure.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_database_info',
        description: 'Get database connection information including PostgreSQL version, Apache AGE extension details, and connection status.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_database_health',
        description: 'Check database health status. Verifies PostgreSQL connection and Apache AGE graph availability.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },

      // ========== Ontology Tools ==========
      {
        name: 'list_ontologies',
        description: 'List all ontologies (collections) in the knowledge graph with concept counts and statistics.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_ontology_info',
        description: 'Get detailed information about a specific ontology including concept count, relationship types, and source documents.',
        inputSchema: {
          type: 'object',
          properties: {
            ontology_name: {
              type: 'string',
              description: 'Name of the ontology to retrieve',
            },
          },
          required: ['ontology_name'],
        },
      },
      {
        name: 'get_ontology_files',
        description: 'List all source files that have been ingested into a specific ontology with metadata.',
        inputSchema: {
          type: 'object',
          properties: {
            ontology_name: {
              type: 'string',
              description: 'Name of the ontology',
            },
          },
          required: ['ontology_name'],
        },
      },
      {
        name: 'delete_ontology',
        description: 'Delete an entire ontology and all its concepts, relationships, and evidence. Requires force=true for confirmation.',
        inputSchema: {
          type: 'object',
          properties: {
            ontology_name: {
              type: 'string',
              description: 'Name of the ontology to delete',
            },
            force: {
              type: 'boolean',
              description: 'Must be true to confirm deletion',
              default: false,
            },
          },
          required: ['ontology_name', 'force'],
        },
      },

      // ========== Job Tools ==========
      {
        name: 'get_job_status',
        description: 'Get status of an ingestion job including progress, cost estimates, and any errors. Use job_id from ingest operations.',
        inputSchema: {
          type: 'object',
          properties: {
            job_id: {
              type: 'string',
              description: 'Job ID returned from ingest operation',
            },
          },
          required: ['job_id'],
        },
      },
      {
        name: 'list_jobs',
        description: 'List recent ingestion jobs with optional filtering by status (pending, awaiting_approval, running, completed, failed).',
        inputSchema: {
          type: 'object',
          properties: {
            status: {
              type: 'string',
              description: 'Filter by job status (optional)',
            },
            limit: {
              type: 'number',
              description: 'Maximum number of jobs to return (default: 50)',
              default: 50,
            },
          },
        },
      },
      {
        name: 'approve_job',
        description: 'Approve a job for processing after reviewing cost estimates (ADR-014 approval workflow). Job must be in awaiting_approval status.',
        inputSchema: {
          type: 'object',
          properties: {
            job_id: {
              type: 'string',
              description: 'Job ID to approve',
            },
          },
          required: ['job_id'],
        },
      },
      {
        name: 'cancel_job',
        description: 'Cancel a pending or running job. Cannot cancel completed or failed jobs.',
        inputSchema: {
          type: 'object',
          properties: {
            job_id: {
              type: 'string',
              description: 'Job ID to cancel',
            },
          },
          required: ['job_id'],
        },
      },

      // ========== Ingestion Tools ==========
      {
        name: 'ingest_text',
        description: 'Submit text content to the knowledge graph for concept extraction. Automatically processes and extracts concepts, relationships, and evidence. Specify which ontology (knowledge domain) to add the concepts to. The system will chunk the text, extract concepts using LLM, and add them to the graph. Returns a job ID for tracking progress.',
        inputSchema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: 'Text content to ingest into the knowledge graph',
            },
            ontology: {
              type: 'string',
              description: 'Ontology/collection name (ask user which knowledge domain this belongs to, e.g., "Project Documentation", "Research Notes", "Meeting Notes")',
            },
            filename: {
              type: 'string',
              description: 'Optional filename for source tracking (default: "text_input")',
            },
            auto_approve: {
              type: 'boolean',
              description: 'Auto-approve and start processing immediately (default: true). Set to false to require manual approval.',
              default: true,
            },
            force: {
              type: 'boolean',
              description: 'Force re-ingestion even if content already exists (default: false)',
              default: false,
            },
            processing_mode: {
              type: 'string',
              enum: ['serial', 'parallel'],
              description: 'Processing mode: serial (clean, recommended) or parallel (fast, may duplicate concepts)',
              default: 'serial',
            },
            target_words: {
              type: 'number',
              description: 'Target words per chunk (default: 1000, range: 500-2000)',
              default: 1000,
            },
            overlap_words: {
              type: 'number',
              description: 'Word overlap between chunks for context (default: 200)',
              default: 200,
            },
          },
          required: ['text', 'ontology'],
        },
      },

      // ========== System Tools ==========
      {
        name: 'get_api_health',
        description: 'Check API server health status. Returns status and timestamp.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'get_system_status',
        description: 'Get comprehensive system status including database, job scheduler, and resource usage statistics.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
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

1. **search_concepts** - Your entry point. Find concepts by semantic similarity.
   - Returns: Grounding strength + sample evidence
   - Use 2-3 word phrases (e.g., "configuration management", "licensing issues")

2. **get_concept_details** - See the complete picture for any concept.
   - Returns: ALL quoted evidence + relationships
   - IMPORTANT: Contradicted concepts (negative grounding) are VALUABLE - they show problems/outdated approaches

3. **find_connection_by_search** - Discover HOW concepts connect.
   - Trace problem→solution chains
   - See grounding + evidence at each step in the path
   - Reveals narrative flow through ideas

4. **find_related_concepts** - Explore neighborhoods.
   - Find what's nearby in the concept graph
   - Discover clusters and themes
   - Use depth=1-2 for neighbors, 3-4 for broader exploration

## Grounding Strength (-1.0 to 1.0):
- **Positive (>0.7)**: Well-supported, reliable concept
- **Moderate (0.3-0.7)**: Mixed evidence, use with caution
- **Negative (<0)**: Contradicted or presented as a problem
- **Contradicted (-1.0)**: Often the most interesting - shows pain points!

## Pro Tips:
- Don't just search - explore connections and evidence
- Contradicted concepts reveal problems that need solutions
- Use retrieval hints in responses to dig deeper
- Follow relationship chains (SUPPORTS, CONTRADICTS, ENABLES)`,
          },
        },
      ],
    };
  }

  throw new Error(`Unknown prompt: ${name}`);
});

/**
 * Tool Call Handler
 *
 * Routes tool calls to the appropriate KnowledgeGraphClient method
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // Ensure args is defined (MCP spec requires it but TypeScript doesn't guarantee it)
  const toolArgs = args || {};

  try {
    switch (name) {
      // ========== Search & Query Tools ==========
      case 'search_concepts': {
        const query = toolArgs.query as string;
        const limit = toolArgs.limit as number || 10;
        const min_similarity = toolArgs.min_similarity as number || 0.7;
        const offset = toolArgs.offset as number || 0;

        const result = await client.searchConcepts({
          query,
          limit,
          min_similarity,
          offset,
          include_grounding: true,  // Automatic grounding for AI agents
          include_evidence: true,   // Include sample evidence quotes
        });

        const formattedText = formatSearchResults(result);

        return {
          content: [{ type: 'text', text: formattedText }],
        };
      }

      case 'get_concept_details': {
        const includeGrounding = toolArgs.include_grounding !== false; // Default: true (ADR-044)
        const result = await client.getConceptDetails(
          toolArgs.concept_id as string,
          includeGrounding
        );

        const formattedText = formatConceptDetails(result);

        return {
          content: [{ type: 'text', text: formattedText }],
        };
      }

      case 'find_related_concepts': {
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

      case 'find_connection': {
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
      }

      case 'find_connection_by_search': {
        const result = await client.findConnectionBySearch({
          from_query: toolArgs.from_query as string,
          to_query: toolArgs.to_query as string,
          max_hops: toolArgs.max_hops as number || 5,
          threshold: toolArgs.threshold as number || 0.5,
          include_grounding: true,  // Automatic grounding for AI agents
          include_evidence: true,   // Include sample evidence quotes
        });

        const formattedText = formatConnectionPaths(result);

        return {
          content: [{ type: 'text', text: formattedText }],
        };
      }

      // ========== Database Tools ==========
      case 'get_database_stats': {
        const result = await client.getDatabaseStats();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_database_info': {
        const result = await client.getDatabaseInfo();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_database_health': {
        const result = await client.getDatabaseHealth();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      // ========== Ontology Tools ==========
      case 'list_ontologies': {
        const result = await client.listOntologies();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_ontology_info': {
        const result = await client.getOntologyInfo(toolArgs.ontology_name as string);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_ontology_files': {
        const result = await client.getOntologyFiles(toolArgs.ontology_name as string);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'delete_ontology': {
        const result = await client.deleteOntology(
          toolArgs.ontology_name as string,
          toolArgs.force as boolean || false
        );
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      // ========== Job Tools ==========
      case 'get_job_status': {
        const result = await client.getJobStatus(toolArgs.job_id as string);
        const formattedText = formatJobStatus(result);
        return {
          content: [{ type: 'text', text: formattedText }],
        };
      }

      case 'list_jobs': {
        const result = await client.listJobs(
          toolArgs.status as string | undefined,
          undefined, // client_id - use default from environment
          toolArgs.limit as number || 50
        );
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'approve_job': {
        const result = await client.approveJob(toolArgs.job_id as string);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'cancel_job': {
        const result = await client.cancelJob(toolArgs.job_id as string);
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      // ========== Ingestion Tools ==========
      case 'ingest_text': {
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
        });
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      // ========== System Tools ==========
      case 'get_api_health': {
        const result = await client.health();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_system_status': {
        const result = await client.getSystemStatus();
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    // Return error details in a structured format
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
