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
- [ ] Review current backup format in `api/api/lib/serialization.py`
- [ ] Review Garage client for document retrieval patterns
- [ ] Design backup archive structure:
  ```
  backup_<ontology>_<date>/
  ├── manifest.json        # graph data + relative document paths
  └── documents/
      ├── <hash>.md
      ├── <hash>.txt
      └── images/
          ├── <hash>.jpg
          └── <hash>_prose.md
  ```
  manifest.json sources reference files via relative paths:
  ```json
  {
    "sources": [{
      "source_id": "sha256:abc123",
      "document_path": "documents/abc123.md",
      "garage_key": "original/garage/key"
    }]
  }
  ```
- [ ] Decide archive format: directory, .tar.gz, or .zip

### A2. API Changes
- [ ] Extend `DataExporter` to stream Garage documents alongside JSON
- [ ] Add document reference paths to source entries (not embedded base64)
- [ ] Create archive streaming endpoint or multi-part response

### A3. Restore Changes
- [ ] Extend `DataImporter` to read from archive structure
- [ ] Upload documents to Garage from archive
- [ ] Handle Garage key conflicts (overwrite vs skip)

### A4. CLI Updates
- [ ] Update `kg admin backup` to save directory/archive structure
- [ ] Update `kg admin restore` to read from directory/archive
- [ ] Update progress display for document count
- [ ] Test round-trip: backup → restore → verify Garage content intact

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

