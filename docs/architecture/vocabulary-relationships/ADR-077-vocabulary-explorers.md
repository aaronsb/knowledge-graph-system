---
status: Draft
---

# ADR-077: Vocabulary Explorers

## Status
Proposed

## Date
2025-12-10

## Context

The knowledge graph system uses a self-refining vocabulary of edge types (ADR-032) that grows organically as documents are ingested. With 100 edge types across 9+ categories and 4,856 relationships in the current database, understanding vocabulary usage patterns becomes increasingly important for:

1. **System health monitoring** - Which vocabulary types are heavily used vs dormant?
2. **Ontology debugging** - Why do certain edge types dominate? Are relationships being correctly categorized?
3. **Semantic flow understanding** - How do categories interconnect? What patterns emerge?
4. **Query-specific analysis** - What vocabulary characterizes a specific graph neighborhood?

Currently, vocabulary insights are only available via CLI (`kg vocab list`, `kg db stats`). The web interface lacks visual exploration tools for understanding edge type distribution and inter-category flows.

### Two Distinct Use Cases

**1. System-Wide Exploration (Edge Explorer)**
- View all vocabulary across the entire graph
- Understand category-level flows (Causation → Semantic, Evidential → Modification)
- Monitor vocabulary health: active vs dormant types, builtin vs custom
- Identify vocabulary consolidation opportunities
- No concept query required - operates on global statistics

**2. Query-Specific Exploration (Chord View)**
- Analyze vocabulary within a specific graph neighborhood (from 2D/3D explorer)
- Understand how a particular set of concepts are connected
- Filter/highlight specific edge types within the queried subgraph
- Complement to existing spatial visualization (2D/3D shows structure, chord shows vocabulary)

## Decision

Implement two vocabulary exploration tools as part of the web UI explorer framework:

### 1. Edge Explorer (`/vocabulary/edge`)
A system-wide visualization with three view modes:

**Chord View (Category Flow)**
- D3 chord diagram showing inter-category edge flows
- Arc width proportional to edge count per category
- Ribbon width proportional to edges between category pairs
- Hover to isolate specific category connections
- Interactive: click category to filter edge type list

**Edge Types View (Radial Bar)**
- Radial visualization with each edge type as a spoke
- Spoke length and width encode edge count
- Color-coded by category
- Click to show edge type details and flow patterns

**Matrix View**
- Category × Category adjacency matrix
- Cell size/intensity encodes edge count
- Hover rows/columns to highlight flows
- Good for dense category relationships

**Side Panel**
- Category health breakdown (types active/total, utilization %)
- Edge type ranking by count
- Dormant vocabulary list (unused types)
- Click edge type to see: category, builtin/custom, flow breakdown

### 2. Vocabulary Chord View (`/vocabulary/chord`)
Query-specific vocabulary analysis:

**Input**: Graph data from 2D/3D explorer (shared state via graphStore)
- When user performs a query in 2D explorer, vocabulary chord can analyze the same result set
- Alternatively: direct concept search within the vocabulary chord workspace

**Visualization**
- Chord diagram showing edge types used within the subgraph
- Nodes = concepts from the query result
- Chords = edges between them, colored by edge type category
- Filter/highlight by category or specific edge type

**Side Panel**
- Edge type breakdown for this specific subgraph
- Comparison to system-wide distribution (is this subgraph typical?)
- Concept-to-concept edge listing with types

## Implementation Plan

### Phase 1: API Endpoints

Add endpoints to `/vocabulary` routes:

```python
# System-wide statistics
GET /vocabulary/system-stats
Response: {
  stats: { concepts, sources, instances, totalRelationships, vocabularySize, activeVocabulary },
  categories: [{ id, name, color, totalTypes, activeTypes, totalEdges }],
  edgeTypes: [{ type, category, count, builtin, confidence }],
  categoryFlows: [{ source, target, count, types: [{type, count}] }]
}

# Query-specific vocabulary analysis
POST /vocabulary/analyze-subgraph
Body: { conceptIds: string[] }
Response: {
  edgeTypes: [{ type, category, count }],
  categoryFlows: [{ source, target, count }],
  conceptEdges: [{ from, to, type, category }]
}
```

### Phase 2: Components

**Directory Structure:**
```
web/src/components/vocabulary/
├── EdgeExplorerWorkspace.tsx      # Main workspace for system-wide
├── VocabularyChordWorkspace.tsx   # Main workspace for query-specific
├── visualizations/
│   ├── ChordDiagram.tsx           # D3 chord diagram (shared)
│   ├── RadialEdgeTypes.tsx        # Radial bar chart
│   ├── CategoryMatrix.tsx         # Matrix view
│   └── EdgeTypeList.tsx           # Ranked list panel
├── panels/
│   ├── CategoryHealthPanel.tsx    # Category breakdown
│   ├── EdgeTypeDetailPanel.tsx    # Single type details
│   └── SubgraphComparisonPanel.tsx # Compare to system average
└── types.ts                       # TypeScript interfaces
```

### Phase 3: Integration

1. **Routing**: Add `/vocabulary/edge` and `/vocabulary/chord` routes
2. **Navigation**: Add to sidebar under "Vocabulary" section
3. **Graph Store Integration**: Share query results between 2D/3D explorer and chord view
4. **Theme Integration**: Use existing theming system (postmodern, etc.)

### Phase 4: Data Flow

**Edge Explorer** (System-Wide):
```
Page Load → GET /vocabulary/system-stats → Render chord/radial/matrix
Hover category → Filter ribbons/bars
Click edge type → Show detail panel
```

**Vocabulary Chord** (Query-Specific):
```
Option A: Import from 2D/3D
  User queries in 2D → graphStore.nodes/edges populated
  Navigate to Vocabulary Chord → POST /vocabulary/analyze-subgraph with concept IDs

Option B: Direct search
  User enters search in Vocabulary Chord
  Query concepts → POST /vocabulary/analyze-subgraph
```

## Consequences

### Positive
- Visual insight into vocabulary health and distribution
- Easier identification of vocabulary consolidation candidates
- Complement to spatial graph views (2D/3D shows structure, chord shows vocabulary)
- Query-specific analysis enables debugging specific neighborhoods
- Reusable chord diagram component for future use

### Negative
- D3 chord diagrams are complex to implement well
- Performance considerations for large vocabularies (100+ types)
- Additional API endpoints and database queries
- More components to maintain

### Neutral
- Natural extension of existing explorer pattern (2D, 3D, Polarity, now Vocabulary)
- Follows established workspace structure

## Technical Notes

### D3 Integration
- Use `d3-chord` for chord layout computation
- Render via React SVG (not raw D3 DOM manipulation)
- `useMemo` for expensive layout calculations
- Responsive sizing via `ResponsiveContainer` pattern (see Polarity)

### Category Colors (From Prototypes)
```typescript
const categoryColors = {
  evidential: "#4ade80",    // Green
  causation: "#f97316",     // Orange
  modification: "#a78bfa",  // Purple
  semantic: "#38bdf8",      // Blue
  logical: "#fbbf24",       // Yellow
  composition: "#f472b6",   // Pink
  dependency: "#ef4444",    // Red
  hierarchical: "#94a3b8",  // Gray
  temporal: "#2dd4bf",      // Teal
  operation: "#fb923c",     // Light orange
};
```

### Performance Considerations
- Category flow matrix is O(categories²) - manageable with ~10 categories
- Edge type list can be virtualized if needed (>100 types)
- Chord ribbons scale with category pairs, not total edges

## Alternatives Considered

### Single Explorer with Tabs
Could combine Edge Explorer and Chord View into one workspace with tabs. Rejected because:
- Different data sources (system-wide vs query-specific)
- Different mental models (monitoring vs analysis)
- Cleaner separation of concerns

### Force-Directed Edge Type Graph
Could show edge types as nodes connected by co-occurrence. Rejected because:
- Chord diagram more effectively shows flows
- Force layout less intuitive for vocabulary relationships

### Sankey Diagram Instead of Chord
Sankey good for flow but:
- Chord better shows bidirectional flows (A→B and B→A)
- Chord more compact for self-loops (semantic→semantic)
- Chord established in prototype designs

## Related ADRs

- ADR-032: Automatic Edge Vocabulary Expansion
- ADR-047: Vocabulary Category Scoring
- ADR-053: Vocabulary Similarity Analysis
- ADR-065: Epistemic Status Classification
- ADR-070: Polarity Axis Analysis (similar explorer pattern)

## References

- Prototype: `kg-edge-explorer-v3.jsx` (system-wide chord/radial/matrix)
- Prototype: `vocabulary-chord-view.jsx` (query-specific analysis)
- D3 Chord: https://d3js.org/d3-chord
