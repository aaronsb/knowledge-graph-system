# Storage Architecture

This document describes how data flows through the system and where different types of content are stored.

## Storage Tiers

The system uses a multi-tier storage architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Storage Hierarchy                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Apache AGE (Graph Database)                                        │
│    • Concepts, relationships, evidence                              │
│    • Chunks as :Source nodes (with pointers to full docs)           │
│    • Extracted quotes as :Instance nodes                            │
│    • Semantic structure and connections                             │
│                                                                     │
│  PostgreSQL (Relational)                                            │
│    • User accounts, groups, permissions (kg_auth.*)                 │
│    • Job queue, scheduled jobs (kg_api.*)                           │
│    • Artifact metadata, small inline payloads (kg_api.artifacts)    │
│    • Query definitions (kg_api.query_definitions)                   │
│    • Configuration and API keys (kg_api.*)                          │
│                                                                     │
│  Garage S3 (Object Storage)                                         │
│    • Original source documents (pre-chunking)                       │
│    • Original images                                                │
│    • Large computed artifacts (>10KB)                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Garage Namespaces

Garage object storage is organized into namespaces by content type:

| Namespace | Purpose | Key Pattern | ADR |
|-----------|---------|-------------|-----|
| `sources/` | Full original documents | `sources/{ontology}/{filename}` | ADR-081 |
| `images/` | Original image files | `images/{hash}.{ext}` | ADR-057 |
| `artifacts/` | Computed results | `artifacts/{type}/{id}.json` | ADR-083 |
| `projections/` | Legacy projections | `projections/{ontology}/...` | ADR-079 |

## Data Flow: Document Ingestion

```
                    ┌─────────────────┐
                    │ Original Doc    │
                    │ (PDF, TXT, MD)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Store in Garage │ sources/{ontology}/{file}
                    │ (full document) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Chunk Document  │ ~1000 words per chunk
                    │ (semantic split)│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Chunk 1  │  │ Chunk 2  │  │ Chunk N  │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │             │             │
             ▼             ▼             ▼
        ┌─────────────────────────────────────┐
        │ LLM Concept Extraction              │
        │ (per chunk)                         │
        └────────────────┬────────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────────┐
        │           Apache AGE Graph          │
        ├─────────────────────────────────────┤
        │ :Source nodes (chunks)              │
        │   - source_id, document, paragraph  │
        │   - full_text (chunk content)       │
        │   - garage_key → full doc pointer   │
        │                                     │
        │ :Concept nodes                      │
        │   - concept_id, label, embedding    │
        │   - description, search_terms       │
        │                                     │
        │ :Instance nodes (evidence)          │
        │   - instance_id, quote              │
        │                                     │
        │ Relationships                       │
        │   - APPEARS_IN, EVIDENCED_BY        │
        │   - IMPLIES, SUPPORTS, CONTRADICTS  │
        └─────────────────────────────────────┘
```

## Data Flow: Image Ingestion

```
        ┌─────────────────┐
        │ Original Image  │
        │ (PNG, JPG, etc) │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Store in Garage │ images/{hash}.{ext}
        │ (original file) │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Vision Model    │ Image → Prose description
        │ (GPT-4V, etc)   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Prose Document  │ Treated as text from here
        └────────┬────────┘
                 │
                 ▼
        (Same flow as document ingestion)
```

## Data Flow: Artifact Storage

Computed results (polarity analyses, projections, reports) follow a different path:

```
        ┌─────────────────┐
        │ Computation     │ Polarity axis, projection, etc.
        │ (expensive)     │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Size Check      │
        │ <10KB? >10KB?   │
        └────────┬────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
    ┌─────────┐    ┌──────────┐
    │ <10KB   │    │ >10KB    │
    │ Inline  │    │ Garage   │
    └────┬────┘    └────┬─────┘
         │              │
         ▼              ▼
    ┌─────────────────────────────────────┐
    │ kg_api.artifacts table              │
    │   - inline_result (JSONB) OR        │
    │   - garage_key (pointer)            │
    │   - graph_epoch (freshness)         │
    │   - owner_id, parameters, metadata  │
    └─────────────────────────────────────┘
```

## Retrieval Paths

### Source Content

| What | Where | How to Retrieve |
|------|-------|-----------------|
| Chunk text | Graph (:Source.full_text) | `GET /sources/{id}` or concept details |
| Evidence quote | Graph (:Instance.quote) | Concept details endpoint |
| Full original doc | Garage (sources/) | `GET /sources/{id}/document` |
| Original image | Garage (images/) | `GET /sources/{id}/image` |

### Computed Artifacts

| What | Where | How to Retrieve |
|------|-------|-----------------|
| Artifact metadata | PostgreSQL | `GET /artifacts/{id}` |
| Small payload | PostgreSQL (inline) | `GET /artifacts/{id}/payload` |
| Large payload | Garage (artifacts/) | `GET /artifacts/{id}/payload` (transparent) |

### Concepts and Relationships

| What | Where | How to Retrieve |
|------|-------|-----------------|
| Concept search | Graph | `POST /query/search` |
| Concept details | Graph | `GET /query/concept/{id}` |
| Relationships | Graph | `POST /query/connect` |
| Evidence | Graph (:Instance) | Included in concept details |

## Key Design Principles

1. **Graph stores structure, Garage stores blobs**
   - The graph holds semantic relationships and extracted content
   - Garage holds original files and large computed results

2. **Chunks live in the graph, full docs live in Garage**
   - :Source nodes contain chunk text directly (for fast evidence retrieval)
   - `garage_key` on :Source points to full original for context

3. **Artifacts are computed results, not source data**
   - Artifacts table stores analysis outputs (polarity, projections)
   - Source documents are NOT artifacts - they're ingested content

4. **Freshness tracked via graph_epoch**
   - `graph_change_counter` increments on graph modifications
   - Artifacts store their creation epoch for staleness detection

5. **Size-based routing for artifacts**
   - Small payloads (<10KB) inline in PostgreSQL for speed
   - Large payloads (>10KB) in Garage to avoid DB bloat

## Related ADRs

- **ADR-057**: Image storage and retrieval via Garage
- **ADR-079**: Projection artifact storage (generalized by ADR-083)
- **ADR-081**: Source document storage in Garage
- **ADR-083**: Unified artifact persistence pattern
- **ADR-082**: User scoping and artifact ownership
