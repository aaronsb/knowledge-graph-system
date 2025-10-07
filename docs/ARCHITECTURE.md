# Knowledge Graph System Architecture

## Overview

The Knowledge Graph System transforms linear documents into interconnected concept graphs, enabling semantic exploration beyond sequential reading.

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Document Ingestion                         │
│  .txt/.pdf files → API Server → Background Jobs → Neo4j      │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Server (Phase 1)                    │
│  • REST endpoints (ingest, jobs)                              │
│  • Job queue (in-memory + SQLite)                             │
│  • Content deduplication (SHA-256)                            │
│  • Placeholder auth (X-Client-ID, X-API-Key)                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                Neo4j Graph Database                           │
│  • Concepts (nodes with vector embeddings)                    │
│  • Instances (evidence quotes)                                │
│  • Sources (document paragraphs)                              │
│  • Relationships (IMPLIES, SUPPORTS, CONTRADICTS, etc.)       │
└──────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────────┐
                    │                   │
         ┌──────────▼─────┐  ┌──────────▼─────────┐
         │  TypeScript    │  │  MCP Server        │
         │  CLI (kg)      │  │  (Phase 2)         │
         │  • Ingest      │  │  • Claude Desktop  │
         │  • Jobs        │  │  • Same codebase   │
         └────────────────┘  └────────────────────┘
```

## Core Components

### 1. API Server Layer (`src/api/`)

**FastAPI REST Server** (Phase 1):
- **Routes**: Ingestion (`POST /ingest`), job management (`GET/POST /jobs/*`)
- **Services**: Job queue (abstract interface), content hasher (deduplication)
- **Workers**: Background ingestion processing with progress updates
- **Models**: Pydantic request/response schemas matching TypeScript client
- **Middleware**: Placeholder authentication (X-Client-ID, X-API-Key headers)

**Job Queue Pattern**:
```python
# Abstract interface for Phase 1 → Phase 2 migration
class JobQueue(ABC):
    def enqueue(job_type, job_data) -> job_id
    def get_job(job_id) -> JobStatus
    def update_job(job_id, updates) -> None

# Phase 1: InMemoryJobQueue (SQLite persistence)
# Phase 2: RedisJobQueue (distributed workers)
```

**Content Deduplication**:
- SHA-256 hash of document content + ontology name
- Prevents expensive re-ingestion ($50-100 per document)
- Returns existing job results if already completed
- Force flag to override when intentional

See [ADR-012](ADR-012-api-server-architecture.md) for detailed design.

### 2. AI Provider Layer (`src/ingest/ai_providers.py`)

Modular abstraction for LLM providers:

**OpenAI Provider:**
- Extraction: GPT-4o, GPT-4o-mini, o1-preview, o1-mini
- Embeddings: text-embedding-3-small, text-embedding-3-large

**Anthropic Provider:**
- Extraction: Claude Sonnet 4.5, Claude 3.5 Sonnet, Claude 3 Opus
- Embeddings: Delegates to OpenAI (Anthropic doesn't provide embeddings)

### 3. Ingestion Pipeline (`src/ingest/`)

**Components:**
- `parser.py` - Document parsing (text, PDF, DOCX)
- `llm_extractor.py` - LLM-based concept extraction
- `neo4j_client.py` - Graph database operations
- `ingest_chunked.py` - Main orchestration with chunking

**Flow:**
1. **API Submission**: Client POSTs file → API returns job_id
2. **Background Processing**: Worker pulls job from queue
3. **Parse & Chunk**: Document → semantic chunks with overlap
4. **For each chunk**:
   - Query recent concepts from graph (context)
   - Extract concepts using LLM
   - Generate embeddings
   - Match against existing concepts (vector similarity > 0.85)
   - Upsert to Neo4j (create/update nodes and relationships)
   - Update job progress (percent, concepts created)
5. **Complete**: Worker writes final stats to job result

### 4. Client Layer (`client/`)

**Unified TypeScript Client** (CLI + MCP in one codebase):

**Shared Components**:
- `src/types/` - TypeScript interfaces matching FastAPI Pydantic models
- `src/api/client.ts` - HTTP client wrapping REST API endpoints
- Configuration: Environment variables (`KG_API_URL`, `KG_CLIENT_ID`)

**CLI Mode** (Phase 1 - Complete):
- Commands: `kg health`, `kg ingest file/text`, `kg jobs status/list/cancel`
- User experience: Color-coded output, progress spinners, duplicate detection
- Installation: Wrapper script (`scripts/kg-cli.sh`), direct node, or npm link

**MCP Server Mode** (Phase 2 - Future):
- Entry point detects `MCP_SERVER_MODE=true` environment variable
- Runs as MCP server for Claude Desktop/Code
- Tools use same API client as CLI
- Claude Desktop config: Node.js + environment variables

See [ADR-013](ADR-013-unified-typescript-client.md) for detailed design.

### 5. Graph Database (Neo4j)

**Node Types:**

```cypher
// Concept - Core knowledge unit
(:Concept {
  concept_id: "linear-scanning-system",
  label: "Linear scanning system",
  embedding: [0.123, ...],  // 1536 dims
  search_terms: ["linear thinking", "sequential processing"]
})

// Source - Document location
(:Source {
  source_id: "watts-doc-1-para-4",
  document: "Watts Doc 1",
  paragraph: 4,
  full_text: "..."
})

// Instance - Evidence quote
(:Instance {
  instance_id: "uuid",
  quote: "exact verbatim quote"
})
```

**Relationships:**
- `APPEARS_IN` - Concept → Source
- `EVIDENCED_BY` - Concept → Instance
- `FROM_SOURCE` - Instance → Source
- `IMPLIES` - Concept → Concept (logical implication)
- `CONTRADICTS` - Concept → Concept
- `SUPPORTS` - Concept → Concept
- `PART_OF` - Concept → Concept

### 6. Legacy Query Interfaces

**Legacy Python CLI (`scripts/cli.py`):**
- Direct Neo4j database access
- Color-coded output
- Commands: search, details, related, connect, ontology (list/info/files/delete), database (stats/info/health)
- **Status**: Retained during TypeScript client migration

**Legacy MCP Server (`mcp-server/`):**
- Direct Neo4j database access
- Claude Desktop integration
- Tools: search_concepts, get_concept_details, find_related_concepts, etc.
- **Status**: Will migrate to unified TypeScript client (Phase 2)

## Data Flow

### Ingestion Flow (Current Architecture)

```
Client (kg CLI)
  ↓ POST /ingest (file + ontology)
API Server
  ├→ Calculate SHA-256 hash
  ├→ Check for duplicate (hash + ontology)
  │   ├→ Duplicate found: return existing job result
  │   └→ No duplicate: continue
  ├→ Create job in SQLite
  ├→ Enqueue to in-memory queue
  ├→ Return job_id immediately
  └→ Background worker starts

Background Worker
  ↓ Parse & chunk document
Chunks with context overlap
  ↓ for each chunk
  ├→ Query recent concepts from graph (context for LLM)
  ├→ Extract concepts (LLM)
  │   ├→ concepts: [{id, label, search_terms}]
  │   ├→ instances: [{concept_id, quote}]
  │   └→ relationships: [{from, to, type, confidence}]
  │
  ├→ Generate embeddings (OpenAI)
  │
  ├→ Match existing concepts (vector search)
  │   ├→ similarity > 0.85: use existing
  │   └→ else: create new
  │
  ├→ Upsert to Neo4j
  │   ├→ CREATE/UPDATE concepts
  │   ├→ CREATE instances
  │   └→ CREATE relationships
  │
  └→ Update job progress (SQLite)
      └→ percent, chunks_processed, concepts_created

Client polls GET /jobs/{job_id}
  ↓ every 2 seconds
Job Status Response
  ├→ status: queued | processing | completed | failed
  ├→ progress: {percent, chunks_processed, concepts_created}
  └→ result: {stats, cost} (if completed)
```

### Query Flow

```
User Query
  ↓
Generate embedding
  ↓
Vector similarity search
  ↓
MATCH concepts WHERE similarity > threshold
  ↓
OPTIONAL MATCH related concepts
  ↓
Return structured results
```

## Configuration

### Environment Variables

**API Server** (`.env`):
```bash
# AI Provider Selection
AI_PROVIDER=openai  # or "anthropic"

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_EXTRACTION_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Anthropic (optional)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Authentication (Phase 1: disabled)
AUTH_ENABLED=false
AUTH_REQUIRE_CLIENT_ID=false
AUTH_API_KEYS=  # Comma-separated keys for Phase 2
```

**TypeScript Client**:
```bash
# API connection
KG_API_URL=http://localhost:8000
KG_CLIENT_ID=my-client
KG_API_KEY=  # Optional, for Phase 2

# Mode selection (CLI vs MCP)
MCP_SERVER_MODE=false  # or "true" for MCP server mode
```

## Concept Matching Algorithm

Multi-stage matching to prevent duplicates:

**Stage 1: Exact ID Match**
- LLM predicted existing concept_id → use it
- Confidence: 100%

**Stage 2: Vector Similarity (Primary)**
- Embed: `label + search_terms`
- Cosine similarity search
- Threshold > 0.85 → match
- Confidence: similarity score

**Stage 3: Create New**
- No match found
- Generate new concept_id (kebab-case)

## Scalability Considerations

### Phase 1 (Current)
- **API Server**: Single FastAPI instance with BackgroundTasks
- **Job Queue**: In-memory dict + SQLite persistence
- **Database**: Single Neo4j instance
- **Limitations**: No distributed workers, no multi-instance API

### Phase 2 (Planned)
- **Job Queue**: Redis-based distributed queue
- **Workers**: Separate worker processes (can scale horizontally)
- **API Server**: Multiple instances behind load balancer
- **Real-time Updates**: WebSocket/SSE for job progress
- **Authentication**: Full API key validation and rate limiting

### Future Enhancements
- Neo4j cluster for HA
- Dedicated vector database (Pinecone, Weaviate)
- Incremental updates (avoid re-processing)
- Caching layer for query results

## Security

### API Keys
- Stored in `.env` (gitignored)
- Never committed to version control
- Validated on startup

### Database
- Neo4j auth required (no anonymous access)
- Local development: simple password
- Production: strong auth + TLS

## Testing Strategy

### Unit Tests
- AI provider abstraction
- Concept matching logic
- Graph queries

### Integration Tests
- End-to-end ingestion
- MCP tool functionality
- CLI commands

### Manual Testing
- Use sample Watts documents
- Verify concept extraction quality
- Test relationship accuracy
