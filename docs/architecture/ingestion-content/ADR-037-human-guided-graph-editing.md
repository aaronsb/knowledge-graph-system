---
status: Proposed
date: 2025-10-17
deciders:
  - Aaron Bockelie
  - Claude Code
related:
  - ADR-014
  - ADR-016
  - ADR-033
  - ADR-036
---

# ADR-037: Human-Guided Graph Editing

## Overview

Picture this: you're exploring a knowledge graph and you see two clusters of concepts sitting far apart from each other. Your brain immediately recognizes they're related—"oh, that business strategy is implemented through this technical system"—but the graph doesn't show any connection because no single document explicitly stated that relationship. The AI can only learn from what's written down, but you just know these things connect.

This is the "hunch problem." As a human expert, you possess knowledge that doesn't exist in any document yet: cross-domain connections, intuitive leaps, domain expertise that lives in your head. The current system treats you as a passive observer of the graph, when you should be able to actively teach it what you know.

This ADR introduces human-guided graph editing where you can multi-select concepts across the graph and create connections between them by explaining why they relate. But here's the clever part: instead of directly mutating the graph (which would bypass the evidence system), your explanation gets fed back through the same ingestion pipeline that processes documents. The system treats your justification as a new piece of evidence, extracting concepts and relationships from it just like any other document.

This approach maintains the graph's integrity while capturing irreplaceable human intelligence. Your hunches become queryable facts, your insights become evidence, and your expertise teaches the system connections it could never discover on its own. The "teaching ontology" collects all human contributions, creating a valuable dataset of expert knowledge that enriches the graph without corrupting it.

---

## Context

Humans possess intuitive knowledge that AI cannot extract from documents alone - cross-domain connections, hunches, domain expertise, and emergent insights. The current system can only learn from explicit relationships stated in ingested documents.

### The "Hunch" Problem

**Scenario:** A user loads two disconnected graph clusters:
1. "Enterprise Strategy" neighborhood (business concepts)
2. "NorthWind Role" neighborhood (technical implementation)

The human sees: *"These should be connected because we're implementing the strategy through these systems"* - but the graph doesn't know this because no single document explicitly states it.

**Current Limitation:** The graph can only show what documents say, not what the human *knows* but hasn't written down yet.

### Use Cases

1. **Cross-Domain Bridging:** Connecting business concepts to technical implementations
2. **Hypothesis Formation:** "I think this relates to that, let me test it"
3. **Domain Expert Corrections:** "This relationship is wrong/misleading"
4. **Emergent Insights:** Connections that become obvious only when viewing the graph
5. **Gap Filling:** Adding relationships that should be documented but aren't

## Decision

Implement **Human-Guided Graph Editing** system that treats human justifications as first-class evidence, feeding them back through the existing ingestion pipeline.

### Core Principles

1. **Human Justification as Evidence:** Treat human explanations as new source documents
2. **Pipeline Reuse:** Use existing `kg ingest` pipeline (no special graph mutation logic)
3. **Auditability:** All edits are traceable with human-provided justifications
4. **Reversibility:** Deletions mark relationships as invalid rather than removing them
5. **Teaching Ontology:** Special ontology for human-contributed knowledge

## Architecture

### 1. Connection Creation Flow

**UI Workflow:**
```
1. User multi-selects concepts across disconnected graphs
2. Right-click → "Connect These Concepts"
3. Modal appears: "Why are these concepts connected?"
   - Shows selected concept labels
   - Shows existing concept hints/search_terms from graph
   - Text area for human justification
   - Ontology selector (smart default)
4. User writes justification: "Enterprise strategy is implemented through
   NorthWind's integration systems because [reasoning]"
5. Submit → Feeds into ingestion pipeline
```

**Backend Processing:**
```typescript
POST /api/human-edit/connect
{
  concept_ids: ['concept_a_id', 'concept_b_id'],
  justification: "Human explanation here...",
  ontology: "human-teaching" | "best-fit-auto",
  editor_metadata: {
    timestamp: "2025-10-17T12:00:00Z",
    session_id: "uuid",
    confidence: "human-asserted"
  }
}
```

**Ingestion Pipeline:**
1. Create synthetic document from justification:
   ```json
   {
     "source": "human-edit:uuid",
     "document": "human-teaching/connection-2025-10-17-uuid.txt",
     "content": "The concept [Concept A] relates to [Concept B] because: [justification]",
     "metadata": {
       "type": "human-contribution",
       "editor": "session-id",
       "concepts": ["concept_a_id", "concept_b_id"]
     }
   }
   ```

2. Feed through `POST /ingest/text` endpoint
3. LLM extracts concepts + relationships (will likely create RELATES_TO edge)
4. Match phase recognizes concept IDs in synthetic doc
5. Graph update creates edge with human justification as evidence

**Result:** New relationship with traceable human justification as source

### 2. Ontology Selection Strategy

**Option A: Teaching Ontology (Recommended)**
- Create special `human-teaching` ontology
- All human contributions go here
- Clearly separates human insights from document-extracted knowledge
- Easy to query: "Show me what humans taught the system"

**Option B: Best-Fit Ontology**
- Analyze selected concepts' ontologies
- Choose ontology with most matches
- Example: 3 concepts from "tbm-model", 1 from "watts-lectures" → choose "tbm-model"

**Option C: Hybrid**
- User can choose ontology
- Smart default: `human-teaching`
- Advanced option: "Add to existing ontology"

**Decision:** Start with Option A (Teaching Ontology), add Option C selector later

### 3. Relationship Deletion Flow

**UI Workflow:**
```
1. User clicks edge between two concepts
2. Right-click → "Flag Relationship as Invalid"
3. Modal: "Why is this relationship incorrect?"
   - Shows: Source → Type → Target
   - Shows: Existing evidence instances
   - Text area for invalidation reason
4. User writes: "This connection is misleading because [reasoning]"
5. Submit → Creates invalidation record
```

**Backend Processing:**
```typescript
POST /api/human-edit/invalidate
{
  from_id: "concept_a_id",
  to_id: "concept_b_id",
  relationship_type: "IMPLIES",
  reason: "Human invalidation reason...",
  invalidation_metadata: {
    timestamp: "2025-10-17T12:00:00Z",
    session_id: "uuid"
  }
}
```

**Deletion Strategy - Soft Delete with Flag:**
```cypher
// Don't DELETE the relationship
// Instead, add metadata property
MATCH (a:Concept {concept_id: $from_id})-[r:IMPLIES]->(b:Concept {concept_id: $to_id})
SET r.invalidated = true,
    r.invalidated_reason = $reason,
    r.invalidated_at = timestamp(),
    r.invalidated_by = $session_id
RETURN r
```

**Query Filtering:**
- Default queries filter out `r.invalidated = true`
- Admin queries can show all relationships including invalidated
- Evidence instances remain (for auditability)

**Alternative: Create Counter-Relationship**
```cypher
CREATE (a)-[:INVALIDATES {
  target_relationship: "IMPLIES",
  reason: $reason,
  source: "human-edit:uuid"
}]->(b)
```
This preserves original relationship but marks it as disputed.

### 4. MCP Server Integration

**New MCP Tools:**

```typescript
// 1. Connect concepts with justification
{
  "name": "connect_concepts",
  "description": "Create relationship between concepts with human justification",
  "parameters": {
    "from_concept": "Concept label or ID",
    "to_concept": "Concept label or ID",
    "justification": "Why these concepts relate",
    "relationship_type": "RELATES_TO (default) | custom"
  }
}

// 2. Search for connection opportunities
{
  "name": "suggest_connections",
  "description": "Find potentially related concepts across disconnected graphs",
  "parameters": {
    "concept_id": "Starting concept",
    "semantic_similarity_threshold": 0.7
  }
}

// 3. Invalidate relationship
{
  "name": "invalidate_relationship",
  "description": "Flag relationship as incorrect with reason",
  "parameters": {
    "from_concept": "Source concept",
    "to_concept": "Target concept",
    "relationship_type": "Type to invalidate",
    "reason": "Why this is incorrect"
  }
}
```

**Claude-Assisted Workflow:**
```
User: "Connect enterprise strategy to NorthWind's systems"
Claude: [Uses search to find concepts]
Claude: "I found:
  - 'Enterprise Strategy' (12 instances)
  - 'NorthWind's Role' (8 instances)

  Why do you think these relate?"
User: "We're implementing the strategy through their integration platform"
Claude: [Calls connect_concepts with justification]
Claude: "Connected! Created RELATES_TO relationship in human-teaching ontology"
```

## Technical Implementation

### Phase 1: UI Components (viz-app)

**1. Multi-Select System**
```typescript
// Store selected nodes
const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());

// Shift+Click to multi-select
// Ctrl+Click to add to selection
// Visual: Selected nodes get blue ring (vs gold "You Are Here")
```

**2. Context Menu Extension**
```typescript
// If multiple nodes selected
contextMenuItems = [
  {
    label: "Connect These Concepts",
    icon: Link,
    onClick: () => openConnectModal(selectedNodes),
    disabled: selectedNodes.size < 2
  }
]

// If edge clicked
contextMenuItems = [
  {
    label: "Flag as Invalid",
    icon: AlertTriangle,
    onClick: () => openInvalidateModal(edge)
  }
]
```

**3. Connection Modal**
```tsx
<ConnectConceptsModal
  concepts={selectedConcepts}
  onSubmit={(justification, ontology) => {
    // Call API to create connection
  }}
>
  <ConceptList concepts={selectedConcepts} />
  <HintDisplay hints={aggregatedSearchTerms} />
  <TextArea
    label="Why are these connected?"
    placeholder="Explain the relationship..."
    required
  />
  <OntologySelector default="human-teaching" />
  <Actions>
    <Button variant="primary">Connect</Button>
    <Button variant="secondary">Cancel</Button>
  </Actions>
</ConnectConceptsModal>
```

### Phase 2: API Endpoints (FastAPI)

**File:** `src/api/routes/human_editing.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/human-edit", tags=["human-editing"])

class ConnectRequest(BaseModel):
    concept_ids: List[str]
    justification: str
    ontology: str = "human-teaching"
    relationship_type: str = "RELATES_TO"

class InvalidateRequest(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str
    reason: str

@router.post("/connect")
async def connect_concepts(req: ConnectRequest):
    """
    Create connection between concepts via human justification.

    Workflow:
    1. Validate all concept_ids exist
    2. Create synthetic document from justification
    3. Feed through ingestion pipeline
    4. Return job_id for status tracking
    """
    # Validate concepts exist
    for concept_id in req.concept_ids:
        concept = age_client.get_concept(concept_id)
        if not concept:
            raise HTTPException(404, f"Concept {concept_id} not found")

    # Build synthetic document
    concept_labels = [
        age_client.get_concept(cid)['label']
        for cid in req.concept_ids
    ]

    synthetic_doc = f"""
    Human-Contributed Connection ({datetime.now().isoformat()})

    Connected Concepts: {', '.join(concept_labels)}

    Justification:
    {req.justification}

    Metadata:
    - Type: Human-Guided Connection
    - Concept IDs: {', '.join(req.concept_ids)}
    - Relationship Type: {req.relationship_type}
    """

    # Create unique filename
    edit_id = str(uuid.uuid4())
    filename = f"human-edit-{datetime.now().strftime('%Y%m%d')}-{edit_id}.txt"

    # Submit to ingestion pipeline
    job = await ingest_text(
        text=synthetic_doc,
        ontology=req.ontology,
        filename=filename,
        force=False,
        auto_approve=True  # Human edits auto-approved
    )

    return {
        "status": "submitted",
        "job_id": job.job_id,
        "edit_id": edit_id,
        "message": f"Connection queued for processing. {len(req.concept_ids)} concepts."
    }

@router.post("/invalidate")
async def invalidate_relationship(req: InvalidateRequest):
    """
    Flag relationship as invalid with human reason.

    Uses soft-delete: adds invalidation metadata rather than removing.
    """
    # Validate relationship exists
    query = """
    MATCH (a:Concept {concept_id: $from_id})
          -[r:RELATIONSHIP {type: $rel_type}]->
          (b:Concept {concept_id: $to_id})
    RETURN r
    """

    result = age_client._execute_cypher(
        query,
        params={
            'from_id': req.from_id,
            'to_id': req.to_id,
            'rel_type': req.relationship_type
        },
        fetch_one=True
    )

    if not result:
        raise HTTPException(404, "Relationship not found")

    # Soft delete with invalidation flag
    invalidate_query = """
    MATCH (a:Concept {concept_id: $from_id})
          -[r:RELATIONSHIP {type: $rel_type}]->
          (b:Concept {concept_id: $to_id})
    SET r.invalidated = true,
        r.invalidated_reason = $reason,
        r.invalidated_at = timestamp(),
        r.invalidated_by = $session_id
    RETURN r
    """

    age_client._execute_cypher(
        invalidate_query,
        params={
            'from_id': req.from_id,
            'to_id': req.to_id,
            'rel_type': req.relationship_type,
            'reason': req.reason,
            'session_id': str(uuid.uuid4())
        }
    )

    return {
        "status": "invalidated",
        "from_id": req.from_id,
        "to_id": req.to_id,
        "relationship_type": req.relationship_type,
        "message": "Relationship flagged as invalid"
    }
```

### Phase 3: MCP Server Tools (TypeScript)

**File:** `client/src/mcp/tools/human-editing.ts`

```typescript
import { z } from 'zod';
import { apiClient } from '../../api/client';

export const connectConceptsTool = {
  name: 'connect_concepts',
  description: 'Create relationship between concepts with human justification',
  inputSchema: z.object({
    from_concept: z.string().describe('First concept label or ID'),
    to_concept: z.string().describe('Second concept label or ID'),
    justification: z.string().describe('Why these concepts are related'),
    relationship_type: z.string().optional().default('RELATES_TO'),
    ontology: z.string().optional().default('human-teaching')
  }),

  async execute(args: z.infer<typeof connectConceptsTool.inputSchema>) {
    // Search for concepts by label if not IDs
    const fromConcept = await resolveConceptId(args.from_concept);
    const toConcept = await resolveConceptId(args.to_concept);

    // Submit connection
    const result = await apiClient.post('/api/human-edit/connect', {
      concept_ids: [fromConcept.concept_id, toConcept.concept_id],
      justification: args.justification,
      relationship_type: args.relationship_type,
      ontology: args.ontology
    });

    return {
      content: [{
        type: 'text',
        text: `Connected "${fromConcept.label}" to "${toConcept.label}"
               via ${args.relationship_type}.
               Job ID: ${result.job_id}
               Status: ${result.status}`
      }]
    };
  }
};

async function resolveConceptId(query: string): Promise<{concept_id: string, label: string}> {
  // If looks like UUID, use directly
  if (query.match(/^[a-f0-9\-]{36}$/)) {
    const concept = await apiClient.get(`/query/concept/${query}`);
    return concept;
  }

  // Otherwise search by label
  const results = await apiClient.searchConcepts({
    query,
    limit: 1,
    min_similarity: 0.7
  });

  if (results.results.length === 0) {
    throw new Error(`Concept not found: ${query}`);
  }

  return results.results[0];
}
```

## Benefits

1. **Human Intelligence Integration:** Captures domain expertise and hunches
2. **Pipeline Reuse:** No special graph mutation logic - uses proven ingestion path
3. **Auditability:** Every edit has human justification as evidence
4. **Teaching Dataset:** `human-teaching` ontology becomes training data
5. **Gradual Knowledge Growth:** System learns from human corrections
6. **MCP Accessibility:** Claude can help users make connections
7. **Reversible:** Soft-delete preserves history

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Bad human edits** | Audit log with session tracking; review system |
| **Justification quality** | Require minimum text length; show hints |
| **Ontology pollution** | Separate `human-teaching` ontology by default |
| **Spam/abuse** | Rate limiting; session-based tracking |
| **LLM extraction variance** | Test synthetic doc format; validate outputs |

## Alternatives Considered

### Alternative 1: Direct Graph Mutation
Instead of ingestion pipeline, directly create edges in AGE.

**Rejected:** Bypasses evidence system, no auditability, loses LLM refinement.

### Alternative 2: Annotation System
Store human insights as metadata, don't modify graph.

**Rejected:** Insights aren't queryable via graph traversal, separate from evidence.

### Alternative 3: Separate "Human" Relationship Type
All human edits use `HUMAN_ASSERTS` relationship type.

**Considered:** Could combine with current proposal - human edits create `HUMAN_ASSERTS` edges that are clearly marked.

## Implementation Phases

### Phase 1: Core Connection Creation (Week 1-2)
- [ ] Multi-select UI in ForceGraph2D
- [ ] Connection modal with justification input
- [ ] `/api/human-edit/connect` endpoint
- [ ] Synthetic document generation
- [ ] Feed through existing ingestion pipeline
- [ ] `human-teaching` ontology creation

### Phase 2: Relationship Invalidation (Week 3)
- [ ] Edge click/select in visualization
- [ ] Invalidation modal
- [ ] `/api/human-edit/invalidate` endpoint
- [ ] Soft-delete with metadata flags
- [ ] Query filtering for invalidated edges

### Phase 3: MCP Integration (Week 4)
- [ ] `connect_concepts` MCP tool
- [ ] `suggest_connections` MCP tool
- [ ] `invalidate_relationship` MCP tool
- [ ] Concept label → ID resolution
- [ ] Documentation and examples

### Phase 4: Advanced Features (Future)
- [ ] Bulk connection creation
- [ ] Connection templates (common patterns)
- [ ] Confidence scoring for human edits
- [ ] Peer review system
- [ ] Analytics: "Most taught concepts"
- [ ] Export teaching dataset for model fine-tuning

## Success Metrics

- **Adoption:** Number of human connections created per week
- **Quality:** LLM successfully extracts relationships from 95%+ of justifications
- **Coverage:** Percentage of disconnected clusters bridged by humans
- **Retention:** Human-created edges remain valid (not later invalidated)
- **MCP Usage:** Claude successfully helps users create connections

## Example Scenarios

### Scenario 1: Cross-Domain Bridge
```
User sees:
- Cluster A: "Enterprise Strategy", "Cost Optimization", "Value Stream"
- Cluster B: "Integration Systems", "Data Flow", "Centralization"

User multi-selects: "Value Stream" + "Integration Systems"

Justification: "Value streams are enabled through integration systems
because they connect data flows between business processes and technical
implementation, allowing us to track end-to-end value delivery."

Result: New ENABLES relationship with human evidence
```

### Scenario 2: Correction
```
User sees edge: "Agile" -[CONTRADICTS]-> "Governance"

User thinks: "This is wrong - they complement each other"

Invalidation: "This relationship is misleading. Agile methodologies
don't contradict governance; they require different governance models
focused on lightweight, adaptive controls rather than heavy processes."

Result: Edge marked invalidated, hidden from default queries
```

### Scenario 3: MCP-Assisted Connection
```
User to Claude: "I think enterprise architecture relates to cloud migration"

Claude: [Searches concepts]
Claude: "Found these concepts:
  1. Enterprise Architecture (15 instances)
  2. Cloud Migration (22 instances)

  Why do you think they're related?"

User: "EA provides the framework and standards for cloud migration decisions"

Claude: [Calls connect_concepts]
Claude: "Connected! Created in human-teaching ontology. The system will
process this and extract the PROVIDES_FRAMEWORK relationship."
```

## Future Enhancements

1. **Collaborative Editing:** Multi-user sessions with conflict resolution
2. **Suggestion Engine:** AI suggests potential connections for human review
3. **Diff View:** Show before/after when human edits change graph structure
4. **Export/Import:** Share human teaching datasets between deployments
5. **Fine-Tuning Loop:** Use high-quality human justifications to improve LLM
6. **Gamification:** Reputation scores for quality human contributions

## Conclusion

Human-Guided Graph Editing transforms the knowledge graph from a read-only artifact into a collaborative thinking tool. By treating human justifications as first-class evidence and feeding them through the existing ingestion pipeline, we maintain system integrity while capturing irreplaceable human intelligence.

The "hunch" becomes queryable fact. The insight becomes evidence. The expert becomes teacher.

**Status:** Ready for implementation pending approval.
