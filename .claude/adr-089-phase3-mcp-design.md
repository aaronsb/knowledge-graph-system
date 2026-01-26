# ADR-089 Phase 3: Graph Editing Design

## Overview

Design notes for deterministic graph editing across **all interfaces**: Import, CLI, MCP, and Web Workstation. While MCP has unique context management challenges, the core concepts (working sets, modes, semantic resolution) should be consistent across all entry points.

**Future consideration**: Graph may expand beyond `Concept` nodes to include `Action`, `Goal`, `Evidence`, and other node types. This design should accommodate that evolution.

---

## Industry Research (Jan 2026)

Research into existing agent-graph systems validates our approach and provides concrete guidance.

### Validation of Our Concepts

| Our Concept | Industry Evidence | Source |
|-------------|-------------------|--------|
| **Working Set** | Letta Memory Blocks, MemGPT self-editing memory, scratchpad patterns | [Letta](https://www.letta.com/blog/memory-blocks) |
| **Intent Modes** | LangChain tool-based vs prompt modes; Graphiti invalidation vs deletion | [LangChain](https://python.langchain.com/docs/how_to/graph_constructing/) |
| **Session State** | LangGraph StateGraph, MCP inherently stateful, ADK Sessions | [LangGraph](https://github.com/langchain-ai/langgraph) |
| **Semantic Resolution** | Graphiti entity resolution, GraphRAG patterns widely adopted | [Graphiti](https://github.com/getzep/graphiti) |
| **MCP for Graphs** | Neo4j MCP servers, Graphiti MCP server already exist | [Neo4j MCP](https://github.com/neo4j-contrib/mcp-neo4j) |

### Critical Requirements from Research

1. **Entity Resolution Accuracy ≥85%** - Errors compound with each graph traversal. Below 85%, the system becomes unreliable. ([Zep Paper](https://arxiv.org/abs/2501.13956))

2. **Observation Masking > LLM Summarization** - JetBrains research found masking outperforms summarization for context management. Keep recent items in full, mask older ones. ([JetBrains](https://blog.jetbrains.com/research/2025/12/efficient-context-management/))

3. **Large Context Windows Don't Help** - "Needle in haystack" research proves information buried in massive context is ignored. Working sets are the right approach. ([Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents))

4. **Vector Stores Alone Fail** - Multi-hop reasoning requires graphs; vector-only approaches fail for complex queries. Our graph-first approach is validated.

### Concrete Numbers from Research

| Parameter | Research Finding | Our Decision |
|-----------|------------------|--------------|
| Working set window | Keep latest 10 turns in full | 10-item "hot" window |
| Summarization batch | Summarize 21 turns at a time | Summarize when evicting |
| Entity resolution threshold | 85%+ required for reliability | Use 85% match threshold |
| Graph query timeout | Complex traversals can hang | max_hops=3, threshold≥0.75 (existing) |

### Similar Projects to Study

- **[Graphiti](https://github.com/getzep/graphiti)** - Most similar: real-time KG with bi-temporal model, entity resolution, MCP server
- **[Neo4j MCP Servers](https://github.com/neo4j-contrib/mcp-neo4j)** - Production MCP+graph patterns
- **[Letta/MemGPT](https://docs.letta.com/concepts/memgpt/)** - Memory block architecture, self-editing context
- **[LangGraph](https://github.com/langchain-ai/langgraph)** - State graph for agent workflows

### Anti-Patterns to Avoid

| Anti-Pattern | Problem | Our Mitigation |
|--------------|---------|----------------|
| Context poisoning | Hallucinations contaminate future reasoning | Working set isolation, checkpoint/reset |
| Context distraction | Too much info overwhelms decision-making | 10-item hot window, on-demand expansion |
| "Context as memory" | No learning loop, inconsistent decisions | Explicit session state, not just context |
| Retrieve-only memory | No feedback on retrieval quality | Return similar concepts for agent to validate |

---

## Interfaces

Four ways to edit the graph, all using the same underlying API:

| Interface | User | Characteristics | Session State |
|-----------|------|-----------------|---------------|
| **Import** | Scripts, pipelines | Batch, fire-and-forget, high volume | None (stateless) |
| **CLI** | Developers, operators | Interactive or scripted, medium volume | Optional (flags) |
| **MCP** | AI agents | Conversational, needs breadcrumbs, token-limited | Required (working set) |
| **Web** | Humans | Visual, drag-drop, real-time feedback | Browser state |

### Interface Capabilities Matrix

| Capability | Import | CLI | MCP | Web |
|------------|--------|-----|-----|-----|
| Batch create | ✅ Primary | ✅ `kg batch` | ⚠️ Possible | ❌ |
| Single create | ✅ | ✅ `kg concept create` | ✅ | ✅ |
| Interactive wizard | ❌ | ✅ `-i` flag | ❌ | ✅ Native |
| Semantic resolution | ✅ Labels | ✅ `--from-label` | ✅ Required | ✅ Search-first |
| Working set | ❌ | ❌ | ✅ Required | ✅ Canvas |
| Undo/history | ❌ | ❌ | ⚠️ Checkpoint | ✅ Native |
| Suggestions | ❌ | ❌ | ✅ `graph/suggestions` | ✅ UI hints |
| Visual feedback | ❌ | ❌ | ❌ | ✅ Primary |

---

## Usage Scenarios

### Content Integration

| # | Scenario | Description | Key Need |
|---|----------|-------------|----------|
| 1 | **Document enrichment** | Ingest documents → review → find gaps → add strategic concepts | Gap detection, targeted additions |
| 2 | **Process codification** | Create specific concepts reflecting a workflow or methodology | Precise topology control |
| 3 | **Free association** | Share concepts freely, let graph find attachment points | High deduplication, auto-linking |
| 4 | **Mind mapping** | Explore ideas interactively, build as you think | Fast iteration, undo-friendly |
| 5 | **Evidence attachment** | Add supporting quotes/sources to existing concepts | Target existing nodes, append-only |

### Knowledge Work

| # | Scenario | Description | Key Need |
|---|----------|-------------|----------|
| 6 | **Debate mapping** | Capture opposing viewpoints with evidence chains | Bidirectional edges, attribution |
| 7 | **Knowledge transfer** | Expert dictates institutional knowledge | Stream capture, loose structure |
| 8 | **Literature synthesis** | Connect concepts across multiple papers | Multi-source dedup, citation tracking |
| 9 | **Root cause analysis** | Build causal chains from symptoms to causes | Linear chains, CAUSES relationships |
| 10 | **Goal decomposition** | Break objectives into sub-tasks/requirements | Hierarchical REQUIRES/ENABLES |

### Maintenance & Refinement

| # | Scenario | Description | Key Need |
|---|----------|-------------|----------|
| 11 | **Comparative analysis** | Map similarities and differences between systems | Parallel structures, SIMILAR_TO |
| 12 | **Correction/refinement** | Fix, improve, or merge existing concepts | Edit history, merge support |
| 13 | **Q&A enrichment** | Agent answers questions, captures insights as concepts | Opportunistic attachment |
| 14 | **Gap analysis** | Identify missing connections or orphaned concepts | Graph introspection |
| 15 | **Consolidation** | Merge duplicate or near-duplicate concepts | Similarity detection, bulk ops |

### Scenario × Interface Fit

Which interface suits which scenario best:

| Scenario | Import | CLI | MCP | Web | Notes |
|----------|:------:|:---:|:---:|:---:|-------|
| 1. Document enrichment | ✅ | ⚠️ | ✅ | ⚠️ | Import bulk, MCP/CLI for gaps |
| 2. Process codification | ⚠️ | ✅ | ✅ | ✅ | Precise control needed |
| 3. Free association | ⚠️ | ⚠️ | ✅ | ✅ | AI/visual excel here |
| 4. Mind mapping | ❌ | ❌ | ✅ | ✅ | Interactive, exploratory |
| 5. Evidence attachment | ⚠️ | ✅ | ✅ | ✅ | Target existing nodes |
| 6. Debate mapping | ❌ | ⚠️ | ✅ | ✅ | Structure matters |
| 7. Knowledge transfer | ⚠️ | ⚠️ | ✅ | ❌ | Stream of consciousness |
| 8. Literature synthesis | ✅ | ⚠️ | ✅ | ⚠️ | Bulk + refinement |
| 9. Root cause analysis | ❌ | ⚠️ | ✅ | ✅ | Build chains iteratively |
| 10. Goal decomposition | ❌ | ⚠️ | ✅ | ✅ | Hierarchical, visual helps |
| 11. Comparative analysis | ⚠️ | ⚠️ | ✅ | ✅ | Parallel structures |
| 12. Correction/refinement | ❌ | ✅ | ✅ | ✅ | Need to see before editing |
| 13. Q&A enrichment | ❌ | ❌ | ✅ | ❌ | Agent-native |
| 14. Gap analysis | ❌ | ⚠️ | ✅ | ✅ | Visualization helps |
| 15. Consolidation | ⚠️ | ✅ | ⚠️ | ✅ | Bulk ops + visual review |

✅ = Primary fit | ⚠️ = Possible | ❌ = Poor fit

**Key insight**: MCP and Web cover nearly all scenarios. Import is for bulk/pipeline. CLI bridges scripting and interactive.

---

## The Context Token Problem

AI agents face a fundamental tension:
- **Need context** to avoid duplicates and make good connections
- **Limited tokens** prevent loading entire ontologies
- **Session amnesia** loses track of what was just created

### Context Requirements by Scenario

| Scenario | Must Know | Can Ignore |
|----------|-----------|------------|
| Mind mapping | Recent creates, nearby | Full ontology |
| Literature synthesis | Domain concepts, duplicates | Other ontologies |
| Root cause | Current causal chain | Parallel concepts |
| Correction | Target concept history | Unrelated concepts |
| Free association | Similar concepts | Structure/topology |

---

## Design Concepts

These concepts apply across interfaces, but with different implementations:

| Concept | Import | CLI | MCP | Web |
|---------|:------:|:---:|:---:|:---:|
| 1. Working Set | ❌ | ❌ | ✅ Server-side | ✅ Canvas state |
| 2. Intent Modes | ✅ `matching_mode` | ✅ `--matching-mode` | ✅ `mode` param | ✅ UI toggle |
| 3. Semantic Resolution | ✅ `from_label` | ✅ `--from-label` | ✅ Default | ✅ Search-first |
| 4. Session Resource | ❌ | ❌ | ✅ `graph/session` | ✅ UI state |
| 5. Compound Ops | ✅ Batch | ⚠️ Pipe-able | ✅ Single call | ✅ Drag-drop |
| 6. Checkpoint | ❌ | ❌ | ✅ Named saves | ✅ Auto-save |
| 7. Suggestions | ❌ | ❌ | ✅ Resource | ✅ UI hints |

### 1. Working Set

The core abstraction: a scoped "scratchpad" of concepts the agent is actively working with.

```
Working Set = {
  // Hot window (always returned in full) - max 10 items per JetBrains research
  hot: [c_abc, c_def, ...],           // Most recent 10 concepts touched
  hot_edges: [e_1, e_2, ...],         // Most recent 10 edges created

  // Warm set (summarized, available on request)
  warm: [c_older1, c_older2, ...],    // Older items, FIFO eviction from hot

  // Context
  focus_query: "distributed systems", // Optional semantic filter
  ontology: "tech-notes",             // Scope boundary
  neighbors: [c_xyz, c_123]           // 1-hop from hot set (computed on demand)
}
```

**Research-Backed Design:**
- **10-item hot window**: JetBrains research found keeping latest 10 turns in full optimal
- **Observation masking**: Older items are summarized, not deleted
- **On-demand neighbors**: 1-hop expansion only when requested (performance)

**Benefits:**
- Prevents context explosion (only return relevant concepts)
- Enables smart suggestions ("based on your working set...")
- Provides breadcrumbs for what was just created
- Natural checkpoint boundary
- Aligns with industry best practices for agent memory

### 2. Intent-Driven Modes

Different modes for different scenarios:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `strict` | Error if >80% match exists | Precise process codification |
| `auto` | Link if match, create if not | General use (default) |
| `force` | Always create new | Parallel structures, comparisons |
| `enrich` | Add to existing concept | Evidence attachment |
| `explore` | Create loosely, auto-link | Mind mapping, free association |

### 3. Semantic Resolution

Allow concepts to be referenced by label, not just ID:

```
# Instead of requiring:
from_id: "c_a1b2c3d4"

# Allow:
from_label: "CAP Theorem"
from_query: "distributed consistency"  # Fuzzy match
```

Resolution returns confidence so agent can confirm if uncertain.

### 4. Session State Resource

MCP Resource `graph/session` that the agent can read anytime:

```
Session: mind-mapping-distributed-systems
Started: 5 minutes ago
Ontology: tech-notes

Recently Created:
  c_abc123: "CAP Theorem" (2 min ago)
  c_def456: "Partition Tolerance" (1 min ago)
  Edge: c_abc123 -[REQUIRES]-> c_def456

Working Set (4 concepts):
  - CAP Theorem
  - Partition Tolerance
  - Consistency Models (matched existing)
  - Availability Guarantees

Suggestions:
  - "Network Partitions" (82% similar to working set, not connected)
  - Gap: No CONTRADICTS edges in working set
```

### 5. Compound Operations

Single calls that do multiple things and return rich context:

```
graph action:"create_and_connect"
  label: "Eventual Consistency"
  connect_to: "CAP Theorem"
  relationship: "ENABLES"

Returns:
  created: c_ghi789
  connected_to: c_abc123 (CAP Theorem)
  edge: c_abc123 -[ENABLES]-> c_ghi789
  similar_existing: ["Consistency Models" (78%)]
  working_set_size: 5
```

### 6. Checkpoint/Resume

Persist working set across sessions:

```
# Save state
graph action:"checkpoint" name:"ml-safety-review"

# Later session
graph action:"resume" name:"ml-safety-review"
→ Restores working set, shows last activity, suggests next steps
```

### 7. Focused Suggestions

Server proactively identifies opportunities:

```
graph action:"suggest"
  type: "gaps"        # Missing connections
  type: "duplicates"  # Potential merges
  type: "orphans"     # Unconnected concepts
  type: "next"        # What to explore next
```

---

## MCP Tool Design

### Decision: Option A - Single `graph` Tool

**Rationale**: Mirrors the existing `concept` tool pattern (details/related/connect actions). Keeps tool count manageable. Complex schema is acceptable given good documentation.

```typescript
{
  name: 'graph',
  description: 'Create, edit, and manage the knowledge graph. Maintains a working set for context.',
  inputSchema: {
    action: {
      type: 'string',
      enum: ['create', 'edit', 'delete', 'list', 'connect',
             'session', 'checkpoint', 'resume', 'suggest'],
      description: 'Operation to perform'
    },
    // Entity type
    entity: {
      type: 'string',
      enum: ['concept', 'edge'],
      description: 'Entity type (for create/edit/delete/list)'
    },
    // Creation mode
    mode: {
      type: 'string',
      enum: ['strict', 'auto', 'force', 'enrich', 'explore'],
      default: 'auto',
      description: 'How to handle duplicates'
    },
    // Semantic resolution
    label: { type: 'string', description: 'Concept label (for create)' },
    from_label: { type: 'string', description: 'Source concept by label' },
    to_label: { type: 'string', description: 'Target concept by label' },
    // ... additional action-specific params
  }
}
```

### Alternatives Considered

**Option B: Separate Tools** - `graph_create`, `graph_edit`, etc.
- Rejected: Tool proliferation, harder to discover

**Option C: Extend `concept` Tool** - Add write actions to existing tool
- Rejected: Breaks read-only expectation, confuses existing users

---

## MCP Resources

| Resource | Description | Updates |
|----------|-------------|---------|
| `graph/session` | Current working set, recent activity | On each mutation |
| `graph/suggestions` | Gaps, duplicates, next steps | On request |
| `graph/checkpoints` | List of saved checkpoints | On checkpoint ops |

---

## Future: Multi-Node Types

When graph expands beyond Concepts:

```
Node Types:
  Concept   - Ideas, definitions, entities
  Action    - Verbs, operations, processes
  Goal      - Objectives, targets, outcomes
  Evidence  - Quotes, citations, data points
  Question  - Open inquiries, unknowns

Edge semantics change:
  Action -[ACHIEVES]-> Goal
  Evidence -[SUPPORTS]-> Concept
  Question -[ABOUT]-> Concept
  Action -[REQUIRES]-> Concept
```

The Working Set and Session abstractions should work across node types.

---

## Implementation Phases

### Phase 3a: MCP Core CRUD

Add `graph` tool to MCP server with basic CRUD operations.

**MCP Tool:**
- [ ] `graph action:"create" entity:"concept"` - Create concept
- [ ] `graph action:"create" entity:"edge"` - Create edge
- [ ] `graph action:"edit"` - Update concept/edge
- [ ] `graph action:"delete"` - Delete concept/edge
- [ ] `graph action:"list"` - List with filters

**Features:**
- [ ] Semantic resolution (label lookup via existing search)
- [ ] Mode support (strict/auto/force) using existing `matching_mode`
- [ ] Return created entity + similar concepts for context
- [ ] Reuse CLI validation library where possible

**Files:**
- `cli/src/mcp-server.ts` - Add graph tool definition + handler
- `cli/src/mcp/formatters.ts` - Add graph result formatters

### Phase 3b: Session State

Track working set for context breadcrumbs. Based on JetBrains research on optimal context windows.

**MCP Resource:**
- [ ] `graph/session` - Current working set, recent mutations

**Working Set (in-memory):**
- [ ] **Hot window (10 items)**: Most recent concepts/edges in full detail
- [ ] **Warm set (40 items)**: Older items with label + ID only (summarized)
- [ ] Track concepts touched (viewed/edited) separately from created
- [ ] Compute 1-hop neighbors on demand (not stored)
- [ ] FIFO eviction: hot → warm → evicted

**Mutation Returns:**
- [ ] Include hot window in all responses
- [ ] Include "nearby" concepts (1-hop from hot set)
- [ ] Include potential duplicates (≥85% similarity)
- [ ] Flag if entity resolution was uncertain (<90% match)

### Phase 3c: Persistence & Suggestions

Named checkpoints and smart recommendations.

**Checkpoint/Resume:**
- [ ] `graph action:"checkpoint" name:"..."` - Save working set
- [ ] `graph action:"resume" name:"..."` - Restore working set
- [ ] Store checkpoints in localStorage or API (TBD)

**Suggestions Resource:**
- [ ] `graph/suggestions` - Gaps, duplicates, orphans, next steps
- [ ] Based on working set analysis
- [ ] On-demand (not proactive)

### Phase 3d: Web Workstation (Future)

Visual graph editing with shared concepts.

- [ ] Canvas-based working set (visual equivalent)
- [ ] Drag-drop concept creation
- [ ] Visual edge creation
- [ ] Same modes (strict/auto/force) as toggle
- [ ] Real-time similar concept hints
- [ ] Undo/redo stack

---

## Design Decisions (Research-Informed)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Session scope** | Per-connection + optional checkpoints | MCP is inherently stateful per-connection; checkpoints enable handoff |
| **Working set limits** | 10 hot + 40 warm (FIFO) | JetBrains: 10-item window optimal; 50 total before hard eviction |
| **Suggestion triggers** | On-demand only | Avoids context distraction anti-pattern |
| **Multi-agent** | No shared state | Per-connection isolation prevents context poisoning |
| **Undo** | No for MCP, Yes for Web | Graphiti pattern: invalidate edges, don't delete (temporal model) |
| **Entity resolution threshold** | 85% similarity | Below this, error compounding makes system unreliable |

## Remaining Open Questions

1. **Checkpoint storage**: localStorage (client-side) vs API (server-side)?
   - Trade-off: Simplicity vs cross-device access

2. **Warm set representation**: Full summaries or just IDs + labels?
   - Trade-off: Token cost vs context richness

3. **Neighbor depth**: Always 1-hop, or configurable?
   - Trade-off: Performance vs exploration breadth

---

## References

### MCP Protocol
- [MCP Specification (Nov 2025)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Resources](https://spec.modelcontextprotocol.io/specification/server/resources/)
- [MCP Sampling](https://spec.modelcontextprotocol.io/specification/server/sampling/)
- [MCP Session Management](https://zeo.org/resources/blog/mcp-server-architecture-state-management-security-tool-orchestration)

### Agent Memory Research
- [Effective Context Engineering - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Efficient Context Management - JetBrains](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)
- [Memory Engineering for Multi-Agent Systems - MongoDB](https://www.mongodb.com/company/blog/technical/why-multi-agent-systems-need-memory-engineering)
- [Context Engineering for Agents - LangChain](https://rlancemartin.github.io/2025/06/23/context_engineering/)

### Graph + Agent Frameworks
- [Graphiti - Real-Time Knowledge Graphs](https://github.com/getzep/graphiti)
- [Zep Temporal KG Paper](https://arxiv.org/abs/2501.13956)
- [Neo4j MCP Servers](https://github.com/neo4j-contrib/mcp-neo4j)
- [LangGraph - Resilient Language Agents](https://github.com/langchain-ai/langgraph)
- [Letta Memory Blocks](https://www.letta.com/blog/memory-blocks)
- [MemGPT Documentation](https://docs.letta.com/concepts/memgpt/)

### Internal ADRs
- ADR-089: Deterministic Node/Edge Creation
- ADR-013: MCP Tool Consolidation
- ADR-048: Query Safety (max_hops, thresholds)
