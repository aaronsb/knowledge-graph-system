---
status: Accepted
date: 2025-10-06
deciders:
  - Development Team
---

# ADR-013: Unified TypeScript Client (CLI + MCP Server)

## Overview

Building software interfaces often leads to duplication. You create a command-line tool, then realize you need an MCP server for Claude integration, and suddenly you're maintaining two codebases with the same API calls, the same type definitions, and the same bug fixes needed in both places.

This ADR takes a different approach, inspired by how Anthropic builds their tools: one TypeScript codebase that can run in multiple modes. When you run `kg search`, you get a CLI. When Claude Desktop starts the MCP server, it gets the same underlying client code but wrapped in MCP protocol. Same API logic, same types, same error handling—just different interfaces.

The payoff is simple: change the API client once, both interfaces work. Add a new feature, it's available everywhere. Fix a bug, it's fixed everywhere. Instead of maintaining separate CLI and MCP codebases, we maintain one unified client that adapts its interface based on how it's launched.

---

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
    // MCP server mode
    import('./mcp/server').then(startMcpServer);
} else {
    // CLI mode
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
│   ├── cli/                  # CLI mode
│   │   ├── commands.ts       # Command registration
│   │   ├── search.ts         # Search commands
│   │   ├── concept.ts        # Concept commands
│   │   ├── ontology.ts       # Ontology commands
│   │   └── job.ts            # Job management commands
│   └── mcp/                  # MCP server mode
│       ├── server.ts         # MCP server implementation
│       └── formatters.ts     # Rich output formatters
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

## CLI Implementation

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

## MCP Server Implementation

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

### MCP Tool Organization (Context Budget Optimization)

**Problem**: Initial MCP server exposed 22 individual tools, consuming significant context budget in Claude Desktop conversations. Many tools performed similar operations with different parameters (e.g., `list_ontologies`, `get_ontology_info`, `get_ontology_files`, `delete_ontology`).

**Solution**: Consolidate tools using action parameters, mirroring the `kg` CLI command tree structure.

**Tool Consolidation (22 → 6 tools, 73% reduction)**:

```typescript
// Core exploration tools (high frequency, keep separate)
1. search
   - query, limit, min_similarity, offset
   - Primary entry point for graph exploration

2. concept
   - action: "details" | "related" | "connect"
   - Consolidates: get_concept_details, find_related_concepts,
                   find_connection, find_connection_by_search

// Grouped management tools (mirror CLI structure)
3. ontology
   - action: "list" | "info" | "files" | "delete"
   - Consolidates: list_ontologies, get_ontology_info,
                   get_ontology_files, delete_ontology

4. job
   - action: "status" | "list" | "approve" | "cancel"
   - Consolidates: get_job_status, list_jobs, approve_job, cancel_job

5. ingest
   - type: "text" (extensible to "file", "url")
   - Core content ingestion

6. source
   - action: "image" (ADR-057 image retrieval)
   - Retrieves original source images for verification
```

**MCP Resources** (5 resources for status/health queries):

Status and health information moved to MCP resources for on-demand querying with fresh data:

```typescript
1. database/stats      - Concept counts, relationship counts, ontology stats
2. database/info       - PostgreSQL version, Apache AGE extension details
3. database/health     - Database connection status, graph availability
4. system/status       - Job scheduler status, resource usage
5. api/health          - API server health and timestamp
```

**Resources vs Tools**: Resources are queried on-demand for fresh data and don't consume tool budget in Claude's context. Perfect for status/health information that changes frequently.

**Rich Output Preserved**: All formatters (`formatSearchResults`, `formatConceptDetails`, `formatConnectionPaths`, etc.) remain unchanged. Tools still return:
- Grounding strength scores
- Complete evidence chains
- Relationship types and paths
- Sample quotes with source locations
- Image indicators for visual verification

**Design Principle**: Reduce tool COUNT, not information QUALITY. The consolidation is purely organizational - using action parameters instead of separate tools. All the context-rich details stay intact.

**Example Tool Definition**:
```typescript
{
  name: 'concept',
  description: 'Work with concepts: get details, find related, or discover connections',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['details', 'related', 'connect'],
        description: 'Operation to perform'
      },
      concept_id: {
        type: 'string',
        description: 'Concept ID (for details, related)'
      },
      from_id: {
        type: 'string',
        description: 'Starting concept (for connect with exact IDs)'
      },
      to_id: {
        type: 'string',
        description: 'Target concept (for connect with exact IDs)'
      },
      from_query: {
        type: 'string',
        description: 'Starting phrase (for connect with semantic search)'
      },
      to_query: {
        type: 'string',
        description: 'Target phrase (for connect with semantic search)'
      },
      connection_mode: {
        type: 'string',
        enum: ['exact', 'semantic'],
        description: 'Connection mode: exact IDs or semantic phrases'
      },
      max_depth: {
        type: 'number',
        description: 'Max depth for related, max hops for connect'
      }
    },
    required: ['action']
  }
}
```

**CLI Alignment**: Tool structure mirrors `kg` CLI commands:
- `kg search` → `search` tool
- `kg concept details` → `concept` tool (action: "details")
- `kg ontology list` → `ontology` tool (action: "list")
- `kg job status` → `job` tool (action: "status")

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

**MCP**:
- `@modelcontextprotocol/sdk` - MCP protocol implementation

## Consequences

### Positive

1. **Code Reuse**: Types and API client shared between CLI and MCP server
2. **Type Safety**: TypeScript types match FastAPI Pydantic models
3. **Single Source of Truth**: API changes propagate automatically
4. **Proven Pattern**: Following Anthropic's established MCP SDK approach
5. **Context Efficiency**: Consolidated MCP tools (73% reduction) preserve conversation budget
6. **CLI Alignment**: Tool structure mirrors `kg` command tree for consistency

### Negative

1. **Build Step Required**: TypeScript compilation needed before running
2. **Node.js Dependency**: Adds runtime requirement beyond Python
3. **Complexity**: More sophisticated than simple bash script wrapper

### Mitigations

- **Build Step**: Handled transparently by `kg` wrapper script
- **Clear Docs**: README.md documents installation and usage
- **Type Safety**: TypeScript ensures correctness at compile time

## Related ADRs

- **ADR-011**: Project Structure (why client/ is separate from src/)
- **ADR-012**: API Server Architecture (what this client connects to)

## References

- Anthropic MCP SDK: https://github.com/anthropics/modelcontextprotocol
- Commander.js: https://github.com/tj/commander.js
- TypeScript Handbook: https://www.typescriptlang.org/docs/

---

**Last Updated:** 2025-11-08
