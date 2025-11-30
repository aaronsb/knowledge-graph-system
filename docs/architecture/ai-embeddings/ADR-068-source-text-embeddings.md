# ADR-068: Source Text Embeddings for Grounding Truth Retrieval

**Status:** Accepted - Partially Implemented (Phase 1-3 complete, Phase 4 pending)
**Date:** 2025-11-27
**Updated:** 2025-11-28 (Phase 3 complete: Source search endpoint + CLI)
**Deciders:** System Architect
**Tags:** #embeddings #source-retrieval #async-processing #lcm

## Overview

Your knowledge graph has embeddings for concepts (the ideas extracted from documents) and embeddings for relationship types (SUPPORTS, CONTRADICTS, etc.), but here's what's missing: embeddings for the source documents themselves—the actual paragraphs and passages that concepts came from. This creates a blind spot. You can search for concepts semantically ("find concepts similar to 'recursive depth tracking'"), but you can't search the original text that way. You're forced to use keyword search, which misses semantic matches.

Think about the difference between these two questions: "Which concepts are related to performance optimization?" versus "Show me the original passages that discuss performance optimization." The first searches concept labels; the second searches the source text. Without source embeddings, you can only answer the first question semantically. For the second, you're stuck with keyword matching—"WHERE full_text LIKE '%performance%'"—which misses passages that discuss optimization without using that exact word.

This matters for RAG (Retrieval-Augmented Generation) workflows. When you want to answer a question using your knowledge graph, you need to retrieve relevant context—not just concept names, but the actual text that provides nuanced detail. Source embeddings enable this: generate an embedding for the user's question, find the most similar source passages, and feed that rich context to an LLM for generation. It's the difference between saying "there's a concept called 'caching strategies'" (shallow) versus showing the actual paragraph explaining different caching approaches (deep).

This ADR implements source text embeddings as a first-class system feature, stored in a separate table with chunk-level granularity and hash-based verification. Each source passage gets split into embedding chunks (around 100-120 words each, stored with character offsets for precise highlighting), and the system tracks which chunks came from which source using content hashes. This enables three new capabilities: semantic search over source passages, hybrid queries that blend concept matches with source matches, and complete RAG workflows that retrieve evidence-rich context for generation. The vision is a "Large Concept Model" where everything in the graph—concepts, sources, relationships, even images—participates in semantic search and retrieval.

---

## Context

### Current State

The system currently generates embeddings for:
- **Concepts**: Label + description + search terms (text embeddings)
- **Relationship Types**: Vocabulary embeddings for grounding calculations (ADR-044)
- **Images**: Visual embeddings (Nomic Vision v1.5, 768-dim, ADR-057)

However, **Source nodes** (the grounding truth documents) do NOT have embeddings:

```python
# From api/api/workers/ingestion_worker.py:294
text_embedding=None  # Will be generated during concept extraction
```

Source nodes contain:
- `full_text` - Raw paragraph/chunk text (potentially 500-1500 words)
- `document` - Ontology name
- `paragraph` - Chunk number
- `content_type` - "document" or "image"
- No embedding field for text similarity search

### The Problem

This creates a critical gap in retrieval capabilities:

1. **No Direct Source Search**: Cannot find similar source passages via embedding similarity
2. **Lost Context**: When a concept matches, we can't easily find related context from neighboring source text
3. **Incomplete RAG**: The system has concept embeddings but not the underlying evidence embeddings
4. **Search Mode Gap**:
   - ✅ Text search (full-text indexes on Source.full_text)
   - ✅ Concept search (embedding similarity on Concept.embedding)
   - ❌ Source passage search (no embedding on Source nodes)

### The Vision: Large Concept Model (LCM)

This ADR is a foundational piece toward a **Large Concept Model** architecture where ALL graph elements participate in semantic search:

**Current state (Concept-centric)**:
```
Text → Concepts → Embeddings → Graph
```

**Target state (LCM - Everything embedded)**:
```
Text → {Concepts, Sources, Edges} → Embeddings → Multi-modal Graph
             ↓                              ↓
      Recursive Relationships      Constructive Queries
```

**LCM Characteristics:**
1. **Text Search**: Traditional full-text indexes
2. **Text Embeddings**: Dense vector search on passages
3. **RAG**: Retrieve and generate from source chunks
4. **Visual Embeddings**: Image similarity search (✅ ADR-057)
5. **Graph Embeddings**: Concept and edge embeddings (✅ ADR-044, ADR-045)
6. **Source Embeddings**: Grounding truth chunk search (❌ **This ADR**)
7. **Emergent Edges**: Relationships discovered via embedding proximity
8. **Constructive Queries**: Build knowledge paths from multi-modal signals

### Philosophical Foundation: Evidence vs. Grounding

**IMPORTANT:** Source embeddings serve a fundamentally different purpose than grounding calculation. This distinction is critical to understanding the architecture:

#### Evidence Layer (Descriptive - This ADR)
```
Source Text → Extraction → Concept
"The recursive depth tracker maintains state..."
                ↓
        [Concept: "Recursive Depth Tracking"]
```

**Purpose:** Provenance and evidence retrieval
- **Nature:** Observational, neutral representation
- **Language:** "Concept" (intentionally NOT "fact" or "truth")
- **What it captures:** Ideas stated/observed in source text
- **Judgment:** None - purely descriptive
- **Query use case:** "Show me the original text where this concept came from"

**Graph Traversal:**
```cypher
(:Concept)-[:EVIDENCED_BY]->(:Instance)-[:FROM_SOURCE]->(:Source)
```

**NOT used for grounding calculation** - only for citation and provenance.

#### Grounding Layer (Evaluative - ADR-044, ADR-058)
```
Concept ↔ Concept (relationships)
[:SUPPORTS], [:CONTRADICTS], [:ENABLES], etc.
                ↓
        Polarity projection → Grounding strength
```

**Purpose:** Truth convergence and validation
- **Nature:** Interpretive, evaluative assessment
- **Method:** Semantic projection of concept relationships onto polarity axis
- **What it measures:** How concepts validate/contradict each other
- **Source:** Concept-to-concept relationships, NOT source citations
- **Algorithm:** Polarity Axis Triangulation (ADR-058)

**Graph Traversal:**
```cypher
MATCH (c:Concept) <-[r]-(other:Concept)
// Project r onto SUPPORTS ↔ CONTRADICTS axis
```

#### Why This Separation Matters

**Evidence ≠ Validation:**
- Just because source text *states* something doesn't make it *grounded*
- Concepts from sources are neutral observations of what was written
- Grounding emerges from how concepts relate to *each other*, not from source citations

**Example:**
```
Source A: "The earth is flat"
  → Concept: "Flat Earth Model" (neutral observation)

Source B: "Spherical earth confirmed by gravity"
  → Concept: "Spherical Earth Model" (neutral observation)

Relationship: (Spherical Earth)-[:CONTRADICTS]->(Flat Earth)
  → Grounding: Flat Earth has negative grounding (contradicted)
```

The source text itself doesn't determine truth - the **semantic relationships between concepts** do.

**This ADR addresses evidence retrieval only.** Grounding calculation is handled separately by ADR-044 (Probabilistic Truth Convergence) and ADR-058 (Polarity Axis Triangulation).

## Decision

We will implement **asynchronous source text embedding generation** with the following design:

### 1. Separate Embeddings Table with Referential Integrity

**Key Insight**: Source nodes remain the canonical source of truth. Embeddings are stored separately with offset tracking and hash verification.

**Understanding the Chunking Architecture:**
```
Document (100KB)
    ↓ Ingestion chunking (smart chunker with overlap)
    ├─ Source node 1 (500-1500 words) ────→ Embedding chunk(s)
    ├─ Source node 2 (500-1500 words) ────→ Embedding chunk(s)
    ├─ Source node 3 (500-1500 words) ────→ Embedding chunk(s)
    ...
    └─ Source node N (500-1500 words) ────→ Embedding chunk(s)
                ↓
    Concepts extracted (references Sources)
```

**Two-level chunking:**
1. **Ingestion chunking** (existing): Document → Source nodes (500-1500 words each)
2. **Embedding chunking** (this ADR): Source.full_text → Embedding chunks (~100-120 words each)

**Typical scenario:**
- Large document → 10 Source nodes (ingestion chunks)
- 100 concepts extracted → reference those 10 Sources
- Each Source → 1-3 embedding chunks (depending on length)
- Total: 10-30 embeddings for entire document

```sql
-- Source node (canonical truth)
(:Source {
    source_id: "doc123_chunk5",
    full_text: "...",           -- Canonical text (500-1500 words from ingestion)
    content_hash: "sha256..."   -- Hash for verification (NULL for existing Sources)
})

-- Separate embeddings table with offsets
CREATE TABLE kg_api.source_embeddings (
    embedding_id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,

    -- Chunk tracking
    chunk_index INT NOT NULL,         -- 0-based chunk number
    chunk_strategy TEXT NOT NULL,     -- 'sentence', 'paragraph', 'semantic'

    -- Offset in Source.full_text (character positions)
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    chunk_text TEXT NOT NULL,         -- Actual chunk (for verification)

    -- Referential integrity (double hash verification)
    chunk_hash TEXT NOT NULL,         -- SHA256 of chunk_text
    source_hash TEXT NOT NULL,        -- SHA256 of Source.full_text

    -- Embedding data
    embedding BYTEA NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INT NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, chunk_index, chunk_strategy)
);
```

**Why separate table?**
- One Source can have multiple embedding chunks (granular retrieval)
- Offsets enable precise text highlighting and context extraction
- Hash verification ensures embeddings match current source text
- Stale embeddings detectable when source text changes
- Supports multiple strategies per Source (sentence + paragraph)

### 2. Chunking Strategy

Source text will be chunked using **simple, tunable strategies**:

```python
# In api/api/workers/source_embedding_worker.py
# Tuning constants (easy to adjust, no complex config needed)

CHUNKING_STRATEGIES = {
    "sentence": {
        "max_chars": 500,      # ~100-120 words
        "splitter": "sentence"  # Use sentence boundaries
    },
    "paragraph": {
        "max_chars": None,      # Use full Source.full_text
        "splitter": None        # No splitting needed
    },
    "semantic": {
        "max_chars": 1000,      # ~200-250 words
        "splitter": "semantic"  # Use existing SemanticChunk logic
    }
}

# Default strategy (simplest - no chunking)
DEFAULT_STRATEGY = "paragraph"
```

**Key Constraints**:
- Source.full_text already bounded (500-1500 words from ingestion chunker)
- No chunk can exceed embedding model context window
- Simple constants in code - easy to tune, no database config needed

**Configuration** (use existing embedding_config):
```python
# NO separate source_embedding_config table!
# Source embeddings use system-wide kg_api.embedding_config:
embedding_config = load_active_embedding_config()
{
    "provider": "local" | "openai",
    "model_name": "nomic-ai/nomic-embed-text-v1.5",
    "embedding_dimensions": 768,     # MUST match concept embeddings!
    "precision": "float16" | "float32",
    ...
}

# Why? Source embeddings must be comparable to concept embeddings.
# Using different dimensions would break cosine similarity.
```

**Always Enabled:**
- Source embedding generation is a first-class system feature
- No opt-in/opt-out flags
- Runs automatically for all ingested Sources
- Can be regenerated via existing regenerate embeddings worker

### 3. Migration Strategy: Add Field, Compute On-Demand

**Source.content_hash field:**
- Migration 068 adds field to Source nodes
- **NULL for existing Sources** (no backfill in migration)
- Computed on-demand when embeddings generated
- Existing regenerate embeddings worker handles backfill

**Rationale:**
- Avoid expensive migration (computing hash for all existing Sources)
- Leverage existing worker pattern (cures non-existent embeddings)
- Operators can regenerate at their leisure
- Non-blocking rollout

**Backfill process (optional, any time after migration):**
```bash
# Use existing regenerate embeddings pattern
kg admin regenerate-embeddings --type source --all

# Or per ontology
kg admin regenerate-embeddings --type source --ontology "MyDocs"
```

### 4. Hash Verification for Referential Integrity

**Double verification prevents silent corruption**:

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

**Benefits**:
- Detect when Source.full_text changes (invalidates embeddings)
- Verify chunk extraction matches original
- Enable automatic regeneration triggers
- Prevent serving stale embeddings

### 5. Async Job Processing

Leverage existing job system (ADR-014) for embedding generation:

```python
# New job type: "source_embedding"
{
    "job_type": "source_embedding",
    "status": "pending",
    "job_data": {
        "ontology": "MyOntology",
        "strategy": "paragraph",
        "source_ids": ["src_123", "src_456", ...],  // Batch of sources
        "embedding_provider": "local",
        "embedding_model": "nomic-ai/nomic-embed-text-v1.5"
    }
}
```

**Worker**: `api/api/workers/source_embedding_worker.py`

```python
def run_source_embedding_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Generate embeddings for source text chunks.

    Processing:
    1. Fetch Source nodes by source_ids
    2. Apply chunking strategy to full_text
    3. Generate embeddings via EmbeddingWorker (ADR-045)
    4. Update Source.embedding field
    5. Report progress to job queue
    """
```

### 6. Generation Triggers

**At Ingestion Time** (always enabled):
```python
# In api/api/workers/ingestion_worker.py
# After creating Source node
# No enable/disable check - always generate embeddings
job_queue.submit_job({
    "job_type": "source_embedding",
    "job_data": {
        "source_ids": [source_id],
        "ontology": ontology,
        "strategy": "sentence"  # Default strategy
    }
})
```

**Bulk Regeneration** (admin tool):
```bash
# Regenerate embeddings for entire ontology
kg admin regenerate-embeddings --ontology "MyOntology" --type source

# Regenerate for entire system (provider change)
kg admin regenerate-embeddings --type source --all
```

**Selective Regeneration** (configuration change):
```bash
# Change embedding provider, regenerate affected sources
kg admin source-embeddings config --ontology "MyOntology" --strategy paragraph
kg admin source-embeddings generate --ontology "MyOntology" --force
```

### 7. Query Integration

**New Search Mode: Source Similarity Search**

```python
# API endpoint: POST /queries/sources/search
{
    "query_text": "How does recursive depth affect performance?",
    "ontology": "SystemDocs",
    "limit": 10,
    "include_concepts": true  // Also return attached concepts
}

# Response
{
    "sources": [
        {
            "source_id": "doc123_chunk5",
            "document": "SystemDocs",
            "full_text": "...",
            "similarity": 0.87,
            "concepts": [...]  // Concepts extracted from this source
        }
    ]
}
```

**Hybrid Search: Concept + Source**

```python
# Find concepts, then return supporting source passages
{
    "query_text": "recursive relationships",
    "mode": "hybrid",  // Search both concepts AND sources
    "concept_limit": 5,
    "source_limit": 10
}

# Returns both concept matches AND similar source passages
```

**Context Window: Source Neighbors**

```cypher
// Given a matched concept, find neighboring source context
MATCH (c:Concept {concept_id: $concept_id})-[:APPEARS_IN]->(s:Source)
MATCH (neighbor:Source {document: s.document})
WHERE neighbor.paragraph >= s.paragraph - 2
  AND neighbor.paragraph <= s.paragraph + 2
RETURN neighbor
ORDER BY neighbor.paragraph
```

### 8. Cost and Performance

**Storage**:
- 768-dim float16 embedding = 1.5KB per chunk
- Typical: 1-2 chunks per Source (500-1500 word Sources)
- Avg 1.5 chunks per Source = 2.25KB per Source
- 1M sources = ~2.25GB embedding storage
- Plus ~500 bytes metadata per chunk = ~750MB
- Total: ~3GB for 1M sources (acceptable for PostgreSQL)

**Note:** Most Sources (500-1500 words) will have 1-2 embedding chunks at 500 char (~100 word) granularity.

**Generation**:
- Local embeddings (Nomic): ~5-10ms per chunk (CPU fallback: ~20-50ms)
- Typical: 1-2 chunks per Source = ~10-20ms per Source
- OpenAI API: ~50-100ms per batch (rate limited)
- Async processing prevents ingestion blocking
- Hash calculation: <1ms (negligible)
- Content_hash computed once per Source, cached in node

**Regeneration**:
- Leverage existing regenerate embeddings worker
- Worker cures non-existent embeddings (NULL content_hash)
- 1M sources @ 15ms = ~4 hours (local, 1-2 chunks per Source)
- Progress tracking via job system
- Resumable on failure
- Can regenerate entire system or per-ontology

## Consequences

### Positive

1. **Referential Integrity**
   - Double hash verification (source + chunk)
   - Detect stale embeddings automatically
   - Prevent serving outdated results
   - Enable automatic regeneration triggers

2. **Granular Retrieval**
   - 1-2 embeddings per Source (typical)
   - Precise offset tracking for highlighting
   - Context-aware search results
   - Chunking overlap from ingestion ensures continuity

3. **Complete Retrieval Coverage**
   - Text search (full-text)
   - Concept search (embeddings)
   - Source search (embeddings) ← NEW
   - Visual search (image embeddings)

4. **Enhanced RAG**
   - Retrieve source passages directly
   - Combine with concept context
   - Build richer prompts for LLM generation

5. **Context Discovery**
   - Find similar passages across documents
   - Identify conceptual overlap via source similarity
   - Build "source graphs" of related passages

6. **LCM Foundation**
   - All graph elements become searchable
   - Enables emergent relationship discovery
   - Supports constructive multi-modal queries

7. **Provider Flexibility**
   - Regenerate embeddings when provider changes
   - A/B test embedding models
   - Mix providers per ontology

8. **Simple Configuration**
   - Uses existing kg_api.embedding_config (system-wide)
   - No separate configuration table
   - Must match concept embedding dimensions
   - Always enabled (first-class feature)

9. **Leverage Existing Patterns**
   - Uses existing regenerate embeddings worker
   - Worker cures NULL content_hash on-demand
   - No expensive migration backfill
   - Operators control regeneration timing

### Negative

1. **Storage Overhead**
   - +2.25KB per Source (1.5 chunks @ 1.5KB each, typical)
   - Plus ~750MB metadata (1M sources)
   - For 1M sources: ~3GB storage
   - Acceptable for PostgreSQL at scale

2. **Ingestion Latency**
   - Async job adds ~15ms per source (1-2 chunks typical)
   - Hash calculation adds <1ms (cached in Source.content_hash)
   - Mitigated by background processing
   - Total impact negligible

3. **Schema Complexity**
   - Additional table to maintain (source_embeddings)
   - Hash verification logic required
   - Stale embedding detection needed

4. **API Complexity**
   - New search modes to maintain
   - Hybrid search requires careful tuning
   - Offset extraction and highlighting logic

5. **Migration Cost**
   - Migration 068 adds field only (fast, no backfill)
   - Existing Sources have NULL content_hash initially
   - Backfill via regenerate embeddings worker (optional, at leisure)
   - No downtime required (graceful degradation)

### Neutral

1. **Always-On Feature**
   - Source embedding generation runs for all ingestions
   - No opt-in/opt-out (first-class system feature)
   - Simplified architecture (no conditional logic)

2. **Backward Compatible**
   - Migration adds field, NULL for existing Sources
   - Existing Source nodes continue working
   - Regenerate embeddings worker handles backfill
   - Queries gracefully handle NULL content_hash

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Migration 068: Create `kg_api.source_embeddings` table
- [ ] Migration 068: Add `Source.content_hash` field (NULL for existing)
- [ ] Implement hash verification utilities (SHA256)
- [ ] Implement sentence chunking with offset tracking (500 chars)
- [ ] Implement `SourceEmbeddingWorker` skeleton
- [ ] Query active `embedding_config` for dimensions
- [ ] Add job type "source_embedding" to queue

### Phase 2: Generation (Week 2)
- [ ] Implement full `SourceEmbeddingWorker` with chunking
- [ ] Add hash verification at generation time
- [ ] Store embeddings in `source_embeddings` table
- [ ] Update `Source.content_hash` field when embedding
- [ ] Add ingestion-time embedding generation (always enabled)
- [ ] Test with small ontology (verify chunks, offsets, hashes)

### Phase 3: Query Integration (Week 3)
- [ ] Implement `/queries/sources/search` endpoint
- [ ] Add stale embedding detection in queries
- [ ] Return matched chunks with offsets for highlighting
- [ ] Add context window expansion (neighboring chunks)
- [ ] Implement hash verification at query time

### Phase 4: Unified Embedding Regeneration (Week 4)

**Critical Infrastructure:** Enables cross-entity semantic queries and global model migrations.

**Rationale:** The system currently has embeddings in three namespaces:
1. **Concepts**: `Concept.embedding` (AGE graph nodes)
2. **Sources**: `kg_api.source_embeddings` table (this ADR)
3. **Vocabulary**: `kg_api.vocabulary_embeddings` table (ADR-044)

Without unified regeneration:
- ❌ Cannot switch embedding models globally (must manually regenerate 3 systems)
- ❌ Cannot guarantee cross-entity semantic compatibility
- ❌ Cannot execute blended queries (concept + source + relationship)
- ❌ Cannot discover emergent relationships via embedding proximity

**Phase 4 Solution: Single interface for ALL graph text embeddings**

#### 4.1: Source Embedding Regeneration
- [ ] Implement `regenerate_source_embeddings()` function in `source_embedding_worker.py`
- [ ] Fetch sources from AGE (filter by ontology, detect missing embeddings)
- [ ] Batch process sources with progress tracking
- [ ] Support `--only-missing` flag (skip sources with valid embeddings)
- [ ] Detect and regenerate stale embeddings (hash mismatch)

#### 4.2: Vocabulary Embedding Regeneration
- [ ] Implement `regenerate_vocabulary_embeddings()` function
- [ ] Regenerate embeddings for all relationship types in vocabulary
- [ ] Update `kg_api.vocabulary_embeddings` table
- [ ] Support categorical filtering (semantic, structural, epistemic, etc.)

#### 4.3: Unified API Endpoint
- [ ] Add `/admin/regenerate-embeddings` endpoint (replaces `/admin/regenerate-concept-embeddings`)
- [ ] Support `type` parameter: `concept`, `source`, `vocabulary`, `all`
- [ ] Support filters: `ontology`, `only_missing`, `limit`, `offset`
- [ ] Return unified progress tracking and statistics

#### 4.4: CLI Enhancement
- [ ] Update `kg admin regenerate-embeddings` command
- [ ] Add `--type <concept|source|vocabulary|all>` flag (default: `concept`)
- [ ] Support `--ontology <name>` (limit to specific namespace)
- [ ] Support `--only-missing` (skip entities with valid embeddings)
- [ ] Support `--limit <n>` and `--offset <n>` for batching
- [ ] Unified progress display for all entity types

#### 4.5: Cross-Entity Query Foundation
- [ ] Document semantic query patterns (see "Cross-Entity Query Capabilities" below)
- [ ] Add examples for blended search (concept + source + relationship)
- [ ] Performance benchmarks for cross-entity queries
- [ ] Add MCP tools for unified semantic search

**Example Usage:**

```bash
# Model migration: Regenerate ALL embeddings with new model
kg admin regenerate-embeddings --all

# Selective regeneration
kg admin regenerate-embeddings --type concept --ontology "MyDocs"
kg admin regenerate-embeddings --type source --only-missing
kg admin regenerate-embeddings --type vocabulary

# Batch processing
kg admin regenerate-embeddings --type source --limit 1000 --offset 0
```

### Phase 5: Advanced Features (Future)
- [ ] Hybrid search (concept + source combined)
- [ ] Semantic chunking strategy
- [ ] Multiple strategies per Source
- [ ] Cross-document source similarity
- [ ] Edge embeddings for emergent relationships

## Cross-Entity Query Capabilities

**The Emergent Power of Unified Semantic Space**

Once concepts, sources, and vocabulary (relationship types) share the same semantic space with compatible embeddings, powerful cross-entity query patterns emerge. This is the foundation of the **Large Concept Model (LCM)** architecture.

### 1. Dynamic Query Routing

Route queries to the most relevant entity type automatically:

```python
# Single query → multiple semantic entry points
query = "recursive depth management"

results = {
    "via_concepts": search_concepts(query),           # Direct concept match
    "via_sources": search_sources(query),             # Evidence passage match
    "via_relationships": search_relationships(query), # Semantic edge match
}

# System automatically selects best entry point by similarity
best_entry = max(results, key=lambda r: r.max_similarity)
```

**Use Case:** User doesn't know whether their query matches a concept name, a source passage, or a relationship type. The system finds the best match across all three and uses that as the entry point.

### 2. Semantic Path Discovery

Discover relationships not by exact type, but by semantic meaning:

```cypher
// Traditional: Exact relationship traversal
MATCH (c:Concept {concept_id: $id})-[:SUPPORTS]->(target)

// With embeddings: Semantic relationship discovery
MATCH (c:Concept {concept_id: $id})-[r]->(target:Concept)
WHERE vocabulary_embedding_similarity(type(r), "strengthens, enables, reinforces") > 0.8
RETURN target
ORDER BY vocabulary_embedding_similarity(type(r), $query_embedding) DESC
```

**Use Case:** Find all concepts that "support" a given concept, but include relationships with semantically similar meanings (ENABLES, REINFORCES, STRENGTHENS, etc.).

### 3. Multi-Entity Blending

Merge results from multiple entity types for comprehensive coverage:

```python
# Query: "How does probabilistic reasoning work?"

# Strategy A: Find concepts directly
concepts_direct = search_concepts("probabilistic reasoning", limit=10)

# Strategy B: Find source passages → extract their concepts
sources = search_sources("probabilistic reasoning", limit=10)
concepts_from_sources = get_concepts_for_sources(sources)

# Strategy C: Find relationships → traverse to concepts
relationships = search_relationships("probabilistic reasoning", limit=10)
concepts_via_edges = get_concepts_connected_by(relationships)

# BLEND: Merge + deduplicate + rank by combined signals
blended_results = merge_and_rank([
    (concepts_direct, weight=1.0),          # Direct matches
    (concepts_from_sources, weight=0.8),    # Evidence-based
    (concepts_via_edges, weight=0.6)        # Relationship-based
])
```

**Use Case:** Comprehensive search that considers all perspectives—concepts mentioned explicitly, concepts discussed in sources, and concepts connected via semantically relevant relationships.

### 4. Contextual Re-Ranking

Rank evidence by semantic relevance to the query, not just presence:

```python
# Query: "grounding strength calculation"

# Step 1: Find best concept match
concept = search_concepts("grounding strength")[0]

# Step 2: Get evidence, but rank by CONTEXT similarity
evidence = get_concept_evidence(concept.id)

for source in evidence:
    # Traditional: "This source mentions this concept" (binary)
    # Enhanced: "This source passage is contextually relevant to the query" (scored)
    source.relevance_score = cosine_similarity(
        embed("grounding strength calculation"),
        source.embedding
    )

# Return context-aware evidence ranking
return sorted(evidence, key=lambda s: s.relevance_score, reverse=True)
```

**Use Case:** Show the most relevant evidence first—passages that not only mention the concept but discuss it in the context the user cares about.

### 5. Semantic Subgraph Extraction

Extract connected subgraphs based on semantic similarity, not just explicit edges:

```python
# "Show me everything semantically related to 'epistemic status'"

query_emb = embed("epistemic status")

# Find ALL entities semantically close (threshold = 0.7)
semantic_neighborhood = {
    "concepts": cosine_search(Concept.embedding, query_emb, threshold=0.7),
    "sources": cosine_search(source_embeddings, query_emb, threshold=0.7),
    "relationships": cosine_search(vocabulary_embeddings, query_emb, threshold=0.7)
}

# Extract connected subgraph containing these entities
subgraph = extract_connected_subgraph(semantic_neighborhood)

# Visualize: Everything semantically related, regardless of entity type
```

**Use Case:** Explore a topic by finding all concepts, sources, and relationships semantically related to it—not just those explicitly linked.

### 6. Emergent Relationship Discovery

Find implicit relationships via embedding proximity:

```cypher
// Find concepts that are semantically similar but not explicitly connected
MATCH (c1:Concept), (c2:Concept)
WHERE embedding_similarity(c1, c2) > 0.85
  AND NOT (c1)-[]-(c2)  // Not explicitly connected

// Find sources that bridge them
MATCH (s:Source)
WHERE source_embedding_similarity(s, c1) > 0.75
  AND source_embedding_similarity(s, c2) > 0.75

RETURN c1, c2, s
// Result: "These concepts aren't linked, but this source passage
//          discusses both → potential emergent relationship"
```

**Use Case:** Discover hidden connections—concepts that should be related based on semantic proximity but haven't been explicitly linked yet.

### 7. Cross-Modal Query Fusion (Future)

With visual embeddings (ADR-057), blend text + visual semantics:

```python
# Query: "system architecture"

results = blend_multimodal([
    search_concepts("system architecture"),
    search_sources("architecture diagrams"),
    search_relationships("defines structure"),
    search_images(visual_query="architecture diagram")  # Visual similarity
])

# Result: Concepts + passages + diagrams, all ranked by semantic relevance
```

**Use Case:** Find everything related to a topic—concepts, source passages, AND diagrams/images—all ranked by unified semantic similarity.

## Why This Matters: The LCM Vision

Traditional RAG (Retrieval-Augmented Generation):
```
Documents → Chunks → Embeddings → Vector DB → Retrieve → Generate
```

Large Concept Model (LCM) with Unified Embeddings:
```
Documents → {Concepts, Sources, Relationships} → Embeddings → Multi-Entity Graph
                                                       ↓
                        Dynamic Routing + Blending + Emergent Discovery
                                                       ↓
                              Semantic Subgraphs + Context-Aware Ranking
```

**Key Differences:**
1. **Multi-Entity**: Not just document chunks, but concepts + sources + relationships
2. **Semantic Graph**: Explicit edges PLUS embedding-based proximity
3. **Dynamic Routing**: Query finds best entry point automatically
4. **Blended Results**: Combine signals from multiple entity types
5. **Emergent Discovery**: Find implicit relationships via embedding similarity

**This is only possible with unified embedding regeneration (Phase 4).**

## Alternatives Considered

### Alternative 1: Generate Embeddings at Query Time

**Rejected**: Too slow for real-time queries. Source embedding generation would block response.

### Alternative 2: Store Single Embedding on Source Node

**Rejected**: Cannot support multiple chunks per Source. Loses granularity and offset tracking.

### Alternative 3: Only Embed Concept Descriptions (Status Quo)

**Rejected**: Loses access to full source context. Cannot retrieve similar passages directly.

### Alternative 4: Use Full-Text Search Only

**Rejected**: Full-text search is lexical, not semantic. Misses conceptual similarity.

## Key Design Decisions Summary

### 1. content_hash Field: Add, Don't Backfill
- Migration adds field to Source nodes
- NULL for existing Sources
- Computed on-demand during embedding generation
- Leverage existing regenerate embeddings worker for backfill

### 2. No Separate Configuration
- Use existing `kg_api.embedding_config` (system-wide)
- Source embeddings MUST match concept embedding dimensions
- No opt-in/opt-out flags

### 3. Chunk Size: 500 Characters (~100 words)
- Balances granularity vs overhead
- Most Sources (500-1500 words) → 1-2 embedding chunks
- Large document: 10 Sources → 10-20 embeddings total
- Chunking overlap from ingestion ensures continuity

### 4. Always Enabled
- Source embedding generation is first-class feature
- Runs automatically for all ingestions
- Simplified architecture (no conditional logic)

### 5. Leverage Existing Patterns
- Existing regenerate embeddings worker handles backfill
- Worker cures NULL content_hash
- Operators control regeneration timing

## Related ADRs

- **ADR-022**: Semantic Relationship Taxonomy (Porter stemmer hybrid chunking with overlap)
- **ADR-044**: Probabilistic Truth Convergence (relationship embeddings for grounding)
- **ADR-045**: Unified Embedding Generation (EmbeddingWorker architecture)
- **ADR-057**: Multimodal Image Ingestion (visual embeddings for images)
- **ADR-014**: Job Approval Workflow (async job processing)
- **ADR-039**: Local Embedding Service (embedding configuration system)

## References

### Large Concept Model (LCM) Vision

The term "Large Concept Model" extends the RAG paradigm to full graph embeddings:

**Traditional RAG Stack:**
1. Chunk documents
2. Embed chunks
3. Store in vector DB
4. Retrieve similar chunks
5. Generate response

**LCM Stack (Proposed):**
1. Chunk documents → Sources
2. Extract concepts → Concepts
3. Generate relationships → Edges
4. Embed EVERYTHING → Sources, Concepts, Edges
5. Multi-modal retrieval → Text, concept, relationship, visual
6. Graph-aware generation → Context from graph structure + embeddings
7. Emergent synthesis → Discover new relationships via proximity

This ADR implements step 4 for Sources, completing the embedding coverage.

### External Resources

- [Dense Passage Retrieval (DPR)](https://arxiv.org/abs/2004.04906) - Dual-encoder architecture for passage retrieval
- [ColBERT](https://arxiv.org/abs/2004.12832) - Late interaction for efficient passage ranking
- [REALM](https://arxiv.org/abs/2002.08909) - Retrieval-augmented language model pre-training
- [Graph Neural Networks](https://arxiv.org/abs/1901.00596) - Comprehensive survey of GNN architectures

## Appendix: Example Queries

### Source Similarity Search

```python
# Find passages similar to query
client.search_sources(
    query="How does grounding strength work?",
    ontology="ADRs",
    limit=5
)
# Returns:
# - Top 5 most similar source passages
# - Attached concepts for each passage
# - Similarity scores
```

### Hybrid Concept + Source Search

```python
# Find concepts, then expand to source context
results = client.hybrid_search(
    query="epistemic status measurement",
    concept_limit=3,
    source_limit=10,
    expand_context=True  # Include neighboring source paragraphs
)
# Returns:
# - 3 most relevant concepts
# - 10 most similar source passages
# - Context window around matched sources
```

### Context Window for Concept

```python
# Given a concept, find surrounding source context
client.get_concept_context(
    concept_id="concept-123",
    window_size=2  # ±2 paragraphs
)
# Returns:
# - Source paragraph containing concept
# - 2 paragraphs before
# - 2 paragraphs after
# - Enables reading concept in original context
```

### Cross-Document Source Similarity

```python
# Find similar passages across multiple documents
client.cross_document_similarity(
    source_id="doc1_chunk5",
    ontologies=["ADRs", "CodeDocs", "Research"],
    limit=10
)
# Returns:
# - Similar passages from other documents
# - Identifies conceptual overlap
# - Builds "source graph" of related passages
```

---

**Last Updated:** 2025-11-27
**Next Review:** After Phase 1 implementation (1 month)
