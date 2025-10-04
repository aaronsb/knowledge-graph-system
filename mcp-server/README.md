# Knowledge Graph MCP Server

MCP (Model Context Protocol) server for querying Neo4j knowledge graphs from Claude Desktop.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j and OpenAI credentials
   ```

3. **Build the server:**
   ```bash
   npm run build
   ```

4. **Configure Claude Desktop:**

   Add to your Claude Desktop MCP settings file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

   ```json
   {
     "mcpServers": {
       "knowledge-graph": {
         "command": "node",
         "args": ["/absolute/path/to/knowledge-graph-system/mcp-server/build/index.js"],
         "env": {
           "NEO4J_URI": "bolt://localhost:7687",
           "NEO4J_USERNAME": "neo4j",
           "NEO4J_PASSWORD": "your_password",
           "OPENAI_API_KEY": "your_openai_key"
         }
       }
     }
   }
   ```

## Available Tools

### 1. search_concepts
Search for concepts using natural language queries.

**Example usage in Claude Desktop:**
```
Search the knowledge graph for "machine learning algorithms"
```

**Parameters:**
- `query` (required): Natural language search query
- `threshold` (optional): Minimum similarity threshold (0-1, default: 0.7)
- `limit` (optional): Maximum results (1-100, default: 10)

**Returns:**
```json
{
  "query": "machine learning algorithms",
  "resultsCount": 5,
  "concepts": [
    {
      "id": "concept-123",
      "name": "Neural Networks",
      "description": "A type of machine learning model...",
      "type": "algorithm",
      "similarity": 0.92
    }
  ]
}
```

### 2. get_concept_details
Get detailed information about a specific concept.

**Example usage in Claude Desktop:**
```
Get details about concept "concept-123"
```

**Parameters:**
- `concept_id` (required): The unique identifier of the concept

**Returns:**
```json
{
  "concept": {
    "id": "concept-123",
    "name": "Neural Networks",
    "description": "A type of machine learning model...",
    "type": "algorithm",
    "metadata": {}
  },
  "instances": [
    {
      "id": "instance-456",
      "content": "Example of neural network usage...",
      "source": "research-paper-2024",
      "timestamp": "2024-01-15T10:30:00Z",
      "metadata": {}
    }
  ],
  "relationships": [
    {
      "type": "RELATES_TO",
      "relatedConcept": {
        "id": "concept-789",
        "name": "Deep Learning",
        "type": "field"
      },
      "strength": 0.95,
      "metadata": {}
    }
  ]
}
```

### 3. find_related_concepts
Discover concepts related to a given concept through graph traversal.

**Example usage in Claude Desktop:**
```
Find concepts related to "concept-123" within 2 hops
```

**Parameters:**
- `concept_id` (required): The starting concept ID
- `relationship_types` (optional): Array of relationship types to filter (e.g., ["RELATES_TO", "CAUSES"])
- `max_depth` (optional): Maximum traversal depth (1-5, default: 2)

**Returns:**
```json
{
  "conceptId": "concept-123",
  "maxDepth": 2,
  "relationshipTypes": "all",
  "resultsCount": 8,
  "relatedConcepts": [
    {
      "id": "concept-789",
      "name": "Deep Learning",
      "description": "A subset of machine learning...",
      "type": "field",
      "distance": 1,
      "relationshipPath": ["RELATES_TO"],
      "strengthPath": [0.95]
    }
  ]
}
```

## Development

**Watch mode for development:**
```bash
npm run watch
```

**Rebuild after changes:**
```bash
npm run build
```

## Prerequisites

- Neo4j database with:
  - Vector index named `concept_embeddings` on Concept nodes
  - Schema following the knowledge graph architecture (Concept, Instance nodes)
- OpenAI API key for generating embeddings
- Node.js 20+
