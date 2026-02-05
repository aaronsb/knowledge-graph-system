# Saved Queries

How to save, load, and share graph explorations across explorer views.

## What is a Saved Query?

A saved query is an ordered list of graph operations — each tagged as additive (+) or subtractive (-). This is the universal unit of work across all explorer views.

```
+ MATCH (c:Concept)-[r*1..1]-(n:Concept) WHERE c.concept_id = 'abc' RETURN c, r, n;
+ MATCH (c:Concept)-[r*1..1]-(n:Concept) WHERE c.concept_id = 'def' RETURN c, r, n;
- MATCH (c:Concept) WHERE c.concept_id = 'xyz' RETURN c;
```

The `+` operator merges results into the graph. The `-` operator removes nodes and their edges. This lets you sculpt a graph by building it up and trimming it down.

## Creating a Saved Query

### From Smart Search (2D/3D Graph)

Every action you take in the graph explorer is recorded as a step:

1. **Search** for a concept — step recorded as `+ MATCH ...`
2. **Right-click a node** and choose "Add Adjacent" — step recorded as `+`
3. **Right-click a node** and choose "Remove from Graph" — step recorded as `-`
4. **Follow** a concept (double-click) — step recorded as `+`

When you have a graph you want to keep:
1. Open the **Saved Queries** panel (folder icon in the left rail)
2. Click **Save Exploration**
3. Give it a name
4. The full step sequence is saved as a replayable program

### From the Cypher Editor

Write `+` and `-` prefixed statements directly:

```
+ MATCH (c:Concept)-[r*1..2]-(n:Concept) WHERE c.label CONTAINS 'governance' RETURN c, r, n;
- MATCH (c:Concept) WHERE c.label CONTAINS 'deprecated' RETURN c;
```

Save via the Saved Queries panel.

### From the Block Editor

Block diagrams compile to Cypher statements. Save via the panel as a block diagram definition.

## Loading a Saved Query

1. Open any explorer view
2. Open the **Saved Queries** panel (folder icon)
3. Click a saved query

The system replays each statement in order, applying `+/-` operators to build the graph state. The result is identical to the original exploration.

## Cross-Explorer Flow

Saved queries are shared across all explorer views. Save in one, load in another:

| Explorer | What it shows from the same query |
|----------|-----------------------------------|
| 2D Graph | Force-directed node/edge visualization |
| 3D Graph | Spatial perspective of the same graph |
| Cypher Editor | The `+/-` statements as editable text |
| Vocabulary Analysis | Relationship type breakdown of query results |
| Document Explorer | Source documents for the query's concepts |
| Polarity Explorer | Semantic axis analysis of query concepts |
| Embedding Landscape | Embedding space projection of query concepts |

Switching views preserves the graph. The folder icon appears consistently in all rails.

## Query Types

Each saved query has a type that determines how it replays:

| Type | Saved From | Contains |
|------|-----------|----------|
| `exploration` | Smart search, Cypher editor | `{ op, cypher }[]` statements |
| `polarity` | Polarity explorer | Pole concept IDs + analysis params |
| `block_diagram` | Block editor | ReactFlow nodes/edges layout |

The Saved Queries panel shows type-aware subtitles (e.g., "3 steps" for explorations, "2 poles" for polarity).

## The +/- Operator Algebra

The operators work like set arithmetic on graph results:

- **`+` (union)**: Execute the Cypher statement and merge its nodes/edges into the current graph. Duplicate nodes are deduplicated by ID.
- **`-` (difference)**: Execute the Cypher statement and remove matching nodes from the current graph. Edges connected to removed nodes are also removed.

### Example: Building a Focused Subgraph

```
# Start with everything related to "governance"
+ MATCH (c:Concept)-[r*1..2]-(n) WHERE c.label CONTAINS 'governance' RETURN c, r, n;

# Add concepts about "compliance"
+ MATCH (c:Concept)-[r*1..1]-(n) WHERE c.label CONTAINS 'compliance' RETURN c, r, n;

# Remove noise — concepts about "legacy systems"
- MATCH (c:Concept) WHERE c.label CONTAINS 'legacy' RETURN c;
```

This produces a graph focused on governance + compliance, with legacy system noise trimmed out.

## Exporting to Cypher

From the 2D/3D graph explorer, your exploration can be sent to the Cypher editor:

1. Build your graph through search and navigation
2. The exploration session is automatically tracked
3. Switch to the Cypher editor tab
4. Your steps appear as `+/-` prefixed statements
5. Edit, rearrange, or share the text

The text format is designed to be copy/pasteable between users.

## Document Explorer Integration

The Document Explorer uses saved exploration queries differently:

1. Load an exploration query
2. The system finds all documents containing those concepts
3. A multi-document concept graph is built automatically
4. Passage search adds colored rings to matching nodes
5. Double-click a document to view it with highlighted passages

## Tips

- **Name queries descriptively** — "Governance + Compliance minus Legacy" is better than "Query 1"
- **Start broad, then subtract** — it's easier to remove noise than to find everything piecemeal
- **Use the Cypher editor to inspect** — seeing the statements helps understand what an exploration actually does
- **Cross-explorer replay is instant** — saved queries don't re-fetch from the API, they replay the recorded operations

## Next Steps

- [Exploring Knowledge](exploring.md) — General search and navigation
- [Querying](querying.md) — CLI, API, and MCP query access
- [Polarity Axis Analysis](POLARITY_AXIS_ANALYSIS.md) — Semantic dimension analysis
