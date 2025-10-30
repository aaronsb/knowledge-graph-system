# MCP Server Setup Guide

The Knowledge Graph MCP (Model Context Protocol) server enables Claude to query and explore the graph database directly during conversations.

## Prerequisites

- Node.js 18+ installed
- PostgreSQL + Apache AGE database running (see `docs/guides/01-QUICKSTART.md`)
- FastAPI server running (`./scripts/start-api.sh`)
- kg CLI installed globally (`cd client && ./install.sh`)
- **User account created** - Run `kg login` to create an admin account if you haven't already

## Important: Authentication Required

**The MCP server now requires authentication.** You must configure username and password in your MCP server settings. The server will automatically login on startup, making authentication transparent to Claude.

**Features:**
- ✅ Automatic login on startup
- ✅ Automatic token refresh before expiry (refreshes 5 minutes before token expires)
- ✅ Long-lived sessions without manual re-authentication
- ✅ Transparent to Claude - the AI is never aware of authentication

If you previously configured the MCP server without authentication, you'll need to **remove and re-add it** with the new configuration (see below).

## Setup for Claude Code (CLI)

Claude Code uses the `claude` CLI for MCP server management.

### Step 1: Create a User Account (If You Haven't Already)

```bash
# Login to create your admin account
kg login

# Follow the prompts to:
# 1. Create a new admin user (first time)
# 2. Set your username (e.g., "admin")
# 3. Set your password
#
# After successful login, you'll see:
# ✓ Login successful
# ✓ Logged in as: admin (role: admin)
```

### Step 2: Remove Old MCP Server (If Previously Configured)

If you had the MCP server configured without authentication, remove it first:

```bash
claude mcp remove knowledge-graph
```

### Step 3: Add the Knowledge Graph MCP Server

```bash
claude mcp add knowledge-graph
```

You'll be prompted for configuration. Here's what to enter:

```
Server name: knowledge-graph
Command: kg-mcp-server
Arguments (optional): [press Enter to skip]

Do you want to add environment variables? (y/n): y

Environment variable name: KG_USERNAME
Environment variable value: admin

Add another? (y/n): y

Environment variable name: KG_PASSWORD
Environment variable value: [your-password-here]

Add another? (y/n): n
```

**Result:** The MCP server is now configured with authentication. It will automatically login on startup.

### Step 4: Restart Claude Code

Close and reopen Claude Code to reload the MCP server configuration.

### Step 5: Verify Installation

```bash
# List configured MCP servers
claude mcp list

# Should show:
# knowledge-graph: kg-mcp-server  - ✓ Connected
```

Check the MCP server logs (visible in Claude Code stderr) for authentication confirmation:
```
[MCP Auth] Successfully authenticated as admin
[MCP Auth] Token expires at 2025-10-31T12:34:56.789Z
[MCP Auth] Token refresh scheduled in 55 minutes
Knowledge Graph MCP Server running on stdio
```

**Authentication Lifecycle:**
- The MCP server automatically logs in on startup
- JWT tokens are long-lived (typically 1 hour)
- The server automatically refreshes the token 5 minutes before expiry
- You'll see `[MCP Auth] Refreshing authentication token...` in the logs before token expires
- This ensures uninterrupted access without manual intervention

### Step 6: Test Connection

Start a new Claude Code conversation and try:

```
List all ontologies in the database
```

Claude should use the `list_ontologies` tool to query your graph. You should **not** see any 401 authentication errors.

## Setup for Claude Desktop (macOS/Windows)

Claude Desktop requires manual configuration file editing.

### Step 1: Create a User Account (If You Haven't Already)

```bash
# From your terminal, login to create your admin account
kg login

# Follow the prompts to create a user account
# Remember your username and password - you'll need them for Step 3
```

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
    "knowledge-graph": {
      "command": "kg-mcp-server",
      "env": {
        "KG_USERNAME": "admin",
        "KG_PASSWORD": "your-password-here"
      }
    }
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
      "env": {
        "KG_USERNAME": "admin",
        "KG_PASSWORD": "your-password-here"
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
- ✅ The API server must be running: `./scripts/start-api.sh`

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
- Check that `KG_USERNAME` and `KG_PASSWORD` are correct in the config file
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
./scripts/start-api.sh
```

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
# Should show knowledge-graph-postgres container
```

### Environment Variable Issues

**Required environment variables for MCP server:**
- `KG_USERNAME`: Your username for authentication
- `KG_PASSWORD`: Your password for authentication

**Optional environment variables:**
- `KG_API_URL`: API server URL (default: `http://localhost:8000`)

**If you see 401 authentication errors:**
- Verify `KG_USERNAME` and `KG_PASSWORD` are set in your MCP config
- Test login with `kg login` using the same credentials
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
        "KG_API_URL": "http://localhost:8000",
        "KG_USERNAME": "admin",
        "KG_PASSWORD": "dev-password"
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
        "KG_USERNAME": "admin",
        "KG_PASSWORD": "prod-password"
      }
    }
  }
}
```

**Environment Variables:**
- `KG_API_URL`: API server URL (default: `http://localhost:8000`)
- `KG_USERNAME`: Username for authentication (required for authenticated APIs)
- `KG_PASSWORD`: Password for authentication (required for authenticated APIs)

## Security Considerations

### API Key Protection

- **Never commit** `claude_desktop_config.json`
- API keys are managed by the FastAPI server (in `.env` file)
- The MCP server only communicates with the API server

### API Server Authentication

- The FastAPI server requires JWT-based authentication
- MCP server authenticates automatically using `KG_USERNAME` and `KG_PASSWORD` environment variables
- JWT tokens are stored in memory during the MCP server session
- For production, use HTTPS and strong passwords
- **Never commit** credentials to version control
- Store credentials securely in Claude Desktop config file (`claude_desktop_config.json`)
- Consider using separate user accounts for MCP server vs. CLI usage

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
