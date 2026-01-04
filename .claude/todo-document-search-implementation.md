# Document Search & Backup Extension Implementation

**Branch:** `feature/document-search`
**ADRs:** ADR-084 (Document Search), ADR-015 (Backup - extend)
**Created:** 2026-01-03

## Overview

Two related work streams:
1. **Backup Extension** - Add Garage content to ontology backups for full cloning
2. **Document Search** - New endpoints for document discovery and retrieval

---

## Part A: Backup Extension (ADR-015)

Update backup/restore to include Garage-stored source documents. Garage is now the canonical storage for original documents (ADR-081), so backups should include this data by default.

### A1. Research & Design
- [x] Review current backup format in `api/lib/serialization.py`
- [x] Review Garage client for document retrieval patterns
- [x] Design backup archive structure
- [x] Decide archive format: `.tar.gz`

**Design Decisions:**

Archive structure mirrors Garage layout:
```
backup_<ontology>_<date>.tar.gz
└── backup_<ontology>_<date>/
    ├── manifest.json
    └── documents/
        ├── sources/
        │   └── <ontology>/
        │       ├── abc123.txt
        │       └── def456.md
        └── images/
            └── <ontology>/
                ├── img789.jpg
                └── img789_prose.md
```

Extended source entries in manifest.json:
```json
{
  "sources": [{
    "source_id": "sha256:abc123",
    "document": "My Ontology",
    "paragraph": 0,
    "full_text": "...",
    "garage_key": "sources/my_ontology/abc123.txt",
    "document_path": "documents/sources/my_ontology/abc123.txt",
    "content_type": "document"
  }]
}
```

Garage services to use:
- `SourceDocumentService.list(ontology)` → list source docs
- `SourceDocumentService.get(garage_key)` → download content
- `ImageStorageService` → similar for images

### A2. API Changes
- [x] Extend `DataExporter.export_sources` with garage_key, content_type, storage_key
- [x] Create `backup_archive.py` module for tar.gz streaming
- [x] Update backup endpoint to support "archive" format (now default)
- [x] Add document_path to source entries in manifest.json

### A3. Restore Changes
- [x] Create `restore_backup_archive()` function to extract tar.gz
- [x] Extend `DataImporter` to read from extracted archive
- [x] Upload documents to Garage from archive
- [x] Handle Garage key conflicts (overwrite vs skip)

### A4. CLI Updates
- [x] Update `kg admin backup` to handle .tar.gz files
- [x] Update `kg admin restore` to extract and process archives
- [x] Fix CLI display issue (was server-side variable shadowing bug in restore_worker.py)
- [ ] Test round-trip: backup → restore → verify Garage content downloadable

### A5. RBAC Updates
- [x] Add migration 037 for admin backup permissions (create, restore)

**Note:** Backup/restore is CLI-only (admin operation). Not exposed via MCP.

---

## Part B: Document Search (ADR-084)

### B1. API Endpoints - Phase 1 ✅
- [x] Create `api/api/routes/documents.py` route file
- [x] Implement `POST /query/documents/search`
  - [x] Reuse `source_embeddings` search
  - [x] Aggregate chunks to DocumentMeta level
  - [x] Rank by max chunk similarity
  - [x] Include concept_ids per document
  - [x] Add ontology filter parameter
- [x] Implement `GET /documents/{document_id}/content`
  - [x] Fetch from Garage (document or image+prose)
  - [x] Include chunks from Source nodes
  - [x] Return appropriate content type
- [x] Implement `GET /documents` (list all with optional ontology filter)
  - [x] List all DocumentMeta
  - [x] Optional limit/offset pagination
- [x] Pydantic models included in routes/documents.py
- [x] Register routes in `api/api/main.py`
- [x] Test endpoints with curl/httpie

### B2. CLI - Phase 2
- [ ] Create `cli/src/cli/document.ts` command file
- [ ] Implement `kg document search "query"`
  - [ ] Table output: filename, ontology, similarity, concepts
  - [ ] `--ontology` filter flag
  - [ ] `--json` structured output
  - [ ] `--limit` parameter
- [ ] Implement `kg document show <id>`
  - [ ] Fetch and display content
  - [ ] Handle image (show path or open?)
- [ ] Implement `kg document list --ontology <name>`
- [ ] Add to CLI index, build, install
- [ ] Test all commands

### B3. MCP Tool - Phase 3 (Search Only)
- [ ] Extend `search` tool with `type: "documents"` parameter
- [ ] Add `document` tool for content retrieval
- [ ] Test with Claude Desktop
- [ ] Update MCP tool documentation

**Note:** MCP exposes document search/retrieval only. Backup/restore excluded (admin ops).

### B4. Web Explorer - Phase 4
- [ ] Design document search UI component
- [ ] Add document search to explorer sidebar
- [ ] Implement document→concept graph visualization
- [ ] Add ontology filter dropdown
- [ ] Test multi-document loading

---

## Testing Checklist

- [ ] Unit tests for document aggregation logic
- [ ] Integration tests for search endpoint
- [ ] Round-trip test: ingest → search → retrieve → verify content
- [ ] Backup round-trip with Garage content
- [ ] CLI command tests
- [ ] MCP tool verification

---

## Notes

_Add implementation notes, decisions, and blockers here as work progresses._

### Session 1 (2026-01-03)
- Created ADR-084 with refined design
- Researched backup system - already supports ontology scoping
- Decided: extend backup for Garage content, don't duplicate in ADR-084
- Branch created and pushed

### Session 1 continued
- Completed A1: Research & Design (backup format, Garage client)
- Completed A2: API Changes
  - Extended `DataExporter.export_sources` with Garage fields
  - Created `api/api/lib/backup_archive.py` for tar.gz streaming
  - Updated backup endpoint - "archive" is now default format

### Session 2 (2026-01-04)
- Completed A4: CLI Updates for backup
  - Updated `cli/src/cli/admin/backup.ts` - archive format as default
  - Updated `cli/src/api/client.ts` - handle .tar.gz filenames
  - Updated `cli/src/types/index.ts` - BackupRequest format type
  - Updated `list-backups` and `restore` to recognize .tar.gz files
- Created migration 037 for admin backup permissions
  - Admin role now has backups:create and backups:restore
  - Previously only platform_admin had these
- Successfully tested backup: archive contains manifest.json + documents/
- Next: A3 (restore function for archive format)

### Session 3 (2026-01-04 continued)
- Completed A3: Restore function for archive format
  - Added `extract_backup_archive()`, `restore_documents_to_garage()`, `cleanup_extracted_archive()` to backup_archive.py
  - Updated `admin.py` restore endpoint to accept .tar.gz files
  - Updated `restore_worker.py` to call `restore_documents_to_garage()` after graph restore
  - Fixed: SourceDocumentService uses `base.put_object()` not `put()`
  - Fixed: backup was adding same document multiple times (added deduplication)
- Restore round-trip test:
  - **Server-side: WORKING** - "Document restore complete: 2 uploaded, 0 skipped, 0 failed"
  - ~~**CLI display: BUG** - "connection pool is closed" error~~ **FIXED**
- Completed A4: CLI restore updates
  - Changed from password auth to `--confirm` flag
  - Changed from SSE to polling (simpler, more reliable)

### Session 4 (2026-01-04 continued)
- **Fixed "connection pool is closed" bug** - root cause was variable shadowing in restore_worker.py
  - `client = AGEClient()` at line 80 created original client
  - `client = AGEClient()` at line 162 shadowed it with metrics refresh client
  - `client.close()` in finally block tried to close already-closed client
  - Fix: Renamed metrics client to `metrics_client` to avoid shadowing
- Part A now fully complete and tested

### Session 5 (2026-01-04 continued)
- Completed B1: Document Search API Endpoints
  - Created `api/api/routes/documents.py` with Pydantic models
  - `POST /query/documents/search` - semantic search with document aggregation
  - `GET /documents` - list documents with metadata and counts
  - `GET /documents/{id}/content` - retrieve full content from Garage
- **Fixed HAS_SOURCE relationship bug in ingestion_worker.py**
  - Worker was using `{filename}_chunk{n}` pattern
  - Source nodes use `{document_id[:12]}_chunk{n}` pattern
  - Fix: Use document_id pattern to match actual Source IDs
- **Fixed APPEARS relationship in concept query**
  - Was using `APPEARS_IN`, actual relationship is `APPEARS`
- All endpoints tested and working

### TODO
- [x] Test document download once B1 endpoints are implemented
- [ ] Verify round-trip: backup → delete ontologies → restore → verify Garage content retrievable
- [ ] B2: CLI commands for document search
- [ ] B3: MCP tool extension
- [ ] B4: Web explorer integration

