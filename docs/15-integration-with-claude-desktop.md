# 15 - Integration with Claude Desktop

**Part:** II - Configuration
**Reading Time:** ~15 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)

---

This section explains how to connect your knowledge graph to Claude Desktop or Claude Code using the Model Context Protocol (MCP). Once configured, Claude can query your knowledge graph directly during conversations.

## What Is MCP Integration

The Model Context Protocol (MCP) is a standard that lets AI assistants access external tools and data sources. The knowledge graph MCP server exposes your graph to Claude, enabling:

**Direct graph queries during conversations:**
```
You: "What concepts are in my knowledge graph about authentication?"
Claude: [uses search_concepts tool]
       "I found 8 concepts related to authentication..."
```

**Path finding between concepts:**
```
You: "How does 'Microservices' connect to 'Resilience'?"
Claude: [uses find_connection tool]
       "I found a path: Microservices → Distributed Systems → Fault Tolerance → Resilience"
```

**Ontology management:**
```
You: "What ontologies do I have?"
Claude: [uses list_ontologies tool]
       "You have 3 ontologies: Research Papers (247 concepts), Architecture Docs (189 concepts), Meeting Notes (45 concepts)"
```

**Text ingestion:**
```
You: "Ingest this text into my Research Papers ontology: [paste content]"
Claude: [uses ingest_text tool]
       "Started ingestion job. Processing..."
```

Claude becomes a natural language interface to your knowledge graph.

## Available Capabilities

Once configured, Claude has access to 18 tools:

### Query Tools

- `search_concepts` - Semantic search with pagination
- `get_concept_details` - Full concept information with evidence
- `find_related_concepts` - Graph traversal from a concept
- `find_connection` - Shortest path between concepts by ID
- `find_connection_by_search` - Path finding with natural language queries

### Database Tools

- `get_database_stats` - Overall statistics
- `get_database_info` - Connection information
- `get_database_health` - Health check

### Ontology Tools

- `list_ontologies` - List all ontologies
- `get_ontology_info` - Detailed ontology statistics
- `get_ontology_files` - Source files in an ontology
- `delete_ontology` - Delete an ontology (requires force=true)

### Job Management Tools

- `get_job_status` - Check ingestion job status
- `list_jobs` - List recent jobs with filtering
- `approve_job` - Approve a job for processing
- `cancel_job` - Cancel a running job

### Ingestion Tools

- `ingest_text` - Ingest text content into the graph

### System Tools

- `get_api_health` - API server health check
- `get_system_status` - Comprehensive system status

## Prerequisites

Before setting up MCP:

**1. Database running:**
```bash
docker ps | grep postgres
# Should show knowledge-graph-postgres container
```

Start if needed:
```bash
docker-compose up -d
```

**2. API server running:**
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

Start if needed:
```bash
./scripts/start-api.sh
```

**3. kg CLI installed globally:**
```bash
which kg
# Should show: /usr/local/bin/kg
```

Install if needed:
```bash
cd client && ./install.sh && cd ..
```

**4. Node.js 18+ installed:**
```bash
node --version  # Should be 18.0.0 or higher
```

## Setup for Claude Code (CLI)

Claude Code uses the `claude` CLI for MCP server management.

### 1. Add MCP Server

```bash
claude mcp add knowledge-graph
```

**When prompted:**
- **Server name:** knowledge-graph
- **Command:** kg-mcp-server
- **Arguments:** (leave empty)
- **Environment variables:** (leave empty)

**What this does:**
- Registers the MCP server with Claude Code
- Configures it to use the `kg-mcp-server` command (installed globally with kg CLI)

### 2. Verify Installation

```bash
claude mcp list
```

**Expected output:**
```
knowledge-graph: kg-mcp-server  - ✓ Connected
```

If you see "✗ Not connected", check prerequisites (API server running, kg CLI installed).

### 3. Test in Conversation

Start a Claude Code conversation:

```
List all ontologies in the database
```

Claude should use the `list_ontologies` tool and show your ontologies.

### 4. Remove/Reinstall if Needed

```bash
# Remove server
claude mcp remove knowledge-graph

# Add again
claude mcp add knowledge-graph
```

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

If the file doesn't exist, create it.

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

**If you already have other MCP servers configured:**

```json
{
  "mcpServers": {
    "existing-server": {
      "command": "existing-command"
    },
    "knowledge-graph": {
      "command": "kg-mcp-server"
    }
  }
}
```

**Important notes:**
- The `kg-mcp-server` command must be globally installed (via `cd client && ./install.sh`)
- MCP server connects to the API at `http://localhost:8000` by default
- Ensure valid JSON syntax (use `jq` or JSON validator to check)

### 3. Restart Claude Desktop

Completely quit Claude Desktop (not just close the window) and reopen.

**macOS:**
- Cmd+Q to quit
- Reopen from Applications

**Windows:**
- Right-click system tray icon → Quit
- Reopen from Start menu

### 4. Verify Connection

In a new Claude Desktop conversation:

```
What ontologies are available in the knowledge graph?
```

Claude should query the database and list your ontologies.

## Example Interactions

### Semantic Search

**You:**
```
Search for concepts about distributed systems in my knowledge graph
```

**Claude:**
```
[uses search_concepts with query: "distributed systems"]

I found 12 concepts related to distributed systems:

1. Microservices Architecture (similarity: 0.94)
2. Distributed Consensus (similarity: 0.91)
3. CAP Theorem (similarity: 0.89)
4. Service Mesh (similarity: 0.87)
...
```

### Path Finding

**You:**
```
How does "Authentication" connect to "Zero Trust Architecture"?
```

**Claude:**
```
[uses find_connection_by_search with from_query: "Authentication", to_query: "Zero Trust Architecture"]

I found a path connecting these concepts (3 hops):

Authentication
  → [REQUIRES] Identity Verification
  → [PART_OF] Security Framework
  → [IMPLEMENTS] Zero Trust Architecture

This shows that authentication requires identity verification, which is part of a security framework that implements zero trust architecture.
```

### Concept Details

**You:**
```
Tell me about the concept "microservices-architecture" in detail
```

**Claude:**
```
[uses get_concept_details with concept_id: "microservices-architecture"]

Concept: Microservices Architecture

Search Terms:
- microservices
- distributed services
- service-oriented architecture

Relationships:
- PART_OF → Distributed Systems Architecture (confidence: 0.89)
- REQUIRES → API Gateway (confidence: 0.87)
- ENABLES → Independent Deployment (confidence: 0.92)
- CONTRADICTS → Monolithic Architecture (confidence: 0.85)

Evidence (5 instances):
1. "Microservices architecture decomposes applications into small, independent services that communicate via APIs."
   Source: architecture-patterns.md

2. "Each microservice can be deployed independently without affecting other services."
   Source: deployment-guide.md

...
```

### Ontology Statistics

**You:**
```
What's in my "Research Papers" ontology?
```

**Claude:**
```
[uses get_ontology_info with ontology_name: "Research Papers"]

Ontology: Research Papers

Statistics:
- Concepts: 247
- Sources: 89
- Evidence instances: 1,203
- Relationships: 478
- Created: 2025-10-15

Top concepts (by evidence):
1. Machine Learning Models (15 instances)
2. Neural Network Architecture (12 instances)
3. Training Optimization (11 instances)

Source files:
- attention-is-all-you-need.pdf (47 concepts)
- bert-pretraining.pdf (52 concepts)
- gpt-architecture.pdf (39 concepts)
...
```

### Text Ingestion

**You:**
```
Ingest this text into my "Meeting Notes" ontology:

Today's architecture review covered the transition from monolithic to microservices.
Key decisions: adopt API gateway pattern, implement service mesh for observability,
and use event-driven communication between services.
```

**Claude:**
```
[uses ingest_text with text content and ontology: "Meeting Notes"]

I've started ingesting this text into your "Meeting Notes" ontology.

Job Status:
- Job ID: job_abc123
- Status: processing
- Progress: 67% (2/3 chunks processed)
- Concepts created: 8

The ingestion is currently running. I'll let you know when it completes.

[... after completion ...]

✓ Ingestion completed successfully!

Results:
- Chunks processed: 3
- Concepts created: 12
- Relationships: 18
- Cost: $0.08

New concepts include:
- API Gateway Pattern
- Service Mesh Observability
- Event-Driven Communication
- Microservices Transition
...
```

## Environment Configuration (Advanced)

### Change API URL

If your API server runs on a different host or port:

**Claude Desktop:**

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "http://192.168.1.100:8000"
      }
    }
  }
}
```

**Claude Code:**

Set environment variable before adding server:
```bash
export KG_API_URL=http://192.168.1.100:8000
claude mcp add knowledge-graph
```

### Multiple Environments

Configure separate servers for development and production:

```json
{
  "mcpServers": {
    "knowledge-graph-dev": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "http://localhost:8000"
      }
    },
    "knowledge-graph-prod": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "https://api.production-host.com"
      }
    }
  }
}
```

Tell Claude which environment to use:
```
Use the knowledge-graph-prod server to search for...
```

## Troubleshooting

### MCP Server Not Connecting

**Check kg CLI is installed:**

```bash
which kg-mcp-server
# Should show: /usr/local/bin/kg-mcp-server
```

If not found:
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

Start if needed:
```bash
./scripts/start-api.sh
```

**Check PostgreSQL is running:**

```bash
docker ps | grep postgres
# Should show knowledge-graph-postgres container
```

Start if needed:
```bash
docker-compose up -d
```

### Claude Can't See Tools

**For Claude Code:**

Remove and re-add the server:
```bash
claude mcp remove knowledge-graph
claude mcp add knowledge-graph
```

**For Claude Desktop:**

- Verify JSON syntax in config file (use `jq` to validate)
- Check paths are correct
- Completely quit and restart Claude Desktop (not just close window)
- Check logs for errors

### Viewing MCP Server Logs

**Claude Desktop logs location:**

**macOS:**
```bash
~/Library/Logs/Claude/mcp*.log

# View logs
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Windows:**
```
%APPDATA%\Claude\logs\mcp*.log
```

**Claude Code:**

MCP server stderr is captured in Claude Code session logs. Errors will appear in the conversation.

### Permission Errors

**Check Node.js version:**
```bash
node --version  # Should be 18.0.0 or higher
```

**Ensure kg-mcp-server is executable:**
```bash
ls -la $(which kg-mcp-server)
# Should show executable permissions
```

### JSON Configuration Errors

**Validate syntax:**

```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | jq .
# Should pretty-print the JSON
# Any syntax errors will be shown
```

**Common mistakes:**
- Missing comma between MCP server entries
- Trailing comma after last entry
- Unquoted keys or values
- Wrong quote types (use " not ')

## Security Considerations

### API Key Protection

- API keys are managed by the FastAPI server (in `.env` file)
- The MCP server only communicates with the API server
- Never commit `claude_desktop_config.json` to version control

### MCP Server Capabilities

The MCP server has **full access** to the API:
- Can query and traverse the graph
- Can ingest text content
- Can manage jobs (approve, cancel)
- Can delete ontologies (with force=true)

**Use with caution** - the MCP server has write access.

In production:
- Use HTTPS for API connections
- Implement API authentication (see `docs/guides/AUTHENTICATION.md`)
- Restrict MCP server network access

### PostgreSQL Security

- Use strong passwords in production
- Restrict network access to PostgreSQL port (5432)
- Configure PostgreSQL authentication (pg_hba.conf)

## Rebuilding After Code Changes

If you modify the MCP server code:

```bash
cd client
npm run build
./install.sh  # Reinstall globally

# For Claude Code: Restart conversation
# For Claude Desktop: Completely quit and restart application
```

## Testing Without Claude

Test MCP server functionality using kg CLI:

```bash
kg search query "linear thinking"
kg ontology list
kg database stats
```

The kg CLI uses the same REST API as the MCP server. If CLI commands work, MCP server should work.

## What's Next

Now that you have MCP integration, you can:

- **[Section 16 - Multi-Modal Ingestion](16-multi-modal-ingestion.md)**: Ingest images, PDFs, and other formats
- **[Section 60 - Case Study: Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)**: Real-world usage examples

For technical details:
- **Architecture:** [ADR-013 - Unified TypeScript Client](architecture/ADR-013-unified-typescript-client.md)
- **Setup Guide:** [guides/MCP_SETUP.md](guides/MCP_SETUP.md)
- **MCP Protocol:** https://spec.modelcontextprotocol.io/

---

← [Previous: Advanced Query Patterns](14-advanced-query-patterns.md) | [Documentation Index](README.md) | [Next: Multi-Modal Ingestion →](16-multi-modal-ingestion.md)
