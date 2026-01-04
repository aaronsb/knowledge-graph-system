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

Extend existing ontology backup to include Garage-stored original documents.

### A1. Research & Design
- [ ] Review current backup format in `api/api/lib/serialization.py`
- [ ] Review Garage client for document retrieval patterns
- [ ] Design extended backup format (embed base64? separate archive?)
- [ ] Decide: single JSON with embedded content vs tarball with JSON + files

### A2. API Changes
- [ ] Add `include_garage: bool` parameter to backup request model
- [ ] Extend `DataExporter` to fetch Garage documents per ontology
- [ ] Handle image + prose file pairing in export
- [ ] Update backup streaming for larger payloads
- [ ] Add `garage_documents` section to backup format

### A3. Restore Changes
- [ ] Extend `DataImporter` to restore Garage documents
- [ ] Handle Garage key conflicts (overwrite vs skip)
- [ ] Update restore worker for Garage upload
- [ ] Add progress tracking for Garage restore phase

### A4. CLI Updates
- [ ] Add `--include-garage` flag to `kg admin backup`
- [ ] Add `--include-garage` handling to `kg admin restore`
- [ ] Update progress display for Garage content
- [ ] Test round-trip: backup with Garage → restore → verify

**Note:** Backup/restore is CLI-only (admin operation). Not exposed via MCP.

---

## Part B: Document Search (ADR-084)

### B1. API Endpoints - Phase 1
- [ ] Create `api/api/routes/documents.py` route file
- [ ] Implement `POST /query/documents/search`
  - [ ] Reuse `source_embeddings` search
  - [ ] Aggregate chunks to DocumentMeta level
  - [ ] Rank by max chunk similarity
  - [ ] Include concept_ids per document
  - [ ] Add ontology filter parameter
- [ ] Implement `GET /documents/{document_id}/content`
  - [ ] Fetch from Garage (document or image+prose)
  - [ ] Include chunks from Source nodes
  - [ ] Return appropriate content type
- [ ] Implement `GET /ontology/{name}/documents`
  - [ ] List all DocumentMeta in ontology
  - [ ] Optional limit parameter
- [ ] Add Pydantic models in `api/api/models/documents.py`
- [ ] Register routes in `api/api/main.py`
- [ ] Test endpoints with curl/httpie

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

