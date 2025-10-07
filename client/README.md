# Knowledge Graph TypeScript Client

Unified TypeScript client for the Knowledge Graph system. Can run as:
1. **CLI tool** - command-line interface for ingestion and job management
2. **MCP server** - Model Context Protocol server for Claude Desktop (Phase 2)

## Quick Start

### Install Dependencies

```bash
cd client
npm install
```

### Build

```bash
npm run build
```

### Run CLI

```bash
# Using npm
npm start -- health

# Or use node directly
node dist/index.js health

# Or make it executable (recommended)
chmod +x dist/index.js
./dist/index.js health

# Or install globally (creates 'kg' command)
npm link
kg health
```

## CLI Usage

### Health Check

```bash
kg health
```

### Ingest Documents

**Ingest a file:**
```bash
kg ingest file mydocument.txt --ontology "My Ontology"

# With options
kg ingest file document.pdf \
  --ontology "My Ontology" \
  --target-words 1500 \
  --overlap-words 300 \
  --force

# Submit and exit (don't wait)
kg ingest file large.txt \
  --ontology "My Ontology" \
  --no-wait
```

**Ingest raw text:**
```bash
kg ingest text "This is my document content..." \
  --ontology "Test" \
  --filename "test.txt"
```

### Job Management

**Get job status:**
```bash
kg jobs status job_abc123

# Watch until completion
kg jobs status job_abc123 --watch
```

**List jobs:**
```bash
# All jobs
kg jobs list

# Filter by status
kg jobs list --status completed
kg jobs list --status processing

# Limit results
kg jobs list --limit 10
```

**Cancel a job:**
```bash
kg jobs cancel job_abc123
```

## Configuration

### Environment Variables

```bash
# API endpoint (default: http://localhost:8000)
export KG_API_URL=http://localhost:8000

# Client ID for multi-tenancy (optional)
export KG_CLIENT_ID=my-client

# API key for authentication (optional, Phase 2)
export KG_API_KEY=your-api-key
```

### Command-line Options

All commands support global options:

```bash
kg --api-url http://prod-api.example.com health
kg --client-id my-client jobs list
kg --api-key secret-key ingest file doc.txt --ontology "Test"
```

## API Client Library

The client can also be used as a library:

```typescript
import { KnowledgeGraphClient } from '@kg/client';

const client = new KnowledgeGraphClient({
  baseUrl: 'http://localhost:8000',
  clientId: 'my-app',
  apiKey: 'optional-key'
});

// Ingest a file
const result = await client.ingestFile('document.txt', {
  ontology: 'My Ontology',
  force: false,
  options: {
    target_words: 1000
  }
});

console.log(`Job ID: ${result.job_id}`);

// Poll for completion
const job = await client.pollJob(result.job_id, (job) => {
  console.log(`Progress: ${job.progress?.percent}%`);
});

console.log('Completed!', job.result);
```

## MCP Server Mode (Phase 2)

When `MCP_SERVER_MODE=true`, the client runs as an MCP server:

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["/path/to/client/dist/index.js"],
      "env": {
        "MCP_SERVER_MODE": "true",
        "KG_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Not implemented yet - coming in Phase 2!**

## Development

### Watch mode (auto-rebuild)

```bash
npm run dev
```

### Type checking

```bash
npm run type-check
```

### Clean build

```bash
npm run clean
npm run build
```

## Available Commands

```
kg health                           # Check API health
kg ingest file <path>               # Ingest a document file
kg ingest text <text>               # Ingest raw text
kg jobs status <job-id>             # Get job status
kg jobs list                        # List recent jobs
kg jobs cancel <job-id>             # Cancel a job
```

## Examples

### Basic Workflow

```bash
# 1. Check API is running
kg health

# 2. Ingest a document
kg ingest file research_paper.pdf --ontology "Research Papers"

# Output: ✓ Job submitted: job_abc123
# 3. Watch progress
kg jobs status job_abc123 --watch

# Output:
# Processing: 45% (23/50 chunks)
# ...
# ✓ Ingestion completed!
# Results:
#   Chunks processed: 50
#   Concepts created: 127
#   ...
#   Total cost: $2.46
```

### Batch Ingestion

```bash
# Ingest multiple files (submit all, don't wait)
for file in documents/*.txt; do
  kg ingest file "$file" \
    --ontology "My Collection" \
    --no-wait
done

# Monitor all jobs
kg jobs list --status processing
```

### Error Handling

```bash
# If duplicate detected
kg ingest file doc.txt --ontology "Test"
# ⚠ Duplicate detected
#   Existing job: job_xyz789
#   Use --force to re-ingest

# Force re-ingestion
kg ingest file doc.txt --ontology "Test" --force
```

## Publishing (Future)

When ready to publish:

```bash
# 1. Update version in package.json
# 2. Build
npm run build

# 3. Publish to npm
npm publish --access public

# Or install from GitHub before publishing
npx github:owner/repo/client
```

## Architecture

```
client/
├── src/
│   ├── index.ts           # Entry point (CLI or MCP mode)
│   ├── types/             # TypeScript interfaces
│   │   └── index.ts       # API types matching FastAPI models
│   ├── api/               # API client
│   │   └── client.ts      # HTTP client wrapping FastAPI endpoints
│   ├── cli/               # CLI commands
│   │   ├── commands.ts    # Command registration
│   │   ├── health.ts      # Health check
│   │   ├── ingest.ts      # Ingestion commands
│   │   └── jobs.ts        # Job management
│   └── mcp/               # MCP server (Phase 2)
│       └── (empty)
├── dist/                  # Compiled output
├── package.json
├── tsconfig.json
└── README.md
```

## Troubleshooting

**"Cannot connect to API":**
- Check API is running: `curl http://localhost:8000/health`
- Verify `KG_API_URL` is correct
- Check firewall/network settings

**"Command not found: kg":**
- Run `npm link` in client directory
- Or use `node dist/index.js` directly

**Types don't match API:**
- API types are in `src/types/index.ts`
- Must match FastAPI Pydantic models
- Rebuild after API changes: `npm run build`

## Phase 2 Roadmap

- [ ] MCP server implementation
- [ ] Real-time job updates (WebSocket/SSE)
- [ ] Concept search commands
- [ ] Cypher query command
- [ ] Graph visualization
- [ ] Ontology management

## License

MIT
