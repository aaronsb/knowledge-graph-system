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
| `kg health` | Check API server health |
| `kg login` | Authenticate with username and password |
| `kg logout` | End authentication session |
| `kg oauth` | Manage OAuth clients |
| `kg config` | Manage CLI configuration |
| `kg mcp-config` | Manage MCP file access allowlist |
| `kg ingest <file>` | Ingest documents into the knowledge graph |
| `kg search <query>` | Search and explore the knowledge graph |
| `kg concept` | Create, list, show, and delete concepts |
| `kg edge` | Manage edges (relationships) between concepts |
| `kg batch` | Batch graph operations (atomic import) |
| `kg document` | Search and retrieve documents |
| `kg source` | Manage source documents |
| `kg ontology` | Manage ontologies (knowledge domains) |
| `kg vocabulary` | Vocabulary management and consolidation |
| `kg database` | Database operations and information |
| `kg jobs` | Manage ingestion jobs |
| `kg admin` | System administration (backup, RBAC, AI config) |
| `kg polarity` | Polarity axis analysis between concept poles |
| `kg projection` | Manage embedding projections for visualization |
| `kg artifact` | Manage stored computation results |
| `kg group` | Manage groups and membership |
| `kg query-def` | Manage saved query definitions |
| `kg program` | Manage graph programs (GraphProgram DSL) |
| `kg storage` | Storage diagnostics and inspection |
| `kg ls` | List resources (Unix-style shortcut) |
| `kg cat` | Display resource details (Unix-style shortcut) |
| `kg stat` | Show status or statistics (Unix-style shortcut) |
| `kg rm` | Remove or delete resources (Unix-style shortcut) |

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

| Tool | Description |
|------|-------------|
| `search` | Search concepts, source passages, or documents by semantic similarity |
| `concept` | Get concept details, find related concepts, or discover connection paths |
| `ontology` | Manage ontologies: list, info, files, scores, annealing |
| `job` | Manage ingestion jobs: status, list, approve, cancel, cleanup |
| `ingest` | Ingest content: submit text, inspect/ingest files, ingest directories |
| `source` | Retrieve original source content (text or image) for a source node |
| `epistemic_status` | Vocabulary epistemic status classification for relationship types |
| `analyze_polarity_axis` | Analyze semantic dimensions between two concept poles |
| `artifact` | Manage saved artifacts (persisted search results, projections, analyses) |
| `document` | Work with documents: list, show content, get extracted concepts |
| `graph` | Create, edit, delete, and list concepts and edges directly |
| `program` | Compose and execute GraphProgram queries (set-algebraic DSL) |

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
