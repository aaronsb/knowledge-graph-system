---
status: Proposed
date: 2025-10-16
deciders: Development Team
related:
  - ADR-016
  - ADR-029
  - ADR-033
---

# ADR-034: Graph Visualization & Interactive Query Explorers

## Overview

Knowledge graphs are inherently visual—concepts connect to other concepts, forming webs of meaning that resist linear navigation. Yet until now, our users have been limited to text-based tools: CLI commands that show lists, MCP integration through Claude's text interface, and REST APIs that return JSON. It's like exploring a city with only a phone book.

The challenge isn't just showing pretty pictures. Existing graph visualization tools like Apache AGE Viewer have been abandoned, and generic tools like Gephi don't integrate with our unique capabilities—grounding strength, semantic diversity, and provenance tracking. We needed something purpose-built.

This ADR establishes a web-based visualization application using React and D3.js, built as a separate service that communicates with our REST API. The architecture uses an explorer plugin pattern: each visualization type (force graphs, hierarchies, timelines) plugs into a common framework. Add a new explorer, it automatically appears in the sidebar. The result is a scalable foundation for visual knowledge exploration that can grow with our needs.

---

## Context

The knowledge graph system stores rich conceptual networks with complex relationships, but currently lacks visual exploration tools. Users interact primarily through:

1. **CLI commands** - Text-based search and queries (kg CLI)
2. **MCP integration** - Claude-mediated graph exploration
3. **REST API** - Programmatic access only

### Evaluation of Existing Solutions

Before building a custom solution, we evaluated existing Apache AGE-compatible visualization tools:

**Apache AGE Viewer** (Official)
- Repository: https://github.com/apache/age-viewer
- Last commit: March 22, 2024 (~2 years ago)
- Status: **Effectively abandoned**
- Issues: 85 open, many unresolved (build failures, connection errors, feature requests ignored)
- Technology: Node 14 (EOL), outdated dependencies
- Visualization: Basic force-directed graph, matrix view, histograms
- Limitations: No 3D graphs, no advanced query workbenches, no real-time updates

**Verdict:** Unmaintained subproject with accumulating technical debt and insufficient features for our requirements.

**Gephi**
- Desktop application (not web-based)
- PostgreSQL connector available
- Powerful offline analysis
- License: GPL + CDDL (complicates integration)
- **Verdict:** Complementary tool for research, not a microservice fit

**Cytoscape.js / D3.js**
- Both require custom integration via REST API
- High development effort but full control
- Modern, actively maintained ecosystems
- **Verdict:** Best foundation for custom solution

**Decision:** Build custom visualization application using React + TypeScript + D3.js ecosystem to meet our specific requirements and avoid dependency on abandoned projects.

### Limitations of Current Approach

**Discovery Challenges:**
- Cannot see cluster formations or conceptual neighborhoods
- Difficult to understand relationship patterns visually
- No way to explore graph topology interactively
- Hidden insights trapped in node-edge structures

**Query Complexity:**
- Writing openCypher queries requires expertise
- Hard to construct path-finding queries without visual feedback
- Cannot iteratively refine queries while seeing results
- No visual query builder

**Analysis Gaps:**
- Cannot identify hub concepts (high-degree nodes) visually
- Relationship type distributions invisible
- Concept drift over time not visualized
- Ontology comparison requires manual effort

### User Needs

**Researchers:**
- Explore conceptual neighborhoods around key ideas
- Discover unexpected connections between domains
- Trace knowledge lineage through source citations
- Compare concept density across ontologies

**Curators:**
- Identify poorly connected concepts (orphans)
- Find duplicate concepts to merge
- Visualize relationship type usage
- Validate graph quality metrics

**Analysts:**
- Extract insights from relationship patterns
- Perform temporal analysis (concept evolution)
- Compare ontologies side-by-side
- Export visualizations for reports

## Decision

Build a **separate web-based visualization application** using **React/TypeScript** and **D3.js** ecosystem, deployed as an independent service on a different port from the API server when in local development mode, and in an actual deployment, we assume a service such as ngix to normalize paths for the platform.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Knowledge Graph System Architecture                         │
│                                                             │
│  ┌────────────────┐      ┌────────────────┐                 │
│  │  FastAPI       │      │  Visualization │                 │
│  │  REST API      │◄────►│  Web App       │                 │
│  │  :8000         │      │  :3000         │                 │
│  └────────────────┘      └────────────────┘                 │
│         │                        │                          │
│         │                        │                          │
│         ▼                        ▼                          │
│  ┌────────────────┐      ┌────────────────┐                 │
│  │  PostgreSQL    │      │  Static Assets │                 │
│  │  Apache AGE    │      │  (CDN)         │                 │
│  └────────────────┘      └────────────────┘                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Tech Stack:
- Frontend: React 18+ with TypeScript
- Visualization: D3.js, Three.js (3D), Force Graph
- State: Zustand or Redux Toolkit
- Routing: React Router v6
- API Client: TanStack Query (React Query)
- Build: Vite
- Styling: Tailwind CSS + Radix UI components
```

### Core Principles

1. **Separation of Concerns**
   - Visualization app is a pure client (no database access)
   - All data flows through REST API
   - Stateless server, stateful client
   - Independent deployment and scaling

2. **Progressive Enhancement**
   - Works without JavaScript (server-rendered fallbacks)
   - Graceful degradation for older browsers
   - Mobile-responsive (touch interactions)
   - Accessibility (ARIA labels, keyboard nav)

3. **Performance First**
   - Virtualization for large graphs (>1000 nodes)
   - WebGL acceleration for 3D rendering
   - Lazy loading and code splitting
   - Aggressive caching with service workers

4. **Composable Explorers**
   - Modular visualization components
   - Pluggable query builders
   - Shareable explorer configurations
   - Export-ready outputs

## Golden Path: Building the First Explorer

This section provides a detailed implementation roadmap for building the foundation and first explorer (Force-Directed Graph Explorer). The architecture is designed for extensibility, making it straightforward to add additional explorers following the same patterns.

### Implementation Strategy

**Phase 1 MVP:** Single Force-Directed Graph Explorer (2D)
- Establishes all core patterns (API integration, state management, visualization abstraction)
- Provides immediate value for graph exploration
- Validates architecture before expanding to other explorer types
- Estimated effort: 2-3 weeks

**Phase 2+:** Additional explorers follow the established plugin pattern

### Project Initialization

```bash
# Create React + TypeScript + Vite project
cd knowledge-graph-system
npm create vite@latest viz-app -- --template react-ts

cd viz-app
npm install

# Core dependencies
npm install \
  d3 \
  @types/d3 \
  @tanstack/react-query \
  zustand \
  react-router-dom \
  axios

# UI dependencies
npm install \
  tailwindcss \
  @radix-ui/react-select \
  @radix-ui/react-dialog \
  @radix-ui/react-tabs \
  lucide-react

# Development dependencies
npm install -D \
  @testing-library/react \
  @testing-library/jest-dom \
  vitest \
  @vitest/ui
```

### Core Architecture Patterns

#### 1. Explorer Plugin Interface

Each explorer implements a standard interface for consistent integration:

```typescript
// src/types/explorer.ts

export type VisualizationType =
  | 'force-2d'
  | 'force-3d'
  | 'hierarchy'
  | 'sankey'
  | 'matrix'
  | 'timeline'
  | 'density';

export interface ExplorerConfig {
  id: string;
  type: VisualizationType;
  name: string;
  description: string;
  icon: React.ComponentType;
  requiredDataShape: 'graph' | 'tree' | 'flow' | 'matrix' | 'temporal';
}

export interface ExplorerProps<TData = any, TSettings = any> {
  data: TData;
  settings: TSettings;
  onNodeClick?: (nodeId: string) => void;
  onSelectionChange?: (selection: string[]) => void;
  className?: string;
}

export interface ExplorerPlugin {
  config: ExplorerConfig;
  component: React.ComponentType<ExplorerProps>;
  settingsPanel: React.ComponentType<SettingsPanelProps>;
  dataTransformer: (apiData: any) => any;
  defaultSettings: Record<string, any>;
}
```

#### 2. Explorer Registry

Centralized registry for all explorer types:

```typescript
// src/explorers/registry.ts

import { ForceGraph2DExplorer } from './ForceGraph2DExplorer';
import { HierarchyExplorer } from './HierarchyExplorer';
// ... other explorers

export const EXPLORER_REGISTRY: Map<VisualizationType, ExplorerPlugin> = new Map([
  ['force-2d', ForceGraph2DExplorer],
  ['hierarchy', HierarchyExplorer],
  // ... register as implemented
]);

export function getExplorer(type: VisualizationType): ExplorerPlugin | undefined {
  return EXPLORER_REGISTRY.get(type);
}

export function getAllExplorers(): ExplorerPlugin[] {
  return Array.from(EXPLORER_REGISTRY.values());
}
```

### Extensibility Pattern: Adding New Explorers

Once the foundation is established, adding a new explorer follows this template:

```typescript
// src/explorers/HierarchyExplorer/index.ts

import { TreePine } from 'lucide-react';
import { HierarchyTree } from './HierarchyTree';
import { HierarchySettingsPanel } from './SettingsPanel';

export const HierarchyExplorer: ExplorerPlugin = {
  config: {
    id: 'hierarchy',
    type: 'hierarchy',
    name: 'Hierarchical Tree',
    description: 'Explore taxonomies and containment relationships',
    icon: TreePine,
    requiredDataShape: 'tree',
  },

  component: HierarchyTree,
  settingsPanel: HierarchySettingsPanel,

  dataTransformer: (apiData) => {
    // Convert graph to tree structure
    return buildTreeFromGraph(apiData);
  },

  defaultSettings: {
    layout: 'tidy', // 'tidy' | 'radial' | 'treemap'
    orientation: 'vertical', // 'vertical' | 'horizontal'
    nodeSize: 10,
    showDepth: 5,
  },
};
```

Register in `src/explorers/registry.ts`:
```typescript
import { HierarchyExplorer } from './HierarchyExplorer';

export const EXPLORER_REGISTRY: Map<VisualizationType, ExplorerPlugin> = new Map([
  ['force-2d', ForceGraph2DExplorer],
  ['hierarchy', HierarchyExplorer], // ← Add here
  // ...
]);
```

**That's it!** The new explorer automatically appears in the sidebar and follows all established patterns.

### Detailed Implementation: Force-Directed Graph Explorer

**See complete implementation examples in ADR Appendix A** (data types, API hooks, force simulation, component code, settings panels, testing strategies).

The Force-Directed Graph Explorer serves as the reference implementation demonstrating:
- D3 force simulation integration with React
- Settings panel architecture
- Export capabilities
- Keyboard navigation and accessibility
- Performance optimizations for large graphs

All subsequent explorers follow these same patterns with visualization-specific customizations.

## Visualization Types

### 1. Force-Directed Graph (2D/3D)

**Use Case:** Explore conceptual neighborhoods and clustering

**Libraries:**
- 2D: D3-force, react-force-graph-2d
- 3D: Three.js via react-force-graph-3d

**Features:**
- Physics simulation (attraction/repulsion)
- Cluster highlighting
- Relationship filtering by type
- Node sizing by degree/betweenness
- Color coding by ontology, terms count, vector similarity, or edge phenotype.
- Zoom/pan/rotate controls

**Interactions:**
- Click node → show details panel
- Hover → highlight neighbors
- Drag → reposition node
- Ctrl+Click → expand neighbors
- Double-click → focus subgraph

```typescript
// Example: Force-directed graph component
interface ForceGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  focusNodeId?: string;
  colorBy: 'ontology' | 'degree' | 'centrality';
  physics: {
    charge: number;
    linkDistance: number;
    gravity: number;
  };
}

const ForceGraph: React.FC<ForceGraphProps> = ({
  nodes, links, focusNodeId, colorBy, physics
}) => {
  // D3 force simulation
  const simulation = useD3ForceSimulation(nodes, links, physics);

  // Highlight neighbors on hover
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const neighbors = useNeighbors(hoveredNode, links);

  return (
    <svg viewBox="0 0 1000 1000">
      <Links links={links} highlighted={neighbors} />
      <Nodes
        nodes={nodes}
        colorBy={colorBy}
        onHover={setHoveredNode}
        focused={focusNodeId}
      />
    </svg>
  );
};
```

### 2. Hierarchical Tree Visualization

**Use Case:** Explore taxonomies and containment relationships

**Libraries:**
- D3-hierarchy (tree, cluster, partition)
- react-d3-tree

**Layouts:**
- Radial tree (circular layout)
- Tidy tree (traditional top-down)
- Treemap (nested rectangles)
- Sunburst (radial partitioning)

**Features:**
- Collapse/expand branches
- Breadcrumb navigation
- Leaf node search
- Depth limiting
- Ancestor highlighting

```typescript
// Example: Hierarchical tree
interface TreeNode {
  id: string;
  label: string;
  children?: TreeNode[];
  depth: number;
}

const HierarchyTree: React.FC<{ root: TreeNode }> = ({ root }) => {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const hierarchy = useMemo(() =>
    d3.hierarchy(root)
      .sort((a, b) => a.data.label.localeCompare(b.data.label))
  , [root]);

  const treeLayout = d3.tree<TreeNode>()
    .size([1000, 800])
    .separation((a, b) => a.parent === b.parent ? 1 : 2);

  return (
    <svg>
      <TreeLinks tree={treeLayout(hierarchy)} />
      <TreeNodes
        tree={treeLayout(hierarchy)}
        collapsed={collapsed}
        onToggle={(id) => toggleCollapse(id, collapsed, setCollapsed)}
      />
    </svg>
  );
};
```

### 3. Sankey Diagram

**Use Case:** Visualize knowledge flow between ontologies

**Libraries:**
- D3-sankey
- react-vis

**Features:**
- Concept migration paths
- Ontology merging preview
- Source attribution flow
- Relationship type distribution

**Example Use:**
- Show which concepts from "Research Papers" ontology → "Product Documentation"
- Trace evidence flow from source documents → concept instances

### 4. Matrix/Heatmap View

**Use Case:** Compare relationship patterns across concepts

**Libraries:**
- D3-scale, D3-axis
- visx (reusable chart components)

**Features:**
- Adjacency matrix (concept × concept)
- Relationship type heatmap
- Temporal evolution grid
- Correlation analysis

**Example:**
```
       Concept A  Concept B  Concept C
Concept A    -      IMPLIES    SUPPORTS
Concept B  IMPLIES    -        CONTRADICTS
Concept C  SUPPORTS CONTRADICTS  -
```

### 5. Timeline Visualization

**Use Case:** Explore concept evolution over time

**Libraries:**
- D3-time-scale
- vis-timeline

**Features:**
- Concept creation timeline
- Relationship formation events
- Ingestion batch markers
- Ontology version history

### 6. Concept Density Map

**Use Case:** Identify knowledge-rich areas

**Libraries:**
- D3-contour (for density)
- Deck.gl (hexagonal binning)

**Features:**
- Heatmap of concept clusters
- Ontology coverage overlay
- Sparse area highlighting
- Interactive drill-down

## Terminology Note

**Explorer vs. Explorer:** We use "Explorer" to describe each interactive visualization mode. This term emphasizes the investigative, discovery-oriented nature of the tools and aligns with common graph database UI conventions (e.g., Neo4j Browser, graph explorers). Each explorer combines a specific visualization type with appropriate interaction patterns.

See [ADR-035: Explorer Methods, Uses, and Capabilities](./ADR-035-explorer-methods-uses-capabilities.md) for details on explorers modules.

## Technical Implementation

### Frontend Architecture

```
viz-app/
├── src/
│   ├── components/
│   │   ├── visualizations/
│   │   │   ├── ForceGraph2D.tsx
│   │   │   ├── ForceGraph3D.tsx
│   │   │   ├── HierarchyTree.tsx
│   │   │   ├── SankeyFlow.tsx
│   │   │   ├── MatrixView.tsx
│   │   │   └── Timeline.tsx
│   │   ├── workbenches/
│   │   │   ├── VisualQueryBuilder.tsx
│   │   │   ├── PathExplorer.tsx
│   │   │   ├── NeighborhoodInspector.tsx
│   │   │   ├── OntologyComparator.tsx
│   │   │   └── TemporalViewer.tsx
│   │   └── shared/
│   │       ├── NodeDetails.tsx
│   │       ├── RelationshipFilter.tsx
│   │       └── ExportDialog.tsx
│   ├── hooks/
│   │   ├── useGraphData.ts
│   │   ├── useForceSimulation.ts
│   │   └── useQueryBuilder.ts
│   ├── api/
│   │   ├── client.ts          # REST API client
│   │   ├── graphQueries.ts    # Graph query helpers
│   │   └── websocket.ts       # Real-time updates
│   ├── store/
│   │   ├── graphStore.ts      # Zustand store for graph state
│   │   └── workbenchStore.ts  # Active workbench state
│   └── utils/
│       ├── graphTransform.ts  # API data → D3 format
│       ├── colorScale.ts      # Consistent color schemes
│       └── export.ts          # SVG/PNG/JSON export
├── public/
└── package.json
```

### REST API Endpoints (New)

```python
# src/api/routes/visualization.py

@router.get("/viz/graph/subgraph")
async def get_subgraph(
    center_concept_id: str,
    depth: int = 2,
    relationship_types: Optional[List[str]] = None,
    limit: int = 500
) -> SubgraphResponse:
    """
    Get subgraph centered on a concept.

    Returns nodes and edges within N hops, formatted for D3.

    Response:
    {
      "nodes": [
        {"id": "concept_123", "label": "AI Safety", "ontology": "Research", ...}
      ],
      "links": [
        {"source": "concept_123", "target": "concept_456", "type": "IMPLIES", ...}
      ],
      "stats": {"node_count": 50, "edge_count": 120}
    }
    """
    pass

@router.get("/viz/graph/path")
async def find_path(
    from_id: str,
    to_id: str,
    max_hops: int = 5,
    algorithm: Literal["shortest", "all_simple", "weighted"] = "shortest"
) -> PathResponse:
    """Find paths between two concepts"""
    pass

@router.get("/viz/ontology/compare")
async def compare_ontologies(
    ontology_a: str,
    ontology_b: str
) -> ComparisonResponse:
    """Compare two ontologies (Venn diagram data)"""
    pass

@router.get("/viz/graph/timeline")
async def get_timeline(
    ontology: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    granularity: Literal["day", "week", "month"] = "week"
) -> TimelineResponse:
    """Get graph evolution over time"""
    pass

@router.get("/viz/graph/matrix")
async def get_adjacency_matrix(
    concept_ids: List[str]
) -> MatrixResponse:
    """Get adjacency matrix for selected concepts"""
    pass
```

### WebSocket for Real-Time Updates

```python
# src/api/websocket/graph_events.py

@router.websocket("/ws/graph")
async def graph_events_socket(websocket: WebSocket):
    """
    Real-time graph updates.

    Events:
    - concept_created: {"type": "concept_created", "data": {...}}
    - concept_updated: {"type": "concept_updated", "data": {...}}
    - relationship_created: {"type": "relationship_created", "data": {...}}
    - ingestion_complete: {"type": "ingestion_complete", "ontology": "..."}

    Client can subscribe to specific ontologies:
    > {"action": "subscribe", "ontology": "Research Papers"}
    < {"type": "concept_created", "ontology": "Research Papers", ...}
    """
    await websocket.accept()

    try:
        while True:
            # Listen for subscription changes
            message = await websocket.receive_json()

            # Broadcast relevant events
            if message["action"] == "subscribe":
                # Add to subscriber list
                pass
    except WebSocketDisconnect:
        # Clean up
        pass
```

### Data Transform Layer

```typescript
// src/utils/graphTransform.ts

interface APIGraphNode {
  concept_id: string;
  label: string;
  ontology: string;
  search_terms: string[];
  created_at: string;
}

interface APIGraphLink {
  from_id: string;
  to_id: string;
  relationship_type: string;
  confidence: number;
  category: string;
}

interface D3Node {
  id: string;
  label: string;
  group: string;  // ontology
  size: number;   // degree
  color: string;
  fx?: number;    // fixed position X
  fy?: number;    // fixed position Y
}

interface D3Link {
  source: string;
  target: string;
  type: string;
  value: number;  // confidence
  color: string;
}

export function transformForD3(
  apiNodes: APIGraphNode[],
  apiLinks: APIGraphLink[]
): { nodes: D3Node[]; links: D3Link[] } {
  const colorScale = d3.scaleOrdinal(d3.schemeCategory10);

  const nodes = apiNodes.map(node => ({
    id: node.concept_id,
    label: node.label,
    group: node.ontology,
    size: 10, // Will be updated with degree
    color: colorScale(node.ontology)
  }));

  const links = apiLinks.map(link => ({
    source: link.from_id,
    target: link.to_id,
    type: link.relationship_type,
    value: link.confidence,
    color: getLinkColor(link.category)
  }));

  // Calculate degrees
  const degrees = new Map<string, number>();
  links.forEach(link => {
    degrees.set(link.source, (degrees.get(link.source) || 0) + 1);
    degrees.set(link.target, (degrees.get(link.target) || 0) + 1);
  });

  nodes.forEach(node => {
    node.size = Math.sqrt((degrees.get(node.id) || 1) * 10);
  });

  return { nodes, links };
}
```

## Deployment Architecture

### Option 1: Standalone App (Recommended)

```yaml
# docker-compose.yml

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CORS_ORIGINS=http://localhost:3000,https://viz.example.com

  viz-app:
    build: ./viz-app
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://localhost:8000
      - VITE_WS_URL=ws://localhost:8000/ws
    depends_on:
      - api
```

**Benefits:**
- Independent scaling (viz can scale separately)
- CDN-friendly (static assets)
- Easy A/B testing (deploy multiple versions)

### Option 2: Embedded (Alternative)

```python
# Serve viz app from FastAPI (not recommended for production)

from fastapi.staticfiles import StaticFiles

app.mount("/viz", StaticFiles(directory="viz-app/dist", html=True), name="viz")

# Visit: http://localhost:8000/viz
```

**Use Case:** Development only, single deployment

## Export Capabilities

### 1. Static Image Export

```typescript
// Export SVG to PNG
async function exportToPNG(svgElement: SVGElement): Promise<Blob> {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;

  const svgData = new XMLSerializer().serializeToString(svgElement);
  const img = new Image();

  img.src = 'data:image/svg+xml;base64,' + btoa(svgData);

  await new Promise(resolve => img.onload = resolve);

  canvas.width = img.width;
  canvas.height = img.height;
  ctx.drawImage(img, 0, 0);

  return new Promise(resolve => canvas.toBlob(resolve as BlobCallback, 'image/png'));
}
```

### 2. Interactive Export

```typescript
// Export as standalone HTML with embedded data
function exportAsHTML(graphData: GraphData, title: string): string {
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <title>${title}</title>
      <script src="https://d3js.org/d3.v7.min.js"></script>
      <style>/* ... embedded styles ... */</style>
    </head>
    <body>
      <div id="graph"></div>
      <script>
        const data = ${JSON.stringify(graphData)};
        // ... render graph ...
      </script>
    </body>
    </html>
  `;
}
```

### 3. Data Export

- **JSON**: Full graph structure
- **CSV**: Node/edge lists for analysis
- **GraphML**: Import to Gephi, Cytoscape
- **Cypher**: openCypher query to recreate subgraph

## Accessibility

### Keyboard Navigation

```typescript
// Keyboard controls for graph navigation
const KeyboardControls: React.FC = () => {
  useKeyPress('ArrowUp', () => pan(0, -50));
  useKeyPress('ArrowDown', () => pan(0, 50));
  useKeyPress('ArrowLeft', () => pan(-50, 0));
  useKeyPress('ArrowRight', () => pan(50, 0));
  useKeyPress('+', () => zoom(1.2));
  useKeyPress('-', () => zoom(0.8));
  useKeyPress('Escape', () => clearSelection());
  useKeyPress('/', () => focusSearch());

  return null;
};
```

### ARIA Labels

```tsx
<svg role="img" aria-label="Knowledge graph visualization">
  <g aria-label={`${nodes.length} concepts and ${links.length} relationships`}>
    {nodes.map(node => (
      <circle
        key={node.id}
        role="button"
        aria-label={`Concept: ${node.label}, Ontology: ${node.group}`}
        tabIndex={0}
        onKeyPress={(e) => e.key === 'Enter' && selectNode(node)}
      />
    ))}
  </g>
</svg>
```

### Screen Reader Support

```typescript
// Provide text-based graph description
function generateGraphDescription(graph: GraphData): string {
  const hubNodes = findHubNodes(graph, 3);
  const clusters = detectClusters(graph);

  return `
    This graph contains ${graph.nodes.length} concepts connected by
    ${graph.links.length} relationships.

    Main hubs: ${hubNodes.map(n => n.label).join(', ')}.

    ${clusters.length} distinct clusters identified:
    ${clusters.map((c, i) => `Cluster ${i+1}: ${c.nodes.length} concepts`).join(', ')}.
  `;
}

<div role="region" aria-label="Graph description" className="sr-only">
  {generateGraphDescription(graphData)}
</div>
```

## Performance Considerations

### Large Graph Handling

**Problem:** Rendering 10,000+ nodes crashes browser

**Solutions:**

1. **Level-of-Detail (LOD)**
   ```typescript
   // Render simplified nodes when zoomed out
   const nodeDetail = zoom > 2 ? 'high' : zoom > 1 ? 'medium' : 'low';

   if (nodeDetail === 'low') {
     // Render as points
     return <circle r={2} />;
   } else if (nodeDetail === 'medium') {
     // Render with label
     return <circle r={5}><title>{node.label}</title></circle>;
   } else {
     // Full detail
     return <NodeWithLabelsAndIcons />;
   }
   ```

2. **Viewport Culling**
   ```typescript
   // Only render nodes in viewport
   const visibleNodes = nodes.filter(node =>
     isInViewport(node.x, node.y, viewport)
   );
   ```

3. **Aggregation**
   ```typescript
   // Cluster distant nodes
   const clustered = aggregateDistantNodes(nodes, viewport.zoom);
   ```

4. **WebGL Rendering**
   ```typescript
   // Use Deck.gl for GPU-accelerated rendering
   import { ScatterplotLayer } from '@deck.gl/layers';

   <DeckGL
     layers={[
       new ScatterplotLayer({
         data: nodes,
         getPosition: d => [d.x, d.y],
         getRadius: d => d.size,
         getFillColor: d => hexToRgb(d.color)
       })
     ]}
   />
   ```

### Caching Strategy

```typescript
// Cache subgraph queries
const useGraphData = (centerId: string, depth: number) => {
  return useQuery({
    queryKey: ['subgraph', centerId, depth],
    queryFn: () => fetchSubgraph(centerId, depth),
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 30 * 60 * 1000, // 30 minutes
  });
};
```

## Security Considerations

### CORS Configuration

```python
# src/api/main.py

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development
        "https://viz.example.com"  # Production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Query Limits

```python
# Prevent DoS via expensive queries
@router.get("/viz/graph/subgraph")
async def get_subgraph(
    depth: int = Query(2, ge=1, le=5),  # Max 5 hops
    limit: int = Query(500, ge=1, le=5000)  # Max 5k nodes
):
    # Timeout after 30 seconds
    with timeout(30):
        return fetch_subgraph(...)
```

### Data Sanitization

```typescript
// Escape user input in labels
function sanitizeLabel(label: string): string {
  return label
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

## Testing Strategy

### Unit Tests

```typescript
// Test graph transformations
describe('graphTransform', () => {
  it('transforms API nodes to D3 format', () => {
    const apiNodes = [
      { concept_id: '1', label: 'AI', ontology: 'Tech', ... }
    ];

    const { nodes } = transformForD3(apiNodes, []);

    expect(nodes[0]).toEqual({
      id: '1',
      label: 'AI',
      group: 'Tech',
      size: expect.any(Number),
      color: expect.any(String)
    });
  });
});
```

### Integration Tests

```typescript
// Test workbench interactions
describe('PathExplorer', () => {
  it('finds paths between concepts', async () => {
    render(<PathExplorer />);

    await userEvent.selectOptions(screen.getByLabelText('From'), 'AI Safety');
    await userEvent.selectOptions(screen.getByLabelText('To'), 'Policy');
    await userEvent.click(screen.getByText('Find Paths'));

    expect(await screen.findByText(/3 paths found/)).toBeInTheDocument();
  });
});
```

### Visual Regression Tests

```typescript
// Storybook + Chromatic for visual testing
export const ForceGraphDefault = () => (
  <ForceGraph
    nodes={mockNodes}
    links={mockLinks}
    colorBy="ontology"
  />
);
```

## Migration Path

### Phase 1: MVP
- ✅ React + Vite setup
- ✅ Basic force-directed graph (2D)
- ✅ Node details panel
- ✅ Simple search
- ✅ REST API integration

### Phase 2: Core Exploreres
- ✅ Visual query builder
- ✅ Path explorer
- ✅ Neighborhood inspector
- ✅ Export to PNG/SVG

### Phase 3: Advanced Viz
- ✅ 3D force graph
- ✅ Hierarchical tree
- ✅ Timeline view
- ✅ Matrix view

### Phase 4: Real-Time & Collaboration
- ✅ WebSocket integration
- ✅ Live graph updates
- ✅ Shareable workbench URLs
- ✅ Collaborative annotations

## Future Enhancements

1. **Graph Analytics**
   - PageRank visualization (node importance)
   - Community detection (cluster coloring)
   - Centrality metrics overlay
   - Path criticality analysis

2. **AI-Assisted Exploration**
   - Natural language queries ("Show me concepts related to AI ethics")
   - Suggested paths (ML-powered recommendations)
   - Anomaly detection (unusual relationship patterns)

3. **Collaboration Features**
   - Shared workbench sessions
   - Commenting on nodes/edges
   - Annotation layers
   - Version control for graph snapshots

4. **Mobile App**
   - React Native version
   - Touch gestures for graph manipulation
   - Offline mode with sync

5. **VR/AR Exploration**
   - WebXR for immersive 3D graphs
   - Spatial navigation
   - Hand gesture controls

## References

- [D3.js Documentation](https://d3js.org/)
- [Three.js Documentation](https://threejs.org/)
- [Force Graph Libraries](https://github.com/vasturiano/react-force-graph)
- [React Flow (Alternative)](https://reactflow.dev/)
- [Cytoscape.js (Alternative)](https://js.cytoscape.org/)
- [Vis.js (Alternative)](https://visjs.org/)
- [Gephi Graph Viz](https://gephi.org/)
- [Observable Notebooks (D3 Examples)](https://observablehq.com/@d3)

## Approval & Sign-Off

- [ ] Development Team Review
- [ ] UX/UI Design Review
- [ ] Performance Testing (1000+ node graphs)
- [ ] Accessibility Audit (WCAG 2.1 AA)
- [ ] Security Review (CORS, query limits)
- [ ] Documentation Complete
- [ ] Deployment Guide Ready
