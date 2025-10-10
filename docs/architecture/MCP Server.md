## 8. MCP Server Specification

### 8.1 MCP Server Architecture

The MCP (Model Context Protocol) server provides tools for Claude Desktop to interact with the knowledge graph.

**Location:** `mcp-knowledge-graph-server/`

**Key files:**
- `src/index.ts` - Main server implementation
- `src/database.ts` - Database queries
- `src/tools/` - Individual tool implementations
- `package.json` - Dependencies
- `tsconfig.json` - TypeScript configuration

### 8.2 Tool Definitions

```typescript
// src/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  {
    name: "knowledge-graph-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "search_concepts",
      description: "Search for concepts using semantic similarity or keywords. Returns concepts with their sources and evidence count.",
      inputSchema: {
        type: "object",
        properties: {
          query: { 
            type: "string", 
            description: "Search query - can be keywords or natural language" 
          },
          limit: { 
            type: "number", 
            description: "Maximum number of results to return", 
            default: 10 
          },
          min_similarity: { 
            type: "number", 
            description: "Minimum similarity score (0.0-1.0) for vector search", 
            default: 0.7 
          }
        },
        required: ["query"]
      }
    },
    {
      name: "get_concept_details",
      description: "Get comprehensive details about a specific concept including all instances (quotes), sources, and related concepts.",
      inputSchema: {
        type: "object",
        properties: {
          concept_id: { 
            type: "string",
            description: "The concept_id to retrieve (e.g., 'linear-scanning-system')"
          }
        },
        required: ["concept_id"]
      }
    },
    {
      name: "find_related_concepts",
      description: "Find concepts related to a given concept through various relationship types. Can traverse multiple hops.",
      inputSchema: {
        type: "object",
        properties: {
          concept_id: { 
            type: "string",
            description: "Starting concept_id"
          },
          relationship_types: { 
            type: "array", 
            items: { type: "string" },
            description: "Filter by relationship types: implies, contradicts, supports, part_of, requires. Leave empty for all types."
          },
          max_depth: { 
            type: "number", 
            default: 2,
            description: "Maximum relationship hops to traverse"
          }
        },
        required: ["concept_id"]
      }
    },
    {
      name: "search_by_document",
      description: "Find all concepts that appear in a specific document or paragraph.",
      inputSchema: {
        type: "object",
        properties: {
          document_name: { 
            type: "string",
            description: "Document name to search (e.g., 'Watts Doc 1')"
          },
          paragraph: { 
            type: "number", 
            description: "Optional: specific paragraph number to filter by" 
          }
        },
        required: ["document_name"]
      }
    },
    {
      name: "find_connections",
      description: "Find the shortest path(s) between two concepts in the knowledge graph.",
      inputSchema: {
        type: "object",
        properties: {
          from_concept_id: { 
            type: "string",
            description: "Starting concept"
          },
          to_concept_id: { 
            type: "string",
            description: "Target concept"
          },
          max_hops: { 
            type: "number", 
            default: 5,
            description: "Maximum number of hops to search"
          }
        },
        required: ["from_concept_id", "to_concept_id"]
      }
    },
    {
      name: "get_visualization_url",
      description: "Generate a URL to visualize a subgraph in 3D. Opens in web browser for visual exploration.",
      inputSchema: {
        type: "object",
        properties: {
          concept_ids: { 
            type: "array", 
            items: { type: "string" },
            description: "Concepts to include in visualization. Can be empty to use depth-based expansion."
          },
          depth: { 
            type: "number", 
            default: 1, 
            description: "Include neighbors up to this depth from specified concepts" 
          },
          center_concept: {
            type: "string",
            description: "Optional: concept to center the visualization on"
          }
        }
      }
    },
    {
      name: "list_documents",
      description: "List all documents in the knowledge graph with concept counts.",
      inputSchema: {
        type: "object",
        properties: {}
      }
    }
  ]
}));

// Tool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "search_concepts":
      return await searchConcepts(
        args.query, 
        args.limit ?? 10, 
        args.min_similarity ?? 0.7
      );
    
    case "get_concept_details":
      return await getConceptDetails(args.concept_id);
    
    case "find_related_concepts":
      return await findRelatedConcepts(
        args.concept_id, 
        args.relationship_types ?? [],
        args.max_depth ?? 2
      );
    
    case "search_by_document":
      return await searchByDocument(
        args.document_name, 
        args.paragraph
      );
    
    case "find_connections":
      return await findConnections(
        args.from_concept_id,
        args.to_concept_id,
        args.max_hops ?? 5
      );
    
    case "get_visualization_url":
      return await getVisualizationUrl(
        args.concept_ids ?? [],
        args.depth ?? 1,
        args.center_concept
      );
    
    case "list_documents":
      return await listDocuments();
    
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Knowledge Graph MCP server running on stdio");
}

main().catch(console.error);
```

### 8.3 Tool Implementation Examples

```typescript
// src/database.ts
import { Client } from 'pg';
import OpenAI from 'openai';

const db = new Client({
  connectionString: process.env.DATABASE_URL
});

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

await db.connect();

// Generate embedding for search
async function generateEmbedding(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text,
  });
  return response.data[0].embedding;
}

// Search concepts by semantic similarity
export async function searchConcepts(
  query: string, 
  limit: number, 
  minSimilarity: number
) {
  const embedding = await generateEmbedding(query);
  
  const result = await db.query(`
    SELECT 
      c.concept_id,
      c.label,
      1 - (c.embedding <=> $1::vector) as similarity,
      array_agg(DISTINCT s.document) as documents,
      count(DISTINCT i.instance_id) as evidence_count
    FROM concepts c
    LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
    LEFT JOIN sources s ON cs.source_id = s.source_id
    LEFT JOIN instances i ON c.concept_id = i.concept_id
    WHERE 1 - (c.embedding <=> $1::vector) > $2
    GROUP BY c.concept_id, c.label, c.embedding
    ORDER BY similarity DESC
    LIMIT $3
  `, [JSON.stringify(embedding), minSimilarity, limit]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        query: query,
        results: result.rows
      }, null, 2)
    }]
  };
}

// Get concept details with instances
export async function getConceptDetails(conceptId: string) {
  const conceptResult = await db.query(`
    SELECT c.*, array_agg(DISTINCT s.document) as documents
    FROM concepts c
    LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
    LEFT JOIN sources s ON cs.source_id = s.source_id
    WHERE c.concept_id = $1
    GROUP BY c.concept_id
  `, [conceptId]);

  if (conceptResult.rows.length === 0) {
    throw new Error(`Concept not found: ${conceptId}`);
  }

  const instancesResult = await db.query(`
    SELECT i.quote, s.document, s.paragraph, s.source_id
    FROM instances i
    JOIN sources s ON i.source_id = s.source_id
    WHERE i.concept_id = $1
    ORDER BY s.document, s.paragraph
  `, [conceptId]);

  const relationshipsResult = await db.query(`
    SELECT 
      cr.to_concept_id,
      c.label as to_label,
      cr.relationship_type,
      cr.confidence
    FROM concept_relationships cr
    JOIN concepts c ON cr.to_concept_id = c.concept_id
    WHERE cr.from_concept_id = $1
  `, [conceptId]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        concept: conceptResult.rows[0],
        instances: instancesResult.rows,
        relationships: relationshipsResult.rows
      }, null, 2)
    }]
  };
}

// Find connections between concepts
export async function findConnections(
  fromId: string,
  toId: string,
  maxHops: number
) {
  // Use recursive CTE to find paths
  const result = await db.query(`
    WITH RECURSIVE paths AS (
      -- Base case: direct relationships
      SELECT 
        from_concept_id,
        to_concept_id,
        relationship_type,
        ARRAY[from_concept_id, to_concept_id] as path,
        1 as depth
      FROM concept_relationships
      WHERE from_concept_id = $1
      
      UNION ALL
      
      -- Recursive case: extend paths
      SELECT 
        p.from_concept_id,
        cr.to_concept_id,
        cr.relationship_type,
        p.path || cr.to_concept_id,
        p.depth + 1
      FROM paths p
      JOIN concept_relationships cr ON p.to_concept_id = cr.from_concept_id
      WHERE 
        NOT cr.to_concept_id = ANY(p.path)  -- Prevent cycles
        AND p.depth < $3
    )
    SELECT 
      path,
      depth,
      array_agg(relationship_type) as relationship_types
    FROM paths
    WHERE to_concept_id = $2
    GROUP BY path, depth
    ORDER BY depth
    LIMIT 5
  `, [fromId, toId, maxHops]);

  // Enrich with concept labels
  const enrichedPaths = [];
  for (const row of result.rows) {
    const labels = await db.query(`
      SELECT concept_id, label
      FROM concepts
      WHERE concept_id = ANY($1)
    `, [row.path]);
    
    const labelMap = Object.fromEntries(
      labels.rows.map(r => [r.concept_id, r.label])
    );
    
    enrichedPaths.push({
      path: row.path.map((id: string) => ({
        concept_id: id,
        label: labelMap[id]
      })),
      depth: row.depth,
      relationship_types: row.relationship_types
    });
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        from: fromId,
        to: toId,
        paths: enrichedPaths,
        paths_found: enrichedPaths.length
      }, null, 2)
    }]
  };
}

// Generate visualization URL
export async function getVisualizationUrl(
  conceptIds: string[],
  depth: number,
  centerConcept?: string
) {
  // Generate unique session ID
  const sessionId = Math.random().toString(36).substring(7);
  
  // Store visualization config in temporary table or cache
  await db.query(`
    INSERT INTO visualization_sessions (session_id, concept_ids, depth, center_concept, created_at)
    VALUES ($1, $2, $3, $4, NOW())
  `, [sessionId, conceptIds, depth, centerConcept]);
  
  const baseUrl = process.env.VISUALIZATION_URL || 'http://localhost:3000';
  const url = `${baseUrl}/viz/${sessionId}`;
  
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        url: url,
        message: "Open this URL in your browser to explore the graph in 3D",
        config: {
          concept_ids: conceptIds,
          depth: depth,
          center: centerConcept
        }
      }, null, 2)
    }]
  };
}
```

### 8.4 Claude Desktop Configuration

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": [
        "/absolute/path/to/mcp-knowledge-graph-server/build/index.js"
      ],
      "env": {
        "DATABASE_URL": "postgresql://user:password@localhost:5432/knowledge_graph",
        "OPENAI_API_KEY": "sk-...",
        "VISUALIZATION_URL": "http://localhost:3000"
      }
    }
  }
}
```

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)