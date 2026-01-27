---
status: Proposed
date: 2025-10-17
deciders: Development Team
related:
  - ADR-034
  - ADR-035
  - ADR-016
---

# ADR-036: Universal Visual Query Builder

## Overview

Writing graph queries requires learning openCypher syntax—a barrier that keeps many users from fully exploring their knowledge graphs. When a simple search fails at the default similarity threshold, the system currently just says "no results" without guiding users toward better queries or suggesting adjustments.

The deeper problem is that query interfaces are tied to specific visualizations. Search works in the force graph explorer but not elsewhere. There's no way to build complex queries visually, no way to find paths between concepts without writing code, and no way to express patterns like "find concepts that IMPLIES concepts that CONTRADICTS each other."

This ADR introduces a tri-mode universal query builder that works with any explorer: Smart Search for enhanced text queries with recommendations, Visual Blocks for drag-and-drop query construction, and an openCypher editor for power users. The key insight is the "Rosetta Stone" learning pattern—building queries visually while seeing the generated openCypher teaches users the syntax organically, creating a bridge from visual to textual expertise.

---

## Context

The current visualization application uses a simple concept search interface. While functional, it has several limitations:

**Current Issues:**
1. **Silent failures on phrase searches** - Multi-word queries like "change velocity as a marker of value" fail at default threshold but don't guide users to better results
2. **No smart recommendations** - System says "found 20 concepts at lower similarity (try 30%)" but doesn't show which concept is the best match
3. **Limited query expressiveness** - Cannot express:
   - Path finding: "find paths from ethics to regulation"
   - Neighborhood exploration: "show concepts within 2 hops"
   - Pattern matching: "find concepts that IMPLIES concepts that CONTRADICTS each other"
4. **No visual query construction** - All text-based, barrier to exploration
5. **Explorer-specific queries** - Search is embedded in individual explorers, not reusable

**Design Goal:**
Create a **universal, explorer-agnostic query builder** that produces `QueryResult` objects consumable by any visualization explorer (Force-Directed, Hierarchical Tree, Timeline, etc.).

**Inspiration:**
- **Blockly** - Visual block-based programming
- **TidalCycles** - Hybrid text/visual live coding for music
- **Observable notebooks** - Reactive data exploration

## Decision

Implement a **tri-mode universal query builder** as the primary interface for querying the knowledge graph:

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Query Builder (Universal)                │
│  Mode: [Smart Search] [Visual Blocks] [openCypher]          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Mode-specific UI]                                         │
│  - Smart: Enhanced search with recommendations             │
│  - Visual: Drag-and-drop query blocks                      │
│  - Cypher: Monaco editor with openCypher syntax            │
│                                                             │
│  [Run Query] → QueryResult                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
                    QueryResult
                    (nodes, links, meta)
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                 ↓                 ↓
   Force-Directed    Hierarchical       Timeline
   Explorer          Explorer           Explorer
   (renders)         (renders)          (renders)
```

### Mode 1: Smart Search (Enhanced Concept Search)

**Enhancement over current search:**

```typescript
interface SmartSearchResult {
  results: Concept[];
  meta: {
    threshold: number;
    totalAtThreshold: number;
    recommendation?: {
      message: string;
      suggestedThreshold: number;
      topConcept: {
        label: string;
        similarity: number;
      };
    };
  };
}
```

**Example UX:**

```
┌─────────────────────────────────────────────────────┐
│ Search: [change velocity as a marker________]       │
│ Similarity: [||||||||----------] 50%                │
│                                                     │
│ ⚠ No results at 50%                                 │
│ 💡 Try "Organizational Change" (67% @ 30%)          │
│                                                     │
│ [Adjust to 30%] [View 20 results]                  │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Threshold slider (0-100%)
- Real-time result count as slider moves
- Top match recommendation at lower threshold
- Auto-complete with similarity scores
- Query history

**Implementation:**
- Enhance existing `SearchBar.tsx`
- Add `/search/smart` endpoint to API
- Return top match metadata when count > 0 at lower threshold

---

### Mode 2: Visual Block Builder

**Concept:** Drag-and-drop blocks that compile to openCypher

**Block Palette:**

```
🔍 Search         - Find concepts by text/similarity
🔗 Path           - Find paths between concepts
🌐 Neighborhood   - Explore N-hop neighbors
🎯 Pattern        - Match graph patterns (MATCH clause)
📊 Filter         - Filter by ontology/relationship type
⚙️ Transform      - Limit/sort/aggregate results
🔀 Combine        - Union/intersect multiple queries
```

**Example Visual Query:**

```
┌─────────────────────────────────────────────────────┐
│ [+ Add Block ▼]                          [Run]      │
│                                                     │
│  ┌───────────────────────────────────────────┐     │
│  │ 🔍 Search for concepts                     │     │
│  │    matching: [organizational       ▼]     │     │
│  │    similarity: [||||||||------] 60%       │     │
│  │    limit: [10]                  [×]       │     │
│  └───────────────────────────────────────────┘     │
│          ↓ Then                                     │
│  ┌───────────────────────────────────────────┐     │
│  │ 🌐 Expand neighborhood                     │     │
│  │    depth: [2] hops                        │     │
│  │    direction: [Both        ▼]   [×]       │     │
│  └───────────────────────────────────────────┘     │
│          ↓ Then                                     │
│  ┌───────────────────────────────────────────┐     │
│  │ 📊 Filter results                          │     │
│  │    ontology: [TBM Model    ▼]   [×]       │     │
│  └───────────────────────────────────────────┘     │
│                                                     │
│  Generated openCypher: [View ▼]                    │
│  MATCH (c:Concept)                                 │
│  WHERE c.label CONTAINS 'organizational'           │
│  MATCH (c)-[*1..2]-(neighbor:Concept)              │
│  WHERE neighbor.ontology = 'TBM Model'             │
│  RETURN DISTINCT neighbor                          │
│  LIMIT 10                                          │
└─────────────────────────────────────────────────────┘
```

**Block Structure:**

```typescript
interface QueryBlock {
  id: string;
  type: 'search' | 'path' | 'neighborhood' | 'filter' | 'transform';
  params: Record<string, any>;
  children?: QueryBlock[];
}

// Example blocks:
const searchBlock: QueryBlock = {
  id: 'block-1',
  type: 'search',
  params: {
    query: 'organizational',
    similarity: 0.6,
    limit: 10,
  },
};

const neighborhoodBlock: QueryBlock = {
  id: 'block-2',
  type: 'neighborhood',
  params: {
    depth: 2,
    direction: 'both',
  },
};

const filterBlock: QueryBlock = {
  id: 'block-3',
  type: 'filter',
  params: {
    ontology: ['TBM Model'],
  },
};
```

**Block Compiler:**

```typescript
function compileToOpenCypher(blocks: QueryBlock[]): string {
  // Compile block AST → openCypher query
  const clauses = blocks.map(compileBlock);
  return clauses.join('\n');
}

function compileBlock(block: QueryBlock): string {
  switch (block.type) {
    case 'search':
      return `MATCH (c:Concept) WHERE c.label CONTAINS '${block.params.query}'`;
    case 'neighborhood':
      return `MATCH (c)-[*1..${block.params.depth}]-(neighbor:Concept)`;
    case 'filter':
      return `WHERE neighbor.ontology IN [${block.params.ontology.map(o => `'${o}'`).join(', ')}]`;
    // ... etc
  }
}
```

**UI Components:**
- React DnD or React Flow for drag-and-drop
- Block palette sidebar
- Canvas area for query construction
- Block controls (sliders, dropdowns, concept selectors)
- Real-time openCypher preview

---

### Mode 3: openCypher Editor

**Raw openCypher editing with syntax support**

**Features:**
- Syntax highlighting for openCypher keywords
- Basic autocomplete (keywords, node labels, relationship types)
- Syntax error detection
- Query execution
- Result preview

**Editor Choice: Monaco Editor with Custom Language Definition**

**Why Monaco:**
- Powers VS Code - mature, well-tested
- Custom language definition support
- Syntax highlighting, autocomplete, error detection
- Lightweight embedding

**Why NOT Neo4j tools:**
- Neo4j's Cypher has proprietary extensions (e.g., `ON CREATE SET`, `ON MATCH SET`)
- Apache AGE implements **openCypher** (ISO/IEC 39075:2024 GQL)
- Neo4j language servers/extensions would encourage incompatible syntax

**Custom openCypher Definition:**

```typescript
import * as monaco from 'monaco-editor';

// Define openCypher language for Monaco
monaco.languages.register({ id: 'opencypher' });

monaco.languages.setMonarchTokensProvider('opencypher', {
  keywords: [
    // Core openCypher keywords (ISO/IEC 39075:2024 GQL)
    'MATCH', 'WHERE', 'RETURN', 'CREATE', 'MERGE', 'DELETE',
    'SET', 'REMOVE', 'WITH', 'UNWIND', 'CALL', 'UNION',
    'ORDER', 'BY', 'LIMIT', 'SKIP', 'ASC', 'DESC',
    'AND', 'OR', 'NOT', 'XOR', 'IN', 'CONTAINS', 'STARTS',
    'ENDS', 'NULL', 'TRUE', 'FALSE', 'DISTINCT', 'ALL',
    'OPTIONAL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
  ],

  typeKeywords: [
    'Concept', 'Source', 'Instance', 'Evidence',
  ],

  relationshipTypes: [
    'IMPLIES', 'SUPPORTS', 'CONTRADICTS', 'PART_OF',
    'REQUIRES', 'ENABLES', 'APPEARS_IN', 'EVIDENCED_BY',
  ],

  operators: [
    '=', '<>', '<', '>', '<=', '>=', '+', '-', '*', '/', '%',
    '..', // Variable-length path
  ],

  // Tokenizer rules
  tokenizer: {
    root: [
      [/\b(MATCH|WHERE|RETURN|CREATE|MERGE)\b/, 'keyword'],
      [/\b(Concept|Source|Instance)\b/, 'type'],
      [/\b(IMPLIES|SUPPORTS|CONTRADICTS)\b/, 'relationship'],
      [/'[^']*'/, 'string'],
      [/\d+/, 'number'],
      [/[()[\]{}]/, 'delimiter.bracket'],
      [/[<>=!]+/, 'operator'],
    ],
  },
});

// Define autocomplete provider
monaco.languages.registerCompletionItemProvider('opencypher', {
  provideCompletionItems: (model, position) => {
    const suggestions = [
      {
        label: 'MATCH',
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: 'MATCH (n:Concept)',
        detail: 'Match pattern in graph',
      },
      {
        label: 'RETURN',
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: 'RETURN ',
        detail: 'Return results',
      },
      // Add more completions based on context
    ];
    return { suggestions };
  },
});
```

**Reference:**
- openCypher Language Reference: https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
- Apache AGE Documentation: https://age.apache.org/age-manual/master/intro/cypher.html
- ISO/IEC 39075:2024 GQL Standard

**Query Execution:**

```typescript
const CypherEditor: React.FC = () => {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);

  const executeQuery = async () => {
    const response = await fetch('/api/query/cypher', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
    const result = await response.json();
    setResult(result);
  };

  return (
    <div>
      <MonacoEditor
        language="opencypher"
        value={query}
        onChange={setQuery}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
        }}
      />
      <button onClick={executeQuery}>Run Query</button>
      {result && <ResultPreview result={result} />}
    </div>
  );
};
```

---

## Universal QueryResult Interface

**Contract between Query Builder and Explorers:**

```typescript
export interface QueryResult {
  // Graph data
  nodes: GraphNode[];
  links: GraphLink[];

  // Metadata
  meta: {
    queryType: 'concept_search' | 'path_finding' | 'neighborhood' | 'pattern' | 'raw_cypher';
    executionTime: number;
    totalResults: number;
    cypherQuery: string;  // The actual query executed

    // Optional query-specific metadata
    pathCount?: number;          // For path finding
    depth?: number;              // For neighborhood queries
    similarity?: number;         // For concept search
    recommendation?: {           // For smart search
      message: string;
      suggestedThreshold: number;
      topConcept?: {
        label: string;
        similarity: number;
      };
    };
  };
}

export interface GraphNode {
  id: string;
  label: string;
  ontology: string;
  color: string;
  size?: number;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
  color: string;
  value?: number;
}
```

**Explorer Consumption:**

```typescript
// Any explorer can consume QueryResult
const ForceGraph2D: React.FC<{ result: QueryResult }> = ({ result }) => {
  return <D3ForceGraph nodes={result.nodes} links={result.links} />;
};

const HierarchicalTree: React.FC<{ result: QueryResult }> = ({ result }) => {
  const treeData = convertToTree(result.nodes, result.links);
  return <TreeVisualization data={treeData} />;
};

const Timeline: React.FC<{ result: QueryResult }> = ({ result }) => {
  const timelineData = extractTimestamps(result.nodes);
  return <TimelineVisualization data={timelineData} />;
};
```

---

## API Endpoints

**New query endpoints:**

```typescript
// Smart search with recommendations
POST /api/query/smart
{
  query: "organizational change",
  similarity: 0.5,
  limit: 10
}
→ QueryResult

// Visual block execution
POST /api/query/visual
{
  blocks: [
    { type: 'search', params: { query: 'organizational', similarity: 0.6 } },
    { type: 'neighborhood', params: { depth: 2 } },
  ]
}
→ QueryResult

// Raw openCypher
POST /api/query/cypher
{
  query: "MATCH (c:Concept) WHERE c.label CONTAINS 'organizational' RETURN c LIMIT 10"
}
→ QueryResult
```

---

## Implementation Phases

### Phase 1: Smart Search Enhancement (Quick Win)
**Goal:** Improve current search with better recommendations

- [ ] Add threshold slider to SearchBar
- [ ] Implement `/api/query/smart` endpoint
- [ ] Return top match metadata when no results
- [ ] Show recommendation UI: "Try 'X' (75% @ 30%)"
- [ ] Add query history

**Files:**
- `viz-app/src/components/shared/SearchBar.tsx` (enhance)
- `viz-app/src/api/client.ts` (add smartSearch method)
- `src/api/routes/queries.py` (add smart_search endpoint)

**Time Estimate:** 1-2 days

---

### Phase 2: QueryResult Refactoring
**Goal:** Standardize query → explorer data flow

- [ ] Define `QueryResult` interface
- [ ] Refactor explorers to consume `QueryResult`
- [ ] Update `useGraphData` hook to return `QueryResult`
- [ ] Add query metadata display component

**Files:**
- `viz-app/src/types/query.ts` (new)
- `viz-app/src/hooks/useGraphData.ts` (refactor)
- `viz-app/src/explorers/ForceGraph2D/ForceGraph2D.tsx` (update props)

**Time Estimate:** 2-3 days

---

### Phase 3: openCypher Editor
**Goal:** Raw query capability with syntax support

- [ ] Install Monaco Editor: `npm install monaco-editor`
- [ ] Define custom openCypher language
- [ ] Create `CypherEditor.tsx` component
- [ ] Implement `/api/query/cypher` endpoint
- [ ] Add mode switcher to Query Builder

**Files:**
- `viz-app/src/components/query/CypherEditor.tsx` (new)
- `viz-app/src/components/query/QueryBuilder.tsx` (new)
- `viz-app/src/lib/monaco-opencypher.ts` (new language definition)
- `src/api/routes/queries.py` (add cypher_query endpoint)

**Dependencies:**
```json
{
  "monaco-editor": "^0.52.0",
  "monaco-editor-webpack-plugin": "^7.1.0"
}
```

**Time Estimate:** 3-4 days

---

### Phase 4: Visual Block System
**Goal:** Drag-and-drop query construction

- [ ] Choose block library (React Flow vs React DnD)
- [ ] Design block component architecture
- [ ] Implement block palette
- [ ] Create canvas area
- [ ] Build block compiler (AST → openCypher)
- [ ] Implement `/api/query/visual` endpoint

**Block Types (Initial):**
- 🔍 Search Block
- 🌐 Neighborhood Block
- 📊 Filter Block
- ⚙️ Limit Block

**Files:**
- `viz-app/src/components/query/VisualBlockBuilder.tsx` (new)
- `viz-app/src/components/query/blocks/` (new directory)
- `viz-app/src/lib/block-compiler.ts` (AST → openCypher)
- `src/api/routes/queries.py` (add visual_query endpoint)

**Dependencies:**
```json
{
  "react-flow-renderer": "^10.3.17"
  // OR
  "react-dnd": "^16.0.1",
  "react-dnd-html5-backend": "^16.0.1"
}
```

**Time Estimate:** 1-2 weeks

---

### Phase 5: Advanced Features
**Goal:** Polish and power-user features

- [ ] Path finding block
- [ ] Pattern matching block
- [ ] Query templates/presets
- [ ] Save/load queries
- [ ] Query history with replay
- [ ] Collaborative query sharing

**Time Estimate:** Ongoing

---

## Educational Design Pattern: "Rosetta Stone" Learning

A key design goal is **teaching Apache AGE openCypher through example**, not documentation.

### The Learning Progression

```
Week 1: Blocks Only
User: "I want to find concepts about organizational change"
Action: Drag 🔍 Search block, type "organizational change"
Result: Gets results without knowing Cypher exists

Week 2: Curiosity
User: "I wonder what this looks like in code?"
Action: Click [</> Code] tab
Sees: MATCH (c:Concept) WHERE c.label CONTAINS 'organizational change' RETURN c
Learning: "Oh, that's how you search in graph databases"

Week 3: Pattern Recognition
User builds: 🔍 Search → 🌐 Neighborhood → 📊 Filter
Switches to Code tab, sees:
  MATCH (c:Concept) WHERE c.label CONTAINS 'x'
  MATCH (c)-[*1..2]-(neighbor:Concept)
  WHERE neighbor.ontology = 'TBM Model'
  RETURN neighbor
Learning: "So -[*1..2]- means 'within 2 hops', got it"

Week 4: First Edit
User: "I bet I can change that 2 to a 3"
Action: Edits in Code tab, changes [*1..2] to [*1..3]
Result: Query works! Confidence++

Month 2: Graduation
User: "I can write this faster in Code than dragging blocks"
Action: Switches to Code tab by default
Outcome: Self-sufficient with Apache AGE openCypher
```

### Why This Works

**Traditional Documentation:**
```
Read 50-page manual → Try to remember syntax → Google errors → Give up
```

**Rosetta Stone Approach:**
```
Build visually → See code → Recognize patterns → Edit confidently → Master syntax
```

**Key Principles:**
1. **Immediate feedback** - See code for every block action
2. **Safe experimentation** - Can switch back to blocks if code breaks
3. **Progressive complexity** - Start simple, add features gradually
4. **Pattern recognition** - Similar blocks → similar code patterns
5. **No dead ends** - Advanced users aren't forced to use blocks

### Example Learning Moments

**Learning: Variable-length paths**
```
Drag: 🌐 Neighborhood [2 hops]
See:  MATCH (c)-[*1..2]-(neighbor:Concept)
Aha:  "Square brackets with numbers = path length!"
```

**Learning: Relationship types**
```
Drag: 📊 Filter [Only IMPLIES relationships]
See:  MATCH (c)-[:IMPLIES]-(neighbor:Concept)
Aha:  "[:TYPE] filters the relationship!"
```

**Learning: WHERE clauses**
```
Drag: 🔍 Search [organizational] + 📊 Filter [TBM Model ontology]
See:  WHERE c.label CONTAINS 'organizational' AND c.ontology = 'TBM Model'
Aha:  "WHERE combines multiple conditions with AND!"
```

**Learning: Pattern chaining**
```
Drag: 🔍 Search → 🔗 Path to → 🔍 Another Search
See:  MATCH (a:Concept) WHERE a.label = 'ethics'
      MATCH (b:Concept) WHERE b.label = 'regulation'
      MATCH path = shortestPath((a)-[*]-(b))
Aha:  "You can match multiple patterns and connect them!"
```

### Validation: Real-World Analogy

This is how many developers learned SQL:
1. Used query builder in Access/phpMyAdmin
2. Clicked "View SQL" button
3. Saw `SELECT * FROM users WHERE age > 18`
4. Thought "Oh, that makes sense"
5. Eventually wrote SQL by hand

Same pattern, applied to graph queries.

### Success Metrics

- **Time to first raw query** - How long before users write openCypher without blocks?
- **Query complexity progression** - Simple blocks → Complex blocks → Hand-written queries
- **Error rate** - Users who learned via blocks should make fewer syntax errors
- **Retention** - Users stay engaged because learning curve is gradual, not cliff

### Documentation Strategy

**Don't write:**
```
"To find concepts within 2 hops, use this syntax:
MATCH (c)-[*1..2]-(neighbor:Concept)
WHERE the pattern matches variable-length paths..."
```

**Instead write:**
```
"Try building a Neighborhood block with depth=2,
then click the Code tab to see how it works."
```

Let the **generated code be the documentation**.

---

## Consequences

### Positive

- **Explorer independence** - Query system works with any visualization
- **Progressive disclosure** - Users start with Smart Search, advance to Blocks or Cypher
- **Expressiveness** - Visual blocks enable complex queries without syntax knowledge
- **Discoverability** - Blocks teach users what's possible in the graph
- **Power users** - Raw openCypher for advanced queries
- **Better recommendations** - Smart search guides users to results
- **Reusability** - `QueryResult` interface enables new explorers easily
- **🎓 Self-guided learning** - Users learn Apache AGE openCypher syntax by building with blocks, then viewing generated code:
  - Blocks → Code tab creates a "Rosetta Stone" between visual concepts and syntax
  - Reduces learning curve from weeks to hours
  - Builds confidence to eventually write raw queries
  - Teaches openCypher best practices through generated examples
  - Users graduate from blocks → hand-editing → eventually preferring code for complex queries

### Negative

- **Complexity** - Three modes to maintain
- **Implementation time** - Visual blocks are non-trivial
- **Learning curve** - Users must understand block semantics
- **Potential confusion** - Three ways to do the same thing
- **Compilation overhead** - Blocks → openCypher adds abstraction layer

### Neutral

- **API surface expansion** - Three new query endpoints
- **Bundle size** - Monaco Editor adds ~2MB to bundle
- **Custom language maintenance** - openCypher definition needs updates as spec evolves

---

## Alternatives Considered

### Alternative 1: Natural Language Query (LLM-based)

**Example:** "find me concepts related to organizational change within 2 hops"

**Pros:**
- Most intuitive for non-technical users
- No syntax to learn

**Cons:**
- Requires LLM API (cost, latency)
- Non-deterministic results
- Hard to debug failed queries
- Overpromises capability

**Decision:** Not chosen for v1, but could complement visual/cypher modes in future

---

### Alternative 2: Form-based Query Builder

**Example:** Dropdowns and text fields in a traditional form

```
┌─────────────────────────────┐
│ Query Type: [Search    ▼]   │
│ Term: [organizational___]   │
│ Similarity: [60%]           │
│ Limit: [10]                 │
│ [Submit]                    │
└─────────────────────────────┘
```

**Pros:**
- Simpler to implement than blocks
- Familiar UX pattern

**Cons:**
- Less expressive (can't chain queries)
- Doesn't scale to complex patterns
- Not visual/discoverable

**Decision:** Smart Search mode covers this use case

---

### Alternative 3: SQL-like Query Language

**Example:** Custom domain-specific language inspired by SQL

```
FIND concepts
WHERE label CONTAINS 'organizational'
EXPAND 2 hops
FILTER ontology = 'TBM Model'
LIMIT 10
```

**Pros:**
- More familiar than Cypher for some users
- Could be simpler than openCypher

**Cons:**
- Yet another query language to learn
- Doesn't leverage existing openCypher standard
- Abstraction layer over openCypher anyway

**Decision:** Not chosen - openCypher is the standard we already use

---

## References

- ADR-034: Graph Visualization Architecture
- ADR-035: Explorer Methods, Uses, and Capabilities
- ADR-016: Apache AGE Migration (openCypher compatibility notes)
- openCypher Language Reference: https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
- Apache AGE Cypher Documentation: https://age.apache.org/age-manual/master/intro/cypher.html
- ISO/IEC 39075:2024 GQL Standard
- Monaco Editor: https://microsoft.github.io/monaco-editor/
- React Flow: https://reactflow.dev/
- Blockly: https://developers.google.com/blockly

---

## Decision Record

**Approved:** [Pending Review]
**Implementation Start:** [TBD]
**Target Completion:** Phase 1-3: 1-2 weeks, Phase 4: 2-3 weeks

---

## Appendix: Example Block Types

### Search Block

```typescript
interface SearchBlock extends QueryBlock {
  type: 'search';
  params: {
    query: string;           // Search term(s)
    similarity: number;      // 0-1 threshold
    limit: number;           // Max results
    ontology?: string[];     // Filter by ontology
  };
}
```

**Compiles to:**
```cypher
MATCH (c:Concept)
WHERE c.label CONTAINS 'organizational'
  AND c.ontology IN ['TBM Model']
RETURN c
LIMIT 10
```

---

### Path Block

```typescript
interface PathBlock extends QueryBlock {
  type: 'path';
  params: {
    from: string;         // Concept ID or search term
    to: string;           // Concept ID or search term
    maxHops: number;      // Maximum path length
    algorithm: 'shortest' | 'all_simple';
  };
}
```

**Compiles to:**
```cypher
MATCH path = shortestPath((a:Concept)-[*..5]-(b:Concept))
WHERE a.id = '...' AND b.id = '...'
RETURN path
```

---

### Neighborhood Block

```typescript
interface NeighborhoodBlock extends QueryBlock {
  type: 'neighborhood';
  params: {
    depth: number;                           // 1-5 hops
    direction: 'outgoing' | 'incoming' | 'both';
    relationshipFilter?: string[];           // e.g., ['IMPLIES', 'SUPPORTS']
  };
}
```

**Compiles to:**
```cypher
MATCH (c)-[:IMPLIES|SUPPORTS*1..2]-(neighbor:Concept)
RETURN DISTINCT neighbor
```

---

### Filter Block

```typescript
interface FilterBlock extends QueryBlock {
  type: 'filter';
  params: {
    ontology?: string[];
    relationshipTypes?: string[];
    minConfidence?: number;
  };
}
```

**Compiles to:**
```cypher
WHERE neighbor.ontology IN ['TBM Model', 'Research Papers']
```

---

**Last Updated:** 2025-10-17
