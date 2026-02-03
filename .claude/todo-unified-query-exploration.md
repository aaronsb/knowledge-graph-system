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

### Phase 2: Saved Queries Folder
- [ ] Unify sidebar folder icon across all explorer views (consistent with report explorer pattern)
- [ ] Saved query data model: `{ name, statements: { op, cypher }[] }`
- [ ] Save exploration → creates QueryDefinition with `definition_type: 'exploration'`
- [ ] Load saved query → executes statements in order with +/- semantics
- [ ] Delete saved query

### Phase 3: Editor Integration
- [ ] "Export as Cypher" sends ordered statements to the Cypher editor
- [ ] Cypher editor displays +/- prefixed statements
- [ ] Execute from editor replays the statement sequence
- [x] Subtractive operator: context menu "Remove from Graph" option

### Phase 4: Cross-Explorer Flow
- [ ] Vocabulary explorer reads same saved queries from folder
- [ ] Document explorer reads same saved queries
- [ ] Polarity explorer loads graph from saved query
- [ ] Verify all explorers share the same folder state

### Phase 5: Documentation & Docstrings
- [ ] Add JSDoc docstrings to new exploration tracking code
- [ ] Add JSDoc docstrings to graphStore (actions, types)
- [ ] Add JSDoc docstrings to cypherGenerator
- [ ] Add JSDoc docstrings to SearchBar handlers
- [ ] Add JSDoc docstrings to useGraphContextMenu handlers
- [ ] Document the unified query exploration workflow in user manual
- [ ] Document the +/- operator algebra concept

## Notes

- Block builder compiles TO Cypher but we don't decompose Cypher back to blocks (existing ADR)
- Graph accelerator makes this practical — path finding is now fast enough for interactive multi-step exploration
- The +/- algebra on statements is like set operations: union then difference, letting users sculpt their graph
