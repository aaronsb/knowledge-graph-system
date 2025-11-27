# ADR-068: Source Text Embeddings for Grounding Truth Retrieval

**Status:** Proposed
**Date:** 2025-11-27
**Deciders:** System Architect
**Tags:** #embeddings #source-retrieval #async-processing #lcm

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

## Decision

We will implement **asynchronous source text embedding generation** with the following design:

### 1. Chunking Strategy

Source text will be chunked using **adjustable granularity**:

```python
class SourceChunkingStrategy(Enum):
    SENTENCE = "sentence"      # ~20-40 words per chunk
    PARAGRAPH = "paragraph"    # ~100-200 words per chunk
    COUNT = "count"            # Fixed word count (e.g., 250 words)
    SEMANTIC = "semantic"      # Use existing semantic chunker
```

**Default**: `PARAGRAPH` (aligns with existing Source nodes which store paragraph-level text)

**Configuration** (per ontology):
```sql
CREATE TABLE kg_api.source_embedding_config (
    config_id SERIAL PRIMARY KEY,
    ontology_name TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'paragraph',
    chunk_size INT,  -- For COUNT strategy
    embedding_model TEXT NOT NULL,
    embedding_dimension INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ontology_name)
);
```

### 2. Schema Changes

Add embedding field to Source nodes:

```cypher
// Existing Source node (ADR-057)
CREATE (s:Source {
    source_id: $source_id,
    document: $document,
    paragraph: $paragraph,
    full_text: $full_text,
    content_type: $content_type,
    storage_key: $storage_key,       // Images only
    visual_embedding: $visual_embedding,  // Images only
    embedding: $embedding             // ← NEW: Text embedding of full_text
})
```

**New field**:
- `embedding` - Dense vector of configurable dimension (default: 768 for Nomic, 1536 for OpenAI)
- NULL allowed (for backward compatibility and progressive rollout)
- Same field name as Concept.embedding for consistency

### 3. Async Job Processing

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

### 4. Generation Triggers

**At Ingestion Time** (immediate):
```python
# In api/api/workers/ingestion_worker.py
# After creating Source node
if should_generate_source_embeddings(ontology):
    # Dispatch async job
    job_queue.submit_job({
        "job_type": "source_embedding",
        "job_data": {
            "source_ids": [source_id],
            "ontology": ontology,
            ...
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

### 5. Query Integration

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

### 6. Cost and Performance

**Storage**:
- 768-dim float16 embedding = 1.5KB per Source
- 1M sources = ~1.5GB embedding storage
- Acceptable for PostgreSQL bytea columns

**Generation**:
- Local embeddings (Nomic): ~5-10ms per source (CPU fallback: ~20-50ms)
- OpenAI API: ~50-100ms per batch (rate limited)
- Async processing prevents ingestion blocking

**Regeneration**:
- 1M sources @ 10ms = ~3 hours (local)
- Progress tracking via job system
- Resumable on failure

## Consequences

### Positive

1. **Complete Retrieval Coverage**
   - Text search (full-text)
   - Concept search (embeddings)
   - Source search (embeddings) ← NEW
   - Visual search (image embeddings)

2. **Enhanced RAG**
   - Retrieve source passages directly
   - Combine with concept context
   - Build richer prompts for LLM generation

3. **Context Discovery**
   - Find similar passages across documents
   - Identify conceptual overlap via source similarity
   - Build "source graphs" of related passages

4. **LCM Foundation**
   - All graph elements become searchable
   - Enables emergent relationship discovery
   - Supports constructive multi-modal queries

5. **Provider Flexibility**
   - Regenerate embeddings when provider changes
   - A/B test embedding models
   - Mix providers per ontology

### Negative

1. **Storage Overhead**
   - +1.5KB per Source node
   - For 1M sources: +1.5GB storage

2. **Ingestion Latency**
   - Async job adds ~1-5s per source (amortized)
   - Mitigated by background processing

3. **API Complexity**
   - New search modes to maintain
   - Hybrid search requires careful tuning
   - More configuration options

4. **Migration Cost**
   - Existing installations need embedding backfill
   - Large graphs may take hours to process
   - Requires downtime or staged rollout

### Neutral

1. **Optional Feature**
   - Ontologies can opt-in/opt-out
   - Graceful degradation if embeddings missing
   - Progressive enhancement

2. **Backward Compatible**
   - Existing Source nodes work without embeddings
   - NULL embedding field allowed
   - Queries check for embedding presence

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Add `embedding` field to Source schema (migration)
- [ ] Create `source_embedding_config` table
- [ ] Implement `SourceEmbeddingWorker`
- [ ] Add job type "source_embedding" to queue

### Phase 2: Generation (Week 2)
- [ ] Implement chunking strategies (sentence, paragraph, count, semantic)
- [ ] Add ingestion-time embedding generation (opt-in)
- [ ] Build admin tool for bulk regeneration
- [ ] Add progress tracking and resumption

### Phase 3: Query Integration (Week 3)
- [ ] Implement `/queries/sources/search` endpoint
- [ ] Add hybrid search (concept + source)
- [ ] Implement context window queries
- [ ] Add MCP tools for source search

### Phase 4: Optimization (Week 4)
- [ ] Batch embedding generation for efficiency
- [ ] Add embedding model A/B testing
- [ ] Implement selective regeneration (by ontology)
- [ ] Performance benchmarking and tuning

### Phase 5: LCM Vision (Future)
- [ ] Edge embeddings for emergent relationships
- [ ] Multi-modal constructive queries
- [ ] Recursive concept attachment
- [ ] Knowledge synthesis from embedding proximity

## Alternatives Considered

### Alternative 1: Generate Embeddings at Query Time

**Rejected**: Too slow for real-time queries. Source embedding generation would block response.

### Alternative 2: Store Embeddings in Separate Table

**Rejected**: Adds join complexity. Embedding is intrinsic to Source, should live on node.

### Alternative 3: Only Embed Concept Descriptions (Status Quo)

**Rejected**: Loses access to full source context. Cannot retrieve similar passages directly.

### Alternative 4: Use Full-Text Search Only

**Rejected**: Full-text search is lexical, not semantic. Misses conceptual similarity.

## Related ADRs

- **ADR-044**: Probabilistic Truth Convergence (relationship embeddings for grounding)
- **ADR-045**: Unified Embedding Generation (EmbeddingWorker architecture)
- **ADR-057**: Multimodal Image Ingestion (visual embeddings for images)
- **ADR-014**: Job Approval Workflow (async job processing)
- **ADR-031**: Encrypted API Key Storage (embedding provider credentials)

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
