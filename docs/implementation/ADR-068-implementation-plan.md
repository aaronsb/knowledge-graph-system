# ADR-068 Source Text Embeddings - Implementation Plan

**Status:** Planning Complete - Ready for Implementation
**Branch:** `feature/adr-068-source-embeddings`
**Started:** 2025-11-27
**Target:** Phase 1 completion

---

## Quick Links

- [ADR-068](../architecture/ADR-068-source-text-embeddings.md)
- [Feature Branch](https://github.com/aaronsb/knowledge-graph-system/tree/feature/adr-068-source-embeddings)

---

## Design Decisions Summary

### 1. ✅ content_hash: Add Field, No Backfill

```sql
-- Migration 068 adds field as NULL
ALTER TABLE Source ADD COLUMN content_hash TEXT;

-- Existing Sources: NULL
-- New Sources: Computed during embedding generation
-- Backfill: Via existing regenerate embeddings worker (at leisure)
```

**Rationale:**
- Avoid expensive migration (computing hash for all existing Sources)
- Leverage existing worker pattern (cures non-existent embeddings)
- Operators can regenerate at their leisure
- Non-blocking rollout

### 2. ✅ No Separate Configuration Table

```python
# Use existing kg_api.embedding_config
embedding_config = load_active_embedding_config()
{
    "embedding_dimensions": 768,  # MUST match concepts!
    "model_name": "nomic-ai/nomic-embed-text-v1.5",
    "provider": "local" | "openai",
    ...
}
```

**Why:** Source embeddings must be comparable to concept embeddings. Using different dimensions would break cosine similarity.

### 3. ✅ Chunk Size: 500 Characters (~100 words)

**Typical scenario:**
- Source node = 500-1500 words (from ingestion)
- Embedding chunks = 500 chars each (~100 words)
- Result: **1-2 embeddings per Source**

**Large document example:**
- Document → 10 Source nodes (ingestion chunks)
- 100 concepts extracted → reference those 10 Sources
- Each Source → 1-2 embedding chunks
- Total: **10-20 embeddings for entire document**

**Rationale:**
- Balances granularity vs overhead
- Chunking overlap from ingestion ensures continuity
- Most Sources will have 1-2 embedding chunks

### 4. ✅ Always Enabled

- No enable/disable flags
- First-class system feature
- Runs automatically for all ingestions
- Simplified architecture (no conditional logic)

### 5. ✅ Leverage Existing Worker

- Regenerate embeddings worker handles backfill
- Cures NULL content_hash on-demand
- Operators control regeneration timing
- No expensive migration required

---

## Architecture Overview

### Two-Level Chunking

```
Document (100KB)
    ↓ Ingestion chunking (smart chunker with overlap)
    ├─ Source node 1 (500-1500 words) ────→ 1-2 embedding chunks
    ├─ Source node 2 (500-1500 words) ────→ 1-2 embedding chunks
    ├─ Source node 3 (500-1500 words) ────→ 1-2 embedding chunks
    ...
    └─ Source node N (500-1500 words) ────→ 1-2 embedding chunks
              ↓
    Concepts extracted (reference Sources)
```

**Two-level chunking:**
1. **Ingestion chunking** (existing): Document → Source nodes (500-1500 words each)
2. **Embedding chunking** (this ADR): Source.full_text → Embedding chunks (~100-120 words each)

### Database Schema

```sql
-- Source node (canonical truth)
(:Source {
    source_id TEXT,
    full_text TEXT,           -- 500-1500 words from ingestion
    content_hash TEXT,        -- SHA256 of full_text (NULL for existing)
    document TEXT,
    paragraph INT,
    ...
})

-- Separate embeddings table (referential integrity)
CREATE TABLE kg_api.source_embeddings (
    embedding_id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,

    -- Chunk tracking
    chunk_index INT NOT NULL,         -- 0-based chunk number
    chunk_strategy TEXT NOT NULL,     -- 'sentence', 'paragraph'

    -- Offset in Source.full_text (character positions)
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    chunk_text TEXT NOT NULL,         -- Actual chunk (for verification)

    -- Referential integrity (double hash verification)
    chunk_hash TEXT NOT NULL,         -- SHA256 of chunk_text
    source_hash TEXT NOT NULL,        -- SHA256 of Source.full_text

    -- Embedding data (use active embedding_config dimensions)
    embedding BYTEA NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INT NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, chunk_index, chunk_strategy)
);

CREATE INDEX idx_source_embeddings_source ON kg_api.source_embeddings(source_id);
CREATE INDEX idx_source_embeddings_source_hash ON kg_api.source_embeddings(source_hash);
```

### Hash Verification Flow

```python
# At embedding generation
source_text = source['full_text']
source_hash = sha256(source_text)      # Hash of full source

for chunk in chunks:
    chunk_hash = sha256(chunk.text)     # Hash of this chunk

    db.insert_source_embedding(
        source_id=source_id,
        chunk_text=chunk.text,
        chunk_hash=chunk_hash,          # ✓ Verifies chunk integrity
        source_hash=source_hash,        # ✓ Verifies source hasn't changed
        start_offset=chunk.start,
        end_offset=chunk.end,
        embedding=generate_embedding(chunk.text)
    )

# At query time
current_source_hash = sha256(source['full_text'])
for embedding in embeddings:
    if embedding.source_hash != current_source_hash:
        # Source text changed - embedding is stale
        flag_for_regeneration(embedding)

    # Verify chunk extraction
    extracted_chunk = source_text[embedding.start_offset:embedding.end_offset]
    if sha256(extracted_chunk) != embedding.chunk_hash:
        # Corruption detected!
        raise IntegrityError("Chunk hash mismatch")
```

### Performance Estimates

**Storage:**
- 768-dim float16 embedding = 1.5KB per chunk
- Typical: 1-2 chunks per Source
- Avg 1.5 chunks per Source = 2.25KB per Source
- 1M sources = ~2.25GB embedding storage
- Plus ~500 bytes metadata per chunk = ~750MB
- **Total: ~3GB for 1M sources** (acceptable for PostgreSQL)

**Generation:**
- Local embeddings (Nomic): ~5-10ms per chunk (CPU fallback: ~20-50ms)
- Typical: 1-2 chunks per Source = ~10-20ms per Source
- OpenAI API: ~50-100ms per batch (rate limited)
- Async processing prevents ingestion blocking
- Hash calculation: <1ms (negligible)

**Regeneration:**
- Leverage existing regenerate embeddings worker
- Worker cures non-existent embeddings (NULL content_hash)
- 1M sources @ 15ms = ~4 hours (local, 1-2 chunks per Source)
- Progress tracking via job system
- Resumable on failure

---

## Implementation Phases

### Phase 1: Foundation (First PR) ← **WE ARE HERE**

**Goal:** Schema ready, worker skeleton, no breaking changes

#### Tasks:

- [ ] **Migration 068**
  - [ ] Create `kg_api.source_embeddings` table
  - [ ] Add `Source.content_hash` field (TEXT, NULL for existing)
  - [ ] Create indexes (source_id, source_hash)
  - [ ] Test migration on local database

- [ ] **Hash Utilities** (`api/api/lib/hash_utils.py`)
  - [ ] Implement `sha256_text(text: str) -> str`
  - [ ] Implement `verify_source_hash(source_text, expected_hash) -> bool`
  - [ ] Implement `verify_chunk_hash(chunk_text, expected_hash) -> bool`
  - [ ] Add unit tests for hash utilities

- [ ] **Sentence Chunker** (`api/api/lib/source_chunker.py`)
  - [ ] Define `SourceChunk` dataclass (text, start_offset, end_offset, index)
  - [ ] Implement `chunk_by_sentence(text, max_chars=500) -> List[SourceChunk]`
  - [ ] Handle edge cases (empty text, single sentence, no punctuation)
  - [ ] Add unit tests for chunker

- [ ] **Worker Skeleton** (`api/api/workers/source_embedding_worker.py`)
  - [ ] Create `run_source_embedding_worker(job_data, job_id, job_queue)`
  - [ ] Query active `embedding_config` for dimensions
  - [ ] Return mock result (no actual embedding yet)
  - [ ] Add to job type registry

- [ ] **Job Type Registration**
  - [ ] Add "source_embedding" to job queue types
  - [ ] Update job submission logic
  - [ ] Test job creation and status tracking

**Deliverables:**
- Migration 068 applied (schema ready)
- Hash utilities available
- Sentence chunker working
- Worker registered (skeleton only)
- All unit tests passing

**Review Points:**
- Can we create the tables successfully?
- Are indexes correct?
- Do hash utilities work correctly?
- Does sentence chunker produce correct offsets?

---

### Phase 2: Generation (Second PR)

**Goal:** Full worker implementation, embeddings generated

#### Tasks:

- [ ] **Complete Worker Implementation**
  - [ ] Fetch Source node by source_id
  - [ ] Calculate source_hash
  - [ ] Chunk using sentence strategy
  - [ ] Generate embeddings via EmbeddingWorker
  - [ ] Calculate chunk_hash for each chunk
  - [ ] Insert into source_embeddings table
  - [ ] Update Source.content_hash field

- [ ] **Integration with Ingestion**
  - [ ] Add to `api/api/workers/ingestion_worker.py`
  - [ ] Dispatch job after Source creation
  - [ ] Always enabled (no conditional logic)
  - [ ] Test end-to-end ingestion

- [ ] **Testing**
  - [ ] Test with small ontology (5-10 documents)
  - [ ] Verify chunks created correctly
  - [ ] Verify offsets match source text
  - [ ] Verify hashes match
  - [ ] Check embedding dimensions match config

**Deliverables:**
- Source embeddings generated during ingestion
- Chunks and offsets correct
- Hash verification working
- Integration tests passing

**Review Points:**
- Does ingestion still work correctly?
- Are embeddings generated with correct dimensions?
- Do offsets correctly map to source text?
- Are hashes verifying properly?

---

### Phase 3: Query Integration (Third PR)

**Goal:** Source similarity search working

#### Tasks:

- [ ] **Search Endpoint** (`api/api/routes/queries.py`)
  - [ ] Create `POST /queries/sources/search`
  - [ ] Accept: query_text, ontology, limit
  - [ ] Generate query embedding
  - [ ] Cosine similarity search in source_embeddings
  - [ ] Verify source_hash (detect stale embeddings)
  - [ ] Return chunks with offsets

- [ ] **Response Format**
  - [ ] Include matched_chunk text
  - [ ] Include start_offset, end_offset
  - [ ] Include full_source_text for context
  - [ ] Include similarity score
  - [ ] Include is_stale flag

- [ ] **Testing**
  - [ ] Test search returns relevant results
  - [ ] Test offset highlighting works
  - [ ] Test stale embedding detection
  - [ ] Integration tests

**Deliverables:**
- Source similarity search endpoint working
- Offset-based highlighting
- Stale embedding detection
- API documentation updated

**Review Points:**
- Does search return relevant results?
- Are offsets correct for highlighting?
- Is stale detection working?

---

### Phase 4: Regeneration & Optimization (Fourth PR)

**Goal:** Admin tools, performance tuning

#### Tasks:

- [ ] **Extend Regenerate Embeddings Worker**
  - [ ] Add support for `--type source`
  - [ ] Support `--ontology` flag
  - [ ] Support `--all` flag
  - [ ] Progress tracking
  - [ ] Cure NULL content_hash

- [ ] **Optimization**
  - [ ] Batch embedding generation
  - [ ] Performance benchmarking
  - [ ] Tune chunk size if needed

- [ ] **MCP Tools**
  - [ ] Add source search to MCP server
  - [ ] Test with Claude Desktop

**Deliverables:**
- Regenerate embeddings tool working
- Performance optimized
- MCP integration complete

---

### Phase 5: Advanced Features (Future)

- Hybrid search (concept + source combined)
- Multiple strategies per Source
- Cross-document source similarity
- Semantic chunking strategy

---

## Current Todo List

### Active Tasks

- [x] ~~Review and finalize implementation order for ADR-068~~
- [x] ~~Update ADR-068 with finalized decisions~~
- [ ] **Review finalized ADR-068 and implementation plan** ← YOU ARE HERE
  - Read through this document
  - Verify design decisions are correct
  - Approve Phase 1 scope
  - Give go-ahead to start implementation

### Phase 1 Tasks (Pending Approval)

- [ ] Create migration 068: source_embeddings table + Source.content_hash (NULL)
- [ ] Implement hash utilities (sha256_text, verify_hash)
- [ ] Implement sentence chunking with offset tracking (500 chars)
- [ ] Implement SourceEmbeddingWorker skeleton
- [ ] Query active embedding_config for dimensions
- [ ] Add job type registration for source_embedding

### Phase 2 Tasks (Future)

- [ ] Complete SourceEmbeddingWorker with chunking + hash verification
- [ ] Add source embedding generation to ingestion (always enabled)

### Phase 3 Tasks (Future)

- [ ] Create POST /queries/sources/search endpoint
- [ ] Add stale embedding detection
- [ ] Implement offset-based highlighting

---

## Questions Before Implementation

### 1. ADR Content
**Question:** Does the finalized ADR capture all the design decisions correctly?

**Review checklist:**
- [ ] Two-level chunking explained clearly
- [ ] content_hash strategy (NULL for existing) documented
- [ ] No separate config table (use embedding_config) explained
- [ ] Always-enabled rationale documented
- [ ] Existing worker leverage explained
- [ ] Performance estimates reasonable

### 2. Implementation Scope
**Question:** Should we proceed with Phase 1 (foundation), or adjust the scope?

**Phase 1 includes:**
- Migration only (schema changes)
- Hash utilities
- Sentence chunker
- Worker skeleton (no actual embedding yet)
- Job type registration

**Alternative scopes:**
- Smaller: Migration only
- Larger: Include Phase 2 (full worker + ingestion)

### 3. Migration Timing
**Question:** The migration is non-destructive (adds fields, no backfill). Safe to run on production?

**Migration safety:**
- Adds table: `kg_api.source_embeddings` (new, no data loss risk)
- Adds field: `Source.content_hash` (NULL default, no data loss risk)
- Creates indexes (read-only operation)
- No data backfill (fast migration)
- Backward compatible (existing code works with NULL fields)

### 4. Anything Else?
**Question:** Any other concerns or changes before we start implementing?

---

## File Structure (To Be Created)

```
api/api/lib/
├── hash_utils.py              # NEW: SHA256 utilities
└── source_chunker.py          # NEW: Sentence chunking with offsets

api/api/workers/
└── source_embedding_worker.py # NEW: Source embedding generation

schema/migrations/
└── 068_source_embeddings.sql  # NEW: Schema changes

tests/
├── test_hash_utils.py         # NEW: Hash utility tests
├── test_source_chunker.py     # NEW: Chunker tests
└── test_source_embedding_worker.py  # NEW: Worker tests
```

---

## Risk Assessment

### Low Risk ✅
- Migration (adds fields only, no backfill)
- Hash utilities (pure functions, no side effects)
- Sentence chunker (pure functions, isolated)
- Worker skeleton (no-op, just registration)

### Medium Risk ⚠️
- Integration with ingestion (touches critical path)
- Embedding generation (depends on external services)
- Query endpoint (new API surface)

### Mitigation Strategies
- Phase 1 has no integration with ingestion (low risk)
- Worker skeleton allows testing without actual embedding
- Unit tests for all pure functions
- Integration tests for end-to-end flows
- Feature branch allows safe testing before merge

---

## Success Criteria

### Phase 1 (Foundation)
- [x] Migration 068 applied successfully
- [x] Hash utilities working correctly
- [x] Sentence chunker produces correct offsets
- [x] Worker skeleton registered and testable
- [x] All unit tests passing
- [x] No breaking changes to existing functionality

### Phase 2 (Generation)
- [x] Source embeddings generated during ingestion
- [x] Chunks and offsets correct
- [x] Hash verification working
- [x] Embedding dimensions match config
- [x] Integration tests passing

### Phase 3 (Query)
- [x] Source search endpoint working
- [x] Relevant results returned
- [x] Offset highlighting correct
- [x] Stale detection working

### Phase 4 (Regeneration)
- [x] Regenerate embeddings tool working
- [x] Performance acceptable
- [x] MCP integration complete

---

## Notes and Decisions Log

### 2025-11-27: Design Finalized
- Decided on NULL content_hash (no backfill)
- Confirmed use of existing embedding_config
- Confirmed 500 char chunks (~100 words)
- Confirmed always-enabled (no flags)
- Confirmed leverage existing regenerate worker

### Next Decision Point
- After Phase 1 review: Proceed to Phase 2?
- After Phase 2 review: Adjust chunk size based on testing?

---

## Approval Checklist

Before proceeding to Phase 1 implementation:

- [ ] ADR-068 reviewed and approved
- [ ] Design decisions understood and agreed upon
- [ ] Phase 1 scope approved
- [ ] Risk assessment reviewed
- [ ] Success criteria clear
- [ ] Questions answered
- [ ] Ready to start implementing

---

**Status:** ⏸️ Paused for Review
**Next Step:** Get approval to proceed with Phase 1 implementation

**Last Updated:** 2025-11-27
