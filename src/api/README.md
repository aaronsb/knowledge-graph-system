# Knowledge Graph API - Phase 1

Async REST API for document ingestion with job queue and deduplication.

## Features

✅ **Async Job Processing**
- Non-blocking document ingestion
- Background worker pool
- Progress tracking

✅ **Content Deduplication**
- SHA-256 hashing prevents re-ingestion
- Duplicate detection per ontology
- Force override option

✅ **Job Queue System**
- SQLite persistence (survives restarts)
- Job status polling
- Cancellation support (queued jobs only)

✅ **Clean Architecture**
- Abstract queue interface
- Easy migration to Redis (Phase 2)
- Reusable components

## Quick Start

### Start the API Server

```bash
# From project root
./scripts/start-api.sh

# Custom port
./scripts/start-api.sh 8080

# With hot reload (development)
./scripts/start-api.sh 8000 --reload
```

### API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **API info**: http://localhost:8000/
- **Health check**: http://localhost:8000/health

## Usage Examples

### 1. Submit Document for Ingestion

**Upload file:**
```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@mydocument.txt" \
  -F "ontology=My Ontology" \
  -F "target_words=1000" \
  -F "overlap_words=200"
```

**Response:**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "queued",
  "content_hash": "sha256:abc123...",
  "message": "Job queued for processing. Poll /jobs/{job_id} for status."
}
```

**Submit text directly:**
```bash
curl -X POST "http://localhost:8000/ingest/text" \
  -F "text=This is my document content..." \
  -F "ontology=My Ontology" \
  -F "filename=my_text.txt"
```

### 2. Poll Job Status

```bash
curl "http://localhost:8000/jobs/job_a1b2c3d4e5f6"
```

**Response (processing):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "job_type": "ingestion",
  "status": "processing",
  "progress": {
    "stage": "processing",
    "chunks_total": 45,
    "chunks_processed": 23,
    "percent": 51,
    "current_chunk": 23,
    "concepts_created": 89,
    "sources_created": 23
  },
  "created_at": "2025-10-06T20:00:00",
  "started_at": "2025-10-06T20:00:05"
}
```

**Response (completed):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "completed",
  "result": {
    "status": "completed",
    "stats": {
      "chunks_processed": 45,
      "sources_created": 45,
      "concepts_created": 127,
      "concepts_linked": 89,
      "instances_created": 201,
      "relationships_created": 234
    },
    "cost": {
      "extraction": "$2.34",
      "embeddings": "$0.12",
      "total": "$2.46",
      "extraction_model": "gpt-4o",
      "embedding_model": "text-embedding-3-small"
    },
    "ontology": "My Ontology",
    "filename": "mydocument.txt",
    "chunks_processed": 45
  },
  "created_at": "2025-10-06T20:00:00",
  "started_at": "2025-10-06T20:00:05",
  "completed_at": "2025-10-06T20:12:30"
}
```

### 3. Handle Duplicates

If you submit the same content twice:

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@mydocument.txt" \
  -F "ontology=My Ontology"
```

**Response:**
```json
{
  "duplicate": true,
  "existing_job_id": "job_a1b2c3d4e5f6",
  "status": "completed",
  "created_at": "2025-10-06T20:00:00",
  "completed_at": "2025-10-06T20:12:30",
  "result": { ... },
  "message": "This document was already ingested (job job_a1b2c3d4e5f6). Use force=true to re-ingest.",
  "use_force": "Set force=true to re-ingest"
}
```

**Force re-ingestion:**
```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@mydocument.txt" \
  -F "ontology=My Ontology" \
  -F "force=true"
```

### 4. List Recent Jobs

```bash
# All jobs (last 50)
curl "http://localhost:8000/jobs"

# Filter by status
curl "http://localhost:8000/jobs?status=completed&limit=10"
curl "http://localhost:8000/jobs?status=processing"
curl "http://localhost:8000/jobs?status=failed"
```

### 5. Cancel a Job

```bash
curl -X DELETE "http://localhost:8000/jobs/job_a1b2c3d4e5f6"
```

**Response:**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "cancelled": true,
  "message": "Job cancelled successfully"
}
```

**Note:** Phase 1 can only cancel queued jobs, not running ones.

## Architecture

```
POST /ingest
    ↓
[Content Hasher]  →  Check duplicate
    ↓ (if not duplicate)
[Job Queue]  →  Enqueue job_id
    ↓
[BackgroundTasks]  →  Execute async
    ↓
[Ingestion Worker]  →  Process chunks
    ↓
[Neo4j]  →  Store concepts
    ↓
[Job Queue]  →  Update progress
```

### Directory Structure

```
src/api/
├── main.py               # FastAPI app
├── routes/
│   ├── ingest.py        # POST /ingest, /ingest/text
│   └── jobs.py          # GET /jobs/{id}, etc.
├── services/
│   ├── job_queue.py     # Abstract queue + InMemory impl
│   └── content_hasher.py # Deduplication
├── workers/
│   └── ingestion_worker.py # Async ingestion
└── models/
    ├── job.py           # Pydantic schemas
    └── ingest.py        # Request/response models
```

### Data Files

- `data/jobs.db` - SQLite job metadata
- Persists across API restarts
- Stores job status, progress, results

## Configuration

Set environment variables in `.env`:

```bash
# Queue configuration
QUEUE_TYPE=inmemory  # Phase 1 only
JOB_DB_PATH=data/jobs.db

# AI provider (used by workers)
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_EXTRACTION_MODEL=gpt-4o

# Neo4j connection (required)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Phase 2 Migration Path

Phase 1 uses abstract `JobQueue` interface. To migrate to Redis:

1. Add `RedisJobQueue` class in `services/job_queue.py`
2. Set `QUEUE_TYPE=redis` in `.env`
3. Start Redis container
4. **Zero changes to routes or workers**

See `services/job_queue.py` for implementation details.

## Limitations (Phase 1)

❌ Cannot cancel running jobs (only queued)
❌ Single API instance (no horizontal scaling)
❌ Jobs lost if API crashes (SQLite has history but queue is in-memory)
❌ No authentication/authorization
❌ No rate limiting

**All addressed in Phase 2 with Redis Queue.**

## Testing

### Manual Testing

```bash
# Terminal 1: Start API
./scripts/start-api.sh 8000 --reload

# Terminal 2: Submit job
curl -X POST "http://localhost:8000/ingest/text" \
  -F "text=Linear thinking is a step-by-step process..." \
  -F "ontology=Test" \
  -F "filename=test.txt" \
  -F "target_words=500"

# Get job ID from response, then poll
curl "http://localhost:8000/jobs/job_XXXXX"
```

### Unit Tests (TODO)

```bash
# Future: pytest tests/api/
pytest tests/api/test_job_queue.py
pytest tests/api/test_deduplication.py
pytest tests/api/test_ingestion_worker.py
```

## Troubleshooting

**API won't start:**
- Check Neo4j is running: `docker ps | grep neo4j`
- Check port 8000 is free: `lsof -i :8000`
- Check logs for errors

**Jobs stay "queued" forever:**
- Check worker registration in startup logs
- Verify no exceptions in worker function
- Check Neo4j connection

**Duplicate detection not working:**
- Content hash is case-sensitive
- Whitespace differences = different hash
- Check `data/jobs.db` for existing entries

**High memory usage:**
- Phase 1 keeps active jobs in memory
- Completed jobs moved to SQLite
- Restart API to clear memory

## Next Steps

Ready for Phase 2? Add:
- ✅ Redis Queue (RQ) for persistence
- ✅ Multiple worker processes
- ✅ Job cancellation (running jobs)
- ✅ Retry logic
- ✅ Better monitoring
- ✅ Authentication

See main project docs for Phase 2 planning.
