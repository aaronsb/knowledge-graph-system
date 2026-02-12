# program

> Auto-generated from MCP tool schema

### program

Compose and execute GraphProgram queries against the knowledge graph (ADR-500).

Use search/connect/related for quick lookups (one concept, one path). Use program when you need the neighborhood of more than 2 concepts, want to combine search with traversal, or are asking an analytical question about graph structure. If you've made 3+ individual tool calls without converging, you should already be here.

Programs are JSON ASTs that compose Cypher queries and API calls using set-algebra operators.
Each statement applies an operator to merge/filter results into a mutable Working Graph (W).

**Actions:**
- "validate": Dry-run validation. Returns errors/warnings without storing.
- "create": Notarize + store. Returns program ID for later execution.
- "get": Retrieve a stored program by ID.
- "list": Search stored programs by name/description. Returns lightweight metadata.
- "execute": Run a program server-side. Pass inline AST (program) or stored ID (program_id).
- "chain": Run multiple programs sequentially. W threads through each — program N's output becomes program N+1's input. Pass a deck array of {program_id} or {program} entries (max 10).

**Program Structure:**
{ version: 1, metadata?: { name, description, author }, statements: [{ op, operation, label? }] }

**Operators** (applied to Working Graph W using result R):
  +  Union: merge R into W (dedup by concept_id / link compound key)
  -  Difference: remove R's nodes from W, cascade dangling links
  &  Intersect: keep only W nodes that appear in R
  ?  Optional: union if R non-empty, silent no-op if empty
  !  Assert: union if R non-empty, abort program if empty

**CypherOp** — run read-only openCypher against the source graph:
  { type: "cypher", query: "MATCH (c:Concept)-[r]->(t:Concept) RETURN c, r, t", limit?: 20 }
  Queries must be read-only (no CREATE/SET/DELETE/MERGE). RETURN nodes and relationships.

**AGE Cypher gotchas** (Apache AGE openCypher differs from Neo4j):
- Filter relationship types with WHERE, not inline: `WHERE type(r) IN ['SUPPORTS', 'CONTRADICTS']` (NOT `[r:SUPPORTS|CONTRADICTS]`)
- Reference working graph concepts: `WHERE c.concept_id IN $W_IDS`
- Always RETURN both nodes and relationships for full path data

**ApiOp** — call internal service functions (no HTTP):
  { type: "api", endpoint: "/search/concepts", params: { query: "...", limit: 10 } }

  Allowed endpoints:
  /search/concepts   — params: query (required), min_similarity?, limit?
  /search/sources    — params: query (required), min_similarity?, limit?
  /concepts/details  — params: concept_id (required)
  /concepts/related  — params: concept_id (required), max_depth?, relationship_types?  [returns nodes + edges in programs]
  /concepts/batch    — params: concept_ids (required, list)
  /vocabulary/status — params: relationship_type?, status_filter?

**Example** — find concepts about "machine learning", add their relationships:
  { version: 1, statements: [
    { op: "+", operation: { type: "api", endpoint: "/search/concepts",
        params: { query: "machine learning", limit: 5 } }, label: "seed" },
    { op: "+", operation: { type: "cypher",
        query: "MATCH (c:Concept)-[r]->(t:Concept) WHERE c.concept_id IN $W_IDS RETURN c, r, t" },
      label: "expand relationships" }
  ]}

Read the program/syntax resource for the complete language reference with more examples.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "validate" (dry run), "create" (notarize + store), "get" (retrieve by ID), "list" (search stored programs), "execute" (run server-side), "chain" (run multiple programs sequentially)
  - Allowed values: `validate`, `create`, `get`, `list`, `execute`, `chain`
- `program` (`object`) - GraphProgram AST (required for validate, create, execute). Must have version:1 and statements array.
- `name` (`string`) - Program name (optional for create)
- `program_id` (`number`) - Program ID (required for get, optional for execute as alternative to inline program)
- `params` (`object`) - Runtime parameter values for execute (optional)
- `search` (`string`) - Search text for list action (matches name and description)
- `limit` (`number`) - Max results for list action (default: 20)
- `deck` (`array`) - Array of program entries for chain action (max 10). Each entry needs program_id or program.

---
