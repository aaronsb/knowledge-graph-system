# Graph Object Platform Exploration

**Status:** Design exploration (not an ADR yet)
**Date:** 2026-02-18
**Branch:** `design/ontology-workspace-exploration`

## Context

The knowledge graph system was built as a vertically integrated concept
ingestion pipeline: documents go in, LLM extraction runs, concepts and
edges come out. Over time, the platform has grown capabilities that don't
fit this vertical model:

- Concepts can be created individually via API or MCP (not just via ingestion)
- Edge relationships are fully dynamic (created, typed, weighted independently)
- Ontologies have rich lifecycle management (scoring, annealing, dissolve)
- The MCP server already exposes the graph as a tool surface for AI agents

The current "Ingest" workspace in the web UI reflects this tension. It shows
ontology cards, supports drag-to-ingest, and is the only place ontologies are
visible as first-class objects. It's not really "ingest" anymore — it's
ontology management with an ingest action attached.

## The Shift

**From:** Document ingestion pipeline that produces concepts
**To:** Graph object platform where ingestion is one object management class

### Current Architecture (Vertical)

```
Documents ──→ Ingest Pipeline ──→ LLM Extraction ──→ Concepts + Edges ──→ Graph
                                                          │
                                                     (only output)
```

Everything flows one direction. The graph is a destination, not a workspace.

### Proposed Architecture (Horizontal)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Graph Object Platform                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              Reasoning Core (LLM)                     │      │
│  │                                                       │      │
│  │  The nucleus. Concepts and semantic edges flow         │      │
│  │  through LLM extraction, grounding, and epistemic     │      │
│  │  measurement. This is what makes it a KNOWLEDGE        │      │
│  │  graph, not just a graph database.                    │      │
│  │                                                       │      │
│  │  Documents → Extract → Ground → Measure → Evolve      │      │
│  └───────────────────────────────────────────────────────┘      │
│         ▲                                                       │
│         │ reasoning boundary                                    │
│         ▼                                                       │
│  Node Types:                                                    │
│    ├── Concept ★     (knowledge unit — reasoning-managed)       │
│    ├── Source         (data source — mechanical)                 │
│    ├── Sink           (data destination — mechanical)            │
│    ├── Connector      (live binding — mechanical)               │
│    └── ...future types                                          │
│                                                                 │
│  ★ = passes through reasoning core                              │
│      All other types are structural/mechanical                  │
│                                                                 │
│  Object Management Classes:                                     │
│    ├── Ingest         (bulk creation via reasoning core)         │
│    ├── Editor         (individual CRUD, any node type)           │
│    ├── Connector Mgr  (configure live external bindings)         │
│    └── ...future classes                                        │
│                                                                 │
│  Organizational:                                                │
│    └── Ontology       (container for nodes of any type)          │
│                                                                 │
│  Relationships:                                                 │
│    ├── Semantic edges ★  (IMPLIES, SUPPORTS, CONTRADICTS...)    │
│    ├── Structural edges  (APPEARS, EVIDENCED_BY, FROM_SOURCE)   │
│    └── Connector edges   (READS_FROM, WRITES_TO, QUERIES)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The reasoning core is the differentiator. Mechanical nodes (sources, sinks,
connectors) are managed directly — CRUD operations, configuration, wiring.
Knowledge nodes (concepts) pass through LLM reasoning: extraction, vector
matching against existing concepts, grounding measurement, epistemic
classification. The platform generalizes its object model while keeping
reasoning at the center.

This matters because when a connector points to an external MCP server, and
a concept has an edge to that connector, the reasoning system can chain:
"I found this concept, and I know where to learn more about it." The graph
doesn't just store knowledge — it reasons about where to find more.

### What Changes

| Aspect | Current | Proposed |
|--------|---------|----------|
| Node types | Concept only (plus Source as evidence) | Extensible: concept, source, sink, connector |
| Object creation | Ingest pipeline or manual API call | Multiple management classes per type |
| Ontology role | Implicit grouping during ingest | First-class container for any node type |
| Ingest | The feature | One management class among several |
| MCP server | Exposes graph read/write | Also becomes a connectable node type itself |

## New Node Type Ideas

### Data Source

A node representing an external data origin. Unlike the current `Source` node
(which is an evidence chunk from ingestion), a Data Source is a persistent,
queryable reference to where information lives.

```
Properties:
  - source_type: file | api | database | stream | mcp_server
  - connection_config: { url, auth_method, query_template }
  - refresh_policy: manual | periodic | on_change
  - last_synced_epoch: int
```

### Data Sink

A node representing an external destination. Concepts or query results can
flow outward.

```
Properties:
  - sink_type: webhook | file | api | mcp_server
  - trigger: manual | on_concept_create | on_epoch_change
  - filter: { ontology, node_type, min_grounding }
  - transform_template: string (output format)
```

### Connector (Meta-MCP)

This is where it gets interesting. If KG can represent MCP servers as graph
nodes, it becomes a meta-MCP server — a knowledge graph that knows about
other tool surfaces and can reason about their relationships.

```
Properties:
  - server_uri: string
  - transport: stdio | sse | streamable_http
  - capabilities: { tools: [...], resources: [...] }
  - abstraction_query: string (what to ask this server)
```

An edge from a Concept to a Connector might mean "this concept can be
explored further via this MCP server." The graph becomes a routing layer
for AI agent tool use.

Critically, this still flows through the reasoning core. When new documents
are ingested, the LLM doesn't just extract concepts — it could also recognize
that a concept relates to a known connector's domain and create that edge.
The reasoning system manages the *knowledge about tools*, not just the
knowledge from documents. Ingestion becomes: "here's a document, understand
it, place it in the graph, and figure out what else in the graph it connects
to — including external tool surfaces."

This is the meta-MCP idea: KG reasons about which tools are relevant to
which knowledge, and an agent querying the graph gets back not just concepts
but *paths to more information* through connected MCP servers.

## UI Restructuring

### Sidebar Navigation

```
Home

Explorers
  ├── 2D Force Graph
  ├── 3D Force Graph
  ├── Document Explorer
  ├── Polarity Explorer
  ├── Embedding Landscape
  ├── Edge Explorer
  └── Vocabulary Analysis

Ontologies                          ← renamed from "Ingest"
  ├── Overview                      ← new: ontology cards, stats, lifecycle
  ├── Ingest Content                ← existing drag-to-ingest
  ├── Node Types                    ← new: browse by type within ontology
  └── Annealing                     ← new: proposals, scoring

Block Editor
  └── Flow Editor

Jobs
  └── Job Queue

Report / Edit / Preferences / Admin  ← unchanged
```

### Ontology Overview (New)

Each ontology card could show:
- Name, description, lifecycle state (active/pinned/frozen)
- Node counts by type (concepts: 142, sources: 38, ...)
- Scores (mass, coherence, protection)
- Creation epoch, last activity
- Owner (when ownership model is used)
- Actions: rename, lifecycle change, dissolve, delete

### Node Type Browser (New)

Per-ontology breakdown of graph objects by type:
- Concept list with grounding scores
- Source evidence with document links
- Future: connectors, sources, sinks
- Could show type-specific schemas and creation forms

## Implementation Phases

### Phase 1: Ontology as First-Class UI Object
- Rename sidebar "Ingest" → "Ontologies"
- Create OntologyOverview workspace (cards with stats + lifecycle)
- Move ingest under Ontologies as a sub-item
- Wire up existing API endpoints (info, scores, lifecycle, rename, delete)

### Phase 2: Node Type Awareness
- Add node type browser per ontology
- Show concept counts, source counts per ontology
- Surface graph node schema in the UI

### Phase 3: New Node Types (requires API work)
- Design Data Source / Sink node schema
- Add Cypher node labels beyond Concept/Source
- Create management UIs per type
- Connector edges (READS_FROM, WRITES_TO)

### Phase 4: Meta-MCP / Connector Nodes
- MCP server discovery as graph nodes
- Connector configuration UI
- Agent routing through knowledge graph
- KG as meta-tool-surface

## Open Questions

1. **Ontology ownership model** — The database has ownership fields but
   they're unused. What's the intended permission model? Per-ontology ACLs?
   Or just audit trail (who created it)?

2. **Node type extensibility** — Should node types be hardcoded labels in
   AGE (like Concept, Source) or should there be a type registry that's
   itself stored in the graph?

3. **Connector lifecycle** — If an MCP server goes offline, what happens to
   its node and edges? Soft-delete? Staleness marker? Epoch-based expiry?

4. **Ingest as management class** — Does the ingest pipeline become a
   "Concept Manager" specifically, or does it stay generic (could ingest
   into Source nodes too)?

5. **Graph schema evolution** — Adding new node labels to Apache AGE requires
   migrations. How do we handle schema evolution as new types are added?
