# 02 - System Overview

**Part:** I - Foundations
**Reading Time:** ~12 minutes
**Prerequisites:** [Section 01 - What Is a Knowledge Graph](01-what-is-a-knowledge-graph.md)

---

## Architecture

The system has four main components:

1. **API Server** - FastAPI REST server that handles requests and manages jobs
2. **Graph Database** - Apache AGE (PostgreSQL graph extension) stores concepts and relationships
3. **Client** - TypeScript CLI (`kg` command) and MCP server for Claude Desktop
4. **LLM Providers** - OpenAI, Anthropic, or local Ollama models for extraction

```
┌─────────────┐
│   kg CLI    │  User runs commands
└──────┬──────┘
       │ HTTP
       ↓
┌─────────────────────────────────┐
│      FastAPI REST Server        │  Manages jobs, coordinates work
│  • Job queue (SQLite)           │
│  • Background workers           │
│  • Content deduplication        │
└────────┬────────────────────────┘
         │
    ┌────┴────┬──────────────┐
    │         │              │
    ↓         ↓              ↓
┌────────┐ ┌──────┐  ┌──────────────┐
│ OpenAI │ │ AGE  │  │   Anthropic  │
│   or   │ │(PostgreSQL)│    or      │
│ Ollama │ │Graph │  │   Ollama     │
└────────┘ └──────┘  └──────────────┘
Embeddings  Storage   Extraction
```

## Component Details

### API Server (FastAPI)

The API server is a Python FastAPI application that handles all requests.

**Responsibilities:**
- Receives ingestion requests from clients
- Creates jobs and tracks their status
- Runs background workers to process documents
- Prevents duplicate ingestion via content hashing
- Manages authentication (when enabled)

**Key Files:**
- `src/api/main.py` - Entry point and route registration
- `src/api/routes/` - REST endpoints (ingest, jobs, queries, admin)
- `src/api/lib/ingestion.py` - Document processing logic

The server runs on `localhost:8000` by default.

### Graph Database (Apache AGE)

Apache AGE is a PostgreSQL extension that adds graph database capabilities. It stores the actual knowledge graph.

**Node Types:**

**Concept** - A core idea extracted from text
```sql
(:Concept {
  concept_id: "linear-thinking-pattern",
  label: "Linear Thinking Pattern",
  embedding: [0.123, -0.456, ...],  -- 1536 dimensions
  search_terms: ["linear thinking", "sequential processing"]
})
```

**Source** - A document paragraph
```sql
(:Source {
  source_id: "watts-lecture-01-para-03",
  document: "Alan Watts - Tao of Philosophy - 01",
  paragraph: 3,
  full_text: "The complete paragraph text..."
})
```

**Instance** - An evidence quote
```sql
(:Instance {
  instance_id: "uuid-here",
  quote: "The exact verbatim quote from the source"
})
```

**Relationship Types:**

Structural (connect concepts to evidence):
- `APPEARS_IN` - Concept appeared in this Source
- `EVIDENCED_BY` - Concept supported by this Instance quote
- `FROM_SOURCE` - Instance came from this Source

Semantic (connect concepts to concepts):
- `IMPLIES`, `SUPPORTS`, `CONTRADICTS` - Logical relationships
- `CAUSES`, `ENABLES`, `PREVENTS` - Causal relationships
- `PART_OF`, `CONTAINS`, `SUBSET_OF` - Structural relationships
- 30 types total (see [Section 04](04-understanding-concepts-and-relationships.md) for the full taxonomy)

Each semantic relationship has a `confidence` score (0.0-1.0) from the LLM.

### TypeScript Client

A unified TypeScript codebase that works as both a CLI tool and an MCP server.

**CLI Mode** (`kg` command):
```bash
kg health                    # Check API connection
kg ingest file doc.txt       # Ingest a document
kg jobs status <job-id>      # Check job progress
kg search query "concept"    # Search for concepts
```

**MCP Server Mode** (for Claude Desktop):
The same codebase runs as an MCP server when `MCP_SERVER_MODE=true`. Claude Desktop can then use tools to query the graph during conversations.

**Key Files:**
- `client/src/api/client.ts` - HTTP client for REST API
- `client/src/cli/` - Command implementations
- `client/src/types/` - TypeScript types matching API schemas

### LLM Providers

The system uses LLMs for two tasks:

**Extraction** - Reading text and identifying concepts/relationships
- OpenAI: GPT-4o, GPT-4o-mini
- Anthropic: Claude Sonnet 4, Claude 3.5 Sonnet
- Ollama: Local models (Mistral, Llama, Qwen, etc.)

**Embeddings** - Converting text to vector representations
- OpenAI: text-embedding-3-small (default)
- Local: sentence-transformers (nomic-embed-text-v1.5)

Providers are swappable via configuration. See [Section 08](08-choosing-your-ai-provider.md) for comparison and [Section 10](10-ai-extraction-configuration.md) for setup.

---

## Data Flow

### Ingestion Process

When you run `kg ingest file document.txt --ontology "My Docs"`:

**1. Client Sends Request**
```
POST /ingest
{
  "content": "file contents...",
  "filename": "document.txt",
  "ontology": "My Docs"
}
```

**2. API Server Creates Job**
- Calculates SHA-256 hash of content + ontology
- Checks if this exact content was already ingested
  - If yes: returns existing job result (prevents duplicate work)
  - If no: creates new job
- Stores job in SQLite database
- Returns job ID immediately
- Starts background worker

**3. Background Worker Processes Document**

The worker runs these steps:

**a. Parse and Chunk**
- Split document into semantic chunks (~1000 words each)
- Chunks overlap by ~200 words for context continuity
- Preserve paragraph boundaries when possible

**b. For Each Chunk**

Extract concepts:
```python
# Send chunk to LLM with structured prompt
response = llm.extract_concepts(chunk_text, recent_concepts)

# LLM returns JSON:
{
  "concepts": [
    {
      "id": "linear-thinking",
      "label": "Linear Thinking",
      "search_terms": ["sequential", "linear processing"]
    }
  ],
  "instances": [
    {
      "concept_id": "linear-thinking",
      "quote": "exact quote from text"
    }
  ],
  "relationships": [
    {
      "from": "linear-thinking",
      "to": "pattern-recognition",
      "type": "SUPPORTS",
      "confidence": 0.9
    }
  ]
}
```

Generate embeddings:
```python
# For each concept
embedding = embedding_model.encode(
    f"{concept.label} {' '.join(concept.search_terms)}"
)
# Returns 1536-dimensional vector
```

Match against existing concepts:
```python
# Search graph for similar concepts
similar = search_similar_concepts(embedding, threshold=0.85)

if similar:
    concept_id = similar.concept_id  # Merge with existing
else:
    concept_id = generate_new_id()   # Create new concept
```

Upsert to graph:
```sql
-- Create or update concept
MERGE (c:Concept {concept_id: $id})
ON CREATE SET c.label = $label, c.embedding = $embedding
ON MATCH SET c.search_terms = c.search_terms + $new_terms

-- Create instance
CREATE (i:Instance {instance_id: $instance_id, quote: $quote})

-- Link to source
MATCH (s:Source {source_id: $source_id})
CREATE (i)-[:FROM_SOURCE]->(s)

-- Link to concept
MATCH (c:Concept {concept_id: $concept_id})
CREATE (c)-[:EVIDENCED_BY]->(i)
```

Update job progress:
```python
job.update({
    "progress": {
        "percent": (chunks_done / total_chunks) * 100,
        "chunks_processed": chunks_done,
        "concepts_created": concept_count
    }
})
```

**4. Client Polls for Status**
```bash
GET /jobs/{job_id}
# Returns current status every 2 seconds
{
  "status": "processing",
  "progress": {
    "percent": 45,
    "chunks_processed": 9,
    "chunks_total": 20,
    "concepts_created": 156
  }
}
```

**5. Job Completes**
```json
{
  "status": "completed",
  "result": {
    "concepts_created": 342,
    "relationships_created": 289,
    "chunks_processed": 20,
    "cost_estimate": "$0.45",
    "duration_seconds": 127
  }
}
```

### Query Process

When you run `kg search query "linear thinking"`:

**1. Client Sends Request**
```
POST /queries/search
{
  "query": "linear thinking",
  "limit": 10
}
```

**2. API Server Processes**
```python
# Generate embedding for query
query_embedding = embedding_model.encode("linear thinking")

# Search graph via openCypher
results = db.execute("""
    MATCH (c:Concept)
    WHERE vector_similarity(c.embedding, $query_embedding) > 0.7
    OPTIONAL MATCH (c)-[r]->(related:Concept)
    RETURN c, collect(related) as related_concepts
    ORDER BY vector_similarity(c.embedding, $query_embedding) DESC
    LIMIT $limit
""", {
    "query_embedding": query_embedding,
    "limit": 10
})
```

**3. Returns Results**
```json
{
  "concepts": [
    {
      "concept_id": "linear-thinking-pattern",
      "label": "Linear Thinking Pattern",
      "similarity": 0.94,
      "search_terms": ["linear", "sequential"],
      "related_concepts": [
        {"label": "Pattern Recognition", "relationship": "SUPPORTS"}
      ]
    }
  ]
}
```

---

## Configuration

The system uses environment variables for configuration.

**API Server** (`.env` file):
```bash
# AI Provider
AI_PROVIDER=openai          # or "anthropic" or "ollama"
OPENAI_API_KEY=sk-...       # Your API key
OPENAI_EXTRACTION_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_graph
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Apache AGE
AGE_GRAPH_NAME=knowledge_graph
```

**Client** (`.env` file or environment):
```bash
KG_API_URL=http://localhost:8000
KG_CLIENT_ID=my-client-id
```

See [Section 10](10-ai-extraction-configuration.md) for detailed provider configuration.

---

## Concept Matching

The system prevents duplicate concepts using a multi-stage matching process.

**Stage 1: Exact ID Match**

If the LLM predicts an existing `concept_id` (from recent concepts context), use it directly.

**Stage 2: Vector Similarity**

Embed the new concept:
```python
embedding = encode(f"{label} {search_terms}")
```

Search for similar concepts:
```python
similar = find_similar(embedding, threshold=0.85)
```

If similarity > 0.85: merge with existing concept (add new evidence)
If similarity ≤ 0.85: create new concept

**Stage 3: Create New**

Generate new `concept_id` from label:
```python
concept_id = to_kebab_case(label)  # "Linear Thinking" → "linear-thinking"
```

This prevents the same concept from appearing multiple times with slightly different wording.

---

## Job Queue System

The API server uses a job queue to handle long-running ingestion tasks.

**Current Implementation** (Phase 1):
- In-memory job queue (Python dict)
- SQLite persistence (survives server restarts)
- Background tasks via FastAPI `BackgroundTasks`
- Single API server instance

**How it works:**
```python
# Client submits job
job_id = api.create_job(job_data)

# Background worker picks it up
worker.process_job(job_id)

# Updates progress as it goes
job.update_progress(percent=45, chunks=9)

# Client polls for status
status = api.get_job_status(job_id)
```

**Planned** (Phase 2):
- Redis-based distributed queue
- Separate worker processes
- Multiple API server instances
- WebSocket/SSE for real-time updates

---

## Deduplication

The system avoids re-processing identical content.

**Content Hashing:**
```python
content_hash = sha256(file_content + ontology_name)
```

**Check Before Processing:**
```python
existing_job = db.find_job_by_hash(content_hash)

if existing_job and existing_job.status == "completed":
    return existing_job.result  # Return cached result
else:
    create_new_job()  # Process fresh
```

**Force Re-ingestion:**
```bash
kg ingest file doc.txt --force  # Bypass deduplication
```

This prevents accidentally spending $2.00 to re-ingest a document you already processed.

---

## Performance Characteristics

**Ingestion Speed:**
- ~1-2 chunks per minute (LLM calls are the bottleneck)
- 10-page document (~20 chunks): 10-20 minutes
- Cost: $0.10-$0.50 per 10 pages (depending on provider)

**Query Speed:**
- Vector search: 50-200ms (depends on graph size)
- Graph traversal: 10-50ms per hop
- REST API overhead: ~10-20ms

**Storage:**
- 1000 concepts: ~5MB in PostgreSQL
- Embeddings dominate (1536 floats × 4 bytes = 6KB per concept)
- Text quotes add ~1-2KB per concept

---

## Limitations

**Single Server:** Current architecture runs on one API server. Can't distribute work across multiple machines yet.

**Synchronous Processing:** Each chunk processed sequentially. Parallel processing would be faster but more complex.

**Vector Search:** Full scan of all concepts. Dedicated vector databases (Pinecone, Weaviate) would be faster at scale.

**No Caching:** Query results aren't cached. Same query hits the database every time.

These limitations are acceptable for personal/small-team use. Future phases will address scaling.

---

## What's Next

Now that you understand the architecture, you can:

- **[Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md)**: Actually run the system and ingest your first document
- **[Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md)**: Deep dive into the data model
- **[Section 05 - The Extraction Process](05-the-extraction-process.md)**: How documents become graphs

Or jump ahead to configuration:
- **[Section 10 - AI Extraction Configuration](10-ai-extraction-configuration.md)**: Set up your LLM provider
- **[Section 12 - Local LLM Inference](12-local-llm-inference-with-ollama.md)**: Run everything locally with Ollama

---

← [Previous: What Is a Knowledge Graph](01-what-is-a-knowledge-graph.md) | [Documentation Index](README.md) | [Next: Quick Start →](03-quick-start-your-first-knowledge-graph.md)
