# Unified Query Language — Block Editor Round-Trip

## Status: Ideation (not started)

## Context

We discovered that all three query modes already compile to the same IR:

```
{ op: '+' | '-', cypher: string }[]
```

Smart search and the Cypher editor now round-trip through this format (see `860d571c`).
The block editor is the remaining mode that doesn't participate in the unified program.

## What the Block Editor Does Today

16 block types in two categories:

**Cypher blocks** (compile to openCypher via `blockCompiler.ts`):
- `start`, `end`, `search`, `neighborhood`, `filterOntology`, `filterEdge`,
  `filterNode`, `and`, `or`, `not`, `limit`

**Smart blocks** (route to REST API at execution time, emit comments in Cypher):
- `vectorSearch`, `sourceSearch`, `epistemicFilter`, `enrich`

**Current compilation**: linear chain of blocks -> single openCypher string.
No intermediate representation. Smart blocks detected at runtime in `handleExecute()`.

**Save format**: Full ReactFlow `{ nodes, edges }` stored as `definition_type: 'block_diagram'`
via query definitions API. This is the visual layout, not the executable program.

## The Gap

The block editor compiles to a **single Cypher string**, not to `{ op, cypher }[]`.
It has no concept of `+/-` set algebra — everything is additive.
Smart blocks are handled as special cases at execution time rather than compile time.

## Design Questions to Resolve

### 1. New Block Types for Subgraph Algebra

The `+/-` operators are graph set operations. In block form:

- **Subgraph Space** block — declares "we're building a subgraph" (replaces implicit `start`)
- **Set Operator** block — `+` (union) or `-` (difference), applied between subgraph sections
- Visually: two parallel chains joined by a set operator block

Question: Is the linear chain still the right model, or do we need DAG support?
The `and`/`or` blocks already have this problem — they're pass-through today because
the compiler doesn't handle DAG traversal.

### 2. Smart Blocks in the IR

Smart blocks call REST APIs, not Cypher. Options:

a) **Extend the IR** with a non-Cypher operation type:
   `{ op: '+', type: 'api', endpoint: '/search/concepts', params: {...} }`
   This breaks the clean `{ op, cypher }` shape but captures full intent.

b) **Keep smart blocks as Cypher comments** (current) and handle at execution time.
   Simple but means the IR is lossy — you can't reconstruct a vector search from its comment.

c) **Compile smart blocks to Cypher wrapper functions** if AGE supports them.
   Unlikely to work given AGE's limited function support.

Recommendation: (a) — the IR should capture intent, not just Cypher. The executor
already dispatches by type. This also means the text format needs to represent
non-Cypher operations (e.g. `+ @vectorSearch "query" similarity=0.7 limit=10`).

### 3. Text Syntax Extensions

Current text format only handles `+/- CYPHER;`. For block round-trip we need:

- **Block annotations**: Which block type generated a statement (for decompilation)
- **API directives**: Smart block operations that aren't Cypher
- **Branching**: `and`/`or`/`not` logic gates (if we solve DAG compilation)

Possible extensions to the text format:
```
-- @block search query="organizational"
+ MATCH (c:Concept) WHERE toLower(c.label) CONTAINS toLower('organizational') RETURN c;

-- @block vectorSearch query="organizational" similarity=0.7 limit=10
+ @api /search/concepts {"query": "organizational", "min_similarity": 0.7, "limit": 10};

-- @block neighborhood depth=2 direction=both
+ MATCH (c:Concept)-[r*1..2]-(n:Concept) WHERE c.label = 'X' RETURN c, r, n;
```

The `@block` comment annotations would let us decompile text back to blocks.
The `@api` prefix would mark non-Cypher operations.

### 4. Block Decompilation (Text -> Blocks)

Previously blocked because "we didn't have an AST to ensure validity."
Now the `{ op, cypher }[]` array IS the AST. With `@block` annotations in the
text format, round-trip becomes:

```
Blocks -> IR -> Text -> (edit) -> Text -> IR -> Blocks
```

Each step is invertible if the annotations are preserved.

### 5. Execution Engine Unification

Currently three separate execution paths:
- Smart search: `useSubgraph` / `useFindConnection` hooks
- Block editor: `handleExecute()` with inline smart block detection
- Cypher editor: `handleExecuteCypher()` with `parseCypherStatements`

Could be unified into a single executor that takes `{ op, cypher | api }[]`
and dispatches each operation through the rawGraphData pipeline.

## Implementation Sketch

### Phase 1: Block -> IR compilation (adds IR layer, doesn't change execution)
- New `compileBlocksToIR()` in `blockCompiler.ts`
- Returns `{ op, cypher?, apiCall? }[]` alongside existing Cypher string
- Block editor save format gains optional `compiledStatements` field
- "Send to Editor" sends the `+/-` text format (with `@block` annotations)

### Phase 2: Unified executor
- Single `executeQueryProgram(statements)` function
- Handles both Cypher and API operations
- Records exploration steps for each
- Used by all three modes

### Phase 3: Block decompilation
- Parse `@block` annotations from text
- Reconstruct ReactFlow nodes/edges from annotated IR
- Enable Cypher editor -> Block editor round-trip

## Files Involved

- `web/src/lib/blockCompiler.ts` — add IR compilation layer
- `web/src/components/blocks/BlockBuilder.tsx` — use IR in execute/export
- `web/src/store/blockDiagramStore.ts` — cache compiled IR in save format
- `web/src/utils/cypherGenerator.ts` — extend text format for `@block`/`@api`
- `web/src/types/blocks.ts` — IR type definitions
- `web/src/store/graphStore.ts` — unified executor (Phase 2)

## References

- `860d571c` — unified query program commit (Cypher editor round-trip)
- `web/src/utils/cypherGenerator.ts` — current serializer/deserializer
- `web/src/utils/cypherResultMapper.ts` — AGE ID mapping utility
- `web/src/lib/blockCompiler.ts` — current block -> Cypher compiler
