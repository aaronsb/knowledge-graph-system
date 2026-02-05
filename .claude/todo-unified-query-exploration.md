# Unified Query Exploration System

## Vision

The saved query is the universal unit of work across all explorer views. A query is an ordered list of Cypher statements with additive/subtractive operators, built interactively or by hand, that flows through every explorer identically.

### Core Concept

```
{ name: string, statements: { op: '+' | '-', cypher: string }[] }
```

Each statement represents one intentional action — a discrete thought in an exploration sequence. The order mirrors how the user actually explored. Replay executes them in order, merging (+) or removing (-) each result.

### Entry Points (all produce the same saved artifact)

- **Smart Search** — interactive clicks, add-to-existing, add-adjacent → generates Cypher per action
- **Block Builder** — visual composition → compiles to Cypher
- **Cypher Editor** — hand-written or pasted from a friend
- **Saved query recall** — load a previously saved exploration

### Explorer Views (all consume the same saved query)

| Explorer | What it shows |
|----------|---------------|
| 2D Graph | Force-directed visualization, primary interactive builder |
| 3D Graph | Same graph, spatial perspective |
| Cypher Editor | The statements as editable text, copy/pasteable |
| Vocabulary Analysis | Relationship type introspection on the query's result set |
| Document Explorer | Source documents contributing to the query's concepts |
| Polarity Explorer | Pick edges from the query's graph for polarity axis analysis |

### Sidebar Consistency

Folder icon in the nav rail across all explorer views. Same saved queries list, different lens on the data. Switching views preserves the graph.

## Implementation Phases

### Phase 1: Exploration Tracking & Cypher Generation ✓
- [x] Add `ExplorationStep` type and `explorationSession` to graphStore
- [x] Add `addExplorationStep()`, `clearExploration()` store actions
- [x] Record steps at action points: handleLoadExplore, handleLoadPath, handleFollowConcept, handleAddToGraph
- [x] Create `cypherGenerator.ts` — convert steps to ordered Cypher statements with +/- operators
- [x] Persist `rawGraphData` + `explorationSession` to localStorage (survive refresh)
- [x] Add `subtractRawGraphData` and "Remove from Graph" context menu (op: '-')

### Phase 2: Saved Queries Folder ✓
- [x] Unify sidebar folder icon across all explorer views (FolderOpen, consistent with report explorer)
- [x] Saved query data model: `{ name, statements: { op, cypher }[] }` via QueryDefinition
- [x] Save exploration → creates QueryDefinition with `definition_type: 'exploration'`
- [x] Load saved query → replays statements in order with +/- semantics via executeCypherQuery
- [x] Delete saved query (already worked via queryDefinitionStore)

### Phase 3: Editor Integration ✓
- [x] "Export as Cypher" sends ordered statements to the Cypher editor
- [x] Cypher editor displays +/- prefixed statements
- [x] Execute from editor replays the statement sequence
- [x] Subtractive operator: context menu "Remove from Graph" option

### Phase 4: Cross-Explorer Flow ✓
- [x] Vocabulary explorer reads same saved queries from folder (EdgeExplorerWorkspace)
- [x] Document explorer reads same saved queries (DocumentExplorerWorkspace)
- [x] Polarity explorer loads graph from saved query (PolarityExplorerWorkspace)
- [x] Embedding landscape loads graph from saved query (EmbeddingLandscapeWorkspace)
- [x] Verify all explorers share the same folder state (queryDefinitionStore)
- [x] Type dataTransformer contract with RawGraphData
- [x] Extract color computation from graphTransform.ts into colorScale.ts
- [x] Rename D3Node/D3Link to RenderNode/RenderLink (renderer-agnostic)

### Phase 5: Documentation & Docstrings ✓
- [x] Add JSDoc docstrings to new exploration tracking code
- [x] Add JSDoc docstrings to graphStore (actions, types)
- [x] Add JSDoc docstrings to cypherGenerator
- [x] Add JSDoc docstrings to SearchBar handlers
- [x] Add JSDoc docstrings to useGraphContextMenu handlers
- [x] Document the unified query exploration workflow in user manual (`docs/guides/SAVED_QUERIES.md`)
- [x] Document the +/- operator algebra concept
- [x] Fill remaining docstring gaps (graphStore 4/9→9/9, queryDefinitionStore, useQueryReplay, ExplorerView, useGraphContextMenu)

### Phase 6: Type-Aware Saved Queries ✓
- [x] Backend: `POST /query/documents/by-concepts` endpoint (concept→document reverse lookup)
- [x] Frontend: `findDocumentsByConcepts` API client method
- [x] SavedQueriesPanel: type-aware subtitles (exploration→steps, polarity→poles, block→nodes)
- [x] SavedQueriesPanel: `saveButtonLabel` prop for per-explorer save button text
- [x] useQueryReplay: polarity handler (restores pole selections, triggers auto-analysis)
- [x] PolarityExplorerWorkspace: save/load pole selections as `definition_type: 'polarity'`
- [x] DocumentExplorerWorkspace: load exploration query → concept→document reverse lookup

## Notes

- Block builder compiles TO Cypher but we don't decompose Cypher back to blocks (existing ADR)
- Graph accelerator makes this practical — path finding is now fast enough for interactive multi-step exploration
- The +/- algebra on statements is like set operations: union then difference, letting users sculpt their graph
