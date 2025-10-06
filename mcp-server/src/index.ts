#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import OpenAI from 'openai';
import {
  initializeDriver,
  closeDriver,
  vectorSearch,
  getConceptDetails,
  findRelatedConcepts,
  listOntologies,
  getOntologyInfo,
  getDatabaseStats,
  findShortestPath,
} from './neo4j.js';

// Initialize OpenAI client for embeddings
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/**
 * Generate embedding for a text query
 */
async function generateEmbedding(text: string): Promise<number[]> {
  try {
    const response = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: text,
    });
    return response.data[0].embedding;
  } catch (error) {
    throw new Error(`Failed to generate embedding: ${error}`);
  }
}

/**
 * Create and configure the MCP server
 */
async function main() {
  // Initialize Neo4j connection
  initializeDriver();

  const server = new Server(
    {
      name: 'knowledge-graph-mcp-server',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  /**
   * List available tools
   */
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: 'search_concepts',
          description:
            'Search for concepts in the knowledge graph using natural language queries. Returns concepts ranked by semantic similarity.',
          inputSchema: {
            type: 'object',
            properties: {
              query: {
                type: 'string',
                description: 'Natural language search query',
              },
              threshold: {
                type: 'number',
                description: 'Minimum similarity threshold (0-1), default: 0.7',
                minimum: 0,
                maximum: 1,
              },
              limit: {
                type: 'number',
                description: 'Maximum number of results to return, default: 10',
                minimum: 1,
                maximum: 100,
              },
              offset: {
                type: 'number',
                description: 'Number of results to skip for pagination, default: 0',
                minimum: 0,
              },
            },
            required: ['query'],
          },
        },
        {
          name: 'get_concept_details',
          description:
            'Get detailed information about a specific concept, including all instances and relationships.',
          inputSchema: {
            type: 'object',
            properties: {
              concept_id: {
                type: 'string',
                description: 'The unique identifier of the concept',
              },
            },
            required: ['concept_id'],
          },
        },
        {
          name: 'find_related_concepts',
          description:
            'Find concepts related to a given concept through graph traversal. Discover connections and explore the knowledge graph.',
          inputSchema: {
            type: 'object',
            properties: {
              concept_id: {
                type: 'string',
                description: 'The unique identifier of the starting concept',
              },
              relationship_types: {
                type: 'array',
                items: {
                  type: 'string',
                },
                description:
                  'Optional array of relationship types to filter (e.g., ["RELATES_TO", "CAUSES"])',
              },
              max_depth: {
                type: 'number',
                description: 'Maximum traversal depth, default: 2',
                minimum: 1,
                maximum: 5,
              },
            },
            required: ['concept_id'],
          },
        },
        {
          name: 'list_ontologies',
          description:
            'List all ontologies in the database with their concept and source counts. Use this to discover what knowledge domains are available.',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'get_ontology_info',
          description:
            'Get detailed statistics and information about a specific ontology, including concept counts, relationships, and source files.',
          inputSchema: {
            type: 'object',
            properties: {
              ontology_name: {
                type: 'string',
                description: 'The name of the ontology to get information about',
              },
            },
            required: ['ontology_name'],
          },
        },
        {
          name: 'get_database_stats',
          description:
            'Get overall database statistics including total concepts, sources, instances, relationships, and ontology count.',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'find_shortest_path',
          description:
            'Find the shortest path(s) between two concepts in the knowledge graph. Returns up to 5 paths with nodes, relationships, and hop count.',
          inputSchema: {
            type: 'object',
            properties: {
              from_concept_id: {
                type: 'string',
                description: 'Starting concept ID',
              },
              to_concept_id: {
                type: 'string',
                description: 'Target concept ID',
              },
              max_hops: {
                type: 'number',
                description: 'Maximum path length, default: 5',
                minimum: 1,
                maximum: 10,
              },
            },
            required: ['from_concept_id', 'to_concept_id'],
          },
        },
      ],
    };
  });

  /**
   * Handle tool calls
   */
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      const { name, arguments: args } = request.params;

      switch (name) {
        case 'search_concepts': {
          const { query, threshold = 0.7, limit = 10, offset = 0 } = args as {
            query: string;
            threshold?: number;
            limit?: number;
            offset?: number;
          };

          // Generate embedding for the query
          const embedding = await generateEmbedding(query);

          // Perform vector search (ensure integers)
          const results = await vectorSearch(
            embedding,
            threshold,
            Math.floor(limit),
            Math.floor(offset)
          );

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(
                  {
                    query,
                    resultsCount: results.length,
                    offset,
                    concepts: results,
                  },
                  null,
                  2
                ),
              },
            ],
          };
        }

        case 'get_concept_details': {
          const { concept_id } = args as { concept_id: string };

          const details = await getConceptDetails(concept_id);

          if (!details) {
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(
                    {
                      error: `Concept with id "${concept_id}" not found`,
                    },
                    null,
                    2
                  ),
                },
              ],
              isError: true,
            };
          }

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(details, null, 2),
              },
            ],
          };
        }

        case 'find_related_concepts': {
          const { concept_id, relationship_types, max_depth = 2 } = args as {
            concept_id: string;
            relationship_types?: string[];
            max_depth?: number;
          };

          const relatedConcepts = await findRelatedConcepts(
            concept_id,
            relationship_types,
            max_depth
          );

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(
                  {
                    conceptId: concept_id,
                    maxDepth: max_depth,
                    relationshipTypes: relationship_types || 'all',
                    resultsCount: relatedConcepts.length,
                    relatedConcepts,
                  },
                  null,
                  2
                ),
              },
            ],
          };
        }

        case 'list_ontologies': {
          const ontologies = await listOntologies();

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(
                  {
                    count: ontologies.length,
                    ontologies,
                  },
                  null,
                  2
                ),
              },
            ],
          };
        }

        case 'get_ontology_info': {
          const { ontology_name } = args as { ontology_name: string };

          const info = await getOntologyInfo(ontology_name);

          if (!info) {
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(
                    {
                      error: `Ontology "${ontology_name}" not found`,
                    },
                    null,
                    2
                  ),
                },
              ],
              isError: true,
            };
          }

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(info, null, 2),
              },
            ],
          };
        }

        case 'get_database_stats': {
          const stats = await getDatabaseStats();

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(stats, null, 2),
              },
            ],
          };
        }

        case 'find_shortest_path': {
          const { from_concept_id, to_concept_id, max_hops = 5 } = args as {
            from_concept_id: string;
            to_concept_id: string;
            max_hops?: number;
          };

          const paths = await findShortestPath(
            from_concept_id,
            to_concept_id,
            Math.floor(max_hops)
          );

          if (paths.length === 0) {
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(
                    {
                      message: `No path found between "${from_concept_id}" and "${to_concept_id}" within ${max_hops} hops`,
                      from_concept_id,
                      to_concept_id,
                      max_hops,
                    },
                    null,
                    2
                  ),
                },
              ],
            };
          }

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(
                  {
                    from_concept_id,
                    to_concept_id,
                    pathsFound: paths.length,
                    paths,
                  },
                  null,
                  2
                ),
              },
            ],
          };
        }

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: errorMessage }, null, 2),
          },
        ],
        isError: true,
      };
    }
  });

  // Set up stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Handle cleanup on exit
  process.on('SIGINT', async () => {
    await closeDriver();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    await closeDriver();
    process.exit(0);
  });
}

// Start the server
main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
