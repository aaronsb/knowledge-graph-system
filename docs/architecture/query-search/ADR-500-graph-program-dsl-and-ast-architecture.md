---
status: Draft
date: 2026-02-03
deciders:
  - aaronsb
  - claude
related:
  - ADR-083
  - ADR-048
  - ADR-066
---

# ADR-500: Graph Program DSL and AST Architecture

## Context

The knowledge graph system has three query authoring surfaces — smart search, block editor, and Cypher editor — that converge on a shared intermediate representation:

```
{ op: '+' | '-', cypher: string }[]
```

Smart search and the Cypher editor already round-trip through this IR (see `feature/unified-smart-search`). But several limitations prevent it from becoming a true program representation:

1. **The operator vocabulary is too narrow.** Only `+` (union) and `-` (difference) exist. Intersection, conditional branching, and assertions have no representation.

2. **Smart blocks are invisible to the IR.** Vector search, source search, epistemic filtering, and enrichment blocks compile to Cypher comment markers (`// Smart Block: ...`). The IR is lossy — you can't reconstruct intent from a comment.

3. **The block editor doesn't participate.** It compiles to a single Cypher string, not to the `{ op, cypher }[]` array. Its 18 block types have no mapping to the IR.

4. **Validation is client-side only.** The block compiler runs in the browser. Invalid programs fail at execution time with opaque Cypher errors. There is no structural validation of whether a program is well-formed before it hits the database.

5. **Programs aren't portable.** The current save format stores either raw `searchParams` or ReactFlow layout (`{ nodes, edges }`). Neither captures the executable program in a form that agents, other clients, or the API can work with.

### What This Is

This is a **domain-specific query composition language** built on openCypher — in the same category as Atlassian's JQL (which wraps Lucene). JQL succeeded for 15+ years by staying scoped: system-provided fields and functions, boolean composition, server-side validation, round-trip between visual builder and text. No user-defined functions, no general computation. It became the most powerful feature in Jira precisely because of those constraints.

The parallel is direct:

| JQL | This System |
|---|---|
| Wraps Lucene | Wraps openCypher + REST API |
| Domain fields (`project`, `status`) | Domain concepts (`ontology`, `grounding_strength`) |
| System functions (`currentUser()`) | Smart blocks (`vectorSearch`, `epistemicFilter`) |
| `AND`, `OR`, `NOT` | `+`, `-`, `&` (set algebra) |
| Basic filter UI ↔ JQL text | Block builder ↔ program text |
| Server-side validation | API-side validation |
| Saved/shared filters | Saved/shared programs |

### Design Constraints (The Boundary)

This is a query composition language, not a general-purpose programming language. The boundary is explicit:

**In scope:**
- Set algebra on query results (`+`, `-`, `&`)
- Conditional branching (if/else, switch — select which query to run based on W state)
- Parameters with substitution (resolved once at execution time, not mutable)
- System-provided operations (blocks are the fixed vocabulary)
- Assertions and optional execution (fail-fast or skip on empty results)

**Out of scope — deliberately and permanently:**
- **No iteration.** A program cannot loop over queries against the graph. Every program is a finite, statically-determinable sequence of operations. Iteration against a live database is an unbounded resource commitment — the executor must always be able to answer "how many operations will this program perform?" before running it.
- **No user-defined abstractions.** No `DEFINE BLOCK`, no macros, no function definitions. Blocks are the fixed vocabulary provided by the system.
- **No mutable variables.** Parameters are substituted once. The block compiler generates internal variables (`c0`, `neighbor1`) but these are compilation artifacts, not user-facing bindings.
- **No recursion.** Programs are DAGs at most, never cycles.

The moment any of these constraints is violated, the system has left the JQL zone and should adopt a real language runtime.

### The Two Graphs

Any program operates across two conceptual graphs:

| Graph | Role |
|-------|------|
| **H** (Source) | The persistent knowledge graph. Immutable during query execution. |
| **W** (Working) | The constructed subgraph. Mutable, ephemeral, exists in client state. |

All operators read from H and/or W, and write to W. This framing clarifies operator semantics: `+` queries H and adds to W; `-` queries H (or W) and removes from W; `&` queries H and intersects with W.

### The Authoring Spectrum

Programs can originate from:

```
Recording ────→ Macro ────→ Refined Program ────→ Reusable Policy
    │              │               │                    │
 raw clicks    linear replay   with branches,       generalized,
 or queries    of exploration  conditionals          parameterized,
                                                    stored as
                                                    artifacts
```

The AST must support all points on this spectrum.

## Decision

### 1. The AST is the Canonical Form

Graph programs are JSON ASTs validated by the API. The AST is the single source of truth — text DSL, block diagrams, and recorded explorations are all serialization formats that compile to it.

```typescript
interface GraphProgram {
  version: 1;
  metadata: ProgramMetadata;
  params?: ParamDeclaration[];
  statements: Statement[];
}

interface ProgramMetadata {
  name?: string;
  description?: string;
  author?: 'human' | 'agent' | 'system';
  created?: string;           // ISO timestamp
}

interface ParamDeclaration {
  name: string;               // e.g. "concept_name"
  type: 'string' | 'number';
  default?: string | number;
}
```

### 2. Statements and Operators

Each statement has an operator and a typed operation:

```typescript
interface Statement {
  op: Operator;
  operation: CypherOp | ApiOp | ConditionalOp;
  label?: string;             // human-readable step description
  block?: BlockAnnotation;    // source block type (for decompilation)
}

type Operator =
  | '+'    // Add: query H, merge results into W
  | '-'    // Subtract: query H (or pattern-match W), remove from W
  | '&'    // Intersect: query H, keep only overlap with current W
  | '?'    // Optional: execute, no-op if empty result (don't fail)
  | '!'    // Assert: execute, fail program if empty result
  ;
```

**Why no iteration operator:** Every program must have a statically-determinable operation count. The executor can compute the maximum number of queries a program will issue before running a single one. This is a resource guarantee — programs are bounded by construction, not by runtime safety checks.

### 3. Operation Types

Operations describe *what* to execute. The executor dispatches on `type`:

```typescript
// Execute a Cypher query against H
interface CypherOp {
  type: 'cypher';
  query: string;              // openCypher statement
  limit?: number;
}

// Call a REST API endpoint (smart blocks)
interface ApiOp {
  type: 'api';
  endpoint: string;           // e.g. '/search/concepts'
  params: Record<string, unknown>;
}

// Conditional branching (select execution path based on W state)
interface ConditionalOp {
  type: 'conditional';
  condition: Condition;
  then: Statement[];          // execute if condition is true
  else?: Statement[];         // execute if condition is false
}
```

### 4. Conditional Branching

Programs can branch based on the current state of W. Conditions inspect W without modifying it:

```typescript
type Condition =
  | { test: 'has_results' }                           // W is non-empty
  | { test: 'empty' }                                 // W is empty
  | { test: 'count_gte'; value: number }              // W has >= N nodes
  | { test: 'count_lte'; value: number }              // W has <= N nodes
  | { test: 'has_ontology'; ontology: string }        // W contains nodes from ontology
  | { test: 'has_relationship'; type: string }        // W contains edges of type
  ;
```

Branching is *selection*, not *computation*. It chooses which queries to run based on what's already in the working graph. Every branch path has a deterministic operation count.

**Example — if/else:** "If the initial search found results, expand the neighborhood. Otherwise, try a broader vector search."

```typescript
{
  op: '+',
  operation: {
    type: 'conditional',
    condition: { test: 'has_results' },
    then: [
      { op: '+', operation: { type: 'cypher', query: 'MATCH (c)-[r*1..2]-(n) ...' } }
    ],
    else: [
      { op: '+', operation: { type: 'api', endpoint: '/search/concepts', params: { min_similarity: 0.5 } } }
    ]
  }
}
```

**Example — switch-like pattern:** Chain conditionals for multi-way branching.

```typescript
// If W has "business" ontology nodes → filter to those
// Else if W has "technical" ontology nodes → filter to those
// Else → keep everything
{ op: '&', operation: { type: 'conditional',
    condition: { test: 'has_ontology', ontology: 'business' },
    then: [{ op: '&', operation: { type: 'cypher', query: '...WHERE ontology = "business"...' } }],
    else: [{ op: '&', operation: { type: 'conditional',
        condition: { test: 'has_ontology', ontology: 'technical' },
        then: [{ op: '&', operation: { type: 'cypher', query: '...WHERE ontology = "technical"...' } }]
    }}]
}}
```

Nested conditionals are permitted (for switch-case patterns) but the validator enforces a maximum nesting depth (default: 3) to prevent deep branching trees.

### 5. Block Annotations (Decompilation Support)

When the block editor compiles to the AST, it annotates each statement with its source block type and parameters. This enables text → blocks round-trip:

```typescript
interface BlockAnnotation {
  blockType: BlockType;       // 'search', 'neighborhood', 'vectorSearch', etc.
  params: Record<string, unknown>;
}
```

A statement with a block annotation can be decompiled back to a visual block. Statements without annotations (hand-written Cypher) render as generic "Cypher" blocks.

### 6. Text DSL (Serialization Format)

The text DSL is a human-readable serialization of the AST. It is authored and read by humans; the canonical form is always the JSON AST.

```cypher
-- Exploration: Organizational Patterns
-- Author: human

@param concept_name: string = "organizational"

-- Step 1: Find matching concepts
-- @block search query="organizational"
+ MATCH (c:Concept)-[r]-(n:Concept)
  WHERE c.label CONTAINS $concept_name
  RETURN c, r, n;

-- Step 2: Add semantically similar concepts
-- @block vectorSearch query="organizational" similarity=0.7 limit=10
+ @api /search/concepts {"query": "$concept_name", "min_similarity": 0.7, "limit": 10};

-- Step 3: Remove weakly grounded results
- MATCH (n:Concept) WHERE n.grounding_strength < 0.2 RETURN n;

-- Step 4: Keep only concepts in both neighborhoods (intersection)
& MATCH (c:Concept)-[:SUPPORTS]->(target:Concept) RETURN c, target;

-- Step 5: Branch on results
? IF has_results THEN {
    + MATCH (c)-[r*1..2]-(n:Concept) RETURN c, r, n;
  } ELSE {
    + @api /search/concepts {"query": "$concept_name", "min_similarity": 0.5};
  };
```

**Syntax rules:**

| Element | Syntax |
|---------|--------|
| Operator prefix | `+`, `-`, `&`, `?`, `!` at start of statement |
| Cypher statement | Standard openCypher, terminated by `;` |
| API call | `@api <endpoint> <json_params>;` |
| Parameter declaration | `@param <name>: <type> = <default>` |
| Conditional | `IF <condition> THEN { ... } ELSE { ... };` |
| Block annotation | `-- @block <type> <key>=<value>...` (comment) |
| Metadata | `-- Key: value` header lines |
| Comments | `--` lines without `@` prefix |
| Default operator | Bare Cypher (no prefix) treated as `+` |

### 7. API-Side Validation

The API validates program ASTs before execution. Validation checks:

- **Structural**: Required fields present, operator is valid, operation type is known
- **Boundedness**: Total operation count is statically computable and within limits (default: 100). Conditional branches contribute their longer path to the count.
- **Cypher safety**: Statements pass through the query facade safety checks (ADR-048) — no writes, no unbounded matches without LIMIT
- **Parameter resolution**: All `$param` references resolve to declared parameters or provided values
- **API endpoint allowlist**: `ApiOp` endpoints must be in the permitted set
- **Nesting depth**: Conditional nesting does not exceed maximum (default: 3)

Validation returns structured errors referencing the statement index:

```json
{
  "valid": false,
  "errors": [
    { "statement": 3, "field": "query", "message": "MATCH without LIMIT on unbounded pattern" }
  ]
}
```

### 8. Server-Side Execution

**The executor lives in the API worker, not the client.** Programs are submitted as JSON ASTs and executed entirely server-side. The API returns the resulting W and a step log. Clients are consumers of results, not executors.

```
Client (any)                    API Worker
─────────────                   ──────────

POST /programs/execute ───────→ Validate AST
  { program, params }           Resolve parameters
                                For each statement:
                                  Evaluate conditions against W
                                  Execute CypherOp against H (via AGE)
                                  Execute ApiOp internally (no HTTP round-trip)
                                  Apply operator (+, -, &, ?, !) to W
                           ←─── Return { result: W, log: StepLog[] }
```

This is the central architectural choice. It means:

- **One executor, many clients.** The web app, CLI, MCP server, and AI agents all submit programs to the same endpoint. The set algebra (merge, subtract, intersect) is implemented once in the API worker, not reimplemented per client.
- **Agents execute headless.** An agent can load a saved program, bind parameters, execute it, and receive W — no browser required. Agents can also borrow programs authored by users (or by other agents) from the query definitions store.
- **Smart blocks are internal calls.** `ApiOp` statements don't make HTTP requests back to the API from the client — the executor invokes the underlying service functions directly (vector search, source search, epistemic status). This eliminates N+1 round-trips for programs with multiple smart blocks.
- **W lives server-side during execution.** The working graph is built in memory on the API worker. Only the final result crosses the wire. This is more efficient than the current model where each statement's results travel client → server → client → server.

**Step processing:**

Each statement in the program is processed sequentially:

1. Resolve parameters (`$name` → provided value or default)
2. Evaluate conditionals against current W state (if applicable)
3. Execute the selected operation:
   - `CypherOp`: run against H via the query facade (ADR-048)
   - `ApiOp`: call internal service function directly
4. Map results to `RawGraphData` format
5. Apply the operator to W:
   - `+`: merge results into W (deduplicate by concept_id)
   - `-`: remove matching nodes and their dangling edges from W
   - `&`: intersect — keep only W nodes that appear in results
   - `?`: same as `+`, but empty results are not an error
   - `!`: same as `+`, but empty results abort the program

**Response:**

```typescript
interface ProgramResult {
  result: RawGraphData;         // the final W
  log: StepLogEntry[];          // per-statement execution record
  aborted?: {                   // present if ! (assert) failed
    statement: number;
    reason: string;
  };
}

interface StepLogEntry {
  statement: number;            // index into program.statements
  op: Operator;
  operation_type: string;       // 'cypher' | 'api' | 'conditional'
  branch_taken?: 'then' | 'else';
  nodes_affected: number;
  links_affected: number;
  w_size: { nodes: number; links: number };  // W state after this step
  duration_ms: number;
}
```

The step log enables clients to reconstruct exploration sessions, show step-by-step execution progress, and debug programs. It is also the data structure that would back per-user execution history when stored alongside the program definition.

**Migration from client-side execution:**

The current client-side execution loop (SearchBar's `handleExecuteCypher`, ExplorerView's `handleLoadQuery`) becomes a thin wrapper around `POST /programs/execute`. During transition, both paths can coexist — the client can fall back to local execution for simple single-statement programs while the API handles full programs.

### 9. Mapping Existing Primitives

Every existing block type and exploration action maps to the AST:

| Existing Primitive | AST Mapping |
|---|---|
| `search` block | `+ { type: 'cypher', query: 'MATCH...CONTAINS...' }` |
| `neighborhood` block | `+ { type: 'cypher', query: 'MATCH (c)-[*1..N]-...' }` |
| `filterOntology` block | `& { type: 'cypher', query: 'MATCH...WHERE ontology...' }` |
| `filterEdge` block | `& { type: 'cypher', query: 'MATCH...-[r:TYPE]-...' }` |
| `filterNode` block | `& { type: 'cypher', query: 'MATCH...WHERE confidence...' }` |
| `not` block | `- { type: 'cypher', query: 'MATCH...WHERE pattern...' }` |
| `and` block | `&` operator (intersect two preceding results) |
| `or` block | `+` on second branch (union is additive) |
| `vectorSearch` block | `+ { type: 'api', endpoint: '/search/concepts', params: {...} }` |
| `sourceSearch` block | `+ { type: 'api', endpoint: '/search/sources', params: {...} }` |
| `epistemicFilter` block | `& { type: 'api', endpoint: '/vocabulary/status', params: {...} }` |
| `enrich` block | `+ { type: 'api', endpoint: '/concepts/batch', params: {...} }` |
| `limit` block | `limit` field on the preceding statement's operation |
| `pathTo` block | `+ { type: 'cypher', query: 'MATCH path=...' }` |
| Smart search explore | `+ { type: 'cypher' }` with `block: { blockType: 'neighborhood' }` |
| Context menu follow | `+ { type: 'cypher' }` (recorded as exploration step) |
| Context menu remove | `- { type: 'cypher' }` |

### 10. Storage

Programs are stored as `query_definition` records (ADR-083) with `definition_type: 'program'`:

```json
{
  "definition_type": "program",
  "definition": {
    "version": 1,
    "metadata": { "name": "Organizational Patterns", "author": "human" },
    "statements": [ ... ]
  }
}
```

This sits alongside existing definition types (`exploration`, `block_diagram`, `searchParams`). Migration path: `exploration` definitions are already `{ statements: [{op, cypher}] }` — they gain a `version` field and the operations get `type: 'cypher'` wrappers.

## Consequences

### Positive

- **One executor for all clients.** The web app, CLI, MCP server, and AI agents all use the same `POST /programs/execute` endpoint. Set algebra implemented once, tested once.
- **Headless agent execution.** Agents can author, store, load, and execute programs without a browser. Agents can borrow programs from users or other agents via the query definitions API.
- **No N+1 round-trips.** Smart blocks (vector search, epistemic filter, etc.) are internal function calls during execution, not HTTP requests from the client. A 10-step program with 4 smart blocks is 1 HTTP request, not 11.
- **Static cost guarantees.** The validator computes maximum operation count from the AST before execution. Combined with Cypher safety checks (ADR-048), this means programs can't consume unbounded resources.
- All three authoring surfaces compile to one format — eliminates three separate client-side execution paths
- Smart blocks become first-class IR citizens — programs are no longer lossy
- Block ↔ text ↔ recording round-trip becomes possible via block annotations
- Parameters enable reusable program templates
- The `&` (intersect) operator unblocks the AND/OR blocks that are currently placeholders
- The step log provides per-statement execution history — foundation for per-user execution tracking

### Negative

- Server-side execution means clients can't show incremental W updates during execution (mitigated by the step log and potential streaming in a future phase)
- Migration cost: existing `exploration` and `block_diagram` definitions need adapters
- The block compiler needs a second output path (AST alongside the current Cypher string) during transition
- Intersection (`&`) requires the executor to compare W against query results — more complex than append-only
- Conditional branching adds nesting to the AST — increases validator and executor complexity

### Neutral

- The text DSL is a serialization format, not a standalone language — no parser ecosystem to maintain
- Programs stored as JSON ASTs are machine-readable but less human-scannable than text — both formats coexist
- The `?` and `!` operators are simple wrappers around result-count checks — minimal executor changes
- Block annotations are optional metadata — programs work without them, round-trip is degraded
- Client-side pre-validation is still useful for fast feedback (syntax highlighting, error squiggles) but the API is authoritative

## Alternatives Considered

### A. Extend the current IR minimally (just add `type` field)

Keep `{ op: '+' | '-', type: 'cypher' | 'api', ... }[]` without the full AST wrapper, metadata, parameters, or branching.

Rejected because: This doesn't solve validation, parameterization, or the authoring spectrum. It's an incremental patch that would need to be replaced.

### B. Use Cypher as the canonical form (embed API calls as comments/pragmas)

Keep everything as text Cypher with special comment directives for smart blocks.

Rejected because: Comments are lossy and unparseable by definition. The API can't validate comment-encoded intent. This is what we have today and it's the core problem.

### C. Adopt Datalog or another existing query language

Use a formally-specified language with proven semantics.

Rejected because: The core problem is query *composition*, not query *expression*. Datalog (or SPARQL, GQL, etc.) would be a second query language alongside openCypher, requiring a transpiler to AGE. It also can't represent REST API calls (smart blocks). The system already has a query language — what it needs is an orchestration layer on top of it.

### D. Build a full language with parser, type system, and compiler

Design a standalone DSL with its own grammar, LALR parser, type checker, and compilation stages.

Rejected because: Excessive complexity for the problem size. The JSON AST with a text serialization format achieves the same goals with the language boundary constraints (no iteration, no user-defined abstractions, no mutable variables) preventing scope creep. If requirements eventually exceed these constraints, the AST is the right foundation to build a proper language on top of.

### E. Keep execution client-side (API only validates and runs individual queries)

Clients loop through statements, calling the API for each Cypher/API operation, and manage W in local state (the current architecture).

Rejected because: Every client reimplements set algebra, smart block dispatch, conditional evaluation, and parameter resolution. Agents would need a full client runtime to execute programs. Smart blocks become N+1 HTTP round-trips instead of internal function calls. The execution model can't be audited, rate-limited, or logged centrally. Per-user execution history requires every client to report back.

### F. Validate client-side only (keep API stateless)

Run all validation in the browser, send pre-validated programs to the API.

Rejected because: Agents and non-browser clients need validation too. The API is the trust boundary — programs from any source should be validated at the point of execution. Client-side pre-validation is still useful for fast feedback but is not authoritative.

### F. Allow iteration with safety bounds

Add a `*` (repeat) or `WHILE` operator with maximum iteration counts.

Rejected because: Even bounded iteration makes program cost dependent on graph state rather than program structure. A program with `* MATCH ... LIMIT 100 MAX_ITER 10` could issue anywhere from 1 to 10 queries depending on results. The static boundedness guarantee — knowing the exact maximum operation count from the AST alone — is more valuable than the expressiveness iteration provides. If a use case genuinely needs iterative expansion, it should be implemented as a system-provided smart block (API operation) with its own resource controls, not as a language primitive.

## Implementation Phases

### Phase 1: AST Foundation and API Executor
- Define `GraphProgram` types in a shared schema (used by web, API, CLI, MCP)
- Implement `POST /programs/validate` — structural + safety checks
- Implement `POST /programs/execute` — server-side executor with `CypherOp` and `ApiOp` dispatch, `+`/`-`/`&`/`?`/`!` operators, step log
- Extend `compileBlocksToIR()` to emit AST alongside Cypher string
- Migrate `exploration` definition type to `program` with `version: 1`
- Web client calls execute endpoint instead of local statement loop

### Phase 2: Branching and Parameters
- Conditional branching in executor and validator (`ConditionalOp`, `Condition`)
- Parameter declarations and `$param` substitution
- Nesting depth and operation count enforcement
- MCP / CLI can submit programs with bound parameters

### Phase 3: Round-Trip and Authoring
- Block annotation preservation through serialize/deserialize cycle
- Text → AST parser handles `@block`, `@api`, `@param`, `IF` directives
- AST → Blocks decompiler reconstructs ReactFlow layout
- Full Blocks ↔ Text ↔ Recording interconversion
- Per-user execution history stored alongside program definitions

## References

- `feature/unified-smart-search` — current IR, round-trip between Cypher editor and smart search
- `web/src/utils/cypherGenerator.ts` — current text serializer/deserializer
- `web/src/utils/cypherResultMapper.ts` — AGE result mapping, `RawGraphData` types
- `web/src/lib/blockCompiler.ts` — current block → Cypher compiler
- `web/src/types/blocks.ts` — 18 block type definitions
- `.claude/todo-unified-query-language.md` — prior ideation notes
- ADR-048 — Query safety and GraphQueryFacade
- ADR-083 — Artifact persistence pattern
