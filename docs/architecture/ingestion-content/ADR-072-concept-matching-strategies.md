# ADR-072: Concept Matching Strategies and Configuration

**Status:** Draft
**Date:** 2025-12-04
**Supersedes:** Initial ingestion implementation (no formal ADR)

## Context

Concept similarity matching during ingestion currently uses hardcoded parameters and an exhaustive search strategy that will not scale. The system has evolved since initial implementation:

### Current State (Hardcoded)

```python
# api/api/lib/ingestion.py:336
matches = age_client.vector_search(
    embedding=embedding,
    threshold=0.85,  # ❌ Hardcoded
    top_k=5          # ❌ Hardcoded
)
```

**Issues:**
1. **No pgvector:** Full O(n) Python numpy scan on every concept match
2. **Hardcoded threshold:** 0.85 may not suit all use cases (research vs brainstorming)
3. **Exhaustive search:** Checks all concepts, ignores graph structure
4. **Not configurable:** Users can't tune for their corpus characteristics

### New Capabilities Available

Since initial implementation, the platform now supports:

1. **pgvector Extension** - Can be added to PostgreSQL for native vector indexing
2. **Degree Centrality Data** - Graph structure reveals hub concepts
3. **ADR-041 Configuration Pattern** - Database-first configuration with hot-reload
4. **ADR-071 Epsilon-Greedy Pattern** - Proven degree-biased search strategies

### Performance Bottleneck

With 10k+ concepts, ingestion slows dramatically:
- Current: 100 concepts/chunk × 500ms search = 50 seconds/chunk
- With pgvector: 100 concepts × 10ms = 1 second/chunk
- **50x speedup potential**

### Search Strategy Insight

ADR-071 discovered that degree centrality bias improves both performance and quality for graph traversal. The same principle applies to concept matching:

**High-degree concepts are:**
- More semantically stable (validated by many sources)
- More likely canonical (referenced frequently)
- Better deduplication targets (consolidation nodes)

## Decision

Implement three-tier concept matching system with database-first configuration and pgvector indexing.

### 1. Database Configuration Schema

```sql
-- Migration: Add concept matching configuration
CREATE TABLE IF NOT EXISTS kg_api.concept_match_config (
    config_id SERIAL PRIMARY KEY,
    strategy VARCHAR(50) NOT NULL DEFAULT 'exhaustive',
        CHECK (strategy IN ('exhaustive', 'degree_biased', 'degree_only')),
    similarity_threshold FLOAT NOT NULL DEFAULT 0.85,
        CHECK (similarity_threshold >= 0.0 AND similarity_threshold <= 1.0),
    top_k INTEGER NOT NULL DEFAULT 5,
        CHECK (top_k >= 1 AND top_k <= 20),
    degree_percentile FLOAT NOT NULL DEFAULT 0.75,
        CHECK (degree_percentile >= 0.0 AND degree_percentile <= 1.0),
    evidence_weight FLOAT,
        CHECK (evidence_weight IS NULL OR (evidence_weight >= 0.0 AND evidence_weight <= 1.0)),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default configuration (exhaustive, current behavior)
INSERT INTO kg_api.concept_match_config (
    strategy,
    similarity_threshold,
    top_k,
    degree_percentile,
    evidence_weight,
    description,
    is_active
) VALUES (
    'exhaustive',
    0.85,
    5,
    0.75,
    NULL,
    'Default configuration: exhaustive search with 0.85 threshold',
    TRUE
);
```

### 2. Three Search Strategies

Following ADR-071 epsilon-greedy pattern:

| Strategy | Description | Performance | Quality | Use Case |
|----------|-------------|-------------|---------|----------|
| **exhaustive** | Search all concepts (current) | O(n) slow | Best | Default, small graphs (<10k) |
| **degree_biased** | 80% high-degree + 20% random | 2-3x faster | Good | Growing graphs, balanced |
| **degree_only** | Only high-degree concepts | Fastest | Conservative | Large mature graphs (>50k) |

**Degree Centrality Filter:**
- Calculate degree for each concept: `count(relationships)`
- Filter to top N percentile (default: 75th percentile = top 25%)
- Only search filtered set (degree_only) or bias search toward it (degree_biased)

### 3. pgvector Integration

```sql
-- Add pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector column for fast similarity search
ALTER TABLE ag_catalog.concept
ADD COLUMN embedding_vec vector(1536);

-- Populate from existing JSON embeddings
UPDATE ag_catalog.concept
SET embedding_vec = embedding::vector
WHERE embedding IS NOT NULL;

-- Create index (IVFFlat with cosine distance)
CREATE INDEX concept_embedding_idx
ON ag_catalog.concept
USING ivfflat (embedding_vec vector_cosine_ops)
WITH (lists = 100);
```

**Query Pattern with Degree Centrality (following ADR-071):**
```cypher
-- Degree-biased search (calculate degree inline, no caching needed)
MATCH (c:Concept)-[r]-()
WHERE c.embedding IS NOT NULL
WITH c, count(r) AS degree
ORDER BY degree DESC
LIMIT 1000  -- Pre-filter to top N by degree

-- Then apply pgvector similarity on filtered set
-- (Combined Cypher + SQL for best performance)
```

**pgvector Similarity Search:**
```sql
-- Fast similarity search with pgvector
SELECT c.concept_id, c.label, c.description,
       1 - (c.embedding_vec <=> $1::vector) AS similarity
FROM ag_catalog.concept c
WHERE c.embedding_vec IS NOT NULL
  AND 1 - (c.embedding_vec <=> $1::vector) >= $threshold
ORDER BY c.embedding_vec <=> $1::vector
LIMIT $top_k;
```

### 4. Configuration Loading

Following ADR-041 pattern (database-first with fallbacks):

```python
# api/api/lib/concept_matcher.py

@dataclass
class ConceptMatchConfig:
    """Configuration for concept similarity matching."""
    strategy: str = "exhaustive"
    similarity_threshold: float = 0.85
    top_k: int = 5
    degree_percentile: float = 0.75
    evidence_weight: Optional[float] = None

    @classmethod
    def from_database(cls, db_client) -> "ConceptMatchConfig":
        """Load active configuration from database."""
        query = """
        SELECT strategy, similarity_threshold, top_k,
               degree_percentile, evidence_weight
        FROM kg_api.concept_match_config
        WHERE is_active = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """
        try:
            result = db_client.execute(query)
            if result:
                return cls(**result[0])
        except Exception as e:
            logger.warning(f"Failed to load concept match config: {e}")

        # Fallback to defaults
        return cls()

# Load once at startup, cache, reload on config change
_config_cache: Optional[ConceptMatchConfig] = None

def get_concept_match_config(db_client) -> ConceptMatchConfig:
    """Get active concept matching configuration (cached)."""
    global _config_cache
    if _config_cache is None:
        _config_cache = ConceptMatchConfig.from_database(db_client)
    return _config_cache

def reload_concept_match_config(db_client):
    """Force reload of configuration (called after admin updates)."""
    global _config_cache
    _config_cache = None
    return get_concept_match_config(db_client)
```

### 5. API Endpoints

**GET /admin/concept-match/config** - View current configuration
```json
{
  "strategy": "exhaustive",
  "similarity_threshold": 0.85,
  "top_k": 5,
  "degree_percentile": 0.75,
  "evidence_weight": null,
  "description": "Default configuration: exhaustive search with 0.85 threshold"
}
```

**GET /admin/concept-match/strategies** - List available strategies
```json
{
  "strategies": [
    {
      "name": "exhaustive",
      "description": "Search all concepts with embeddings",
      "performance": "O(n) - slower at scale",
      "quality": "Best - finds optimal match",
      "recommended_for": "Small graphs (<10k concepts), strict deduplication"
    },
    {
      "name": "degree_biased",
      "description": "80% high-degree concepts + 20% random exploration",
      "performance": "2-3x faster than exhaustive",
      "quality": "Good - biases toward stable hub concepts",
      "recommended_for": "Growing graphs, balanced performance/quality"
    },
    {
      "name": "degree_only",
      "description": "Only search high-degree hub concepts",
      "performance": "Fastest - searches top 25% by degree",
      "quality": "Conservative - may miss novel connections",
      "recommended_for": "Large mature graphs (>50k concepts)"
    }
  ],
  "parameters": {
    "similarity_threshold": {
      "type": "float",
      "range": [0.0, 1.0],
      "default": 0.85,
      "description": "Minimum cosine similarity for concept matching"
    },
    "top_k": {
      "type": "integer",
      "range": [1, 20],
      "default": 5,
      "description": "Maximum candidate concepts to evaluate"
    },
    "degree_percentile": {
      "type": "float",
      "range": [0.0, 1.0],
      "default": 0.75,
      "description": "Degree centrality threshold (0.75 = top 25%)"
    },
    "evidence_weight": {
      "type": "float",
      "range": [0.0, 1.0],
      "default": null,
      "description": "Weight for evidence-aware matching (null = disabled)"
    }
  }
}
```

**POST /admin/concept-match/config** - Update configuration
```json
{
  "strategy": "degree_biased",
  "similarity_threshold": 0.87,
  "top_k": 10,
  "degree_percentile": 0.80,
  "description": "Optimized for large research corpus"
}
```

### 6. Ingestion Integration

```python
# api/api/lib/ingestion.py

def process_chunk(...):
    # Load configuration once per ingestion job (cached)
    match_config = get_concept_match_config(age_client)

    for concept in extraction["concepts"]:
        # Generate embedding (unchanged)
        embedding = embedding_worker.generate_concept_embedding(embedding_text)

        # Vector search with configured strategy
        matches = age_client.vector_search_with_strategy(
            embedding=embedding,
            threshold=match_config.similarity_threshold,
            top_k=match_config.top_k,
            strategy=match_config.strategy,
            degree_percentile=match_config.degree_percentile
        )

        # Rest of upsert logic unchanged
        if matches:
            # Link to existing
        else:
            # Create new
```

### 7. Operator CLI Integration

```bash
# View current configuration
docker exec kg-operator python /workspace/operator/configure.py concept-match status

# Update configuration
docker exec kg-operator python /workspace/operator/configure.py concept-match \
  --strategy degree_biased \
  --threshold 0.87 \
  --top-k 10

# List available strategies
docker exec kg-operator python /workspace/operator/configure.py concept-match strategies
```

## Consequences

### Positive

✅ **Massive Performance Improvement**
- pgvector: 100x faster than Python numpy full scan
- degree_biased: 2-3x additional speedup via filtering
- Combined: 50 seconds/chunk → 1 second/chunk potential

✅ **Configurability Without Complexity**
- Database-first: single source of truth
- No per-job overrides (simplicity)
- Hot-reload capability via cache invalidation

✅ **Proven Pattern**
- Follows ADR-041 (database-first configuration)
- Applies ADR-071 lessons (degree-biased search)
- Consistent with platform architecture

✅ **Future-Ready**
- Evidence-aware matching (when ADR-068 complete)
- Per-job overrides (if needed later)
- Query tuning based on graph characteristics

✅ **Backward Compatible**
- Default: exhaustive with 0.85 threshold (current behavior)
- pgvector migration: transparent performance boost
- No API changes for ingestion endpoints

### Negative

❌ **pgvector Dependency**
- Requires PostgreSQL extension installation
- Adds operational complexity (index maintenance)
- Migration effort for existing embeddings

❌ **Configuration Complexity**
- Users must understand strategy trade-offs
- Wrong configuration could hurt deduplication quality
- Requires documentation and guidance

❌ **Degree Calculation Overhead**
- Must calculate/cache degree centrality
- May need periodic recalculation as graph evolves
- Additional query complexity

### Neutral

⚠️ **No Per-Job Override**
- Simplifies implementation (consistency)
- May need future ADR if use cases demand flexibility
- Current decision: wait for actual need

⚠️ **Strategy Selection Guidance**
- Need metrics to recommend strategy per graph size
- "10k concepts" thresholds are estimates
- Real-world tuning required

## Implementation Sequence

### Phase 1: pgvector Foundation
1. Add pgvector extension to PostgreSQL
2. Add `embedding_vec` vector column
3. Migrate existing embeddings: `embedding::vector`
4. Create IVFFlat index with cosine distance
5. Update `vector_search()` to use pgvector
6. Measure performance improvement

### Phase 2: Database Configuration
1. Create `concept_match_config` table with migration
2. Insert default configuration (exhaustive)
3. Implement `ConceptMatchConfig` dataclass
4. Add configuration loading with caching
5. Create operator CLI commands
6. Test configuration hot-reload

### Phase 3: Degree Centrality Helpers
1. Implement inline degree calculation (following ADR-071 pattern)
2. Implement `get_degree_threshold()` for percentile filtering
3. Test degree queries with various graph sizes
4. No caching needed - calculate on-demand in Cypher
5. Document performance characteristics

### Phase 4: Search Strategies
1. Implement `vector_search_with_strategy()` dispatcher
2. Implement exhaustive strategy (pgvector only)
3. Implement degree_only strategy (pgvector + filter)
4. Implement degree_biased strategy (epsilon-greedy)
5. Add strategy enum and validation
6. Test all three strategies with real corpus

### Phase 5: API Endpoints
1. Create `GET /admin/concept-match/config`
2. Create `GET /admin/concept-match/strategies`
3. Create `POST /admin/concept-match/config`
4. Add request/response Pydantic models
5. Add authentication (admin-only endpoints)
6. Test configuration updates and reload

### Phase 6: Ingestion Integration
1. Update `process_chunk()` to load configuration
2. Pass configuration to `vector_search_with_strategy()`
3. Test ingestion with all three strategies
4. Measure deduplication quality (hit rate)
5. Document strategy recommendations
6. Update CLAUDE.md with new workflow

### Phase 7: Monitoring & Tuning
1. Add telemetry for search times per strategy
2. Add metrics for deduplication hit rate
3. Create dashboard for configuration impact
4. Document tuning guidelines
5. Gather real-world performance data
6. Write operational runbook

## Evidence-Aware Matching (Future)

This ADR leaves room for ADR-073 (Evidence-Aware Concept Matching) which will add:

```python
evidence_weight: Optional[float] = None  # Reserved for future use
```

**When evidence_weight is set:**
```python
# Concept similarity (current)
concept_sim = cosine(new_concept_emb, existing_concept_emb)

# Evidence similarity (ADR-073, future)
evidence_chunks = get_source_chunks_for_concept(concept_id)
evidence_sim = max([cosine(new_concept_emb, chunk_emb) for chunk in evidence_chunks])

# Ensemble score
final_score = (1 - evidence_weight) * concept_sim + evidence_weight * evidence_sim
```

This requires ADR-068 (Source Text Embeddings) to be implemented first.

## Alternatives Considered

### Option A: Per-Job Configuration Override

**Pros:** Maximum flexibility, users tune per ingestion
**Cons:** Complexity, inconsistency, hard to reason about graph evolution
**Decision:** Rejected - Database-first for simplicity and consistency

### Option B: Automatic Strategy Selection

**Pros:** System auto-selects based on graph size
**Cons:** Magic behavior, unclear to users, hard to debug
**Decision:** Rejected - Explicit configuration with operator CLI

### Option C: Only Add pgvector (No Strategies)

**Pros:** Simpler, less code
**Cons:** Misses opportunity to apply ADR-071 lessons
**Decision:** Rejected - Degree-biased search proven valuable

### Option D: Embedding Model in Configuration

**Pros:** Could switch embedding models
**Cons:** Breaks existing embeddings, requires full regeneration
**Decision:** Rejected - Embedding model separate concern (ADR-041)

## Related ADRs

- **[ADR-041: AI Extraction Provider Configuration](../ai-embeddings/ADR-041-ai-extraction-config.md)** - Database-first configuration pattern
- **[ADR-049: Rate Limiting and Concurrency](../ai-embeddings/ADR-049-rate-limiting-and-concurrency.md)** - Per-provider semaphores and configuration
- **[ADR-068: Source Text Embeddings](../ai-embeddings/ADR-068-source-text-embeddings.md)** - Future: Evidence-aware matching
- **[ADR-071: Parallel Graph Query Optimization](../query-search/ADR-071-parallel-graph-queries.md)** - Epsilon-greedy degree-biased search pattern
- **[ADR-071a: Parallel Implementation Findings](../query-search/ADR-071a-parallel-implementation-findings.md)** - Discovery that query optimization > parallelization

## References

- **pgvector:** https://github.com/pgvector/pgvector
- **PostgreSQL Vector Extension:** https://www.postgresql.org/docs/current/indexes-types.html
- **IVFFlat Index:** https://github.com/pgvector/pgvector#ivfflat
- **Cosine Distance Operator:** https://github.com/pgvector/pgvector#distance-operators

---

**Last Updated:** 2025-12-04
**Next Steps:** Review with stakeholders, validate approach, begin Phase 1 implementation
