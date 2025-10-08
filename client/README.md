# Knowledge Graph TypeScript Client

Unified TypeScript client that runs as both a CLI tool and MCP server (future).

## Installation

### User-Local Installation (Recommended)

Install to `~/.local/bin/` (no sudo required):

```bash
cd client
./install.sh
```

This will:
1. Build the TypeScript code
2. Install `kg` command to `~/.local/bin/`
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

- **Entry Point**: `src/index.ts` - Mode detection (CLI vs MCP)
- **API Client**: `src/api/client.ts` - HTTP client wrapper
- **CLI Commands**: `src/cli/` - Commander.js command definitions
- **Types**: `src/types/` - TypeScript interfaces matching FastAPI models

Both CLI and future MCP server share the same `KnowledgeGraphClient` class.

## Future: MCP Server Mode

To run as MCP server (Phase 2):

```bash
MCP_SERVER_MODE=true node dist/index.js
```

Configure in Claude Desktop:
```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["/absolute/path/to/client/dist/index.js"],
      "env": {
        "MCP_SERVER_MODE": "true",
        "KG_API_URL": "http://localhost:8000"
      }
    }
  }
}
```
