---
status: Accepted
date: 2025-10-06
deciders:
  - Development Team
---

# ADR-012: API Server Architecture for Scalable Neo4j Access

## Overview

Imagine you're building a knowledge extraction system where users upload documents and AI processes them into a graph. At first, you might have each user's tool connect directly to the database. But what happens when someone accidentally uploads the same document twice? They'd pay for the expensive AI processing all over again. What if the processing takes 10 minutes? The user's tool would just sit there, frozen, waiting.

We needed something smarter sitting between users and the database - a middleman that could catch duplicates before wasting money, handle long-running work in the background, and keep track of what's happening. Think of it like a post office: you drop off your package (document), get a tracking number, and go about your day. The post office handles the actual delivery work and you can check the status anytime.

This decision introduces FastAPI as that intelligent middleman. It accepts document uploads, checks if we've seen them before, assigns them to background workers, and provides a way to track progress. The best part? All the complex logic for managing work lives in one place, making it much easier to add features like rate limiting or user accounts later.

---

## Context

The original architecture had MCP servers making direct database calls to Neo4j. This approach has scaling limitations:

1. **Connection Management**: Each MCP client requires separate Neo4j connection pool
2. **Multi-tenancy**: No isolation or tracking between different clients
3. **Async Operations**: Long-running ingestion blocks MCP tool responses
4. **Deduplication**: No protection against accidentally re-ingesting same documents (costly with LLMs)
5. **Observability**: Difficult to track job status and progress across clients

## Decision

Implement a **FastAPI server as an intermediary layer** between clients and Neo4j with:

### Phase 1 (Current Implementation)
- **REST API** for ingestion and job management
- **In-memory job queue** with SQLite persistence
- **Content-based deduplication** using SHA-256 hashing
- **Placeholder authentication** infrastructure
- **Background task processing** using FastAPI BackgroundTasks

### Phase 2 (Future)
- **Redis-based job queue** for distributed processing
- **WebSocket/SSE** for real-time progress updates
- **Full authentication** with API key validation
- **Cypher proxy endpoint** for complex graph queries
- **Rate limiting** and request validation

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  TypeScript  │────▶│  FastAPI     │────▶│    Neo4j     │
│  Client      │     │  Server      │     │   Database   │
│  (CLI/MCP)   │◀────│  (REST API)  │◀────│              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Job Queue   │
                     │  + Workers   │
                     └──────────────┘
```

### Directory Structure

```
src/
├── api/
│   ├── main.py                    # FastAPI application
│   ├── routes/
│   │   ├── ingest.py             # POST /ingest endpoints
│   │   ├── jobs.py               # Job management endpoints
│   │   └── health.py             # Health check
│   ├── services/
│   │   ├── job_queue.py          # Abstract JobQueue interface
│   │   └── content_hasher.py     # Deduplication service
│   ├── workers/
│   │   └── ingestion_worker.py   # Background ingestion processing
│   ├── models/
│   │   ├── requests.py           # Pydantic request models
│   │   └── responses.py          # Pydantic response models
│   └── middleware/
│       └── auth.py               # Authentication (placeholder)
└── ingest/                       # Existing ingestion pipeline
    ├── ingest_chunked.py
    ├── llm_extractor.py
    └── neo4j_client.py
```

## Key Design Patterns

### 1. Abstract Job Queue Interface

**Rationale**: Enable Phase 1 → Phase 2 migration without rewriting route handlers.

```python
class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, job_type: str, job_data: Dict) -> str:
        """Submit job to queue, return job_id"""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Retrieve job status and result"""
        pass
```

**Implementations**:
- `InMemoryJobQueue` (Phase 1): In-memory dict + SQLite persistence
- `RedisJobQueue` (Phase 2): Redis-backed with distributed workers

### 2. Content-Based Deduplication

**Problem**: Accidentally re-ingesting same document wastes $50-100 in LLM costs.

**Solution**: SHA-256 hash of document content + ontology name as composite key.

```python
# Before ingestion
content_hash = hasher.hash_content(file_bytes)
existing_job = hasher.check_duplicate(content_hash, ontology)

if existing_job and not force:
    return DuplicateJobResponse(
        duplicate=True,
        existing_job_id=existing_job['job_id'],
        status=existing_job['status'],
        result=existing_job['result']  # If completed
    )
```

**Features**:
- Detects duplicates across ingestion attempts
- Returns existing job results if already completed
- `--force` flag to override (intentional re-ingestion)
- Per-ontology tracking (same file, different ontology = allowed)

### 3. Async Job Processing

**Problem**: Document ingestion takes 2-10 minutes. Blocking API requests is unacceptable.

**Solution**: Submit → Poll pattern with progress updates.

```python
# Submit returns immediately
job_id = queue.enqueue("ingestion", job_data)
background_tasks.add_task(queue.execute_job, job_id)
return JobSubmitResponse(job_id=job_id)

# Client polls for status
GET /jobs/{job_id}
→ {
    "status": "processing",
    "progress": {
        "percent": 45,
        "chunks_processed": 23,
        "chunks_total": 50,
        "concepts_created": 127
    }
  }
```

**Benefits**:
- Non-blocking API responses
- Real-time progress tracking
- Job survives API restarts (SQLite persistence)
- Supports `--watch` mode in CLI

### 4. Placeholder Authentication

**Problem**: Don't lose sight of auth flow while building Phase 1.

**Solution**: Infrastructure in place, enforcement disabled.

```python
async def get_current_user(
    x_client_id: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
) -> dict:
    user_info = {
        "client_id": x_client_id or "anonymous",
        "authenticated": False  # Phase 1
    }

    if AuthConfig.is_enabled():  # env: AUTH_ENABLED=true
        # Phase 2: Validate x_api_key
        if x_api_key not in valid_keys:
            raise HTTPException(status_code=403)
        user_info["authenticated"] = True

    return user_info
```

**Environment Variables**:
- `AUTH_ENABLED=false` (Phase 1 default)
- `AUTH_REQUIRE_CLIENT_ID=false`
- `AUTH_API_KEYS=key1,key2,key3` (Phase 2)

**Job Tracking**:
- All jobs store `client_id` field
- Enables future per-client job filtering
- Foundation for multi-tenancy

## API Endpoints

### Ingestion

**POST /ingest**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.txt" \
  -F "ontology=Research Papers" \
  -F "force=false"
```

**Response (Success)**:
```json
{
  "job_id": "job_abc123",
  "status": "queued",
  "message": "Job submitted for processing"
}
```

**Response (Duplicate)**:
```json
{
  "duplicate": true,
  "existing_job_id": "job_xyz789",
  "status": "completed",
  "message": "Duplicate content detected for ontology 'Research Papers'",
  "use_force": "Use force=true to re-ingest",
  "result": {
    "stats": {
      "chunks_processed": 50,
      "concepts_created": 127
    }
  }
}
```

### Job Management

**GET /jobs/{job_id}**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "progress": {
    "stage": "processing",
    "percent": 45,
    "chunks_processed": 23,
    "chunks_total": 50,
    "concepts_created": 127
  },
  "created_at": "2025-10-06T10:30:00Z"
}
```

**GET /jobs**
```bash
# List all jobs
GET /jobs

# Filter by status
GET /jobs?status=completed&limit=10
```

**POST /jobs/{job_id}/cancel**
```json
{
  "job_id": "job_abc123",
  "status": "cancelled"
}
```

**POST /jobs/{job_id}/approve** (ADR-014)
```json
{
  "job_id": "job_abc123",
  "status": "approved",
  "message": "Job approved for processing"
}
```

### Admin & Scheduler (ADR-014)

**GET /admin/scheduler/status**
```json
{
  "running": true,
  "config": {
    "cleanup_interval": 3600,
    "approval_timeout": 24,
    "completed_retention": 48,
    "failed_retention": 168
  },
  "stats": {
    "jobs_by_status": {...}
  }
}
```

**POST /admin/scheduler/cleanup**
```json
{
  "success": true,
  "message": "Cleanup completed successfully"
}
```

## Consequences

### Positive

1. **Scalability**: API server can scale independently of Neo4j
2. **Multi-tenancy**: Client isolation via `client_id` tracking
3. **Cost Protection**: Deduplication prevents expensive re-ingestion mistakes
4. **Non-blocking**: Async job queue enables responsive API
5. **Observability**: Centralized job tracking and monitoring
6. **Migration Path**: Abstract interfaces enable Redis migration without route changes

### Negative

1. **Complexity**: Additional layer between clients and database
2. **Latency**: Extra network hop for all operations
3. **State Management**: Job queue requires persistence and cleanup
4. **Phase 1 Limitations**: In-memory queue doesn't support distributed workers

### Mitigations

- **Phase 1 Simplicity**: Use built-in FastAPI BackgroundTasks, SQLite persistence
- **Abstract Interfaces**: JobQueue abstraction enables future Redis migration
- **Comprehensive Docs**: Clear migration path from Phase 1 to Phase 2

## Implementation Notes

### Running the API Server

```bash
# Development
cd /home/aaron/Projects/ai/knowledge-graph-system
source venv/bin/activate
uvicorn api.app.main:app --reload --port 8000

# Production (future)
uvicorn api.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Job Queue Lifecycle

1. **Submit**: Client POSTs file/text → server returns `job_id`
2. **Enqueue**: Server writes job to SQLite, adds to in-memory dict
3. **Execute**: Background task calls `run_ingestion_worker()`
4. **Progress**: Worker updates job status in SQLite every chunk
5. **Complete**: Worker writes final result, marks status="completed"
6. **Retrieve**: Client polls `/jobs/{job_id}` until completion

### Database Schema (SQLite)

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    client_id TEXT,
    ontology TEXT,
    content_hash TEXT,
    created_at TEXT,
    updated_at TEXT,
    progress TEXT,  -- JSON
    result TEXT,    -- JSON
    error TEXT
);

CREATE INDEX idx_content_hash ON jobs(content_hash, ontology);
CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_client_id ON jobs(client_id);
```

## Related ADRs

- **ADR-011**: Project Structure (why code lives in `src/`)
- **ADR-013**: Unified TypeScript Client (CLI + MCP consumer of this API)
- **ADR-014**: Job Approval Workflow (pre-ingestion analysis and scheduler)

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- BackgroundTasks: https://fastapi.tiangulo.com/tutorial/background-tasks/
- Pydantic Models: https://docs.pydantic.dev/

---

**Last Updated:** 2025-10-07 (Added ADR-014 endpoints)
**Next Review:** Before Phase 2 Redis implementation
