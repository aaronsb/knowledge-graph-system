---
status: Draft
date: 2026-01-29
deciders:
  - aaronsb
  - claude
related: [82, 83, 84, 89, 200]
---

# ADR-700: Ontology Explorer

## Context

The web workstation offers several specialized explorers, each addressing a different facet of the knowledge graph:

| Explorer | Focus | Data Shape |
|----------|-------|------------|
| Force Graph 2D/3D | Concept relationships, topology | graph |
| Document Explorer | Single document's concept radiation | tree |
| Polarity Explorer | Oppositional concept axes | projection |
| Embedding Landscape | Visual embedding space | density |
| Edge Explorer | Relationship vocabulary structure | vocabulary |
| Vocabulary Analysis | Query-driven edge analysis | vocabulary |

**What's missing:** There is no explorer dedicated to **ontologies** — the primary organizational unit of the knowledge graph. Ontologies group documents and their extracted concepts into coherent knowledge domains, yet users have no way to:

1. **See the landscape** — What ontologies exist, how large are they, how do they relate?
2. **Explore within** — What documents and concepts belong to an ontology? What's its internal structure?
3. **Discover bridges** — Which concepts span multiple ontologies? Where does knowledge converge across domains?
4. **Manage** — Create, rename, reorganize, or delete ontologies without dropping to CLI or raw API calls.

Currently, the only UI touchpoint for ontologies is `OntologyFilterBlock` — a query builder filter that lets users include/exclude ontologies from graph queries. Ontology administration lives exclusively in the CLI (`kg ontology list|info|files|rename|delete`) and REST API (`/ontology/` endpoints).

This gap is significant because **cross-ontology concept linking** is a defining capability of the system. Documents are isolated per ontology, but concepts merge automatically across domains via semantic similarity (ADR-068). This creates a rich inter-domain knowledge fabric that no current explorer surfaces.

## Decision

### 1. New Explorer: Ontology Explorer

Add an **Ontology Explorer** to the web workstation following the existing plugin registry pattern (`registerExplorer()`). The explorer operates in three interconnected views:

#### Overview (Landscape View)

A high-level map of all ontologies the user can access. Visualization options:

- **Treemap** — Ontologies as nested rectangles sized by concept or document count. Intuitive for comparing relative scale.
- **Bubble pack** — Circles with area proportional to content, colored by a chosen metric (document count, concept density, recency of updates).

Each ontology node shows:
- Name, ontology ID, lifecycle state (ADR-200 graph node properties)
- Document count, concept count, relationship count
- Creation epoch, embedding status
- Last modified / last ingested timestamp
- Owner (if resource-scoped via ADR-082 grants)

Clicking an ontology transitions to the Detail View.

#### Detail View (Single Ontology)

Drill into one ontology to see its composition:

- **Document list** — All documents (files) in the ontology with per-file stats (chunk count, concept count). Sortable and searchable.
- **Concept cloud** — Top concepts extracted from this ontology, sized by evidence count or grounding strength.
- **Internal graph** — A subgraph view (reusing the existing ForceGraph2D data transformer) filtered to only show concepts and relationships sourced from this ontology.
- **Statistics panel** — Source count, file count, concept count, instance count, relationship count, average grounding strength.

The detail view acts as a launchpad: clicking a concept can navigate to the Force Graph explorer centered on that concept; clicking a document can open the Document Explorer for that document.

#### Bridge View (Cross-Ontology)

Visualize how ontologies connect through shared concepts:

- **Chord diagram** — Ontologies around the perimeter, chords connecting pairs that share concepts. Chord thickness proportional to shared concept count.
- **Shared concept list** — For a selected pair of ontologies, list the bridging concepts with their grounding strength in each domain.
- **Bridge metrics** — Overlap percentage, unique-to-each counts, strongest/weakest bridges.

This view makes the cross-ontology linking (which happens silently during ingestion) visible and explorable.

### 2. Interaction Model

The Ontology Explorer is not view-only. It supports management actions gated by the existing RBAC system (ADR-028, ADR-082):

| Action | Minimum Role | API Endpoint |
|--------|-------------|--------------|
| View ontology list & stats | `read_only` | `GET /ontology/` |
| View ontology details | `read_only` | `GET /ontology/{name}` |
| View ontology files | `read_only` | `GET /ontology/{name}/files` |
| Create new ontology | `curator` | `POST /ontology/` |
| Rename ontology | `curator` | `POST /ontology/{name}/rename` |
| Delete ontology | `admin` | `DELETE /ontology/{name}` |
| Re-ingest documents | `contributor` | `POST /ingest` (existing) |

UI affordances:
- **Create**: A "New Ontology" action in the overview toolbar. Prompts for name and optional description.
- **Rename**: Inline edit or context menu on ontology nodes. Confirms before executing (atomic rename via existing API).
- **Delete**: Context menu with confirmation dialog showing cascade impact (source count, orphan concept count). Requires `force` flag.
- **Drag-to-reorganize** (future): Move documents between ontologies by dragging from one detail view to another. This requires a new API endpoint for document reassignment.

Actions that exceed the user's permissions are hidden or disabled, not shown-then-rejected. The `authStore.hasPermission()` check drives UI visibility.

### 3. Data Requirements

#### Existing API endpoints (ADR-200 foundation)

Ontologies are first-class graph nodes with properties (`ontology_id`, `lifecycle_state`, `creation_epoch`, `embedding`, `search_terms`). ADR-200 established this architecture and exposed it across API, CLI, MCP, and web types.

- `GET /ontology/` — List all ontologies with graph node properties and source stats. Graph nodes are source of truth (includes empty ontologies from directed growth).
- `GET /ontology/{name}` — Detail stats + file list + `node` object with full graph node properties.
- `GET /ontology/{name}/node` — Graph node properties only (ADR-200).
- `GET /ontology/{name}/files` — Per-file breakdown.
- `POST /ontology/` — Create ontology explicitly (directed growth). Generates name-based embedding. (ADR-200)
- `POST /ontology/{name}/rename` — Rename (updates graph node + source properties).
- `DELETE /ontology/{name}` — Delete with cascade (removes graph node + SCOPED_BY edges).

#### New API endpoints needed

| Endpoint | Purpose |
|----------|---------|
| `GET /ontology/{name}/concepts` | List concepts extracted from this ontology, with stats (evidence count, grounding, relationship count). Paginated. |
| `GET /ontology/{name}/subgraph` | Return the internal concept graph for this ontology (nodes + edges where at least one endpoint has evidence in the ontology). Reuses `SubgraphResponse` format. |
| `GET /ontology/bridges` | Cross-ontology shared concept summary. Returns pairs of ontologies with shared concept count and top bridging concepts. Optional filter by specific ontology names. |

#### Data Shape

The Ontology Explorer uses a hybrid data shape — it doesn't fit neatly into `graph`, `tree`, or `flow`:

```typescript
interface OntologyExplorerData {
  // Overview
  ontologies: OntologyNode[];
  bridges: OntologyBridge[];

  // Detail (loaded on drill-down)
  activeOntology?: {
    name: string;
    statistics: OntologyStatistics;
    documents: OntologyDocument[];
    topConcepts: ConceptSummary[];
    subgraph?: SubgraphResponse;  // Reuse existing type
  };
}

interface OntologyNode {
  name: string;
  ontologyId: string;           // ADR-200 graph node UUID
  lifecycleState: string;       // ADR-200: 'active' | 'pinned' | 'frozen'
  creationEpoch: number;        // ADR-200: epoch at creation
  hasEmbedding: boolean;        // ADR-200: whether embedding vector exists
  description?: string;         // ADR-200: domain description
  searchTerms?: string[];       // ADR-200: alternative search terms
  documentCount: number;
  conceptCount: number;
  relationshipCount: number;
  sourceCount: number;
  lastModified?: string;
  owner?: string;
}

interface OntologyBridge {
  from: string;           // Ontology name
  to: string;             // Ontology name
  sharedConceptCount: number;
  topBridgingConcepts: Array<{
    conceptId: string;
    label: string;
    groundingInFrom: number;
    groundingInTo: number;
  }>;
}
```

### 4. Plugin Integration

Follows the established pattern:

```
web/src/explorers/OntologyExplorer/
├── OntologyExplorer.tsx     # Main component (view orchestration)
├── OverviewView.tsx         # Treemap / bubble pack
├── DetailView.tsx           # Single ontology drill-down
├── BridgeView.tsx           # Cross-ontology chord diagram
├── ProfilePanel.tsx         # Settings panel
├── types.ts                 # Data & settings types
└── index.ts                 # Plugin registration
```

Registration:
```typescript
const OntologyExplorerPlugin: ExplorerPlugin = {
  config: {
    id: 'ontology',
    type: 'ontology',  // New VisualizationType
    name: 'Ontology Explorer',
    description: 'Browse and manage knowledge domain groupings',
    icon: Library,  // lucide-react
    requiredDataShape: 'tree',  // Closest fit; overview is tree-like
  },
  component: OntologyExplorer,
  settingsPanel: ProfilePanel,
  dataTransformer: transformOntologyData,
  defaultSettings: DEFAULT_SETTINGS,
};
```

### 5. State Management

New Zustand store or extension to `graphStore`:

```typescript
interface OntologyStore {
  // Data
  ontologies: OntologyNode[];
  bridges: OntologyBridge[];
  activeOntology: string | null;
  activeOntologyDetail: OntologyDetail | null;

  // View state
  currentView: 'overview' | 'detail' | 'bridge';
  selectedOntologyPair: [string, string] | null;

  // Actions
  loadOntologies(): Promise<void>;
  loadOntologyDetail(name: string): Promise<void>;
  loadBridges(ontologyNames?: string[]): Promise<void>;
  setActiveOntology(name: string | null): void;
  setView(view: 'overview' | 'detail' | 'bridge'): void;

  // Management actions
  createOntology(name: string): Promise<void>;
  renameOntology(oldName: string, newName: string): Promise<void>;
  deleteOntology(name: string): Promise<void>;
}
```

### 6. Permissions in the UI

The explorer respects the three-tier permission model:

1. **RBAC (ADR-028)**: `ontologies:read`, `ontologies:create`, `ontologies:delete` actions on the `ontologies` resource type.
2. **Grants (ADR-082)**: Resource-level ownership and grants for specific ontologies (e.g., user owns ontology "my-research" and can manage it even without global curator role).
3. **UI gating**: `authStore.hasPermission('ontologies', 'create')` controls whether the "New Ontology" button appears. `authStore.hasPermission('ontologies', 'delete')` controls whether the delete option is available.

For resource-scoped actions (e.g., rename a specific ontology), the UI can optimistically show the action and handle 403 responses gracefully, or pre-check via `GET /ontology/{name}` which could include an `actions` field listing permitted operations for the current user.

## Consequences

### Positive

- Ontologies become a first-class navigable entity, not just a filter parameter
- Cross-ontology concept bridging becomes visible — users can see how knowledge domains connect
- Management moves from CLI-only to the web UI, lowering the barrier for non-technical users
- The bridge view provides a novel perspective no other explorer offers (inter-domain knowledge flow)
- Fits cleanly into the existing explorer plugin architecture

### Negative

- New API endpoints add surface area (`/concepts`, `/subgraph`, `/bridges`)
- The bridge computation (`/ontology/bridges`) could be expensive for large graphs — may need caching or pre-computation
- Three sub-views (overview/detail/bridge) make this a more complex explorer than existing ones
- The hybrid data shape doesn't map neatly to the existing `DataShape` enum; may need extension

### Neutral

- Requires extending `VisualizationType` with `'ontology'`
- The detail view's internal subgraph reuses existing `SubgraphResponse` format and could delegate rendering to `ForceGraph2D` internals
- Document reassignment (drag between ontologies) is deferred to a future iteration
- `POST /ontology/` already exists (ADR-200) — ontology creation is now explicit via directed growth

## Alternatives Considered

### A. Enhance the Embedding Landscape Explorer

The embedding landscape already shows ontology-colored clusters. We could add ontology interaction overlays there instead of a new explorer.

**Rejected because:** The embedding landscape optimizes for showing vector space geometry, not organizational structure. Adding management actions and bridge analysis would overload its purpose. Ontologies need their own focused experience.

### B. Add an Ontology Sidebar to the Force Graph

A collapsible sidebar in the 2D/3D graph explorers listing ontologies with drill-down.

**Rejected because:** This conflates graph exploration with ontology management. The force graph is concept-centric; ontology management is collection-centric. Different mental models warrant different explorers.

### C. Dashboard-Only Approach (No Explorer)

A standalone admin dashboard page outside the explorer framework showing ontology stats and management.

**Rejected because:** This fragments the experience. Explorers share navigation (clicking a concept in the ontology detail should seamlessly navigate to the graph explorer), shared state (`graphStore`), and consistent UI patterns (PanelStack, context menus). An outside dashboard loses all of this.

### D. Extend the Document Explorer

The document explorer already shows documents. We could add an ontology grouping layer above the document level.

**Rejected because:** The document explorer is designed for single-document concept radiation (radial tidy tree). Adding a parent ontology layer changes its metaphor from "explore one document's impact" to "browse a collection." These are distinct user intents.

## Implementation Notes

### Foundation: ADR-200 (Implemented)

ADR-200 "Annealing Ontologies" provides the data model foundation for this explorer:
- `:Ontology` graph nodes with properties (`ontology_id`, `lifecycle_state`, `creation_epoch`, `embedding`, `search_terms`)
- `:SCOPED_BY` edges linking Sources to Ontologies
- `POST /ontology/` for directed growth (explicit creation before ingest)
- `GET /ontology/{name}/node` for graph node properties
- Enriched list and info responses with graph node data
- CLI `kg ontology create`, MCP `create`/`rename` actions
- Web types updated (`OntologyItem` with graph node fields)

### Phase 1: Overview + Detail (MVP)

- Register `OntologyExplorerPlugin`
- Implement overview (treemap with enriched stats from `GET /ontology/` — includes lifecycle state, embedding status)
- Implement detail view (document list + top concepts from new `GET /ontology/{name}/concepts`)
- Wire up existing management actions (create, rename, delete) with permission gating

### Phase 2: Bridge View

- Implement `GET /ontology/bridges` API endpoint
- Build chord diagram visualization (D3 `d3.chord()`)
- Add shared concept drill-down for selected ontology pairs

### Phase 3: Internal Subgraph

- Implement `GET /ontology/{name}/subgraph` endpoint
- Render internal concept graph (delegate to ForceGraph2D renderer)
- Add navigation links from ontology concepts to the full graph explorer

### Phase 4: Advanced Interaction

- Document reassignment between ontologies (drag-and-drop)
- Ontology merge (combine two ontologies)
- Ontology split (separate a subset of documents into a new ontology)
- Batch operations (multi-select documents for bulk moves)

## Related ADRs

- **ADR-028** — Dynamic RBAC system (permission model for management actions)
- **ADR-068** — Source text embeddings (enables cross-ontology concept merging)
- **ADR-082** — User scoping & groups (resource-level ownership of ontologies)
- **ADR-083** — Artifact persistence (could cache expensive bridge computations)
- **ADR-084** — Document-level search (complementary document discovery)
- **ADR-089** — Deterministic graph editing (ontology-scoped concept creation)
- **ADR-200** — Annealing Ontologies (graph node architecture, directed growth, lifecycle states — data model foundation for this explorer)
