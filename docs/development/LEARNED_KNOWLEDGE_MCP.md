# Learned Knowledge Synthesis - MCP Enhancement Plan

## Overview

This document outlines the planned MCP server enhancements for knowledge synthesis capabilities. These features will allow Claude to create, update, and manage learned connections between concepts across ontologies, capturing "aha!" moments when semantic connections are discovered.

## Current Status

**✅ Implemented:** CLI-based learned knowledge management
**⏳ Planned:** MCP server tools for AI-assisted synthesis

## Rationale

While document ingestion extracts knowledge from text, learned synthesis enables:
- **Cross-ontology bridges**: Connect related concepts from different domains
- **AI-assisted discovery**: Claude can suggest non-obvious connections
- **Iterative refinement**: Update/delete learned knowledge as understanding evolves
- **Provenance tracking**: Always know who/what created synthetic knowledge

## Planned MCP Tools

### 1. `find_bridge_candidates`

**Purpose:** Discover potential connections between ontologies

**Parameters:**
```typescript
{
  ontology1: string;           // First ontology name
  ontology2: string;           // Second ontology name
  min_similarity?: number;     // Default: 0.85
  limit?: number;              // Default: 10
}
```

**Returns:**
```json
{
  "candidatesFound": 5,
  "candidates": [
    {
      "concept1": {
        "id": "chapter_01_chunk2_c56c2ab3",
        "label": "Sensible Transparency",
        "ontology": "Governed Agility"
      },
      "concept2": {
        "id": "signals_pillar1_signal1_62e52f23",
        "label": "Signal Transparency Score",
        "ontology": "Role Based Intelligence"
      },
      "similarity": 0.89,
      "cognitive_leap": "LOW",
      "has_existing_edge": false
    }
  ]
}
```

**Implementation:**
- Vector search across ontologies
- Filter pairs without existing relationships
- Score by semantic similarity
- Flag existing edges to avoid duplicates

---

### 2. `create_learned_relationship`

**Purpose:** Create a connection between existing concepts

**Parameters:**
```typescript
{
  from_concept_id: string;     // Starting concept
  to_concept_id: string;       // Target concept
  relationship_type: string;   // BRIDGES, LEARNED_CONNECTION, etc.
  evidence: string;            // Rationale for connection
  creator?: string;            // Default: "claude-mcp"
}
```

**Validation:**
1. Vectorize evidence text
2. Calculate similarity: evidence ↔ concept1, evidence ↔ concept2
3. Determine cognitive leap:
   - **>0.85**: LOW (obvious) ✓
   - **0.70-0.85**: MEDIUM (reasonable) ⚠️
   - **<0.70**: HIGH (unusual) ⚠️⚠️

**Returns:**
```json
{
  "learned_id": "learned_2025-10-06_001",
  "from_concept": {"id": "...", "label": "..."},
  "to_concept": {"id": "...", "label": "..."},
  "relationship_type": "BRIDGES",
  "similarity_scores": {
    "evidence_to_from": 0.87,
    "evidence_to_to": 0.84
  },
  "cognitive_leap": "LOW",
  "warning": null
}
```

**Warnings:**
- Similarity <0.70: "⚠️ Unusual connection - low semantic similarity detected"
- Edge already exists: "Edge already exists via document extraction"

---

### 3. `create_synthesis_concept`

**Purpose:** Create a new concept that bridges existing ones

**Parameters:**
```typescript
{
  label: string;               // Concept label
  search_terms: string[];      // Keywords for vector search
  ontology: string;            // Target ontology (or create new)
  bridges_concepts: string[];  // Array of concept IDs to link
  evidence: string;            // Synthesis rationale
  creator?: string;            // Default: "claude-mcp"
}
```

**Returns:**
```json
{
  "concept_id": "synthesis_2025-10-06_001",
  "label": "Measurable Transparency",
  "ontology": "Cross-Ontology-Bridges",
  "bridges": [
    {"id": "chapter_01_chunk2_c56c2ab3", "label": "Sensible Transparency"},
    {"id": "signals_pillar1_signal1_62e52f23", "label": "Signal Transparency"}
  ],
  "similarity_scores": [0.89, 0.91],
  "cognitive_leap": "LOW",
  "learned_id": "learned_2025-10-06_001"
}
```

**Behavior:**
- Generate embedding for concept (label + search_terms)
- Create Concept node with embedding
- Create learned Source node with provenance
- Link via EVIDENCED_BY, BRIDGES relationships

---

### 4. `update_learned_knowledge`

**Purpose:** Modify existing learned knowledge

**Parameters:**
```typescript
{
  learned_id: string;
  updates: {
    evidence?: string;         // Update rationale
    relationship_type?: string; // Change relationship
  }
}
```

**Returns:**
```json
{
  "learned_id": "learned_2025-10-06_001",
  "updated_fields": ["evidence"],
  "new_similarity_scores": {"evidence_to_from": 0.92, "evidence_to_to": 0.88},
  "cognitive_leap": "LOW"
}
```

---

### 5. `delete_learned_knowledge`

**Purpose:** Remove learned connections (preserves document-extracted knowledge)

**Parameters:**
```typescript
{
  learned_id: string;
  cascade?: boolean;  // Delete linked synthesis concepts (default: false)
}
```

**Returns:**
```json
{
  "learned_id": "learned_2025-10-06_001",
  "deleted_nodes": 1,
  "deleted_relationships": 2,
  "cascade_deleted_concepts": 0
}
```

**Safety:**
- Only deletes Source nodes with `type: "LEARNED"`
- Never deletes document-extracted knowledge
- Warns if deleting would orphan synthesis concepts

---

### 6. `list_learned_knowledge`

**Purpose:** Query learned knowledge with filters

**Parameters:**
```typescript
{
  creator?: string;            // Filter by creator
  ontology?: string;           // Filter by ontology
  min_similarity?: number;     // Minimum smell test score
  cognitive_leap?: string;     // "LOW", "MEDIUM", "HIGH"
  limit?: number;              // Default: 20
  offset?: number;             // Pagination
}
```

**Returns:**
```json
{
  "total": 15,
  "offset": 0,
  "limit": 20,
  "learned_knowledge": [
    {
      "learned_id": "learned_2025-10-06_001",
      "created_by": "aaron",
      "created_at": "2025-10-06T16:30:00Z",
      "evidence": "Both emphasize transparency through signals",
      "connections": [
        {"from": "Sensible Transparency", "to": "Signal Transparency", "type": "BRIDGES"}
      ],
      "similarity_score": 0.89,
      "cognitive_leap": "LOW"
    }
  ]
}
```

---

## Schema Changes

### Source Node Enhancement

```cypher
// Existing document sources
(:Source {
  source_id: string,
  document: string,
  paragraph: integer,
  full_text: string,
  type: "DOCUMENT"  // NEW FIELD
})

// New learned sources
(:Source {
  source_id: "learned_2025-10-06_001",
  document: "User synthesis" | "AI synthesis",
  paragraph: 0,
  full_text: string,  // Evidence/rationale
  type: "LEARNED",    // NEW VALUE
  created_by: string, // "aaron", "claude-mcp", "claude-code"
  created_at: timestamp,
  similarity_score: float,
  cognitive_leap: "LOW" | "MEDIUM" | "HIGH"
})
```

### New Relationship Types

```cypher
// Cross-ontology bridge
(:Concept)-[:BRIDGES {learned_id: string}]->(:Concept)

// AI/human discovered connection
(:Concept)-[:LEARNED_CONNECTION {learned_id: string}]->(:Concept)

// Synthesis concept links back to originals
(:Concept)-[:SYNTHESIZED_FROM {learned_id: string}]->(:Concept)
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (CLI - ✅ Complete)
- [x] Schema updates for learned Source nodes
- [x] Validation/smell test function
- [x] CLI CRUD operations

### Phase 2: MCP Basic Tools (Planned)
- [ ] `create_learned_relationship` tool
- [ ] `list_learned_knowledge` tool
- [ ] `delete_learned_knowledge` tool
- [ ] Update `mcp-server/src/neo4j.ts` with functions
- [ ] Expose tools in `mcp-server/src/index.ts`

### Phase 3: MCP Advanced Tools (Planned)
- [ ] `find_bridge_candidates` tool
- [ ] `create_synthesis_concept` tool
- [ ] `update_learned_knowledge` tool
- [ ] Auto-suggest connections during searches

### Phase 4: Refinement (Future)
- [ ] Batch operations (create multiple connections)
- [ ] Relationship strength scoring (weak/strong bridges)
- [ ] Conflict detection (contradictory learned knowledge)
- [ ] Export learned knowledge to documents

---

## Usage Examples

### Example 1: AI discovers connection

```
User: "Look for connections between Sensible Transparency and Role-Based Intelligence"

Claude uses: find_bridge_candidates("Governed Agility", "Role Based Intelligence", 0.80)

Result: 3 high-similarity candidates found

Claude suggests: "I found a strong connection (89% similarity) between
'Sensible Transparency' and 'Signal Transparency Score'. Both emphasize
decision-making through measurable, visible data. Should I create this connection?"

User: "Yes"

Claude uses: create_learned_relationship(...)

Result: Bridge created with cognitive_leap="LOW" (obvious connection)
```

### Example 2: User creates synthesis concept

```
User: "Create a concept called 'Quantitative Governance' that bridges
Data-Driven Reasoning from Governed Agility and the metrics pillars
from Role-Based Intelligence"

Claude uses: create_synthesis_concept(
  label="Quantitative Governance",
  search_terms=["metrics", "data-driven", "quantitative", "governance"],
  ontology="Cross-Ontology-Bridges",
  bridges_concepts=["chapter_01_chunk2_55de5dac", "signals_pillar2_..."],
  evidence="Synthesis connecting data-driven governance with quantifiable signals"
)

Result: New concept created at semantic midpoint, bridges 2 ontologies
```

### Example 3: Review and refine

```
User: "Show me all learned knowledge I've created with low confidence"

Claude uses: list_learned_knowledge(creator="aaron", cognitive_leap="HIGH")

Result: 2 connections with <70% similarity

User: "Delete the second one, it doesn't make sense anymore"

Claude uses: delete_learned_knowledge("learned_2025-10-06_005")

Result: Learned connection removed, document knowledge preserved
```

---

## Security & Safety Considerations

### Validation Rules
- ✅ Evidence similarity must be calculated before creation
- ✅ Warn on cognitive_leap="HIGH" (but allow)
- ✅ Prevent duplicate edges (check existing relationships)
- ✅ Validate creator field (must be known source)

### Data Integrity
- ✅ Never delete document-extracted knowledge
- ✅ Cascade options must be explicit (default: false)
- ✅ Track provenance: who, when, why
- ✅ Support rollback via delete operations

### Query Integration
- ✅ Learned knowledge participates in all searches
- ✅ No distinction in vector/graph queries
- ✅ Filter by `Source.type` to separate learned from extracted
- ✅ CLI flags: `--include-learned`, `--learned-only`, `--documents-only`

---

## Testing Strategy

### Unit Tests (Per Tool)
- Validation logic (smell test thresholds)
- CRUD operations (create, read, update, delete)
- Error handling (missing concepts, invalid similarity)

### Integration Tests
- Cross-ontology bridge creation
- Path finding includes learned edges
- Vector search finds synthesis concepts
- Learned knowledge persists across sessions

### End-to-End Tests
1. Create learned relationship → verify in Neo4j
2. Search concepts → learned edges appear in paths
3. Delete learned knowledge → edges removed, concepts preserved
4. Create synthesis concept → participates in vector search

---

## Documentation Updates Needed

- [ ] Add "Learned Knowledge" section to ARCHITECTURE.md
- [ ] Update QUICKSTART.md with synthesis examples
- [ ] Document CLI `learn` subcommand in README.md
- [ ] Update MCP_SETUP.md when tools are implemented
- [ ] Create tutorial: "Bridging Ontologies with Synthesis"

---

## Future Enhancements

### Confidence Scoring
Track connection strength based on:
- Initial similarity score
- Usage frequency (how often queried)
- User validation (thumbs up/down)
- Contradicting evidence

### Collaborative Learning
- Multi-user environments: track who created what
- Vote on learned connections (crowd-sourced validation)
- Conflict resolution when users disagree

### AI-Assisted Curation
- Periodic suggestions: "Review these 5 potential connections?"
- Auto-detect weak connections: "This bridge has low usage, delete?"
- Semantic drift detection: "This connection's similarity has decreased"

### Export/Import
- Export learned knowledge to JSON/Cypher
- Import curated ontology bridges
- Share learned knowledge across instances

---

## Migration Path

When implementing MCP tools:

1. **Reuse CLI logic**: Extract core functions from CLI to shared module
2. **Add MCP wrappers**: Thin layer in `mcp-server/src/neo4j.ts`
3. **Maintain parity**: Both CLI and MCP should have same capabilities
4. **Test both paths**: Ensure CLI and MCP produce identical results

Example shared module structure:
```
ingest/
  learned_knowledge.py      # Core functions (NEW)
    - validate_connection()
    - create_relationship()
    - create_synthesis_concept()
    - update_learned()
    - delete_learned()
    - list_learned()

cli.py                      # CLI wrapper using learned_knowledge.py
mcp-server/src/learned.ts   # MCP wrapper calling Python functions
```

---

## Success Metrics

- **CLI implementation**: Complete, tested, documented
- **MCP tools**: All 6 tools functional
- **Integration**: Learned knowledge seamlessly queryable
- **Performance**: No degradation in search/pathfinding
- **Safety**: Zero document knowledge deletions
- **Usability**: Claude can discover and suggest connections autonomously

---

## Questions for Future Design

1. Should synthesis concepts have different vector index parameters?
2. How to handle versioning (multiple versions of same connection)?
3. Should learned knowledge support bulk import from CSV/JSON?
4. What visualization distinguishes learned from extracted knowledge?
5. How to export learned knowledge for sharing between instances?

---

**Status:** CLI implementation in progress, MCP enhancement planned for future milestone.

**Last Updated:** 2025-10-06
