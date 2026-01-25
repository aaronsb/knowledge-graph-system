# ADR-089: Deterministic Node and Edge Creation

## Status
DRAFT

## Context

The knowledge graph currently populates exclusively through the **ingest pipeline**: documents are chunked, concepts are extracted via LLM, and nodes/edges are created with embedding-based matching. This works well for document-driven knowledge but doesn't support:

1. **Manual curation** - Users wanting to directly create/edit/delete concepts
2. **Agent-driven creation** - MCP tools that let agents build knowledge structures programmatically
3. **Bulk import** - Loading structured data (CSV, JSON) without LLM processing
4. **Subgraph construction** - Creating independent concept clusters for specific purposes
5. **Foreign graph import** - Importing knowledge graphs from external systems (Neo4j exports, RDF, JSON-LD, etc.)

### Current Creation Flow (Ingest)

```
Document → Chunking → LLM Extraction → Embedding → Matching → MERGE
                                                      ↓
                                            ≥0.85: Link existing
                                            0.75-0.84 + label: Link
                                            <0.75: Create new
```

**What gets created:**
- `Source` node (chunk text, embeddings)
- `Concept` nodes (matched or new)
- `Instance` nodes (evidence quotes)
- Relationship edges (IMPLIES, SUPPORTS, etc.)

**Provenance tracked:**
- `source`: "llm_extraction"
- `created_by`: user_id
- `job_id`: ingestion job
- `document_id`: source document hash

## Decision

Implement a **deterministic creation API** that allows direct node/edge creation while maintaining full compatibility with auto-created graph elements.

### Design Principles

1. **Functionally Identical** - Manual nodes are indistinguishable from auto nodes (same properties, same schema)
2. **Full Embedding Support** - Manual concepts get embeddings via same unified worker
3. **Optional Matching** - Can match to existing concepts or force-create standalone
4. **Pruning Compatible** - Manual edges have same properties, subject to same pruning rules
5. **Provenance Tracked** - Clear distinction via `source` property, not node structure

### New Property: `creation_method`

Add to **Concept nodes**:
```
creation_method: "llm_extraction" | "manual_api" | "mcp_tool" | "workstation" | "graph_import"
```

Values:
- `llm_extraction` - Created through document ingest pipeline
- `manual_api` - Created via REST API directly
- `mcp_tool` - Created by AI agents through MCP tools
- `workstation` - Created via web workstation UI by humans
- `graph_import` - Imported from foreign graph systems

**Note:** Backup/restore preserves the original `creation_method` - it's not overwritten during restore.

This is informational only - all concepts are treated identically by queries, matching, and pruning.

### API Endpoints

#### Create Concept
```
POST /api/v1/concepts
{
  "label": "Quantum Entanglement",
  "description": "A quantum mechanical phenomenon...",
  "search_terms": ["entanglement", "quantum correlation"],
  "ontology": "physics",
  "matching_mode": "auto" | "force_create" | "match_only"
}

Response:
{
  "concept_id": "manual_abc123",
  "matched_existing": false,
  "embedding_generated": true
}
```

**Matching modes:**
- `auto` (default): Use standard two-tier matching, create if no match
- `force_create`: Always create new concept, skip matching
- `match_only`: Return match or error, never create

#### Create Edge
```
POST /api/v1/edges
{
  "from_concept_id": "concept_123",
  "to_concept_id": "concept_456",
  "relationship_type": "IMPLIES",
  "confidence": 0.85,
  "ontology": "physics"
}

Response:
{
  "edge_id": "edge_abc123",
  "relationship_type": "IMPLIES",  // May be normalized
  "vocabulary_created": false      // True if new type added
}
```

**Relationship handling:**
- Type normalized via existing mapper (ADR-032)
- Unknown types auto-added to vocabulary with `category: "manual"`
- Embedding generated for new types

#### Create Evidence (Instance)
```
POST /api/v1/concepts/{concept_id}/evidence
{
  "quote": "Einstein described entanglement as 'spooky action'",
  "source_reference": "Einstein 1935 paper"  // Optional metadata
}
```

#### Batch Creation
```
POST /api/v1/graph/batch
{
  "ontology": "physics",
  "concepts": [...],
  "edges": [...],
  "instances": [...]
}
```

### Foreign Graph Import

A significant capability enabled by deterministic creation is importing knowledge from external graph systems. This expands KG beyond document-driven knowledge to incorporate existing structured knowledge.

#### Supported Import Formats

| Format | Source Systems | Notes |
|--------|----------------|-------|
| JSON Graph Format | Generic exports, custom systems | Lightweight, easy to transform |
| Neo4j JSON | Neo4j exports | Direct node/edge mapping |
| RDF/JSON-LD | Semantic web, linked data | Requires vocabulary mapping |
| GraphML | yEd, Gephi, NetworkX | XML-based, widely supported |
| CSV (nodes + edges) | Spreadsheets, databases | Simple tabular format |

#### Import Pipeline

```
Foreign Graph Data
       ↓
   Validation (schema check)
       ↓
   Normalization (required properties)
       ↓
   Enrichment (sources, embeddings)
       ↓
   Matching (optional deduplication)
       ↓
   MERGE into Apache AGE
```

#### Import API

```
POST /api/v1/graph/import
{
  "format": "json_graph" | "neo4j" | "rdf" | "graphml" | "csv",
  "ontology": "imported_knowledge",
  "data": { ... } | "file_path",
  "options": {
    "matching_mode": "auto" | "force_create",
    "generate_embeddings": true,
    "create_synthetic_sources": true,
    "node_mapping": {
      "label_field": "name",
      "description_field": "description"
    },
    "edge_mapping": {
      "type_field": "relationship",
      "confidence_field": "weight"
    }
  }
}

Response:
{
  "job_id": "import_abc123",
  "nodes_imported": 150,
  "edges_imported": 320,
  "nodes_matched": 12,
  "nodes_created": 138,
  "warnings": ["Unknown relationship type 'RELATED_TO' normalized to 'RELATES_TO'"]
}
```

#### Normalization Requirements

Foreign nodes must be enriched to meet KG schema:

| Property | Required | Default/Generation |
|----------|----------|-------------------|
| `label` | Yes | Mapped from source field |
| `description` | No | Empty or mapped |
| `embedding` | Yes | Generated via unified worker |
| `creation_method` | Auto | Set to "graph_import" |
| `source_graph` | Auto | Original system identifier |
| `import_job_id` | Auto | Job tracking |

#### Provenance for Imports

Each import creates a synthetic Source node for provenance:
```cypher
(:Source {
  source_id: "import_{job_id}",
  document: "graph_import:{format}:{source_name}",
  full_text: "Imported from {source_system} on {date}",
  content_type: "graph_import",
  original_format: "neo4j",
  original_node_count: 150,
  original_edge_count: 320
})
```

This enables:
- Tracking which concepts came from which import
- Filtering queries by import source
- Auditing import history
- Potential rollback of imports

### Entry Points

The deterministic creation API supports multiple interfaces suited to different users:

| Interface | Users | Use Cases |
|-----------|-------|-----------|
| **REST API** | Developers, scripts | Automation, integration, bulk operations |
| **MCP Tools** | AI agents (Claude, etc.) | Agent-driven knowledge building |
| **Web Workstation** | Human curators | Manual curation, visual graph editing |
| **CLI** | Operators, developers | Quick edits, scripting |
| **Import API** | Data engineers | Foreign graph ingestion |

### MCP Tools

```typescript
// Create single concept
mcp__kg__create_concept({
  label: "Quantum Entanglement",
  description: "...",
  ontology: "physics",
  matching_mode: "auto"
})

// Create relationship between concepts
mcp__kg__create_edge({
  from_query: "quantum entanglement",  // Semantic search
  to_query: "quantum superposition",    // Semantic search
  relationship_type: "REQUIRES",
  confidence: 0.9
})

// Batch create subgraph
mcp__kg__create_subgraph({
  ontology: "physics",
  nodes: [...],
  edges: [...]
})
```

**Semantic ID resolution:** MCP tools can use concept queries instead of IDs:
- Search by label/description
- Use embedding similarity
- Fail if ambiguous (multiple matches)

### Source Nodes for Manual Concepts

Manual concepts don't have source documents. Options:

**Option A: Synthetic Source (Recommended)**
Create a placeholder source node for provenance:
```cypher
(:Source {
  source_id: "manual_{user_id}_{timestamp}",
  document: "manual_entry",
  full_text: "{description}",
  content_type: "manual"
})
```

**Option B: Optional Source**
Allow concepts without source links. Query patterns must handle NULL.

**Option C: Virtual Source**
Single shared "manual entries" source per ontology.

**Recommendation:** Option A - maintains graph integrity, enables evidence attachment later.

### Edge Properties for Manual Creation

Manual edges get same properties as auto edges:
```cypher
[:IMPLIES {
  confidence: 0.85,           // User-provided or default 1.0
  category: "logical_truth",  // From vocabulary
  source: "manual_api",       // Distinguishes from llm_extraction
  created_by: "user_123",
  created_at: "2026-01-25T...",
  job_id: null,               // No job for manual
  document_id: null           // No document for manual
}]
```

### Embedding Generation

Manual concepts MUST have embeddings for:
- Similarity matching (when `matching_mode: "auto"`)
- Future vector searches
- Grounding calculations

**Flow:**
```
Label + Description + Search Terms
        ↓
  Unified Embedding Worker
        ↓
  Same model as ingest (nomic-embed-text-v1.5 or configured)
        ↓
  Stored on Concept node
```

### Compatibility with Existing Features

| Feature | Manual Nodes | Notes |
|---------|--------------|-------|
| Vector search | ✓ | Same embeddings |
| Grounding calc | ✓ | Same edge properties |
| Pruning | ✓ | Same confidence/source properties |
| Backup/export | ✓ | Same node structure |
| Polarity analysis | ✓ | Same relationships |
| Query definitions | ✓ | Cypher works identically |

### Migration

No schema migration needed. The `creation_method` property is optional and added only to new manually-created nodes. Existing nodes implicitly have `creation_method: "llm_extraction"`.

## Consequences

### Positive
- Users can curate knowledge directly via web workstation
- Agents can build structured knowledge via MCP
- Bulk import possible without LLM costs
- Independent subgraphs for specialized use cases
- Full compatibility with existing features
- **Foreign graph import** expands knowledge sources beyond documents
- Leverage existing knowledge graphs from other systems (Neo4j, RDF stores)
- Enable knowledge federation and migration scenarios

### Negative
- More ways to create inconsistent data (user error)
- Need input validation for manual entries
- Potential for orphaned nodes if not careful
- Documentation complexity increases

### Risks
- Users creating low-quality concepts (garbage in)
- Duplicate concepts if matching disabled carelessly
- Relationship type explosion if not normalized
- Foreign graph imports may have incompatible semantics
- Large imports could overwhelm embedding generation

## Related ADRs

- ADR-032: Relationship vocabulary normalization
- ADR-044: Grounding strength calculation
- ADR-045: Unified embedding generation
- ADR-048: Query safety patterns
- ADR-051: Provenance tracking
- ADR-065: Epistemic status classification

## Implementation Notes

### Phase 1: Core API
- POST /concepts endpoint
- POST /edges endpoint
- Embedding generation integration
- Basic validation

### Phase 2: MCP Tools
- create_concept tool
- create_edge tool
- Semantic ID resolution

### Phase 3: Batch & UI
- Batch creation endpoint
- Web workstation curation UI
- Import from CSV/JSON

### Phase 4: Foreign Graph Import
- JSON Graph Format importer
- Neo4j export importer
- Format detection and validation
- Mapping configuration UI

### Phase 5: Advanced
- RDF/JSON-LD importer
- GraphML importer
- Subgraph templates
- Concept merging
- Edge bulk operations
- Import rollback capability
