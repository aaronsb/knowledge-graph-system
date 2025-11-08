# Knowledge Graph TypeScript Client

Unified TypeScript client with both CLI tool (`kg`) and MCP server (`kg-mcp-server`) executables.

## Installation

### User-Local Installation (Recommended)

Install to `~/.local/bin/` (no sudo required):

```bash
cd client
./install.sh
```

This will:
1. Build the TypeScript code
2. Install `kg` and `kg-mcp-server` commands to `~/.local/bin/`
3. Check if `~/.local/bin` is in your PATH

**Add to PATH** (if needed):

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export PATH="${HOME}/.local/bin:${PATH}"
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### Verify Installation

```bash
kg --version
kg health
```

### Uninstall

```bash
cd client
./uninstall.sh
```

## Usage

### Search & Exploration

```bash
# Search for concepts
kg search query "thinking patterns" --limit 5

# Get concept details
kg search details <concept-id>

# Find related concepts
kg search related <concept-id> --depth 2

# Find path between concepts
kg search connect <from-id> <to-id>
```

### Database Operations

```bash
# Database statistics
kg database stats

# Connection info
kg database info

# Health check
kg database health
```

### Ontology Management

```bash
# List all ontologies
kg ontology list

# Ontology details
kg ontology info "Ontology Name"

# List files in ontology
kg ontology files "Ontology Name"

# Delete ontology (requires --force)
kg ontology delete "Ontology Name" --force
```

### Ingestion

```bash
# Ingest a file
kg ingest file document.txt --ontology "My Ontology"

# Ingest text
kg ingest text "Content here..." --ontology "My Ontology"

# Check ingestion job status
kg jobs status <job-id>

# List all jobs
kg jobs list
```

## Development

### Build

```bash
npm run build
```

### Watch Mode

```bash
npm run dev
```

### Type Check

```bash
npm run type-check
```

### Run Without Installing

```bash
node dist/index.js <command>
```

## Configuration

Set these environment variables:

```bash
export KG_API_URL=http://localhost:8000  # API server URL
export KG_CLIENT_ID=my-client            # Optional client ID
export KG_API_KEY=your-key               # Optional API key
```

Or use command-line flags:

```bash
kg --api-url http://localhost:8000 search query "test"
```

## Architecture

- **CLI Entry**: `src/index.ts` - CLI tool entry point (kg command)
- **MCP Entry**: `src/mcp-server.ts` - MCP server entry point (kg-mcp-server command)
- **API Client**: `src/api/client.ts` - HTTP client wrapper (shared by both)
- **CLI Commands**: `src/cli/` - Commander.js command definitions
- **Types**: `src/types/` - TypeScript interfaces matching FastAPI models

Both CLI and MCP server share the same `KnowledgeGraphClient` class and REST API.

## MCP Server

The MCP server is automatically installed with the client. See `docs/guides/MCP_SETUP.md` for configuration.

**Quick setup for Claude Code:**
```bash
claude mcp add knowledge-graph
# Command: kg-mcp-server
```

**Quick setup for Claude Desktop:**
```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "kg-mcp-server"
    }
  }
}
```

The MCP server provides 18 tools for querying and managing the knowledge graph.
