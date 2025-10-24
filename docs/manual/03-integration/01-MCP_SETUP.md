# MCP Server Setup Guide

The Knowledge Graph MCP (Model Context Protocol) server enables Claude to query and explore the graph database directly during conversations.

## Prerequisites

- Node.js 18+ installed
- PostgreSQL + Apache AGE database running (see `docs/guides/QUICKSTART.md`)
- FastAPI server running (`./scripts/start-api.sh`)
- kg CLI installed globally (`cd client && ./install.sh`)

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
# - Command: kg-mcp-server
# - No additional arguments or environment variables needed
```

**Note:** The MCP server connects to the FastAPI server at `http://localhost:8000`. Ensure the API server is running before using the MCP server.

### 3. Verify Installation

```bash
# List configured MCP servers
claude mcp list

# Should show:
# knowledge-graph: kg-mcp-server  - ✓ Connected
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
      "command": "kg-mcp-server"
    }
  }
}
```

**Important:**
- The `kg-mcp-server` command must be globally installed: `cd client && ./install.sh`
- The MCP server connects to the FastAPI server at `http://localhost:8000`
- Ensure the API server is running before using the MCP server

### 3. Restart Claude Desktop

Close Claude Desktop completely and reopen. The MCP server will initialize on startup.

### 4. Verify Connection

In Claude Desktop, type:

```
What ontologies are available in the knowledge graph?
```

You should see Claude query the database and list your ontologies.

## Available MCP Tools

Once configured, Claude can use these 18 tools:

### Query Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `search_concepts` | Semantic search for concepts (supports pagination via offset parameter) | "Search for concepts about governance" |
| `get_concept_details` | Detailed info about a concept with full text grounding | "Get details for concept ID xyz" |
| `find_related_concepts` | Graph traversal from a concept | "Find concepts related to VUCA" |
| `find_connection` | Find shortest path(s) between two concepts (auto-segments paths > 5 hops) | "Find path from concept X to concept Y" |
| `find_connection_by_search` | Find path between concepts using natural language queries | "Find path from 'Sensible Transparency' to 'Role-Based Intelligence'" |

### Database Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `get_database_stats` | Overall database statistics | "What's in the database?" |
| `get_database_info` | Database connection information | "Show database info" |
| `get_database_health` | Database health check | "Is the database healthy?" |

### Ontology Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `list_ontologies` | List all ontologies | "What ontologies exist?" |
| `get_ontology_info` | Stats for an ontology | "Show stats for Governed Agility" |
| `get_ontology_files` | List files in an ontology | "What files are in this ontology?" |
| `delete_ontology` | Delete an ontology (requires force=true) | "Delete the Test ontology" |

### Job Management Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `get_job_status` | Check job status and progress | "Check status of job xyz" |
| `list_jobs` | List recent jobs with filtering | "Show all running jobs" |
| `approve_job` | Approve a job for processing | "Approve job xyz" |
| `cancel_job` | Cancel a pending/running job | "Cancel job xyz" |

### Ingestion Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `ingest_text` | Ingest text content into knowledge graph | "Ingest this text into 'My Ontology'" |

### System Tools
| Tool | Description | Example Usage |
|------|-------------|---------------|
| `get_api_health` | API server health check | "Is the API healthy?" |
| `get_system_status` | Comprehensive system status | "Show system status" |

## Troubleshooting

### MCP Server Not Connecting

**Check kg CLI is installed:**
```bash
which kg-mcp-server
# Should show: /usr/local/bin/kg-mcp-server (or similar)
```

**Reinstall if needed:**
```bash
cd client
./uninstall.sh
./install.sh
```

**Check API server is running:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

**Start API server if needed:**
```bash
./scripts/start-api.sh
```

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
# Should show knowledge-graph-postgres container
```

### Environment Variable Issues

**No environment variables needed for MCP server!**

The MCP server connects to the FastAPI server at `http://localhost:8000`, which handles all database connections and API keys.

**If you need to change the API URL:**
- Set `KG_API_URL` environment variable in MCP server config
- Default: `http://localhost:8000`

### Permission Errors

**Check Node.js version:**
```bash
node --version  # Should be 18+
```

**Ensure kg-mcp-server is executable:**
```bash
ls -la $(which kg-mcp-server)
```

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
cd client
npm run build
./install.sh  # Reinstall globally

# For Claude Code: Restart conversation
# For Claude Desktop: Restart application
```

### Testing Without Claude

Test MCP server functionality using kg CLI:

```bash
kg search query "linear thinking"
kg ontology list
kg database stats
```

The kg CLI uses the same REST API as the MCP server.

### Adding New Tools

1. Add API endpoint to `src/api/routes/` (if needed)
2. Add client method to `client/src/api/client.ts`
3. Add tool definition to `client/src/mcp-server.ts` (ListToolsRequestSchema handler)
4. Add case handler to CallToolRequestSchema handler
5. Rebuild: `cd client && npm run build && ./install.sh`
6. Restart Claude

## Configuration Examples

### Multiple Environments

**Development (local):**
```json
{
  "mcpServers": {
    "knowledge-graph-dev": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "http://localhost:8000"
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
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "https://api.production-host.com"
      }
    }
  }
}
```

**Note:** The KG_API_URL environment variable is optional. If not set, it defaults to `http://localhost:8000`.

## Security Considerations

### API Key Protection

- **Never commit** `claude_desktop_config.json`
- API keys are managed by the FastAPI server (in `.env` file)
- The MCP server only communicates with the API server

### API Server Authentication

- The FastAPI server requires authentication (see `docs/guides/AUTHENTICATION.md`)
- MCP server connects to API server via `http://localhost:8000`
- For production, use HTTPS and proper authentication

### PostgreSQL Security

- Use strong passwords in production
- Restrict network access to PostgreSQL port (5432)
- Configure PostgreSQL authentication (pg_hba.conf)

### MCP Server Capabilities

The MCP server has **full access** to the API:
- Can query and traverse the graph
- Can ingest text content
- Can manage jobs (approve, cancel)
- Can delete ontologies (with force=true)

**Use with caution** - the MCP server has write access!

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
