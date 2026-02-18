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

## Embedding Unification

The key enabler for cross-type discovery: all node types share the same
embedding space. Concepts already have embeddings. If sources, sinks, and
connectors also have embeddings (derived from their descriptions, schemas,
tool definitions, or cached query results), then vector similarity works
across types automatically.

```
Embedding Space (shared):

  "database replication"  ←── concept (from ingested paper)
         ↕ cosine similarity
  "PostgreSQL monitoring" ←── connector (MCP server tool description)
         ↕ cosine similarity
  "DB metrics dashboard"  ←── data source (Grafana endpoint description)
         ↕ cosine similarity
  "backup verification"   ←── data sink (webhook purpose description)
```

### What Gets Embedded Per Type

| Node Type | Embedding Source |
|-----------|-----------------|
| Concept | Label + description (existing) |
| Connector | MCP tool descriptions, resource descriptions |
| Data Source | Schema description, cached sample data summary |
| Data Sink | Purpose description, filter/transform template |

### Ingestion Becomes Graph-Aware

When a document is ingested, the reasoning core:

1. Extracts concepts (existing behavior)
2. Embeds them (existing behavior)
3. Matches against existing concepts (existing behavior)
4. **NEW:** Also matches against connectors, sources, sinks
5. **NEW:** Creates cross-type edges where similarity is high
6. **NEW:** The graph grows its own operational wiring as knowledge enters

A document about Kubernetes pod autoscaling gets ingested. The reasoning
system extracts concepts, but also discovers: "there's a Kubernetes MCP
server connector in the graph with similar embeddings" and creates an edge.
No manual wiring. The graph learns what tools are relevant to what knowledge.

### Operational Ontologies

Custom ontologies can emerge that describe not just knowledge domains but
operational contexts — the combination of concepts, tools, sources, and sinks
that together represent a capability:

```
Ontology: "database-operations"
  ├── Concepts: replication, failover, backup, indexing, ...
  ├── Connectors: PostgreSQL MCP, MySQL MCP
  ├── Sources: Grafana metrics, slow query logs
  └── Sinks: PagerDuty webhook, backup verification endpoint
```

This ontology isn't just "knowledge about databases" — it's a complete
operational surface. An agent can ask: "what do I know about databases,
what tools can I use, where does the data come from, and where do results
go?"

## Ontology-Gated Access and Epistemic Permissions

External agents connect via MCP. Today, the MCP server executes queries
directly. In this architecture, the MCP server delegates to the platform
agent, which reasons about the question with graph context.

The critical design: **access is ontology-gated, and the agent knows it.**

```
External Agent ──MCP──→ Platform Agent
                              │
                    ┌─────────┴──────────┐
                    │  Ontology-Gated    │
                    │  Graph View        │
                    │                    │
                    │  Granted:          │
                    │    ontology-A ✓    │
                    │    ontology-B ✓    │
                    │                    │
                    │  Visible but       │
                    │  not traversable:  │
                    │    edge → onto-C ◐ │
                    │    edge → onto-D ◐ │
                    │                    │
                    │  The agent KNOWS   │
                    │  what it can't see │
                    └────────────────────┘
```

### Not a Wall — A Quality Knob

Traditional access control: "permission denied, you can't see this."

Ontology-gated epistemic access: "I can see an edge crosses into ontology C,
which I don't have access to. My answer is based on ontologies A and B.
There may be relevant knowledge in C that would improve this answer."

This serves three purposes simultaneously:

**Security.** Scope what an external agent can see. A customer-facing agent
gets access to the product ontology but not internal engineering ontologies.
The boundary is the ontology, which is already the organizational unit for
knowledge.

**Epistemic honesty.** The agent self-reports confidence based on what it
can and can't see. Cross-ontology edges that can't be followed are a
measurable signal: "I know my answer is incomplete because N edges lead to
knowledge I can't access." This reduces hallucination — the agent knows
what it doesn't know, rather than confabulating.

**Ablation.** Researchers (or the system itself) can restrict access to
study how knowledge connectivity affects answer quality. Run the same query
with full access vs. single-ontology access. Measure the difference. This
is a first-class feature, not a limitation.

### Hallucination Reduction Through Data Access

The core philosophy: hallucinations come from gaps between what an agent
is asked and what it can see. The remedy is not better prompting — it's
granting access to data. The knowledge graph is the data. Ontology gating
makes this tunable:

```
Access Level          Quality Signal
─────────────         ──────────────
Full graph access  →  Highest quality, all edges traversable
Multi-ontology     →  Good quality, some cross-ontology edges blocked
Single ontology    →  Focused but potentially incomplete
No graph access    →  Agent hallucinates (baseline for comparison)
```

This is measurable. The grounding scores, epistemic status classifications,
and cross-ontology edge counts already exist in the system. The permission
model maps directly onto the quality model.

## Platform Agent

The platform itself runs an agent loop. Not just a tool surface for external
agents — an active reasoning entity with the graph as persistent context.

```
Architecture:

  External Agent ──MCP──→ ┌─────────────────────┐
                          │                     │
  Platform Agent ──MCP──→ │   MCP Server        │
  (web UI)                │   (one platform)    │
                          │                     │
                          │   Same tools        │
                          │   Same OAuth grants │
                          │   Same ontology     │
                          │   gating            │
                          │                     │
                          └─────────┬───────────┘
                                    │
                              Graph + Connectors
```

There is no separate "internal agent API." The existing MCP server is the
agent capability surface for everyone. The platform agent running in the
web UI connects to the same MCP server as an external agent like Claude
Code. Same tools, same auth flow, same permission model. The differences
are just configuration:

- **Tool filtering**: Disable local-only tools (file path ingestion,
  directory scanning) for the platform agent. Disable web-UI-only tools
  for external CLI agents. The core graph tools are shared.
- **OAuth grants**: The platform agent is another OAuth client with its
  own scoped grants. Ontology access is controlled the same way as any
  external client.
- **No special code paths**: The MCP server doesn't know or care who's
  calling. This means the agent experience (prompt, tool selection,
  context management) can iterate without touching infrastructure.

The platform agent's advantages come from its persistent position, not
from privileged access:

- **Persistent context** — not limited to a single conversation; the
  graph IS the persistent memory
- **Connector traversal** — can follow edges to external MCP servers,
  chain tool calls, bring results back into the graph
- **Self-improving** — ingesting new documents enriches the context the
  agent reasons with; the agent can trigger ingestion of sources it
  discovers through connectors
- **Ontology-aware** — knows which ontologies are relevant, which are
  accessible, and can report what it couldn't see

This is comparable to Claude Desktop but purpose-built: the agent's "desktop"
is the knowledge graph, and its "tools" are the connectors embedded in the
graph itself. The web UI becomes the workspace where a human collaborates
with this agent — viewing what it found, steering where it looks, approving
what it ingests.

### Agent Runtime: Client-Side in the Browser

The agent loop runs in the browser, not on the server. No new server-side
agent infrastructure needed. The web app already has:

- OAuth tokens (authenticated API access)
- AI provider keys (stored encrypted in the platform, retrievable via API)
- REST client wrapping MCP tool endpoints (`web/src/api/client.ts`)

The chat client is a standard agent loop:

```
Browser (client-side):

  ┌─────────────────────────────────────────────┐
  │  Chat Component                             │
  │                                             │
  │  User message                               │
  │       │                                     │
  │       ▼                                     │
  │  LLM API call ──→ Anthropic/OpenAI          │
  │       │            (direct from browser,    │
  │       │             using platform keys)    │
  │       ▼                                     │
  │  Tool use response                          │
  │       │                                     │
  │       ▼                                     │
  │  Resolve against ──→ KG REST API            │
  │  API client           (same endpoints       │
  │       │                MCP server uses)     │
  │       ▼                                     │
  │  Feed results back to LLM                   │
  │       │                                     │
  │       ▼                                     │
  │  Render response + tool activity             │
  └─────────────────────────────────────────────┘
```

This is the same pattern as Claude Desktop, Cursor, or any tool-calling
chat client. The difference is the tool surface: instead of filesystem
and terminal tools, the tools are knowledge graph operations — search,
explore, ingest, connect, program execution.

The system prompt is seeded with the user's ontology grants and the graph's
current state (session_context already provides recent concepts). The
conversation history is the agent's working memory. The graph is the
agent's long-term memory.

### Agent Workspace in the UI

```
Sidebar:
  ...
  Agent                             ← new top-level
    ├── Chat                        ← conversation with platform agent
    ├── Context                     ← what the agent currently "knows"
    ├── Permissions                 ← ontology grants per client
    ├── Connector Status            ← live MCP server health
    └── Activity Log                ← what the agent did, what it found
```

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

### Phase 3: New Node Types + Embedding Unification
- Design Data Source / Sink / Connector node schemas
- All types get embeddings in the shared vector space
- Add Cypher node labels beyond Concept/Source
- Cross-type similarity matching during ingestion
- Connector edges (READS_FROM, WRITES_TO, QUERIES)

### Phase 4: Meta-MCP / Connector Nodes
- MCP server discovery as graph nodes
- Connector configuration and health monitoring UI
- Agent routing through knowledge graph
- Operational ontologies (concepts + tools + sources + sinks)

### Phase 5: Platform Agent
- Agent loop running inside the platform
- Graph as persistent context
- Connector traversal and tool chaining
- Agent workspace in web UI (chat, context, activity)
- Human-in-the-loop for ingestion approval, steering

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

6. **Embedding space compatibility** — MCP tool descriptions and document
   concepts use different vocabularies. Do they embed well in the same space?
   May need embedding model selection or fine-tuning for cross-type matching.

7. **Agent LLM selection** — The platform agent needs an LLM. Same provider
   as extraction? Configurable? Does the agent's model choice affect how it
   reasons about the graph?

8. **Connector authentication** — MCP servers may require auth. How does the
   platform agent authenticate to external tools? Per-connector credential
   storage? OAuth delegation?

9. **Agent autonomy boundaries** — How much can the platform agent do without
   human approval? Ingest new sources? Create connectors? Modify ontologies?
   The same approval gates that exist for ingestion jobs could extend to
   agent actions.
