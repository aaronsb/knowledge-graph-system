# Reports Feature Implementation

Send graph/polarity data from explorers to a tabular Reports view.

## Architecture

```
Explorers (2D, 3D, Polarity)
    ↓ "Send to Reports" button
Report Store (Zustand + localStorage)
    ↓
Report Workspace (IconRailPanel + Table Views)
    ↓
Copy/Export (JSON, CSV, Markdown)
```

## Implementation Checklist

### Phase 1: Core Infrastructure

- [x] Create `reportStore.ts` with Zustand + persist
  - Report types: `graph` | `polarity`
  - CRUD operations: add, delete, rename, select
  - localStorage persistence
  - Delta tracking with previousValues for recalculation

- [x] Update `ReportWorkspace.tsx`
  - IconRailPanel with tabs: Reports (list), Settings
  - Center: Table view of selected report
  - Empty state when no reports

### Phase 2: Table Views

- [x] Graph Report Table View
  - Concepts table (label, description, ontology, grounding, diversity)
  - Relationships table (source, type, target, category, confidence)
  - Sortable columns (all columns clickable to sort)
  - Query info display (mode, center concept, depth)

- [x] Polarity Report Table View
  - Axis info (poles, magnitude)
  - Concepts table (label, position, similarities, grounding)
  - Direction distribution summary
  - Sortable columns

### Phase 3: Send to Reports Buttons

- [x] 2D Explorer: Add "Send to Reports" button
  - Capture current graph state from `useGraphStore`
  - Navigate to `/report` after sending

- [x] 3D Explorer: Add "Send to Reports" button
  - Same as 2D

- [x] Polarity Explorer: Add "Send to Reports" button
  - Capture polarity analysis result
  - Include axis definition and projections

### Phase 4: Copy/Export

- [x] Copy as JSON button
- [x] Copy as CSV button
- [x] Copy as Markdown button
- [x] Download as file option

### Phase 5: Polish

- [x] Report naming/renaming (double-click to edit)
- [x] Delete confirmation
- [x] Recalculate button with progress indicator
- [x] Delta indicators (↑ green, ↓ red, – flat)
- [x] "Computed at" timestamp display
- [ ] Keyboard shortcuts (Ctrl+C for copy)
- [ ] Empty state illustrations

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `web/src/store/reportStore.ts` | Created | Zustand store with delta tracking |
| `web/src/components/report/ReportWorkspace.tsx` | Modified | Full workspace with tables, sorting, recalculate |
| `web/src/views/ExplorerView.tsx` | Modified | Added Send to Reports button |
| `web/src/components/polarity/PolarityExplorerWorkspace.tsx` | Modified | Added Send to Reports button |

## Data Flow

### Graph Report
```typescript
// From graphStore
const { rawGraphData, searchParams } = useGraphStore();

// Transform to report
const report: GraphReportData = {
  type: 'graph',
  nodes: rawGraphData.nodes.map(n => ({
    id: n.id,
    label: n.label,
    description: n.description,
    ontology: n.ontology,
    grounding_strength: n.grounding_strength,
    diversity_score: n.diversity_score,
  })),
  links: rawGraphData.links,
  searchParams: { ... }
};
```

### Polarity Report
```typescript
// From polarityState.analysisHistory[selected]
const analysis = polarityState.analysisHistory.find(a => a.id === selectedAnalysisId);

// Transform to report
const report: PolarityReportData = {
  type: 'polarity',
  positivePole: { ... },
  negativePole: { ... },
  axisMagnitude: analysis.result.axis_quality.magnitude,
  concepts: analysis.result.projections,
  directionDistribution: analysis.result.direction_distribution,
};
```

### Recalculate Flow
```typescript
// Fetch full concept details for all nodes
const details = await apiClient.getConceptDetails(node.id);

// Enrich nodes with grounding, diversity, description
// Enrich links with confidence, category from relationships
// Store previous values for delta comparison
updateReportData(id, newData);
```
