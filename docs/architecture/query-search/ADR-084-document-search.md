---
status: Proposed
date: 2026-01-03
deciders:
  - aaronsb
  - claude
---

# ADR-084: Document-Level Search

## Context

The knowledge graph system excels at concept-level search - finding concepts semantically similar to a query. However, users often need to find the **original documents** that contain relevant information, not just the extracted concepts.

Current state:
- `POST /query/sources/search` searches source embeddings, returns **chunks**
- `:DocumentMeta` nodes track documents with `garage_key` linking to original files
- `(:DocumentMeta)-[:HAS_SOURCE]->(:Source)` links documents to their chunks
- `(:Concept)-[:APPEARS]->(:Source)` links concepts to source chunks

**Use cases:**
1. "Find documents about recursive algorithms" → ranked list of original documents
2. "Which papers discuss this topic?" → documents with related concepts shown
3. Load multiple relevant documents into a graph view for comparison

## Decision

### 1. Two Endpoint Types: Metadata vs Content

**Metadata endpoints** return document references and linked concepts:
- Lightweight, fast responses
- Used for discovery and navigation

**Content endpoints** return actual document data:
- Full document file(s) from Garage
- Chunks (source nodes the document was split into)
- Heavier payloads, fetched on demand

### 2. Search by Query (Phrase/Keyword)

**`POST /query/documents/search`** - Semantic search, returns metadata

```json
// Request
{
  "query": "recursive depth patterns",
  "min_similarity": 0.7,        // score threshold (water level)
  "limit": 20,                  // max results (default: 20, max: 100)
  "ontology": "optional-filter"
}

// Response
{
  "documents": [
    {
      "document_id": "sha256:abc123...",
      "filename": "algorithms.md",
      "ontology": "CS Research",
      "content_type": "document",
      "best_similarity": 0.92,
      "source_count": 5,
      "resources": [
        {"type": "document", "garage_key": "docs/abc123.md"}
      ],
      "concept_ids": ["c-123", "c-456", "c-789"]
    }
  ],
  "returned": 20,
  "total_matches": 42
}
```

**Limiting behavior:**
- `min_similarity` filters by score threshold first
- `limit` caps results after threshold filter
- Both combine: "top N documents above threshold"
- No pagination in v1 (cursor-based pagination if needed later)

### 3. Get Document Content

**`GET /documents/{document_id}/content`** - Fetch actual document

```json
// Response for text document
{
  "document_id": "sha256:abc123...",
  "content_type": "document",
  "content": {
    "document": "# Full markdown content here...",
    "encoding": "utf-8"
  },
  "chunks": [
    {
      "source_id": "sha256:abc123_chunk0",
      "paragraph": 0,
      "full_text": "First chunk content..."
    }
  ]
}

// Response for image (paired resources)
{
  "document_id": "sha256:img456...",
  "content_type": "image",
  "content": {
    "image": "base64-encoded-jpg...",
    "prose": "The diagram shows a recursive tree traversal...",
    "encoding": "base64"
  },
  "chunks": [...]
}
```

**Content definition:**
- **Documents**: Single file (markdown, text, json, html)
- **Images**: Image file + prose description (always paired)
- **Chunks**: Source nodes created during ingestion (part of content)

### 4. Ontology Filtering

All document endpoints support optional ontology filtering:

**Search with ontology filter:**
```json
POST /query/documents/search
{
  "query": "recursive patterns",
  "ontology": "CS Research"  // optional - scope to single ontology
}
```

**Browse ontology documents:**
```
GET /ontology/{name}/documents?limit=50
```

Returns same structure as search (without similarity scores).

### 5. Full Ontology Export (Defer to Backup)

For complete ontology cloning/export, use the existing backup system (ADR-015):

```bash
kg admin backup --type ontology --ontology "CS Research"
```

**Future enhancement (ADR-015 extension):**
- Add `--include-garage` flag to include original Garage documents
- Enables full ontology clone with raw source files

### 6. Content Types

**Documents (single resource):**
- Markdown (`.md`)
- Plain text (`.txt`)
- JSON (`.json`)
- HTML (`.html`)

**Images (two resources - always paired):**
- JPEG, PNG, GIF, WebP, BMP
- Prose description file (LLM-generated text describing the image)

### 7. Aggregation Strategy

**Document ranking:**
- Score = max chunk similarity (best match wins)
- Tie-breaker: count of matching chunks (more matches = more relevant)

**Why max, not average:**
- A document with one highly relevant section is more valuable than one with many mediocre matches
- Prevents dilution from unrelated sections in long documents

### 8. Concept Association

For each document, `concept_ids` are derived by:
1. Find all `:Source` nodes linked via `HAS_SOURCE`
2. Find all `:Concept` nodes linked via `APPEARS` relationship
3. Return unique concept IDs (no ranking in metadata response)

### 9. Implementation Phases

**Phase 1: API Endpoints**
- `POST /query/documents/search` - metadata search (with ontology filter)
- `GET /documents/{id}/content` - content retrieval
- `GET /ontology/{name}/documents` - list documents in ontology
- Reuse existing `source_embeddings` search infrastructure

**Phase 2: CLI**
- `kg document search "query"` - search and list metadata
- `kg document search "query" --ontology "Name"` - scoped search
- `kg document show <id>` - fetch content
- `kg document list --ontology <name>` - browse by ontology
- Table output with `--json` flag for structured output

**Phase 3: MCP Tool**
- `search` tool with `type: "documents"` parameter
- `document` tool for content retrieval
- Returns structured data for Claude analysis

**Phase 4: Web Explorer**
- Document search panel with ontology filter
- Load multiple documents into graph view
- Show document→concept relationships visually

## Consequences

### Positive
- Users can find original source documents, not just concepts
- Enables document-centric workflows (compare papers, find sources)
- Leverages existing source embedding infrastructure
- Metadata/content split keeps responses lightweight
- Ontology filtering enables scoped exploration
- Defers to backup system for full exports (no duplication)

### Negative
- Additional query complexity (chunk→document aggregation)
- Two-step flow for content (search metadata, then fetch)
- Document retrieval requires Garage access

### Neutral
- Builds on existing `:DocumentMeta` infrastructure (ADR-051)
- Complements concept search (different discovery patterns)
- Backup extends naturally for full ontology cloning (ADR-015)

## Alternatives Considered

### A. Full-Text Search (PostgreSQL tsvector)
- **Rejected:** Would require new indexing infrastructure
- Semantic search via embeddings handles synonyms better
- Can add later as complementary feature

### B. Search at Document Embedding Level
- **Rejected:** Would require generating document-level embeddings
- Current chunk embeddings provide finer granularity
- Aggregation from chunks gives similar results with existing data

### C. Return Only Document IDs
- **Rejected:** Users need context (matching chunks, concepts)
- Single query should provide actionable results

## Related ADRs

- ADR-015: Backup/restore streaming (ontology-scoped export, extend for Garage content)
- ADR-051: Document deduplication and `:DocumentMeta` nodes
- ADR-057: Image storage with prose descriptions (image + prose file pairing)
- ADR-068: Source text embeddings (chunk-level search)
- ADR-081: Source document lifecycle and Garage storage
