# ADR-039: Local Embedding Service with Hybrid Client/Server Architecture

**Status:** Proposed
**Date:** 2025-10-18
**Deciders:** System Architecture
**Related:** ADR-012 (API Server), ADR-013 (Unified Client), ADR-016 (Apache AGE), ADR-034 (Graph Visualization)

## Context

### Current State: OpenAI Embedding Dependency

The system currently depends on OpenAI's API for all embedding generation:

**Embedding Use Cases:**
1. **Concept extraction:** Generate embeddings for concepts during document ingestion
2. **Semantic search:** Generate query embeddings for similarity search
3. **Concept matching:** Find duplicate concepts via vector similarity (deduplication)
4. **Interactive search:** Real-time embedding generation as users type in visualization app

**Current Cost & Limitations:**
- Every search query = 1 OpenAI API call (~$0.0001 per call)
- Network latency: 100-300ms per embedding request
- API dependency: System unusable without internet or OpenAI access
- Privacy concerns: Query text sent to external service
- Rate limits: Potential throttling during high usage

### Research Findings

**Transformers.js Browser Embedding Support:**
- Nomic-embed-text-v1/v2 and BGE models fully supported since v2.15.0 (Feb 2024)
- Can generate embeddings directly in browser with no server required
- Models run via ONNX runtime in WebAssembly

**Model Specifications:**

| Model | Dimensions | Context | Size | Quantization |
|-------|-----------|---------|------|--------------|
| nomic-embed-text-v1.5 | 768 (64-768 via Matryoshka) | 8K tokens | ~275MB | Int8, Binary, GGUF |
| BGE-large-en-v1.5 | 1024 | 512 tokens | ~1.3GB | Int8, ONNX |
| OpenAI text-embedding-3-small | 1536 | 8K tokens | N/A (API) | N/A |

**Critical Finding: Quantization Compatibility**

Research confirms that quantized embeddings (4-bit, int8) CAN be compared with full-precision embeddings (float16, float32), but with accuracy degradation:

- **Int8 quantization:** <1% accuracy loss, 4x memory reduction
- **4-bit quantization:** 2-5% accuracy loss, 8x memory reduction
- **Cosine similarity shift:** Lower precision shifts similarity distribution leftward (lower scores)
- **Best practice:** Two-pass search system:
  1. **Fast candidate pruning:** Quantized scan (browser-side, 100+ QPS)
  2. **Accurate reranking:** Full-precision comparison (server-side, top-K only)

**Key Constraint: Embedding Model Consistency**

Embeddings from different models produce incompatible vector spaces. A system MUST use the same model for:
- All stored concept embeddings
- All query embeddings
- All similarity comparisons

Mixing models (e.g., storing nomic embeddings but querying with BGE) produces meaningless similarity scores.

## Decision

**Implement a hybrid local embedding architecture with a single, model-aware API endpoint that abstracts provider selection while ensuring embedding consistency.**

### Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                    Embedding Configuration                    │
│                 (PostgreSQL embedding_config)                 │
│                                                               │
│  {                                                            │
│    provider: "local" | "openai",                              │
│    model: "nomic-embed-text-v1.5" | "text-embedding-3-small", │
│    dimensions: 768 | 1536,                                    │
│    precision: "float16" | "float32"                           │
│  }                                                            │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ Config read at startup
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Server: /embedding/generate            │
│                                                             │
│  1. Read global embedding config                            │
│  2. Route to appropriate provider:                          │
│     - LocalEmbeddingProvider (sentence-transformers)        │
│     - OpenAIProvider (API call)                             │
│  3. Return embedding with metadata                          │
│                                                             │
│  Response: {                                                │
│    embedding: [0.123, -0.456, ...],                         │
│    model: "nomic-embed-text-v1.5",                          │
│    dimensions: 768,                                         │
│    provider: "local"                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
         ┌──────────▼──────────┐  ┌─────▼──────────┐
         │  OpenAI Provider    │  │ Local Provider │
         │  (Current behavior) │  │ (New)          │
         └─────────────────────┘  └────────────────┘
                    │                   │
                    │         ┌─────────┴───────────┐
                    │         │                     │
              API Request   Server                  │
              (internet)    (sentence-              │
                            transformers)           │
                                                    │
                                         ┌──────────▼──────────┐
                                         │ Browser (Optional)  │
                                         │ transformers.js     │
                                         │                     │
                                         │ Quantized model     │
                                         │ (int8 or int4)      │
                                         │                     │
                                         │ Two-pass search:    │
                                         │ 1. Local fast scan  │
                                         │ 2. Server rerank    │
                                         └─────────────────────┘
```

### Component Design

#### 1. Embedding Configuration Storage

**Database Table:** `embedding_config`

```sql
CREATE TABLE IF NOT EXISTS embedding_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- 'local' or 'openai'
    model VARCHAR(200) NOT NULL,    -- 'nomic-embed-text-v1.5', 'text-embedding-3-small'
    dimensions INTEGER NOT NULL,
    precision VARCHAR(20) NOT NULL, -- 'float16', 'float32'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    UNIQUE(active) WHERE active = TRUE  -- Only one active config
);
```

**Environment Variables:**

```bash
# .env
EMBEDDING_PROVIDER=local  # or 'openai'
EMBEDDING_MODEL=nomic-embed-text-v1.5  # or 'text-embedding-3-small'
EMBEDDING_PRECISION=float16
EMBEDDING_DIMENSIONS=768
```

#### 2. Single Embedding API Endpoint

**Endpoint:** `POST /embedding/generate`

```python
# Request
{
    "text": "recursive depth-first traversal algorithms",
    "client_hint": {
        "supports_local": true,
        "supports_quantized": true,
        "preferred_precision": "int8"  # optional hint from browser
    }
}

# Response
{
    "embedding": [0.123, -0.456, 0.789, ...],  # 768 or 1536 dimensions
    "metadata": {
        "provider": "local",
        "model": "nomic-embed-text-v1.5",
        "dimensions": 768,
        "precision": "float16",
        "server_config_id": 42  # For consistency validation
    }
}
```

**Endpoint:** `GET /embedding/config`

Returns current embedding configuration so clients know what model to use:

```python
# Response
{
    "provider": "local",
    "model": "nomic-embed-text-v1.5",
    "dimensions": 768,
    "precision": "float16",
    "supports_browser": true,  # transformers.js compatible
    "quantized_variants": ["int8", "int4"],  # Available for browser
    "config_id": 42
}
```

#### 3. LocalEmbeddingProvider Implementation

**File:** `src/api/lib/ai_providers.py`

```python
class LocalEmbeddingProvider(AIProvider):
    """
    Local embedding generation using sentence-transformers.
    Supports nomic-embed-text and BGE models.
    """

    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

    def generate_embedding(self, text: str, precision: str = "float16") -> List[float]:
        """Generate embedding locally using sentence-transformers."""
        embedding = self.model.encode(text, normalize_embeddings=True)

        if precision == "float16":
            embedding = embedding.astype(np.float16)

        return embedding.tolist()

    def get_dimensions(self) -> int:
        """Return embedding dimensions for this model."""
        return self.model.get_sentence_embedding_dimension()
```

#### 4. Browser-Side Embeddings (Optional Enhancement)

**File:** `viz-app/src/lib/embeddings.ts`

```typescript
import { pipeline } from '@xenova/transformers';

class BrowserEmbeddingService {
  private model: any = null;
  private serverConfig: EmbeddingConfig | null = null;

  async initialize() {
    // Fetch server config to ensure model consistency
    this.serverConfig = await fetchEmbeddingConfig();

    // Only load browser model if server uses compatible local model
    if (this.serverConfig.supports_browser) {
      try {
        // Load quantized version of server's model
        this.model = await pipeline('feature-extraction',
          `nomic-ai/${this.serverConfig.model}`,
          { quantized: true }  // Uses int8 quantization
        );
      } catch (error) {
        console.warn('Browser embedding failed, falling back to server:', error);
        this.model = null;
      }
    }
  }

  async generateEmbedding(text: string): Promise<number[]> {
    // Try browser-side first (fast)
    if (this.model) {
      const output = await this.model(text, { pooling: 'mean', normalize: true });
      return Array.from(output.data);
    }

    // Fallback to server (always works)
    return await fetchServerEmbedding(text);
  }

  async twoPassSearch(query: string, candidates: Concept[]): Promise<Concept[]> {
    // Pass 1: Fast local scan with quantized embeddings
    const queryEmbedding = await this.generateEmbedding(query);
    const topK = this.localCosineSimilarity(queryEmbedding, candidates)
                     .sort((a, b) => b.score - a.score)
                     .slice(0, 20);  // Top 20 candidates

    // Pass 2: Server-side rerank with full precision
    return await fetchServerRerank(query, topK);
  }
}
```

**Client Behavior Matrix:**

| Server Config | Browser Capability | Client Behavior |
|--------------|-------------------|-----------------|
| OpenAI | Any | Always use `/embedding/generate` API (current behavior) |
| Local (nomic) | Supports transformers.js | Two-pass: Browser quantized scan → Server rerank |
| Local (nomic) | Limited resources | Fall back to server-only |
| Local (nomic) | No browser support | Server-only (like OpenAI) |

### 5. Migration Strategy

**Leverage Existing Tool:** The system already has an embedding migration command:

```bash
kg embedding migrate --model nomic-embed-text-v1.5
```

**Migration Steps:**
1. Install sentence-transformers in API server
2. Set `EMBEDDING_PROVIDER=local` in `.env`
3. Restart API server (new config applied)
4. Run migration to re-embed all existing concepts
5. Verify consistency with test queries

**Migration is One-Way Per Model:**
- Switching from OpenAI → nomic requires full re-embedding (incompatible spaces)
- Switching from nomic → BGE requires full re-embedding (incompatible spaces)
- Once migrated, ALL clients must use the same model

### 6. Model Recommendation

**Recommended for Most Use Cases: nomic-embed-text-v1.5**

| Criterion | nomic-embed-text-v1.5 | BGE-large-en-v1.5 | OpenAI text-embedding-3-small |
|-----------|----------------------|-------------------|------------------------------|
| Dimensions | 768 (flexible 64-768) | 1024 | 1536 |
| Context | 8K tokens | 512 tokens | 8K tokens |
| Model Size | ~275MB | ~1.3GB | N/A (API) |
| Browser Support | ✅ Excellent | ✅ Good (large) | ❌ API only |
| Cost | Free (local) | Free (local) | $0.02 / 1M tokens |
| Latency | <50ms (local) | <100ms (local) | 100-300ms (API) |
| Privacy | ✅ Fully local | ✅ Fully local | ❌ External API |
| Quantization | Int8, Int4, Binary | Int8 | N/A |

**Why nomic-embed-text-v1.5:**
- Smaller model = faster loading in browser
- 8K context matches our chunking strategy (1000 words ~= 1500 tokens)
- Matryoshka learning allows dimension flexibility (future optimization)
- Strong transformers.js support
- Proven performance on MTEB benchmark

## Consequences

### Positive

1. **Cost Elimination:** Zero ongoing costs for embeddings (no OpenAI API calls)
2. **Reduced Latency:** Local generation: 10-50ms vs OpenAI API: 100-300ms
3. **Privacy:** All embeddings generated locally, no query text sent externally
4. **Offline Capability:** System works without internet access
5. **Browser Performance:** Two-pass search enables <100ms interactive search
6. **Consistency Guarantee:** Single `/embedding/config` endpoint ensures model alignment
7. **Provider Flexibility:** Easy to switch between local and OpenAI via config
8. **No API Rate Limits:** Unlimited embedding generation

### Negative

1. **Initial Setup Complexity:** sentence-transformers adds ~2GB model downloads
2. **Memory Overhead:** Model loaded in API server (~300MB-1.3GB RAM)
3. **Migration Required:** Existing OpenAI embeddings incompatible with local models
4. **Browser Bundle Size:** Quantized model adds ~100MB to viz app (lazy loaded)
5. **Quantization Trade-off:** Browser search slightly less accurate than server (2-5% degradation)

### Neutral

1. **Embedding Quality:** Nomic and BGE comparable to OpenAI text-embedding-3-small on benchmarks
2. **Configuration Complexity:** Single global config enforces consistency but reduces flexibility
3. **Two Codepaths:** Must maintain both OpenAI and local provider implementations
4. **Model Updates:** sentence-transformers models can be updated independently of code

## Alternatives Considered

### Alternative 1: Client-Only Embeddings (No Server Abstraction)

**Approach:** Each client generates embeddings with its own model choice.

**Rejected Because:**
- Incompatible vector spaces break similarity search
- No way to enforce model consistency across clients
- Database would contain mixed embeddings (unusable)

### Alternative 2: Multiple Embedding Endpoints (Per-Model)

**Approach:** Separate endpoints for each model: `/embedding/openai`, `/embedding/nomic`, `/embedding/bge`

**Rejected Because:**
- Increases complexity for clients (must choose endpoint)
- Doesn't enforce consistency (clients could use wrong endpoint)
- Harder to switch models system-wide
- More API surface area to maintain

### Alternative 3: Dual-Precision Storage (Both Full and Quantized)

**Approach:** Store both float32 and int8 embeddings in database.

**Rejected Because:**
- Doubles storage requirements (~2x database size)
- Adds complexity to ingestion pipeline
- Quantization can be done on-the-fly with minimal overhead
- Not necessary for two-pass search (quantize at query time)

### Alternative 4: Pgvector for Similarity Search (Future Enhancement)

**Approach:** Use pgvector extension for indexed vector similarity instead of full-scan numpy.

**Deferred to Future ADR:**
- Decision point determined by actual usage patterns and scale (not speculation)
- Requires schema changes (vector column type)
- Needs index tuning (HNSW, IVFFlat parameters)
- ADR-038 documents full-scan as "genuinely unusual" architectural choice
- Migration to pgvector should be its own decision when/if scale warrants it
- Compatible with this ADR (provider abstraction unchanged)

## Configuration Update Strategy (Worker Recycling)

**Challenge:** sentence-transformers models are loaded into memory (300MB-1.3GB). Changing embedding configuration requires model reload. How to apply changes without extended downtime?

### Phase 1: Manual API Restart (MVP - Current Implementation)

**Approach:**
- Embedding config stored in `kg_api.embedding_config` table
- API reads config from database at startup
- Configuration changes via `PUT /admin/embedding/config`
- Changes require manual API server restart to apply

**Workflow:**
```bash
# Update config via API
curl -X PUT http://localhost:8000/admin/embedding/config \
  -d '{"model_name": "BAAI/bge-large-en-v1.5", "num_threads": 8}'

# Restart API to apply
./scripts/stop-api.sh && ./scripts/start-api.sh
```

**Characteristics:**
- ✅ Simple implementation
- ✅ No risk of memory leaks
- ✅ Clean process state after restart
- ⚠️ ~2-5 second downtime during restart
- ⚠️ In-flight requests dropped

**When to use:** Single-instance deployments, infrequent config changes

### Phase 2: Hot Reload with Signal Handling (Future Enhancement)

**Approach:**
- Signal handling: `SIGHUP` or `POST /admin/embedding/config/reload` triggers config reload
- Graceful model swap in running process
- No process restart required

**Implementation Strategy:**
```python
async def reload_model(new_config: dict):
    """
    Hot reload model without process restart.

    Process:
    1. Load new model in parallel (brief 2x memory spike)
    2. Atomic swap of model reference
    3. Allow in-flight requests to finish with old model (5s grace period)
    4. Explicit cleanup: del old_model, gc.collect()
    5. Log reload time
    """
    logger.info(f"🔄 Hot reloading model: {new_config['model_name']}")
    start = time.time()

    # Load new model (2x memory temporarily)
    new_model = SentenceTransformer(new_config['model_name'])

    # Atomic swap
    old_model = self.model
    self.model = new_model
    self.model_name = new_config['model_name']

    # Grace period for in-flight requests
    await asyncio.sleep(5)

    # Explicit cleanup
    del old_model
    gc.collect()

    elapsed = time.time() - start
    logger.info(f"✅ Model reloaded in {elapsed:.2f}s")
```

**Workflow:**
```bash
# Update config and reload (single operation)
curl -X POST http://localhost:8000/admin/embedding/config/reload \
  -d '{"model_name": "BAAI/bge-large-en-v1.5", "num_threads": 8}'

# API responds with reload status
{
  "status": "reloading",
  "estimated_time_seconds": 5,
  "old_model": "nomic-ai/nomic-embed-text-v1.5",
  "new_model": "BAAI/bge-large-en-v1.5"
}
```

**Characteristics:**
- ✅ Zero downtime (in-flight requests complete)
- ✅ Fast reload (~2-5 seconds)
- ✅ No external tools required
- ⚠️ Temporary 2x memory usage during reload
- ⚠️ Risk of memory leaks if model not properly released
- ⚠️ Requires testing to verify garbage collection

**When to use:** Single-instance deployments with uptime requirements

### Phase 3: Multi-Worker Rolling Restart (Future - Production Scale)

**Approach:**
- Process pool with multiple workers (e.g., gunicorn with 4-8 workers)
- Rolling restart: reload one worker at a time
- Load balancer routes traffic to healthy workers
- True zero downtime

**Implementation Strategy:**
```bash
# Supervisor manages multiple workers
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# Rolling restart command (gunicorn built-in)
kill -HUP <gunicorn-pid>  # Gracefully reload all workers
```

**Reload Process:**
1. Worker 1: Reload model, rejoin pool
2. Worker 2: Reload model while 1,3,4 serve traffic
3. Worker 3: Reload model while 1,2,4 serve traffic
4. Worker 4: Reload model while 1,2,3 serve traffic

**Characteristics:**
- ✅ True zero downtime
- ✅ No memory spike (workers reload sequentially)
- ✅ Production-grade reliability
- ✅ Built-in gunicorn support
- ⚠️ More complex deployment architecture
- ⚠️ Requires load balancer or proxy
- ⚠️ 4-8x memory overhead (multiple workers)

**When to use:** Multi-user production deployments, high availability requirements

### Decision: Start with Phase 1, Add Phase 2 if Hot Reload Performs Well

**Rationale:**
- Phase 1 is simple and sufficient for most use cases
- Phase 2 can be added later if hot reload proves stable
- Phase 3 only needed at significant scale (>100 concurrent users)
- Discover actual reload performance before committing to complexity

**Metrics to track:**
- Model load time: `time to load model into memory`
- Memory cleanup: `RAM freed after old model deletion`
- Request impact: `number of requests affected during reload`

## Implementation Checklist

**Phase 1: Server-Side Local Embeddings (Core Functionality)**
- [ ] Add sentence-transformers to requirements.txt
- [ ] Create `embedding_config` database table
- [ ] Implement `LocalEmbeddingProvider` class
- [ ] Add `POST /embedding/generate` endpoint
- [ ] Add `GET /embedding/config` endpoint
- [ ] Update `.env.example` with embedding variables
- [ ] Test local embedding generation
- [ ] Update API documentation

**Phase 2: Embedding Configuration Management**
- [ ] Add config validation on API startup
- [ ] Implement config consistency checks
- [ ] Add config to health check endpoint
- [ ] Update admin module with config commands

**Phase 3: Migration Tool Extension**
- [ ] Extend `kg embedding migrate` to support local models
- [ ] Add progress tracking for re-embedding
- [ ] Add validation checks (embedding dimensions)
- [ ] Update CLI documentation

**Phase 4: Browser-Side Embeddings (Optional Enhancement)**
- [ ] Add transformers.js to viz-app dependencies
- [ ] Implement BrowserEmbeddingService
- [ ] Add two-pass search to visualization app
- [ ] Add resource detection and fallback logic
- [ ] Performance testing and optimization

## Related ADRs

- **ADR-012 (API Server):** Embedding endpoint extends FastAPI server architecture
- **ADR-013 (Unified Client):** kg CLI extended with embedding migration commands
- **ADR-016 (Apache AGE):** Embedding config stored in PostgreSQL alongside graph
- **ADR-030 (Concept Deduplication):** Quality tests must account for model changes
- **ADR-034 (Graph Visualization):** Browser embeddings enhance interactive search
- **ADR-038 (O(n) Full-Scan Search):** Local embeddings compatible with current search architecture

**Future Consideration:**
- **ADR-0XX (Pgvector Migration):** Indexed vector search to replace full-scan similarity

## References

**Research Sources:**
- Transformers.js v2.15.0 release notes (Feb 2024)
- Nomic AI: "Nomic Embed Text v2" blog post
- HuggingFace: "Binary and Scalar Embedding Quantization" blog
- OpenCypher specification (ISO/IEC 39075:2024)
- MTEB benchmark (Massive Text Embedding Benchmark)

**Model Documentation:**
- https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
- https://huggingface.co/BAAI/bge-large-en-v1.5
- https://platform.openai.com/docs/guides/embeddings

**Quantization Research:**
- "4bit-Quantization in Vector-Embedding for RAG" (arXiv:2501.10534v1)
- Zilliz Vector Database: Int8 Quantization Effects on Sentence Transformers

---

**Last Updated:** 2025-10-18
