# MCP Server Setup Guide

The Knowledge Graph MCP (Model Context Protocol) server enables Claude to query and explore the graph database directly during conversations.

## Prerequisites

- Node.js 18+ installed
- PostgreSQL + Apache AGE database running (see `docs/guides/QUICKSTART.md`)
- FastAPI server running (`./scripts/services/start-api.sh`)
- kg CLI installed globally (`cd client && ./install.sh`)
- **User account created** - Run `kg login` to create an admin account if you haven't already

## Authentication

The MCP server uses OAuth 2.0 client credentials for authentication. You configure OAuth client ID and secret (`KG_OAUTH_CLIENT_ID` and `KG_OAUTH_CLIENT_SECRET`) in your MCP server settings. The server automatically obtains and refreshes access tokens, making authentication transparent to Claude.

**Features:**
- ✅ OAuth 2.0 client credentials grant
- ✅ Automatic access token refresh before expiry
- ✅ Long-lived OAuth client credentials
- ✅ Transparent to Claude - the AI is never aware of authentication

## Setup for Claude Code (CLI)

Claude Code uses the `claude` CLI for MCP server management.

### Step 1: Login and Create OAuth Client

First, authenticate and create OAuth credentials for the MCP server:

```bash
# Login with your admin credentials
kg login

# Create OAuth client specifically for MCP server
kg oauth create-mcp
```

The `kg oauth create-mcp` command will output your OAuth credentials and provide both manual configuration instructions and a `claude mcp add` command. **Save these credentials securely** - the client secret is shown only once!

### Step 2: Add the Knowledge Graph MCP Server

Use the `claude mcp add` command shown in the output from Step 1, or manually configure:

```bash
claude mcp add knowledge-graph kg-mcp-server \
  --env KG_OAUTH_CLIENT_ID=your-client-id-from-step-1 \
  --env KG_OAUTH_CLIENT_SECRET=your-client-secret-from-step-1 \
  --env KG_API_URL=http://localhost:8000 \
  -s local
```

**Result:** The MCP server is configured with OAuth 2.0 and automatically obtains access tokens on startup.

### Step 3: Restart Claude Code

Close and reopen Claude Code to reload the MCP server configuration.

### Step 4: Verify Installation

```bash
# List configured MCP servers
claude mcp list

# Should show:
# knowledge-graph: kg-mcp-server  - ✓ Connected
```

Check the MCP server logs (visible in Claude Code stderr) for authentication confirmation:
```
[MCP Auth] Successfully authenticated with OAuth client
[MCP Auth] Client ID: kg-mcp-server-username
[MCP Auth] Token expires at 2025-10-31T12:34:56.789Z
Knowledge Graph MCP Server running on stdio
```

**OAuth Authentication Lifecycle:**
- The MCP server uses long-lived OAuth client credentials (client_id + client_secret)
- On startup, it obtains a short-lived access token (typically 1 hour) via OAuth 2.0 client credentials grant
- Access tokens are automatically refreshed before expiry (every ~55 minutes)
- You'll see `[MCP Auth] Refreshing authentication token...` in the logs before token expires
- OAuth client credentials never expire and don't require manual renewal
- This ensures uninterrupted access without manual intervention

### Step 5: Test Connection

Start a new Claude Code conversation and try:

```
List all ontologies in the database
```

Claude should use the `list_ontologies` tool to query your graph. You should **not** see any 401 authentication errors.

## Setup for Claude Desktop (macOS/Windows)

Claude Desktop requires manual configuration file editing.

### Step 1: Login and Create OAuth Client

From your terminal, authenticate and create OAuth credentials for Claude Desktop:

```bash
# Login with your admin credentials
kg login

# Create OAuth client specifically for MCP server
kg oauth create-mcp
```

The command will display your OAuth credentials with ready-to-paste configuration. **Save these credentials securely** - the client secret is shown only once!

### Step 2: Locate Configuration File

**macOS:**
```bash
# The config file is located at:
~/Library/Application Support/Claude/claude_desktop_config.json

# Open it with your preferred editor:
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```
# The config file is located at:
%APPDATA%\Claude\claude_desktop_config.json

# Open it with Notepad or your preferred editor
```

### Step 3: Edit Configuration

**If the file is empty or only has `{}`, replace the entire contents with:**

```json
{
  "mcpServers": {

  }
}
```

**If you already have other MCP servers configured, add the `knowledge-graph` entry:**

```json
{
  "mcpServers": {
    "existing-server": {
      "command": "some-other-mcp-server"
    },
    "knowledge-graph": {  
        "command": "kg-mcp-server",  
        "args": [],  
        "env": {  
          "KG_API_URL": "http://localhost:8000",  
          "KG_USERNAME": "claude",  
          "KG_PASSWORD": "Password1!"  
        }  
     }
  }
}
```

**Configuration Breakdown:**
- `command`: `kg-mcp-server` - The globally installed MCP server command
- `env.KG_USERNAME`: Your username (same as what you used for `kg login`)
- `env.KG_PASSWORD`: Your password
- The MCP server will automatically login on startup using these credentials
- Authentication happens transparently - Claude is not aware of it

**Important Checklist:**
- ✅ Replace `your-password-here` with your actual password
- ✅ Ensure JSON syntax is valid (use a JSON validator if needed)
- ✅ The `kg-mcp-server` command must be globally installed: `cd client && ./install.sh`
- ✅ The API server must be running: `./scripts/services/start-api.sh`

### Step 4: Restart Claude Desktop

**Important:** You must completely quit and restart Claude Desktop:
1. **Quit Claude Desktop completely** (Cmd+Q on macOS, or close from system tray on Windows)
2. Wait a few seconds
3. Open Claude Desktop again

The MCP server will initialize on startup and automatically authenticate.

### Step 5: Verify Connection

In Claude Desktop, start a new conversation and type:

```
What ontologies are available in the knowledge graph?
```

**Expected behavior:**
- Claude should use the `list_ontologies` tool
- You should see a list of your ontologies
- There should be **no 401 authentication errors**

**If you see authentication errors:**
- Check that `KG_OAUTH_CLIENT_ID` and `KG_OAUTH_CLIENT_SECRET` are correct in the config file
- Verify the OAuth client exists: `kg oauth clients`
- Verify the API server is running: `curl http://localhost:8000/health`
- Check Claude Desktop logs (see Troubleshooting section below)

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
./scripts/services/start-api.sh
```

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
# Should show knowledge-graph-postgres container
```

### Environment Variable Issues

**Required environment variables for MCP server:**
- `KG_OAUTH_CLIENT_ID`: OAuth client ID (from `kg oauth create-mcp`)
- `KG_OAUTH_CLIENT_SECRET`: OAuth client secret (shown once during creation)

**Optional environment variables:**
- `KG_API_URL`: API server URL (default: `http://localhost:8000`)

**If you see 401 authentication errors:**
- Verify `KG_OAUTH_CLIENT_ID` and `KG_OAUTH_CLIENT_SECRET` are set in your MCP config
- Verify the OAuth client exists: `kg oauth clients`
- Test that credentials work: `kg login` should show you're already logged in
- Check MCP server logs for authentication messages
- Ensure the API server is running and accepting connections

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

1. Add API endpoint to `api/app/routes/` (if needed)
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
        "KG_API_URL": "http://localhost:8000",
        "KG_OAUTH_CLIENT_ID": "dev-oauth-client-id",
        "KG_OAUTH_CLIENT_SECRET": "dev-oauth-client-secret"
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
        "KG_API_URL": "https://api.production-host.com",
        "KG_OAUTH_CLIENT_ID": "prod-oauth-client-id",
        "KG_OAUTH_CLIENT_SECRET": "prod-oauth-client-secret"
      }
    }
  }
}
```

**Environment Variables:**
- `KG_API_URL`: API server URL (default: `http://localhost:8000`)
- `KG_OAUTH_CLIENT_ID`: OAuth client ID (required - create with `kg oauth create-mcp`)
- `KG_OAUTH_CLIENT_SECRET`: OAuth client secret (required - shown once during creation)

## Security Considerations

### API Key Protection

- **Never commit** `claude_desktop_config.json`
- API keys are managed by the FastAPI server (in `.env` file)
- The MCP server only communicates with the API server

### API Server Authentication

- The FastAPI server requires OAuth 2.0 authentication
- MCP server authenticates automatically using OAuth client credentials grant
- OAuth client credentials (`KG_OAUTH_CLIENT_ID` + `KG_OAUTH_CLIENT_SECRET`) are long-lived and don't expire
- Access tokens are short-lived (1 hour) and refreshed automatically before expiry
- OAuth tokens are stored in memory during the MCP server session
- For production, use HTTPS and protect OAuth credentials
- **Never commit** credentials to version control
- Store credentials securely in Claude Desktop config file (`claude_desktop_config.json`)
- Consider creating separate OAuth clients for different environments (dev, prod)

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

For more examples, see `docs/03-EXAMPLES.md`.
