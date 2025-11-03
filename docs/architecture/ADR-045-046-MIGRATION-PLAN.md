# Migration Plan: ADR-045/046 Implementation

**Date:** 2025-10-25
**Branch:** `refactor/embedding-grounding-system`
**Risk Level:** HIGH (affects core vocabulary and embedding infrastructure)

## Overview

This migration plan implements the ADR-044/045/046 trio for embedding-based grounding and vocabulary management. The implementation is methodical to minimize risk of breaking the production system.

## Migration Files Created

| File | ADR | Purpose | Risk Level |
|------|-----|---------|------------|
| `011_add_grounding_metrics.sql` | ADR-046 | Add grounding contribution metrics to vocabulary table | LOW |
| `012_add_embedding_worker_support.sql` | ADR-045 | Add embedding generation infrastructure | MEDIUM |

## Implementation Order

### Phase 1: Schema Migrations (Current)

**Status:** Planning complete, migrations written
**Risk:** LOW - Additive changes only, no breaking modifications

1. **Apply Migration 011:** Grounding Metrics
   ```bash
   ./scripts/database/migrate-db.sh
   # Applies: 011_add_grounding_metrics.sql
   ```

   **Changes:**
   - Adds columns to `relationship_vocabulary`: `grounding_contribution`, `last_grounding_calculated`, `avg_confidence`, `semantic_diversity`
   - Creates `synonym_clusters` table for tracking detected synonyms
   - Creates indexes for grounding queries
   - Creates placeholder functions (implemented later in Python)

   **Validation:**
   ```sql
   -- Verify new columns exist
   \d kg_api.relationship_vocabulary

   -- Verify synonym_clusters table
   \d kg_api.synonym_clusters

   -- Check migration recorded
   SELECT * FROM public.schema_migrations WHERE version = 11;
   ```

2. **Apply Migration 012:** Embedding Worker Support
   ```bash
   ./scripts/database/migrate-db.sh
   # Applies: 012_add_embedding_worker_support.sql
   ```

   **Changes:**
   - Creates `embedding_generation_jobs` table for job tracking
   - Creates `system_initialization_status` table for cold start tracking
   - Adds `embedding_quality_score` and `embedding_validation_status` columns to vocabulary
   - Creates helper views: `v_builtin_types_missing_embeddings`, `v_types_needing_embedding_regeneration`
   - Creates helper functions: `mark_embeddings_stale_for_model()`, `validate_embedding()`
   - Creates trigger: `trigger_validate_vocabulary_embedding` for automatic validation

   **Validation:**
   ```sql
   -- Verify tables
   \d kg_api.embedding_generation_jobs
   \d kg_api.system_initialization_status

   -- Verify views
   SELECT COUNT(*) FROM kg_api.v_builtin_types_missing_embeddings;
   -- Should return ~30 (builtin types without embeddings)

   -- Check migration recorded
   SELECT * FROM public.schema_migrations WHERE version = 12;
   ```

### Phase 2: Python Implementation (Next)

**Status:** Not started
**Risk:** MEDIUM - New service that could affect ingestion pipeline

1. **Implement EmbeddingWorker Service**
   - File: `src/api/services/embedding_worker.py`
   - Dependencies: `age_client.py`, `ai_providers.py`
   - Key methods:
     - `initialize_builtin_embeddings()` - Cold start
     - `generate_vocabulary_embedding()` - Single type
     - `batch_generate_embeddings()` - Bulk operation
     - `validate_embedding()` - Quality checks

   **Testing:**
   ```bash
   # Start API in test mode
   ./scripts/services/start-api.sh

   # Test cold start initialization
   curl http://localhost:8000/admin/embeddings/initialize

   # Verify embeddings generated
   kg vocab list --with-embeddings
   ```

2. **Integrate EmbeddingWorker into Startup**
   - File: `src/api/main.py`
   - Add startup event handler
   - Call `embedding_worker.initialize_builtin_embeddings()` if needed

   **Testing:**
   ```bash
   # Restart API and check logs
   ./scripts/services/stop-api.sh && ./scripts/services/start-api.sh
   tail -f logs/api_*.log | grep -i "embedding"

   # Should see: "Cold start: Generated embeddings for 30 builtin types"
   ```

### Phase 3: Grounding Strength Calculation (After Phase 2)

**Status:** Not started
**Risk:** MEDIUM - New calculation logic in query paths
**Depends on:** Phase 2 (requires embeddings for all vocabulary)

1. **Implement Grounding Calculation in AGEClient**
   - File: `src/api/lib/age_client.py`
   - New method: `calculate_grounding_strength_semantic(concept_id: str) -> float`
   - Uses embedding similarity to SUPPORTS/CONTRADICTS prototypes

   **Testing:**
   ```python
   # Unit test
   from src.api.lib.age_client import AGEClient

   client = AGEClient()
   grounding = client.calculate_grounding_strength_semantic("concept-123")
   assert 0.0 <= grounding <= 1.0
   ```

2. **Update API Models**
   - File: `src/api/models/queries.py`
   - Add `grounding_strength` field to `ConceptDetailsResponse`
   - Add `grounding_strength` field to `ConceptSearchResult` (optional)

3. **Update API Routes**
   - File: `src/api/routes/queries.py`
   - Update `/query/concepts/{concept_id}` to include grounding
   - Add query parameter `include_grounding` for search endpoints

   **Testing:**
   ```bash
   # Test concept details with grounding
   curl http://localhost:8000/query/concepts/concept-123

   # Should include: "grounding_strength": 0.75
   ```

### Phase 4: Enhanced Vocabulary Scorer (After Phase 3)

**Status:** Not started
**Risk:** LOW - New admin functionality, doesn't affect ingestion

1. **Implement Enhanced VocabularyScorer**
   - File: `src/api/lib/vocabulary_manager.py`
   - Update `EdgeTypeScore` dataclass with new metrics
   - Implement `calculate_grounding_contribution()`
   - Implement `detect_synonym_clusters()`
   - Implement `get_extraction_vocabulary()` for dynamic curation

   **Testing:**
   ```bash
   # Test grounding contribution calculation
   kg vocab analyze --calculate-grounding

   # Test synonym detection
   kg vocab synonyms detect --threshold 0.85

   # Test curated extraction vocabulary
   kg vocab extract-list --limit 50
   ```

2. **Update Merge System**
   - File: `src/api/lib/age_client.py`
   - Update `merge_edge_types()` to handle embeddings
   - Ensure target type has embedding before merge
   - Store deprecated embedding for rollback

   **Testing:**
   ```bash
   # Test merge with embedding preservation
   kg vocab merge SUPPORTED_BY SUPPORTS --reason "Inverse synonym"

   # Verify embedding transferred
   kg vocab details SUPPORTS
   ```

## Data Migration Requirements

### Cold Start: Initialize Builtin Embeddings

**Timing:** After Phase 2 implementation
**Method:** Automatic on API startup
**Duration:** ~30 seconds (30 types × 1 second each)

```python
# Triggered automatically by startup event in main.py
# Or manually via admin endpoint:

POST /admin/embeddings/initialize
```

**Expected Results:**
```json
{
  "job_id": "uuid-here",
  "job_type": "cold_start",
  "target_count": 30,
  "status": "completed",
  "processed_count": 30,
  "failed_count": 0,
  "duration_ms": 28450
}
```

### Grounding Metrics: Initial Calculation

**Timing:** After Phase 3 implementation
**Method:** Manual trigger via admin endpoint
**Duration:** Variable (depends on graph size)

```bash
# Calculate grounding contribution for all active types
POST /admin/vocabulary/calculate-grounding
```

**Expected Results:**
- `grounding_contribution` populated for all active types
- `last_grounding_calculated` timestamp set
- `synonym_clusters` table populated with detected clusters

## Rollback Procedures

### Rollback Phase 1 (Schema Migrations)

If migrations cause issues, rollback is **NOT RECOMMENDED** because:
- Migrations are additive (new columns, tables, indexes)
- No existing functionality broken
- Rolling back loses new data

**If absolutely necessary:**
```bash
# Manual rollback (no automated script)
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph

BEGIN;

-- Remove migration 012
DROP TRIGGER IF EXISTS trigger_validate_vocabulary_embedding ON kg_api.relationship_vocabulary;
DROP FUNCTION IF EXISTS kg_api.auto_validate_vocabulary_embedding();
DROP FUNCTION IF EXISTS kg_api.validate_embedding(JSONB, INTEGER);
DROP FUNCTION IF EXISTS kg_api.mark_embeddings_stale_for_model(VARCHAR);
DROP VIEW IF EXISTS kg_api.v_types_needing_embedding_regeneration;
DROP VIEW IF EXISTS kg_api.v_builtin_types_missing_embeddings;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS embedding_validation_status;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS embedding_quality_score;
DROP TABLE IF EXISTS kg_api.system_initialization_status;
DROP TABLE IF EXISTS kg_api.embedding_generation_jobs;
DELETE FROM public.schema_migrations WHERE version = 12;

-- Remove migration 011
DROP FUNCTION IF EXISTS kg_api.calculate_type_grounding_contribution(VARCHAR);
DROP INDEX IF EXISTS kg_api.idx_synonym_clusters_merge_recommended;
DROP INDEX IF EXISTS kg_api.idx_synonym_clusters_active;
DROP TABLE IF EXISTS kg_api.synonym_clusters;
DROP INDEX IF EXISTS kg_api.idx_vocab_grounding_staleness;
DROP INDEX IF EXISTS kg_api.idx_vocab_grounding_contribution;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS semantic_diversity;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS avg_confidence;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS last_grounding_calculated;
ALTER TABLE kg_api.relationship_vocabulary DROP COLUMN IF EXISTS grounding_contribution;
DELETE FROM public.schema_migrations WHERE version = 11;

COMMIT;
```

### Rollback Phase 2-4 (Python Implementation)

**Simpler approach:** Revert to main branch
```bash
# Stop API
./scripts/services/stop-api.sh

# Switch back to main
git checkout main

# Restart API
./scripts/services/start-api.sh
```

**Note:** Schema changes remain in database but are unused by main branch code.

## Testing Strategy

### Pre-Migration Testing

1. **Backup Database:**
   ```bash
   # Create backup before migrations
   docker exec knowledge-graph-postgres pg_dump -U admin -d knowledge_graph > backup_pre_migration.sql
   ```

2. **Verify Current State:**
   ```bash
   kg database stats
   kg vocab list
   ```

### Post-Migration Testing

1. **Schema Validation:**
   ```bash
   # Run migration
   ./scripts/database/migrate-db.sh -y

   # Verify schema
   docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "\d kg_api.relationship_vocabulary"
   ```

2. **Functional Testing:**
   ```bash
   # Test existing functionality still works
   kg search query "test query"
   kg database stats
   kg vocab list

   # Test new views (should work even before Python implementation)
   docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
     "SELECT COUNT(*) FROM kg_api.v_builtin_types_missing_embeddings;"
   ```

3. **Integration Testing:**
   ```bash
   # Test full ingestion pipeline
   kg ontology delete "Migration Test"
   kg ingest file -o "Migration Test" -y ingest_source/watts_lecture_1.txt

   # Verify no errors in logs
   tail -f logs/api_*.log | grep -i error
   ```

## Success Criteria

### Phase 1 Complete When:
- ✅ Migrations 011 and 012 applied successfully
- ✅ Schema validation passes
- ✅ Existing ingestion pipeline works
- ✅ No errors in API logs
- ✅ Database backup created

### Phase 2 Complete When:
- ✅ EmbeddingWorker service implemented
- ✅ Cold start initializes 30 builtin embeddings
- ✅ `kg vocab list` shows all types have embeddings
- ✅ Admin endpoints functional
- ✅ Unit tests pass

### Phase 3 Complete When:
- ✅ Grounding strength calculation works
- ✅ API returns grounding_strength in responses
- ✅ MCP tools expose grounding data
- ✅ Integration tests pass

### Phase 4 Complete When:
- ✅ Enhanced vocabulary scorer operational
- ✅ Synonym detection works
- ✅ Merge system handles embeddings
- ✅ Dynamic vocabulary curation functional

## Risk Mitigation

### High-Risk Areas

1. **Embedding Generation During Ingestion**
   - **Risk:** EmbeddingWorker integration could break ingestion
   - **Mitigation:** Extensive testing with sample documents before production use
   - **Fallback:** Keep existing `generate_embedding()` calls as backup

2. **Database Performance**
   - **Risk:** New indexes and triggers could slow operations
   - **Mitigation:** Monitor query performance before/after
   - **Fallback:** Drop problematic indexes if needed

3. **Model Changes**
   - **Risk:** Changing embedding model invalidates all embeddings
   - **Mitigation:** `mark_embeddings_stale_for_model()` function tracks this
   - **Fallback:** Regeneration job system handles bulk updates

## Timeline Estimate

- **Phase 1 (Schema):** 1-2 hours (including testing)
- **Phase 2 (EmbeddingWorker):** 8-12 hours (implementation + testing)
- **Phase 3 (Grounding):** 8-12 hours (implementation + testing)
- **Phase 4 (Vocabulary):** 12-16 hours (implementation + testing)

**Total:** 29-42 hours over 1-2 weeks

## Approval Required Before Phase 2

Before proceeding to Phase 2 implementation:
- [ ] Review migration files (011, 012)
- [ ] Test migrations on development database
- [ ] Verify backup procedures
- [ ] Confirm no production impact from schema changes
- [ ] Get explicit approval to proceed with Python implementation

---

**Next Steps:**

1. Review this migration plan
2. Apply migrations 011 and 012 to development database
3. Test schema changes thoroughly
4. Get approval before Phase 2 implementation
