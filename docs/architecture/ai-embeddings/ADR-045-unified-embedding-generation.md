# ADR-045: Unified Embedding Generation System

**Status:** Proposed
**Date:** 2025-10-25
**Authors:** System Architecture Team
**Related:** ADR-044 (Probabilistic Truth Convergence), ADR-046 (Grounding-Aware Vocabulary Management), ADR-039 (Embedding Configuration), ADR-032 (Vocabulary Expansion)

## Overview

Here's a problem that sneaks up on you: your knowledge graph has 30 built-in relationship types (SUPPORTS, CONTRADICTS, IMPLIES, etc.), hundreds of concepts with embeddings, and a new vocabulary system that auto-generates edge types. But when you actually check the database, you discover that those 30 built-in relationship types have zero embeddings. None. They were never generated because there was no code path to create them at system initialization.

This matters because ADR-044's grounding calculation depends on comparing relationship embeddings—measuring how semantically similar an edge type is to SUPPORTS versus CONTRADICTS. Without embeddings for the core vocabulary, grounding calculation simply can't work. You've built a car with no engine.

The root cause is that embedding generation happens in three completely separate places: concepts get embeddings during ingestion, user-created relationship types get embeddings when they're added to the vocabulary, and built-in types... well, they were supposed to get embeddings somehow, but nobody implemented it. There's no cold start initialization, no unified system for regenerating embeddings when you switch from OpenAI to a local model, and no way to verify that all the pieces have embeddings before running grounding calculations.

This ADR creates a unified EmbeddingWorker service that handles all embedding generation across the system—concepts, vocabulary types, and cold start initialization. Think of it like centralizing your payment processing: instead of having separate code for credit cards, PayPal, and cryptocurrency scattered across your app, you have one payment service with a consistent interface. The same principle applies here: all embeddings flow through one worker, making operations like "regenerate all embeddings with the new model" trivial instead of requiring coordinated updates to three different subsystems.

---

## Context

### The ADR-044/045/046 Trio

This ADR is part of a three-part system for truth convergence in the knowledge graph:

| ADR | Focus | Purpose |
|-----|-------|---------|
| **ADR-044** | **Theory** | Probabilistic truth convergence through grounding strength |
| **ADR-045** | **Storage** | Unified embedding generation infrastructure |
| **ADR-046** | **Management** | Vocabulary lifecycle with grounding awareness |

**Implementation Order:** ADR-045 (this) → ADR-044 → ADR-046

This ADR provides the embedding infrastructure that ADR-044 depends on for grounding strength calculations and that ADR-046 uses for synonym detection and vocabulary curation.

---

### The Problem: Scattered Embedding Generation

Embedding generation currently occurs in multiple disconnected locations:

1. **Concept embeddings** - Generated during ingestion (`llm_extractor.py`)
2. **Vocabulary type embeddings** - Generated when adding new types (`vocabulary_manager.py`)
3. **Builtin type embeddings** - **Not generated at all** (0/30 have embeddings)
4. **Model migration** - No unified way to regenerate all embeddings when model changes

**Current state analysis (2025-10-25):**
```sql
SELECT is_builtin, COUNT(*) as total,
       SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embeddings
FROM kg_api.relationship_vocabulary
GROUP BY is_builtin;

-- Results:
-- is_builtin | total | with_embeddings
-- -----------+-------+-----------------
-- f          |    34 |              34  ← LLM-generated: 100% coverage
-- t          |    30 |               0  ← Builtin: 0% coverage
```

**Why this matters for ADR-044:**

ADR-044 (Probabilistic Truth Convergence) proposes **embedding-based grounding strength calculation** that requires:
- All relationship types to have embeddings
- Ability to calculate semantic similarity between edge types
- Consistent embedding model across all types

Without unified embedding generation, ADR-044 cannot be implemented.

### The Architectural Gap

Current system has **four separate embedding paths:**

**Path 1: Concept node embeddings (ingestion)**
```python
# src/api/lib/llm_extractor.py
def generate_embedding(text: str, provider_name: Optional[str] = None):
    provider = get_provider(provider_name)
    return provider.generate_embedding(text)
```

**Path 2: Vocabulary type embeddings (auto-generation on add)**
```python
# src/api/lib/age_client.py
def add_edge_type(..., ai_provider=None):
    # ... add type to vocabulary table ...
    if ai_provider is not None:
        embedding = ai_provider.generate_embedding(descriptive_text)
        # Store in vocabulary table
```

**Path 3: Bulk vocabulary regeneration (manual)**
```python
# src/api/lib/age_client.py
def generate_vocabulary_embeddings(ai_provider, force_regenerate=False):
    # Bulk regenerate embeddings for vocabulary types
```

**Path 4: Missing - Cold start initialization**
```python
# Does not exist!
# Need: Initialize embeddings for builtin types on first run
```

### Use Cases Requiring Unified Approach

1. **Cold start** - Fresh database with 30 builtin types, 0 embeddings
2. **Ingestion** - Generate embeddings for newly extracted concepts
3. **Vocabulary expansion** - Generate embeddings for new LLM-created edge types
4. **Model migration** - Operator changes from `text-embedding-ada-002` to `nomic-embed-text`
5. **Embedding verification** - Ensure all nodes/edges have embeddings before grounding calculation

## Decision

### Implement Unified Embedding Worker

Create a centralized `EmbeddingWorker` service that handles **all embedding generation** across the system.

### Core Architecture

```python
# src/api/services/embedding_worker.py

class EmbeddingWorker:
    """
    Unified embedding generation service.

    Handles embedding generation for:
    - Concept nodes (during ingestion)
    - Vocabulary relationship types (on creation or bulk regeneration)
    - Cold start initialization (builtin types)
    - Model migration (regenerate all embeddings)
    """

    def __init__(self, ai_provider, age_client):
        self.provider = ai_provider
        self.db = age_client

    # ========== Use Case 1: Cold Start Initialization ==========

    def initialize_builtin_embeddings(self) -> Dict[str, int]:
        """
        Generate embeddings for all builtin vocabulary types without embeddings.

        Called during system initialization or after schema migrations.
        Idempotent - safe to call multiple times.

        Returns:
            {"generated": N, "skipped": M, "failed": K}
        """
        return self.db.generate_vocabulary_embeddings(
            ai_provider=self.provider,
            only_missing=True  # Only generate for types without embeddings
        )

    # ========== Use Case 2: Ingestion ==========

    def generate_concept_embedding(self, text: str) -> Dict[str, Any]:
        """
        Generate embedding for concept label during ingestion.

        Used by ingestion pipeline when creating new concepts.

        Returns:
            {"embedding": [...], "model": "text-embedding-ada-002", "tokens": 8}
        """
        return self.provider.generate_embedding(text)

    # ========== Use Case 3: Vocabulary Expansion ==========

    def generate_vocabulary_embedding(self, relationship_type: str) -> bool:
        """
        Generate embedding for a single vocabulary type.

        Called automatically when new edge type is discovered/created.
        Stores embedding in vocabulary table.

        Returns:
            True if generated successfully
        """
        descriptive_text = f"relationship: {relationship_type.lower().replace('_', ' ')}"

        embedding_response = self.provider.generate_embedding(descriptive_text)
        embedding = embedding_response["embedding"]
        model = embedding_response.get("model", "text-embedding-ada-002")

        return self.db.store_embedding(relationship_type, embedding, model)

    # ========== Use Case 4: Model Migration ==========

    def regenerate_all_embeddings(
        self,
        concepts: bool = True,
        vocabulary: bool = True
    ) -> Dict[str, Dict[str, int]]:
        """
        Regenerate ALL embeddings with current embedding model.

        Use when operator changes embedding model in configuration.
        This is a HEAVY operation - can take hours for large graphs.

        Args:
            concepts: Regenerate concept node embeddings (default: True)
            vocabulary: Regenerate vocabulary type embeddings (default: True)

        Returns:
            {
                "concepts": {"generated": N, "failed": K},
                "vocabulary": {"generated": M, "failed": J}
            }
        """
        results = {}

        if vocabulary:
            # Regenerate vocabulary embeddings (fast - only ~64 types)
            results["vocabulary"] = self.db.generate_vocabulary_embeddings(
                ai_provider=self.provider,
                force_regenerate=True  # Force regeneration for all types
            )

        if concepts:
            # Regenerate concept embeddings (slow - could be thousands of concepts)
            results["concepts"] = self._regenerate_concept_embeddings()

        return results

    # ========== Use Case 5: Verification ==========

    def verify_embeddings(self) -> Dict[str, Any]:
        """
        Check embedding coverage across the system.

        Returns diagnostic information about missing embeddings.

        Returns:
            {
                "concepts": {"total": N, "with_embeddings": M, "missing": K},
                "vocabulary": {"total": P, "with_embeddings": Q, "missing": R},
                "embedding_model": "text-embedding-ada-002",
                "ready_for_grounding": True/False
            }
        """
        # Check vocabulary coverage
        vocab_stats = self.db.execute_query("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embeddings,
                   COUNT(*) - SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as missing
            FROM kg_api.relationship_vocabulary
            WHERE is_active = TRUE
        """)

        # Check concept coverage
        concept_stats = self.db._execute_cypher("""
            MATCH (c:Concept)
            WITH count(c) as total,
                 count(c.embedding) as with_embeddings
            RETURN total, with_embeddings, total - with_embeddings as missing
        """, fetch_one=True)

        vocab_ready = vocab_stats[0]["missing"] == 0
        concept_ready = concept_stats["missing"] == 0

        return {
            "concepts": concept_stats,
            "vocabulary": dict(vocab_stats[0]),
            "embedding_model": self.provider.get_embedding_model(),
            "ready_for_grounding": vocab_ready and concept_ready
        }

    def _regenerate_concept_embeddings(self) -> Dict[str, int]:
        """
        Internal: Regenerate embeddings for all concepts in graph.

        This is a heavy operation - processes all concepts.
        Should be run as background job with progress tracking.
        """
        # Get all concepts
        concepts = self.db._execute_cypher("MATCH (c:Concept) RETURN c.concept_id as id, c.label as label")

        generated = 0
        failed = 0

        for concept in concepts:
            try:
                embedding_response = self.provider.generate_embedding(concept["label"])
                embedding = embedding_response["embedding"]

                # Update concept embedding
                self.db._execute_cypher("""
                    MATCH (c:Concept {concept_id: $concept_id})
                    SET c.embedding = $embedding
                """, params={"concept_id": concept["id"], "embedding": embedding})

                generated += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to regenerate embedding for concept {concept['id']}: {e}")

        return {"generated": generated, "failed": failed}
```

### Integration Points

**1. System Initialization (Cold Start)**
```python
# src/api/main.py - FastAPI startup event

@app.on_event("startup")
async def startup_event():
    """Initialize embeddings on system startup if needed."""

    provider = get_provider()
    age_client = AGEClient()
    worker = EmbeddingWorker(provider, age_client)

    # Check if initialization needed
    status = worker.verify_embeddings()

    if not status["ready_for_grounding"]:
        logger.info("Initializing missing embeddings...")
        results = worker.initialize_builtin_embeddings()
        logger.info(f"Embedding initialization: {results}")
```

**2. Ingestion Pipeline**
```python
# src/api/lib/ingestion.py

def ingest_chunk(...):
    # ... existing ingestion logic ...

    # Use unified worker for concept embeddings
    worker = EmbeddingWorker(provider, age_client)
    embedding_response = worker.generate_concept_embedding(concept_label)
```

**3. Vocabulary Expansion**
```python
# src/api/services/vocabulary_manager.py

def add_new_edge_type(self, edge_type: str):
    # Add to vocabulary table
    self.db.add_edge_type(edge_type, category="llm_generated")

    # Generate embedding via unified worker
    worker = EmbeddingWorker(self.ai_provider, self.db)
    worker.generate_vocabulary_embedding(edge_type)
```

**4. Admin Endpoints**
```python
# src/api/routes/admin.py

@router.post("/admin/embeddings/verify")
async def verify_embeddings():
    """Check embedding coverage across system."""
    worker = EmbeddingWorker(get_provider(), get_age_client())
    return worker.verify_embeddings()

@router.post("/admin/embeddings/initialize")
async def initialize_embeddings():
    """Initialize missing embeddings (cold start)."""
    worker = EmbeddingWorker(get_provider(), get_age_client())
    return worker.initialize_builtin_embeddings()

@router.post("/admin/embeddings/regenerate")
async def regenerate_embeddings(concepts: bool = False, vocabulary: bool = True):
    """Regenerate embeddings after model change."""
    worker = EmbeddingWorker(get_provider(), get_age_client())
    return worker.regenerate_all_embeddings(concepts=concepts, vocabulary=vocabulary)
```

### How This Supports ADR-044

**ADR-044 requires:**
1. ✅ All vocabulary types have embeddings
2. ✅ Consistent embedding model across types
3. ✅ Ability to calculate semantic similarity
4. ✅ Support for dynamic vocabulary expansion

**EmbeddingWorker provides:**
1. ✅ Cold start initialization for builtins
2. ✅ Automatic embedding generation for new types
3. ✅ Model migration when config changes
4. ✅ Verification that system is ready for grounding

### Integration with Vocabulary Management (ADR-032)

**Vocabulary merge system needs updates:**

Currently, `merge_edge_types()` in `age_client.py` (lines 1370-1444):
1. Updates graph edges from deprecated → target type
2. Marks deprecated type as inactive
3. Records merge in history

**Missing:** Embedding management during merge

**Required updates:**
```python
def merge_edge_types(self, deprecated_type: str, target_type: str, performed_by: str):
    # Existing logic...
    # UPDATE graph edges
    # MARK deprecated as inactive

    # NEW: Handle embeddings
    # 1. Ensure target type has embedding (generate if missing)
    # 2. Optionally keep deprecated embedding for rollback
    # 3. Invalidate any cached grounding calculations
```

**Rationale:** When merging `SUPPORTED_BY` → `SUPPORTS`:
- Target type (`SUPPORTS`) must have embedding for grounding calculations (ADR-044)
- Deprecated type (`SUPPORTED_BY`) embedding can be preserved as inactive for rollback
- Any cached grounding scores referencing deprecated type should be invalidated

This will be addressed in **Phase 2: Integration** when updating vocabulary_manager.py.

**Grounding calculation workflow:**
```python
# ADR-044 implementation (enabled by ADR-045)

def calculate_grounding_strength_semantic(concept_id: str):
    # Step 1: Verify embeddings ready (ADR-045)
    worker = EmbeddingWorker(provider, age_client)
    status = worker.verify_embeddings()

    if not status["ready_for_grounding"]:
        raise Exception("Embeddings not initialized. Run: POST /admin/embeddings/initialize")

    # Step 2: Get prototype embeddings (ADR-044)
    supports_emb = age_client.get_vocabulary_embedding("SUPPORTS")["embedding"]
    contradicts_emb = age_client.get_vocabulary_embedding("CONTRADICTS")["embedding"]

    # Step 3: Calculate grounding via semantic similarity (ADR-044)
    # ... grounding calculation using embeddings ...
```

## Implementation

### Phase 1: EmbeddingWorker Core (Immediate)

1. Create `src/api/services/embedding_worker.py`
2. Implement core methods:
   - `initialize_builtin_embeddings()`
   - `generate_concept_embedding()`
   - `generate_vocabulary_embedding()`
   - `verify_embeddings()`

### Phase 2: Integration (Week 1)

1. Add startup event to `main.py` for cold start
2. Update ingestion pipeline to use worker
3. Update vocabulary manager to use worker
4. Add admin endpoints

### Phase 3: Model Migration (Week 2)

1. Implement `regenerate_all_embeddings()`
2. Add background job support for heavy regeneration
3. Add progress tracking for concept embedding regeneration

### Phase 4: Enable ADR-044 (Week 3)

1. Verify all embeddings present via `verify_embeddings()`
2. Implement embedding-based grounding strength calculation
3. Integrate into concept details queries

## Consequences

### Positive

✅ **Single source of truth** for embedding generation
✅ **Cold start support** - Fresh databases work immediately
✅ **Model migration** - Can change embedding models safely
✅ **Enables ADR-044** - Grounding calculation requires complete embeddings
✅ **Operator visibility** - Admin can verify/initialize embeddings
✅ **Future-proof** - New embedding use cases go through worker
✅ **Consistent model** - All embeddings use same configured model

### Negative

⚠️ **Migration burden** - Existing code must be updated to use worker
⚠️ **Heavy operations** - Regenerating all concept embeddings is slow
⚠️ **Model lock-in** - All embeddings must use same model (consistency requirement)

### Risks

**Risk:** Model migration on large graphs could take hours
**Mitigation:** Implement as background job with progress tracking and pause/resume

**Risk:** Inconsistent embeddings if migration interrupted
**Mitigation:** Use database transactions, allow resume from checkpoint

**Risk:** Embedding API costs during bulk regeneration
**Mitigation:** Add confirmation step with cost estimate before regeneration

## Alternatives Considered

### 1. Keep Scattered Approach (Rejected)

**Why rejected:**
- Cannot implement ADR-044 (grounding requires complete embeddings)
- Builtin types have 0% embedding coverage
- No way to handle model migrations
- Operator has no visibility into embedding state

### 2. Hard-Code Builtin Embeddings in Schema (Rejected)

**Approach:** Store embeddings as SQL JSONB literals in baseline schema

**Why rejected:**
- Couples schema to specific embedding model
- Makes model migration impossible
- Embedding model should be operator choice, not schema constant
- Violates separation of concerns (data vs configuration)

### 3. Lazy Generation on First Query (Rejected)

**Approach:** Generate embeddings on-demand when first needed

**Why rejected:**
- First query would be very slow (generate 64 embeddings)
- Race conditions if multiple queries start simultaneously
- No way to verify system readiness
- Operator cannot control when API costs are incurred

## References

- **ADR-044:** Probabilistic Truth Convergence (requires embeddings)
- **ADR-039:** Embedding Configuration (model selection)
- **ADR-032:** Automatic Edge Vocabulary Expansion (creates new types)
- **Existing code:** `age_client.generate_vocabulary_embeddings()` (bulk method)

## Validation & Testing

### Test Scenarios

**1. Cold Start Initialization**
- Fresh database with 30 builtin types, 0 embeddings
- Run `initialize_builtin_embeddings()`
- Verify: All 30 builtins now have embeddings
- Verify: `verify_embeddings()` returns `ready_for_grounding: true`

**2. Ingestion with Unified Worker**
- Ingest document, extract concepts
- Verify: Concepts have embeddings generated via worker
- Verify: Embedding model matches configured model

**3. Vocabulary Expansion**
- LLM creates new edge type "FACILITATES"
- Verify: Worker automatically generates embedding
- Verify: Type immediately usable in grounding calculation

**4. Model Migration**
- Change config: `text-embedding-ada-002` → `nomic-embed-text`
- Run `regenerate_all_embeddings(vocabulary=True)`
- Verify: All vocabulary embeddings use new model
- Verify: Grounding calculations use new embeddings

**5. Verification**
- Run `verify_embeddings()`
- Returns: Complete diagnostic information
- Identifies: Any missing embeddings

### Success Criteria

- [ ] All 30 builtin types have embeddings after cold start
- [ ] New concepts get embeddings via worker during ingestion
- [ ] New edge types get embeddings automatically
- [ ] Admin can verify embedding coverage
- [ ] Admin can regenerate embeddings after model change
- [ ] ADR-044 grounding calculation works with complete embeddings

## Implementation Status

- [ ] Phase 1: EmbeddingWorker core implementation
- [ ] Phase 2: Integration with existing systems
- [ ] Phase 3: Model migration support
- [ ] Phase 4: Enable ADR-044 grounding

**Next Steps:**
1. Implement `EmbeddingWorker` class in `src/api/services/embedding_worker.py`
2. Add startup event for cold start initialization
3. Test with fresh database: verify 30 builtin embeddings generated
4. Update ingestion pipeline to use worker
5. Add admin verification endpoint

---

**Last Updated:** 2025-10-25
**Next Review:** After Phase 1 implementation
