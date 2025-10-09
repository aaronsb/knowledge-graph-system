# ADR-013: Unified TypeScript Client (CLI + MCP Server)

**Status:** Accepted (Phase 1: CLI, Phase 2: MCP)
**Date:** 2025-10-06
**Deciders:** Development Team
**Pattern Source:** Anthropic's `@modelcontextprotocol` packages

## Context

The system needs multiple client interfaces:

1. **CLI Tool**: Human-friendly terminal interface for direct graph interaction
2. **MCP Server**: Machine-readable interface for Claude Desktop/Code integration

Traditional approach: Build separate codebases for each interface.

**Problem**: Code duplication for:
- API client logic (HTTP requests, response parsing)
- Type definitions (matching FastAPI Pydantic models)
- Error handling
- Configuration management

**Opportunity**: Anthropic's MCP packages (`@modelcontextprotocol/server-*`) demonstrate a pattern: **single TypeScript codebase, runtime mode detection**.

## Decision

Build a **unified TypeScript client** in `client/` directory following Anthropic's pattern:

```typescript
// Entry point: client/src/index.ts
if (process.env.MCP_SERVER_MODE === 'true') {
    // MCP server mode (Phase 2)
    import('./mcp/server').then(startMcpServer);
} else {
    // CLI mode (Phase 1)
    import('./cli/commands').then(runCli);
}
```

### Directory Structure

```
client/
├── src/
│   ├── index.ts              # Entry point (mode detection)
│   ├── types/
│   │   └── index.ts          # TypeScript types matching FastAPI models
│   ├── api/
│   │   └── client.ts         # HTTP client wrapping REST API
│   ├── cli/                  # CLI mode (Phase 1)
│   │   ├── commands.ts       # Command registration
│   │   ├── health.ts         # Health check command
│   │   ├── ingest.ts         # Ingestion commands
│   │   └── jobs.ts           # Job management commands
│   └── mcp/                  # MCP server mode (Phase 2)
│       └── (empty)           # Not yet implemented
├── dist/                     # Compiled output
├── package.json
├── tsconfig.json
└── README.md
```

## Shared Components

### 1. Type Definitions (`src/types/index.ts`)

**Purpose**: TypeScript interfaces matching FastAPI Pydantic models exactly.

```typescript
// Matches IngestRequest in src/api/models/requests.py
export interface IngestRequest {
  ontology: string;
  filename?: string;
  force?: boolean;
  options?: {
    target_words?: number;
    overlap_words?: number;
  };
}

// Matches JobStatus in src/api/models/responses.py
export interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress?: {
    stage?: string;
    percent?: number;
    chunks_processed?: number;
    chunks_total?: number;
    concepts_created?: number;
  };
  result?: any;
  error?: string;
  created_at?: string;
  updated_at?: string;
}

// Union type for ingestion responses
export type JobSubmitResponse = { job_id: string; status: string; message: string };
export type DuplicateJobResponse = {
  duplicate: true;
  existing_job_id: string;
  status: string;
  message: string;
  use_force?: string;
  result?: any;
};
```

**Benefit**: Changes to API types propagate to both CLI and MCP modes automatically.

### 2. API Client (`src/api/client.ts`)

**Purpose**: HTTP wrapper with typed requests/responses.

```typescript
export class KnowledgeGraphClient {
  private client: AxiosInstance;

  constructor(config: ClientConfig) {
    this.client = axios.create({
      baseURL: config.baseUrl || 'http://localhost:8000',
      headers: {
        'X-Client-ID': config.clientId || 'typescript-client',
        'X-API-Key': config.apiKey,
      },
    });
  }

  async ingestFile(
    filePath: string,
    request: IngestRequest
  ): Promise<JobSubmitResponse | DuplicateJobResponse> {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('ontology', request.ontology);
    if (request.force) form.append('force', 'true');

    const response = await this.client.post('/ingest', form, {
      headers: form.getHeaders(),
    });
    return response.data;
  }

  async pollJob(
    jobId: string,
    onProgress?: (job: JobStatus) => void
  ): Promise<JobStatus> {
    while (true) {
      const job = await this.getJob(jobId);
      if (onProgress) onProgress(job);

      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        return job;
      }

      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
}
```

**Benefit**: Both CLI and MCP use same HTTP client, reducing bugs and duplication.

### 3. Configuration

**Environment Variables**:
```bash
KG_API_URL=http://localhost:8000
KG_CLIENT_ID=my-client
KG_API_KEY=optional-key
MCP_SERVER_MODE=false  # or "true" for MCP mode
```

**CLI Override** (command-line flags take precedence):
```bash
kg --api-url http://prod.example.com health
kg --client-id production-client jobs list
```

## Phase 1: CLI Implementation

### Commands

**Health Check**:
```bash
kg health
# Output: ✓ API server is healthy
```

**Ingestion**:
```bash
# File ingestion
kg ingest file document.txt --ontology "Research Papers"

# With options
kg ingest file paper.pdf \
  --ontology "Research Papers" \
  --target-words 1500 \
  --overlap-words 300 \
  --force

# Text ingestion
kg ingest text "This is raw text content..." \
  --ontology "Test" \
  --filename "test.txt"

# Submit and exit (don't wait)
kg ingest file large.txt --ontology "Docs" --no-wait
```

**Job Management**:
```bash
# Get status
kg jobs status job_abc123

# Watch until completion
kg jobs status job_abc123 --watch

# List jobs
kg jobs list
kg jobs list --status completed --limit 10

# Cancel job
kg jobs cancel job_abc123
```

### User Experience Features

**Progress Display** (using `ora` spinner):
```
⠋ Processing... 45% (23/50 chunks, 127 concepts)
```

**Duplicate Detection**:
```
⚠ Duplicate detected
  Existing job: job_xyz789
  Status: completed

  Use --force to re-ingest

✓ Previous ingestion completed:
  Chunks processed: 50
  Concepts created: 127
  Total cost: $2.46
```

**Color-coded Output** (using `chalk`):
- Blue: Info messages
- Green: Success
- Yellow: Warnings
- Red: Errors
- Gray: Metadata

### Installation Options

**1. Wrapper Script (Recommended)**:
```bash
./scripts/kg-cli.sh health
```

**2. Direct Execution**:
```bash
node client/dist/index.js health
```

**3. Add to PATH**:
```bash
export PATH="/path/to/knowledge-graph-system/scripts:$PATH"
alias kg='kg-cli.sh'
```

**4. npm link (Optional)**:
```bash
cd client
npm link  # May require sudo
kg health
```

**Rationale for Wrapper Script**: Avoids npm link permission issues while providing clean UX.

## Phase 2: MCP Server Implementation (Future)

### Mode Detection

```typescript
// client/src/index.ts
if (process.env.MCP_SERVER_MODE === 'true') {
  import('./mcp/server').then(({ startMcpServer }) => {
    startMcpServer();
  });
}
```

### MCP Server Structure

```typescript
// client/src/mcp/server.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { KnowledgeGraphClient } from '../api/client.js';

const server = new Server({
  name: 'knowledge-graph',
  version: '0.1.0',
});

// Register tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'search_concepts',
      description: 'Search for concepts using natural language',
      inputSchema: { /* ... */ },
    },
    {
      name: 'ingest_document',
      description: 'Ingest a document into the knowledge graph',
      inputSchema: { /* ... */ },
    },
    // ... more tools
  ],
}));

// Tool handlers use shared KnowledgeGraphClient
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const client = createClientFromEnv();

  if (request.params.name === 'ingest_document') {
    const result = await client.ingestFile(
      request.params.arguments.path,
      request.params.arguments.options
    );
    return { content: [{ type: 'text', text: JSON.stringify(result) }] };
  }
  // ... handle other tools
});
```

### Claude Desktop Configuration

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
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

## Type Safety & Error Handling

### Union Type Handling

**Problem**: TypeScript can't always narrow union types after runtime checks.

```typescript
// This fails type checking
const result = await client.ingestFile(path, request);
if ('duplicate' in result && result.duplicate) {
  console.log(result.existing_job_id);  // Error! Property might not exist
  return;
}
console.log(result.job_id);  // Error! Property might not exist
```

**Solution**: Explicit type assertions after narrowing checks.

```typescript
const result = await client.ingestFile(path, request);

// Check for duplicate
if ('duplicate' in result && result.duplicate) {
  const dupResult = result as DuplicateJobResponse;
  console.log(dupResult.existing_job_id);  // ✓ OK
  console.log(dupResult.message);
  return;
}

// Type narrowed to JobSubmitResponse
const submitResult = result as JobSubmitResponse;
console.log(submitResult.job_id);  // ✓ OK
```

### Error Handling

```typescript
try {
  const result = await client.ingestFile(path, request);
  // ... handle result
} catch (error: any) {
  console.error(chalk.red('✗ Ingestion failed'));
  console.error(chalk.red(
    error.response?.data?.detail || error.message
  ));
  process.exit(1);
}
```

## Build & Development

### TypeScript Configuration

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "resolveJsonModule": true
  }
}
```

### Package Scripts

```json
{
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "type-check": "tsc --noEmit",
    "clean": "rm -rf dist"
  }
}
```

### Dependencies

**Core**:
- `commander` - CLI framework
- `axios` - HTTP client
- `form-data` - File uploads

**UX**:
- `chalk` - Colored output
- `ora` - Progress spinners

**Future (MCP)**:
- `@modelcontextprotocol/sdk` - MCP protocol implementation

## Consequences

### Positive

1. **Code Reuse**: Types and API client shared between CLI and MCP
2. **Type Safety**: TypeScript types match FastAPI Pydantic models
3. **Single Source of Truth**: API changes propagate automatically
4. **Proven Pattern**: Following Anthropic's established approach
5. **Incremental Implementation**: Phase 1 (CLI) works without Phase 2 (MCP)
6. **Easy Migration**: Legacy Python CLI can be deprecated without breaking workflows

### Negative

1. **Build Step Required**: TypeScript compilation needed before running
2. **Node.js Dependency**: Adds runtime requirement beyond Python
3. **Complexity**: More sophisticated than simple bash script wrapper

### Mitigations

- **Wrapper Script**: `scripts/kg-cli.sh` handles build verification and execution
- **Clear Docs**: README.md documents all installation options
- **Gradual Adoption**: Legacy Python CLI remains in `scripts/` during transition

## Migration Path

### From Legacy Python CLI

**Old**:
```bash
python cli.py search "query"
python cli.py ontology list
```

**New**:
```bash
kg search "query"       # Not yet implemented (Phase 3)
kg ontology list        # Not yet implemented (Phase 3)
kg jobs list            # ✓ Phase 1 complete
kg ingest file doc.txt  # ✓ Phase 1 complete
```

**Status**:
- Phase 1 (Complete): Ingestion and job management only
- Phase 2 (Future): MCP server mode
- Phase 3 (Future): Full graph query commands (`search`, `details`, `related`, etc.)

### Deprecation Plan

1. **Phase 1**: CLI supports ingestion + jobs (current)
2. **Phase 2**: Add MCP server mode
3. **Phase 3**: Add remaining graph query commands
4. **Phase 4**: Deprecate `scripts/cli.py`, update all docs to use `kg` command

## Related ADRs

- **ADR-011**: Project Structure (why client/ is separate from src/)
- **ADR-012**: API Server Architecture (what this client connects to)

## References

- Anthropic MCP SDK: https://github.com/anthropics/modelcontextprotocol
- Commander.js: https://github.com/tj/commander.js
- TypeScript Handbook: https://www.typescriptlang.org/docs/

---

**Last Updated:** 2025-10-06
**Next Review:** Before Phase 2 MCP implementation
