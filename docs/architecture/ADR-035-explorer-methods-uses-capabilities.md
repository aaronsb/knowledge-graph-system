# ADR-035: Explorer Methods, Uses, and Capabilities

**Status:** Proposed
**Date:** 2025-10-17
**Last Updated:** 2025-10-17
**Deciders:** Development Team
**Related:** ADR-034 (Graph Visualization Architecture)

## Context

ADR-034 establishes the core architecture for the graph visualization application. This ADR documents the specific explorer types, their use cases, interaction patterns, and planned enhancements for navigating and understanding the knowledge graph.

Explorers are specialized visualization modes optimized for different analysis tasks. Each explorer type serves distinct user needs - from discovering conceptual neighborhoods to comparing ontologies or analyzing temporal evolution.

## Explorer Types

### 1. Force-Directed Graph (2D/3D)

**Use Case:** Explore conceptual neighborhoods and discover clustering patterns

**Best For:**
- Discovering unexpected connections between concepts
- Understanding relationship density in graph regions
- Identifying hub concepts (high-degree nodes)
- Exploring concept neighborhoods interactively

**Libraries:**
- 2D: D3-force, react-force-graph-2d
- 3D: Three.js via react-force-graph-3d

**Features:**
- Physics simulation (attraction/repulsion forces)
- Cluster highlighting
- Relationship filtering by type
- Node sizing by degree/betweenness centrality
- Color coding by ontology, terms count, vector similarity, or edge phenotype
- Zoom/pan/rotate controls (3D)
- Dynamic force parameters (charge, link distance, gravity)

**Current Interactions:**
- **Click node** → Focus subgraph on that concept (re-centers exploration)
- **Hover node** → Highlight neighbors and connecting edges
- **Drag node** → Reposition and pin to location
- **Scroll/pinch** → Zoom in/out
- **Click+drag background** → Pan viewport

**Planned Interactions (ADR-035 Enhancements):**
- **Double-click node** → Expand neighbors into existing graph (additive)
- **Right-click node** → Context menu (expand, find path to, view details, copy ID)
- **Ctrl+Click node** → Add to selection set
- **Shift+Click two nodes** → Find shortest path between them
- **Keyboard arrows** → Pan viewport
- **+/- keys** → Zoom
- **Escape** → Clear selection

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

**Best For:**
- Understanding IS-A and PART-OF hierarchies
- Exploring classification systems
- Analyzing ontology structure
- Navigating nested concepts

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
- Subtree statistics

**Interactions:**
- Click node → Expand/collapse children
- Double-click → Focus on subtree
- Breadcrumb click → Navigate to ancestor

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

**Best For:**
- Understanding how concepts flow between ontologies
- Planning ontology merges
- Tracing evidence from sources to concepts
- Analyzing relationship type distribution

**Libraries:**
- D3-sankey
- react-vis

**Features:**
- Concept migration paths
- Ontology merging preview
- Source attribution flow
- Relationship type distribution
- Flow volume indicators

**Example Use:**
- Show which concepts from "Research Papers" ontology → "Product Documentation"
- Trace evidence flow from source documents → concept instances
- Visualize how IMPLIES relationships connect concept groups

### 4. Matrix/Heatmap View

**Use Case:** Compare relationship patterns across concepts

**Best For:**
- Identifying relationship patterns
- Finding missing connections
- Analyzing relationship symmetry
- Comparing concept pairs

**Libraries:**
- D3-scale, D3-axis
- visx (reusable chart components)

**Features:**
- Adjacency matrix (concept → concept)
- Relationship type heatmap
- Temporal evolution grid
- Correlation analysis
- Sortable rows/columns

**Example:**

|           | Concept A | Concept B   | Concept C   |
| --------- | --------- | ----------- | ----------- |
| Concept A | -         | IMPLIES     | SUPPORTS    |
| Concept B | IMPLIES   | -           | CONTRADICTS |
| Concept C | SUPPORTS  | CONTRADICTS | -           |


### 5. Timeline Visualization

**Use Case:** Explore concept evolution over time

**Best For:**
- Understanding graph growth patterns
- Analyzing ingestion history
- Identifying concept emergence
- Tracking relationship formation

**Libraries:**
- D3-time-scale
- vis-timeline

**Features:**
- Concept creation timeline
- Relationship formation events
- Ingestion batch markers
- Ontology version history
- Growth rate metrics
- Temporal filtering

**Interactions:**
- Scrub timeline → View graph at specific date
- Click event → Show details
- Zoom timeline → Adjust granularity
- Play button → Animate growth

### 6. Concept Density Map

**Use Case:** Identify knowledge-rich areas and gaps

**Best For:**
- Finding under-documented regions
- Identifying concept clusters
- Planning curation efforts
- Visualizing coverage

**Libraries:**
- D3-contour (for density)
- Deck.gl (hexagonal binning)

**Features:**
- Heatmap of concept clusters
- Ontology coverage overlay
- Sparse area highlighting
- Interactive drill-down
- Density metrics

## Query Workbenches

### Workbench 1: Visual Query Builder

**Concept:** No-code graph pattern construction

**Use Case:** Build complex graph queries without writing openCypher

```
┌─────────────────────────────────────────┐
│  Visual Query Builder                   │
│                                         │
│      IMPLIES                            │
│   ┌──────┐        ┌──────┐              │
│   │Node1 │───────>│Node2 │              │
│   └───┬──┘        └──────┘              │
│       │                                 │
│       │ PART_OF                         │
│       │                                 │
│       ▼                                 │
│   ┌──────┐                              │
│   │Node3 │                              │
│   └──────┘                              │
│                                         │
│  [Add Node] [Add Edge] [Run Query]      │
│                                         │
│  Generated openCypher:                  │
│  MATCH (n1:Concept)-[:IMPLIES]->        │
│        (n2:Concept)                     │
│  WHERE (n1)-[:PART_OF]->(:Concept)      │
│  RETURN n1, n2                          │
└─────────────────────────────────────────┘
```

**Features:**
- Drag-and-drop nodes and edges
- Filter palette (relationship types)
- Property constraints (label, ontology)
- Path length controls
- Live query preview
- Save/load query templates
- Export as openCypher

### Workbench 2: Path Explorer

**Concept:** Find and visualize paths between concepts

```
┌─────────────────────────────────────────┐
│  Path Explorer                          │
│                                         │
│  From: [AI Safety       ▼]              │
│  To:   [Regulatory Framework ▼]         │
│                                         │
│  Max Hops: [5]  Algorithm: [Shortest ▼] │
│                                         │
│  [Find Paths]                           │
│                                         │
│  Results: 3 paths found                 │
│                                         │
│                                         │
│   Path 1 (3 hops): 89% confidence       │
│   AI Safety → Ethics → Policy →         │
│   Regulatory Framework                  │
│                                         │
└─────────────────────────────────────────┘
```

**Features:**
- Concept auto-complete
- Multiple path algorithms (shortest, all simple, weighted)
- Confidence scoring
- Path comparison side-by-side
- Export to citation format
- Highlight paths in main graph

### Workbench 3: Neighborhood Inspector

**Concept:** Deep-dive into concept surroundings

```
┌─────────────────────────────────────────┐
│  Neighborhood Inspector                 │
│                                         │
│  Focus: [Machine Learning]              │
│                                         │
│  Depth: [2]  Relationship: [All ▼]      │
│                                         │
│                                         │
│       [Neural Networks]                 │
│              │ PART_OF                  │
│              ▼                          │
│       [Machine Learning] ◄────┐         │
│              │                │         │
│       ┌──────┴──────┐         │         │
│       │             │         │         │
│    REQUIRES      ENABLES   IMPLIES      │
│       │             │         │         │
│       ▼             ▼         │         │
│    [Data]    [Automation]  ───┘         │
│                                         │
│                                         │
│  Stats:                                 │
│  • 12 neighbors at depth 1              │
│  • 47 neighbors at depth 2              │
│  • Avg relationship strength: 0.82      │
└─────────────────────────────────────────┘
```

**Features:**
- Expandable radius (1-5 hops)
- Relationship type filtering
- Degree distribution chart
- Orphan concept highlighting
- Export subgraph
- Statistics overlay

### Workbench 4: Ontology Comparator

**Concept:** Side-by-side ontology analysis

```
┌────────────────────────────────────────────────────────┐
│  Ontology Comparator                                   │
│                                                        │
│  Left: [Research Papers ▼]  Right: [Blog Posts ▼]      │
│                                                        │
│                                                        │
│    Unique: 45              Unique: 32                  │
│    Shared: 23    ◄═══►    Shared: 23                   │
│    Total: 68               Total: 55                   │
│                                                        │
│                                                        │
│  Shared Concepts:                                      │
│  • Neural Networks (95% similar)                       │
│  • Deep Learning (88% similar)                         │
│  • Transfer Learning (76% similar)                     │
│                                                        │
│  [Merge Preview] [Export Diff]                         │
└────────────────────────────────────────────────────────┘
```

**Features:**
- Venn diagram visualization
- Concept similarity scoring
- Merge impact preview
- Relationship overlap analysis
- Diff export

### Workbench 5: Temporal Evolution Viewer

**Concept:** Watch graph grow over time

```
┌─────────────────────────────────────────┐
│  Temporal Evolution Viewer              │
│                                         │
│  Timeline: [◄] ████▓████████████        │
│            Jan    Mar     Jun           │
│                                         │
│                                         │
│         [Graph at Mar 15]               │
│                                         │
│    ▸ New concepts: +12                  │
│    ▸ New relationships: +34             │
│    ▸ Merged concepts: 3                 │
│                                         │
│                                         │
│  Growth Rate: +4.2 concepts/week        │
│  [Play Animation] [Export GIF]          │
└─────────────────────────────────────────┘
```

**Features:**
- Playback controls (play/pause/step)
- Growth metrics overlay
- Highlight new/modified nodes
- Export as animated GIF/video

## Navigation Enhancements

### 1. "You Are Here" Persistent Highlighter

**Problem:** When clicking a node to explore its neighborhood, the new graph loads and you lose track of which node you clicked on.

**Solution:** Maintain visual continuity across graph transitions with a persistent "origin node" indicator.

**Implementation:**
```typescript
interface GraphState {
  focusedNodeId: string | null;  // The concept we're centered on
  originNodeId: string | null;    // The node that was clicked to get here
  previousFocusId: string | null; // For back button
}

// Visual indicators:
// - Origin node: Pulsing ring effect, distinct color (e.g., gold)
// - Focused node: Larger size, brighter color
// - Previous focus: Dashed outline (if still in graph)
```

**Color Scheme:**
- **Origin node** (what you clicked): Gold/yellow pulsing ring
- **Current focus** (center of graph): Bright blue, larger size
- **Regular nodes**: Colored by ontology
- **Hovered node**: White outline
- **Selected nodes**: Solid ring

### 2. Navigation History (Breadcrumb Trail)

**Concept:** Track exploration path with visual breadcrumb trail

**UI Location:** Top of graph viewport, below search bar

**Features:**
- Click any breadcrumb → Jump back to that concept
- Shows concept labels (truncated if needed)
- Maximum 5 visible crumbs (with "..." for older)
- Clear history button

```typescript
interface NavigationHistory {
  trail: Array<{
    conceptId: string;
    label: string;
    timestamp: Date;
  }>;
  currentIndex: number;
}

// Example breadcrumb UI:
// Home > AI Safety > Regulatory Framework > [Current Concept]
```

### 3. Back/Forward Navigation Buttons

**Concept:** Browser-style navigation for graph exploration

**UI Location:** Toolbar, next to search bar

**Features:**
- Back button: Return to previous concept
- Forward button: Re-visit next concept (after going back)
- Keyboard shortcuts: Alt+Left (back), Alt+Right (forward)
- Disabled when no history available

```typescript
const useNavigationHistory = () => {
  const [history, setHistory] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);

  const goBack = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      return history[currentIndex - 1];
    }
  };

  const goForward = () => {
    if (currentIndex < history.length - 1) {
      setCurrentIndex(currentIndex + 1);
      return history[currentIndex + 1];
    }
  };

  const navigateTo = (conceptId: string) => {
    // Truncate forward history and add new entry
    const newHistory = history.slice(0, currentIndex + 1);
    newHistory.push(conceptId);
    setHistory(newHistory);
    setCurrentIndex(newHistory.length - 1);
  };

  return { goBack, goForward, navigateTo, canGoBack: currentIndex > 0, canGoForward: currentIndex < history.length - 1 };
};
```

### 4. Expand on Double-Click

**Concept:** Add neighbors to existing graph instead of replacing

**Behavior:**
- Single click: Replace graph with new subgraph (current behavior)
- Double click: Add clicked node's neighbors to existing graph
- Shift+Double click: Add 2-hop neighbors

**Use Case:** Build up complex subgraphs incrementally without losing context

```typescript
const handleNodeDoubleClick = async (nodeId: string) => {
  const neighbors = await fetchNeighbors(nodeId, { depth: 1 });

  // Merge new nodes/edges with existing graph
  setGraphData(prev => ({
    nodes: mergeNodes(prev.nodes, neighbors.nodes),
    links: mergeLinks(prev.links, neighbors.links),
  }));
};
```

### 5. Right-Click Context Menu

**Concept:** Context-sensitive actions on nodes and edges

**Node Context Menu:**
- **Focus Here** - Re-center graph on this concept
- **Expand Neighbors** - Add this node's neighbors to graph
- **Find Path To...** - Opens path finder dialog
- **View Details** - Opens side panel with concept details
- **Copy Concept ID** - Copy to clipboard
- **Export Subgraph** - Export neighborhood as JSON/GraphML
- **Remove from Graph** - Hide this node (temporarily)

**Edge Context Menu:**
- **View Relationship Details** - Show confidence, source documents
- **Find Similar Relationships** - Query for same relationship type
- **Remove Edge Type** - Hide all edges of this type

```typescript
interface ContextMenuProps {
  x: number;
  y: number;
  target: Node | Edge;
  onClose: () => void;
}

const NodeContextMenu: React.FC<ContextMenuProps> = ({ x, y, target, onClose }) => {
  return (
    <div className="context-menu" style={{ left: x, top: y }}>
      <MenuItem onClick={() => focusNode(target.id)}>Focus Here</MenuItem>
      <MenuItem onClick={() => expandNeighbors(target.id)}>Expand Neighbors</MenuItem>
      <MenuItem onClick={() => openPathFinder(target.id)}>Find Path To...</MenuItem>
      <Separator />
      <MenuItem onClick={() => viewDetails(target.id)}>View Details</MenuItem>
      <MenuItem onClick={() => copyToClipboard(target.id)}>Copy ID</MenuItem>
      <Separator />
      <MenuItem onClick={() => removeNode(target.id)}>Remove from Graph</MenuItem>
    </div>
  );
};
```

### 6. Multi-Select and Bulk Actions

**Concept:** Select multiple nodes for batch operations

**Interactions:**
- Ctrl+Click → Add node to selection
- Shift+Click → Range select (all nodes between)
- Click+Drag → Lasso select
- Escape → Clear selection

**Bulk Actions:**
- Export selected nodes
- Find paths between selected nodes
- Create custom subgraph from selection
- Highlight selected neighborhood
- Remove selected from view

### 7. Zoom-to-Fit and Focus Animations

**Features:**
- **Zoom to Fit** button: Auto-zoom to show all nodes
- **Focus Animation**: Smooth camera transition when clicking nodes
- **Highlight Flash**: Brief pulse when focusing new node

```typescript
const animateFocus = (nodeId: string) => {
  const node = findNode(nodeId);

  // Calculate zoom level to show node + 1-hop neighbors
  const neighborsBox = calculateBoundingBox([node, ...getNeighbors(nodeId)]);

  // Animate camera to focus on bounding box
  d3.transition()
    .duration(750)
    .ease(d3.easeCubicOut)
    .call(zoom.transform,
      d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(calculateZoom(neighborsBox))
        .translate(-neighborsBox.centerX, -neighborsBox.centerY)
    );

  // Flash highlight on focused node
  d3.select(`#node-${nodeId}`)
    .transition()
    .duration(150)
    .attr('r', node.size * 2)
    .transition()
    .duration(150)
    .attr('r', node.size);
};
```

## Implementation Patterns

### Imperative DOM Manipulation for Dynamic Highlighting

**Problem:** React's declarative useEffect pattern can create timing issues when highlighting nodes in D3-rendered SVG graphs. Specifically:
- Effects only run when dependencies change (clicking same node twice doesn't re-trigger)
- Effects may run before D3 has positioned elements in the DOM
- Graph data reloads clear the DOM, requiring re-application of highlights

**Solution:** Hybrid imperative/declarative approach combining React hooks with direct DOM manipulation.

**Pattern:**

```typescript
// 1. Create imperative function with useCallback to apply styles directly to DOM
const applyHighlight = useCallback((nodeId: string, style: HighlightStyle) => {
  if (!svgRef.current || !settings.highlightEnabled) return;

  const svg = d3.select(svgRef.current);

  // Remove previous highlights
  svg.selectAll('circle.highlighted')
    .interrupt()
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)
    .classed('highlighted', false);

  // Apply to target node using data-node-id attribute
  const targetCircle = svg.select<SVGCircleElement>(`circle[data-node-id="${nodeId}"]`);

  if (!targetCircle.empty()) {
    targetCircle
      .attr('stroke', style.color)
      .attr('stroke-width', style.width)
      .classed('highlighted', true);

    // Optional: Add animation
    if (style.animated) {
      const pulse = () => {
        targetCircle
          .transition()
          .duration(1000)
          .attr('stroke-width', style.width * 1.5)
          .attr('stroke-opacity', 0.6)
          .transition()
          .duration(1000)
          .attr('stroke-width', style.width)
          .attr('stroke-opacity', 1)
          .on('end', pulse);
      };
      pulse();
    }
  }
}, [settings.highlightEnabled]);

// 2. Call imperatively for immediate feedback (e.g., on click)
const handleNodeClick = (nodeId: string) => {
  setSelectedNodeId(nodeId);
  applyHighlight(nodeId, HIGHLIGHT_STYLES.origin); // Immediate visual update
};

// 3. Call declaratively from effect for persistence after data changes
useEffect(() => {
  if (!selectedNodeId) return;

  // Wait for DOM to be fully rendered after data reload
  const rafId = requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      applyHighlight(selectedNodeId, HIGHLIGHT_STYLES.origin);
    });
  });

  return () => {
    cancelAnimationFrame(rafId);
    // Cleanup highlights on unmount
    if (svgRef.current) {
      d3.select(svgRef.current)
        .selectAll('circle.highlighted')
        .interrupt()
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .classed('highlighted', false);
    }
  };
}, [selectedNodeId, data, applyHighlight]);
```

**Key Techniques:**

1. **Data Attributes for Selection**: Add `data-node-id` attributes to DOM elements for reliable selection
2. **useCallback Memoization**: Prevents function recreation, making it safe to include in effect dependencies
3. **Double requestAnimationFrame**: Ensures DOM layout is complete before manipulation
4. **Interrupt Transitions**: Stop ongoing animations before applying new ones
5. **CSS Classes for State**: Use classes like `.highlighted` for easier debugging and cleanup

**Benefits:**
- ✅ Works immediately on user interaction (no effect delay)
- ✅ Persists across graph data changes
- ✅ Handles same-node re-clicks correctly
- ✅ No position tracking needed (styles the actual DOM element)
- ✅ Graceful cleanup on unmount or settings changes

### Application: Path Highlighting

**Use Case:** Visualize query results like "find path from Concept A to Concept B" by highlighting multiple nodes and edges along the route.

**Example - Highlighting a Path:**

```typescript
interface PathHighlight {
  nodeIds: string[];
  edgeIds: string[];
  style: 'primary' | 'secondary' | 'alternate';
}

const applyPathHighlight = useCallback((path: PathHighlight) => {
  if (!svgRef.current) return;

  const svg = d3.select(svgRef.current);

  // Clear previous path highlights
  svg.selectAll('.path-highlight').classed('path-highlight', false);

  // Highlight nodes in path
  path.nodeIds.forEach((nodeId, index) => {
    const circle = svg.select<SVGCircleElement>(`circle[data-node-id="${nodeId}"]`);

    if (!circle.empty()) {
      circle
        .classed('path-highlight', true)
        .attr('stroke', PATH_COLORS[path.style])
        .attr('stroke-width', 4)
        .attr('stroke-dasharray', index === 0 || index === path.nodeIds.length - 1 ? 'none' : '5,5');
        // Dashed for intermediate nodes, solid for start/end
    }
  });

  // Highlight edges in path
  path.edgeIds.forEach(edgeId => {
    const line = svg.select<SVGLineElement>(`line[data-edge-id="${edgeId}"]`);

    if (!line.empty()) {
      line
        .classed('path-highlight', true)
        .attr('stroke', PATH_COLORS[path.style])
        .attr('stroke-width', 3)
        .attr('stroke-opacity', 0.8);
    }
  });

  // Optional: Animate path traversal
  animatePathTraversal(path.nodeIds, path.edgeIds);
}, []);

// Animate a "flow" effect along the path
const animatePathTraversal = (nodeIds: string[], edgeIds: string[]) => {
  let delay = 0;

  nodeIds.forEach((nodeId, index) => {
    setTimeout(() => {
      const circle = d3.select(`circle[data-node-id="${nodeId}"]`);
      circle
        .transition()
        .duration(300)
        .attr('r', (d: D3Node) => ((d.size || 10) * settings.visual.nodeSize) * 1.5)
        .transition()
        .duration(300)
        .attr('r', (d: D3Node) => (d.size || 10) * settings.visual.nodeSize);
    }, delay);

    delay += 400;
  });
};
```

**Future Applications:**

1. **Multi-Path Comparison**: Show 3-5 paths simultaneously with different colors
   - Primary path: Gold (#FFD700)
   - Alternate path 1: Blue (#4A90E2)
   - Alternate path 2: Green (#50C878)

2. **Confidence Visualization**: Edge thickness proportional to relationship confidence
   ```typescript
   .attr('stroke-width', (d) => 1 + (d.confidence * 4)) // 1-5px based on 0-1 confidence
   ```

3. **Interactive Path Exploration**:
   - Click node in path → Show evidence from source documents
   - Hover edge → Show relationship type and confidence tooltip
   - Right-click path → "Find alternate paths" or "Explain this connection"

4. **Breadcrumb Trail Visualization**: Highlight your navigation history in the graph
   ```typescript
   applyPathHighlight({
     nodeIds: navigationHistory.trail.map(h => h.conceptId),
     edgeIds: [], // Don't highlight edges for history
     style: 'secondary'
   });
   ```

5. **Query Result Highlighting**: Show subgraph matching a pattern query
   - Highlight nodes matching pattern
   - Differentiate by role in pattern (subject, object, predicate)

**Performance Considerations:**

- Batch DOM updates when highlighting many nodes/edges
- Use CSS classes for bulk style changes when possible
- Debounce frequent highlight changes (e.g., during animation scrubbing)
- Consider virtual viewport for large graphs (only highlight visible elements)

```typescript
// Batch update example
const applyBatchHighlight = (nodeIds: string[], style: HighlightStyle) => {
  const svg = d3.select(svgRef.current);

  // Single D3 selection update for all nodes
  svg.selectAll<SVGCircleElement, D3Node>('circle')
    .filter((d) => nodeIds.includes(d.id))
    .attr('stroke', style.color)
    .attr('stroke-width', style.width)
    .classed('highlighted', true);
};
```

**Testing Checklist:**
- [ ] Highlights persist across graph reloads
- [ ] Multiple paths can be highlighted simultaneously
- [ ] Clicking same node re-applies highlight correctly
- [ ] Animations can be interrupted/restarted cleanly
- [ ] Cleanup occurs on unmount/setting toggle
- [ ] Performance acceptable with 100+ node paths

## Terminology

**Explorer vs. Workbench:**
- **Explorer**: Interactive visualization mode (Force-Directed, Hierarchy, etc.)
- **Workbench**: Query construction tool (Visual Query Builder, Path Finder, etc.)

We use "Explorer" to describe each interactive visualization mode. This term emphasizes the investigative, discovery-oriented nature of the tools and aligns with common graph database UI conventions (e.g., Neo4j Browser, graph explorers).

## Implementation Priority

**Phase 1 (Current):**
-  Force-Directed 2D Explorer
-  Basic click-to-focus navigation
-  Hover highlighting

**Phase 2 (Next):**
- = "You Are Here" persistent highlighter
- = Navigation history (back/forward buttons)
- = Breadcrumb trail
- = Right-click context menu

**Phase 3:**
- Expand on double-click
- Multi-select and bulk actions
- Path Explorer workbench
- Force-Directed 3D Explorer

**Phase 4:**
- Hierarchical Tree Explorer
- Timeline Explorer
- Visual Query Builder
- Ontology Comparator

## Success Metrics

**User Engagement:**
- Average exploration depth (clicks per session)
- Time spent in visualization
- Number of concepts explored per session

**Discovery Metrics:**
- Unexpected connections found
- Path queries executed
- Concepts bookmarked/exported

**Usability:**
- Navigation efficiency (time to find target)
- Error rate (backtracking, confusion)
- Feature adoption (% using history/context menu)

## References

- ADR-034: Graph Visualization Architecture
- [D3.js Force Simulation](https://d3js.org/d3-force)
- [Three.js Documentation](https://threejs.org/)
- [Neo4j Browser Interactions](https://neo4j.com/docs/browser-manual/current/)
- [Observable D3 Examples](https://observablehq.com/@d3)

## Approval & Sign-Off

- [ ] Development Team Review
- [ ] UX/UI Design Review
- [ ] User Testing (navigation flows)
- [ ] Documentation Complete
