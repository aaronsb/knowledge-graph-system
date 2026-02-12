# MCP Server Tool Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from MCP server tool schemas.
> Last updated: 2026-02-12

---

## Overview

The Knowledge Graph MCP server provides tools for Claude Desktop to interact with the knowledge graph.
These tools enable semantic search, concept exploration, and graph traversal directly from Claude.

---

## Available Tools

- [`search`](#search) - Search for concepts, source passages, or documents using semantic similarity. Your ENTRY POINT to the graph.
- [`concept`](#concept) - Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts).
- [`ontology`](#ontology) - Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.
- [`job`](#job) - Manage ingestion jobs: get status, list jobs, approve, cancel, delete, or cleanup. Use action parameter to specify operation.
- [`ingest`](#ingest) - Ingest content into the knowledge graph: submit text, inspect files, ingest files, or ingest directories. Use action parameter to specify operation.
- [`source`](#source) - Retrieve original source content (text or image) for a source node (ADR-057).
- [`epistemic_status`](#epistemic-status) - Vocabulary epistemic status classification (ADR-065 Phase 2). Knowledge validation state for relationship types.
- [`analyze_polarity_axis`](#analyze-polarity-axis) - Analyze bidirectional semantic dimension (polarity axis) between two concept poles (ADR-070).
- [`artifact`](#artifact) - Manage saved artifacts (ADR-083). Artifacts persist computed results like search results, projections, and polarity analyses for later recall.
- [`document`](#document) - Work with documents: list all, show content, or get concepts (ADR-084).
- [`graph`](#graph) - Create, edit, delete, and list concepts and edges in the knowledge graph (ADR-089).
- [`program`](#program) - Compose and execute GraphProgram queries against the knowledge graph (ADR-500).

---

### search

Search for concepts, source passages, or documents using semantic similarity. Your ENTRY POINT to the graph.

CONCEPT SEARCH (type: "concepts", default) - Find concepts by semantic similarity:
- Grounding strength (-1.0 to 1.0): Reliability/contradiction score
- Diversity score: Conceptual richness (% of diverse connections)
- Authenticated diversity: Support vs contradiction indicator (✅✓⚠❌)
- Evidence samples: Quoted text from source documents
- Image indicators: Visual evidence when available
- Document sources: Where concepts originated

SOURCE SEARCH (type: "sources") - Find source text passages directly (ADR-068):
- Searches source document embeddings, not concept embeddings
- Returns matched text chunks with character offsets for highlighting
- Shows concepts extracted from those passages
- Useful for RAG workflows and finding original context

DOCUMENT SEARCH (type: "documents") - Find documents by semantic similarity (ADR-084):
- Searches at document level (aggregates source chunks)
- Returns documents ranked by best matching chunk similarity
- Shows concepts extracted from each document
- Use with document tool for content retrieval

RECOMMENDED WORKFLOW: After search, use concept (action: "connect") to find HOW concepts relate - this reveals narrative flows and cause/effect chains that individual searches cannot show. Connection paths are often more valuable than isolated concepts.

For multi-step exploration, compose searches into a GraphProgram (program tool) instead of making individual calls. One program can seed from search, expand relationships, and filter — all server-side in a single round-trip. Use program (action: "list") to find reusable stored programs, or read the program/syntax resource for composition examples.

ESCALATION: For analytical questions or exploring more than 2 concepts, go directly to the program tool — one composed query replaces many individual calls.

To verify a result, use source to retrieve the original text behind any evidence, or concept (action: "details") to see all evidence and relationships for a concept.

Use 2-3 word phrases (e.g., "linear thinking patterns").

**Parameters:**

- `query` (`string`) **(required)** - Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")
- `type` (`string`) - Search type: "concepts" (default), "sources" (passage search), or "documents" (document-level search)
  - Allowed values: `concepts`, `sources`, `documents`
  - Default: `"concepts"`
- `limit` (`number`) - Maximum number of results to return (default: 10, max: 100)
  - Default: `10`
- `min_similarity` (`number`) - Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)
  - Default: `0.7`
- `offset` (`number`) - Number of results to skip for pagination (default: 0)
  - Default: `0`
- `ontology` (`string`) - Filter by ontology/document name (sources only)

---

### concept

Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts).

For "connect" action, defaults (threshold=0.5, max_hops=5) match the CLI and work well for most queries. Use higher thresholds (0.75+) only if you need to narrow results for precision. Note: connect traverses semantic edges only (IMPLIES, SUPPORTS, CONTRADICTS, etc.) — manually-created edges with no traversal history may not appear in paths. Use program/Cypher for comprehensive traversal.

If connect returns no paths or you need to combine multiple lookups, escalate to the program tool — one composed query replaces many individual calls. Do not repeat connect hoping for different results.

For multi-step workflows (search → connect → expand → filter), compose these into a GraphProgram instead of making individual calls. For example, seed from a search then expand via Cypher using $W_IDS to reference accumulated concept IDs. See the program tool and program/syntax resource for this and other composition patterns.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "details" (get ALL evidence), "related" (explore neighborhood), "connect" (find paths)
  - Allowed values: `details`, `related`, `connect`
- `concept_id` (`string`) - Concept ID (required for details, related)
- `include_grounding` (`boolean`) - Include grounding_strength (default: true)
  - Default: `true`
- `include_diversity` (`boolean`) - Include diversity metrics for details action (default: false, adds ~100-500ms)
  - Default: `false`
- `diversity_max_hops` (`number`) - Max hops for diversity calculation (default: 2)
  - Default: `2`
- `truncate_evidence` (`boolean`) - Truncate evidence full_text context to 200 chars (default: true for token efficiency). Set false for complete context.
  - Default: `true`
- `max_depth` (`number`) - Max traversal depth for related (1-5, default: 2)
  - Default: `2`
- `relationship_types` (`array`) - Filter relationships (e.g., ["SUPPORTS", "CONTRADICTS"]). Constrains traversal, not just results — omit for broadest results, then narrow.
- `include_epistemic_status` (`array`) - Only include relationships with these epistemic statuses (e.g., ["AFFIRMATIVE", "CONTESTED"])
- `exclude_epistemic_status` (`array`) - Exclude relationships with these epistemic statuses (e.g., ["HISTORICAL", "INSUFFICIENT_DATA"])
- `connection_mode` (`string`) - Connection mode: "exact" (IDs) or "semantic" (phrases)
  - Allowed values: `exact`, `semantic`
  - Default: `"semantic"`
- `from_id` (`string`) - Starting concept ID (for exact mode)
- `to_id` (`string`) - Target concept ID (for exact mode)
- `from_query` (`string`) - Starting phrase (for semantic mode, 2-3 words)
- `to_query` (`string`) - Target phrase (for semantic mode, 2-3 words)
- `max_hops` (`number`) - Max path length (default: 5). Higher values find longer paths but take more time.
  - Default: `5`
- `threshold` (`number`) - Similarity threshold for semantic mode (default: 0.5). Lower values find broader matches. The API enforces backend safety limits.
  - Default: `0.5`

---

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "create" (new ontology), "rename" (change name), "delete" (remove), "lifecycle" (set state), "scores" (cached scores), "score" (recompute one), "score_all" (recompute all), "candidates" (top concepts), "affinity" (cross-ontology overlap), "edges" (ontology-to-ontology edges), "reassign" (move sources), "dissolve" (non-destructive demotion), "proposals" (list annealing proposals), "proposal_review" (approve/reject proposal), "annealing_cycle" (trigger annealing cycle)
  - Allowed values: `list`, `info`, `files`, `create`, `rename`, `delete`, `lifecycle`, `scores`, `score`, `score_all`, `candidates`, `affinity`, `edges`, `reassign`, `dissolve`, `proposals`, `proposal_review`, `annealing_cycle`
- `ontology_name` (`string`) - Ontology name (required for info, files, create, rename, delete)
- `description` (`string`) - What this knowledge domain covers (for create action)
- `new_name` (`string`) - New ontology name (required for rename action)
- `lifecycle_state` (`string`) - Target lifecycle state (required for lifecycle action)
  - Allowed values: `active`, `pinned`, `frozen`
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`
- `target_ontology` (`string`) - Target ontology for reassign/dissolve actions
- `source_ids` (`array`) - Source IDs to move (for reassign action)
- `limit` (`number`) - Max results for candidates/affinity (default: 20/10)
- `proposal_id` (`number`) - Proposal ID (for proposal_review action)
- `status` (`string`) - Filter proposals by status, or review status (approved/rejected)
  - Allowed values: `pending`, `approved`, `rejected`, `executing`, `executed`, `failed`
- `proposal_type` (`string`) - Filter proposals by type
  - Allowed values: `promotion`, `demotion`
- `notes` (`string`) - Review notes (for proposal_review action)
- `dry_run` (`boolean`) - Preview candidates without proposals (for annealing_cycle)
  - Default: `false`
- `demotion_threshold` (`number`) - Protection score below which to consider demotion (default: 0.15)
- `promotion_min_degree` (`number`) - Minimum concept degree for promotion candidacy (default: 10)
- `max_proposals` (`number`) - Maximum proposals per annealing cycle (default: 5)

---

### job

Manage ingestion jobs: get status, list jobs, approve, cancel, delete, or cleanup. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job), "delete" (permanently delete single job), "cleanup" (delete jobs matching filters)
  - Allowed values: `status`, `list`, `approve`, `cancel`, `delete`, `cleanup`
- `job_id` (`string`) - Job ID (required for status, approve, cancel, delete)
- `status` (`string`) - Filter by status for list/cleanup (pending, awaiting_approval, running, completed, failed)
- `limit` (`number`) - Max jobs to return for list (default: 50)
  - Default: `50`
- `force` (`boolean`) - Force delete even if job is processing (for delete action)
  - Default: `false`
- `system_only` (`boolean`) - Only delete system/scheduled jobs (for cleanup action)
  - Default: `false`
- `older_than` (`string`) - Delete jobs older than duration: 1h, 24h, 7d, 30d (for cleanup action)
- `job_type` (`string`) - Filter by job type for cleanup (ingestion, epistemic_remeasurement, projection, etc)
- `dry_run` (`boolean`) - Preview what would be deleted without deleting (for cleanup, default: true)
  - Default: `true`
- `confirm` (`boolean`) - Confirm deletion - set to true to actually delete (for cleanup action)
  - Default: `false`

---

### ingest

Ingest content into the knowledge graph: submit text, inspect files, ingest files, or ingest directories. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "text" (raw text), "inspect-file" (validate), "file" (ingest files), "directory" (ingest directory)
  - Allowed values: `text`, `inspect-file`, `file`, `directory`
- `text` (`string`) - Text content to ingest (required for text action)
- `ontology` (`string`) - Ontology name (required for text/file/directory, optional for directory - defaults to dir name)
- `filename` (`string`) - Optional filename for source tracking (text action)
- `processing_mode` (`string`) - Processing mode (text action, default: serial)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Words per chunk (text action, default: 1000)
  - Default: `1000`
- `overlap_words` (`number`) - Overlap between chunks (text action, default: 200)
  - Default: `200`
- `path` (`any`) - File/directory path (required for inspect-file/file/directory). For file action: single path string OR array for batch
- `auto_approve` (`boolean`) - Auto-approve processing (file/directory actions, default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion (file/directory actions, default: false)
  - Default: `false`
- `recursive` (`boolean`) - Process subdirectories recursively (directory action, default: false)
  - Default: `false`
- `limit` (`number`) - Number of files to show per page (directory action, default: 10)
  - Default: `10`
- `offset` (`number`) - Number of files to skip for pagination (directory action, default: 0)
  - Default: `0`

---

### source

Retrieve original source content (text or image) for a source node (ADR-057).

For IMAGE sources: Returns the image for visual verification
For TEXT sources: Returns full_text content with metadata (document, paragraph, offsets)

Use when you need to:
- Verify extracted concepts against original source
- Get the full context of a text passage
- Retrieve images for visual analysis
- Check character offsets for highlighting

Source IDs appear in search results and concept details evidence. Use concept (action: "details") to see all evidence for a concept, or search (type: "sources") to find passages directly.

**Parameters:**

- `source_id` (`string`) **(required)** - Source ID from evidence or search results

---

### epistemic_status

Vocabulary epistemic status classification (ADR-065 Phase 2). Knowledge validation state for relationship types.

Three actions available:
- "list": List all vocabulary types with epistemic status classifications (AFFIRMATIVE/CONTESTED/CONTRADICTORY/HISTORICAL/INSUFFICIENT_DATA/UNCLASSIFIED)
- "show": Get detailed status for a specific relationship type
- "measure": Run measurement to calculate epistemic status for all types (admin operation)

EPISTEMIC STATUS CLASSIFICATIONS:
- AFFIRMATIVE: High avg grounding >0.8 (well-established knowledge)
- CONTESTED: Mixed grounding 0.2-0.8 (debated/mixed validation)
- CONTRADICTORY: Low grounding <-0.5 (contradicted knowledge)
- HISTORICAL: Temporal vocabulary (detected by name)
- INSUFFICIENT_DATA: <3 successful measurements
- UNCLASSIFIED: Doesn't fit known patterns

Use for filtering relationships by epistemic reliability, identifying contested knowledge areas, and curating high-confidence vs exploratory subgraphs.

Concept (action: "related") and connect accept include_epistemic_status/exclude_epistemic_status filters to narrow traversals by reliability. Use search to find concepts in contested areas, then epistemic_status to understand why.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all types), "show" (specific type), "measure" (run measurement)
  - Allowed values: `list`, `show`, `measure`
- `status_filter` (`string`) - Filter by status for list action: AFFIRMATIVE, CONTESTED, CONTRADICTORY, HISTORICAL, INSUFFICIENT_DATA, UNCLASSIFIED
- `relationship_type` (`string`) - Relationship type to show (required for show action, e.g., "IMPLIES", "SUPPORTS")
- `sample_size` (`number`) - Edges to sample per type for measure action (default: 100)
  - Default: `100`
- `store` (`boolean`) - Store results to database for measure action (default: true)
  - Default: `true`
- `verbose` (`boolean`) - Include detailed statistics for measure action (default: false)
  - Default: `false`

---

### analyze_polarity_axis

Analyze bidirectional semantic dimension (polarity axis) between two concept poles (ADR-070).

Projects concepts onto an axis formed by opposing semantic poles (e.g., Modern ↔ Traditional, Centralized ↔ Distributed). Returns:
- Axis quality and magnitude (semantic distinctness)
- Concept positions along the axis (-1 to +1)
- Direction distribution (positive/neutral/negative)
- Grounding correlation patterns
- Statistical analysis of projections

PERFORMANCE: Direct query pattern, ~2-3 seconds execution time.

Use Cases:
- Explore conceptual spectrums and gradients
- Identify position-grounding correlation patterns
- Discover concepts balanced between opposing ideas
- Map semantic dimensions in the knowledge graph

Requires concept IDs for poles — use search to find opposing concepts first. Use concept (action: "details") to inspect pole concepts before analysis.

**Parameters:**

- `positive_pole_id` (`string`) **(required)** - Concept ID for positive pole (e.g., ID for "Modern")
- `negative_pole_id` (`string`) **(required)** - Concept ID for negative pole (e.g., ID for "Traditional")
- `candidate_ids` (`array`) - Specific concept IDs to project onto axis (optional)
- `auto_discover` (`boolean`) - Auto-discover related concepts if candidate_ids not provided (default: true)
  - Default: `true`
- `max_candidates` (`number`) - Maximum candidates for auto-discovery (default: 20, max: 100)
  - Default: `20`
- `max_hops` (`number`) - Maximum graph hops for auto-discovery (1-3, default: 1)
  - Default: `1`

---

### artifact

Manage saved artifacts (ADR-083). Artifacts persist computed results like search results, projections, and polarity analyses for later recall.

Three actions available:
- "list": List artifacts with optional filtering by type, representation, or ontology
- "show": Get artifact metadata by ID (without payload)
- "payload": Get artifact with full payload (for reusing stored analysis)

Use artifacts to:
- Recall previously computed analyses without re-running expensive queries
- Share analysis results across sessions
- Track analysis history with parameters and timestamps
- Check freshness (is_fresh indicates if graph has changed since artifact creation)

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (list artifacts), "show" (metadata only), "payload" (full result)
  - Allowed values: `list`, `show`, `payload`
- `artifact_id` (`number`) - Artifact ID (required for show, payload)
- `artifact_type` (`string`) - Filter by type: search_result, projection, polarity_analysis, query_result, etc.
- `representation` (`string`) - Filter by source: cli, mcp_server, polarity_explorer, embedding_landscape, etc.
- `ontology` (`string`) - Filter by associated ontology name
- `limit` (`number`) - Max artifacts to return for list (default: 20)
  - Default: `20`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`

---

### document

Work with documents: list all, show content, or get concepts (ADR-084).

Three actions available:
- "list": List all documents with optional ontology filter
- "show": Retrieve document content from Garage storage
- "concepts": Get all concepts extracted from a document

Documents are aggregated from source chunks and stored in Garage (S3-compatible storage).
Use search tool with type="documents" to find documents semantically. Use document (action: "concepts") to see what was extracted, then concept (action: "details") or source to drill into specifics.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all documents), "show" (content), "concepts" (extracted concepts)
  - Allowed values: `list`, `show`, `concepts`
- `document_id` (`string`) - Document ID (required for show, concepts). Format: sha256:...
- `include_details` (`boolean`) - Include full concept details (evidence, relationships, grounding) in one call. Default: false for lightweight list.
  - Default: `false`
- `ontology` (`string`) - Filter by ontology name (for list)
- `limit` (`number`) - Max documents to return for list (default: 50)
  - Default: `50`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`

---

### graph

Create, edit, delete, and list concepts and edges in the knowledge graph (ADR-089).

This tool provides deterministic graph editing without going through the LLM ingest pipeline.
Use for manual curation, agent-driven knowledge building, and precise graph manipulation.

**Actions:**
- "create": Create a new concept or edge
- "edit": Update an existing concept or edge
- "delete": Delete a concept or edge
- "list": List concepts or edges with filters

**Entity Types:**
- "concept": Knowledge graph concepts (nodes)
- "edge": Relationships between concepts

**Matching Modes (for create):**
- "auto": Link to existing if match found, create if not (default)
- "force_create": Always create new, even if similar exists
- "match_only": Only link to existing, error if no match

**Semantic Resolution:**
- Use `from_label`/`to_label` to reference concepts by name instead of ID
- Resolution uses vector similarity (75% threshold) to find matching concepts
- Near-misses (60-75%) return "Did you mean?" suggestions with concept IDs

**Examples:**
- Create concept: `{action: "create", entity: "concept", label: "CAP Theorem", ontology: "distributed-systems"}`
- Create edge: `{action: "create", entity: "edge", from_label: "CAP Theorem", to_label: "Partition Tolerance", relationship_type: "REQUIRES"}`
- List concepts: `{action: "list", entity: "concept", ontology: "distributed-systems"}`
- Delete concept: `{action: "delete", entity: "concept", concept_id: "c_abc123"}`

**Queue Mode** (batch multiple operations in one call):
```json
{
  "action": "queue",
  "operations": [
    {"op": "create", "entity": "concept", "label": "A", "ontology": "test"},
    {"op": "create", "entity": "concept", "label": "B", "ontology": "test"},
    {"op": "create", "entity": "edge", "from_label": "A", "to_label": "B", "relationship_type": "IMPLIES"}
  ]
}
```
Queue executes sequentially, continues past errors by default (set continue_on_error=false to stop on first error). Max 20 operations.

**Parameters:**

- `action` (`string`) **(required)** - Operation to perform. Use "queue" to batch multiple operations.
  - Allowed values: `create`, `edit`, `delete`, `list`, `queue`
- `entity` (`string`) - Entity type (required for create/edit/delete/list, not for queue)
  - Allowed values: `concept`, `edge`
- `operations` (`array`) - Array of operations for queue action (max 20). Each has op, entity, and action-specific fields.
- `continue_on_error` (`boolean`) - For queue: continue executing after errors (default: true). Set false to stop on first error.
  - Default: `true`
- `label` (`string`) - Concept label (required for create concept)
- `ontology` (`string`) - Ontology/namespace (required for create concept, optional filter for list)
- `description` (`string`) - Concept description (optional)
- `search_terms` (`array`) - Alternative search terms for the concept
- `matching_mode` (`string`) - How to handle similar existing concepts (default: auto)
  - Allowed values: `auto`, `force_create`, `match_only`
  - Default: `"auto"`
- `from_concept_id` (`string`) - Source concept ID (for edge create/delete)
- `to_concept_id` (`string`) - Target concept ID (for edge create/delete)
- `from_label` (`string`) - Source concept by label (semantic resolution)
- `to_label` (`string`) - Target concept by label (semantic resolution)
- `relationship_type` (`string`) - Edge relationship type (e.g., IMPLIES, SUPPORTS, CONTRADICTS)
- `category` (`string`) - Semantic category of the relationship (default: structural)
  - Allowed values: `logical_truth`, `causal`, `structural`, `temporal`, `comparative`, `functional`, `definitional`
  - Default: `"structural"`
- `confidence` (`number`) - Edge confidence 0.0-1.0 (default: 1.0)
  - Default: `1`
- `concept_id` (`string`) - Concept ID (for edit/delete concept)
- `label_contains` (`string`) - Filter concepts by label substring (for list)
- `creation_method` (`string`) - Filter by creation method (for list)
- `source` (`string`) - Filter edges by source (for list)
- `limit` (`number`) - Max results to return (default: 20)
  - Default: `20`
- `offset` (`number`) - Number to skip for pagination (default: 0)
  - Default: `0`
- `cascade` (`boolean`) - For concept delete: also delete orphaned synthetic sources (default: false)
  - Default: `false`

---

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
