# Connect via MCP

The Kappa Graph MCP server gives Claude and other MCP-compatible AI clients direct access to your graph — search, traversal, ingestion, and job management — during a conversation.

## Before you start

- Node.js 20.12.0 or later
- Kappa Graph platform running: `./operator.sh start`
- `kg` CLI installed: `cd cli && npm run build && ./install.sh`
- An admin user account (created by `./operator.sh init`)

## Create OAuth credentials

The MCP server authenticates via OAuth 2.0 client credentials. Run this once to create a dedicated client:

```bash
kg login
kg oauth create-mcp
```

`kg oauth create-mcp` prints your `KG_OAUTH_CLIENT_ID` and `KG_OAUTH_CLIENT_SECRET`. Save the secret now — it is shown only once.

The MCP server exchanges these long-lived credentials for short-lived access tokens (1 hour) automatically. Tokens refresh before expiry without any manual action.

## Connect Claude Code

```bash
claude mcp add knowledge-graph kg-mcp-server \
  --env KG_OAUTH_CLIENT_ID=<client-id> \
  --env KG_OAUTH_CLIENT_SECRET=<client-secret> \
  --env KG_API_URL=http://localhost:8000 \
  -s local
```

Restart Claude Code to load the new server.

Verify:

```bash
claude mcp list
# knowledge-graph: kg-mcp-server  - ✓ Connected
```

## Connect Claude Desktop

Edit the Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the `knowledge-graph` entry:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "kg-mcp-server",
      "args": [],
      "env": {
        "KG_API_URL": "http://localhost:8000",
        "KG_OAUTH_CLIENT_ID": "<client-id>",
        "KG_OAUTH_CLIENT_SECRET": "<client-secret>"
      }
    }
  }
}
```

Quit and relaunch Claude Desktop completely (not just close the window).

## Verify the connection

Start a new conversation and ask:

```
What ontologies are available?
```

Claude calls `list_ontologies` and returns results. If you see 401 errors instead:

```bash
# Confirm the OAuth client exists
kg oauth clients

# Confirm the API is reachable
curl http://localhost:8000/health
# {"status":"healthy"}
```

## What the MCP server can do

Once connected, Claude can search concepts, traverse relationships, find paths between concepts, ingest text, manage ingestion jobs, inspect ontologies, and query system status. The full tool schema is in [Reference › MCP Tools](../reference/mcp.md) (generated from `cli/scripts/generate-mcp-docs.mjs`).

Example conversations:

```
Find concepts related to distributed systems.
```

```
What evidence supports the claim that caching improves performance?
```

```
Find the shortest path from 'technical debt' to 'team productivity'.
```

```
Ingest this text into the architecture ontology: <paste content>
```

```
Show all running ingestion jobs.
```

The MCP server has write access: it can ingest content, approve jobs, and delete ontologies (`force=true`). Configure a separate OAuth client with a read-only role for shared or untrusted environments.

## Multiple environments

To connect to a remote instance or maintain separate dev and prod clients, add a second entry under `mcpServers` with a distinct key and the appropriate `KG_API_URL`:

```json
{
  "mcpServers": {
    "knowledge-graph-dev": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "http://localhost:8000",
        "KG_OAUTH_CLIENT_ID": "<dev-client-id>",
        "KG_OAUTH_CLIENT_SECRET": "<dev-client-secret>"
      }
    },
    "knowledge-graph-prod": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "https://api.your-host.example.com",
        "KG_OAUTH_CLIENT_ID": "<prod-client-id>",
        "KG_OAUTH_CLIENT_SECRET": "<prod-client-secret>"
      }
    }
  }
}
```

## Troubleshooting

**`kg-mcp-server` not found:**

```bash
which kg-mcp-server   # should print /usr/local/bin/kg-mcp-server
cd cli && ./uninstall.sh && ./install.sh
```

**Claude does not see the tools (Claude Code):**

```bash
claude mcp remove knowledge-graph
claude mcp add knowledge-graph kg-mcp-server \
  --env KG_OAUTH_CLIENT_ID=<client-id> \
  --env KG_OAUTH_CLIENT_SECRET=<client-secret> \
  --env KG_API_URL=http://localhost:8000 \
  -s local
```

**Claude does not see the tools (Claude Desktop):**
Validate the JSON in the config file (`jq . claude_desktop_config.json`), then quit and relaunch the application.

**MCP server logs:**

- Claude Desktop (macOS): `tail -f ~/Library/Logs/Claude/mcp*.log`
- Claude Desktop (Windows): `%APPDATA%\Claude\logs\mcp*.log`
- Claude Code: MCP stderr appears in the session log.

A successful startup looks like:

```
[MCP Auth] Successfully authenticated with OAuth client
[MCP Auth] Token expires at 2026-07-14T12:34:56.789Z
Knowledge Graph MCP Server running on stdio
```

**After rebuilding the CLI:**

```bash
cd cli && npm run build && ./install.sh
# Claude Code: restart the conversation
# Claude Desktop: quit and relaunch
```
