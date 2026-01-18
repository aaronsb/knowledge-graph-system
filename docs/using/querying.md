# Querying the Knowledge Graph

Programmatic access via CLI, REST API, and MCP.

## Overview

Three ways to query:

| Method | Best For | Authentication |
|--------|----------|----------------|
| **CLI** | Interactive use, scripts | OAuth (browser login) |
| **REST API** | Custom applications | OAuth tokens |
| **MCP** | AI assistants (Claude, etc.) | Configured per-assistant |

## CLI Queries

The `kg` command-line interface provides full access.

### Authentication

```bash
# Login (opens browser for OAuth)
kg login

# Check configuration and auth status
kg config show

# Logout
kg logout
```

### Search

```bash
# Basic search
kg search "your query"

# With options
kg search --limit 20 --ontology "research" "machine learning"

# Output formats
kg search --format json "query"
kg search --format table "query"
```

### Concept Operations

```bash
# Get full details
kg search details <concept-id>

# Find related concepts
kg search related <concept-id>
kg search related <concept-id> --depth 2 --type SUPPORTS

# Find paths between concepts
kg search connect "concept A" "concept B"
kg search connect <id1> <id2> --max-hops 4
```

### Ontology Operations

```bash
# List ontologies
kg ontology list

# Get ontology info
kg ontology info <name>

# List files in ontology
kg ontology files <name>
```

### Job Management

```bash
# List jobs
kg job list
kg job list --status pending

# Check job status
kg job status <job-id>

# Approve pending job
kg job approve <job-id>

# Cancel job
kg job cancel <job-id>
```

## REST API

Direct HTTP access for custom applications.

### Authentication

Get an OAuth token first:

```bash
# Using the CLI token
TOKEN=$(kg auth token)

# Or via OAuth flow
curl -X POST "http://localhost:8000/auth/oauth/token" \
  -d "grant_type=authorization_code&code=..."
```

### Search Endpoint

```bash
curl "http://localhost:8000/concepts/search?query=climate+change&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "results": [
    {
      "concept_id": "abc123",
      "name": "Climate change increases extreme weather",
      "similarity": 0.89,
      "grounding_strength": 0.72,
      "source_count": 5
    }
  ]
}
```

### Concept Details

```bash
curl "http://localhost:8000/concepts/abc123" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "concept_id": "abc123",
  "name": "Climate change increases extreme weather",
  "type": "claim",
  "grounding_strength": 0.72,
  "evidence": [
    {
      "source_id": "src456",
      "text": "Studies show that climate change...",
      "document": "IPCC Report 2023"
    }
  ],
  "relationships": [
    {
      "type": "CAUSES",
      "target_id": "def789",
      "target_name": "Increased flooding"
    }
  ]
}
```

### Ingest Document

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "ontology=research" \
  -F "auto_approve=true"
```

### Full API Reference

See [API Reference](../reference/api/README.md) for complete endpoint documentation.

## MCP (Model Context Protocol)

For AI assistants like Claude Desktop.

### Setup

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["/path/to/knowledge-graph-system/mcp/dist/index.js"],
      "env": {
        "KG_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Available Tools

Once configured, Claude can use these tools:

#### search
Find concepts by semantic similarity.

```
Use search tool with query "climate effects on agriculture"
```

**Parameters:**
- `query` (required): Search text
- `limit`: Max results (default 10)
- `min_similarity`: Threshold 0-1 (default 0.7)
- `ontology`: Filter by ontology name

#### concept
Work with specific concepts.

**Actions:**
- `details`: Get full concept with evidence
- `related`: Find connected concepts
- `connect`: Find paths between concepts

```
Use concept tool with action "details" and concept_id "abc123"
```

```
Use concept tool with action "connect", from_query "inflation", to_query "unemployment"
```

#### ingest
Add documents to the knowledge graph.

```
Use ingest tool with action "text", text "...", ontology "notes"
```

#### ontology
Manage knowledge collections.

```
Use ontology tool with action "list"
```

#### source
Retrieve original source text.

```
Use source tool with source_id "src456"
```

### MCP for AI Reasoning

When an AI uses MCP, it can:

1. **Query for context**: Before answering, search for relevant concepts
2. **Check grounding**: Verify claims have evidence
3. **Find contradictions**: Identify where sources disagree
4. **Trace sources**: Link answers to original documents
5. **Build knowledge**: Ingest new information during conversation

**Example AI workflow:**
```
User: "What are the effects of sleep deprivation?"

AI thinks: Let me check the knowledge graph...
[Uses search tool: "sleep deprivation effects"]

AI: Based on the knowledge graph, sleep deprivation has several documented effects:
- Memory impairment (grounding: 0.85, 12 sources)
- Reduced cognitive function (grounding: 0.78, 8 sources)
- Increased accident risk (grounding: 0.65, 5 sources)

Sources include: Smith et al. 2023, Sleep Research Journal...
```

### Full MCP Reference

See [MCP Reference](../reference/mcp/README.md) for complete tool documentation.

## Query Patterns

### Get Grounded Answers

1. Search for the topic
2. Check grounding scores
3. For high-grounding concepts, trust the answer
4. For low-grounding, caveat with uncertainty

### Explore a Topic

1. Search for central concept
2. Get related concepts (depth 2)
3. Look for clusters of connected ideas
4. Follow interesting paths

### Verify a Claim

1. Search for the specific claim
2. Check if concept exists
3. If yes, check grounding and sources
4. If no, the claim isn't in your knowledge base

### Find Disagreements

1. Search for contested topic
2. Look for concepts with grounding near 0
3. Get details to see conflicting sources
4. Use `connect` to find the conflict structure

## Tips

### Use Semantic Queries
"What causes inflation" works better than "inflation causes" because the system matches by meaning.

### Check Multiple Phrasings
If initial search misses, try synonyms or related terms.

### Follow the Evidence
Always check source text for important claims. Grounding tells you confidence, sources tell you why.

### Combine Methods
Use CLI for exploration, API for automation, MCP for AI-assisted work.

## Next Steps

- [Understanding Grounding](understanding-grounding.md) - Interpret confidence scores
- [API Reference](../reference/api/README.md) - Complete endpoint docs
- [MCP Reference](../reference/mcp/README.md) - All MCP tools
