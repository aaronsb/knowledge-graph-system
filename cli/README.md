# @aaronsb/kg-cli

CLI and MCP server for interacting with [Knowledge Graph System](https://github.com/aaronsb/knowledge-graph-system) deployments.

## Installation

**Global install (requires sudo or npm configured for user-local):**
```bash
npm install -g @aaronsb/kg-cli
```

**User-local install (no sudo required):**
```bash
npm install -g @aaronsb/kg-cli --prefix ~/.local
```
Then ensure `~/.local/bin` is in your PATH.

**Run without installing:**
```bash
npx @aaronsb/kg-cli health
npx @aaronsb/kg-cli search "query"
```

This installs two commands:
- `kg` - Command-line interface for the knowledge graph
- `kg-mcp-server` - MCP server for AI assistant integration

## Quick Start

```bash
# Configure your knowledge graph endpoint
kg config set api.url https://kg.example.com/api

# Login
kg login

# Check health
kg health

# Ingest a document
kg ingest document.pdf

# Search concepts
kg search "machine learning"
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `kg health` | Check API connection |
| `kg login` | Authenticate with the API |
| `kg logout` | Clear saved credentials |
| `kg config` | View/edit configuration |
| `kg ingest <file>` | Submit document for extraction |
| `kg search <query>` | Search concepts |
| `kg jobs` | List extraction jobs |
| `kg artifact` | Manage artifacts |
| `kg document` | Manage documents |

Run `kg --help` or `kg <command> --help` for detailed usage.

## MCP Server

The MCP server allows AI assistants (like Claude) to interact with your knowledge graph.

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "npx",
      "args": ["-p", "@aaronsb/kg-cli", "kg-mcp-server"],
      "env": {
        "KG_API_URL": "https://kg.example.com/api",
        "KG_API_TOKEN": "your-token-here"
      }
    }
  }
}
```

Or if installed globally/user-local (simpler):
```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "kg-mcp-server",
      "env": {
        "KG_API_URL": "https://kg.example.com/api",
        "KG_API_TOKEN": "your-token-here"
      }
    }
  }
}
```

### Available MCP Tools

- `search_concepts` - Semantic search across the knowledge graph
- `get_concept` - Get details about a specific concept
- `list_sources` - List ingested documents
- `get_relationships` - Find connections between concepts
- `ingest_document` - Submit new documents (with approval)

## Configuration

Configuration is stored in `~/.config/kg/config.json`:

```json
{
  "api": {
    "url": "https://kg.example.com/api"
  },
  "auth": {
    "token": "..."
  }
}
```

Or use environment variables:
- `KG_API_URL` - API endpoint
- `KG_API_TOKEN` - Authentication token

## Requirements

- Node.js 18+
- A running Knowledge Graph System instance

## Shell Alias (optional)

If using npx, add an alias to your shell profile:
```bash
alias kg='npx @aaronsb/kg-cli'
```

## Links

- [Knowledge Graph System](https://github.com/aaronsb/knowledge-graph-system)
- [Documentation](https://github.com/aaronsb/knowledge-graph-system/tree/main/docs)
- [Issues](https://github.com/aaronsb/knowledge-graph-system/issues)

## License

MIT
