# ADR-081 Implementation Todo List

**Branch:** `feature/adr-081-source-lifecycle`
**PR:** Pending
**Date:** 2025-12-13

## Completed

- [x] Draft ADR-080 (Garage service refactor)
- [x] Draft ADR-081 (Source document lifecycle)
- [x] Peer review ADR-081 refinements
  - Knowledge Keeper mental model
  - 128-bit hash (UUID-equivalent)
  - Model Evolution Insurance rationale
  - YAGNI for Graph→Garage reconstruction
- [x] Refactor GarageClient into modular services (#176)
  - `api/api/lib/garage/base.py`
  - `api/api/lib/garage/image_storage.py`
  - `api/api/lib/garage/projection_storage.py`
  - `api/api/lib/garage/source_storage.py`
  - `api/api/lib/garage/retention.py`
  - Backward-compatible wrapper in `__init__.py`
- [x] Phase 1: Pre-Ingestion Storage
  - Integrated `SourceDocumentService` into `ingestion_worker.py`
  - Stores document BEFORE chunking
  - Passes `garage_key` and `content_hash` to Source nodes
- [x] Phase 2: Schema Changes (Source nodes)
  - Added `garage_key`, `content_hash` to Source nodes
  - Added `char_offset_start`, `char_offset_end` for offset tracking
  - Added `chunk_index` (0-indexed) for ordering
- [x] Phase 2b: DocumentMeta Enhancement
  - Added `garage_key` to DocumentMeta node (ADR-081)
  - Reuses existing DocumentMeta (ADR-051) rather than creating new Document type
  - Complete linkage: DocumentMeta(garage_key) → Source(garage_key, offsets) → Garage
- [x] Phase 2c: Hash Format Consistency
  - Fixed inconsistency: ContentHasher uses "sha256:abc..." but Garage uses raw "abc..."
  - Added `normalize_content_hash()` helper to strip prefix
  - Added `precomputed_hash` parameter to `compute_identity()` and `store()`
  - Worker now reuses hash from dedup check (avoids recomputing SHA-256)

## Remaining

### Phase 3: Deduplication
- [x] Exact-match deduplication (hash check) — **Already implemented** via ContentHasher + DocumentMeta
- [~] ~~Similarity-based deduplication (embedding comparison)~~ — **DEFERRED** (see rationale below)
- [ ] Add force override with versioning
- [ ] Update API to return dedup warnings

## Deferred: Similarity-Based Document Deduplication

**Decision:** Do NOT implement document-level similarity detection.

**Rationale:**
1. **Concept-level dedup is the unique strength** — The graph already deduplicates
   semantically at the concept level during ingestion. Each concept is matched against
   existing concepts via embedding similarity. This is where semantic understanding happens.

2. **Wrong layer for intelligence** — Document-level similarity tries to be smart at
   the file level instead of the knowledge level. We're not building MS GraphRAG.

3. **Scope creep risk** — Opens a can of worms: embeddings, thresholds, batch latency,
   approximate vs exact, etc. High effort, low unique value.

4. **Hash exact-match is sufficient** — True duplicates (same bytes) are already caught.
   Near-duplicates (formatting changes, typo fixes) are rare edge cases. If they occur,
   the concept-level matching handles semantic overlap anyway.

5. **Latency concern** — Similarity check requires embedding before decision, adding
   ~100-500ms latency per document. For batch uploads this compounds badly.

**What we have instead:**
- Hash-based exact match (fast, via ContentHasher → DocumentMeta)
- Concept-level semantic deduplication (during ingestion)
- Time-based policy (allow re-ingest after 30 days)

### Phase 4: Regeneration
- [ ] Implement Garage → Graph regeneration ("new keeper" scenario)
- [ ] Add admin endpoints for recovery operations
- [ ] Add dry-run mode for cost estimation

### Phase 5: Deletion (Optional)
- [ ] Implement cascade deletion
- [ ] Add orphan cleanup
- [ ] Document the "forgetting" workflow

## References

- ADR-080: Garage Service Architecture
- ADR-081: Source Document Lifecycle
- Issue #172: Expand Garage storage
- Issue #175: Refactor GarageClient (SRP)
- ADR-069: Semantic FUSE Filesystem (enabled by this work)
