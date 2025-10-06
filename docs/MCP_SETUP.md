# MCP Server Setup Guide

The Knowledge Graph MCP (Model Context Protocol) server enables Claude to query and explore the graph database directly during conversations.

## Prerequisites

- Node.js 18+ installed
- Neo4j database running (see `docs/QUICKSTART.md`)
- MCP server built: `cd mcp-server && npm run build`
- Environment variables configured in `.env`

## Setup for Claude Code (CLI)

Claude Code uses the `claude` CLI for MCP server management.

### 1. Check Available Commands

```bash
claude mcp --help
claude mcp list
```

### 2. Add the Knowledge Graph MCP Server

```bash
# From project root
claude mcp add knowledge-graph

# When prompted, provide:
# - Server name: knowledge-graph
# - Command: node
# - Args: /absolute/path/to/knowledge-graph-system/mcp-server/build/index.js
# - Environment variables: (see below)
```

**Environment variables to configure:**

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
OPENAI_API_KEY=sk-...
```

### 3. Verify Installation

```bash
# List configured MCP servers
claude mcp list

# Should show:
# knowledge-graph: /path/to/mcp-server/build/index.js
```

### 4. Test Connection

Start a Claude Code conversation and try:

```
List all ontologies in the database
```

Claude should use the `list_ontologies` tool to query your graph.

## Setup for Claude Desktop (macOS/Windows)

Claude Desktop requires manual configuration file editing.

### 1. Locate Configuration File

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### 2. Edit Configuration

Open the file and add the MCP server configuration:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": [
        "/absolute/path/to/knowledge-graph-system/mcp-server/build/index.js"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

**Important:**
- Use **absolute paths** - relative paths don't work
- Replace `/absolute/path/to/` with your actual project path
- Use your actual OpenAI API key and Neo4j credentials

### 3. Restart Claude Desktop

Close Claude Desktop completely and reopen. The MCP server will initialize on startup.

### 4. Verify Connection

In Claude Desktop, type:

```
What ontologies are available in the knowledge graph?
```

You should see Claude query the database and list your ontologies.

## Available MCP Tools

Once configured, Claude can use these tools:

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `search_concepts` | Semantic search for concepts (supports pagination via offset parameter) | "Search for concepts about governance" |
| `get_concept_details` | Detailed info about a concept | "Get details for concept ID xyz" |
| `find_related_concepts` | Graph traversal from a concept | "Find concepts related to VUCA" |
| `find_shortest_path` | Find shortest path(s) between two concepts | "Find path from concept X to concept Y" |
| `list_ontologies` | List all ontologies | "What ontologies exist?" |
| `get_ontology_info` | Stats for an ontology | "Show stats for Governed Agility" |
| `get_database_stats` | Overall database statistics | "What's in the database?" |

## Troubleshooting

### MCP Server Not Connecting

**Check server build:**
```bash
cd mcp-server
npm run build
ls -la build/index.js  # Should exist
```

**Check Neo4j is running:**
```bash
docker ps | grep neo4j
# Should show knowledge-graph-neo4j container
```

**Test Neo4j connection:**
```bash
source venv/bin/activate
python cli.py database health
```

### Environment Variable Issues

**Claude Code:** Environment variables are passed through the CLI configuration.

**Claude Desktop:** Must be in `claude_desktop_config.json` - `.env` file is NOT read by MCP server when launched from Claude Desktop.

### Permission Errors

**Ensure MCP server is executable:**
```bash
chmod +x mcp-server/build/index.js
```

**Check Node.js version:**
```bash
node --version  # Should be 18+
```

### API Key Errors

**MCP server requires OpenAI API key for embeddings:**
- Vector search uses `text-embedding-3-small` model
- Ensure `OPENAI_API_KEY` is set in MCP server environment

### Claude Can't See Tools

**For Claude Code:**
```bash
# Remove and re-add server
claude mcp remove knowledge-graph
claude mcp add knowledge-graph
```

**For Claude Desktop:**
- Verify JSON syntax in config file (use `jq` or JSON validator)
- Check absolute paths are correct
- Completely quit and restart Claude Desktop (not just close window)

### Viewing MCP Server Logs

**Claude Desktop logs location:**

**macOS:**
```bash
~/Library/Logs/Claude/mcp*.log
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Windows:**
```
%APPDATA%\Claude\logs\mcp*.log
```

**Claude Code logs:**
MCP server stderr is captured in Claude Code session logs.

## Development Tips

### Rebuilding After Code Changes

```bash
cd mcp-server
npm run build

# For Claude Code: Restart conversation
# For Claude Desktop: Restart application
```

### Testing Without Claude

Test MCP server queries directly:

```bash
source venv/bin/activate
python cli.py ontology list
python cli.py database stats
```

These CLI commands mirror MCP server functionality for debugging.

### Adding New Tools

1. Add query function to `mcp-server/src/neo4j.ts`
2. Export function from neo4j.ts
3. Import in `mcp-server/src/index.ts`
4. Add tool definition to `ListToolsRequestSchema` handler
5. Add case handler to `CallToolRequestSchema` handler
6. Rebuild: `npm run build`
7. Restart Claude

## Configuration Examples

### Multiple Environments

**Development (local):**
```json
{
  "mcpServers": {
    "knowledge-graph-dev": {
      "command": "node",
      "args": ["/path/to/dev/mcp-server/build/index.js"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

**Production (remote):**
```json
{
  "mcpServers": {
    "knowledge-graph-prod": {
      "command": "node",
      "args": ["/path/to/prod/mcp-server/build/index.js"],
      "env": {
        "NEO4J_URI": "bolt://production-host:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "secure-password",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Using .env File (Development Only)

**For local development with Node.js directly:**

```bash
# Start MCP server with .env loaded
cd mcp-server
node --require dotenv/config build/index.js
```

**Note:** This only works when running MCP server manually, not through Claude Code/Desktop.

## Security Considerations

### API Key Protection

- **Never commit** `claude_desktop_config.json` with real API keys
- Use environment-specific keys (dev vs. prod)
- Rotate keys periodically

### Neo4j Authentication

- Use strong passwords in production
- Consider Neo4j Auth plugins for enterprise
- Restrict network access to Neo4j port (7687)

### MCP Server Permissions

MCP server has **read-only** access to the graph:
- Cannot ingest documents
- Cannot modify concepts
- Cannot delete ontologies
- Can only query and traverse

For write operations, use the CLI or ingestion scripts.

## Next Steps

After setup:
1. Try semantic search: "Find concepts about risk management"
2. Explore relationships: "Show me concepts related to [concept_id]"
3. Compare ontologies: "What are the differences between ontology A and B?"
4. Find concept connections: "Find the shortest path from concept X to concept Y"
5. Paginate results: "Search for governance concepts, show results 10-20" (uses offset parameter)

**Example traversal query:**
```
Find the shortest path between the concept about "Sensible Transparency"
and the concept about "Signal-Based Decision Making"
```

**Example pagination query:**
```
Search for concepts related to "leadership", show me the next 10 results
```

For more examples, see `docs/EXAMPLES.md`.
