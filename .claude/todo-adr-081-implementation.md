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

## Remaining

### Phase 2b: Document Node Type
- [ ] Add Document node type
  - Links to Source nodes via `HAS_CHUNK` relationship
  - Stores document-level metadata
  - `shard_origin` for future provenance

### Phase 3: Deduplication
- [ ] Implement exact-match deduplication (hash check)
- [ ] Implement similarity-based deduplication (embedding comparison)
- [ ] Add force override with versioning
- [ ] Update API to return dedup warnings

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
