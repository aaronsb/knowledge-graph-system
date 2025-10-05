# Architectural Decision Records (ADRs)

## ADR-001: Multi-Tier Agent Access Model

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Support multiple AI agents and human users interacting with knowledge graph simultaneously

**Decision:** Implement tiered access control via Neo4j user accounts, not MCP server claims.

### Access Tiers

#### Tier 1: Reader (Query-Only)
- **Neo4j Role:** `reader`
- **Permissions:** Read-only access to graph
- **Use Cases:** General purpose LLM agents, public web interface, text generation

#### Tier 2: Contributor (Controlled Write)
- **Neo4j Role:** `contributor`
- **Permissions:**
  - Read all nodes/relationships
  - Create Concept, Instance, Relationship nodes
  - Update fitness metrics (query_count, relevance_sum)
- **Restrictions:**
  - Cannot delete nodes
  - Cannot modify core properties of existing nodes
  - Cannot adjust manual_bias scores
- **Use Cases:** AI agents adding knowledge from conversations, automated ingestion

#### Tier 3: Librarian (Maintenance)
- **Neo4j Role:** `librarian`
- **Permissions:**
  - All Contributor permissions
  - Merge concepts (transfer relationships, delete duplicates)
  - Flag nodes for review
  - Set quality metadata (confidence, review flags)
- **Restrictions:**
  - Cannot adjust manual_bias
  - Cannot delete Source nodes
- **Use Cases:** Quality control agents, deduplication services

#### Tier 4: Curator (Structural)
- **Neo4j Role:** `curator`
- **Permissions:**
  - All Librarian permissions
  - Adjust manual_bias scores
  - Delete any node type
  - Bulk operations
  - Cross-graph operations (staging → production)
- **Use Cases:** Human administrators, CLI bulk operations

### Security Model

**Never trust MCP client claims:**
```
Agent claims role="curator" via MCP
  ↓
MCP server receives request
  ↓
MCP uses Neo4j connection with agent's actual credentials
  ↓
Neo4j enforces role-based permissions
  ↓
Operation succeeds/fails based on actual Neo4j role
```

**MCP Server Role:**
- Route requests to appropriate Neo4j connection
- Provide workflow hints and prerequisites (UX only, not security)
- Log operations for audit trail
- Return helpful error messages

**Neo4j Role Setup:**
```cypher
// Create roles
CREATE ROLE reader;
CREATE ROLE contributor;
CREATE ROLE librarian;
CREATE ROLE curator;

// Grant permissions (example for contributor)
GRANT TRAVERSE ON GRAPH * NODES * TO contributor;
GRANT READ {*} ON GRAPH * NODES * TO contributor;
GRANT CREATE ON GRAPH * NODES Concept, Instance TO contributor;
GRANT SET PROPERTY {query_count, relevance_sum, fitness_score} ON GRAPH * NODES Concept TO contributor;

// Create user with role
CREATE USER agent_gpt4o SET PASSWORD 'secure_password';
GRANT ROLE contributor TO agent_gpt4o;
```

**Rationale:**
- Security enforced at database level, not application level
- Multiple MCP servers can exist without security concerns
- Compromised MCP server cannot escalate privileges
- Clear audit trail via Neo4j authentication logs

---

## ADR-002: Node Fitness Scoring System

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Enable evolutionary knowledge graph where useful concepts naturally rise in prominence

**Decision:** Implement automatic fitness scoring based on query patterns, with manual curator override.

### Node Fitness Properties

```cypher
(:Concept {
  // Core properties
  concept_id: string,
  label: string,
  embedding: float[],

  // Provenance
  created_by: string,      // Agent/user identifier
  created_at: datetime,    // Creation timestamp
  source_type: enum,       // "document" | "conversation" | "inference"

  // Fitness metrics (auto-updated)
  query_count: integer,    // Total times retrieved
  relevance_sum: float,    // Cumulative match scores
  fitness_score: float,    // relevance_sum / query_count

  // Curator adjustments
  manual_bias: float,      // -1.0 to +1.0, curator override
  final_score: float,      // fitness_score + manual_bias

  // Quality flags
  flagged_for_review: boolean,
  confidence: float        // 0.0 to 1.0
})
```

### Auto-Update Mechanism

**Lazy Write Pattern:**
- Query operations queue fitness updates
- Batch flush every 100 queries or 10 seconds
- Updates happen outside query transaction (async)

```python
class ScoringQueue:
    updates = defaultdict(lambda: {"count": 0, "relevance": 0.0})

    def record_hit(concept_id: str, relevance: float):
        updates[concept_id]["count"] += 1
        updates[concept_id]["relevance"] += relevance

    async def flush():
        # Batch update Neo4j
        UNWIND $updates as u
        MATCH (c:Concept {concept_id: u.id})
        SET c.query_count = coalesce(c.query_count, 0) + u.count,
            c.relevance_sum = coalesce(c.relevance_sum, 0.0) + u.relevance,
            c.fitness_score = c.relevance_sum / c.query_count,
            c.final_score = c.fitness_score + coalesce(c.manual_bias, 0.0)
```

### Search Boosting

```cypher
// Vector search with fitness boost
CALL db.index.vector.queryNodes('concept-embeddings', 10, $embedding)
YIELD node, score
RETURN node, (score * (1 + node.final_score)) as boosted_score
ORDER BY boosted_score DESC
```

### Curator Interventions

```python
# Promote undervalued concept
curator.adjust_bias("concept_091", bias=+0.5, reason="Critical but obscure")

# Demote over-prominent concept
curator.adjust_bias("concept_042", bias=-0.3, reason="Popular but low quality")
```

**Rationale:**
- Self-organizing knowledge network
- Useful concepts naturally promoted through usage
- Combats semantic search bias (popular ≠ relevant)
- Curator can override for edge cases
- Minimal storage overhead (4 floats per node)

---

## ADR-003: Semantic Tool Hint Networks

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Prevent agent chaos by guiding tool usage without hard enforcement

**Decision:** Implement "text adventure" style tool hints in MCP server, where tools suggest prerequisites and next actions.

### Tool Hint Structure

```typescript
interface ToolHints {
  prerequisites?: string[];           // Tools that should be called first
  next_actions?: string[];            // Suggested tools to call after
  permission_level: AccessTier;       // Minimum required role
  error_hints: {
    [errorType: string]: string;      // Helpful messages for common errors
  };
  audit?: boolean;                    // Log this operation
}

const tools = {
  create_concept: {
    permission_level: "contributor",
    prerequisites: ["search_concepts"],
    error_hints: {
      duplicate_concept: "Similar concept found. Use create_relationship or merge_concepts instead.",
      no_search_performed: "Search for similar concepts first to avoid duplicates."
    },
    next_actions: ["create_relationship", "add_evidence"]
  },

  search_concepts: {
    permission_level: "reader",
    next_actions: ["create_concept", "create_relationship", "get_concept_details"]
  },

  merge_concepts: {
    permission_level: "librarian",
    prerequisites: ["flag_similar_concepts"],
    audit: true,
    error_hints: {
      insufficient_similarity: "Concepts must have similarity > 0.85 to merge",
      missing_flag: "Flag concepts for review before merging"
    }
  }
};
```

### Execution Flow (Text Adventure Pattern)

```typescript
async function executeWithHints(
  toolName: string,
  params: any,
  context: ExecutionContext,
  neo4jConnection: Neo4jDriver  // Uses agent's actual credentials
) {
  const tool = tools[toolName];

  // Check prerequisites (UX hint, not security)
  for (const prereq of tool.prerequisites || []) {
    if (!context.completed.includes(prereq)) {
      return {
        error: "PREREQUISITE_SUGGESTED",
        message: `Consider calling ${prereq} first`,
        hint: tool.error_hints[`missing_${prereq}`],
        can_proceed: true  // Suggestion, not enforcement
      };
    }
  }

  // Execute with agent's Neo4j credentials
  try {
    const result = await tool.execute(params, neo4jConnection);

    // Add to context
    context.completed.push(toolName);

    // Suggest next actions
    result.suggested_next_actions = tool.next_actions;

    return result;
  } catch (neo4jError) {
    // Neo4j permission error is the real enforcement
    return {
      error: "PERMISSION_DENIED",
      message: neo4jError.message,
      hint: "Your Neo4j role lacks permission for this operation"
    };
  }
}
```

### Example Interaction

```
Agent: create_concept({label: "Holacracy"})

MCP Response: {
  error: "PREREQUISITE_SUGGESTED",
  message: "Consider calling search_concepts first",
  hint: "Search for similar concepts to avoid creating duplicates",
  can_proceed: true
}

Agent: search_concepts({query: "Holacracy"})

MCP Response: {
  results: [...],
  suggested_next_actions: ["create_concept", "create_relationship"]
}

Agent: create_concept({label: "Holacracy"})

MCP Response: {
  success: true,
  concept_id: "holacracy-role-assignment",
  suggested_next_actions: ["create_relationship", "add_evidence"]
}
```

**Rationale:**
- Guides agent behavior without hard constraints
- LLM learns workflow through interaction
- Hints improve UX but don't replace Neo4j security
- Flexible - agents can ignore hints if they have context
- Prevents most mistakes while allowing informed override

---

## ADR-004: Pure Graph Design (Library Metaphor)

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Separate knowledge storage from access control and workflow logic

**Decision:** Keep graph as pure knowledge store. All access control, workflow, and business logic lives in MCP server or external services.

### Graph Responsibilities (The Library)
- Store concepts, relationships, instances, sources
- Maintain vector embeddings for semantic search
- Track provenance (who created, when, from where)
- Record usage metrics (fitness scores)
- Enforce data constraints via Neo4j

### Graph Does NOT Contain
- ❌ Access control logic (use Neo4j roles)
- ❌ Workflow rules (use MCP hints)
- ❌ Business logic (use application layer)
- ❌ Tool definitions (use MCP server)
- ❌ UI state (use client applications)

### MCP Server Responsibilities (The Librarian's Desk)
- Route requests to appropriate Neo4j connection
- Provide tool hints and workflow guidance
- Log operations for audit
- Translate between LLM and graph operations
- Return helpful error messages

### Quality Control Services (The Librarians)
- Automated agents that read/flag/merge
- Periodic quality assessments
- Duplicate detection
- Orphaned node cleanup
- Confidence scoring

### Analogy: "Any moron can enter the library"

**The Comic Book in Medical Texts Problem:**
```cypher
// Automated librarian finds suspicious placements
MATCH (c:Concept)-[r]-(neighbor:Concept)
WHERE c.created_at > datetime() - duration('P7D')
WITH c, collect(neighbor.label) as neighbors
CALL db.index.vector.queryNodes('concept-embeddings', 5, c.embedding)
  YIELD node, score
WITH c, neighbors, collect(node.label) as semantically_similar
WHERE none(n IN neighbors WHERE n IN semantically_similar)
SET c.flagged_for_review = true,
    c.flag_reason = "Linked to semantically distant concepts"
```

**Provenance Tracking:**
```cypher
(:Concept {
  created_by: "agent_gpt4o_session_abc123",
  created_at: "2025-10-04T20:15:00Z",
  source_type: "conversation"
})

// Query: Who created low-quality nodes?
MATCH (c:Concept)
WHERE c.confidence < 0.5 AND c.created_by STARTS WITH "agent_"
RETURN c.created_by, count(*) as low_quality_count
ORDER BY low_quality_count DESC
```

**Rationale:**
- Clear separation of concerns
- Graph remains queryable by any tool/language
- Easy to add new access methods (web UI, API, etc.)
- Quality issues can be detected and fixed programmatically
- Scales to multiple MCP servers without data duplication

---

## ADR-005: Source Text Tracking and Retrieval

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Maintain traceability from concepts back to original source text for verification and context

**Decision:** Use markdown as canonical source format with paragraph/sentence indexing. Graph stores references, not full text.

### Source Storage Model

**Document Store (File System):**
```
documents/
  governed-agility.md           # Source markdown
  watts-lecture-1.md
  safe-framework.md

.document-index/
  governed-agility.json         # Paragraph/sentence offsets
  {
    "paragraphs": [
      {"id": 1, "start": 0, "end": 245, "sentences": 3},
      {"id": 2, "start": 246, "end": 512, "sentences": 2}
    ]
  }
```

**Graph References:**
```cypher
(:Source {
  source_id: "governed-agility_p42",
  document: "governed-agility",
  document_path: "documents/governed-agility.md",
  paragraph: 42,
  paragraph_start_char: 5234,
  paragraph_end_char: 5687,
  full_text: "..."  // The paragraph text (optional, for quick access)
})

(:Instance {
  instance_id: "...",
  quote: "exact verbatim quote from text",
  char_offset_start: 5341,  // Offset within document
  char_offset_end: 5423,
  sentence_index: 2          // Which sentence in paragraph
})
```

### Retrieval Pattern

**Query: Get concept with full context**
```cypher
MATCH (concept:Concept {concept_id: $id})
MATCH (concept)-[:EVIDENCED_BY]->(instance:Instance)
MATCH (instance)-[:FROM_SOURCE]->(source:Source)
RETURN
  concept.label as concept,
  instance.quote as evidence,
  source.document as document,
  source.paragraph as paragraph,
  source.document_path as file_path,
  source.full_text as context
ORDER BY source.paragraph
```

**Retrieval Service:**
```python
def get_concept_with_context(concept_id: str):
    # Query graph for references
    result = neo4j.run(query, concept_id=concept_id)

    for record in result:
        # Option 1: Use cached paragraph text from Source node
        context = record["context"]

        # Option 2: Retrieve from markdown file (if not cached)
        if not context:
            context = retrieve_paragraph(
                file_path=record["file_path"],
                paragraph_num=record["paragraph"]
            )

        yield {
            "concept": record["concept"],
            "evidence": record["evidence"],
            "source_document": record["document"],
            "source_paragraph": record["paragraph"],
            "source_context": context
        }
```

### Markdown as Canonical Format

**Ingestion converts all formats to markdown:**
- PDF → markdown (via pandoc or similar)
- DOCX → markdown
- HTML → markdown
- Plain text → markdown (trivial)

**Benefits:**
- Simple, git-friendly format
- Easy to version control
- Human readable
- Preserves structure (headers, lists, emphasis)
- Can embed metadata in frontmatter

### Text Retrieval Modes

**1. Quote Only (Fast):**
```python
instance.quote  # Just the extracted quote
```

**2. Paragraph Context (Medium):**
```python
source.full_text  # Entire paragraph containing quote
```

**3. Document Section (Slower):**
```python
retrieve_markdown_section(
    document="governed-agility.md",
    start_paragraph=40,
    end_paragraph=45
)
```

**4. Full Document (Rare):**
```python
retrieve_full_document("governed-agility.md")
```

**Rationale:**
- Graph stores references, not bulky text
- Source text remains in version-controlled markdown
- Flexible retrieval based on context needs
- Can reconstruct full context when needed
- Supports incremental loading (paragraph → section → document)

---

## ADR-006: Staging and Migration Workflows

**Status:** Proposed
**Date:** 2025-10-04
**Context:** Support experimental ingestion and safe promotion to production knowledge graph

**Decision:** Use separate Neo4j databases for staging/production with CLI tools for migration.

### Database Structure

```
Neo4j Instance:
├── graph_staging        # Experimental ingestion, agent testing
├── graph_production     # Curated, validated knowledge
└── graph_archive        # Historical versions, backups
```

### Migration Workflow

**1. Ingest to Staging:**
```bash
# Ingest with staging flag
./scripts/ingest.sh document.md --name "New Doc" --target staging

# Or via MCP (contributor role)
create_concept({...}, target_graph="staging")
```

**2. Review in Staging:**
```bash
# CLI queries against staging
python cli.py --graph staging search "topic"
python cli.py --graph staging stats

# Web UI shows staging vs production toggle
```

**3. Quality Check:**
```python
# Automated librarian review
def assess_staging_quality():
    # Check for orphans, duplicates, low confidence
    issues = find_quality_issues(graph="staging")

    if issues:
        flag_for_manual_review(issues)
    else:
        approve_for_promotion()
```

**4. Promote to Production:**
```bash
# CLI migration tool
python cli.py migrate \
  --from staging \
  --to production \
  --concepts concept_101,concept_102,concept_103 \
  --include-relationships \
  --include-instances

# Or full graph merge
python cli.py migrate \
  --from staging \
  --to production \
  --merge-all \
  --deduplicate
```

**5. Archive Old Versions:**
```bash
# Before major updates, snapshot production
python cli.py snapshot \
  --from production \
  --to archive \
  --tag "pre-migration-2025-10-04"
```

### Migration Operations

**Copy (Non-destructive):**
```cypher
// Copy concept cluster to production
CALL apoc.graph.fromCypher(
  "MATCH (c:Concept) WHERE c.concept_id IN $ids
   MATCH (c)-[r*0..2]-(related)
   RETURN c, r, related",
  {ids: $concept_ids},
  {target: 'graph_production'}
)
```

**Move (Destructive in source):**
```cypher
// Move approved concepts
MATCH (c:Concept) WHERE c.approved = true
CALL apoc.refactor.cloneSubgraphFromPaths([c], {target: 'graph_production'})
WITH c
DETACH DELETE c  // Remove from staging
```

**Merge (Deduplicate):**
```python
def merge_graphs(source: str, target: str):
    # Find duplicates across graphs
    duplicates = find_cross_graph_duplicates(source, target)

    for src_concept, tgt_concept in duplicates:
        # Merge relationships into target
        merge_concepts(
            from_graph=source,
            to_graph=target,
            from_id=src_concept,
            to_id=tgt_concept
        )
```

### Rollback Capability

```bash
# Restore from archive
python cli.py restore \
  --from archive \
  --snapshot "pre-migration-2025-10-04" \
  --to production \
  --confirm

# Partial rollback (remove recent additions)
python cli.py rollback \
  --concepts-created-after "2025-10-04T14:00:00Z" \
  --graph production \
  --dry-run  # Preview first
```

**Rationale:**
- Safe experimentation without polluting production
- Gradual promotion of validated knowledge
- Rollback capability for mistakes
- Archive provides audit trail
- Supports A/B testing of different ingestion strategies

---

## Future Considerations

### ADR-007: Edge Fitness Scoring (Proposed)
Track which relationship types are most useful for traversal:
```cypher
(:Concept)-[:IMPLIES {
  traversal_count: 423,
  useful_count: 387,      // Led to relevant results
  fitness: 0.915          // useful_count / traversal_count
}]->(:Concept)
```

### ADR-008: Multi-Agent Coordination (Proposed)
- Event streaming for graph changes
- Agent-to-agent communication via graph annotations
- Conflict resolution strategies for concurrent edits

### ADR-009: Cross-Graph Querying (Proposed)
- Federated queries across staging/production/archive
- Virtual graph views (merge multiple graphs at query time)

### ADR-010: LLM-Assisted Curation (Proposed)
- Use LLM to suggest merges, generate summaries
- Auto-generate concept descriptions from instances
- Semantic consistency checking
