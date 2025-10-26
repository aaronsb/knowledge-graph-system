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
} from '@modelcontextprotocol/sdk/types.js';
import { createClientFromEnv } from './api/client.js';

// Create server instance
const server = new Server(
  {
    name: 'knowledge-graph-server',
    version: '0.1.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Get API client instance
const client = createClientFromEnv();

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
        description: 'Search for concepts using semantic similarity with vector embeddings. Uses 2-3 word descriptive phrases for best results. Returns concepts ranked by similarity score with smart threshold hints. Supports pagination with offset parameter.',
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
        description: 'Get detailed information about a specific concept including evidence instances (quoted text from documents), source references, and semantic relationships to other concepts. Includes grounding_strength (ADR-044) by default - a probabilistic truth score (0.0-1.0) measuring support vs contradiction based on incoming relationship semantics. Higher grounding = more reliable concept.',
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
        description: 'Find concepts related through graph traversal using breadth-first search. Explores outgoing relationships level by level and groups results by distance from starting concept.',
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
        description: 'Find shortest paths between concepts using semantic phrase matching. Matches query phrases to concepts via vector embeddings, then finds paths. Use specific 2-3 word phrases (e.g., "licensing issues" not "licensing").',
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
        description: 'Ingest raw text content into the knowledge graph. Creates a job with cost estimation. Use auto_approve=true to skip approval or approve manually with approve_job.',
        inputSchema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: 'Text content to ingest',
            },
            ontology: {
              type: 'string',
              description: 'Ontology/collection name to organize concepts',
            },
            filename: {
              type: 'string',
              description: 'Optional filename for source tracking (default: "text_input")',
            },
            auto_approve: {
              type: 'boolean',
              description: 'Auto-approve job and skip manual review (default: false)',
              default: false,
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
        });

        // Format response to match old server style with metadata
        const formattedResult = {
          query,
          threshold: min_similarity,
          limit,
          offset,
          resultsCount: result.count || 0,
          concepts: result.results || [],
          belowThreshold: result.below_threshold_count || 0,
          suggestedThreshold: result.suggested_threshold,
        };

        return {
          content: [{ type: 'text', text: JSON.stringify(formattedResult, null, 2) }],
        };
      }

      case 'get_concept_details': {
        const includeGrounding = toolArgs.include_grounding !== false; // Default: true (ADR-044)
        const result = await client.getConceptDetails(
          toolArgs.concept_id as string,
          includeGrounding
        );

        // Add explanatory note about grounding if present (educate AI agents)
        let responseText = JSON.stringify(result, null, 2);
        if (result.grounding_strength !== undefined && result.grounding_strength !== null) {
          const groundingNote = `\n\n--- Grounding Strength (ADR-044) ---\nScore: ${result.grounding_strength.toFixed(3)} (${(result.grounding_strength * 100).toFixed(0)}%)\nInterpretation: ${
            result.grounding_strength >= 0.7 ? 'Strong - Well-supported by evidence' :
            result.grounding_strength >= 0.3 ? 'Moderate - Mixed evidence, use with caution' :
            result.grounding_strength >= 0 ? 'Weak - More contradictions than support' :
            'Contradicted - Evidence suggests concept is incorrect or outdated'
          }\nMeaning: Grounding measures probabilistic truth convergence based on SUPPORTS vs CONTRADICTS relationships.\nHigher values (>0.7) indicate reliable concepts. Lower values (<0.3) suggest historical/incorrect information.\n`;
          responseText = JSON.stringify(result, null, 2) + groundingNote;
        }

        return {
          content: [{ type: 'text', text: responseText }],
        };
      }

      case 'find_related_concepts': {
        const result = await client.findRelatedConcepts({
          concept_id: toolArgs.concept_id as string,
          max_depth: toolArgs.max_depth as number || 2,
          relationship_types: toolArgs.relationship_types as string[] | undefined,
        });
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
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
        });

        // Segment long paths for readability
        if (result.paths && result.paths.length > 0) {
          result.paths = result.paths.map(segmentPath);
        }

        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
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
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
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
          auto_approve: toolArgs.auto_approve as boolean || false,
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
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is used for MCP protocol)
  console.error('Knowledge Graph MCP Server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
