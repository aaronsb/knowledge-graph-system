# Explore and Query

Search concepts by meaning, traverse relationships, find paths between ideas, and replay saved explorations — from the CLI, the REST API, MCP, or the web interface.

---

## Authenticate

All query methods require an authenticated session. Run this once; the CLI stores tokens in `~/.config/kg/config.json`.

```bash
kg login        # Opens browser for OAuth
kg config list  # Verify connection and auth status
kg logout       # Clear stored tokens
```

---

## Search by Meaning

`kg search` matches concepts by semantic similarity, not keyword overlap. Specific phrases return more relevant results than single words.

```bash
# Direct shortcut
kg search "climate change effects on agriculture"

# Explicit subcommand — same result, more options
kg search query "climate change effects on agriculture" --limit 20

# Lower the similarity threshold to broaden matches (default 0.7)
kg search query "machine learning" --min-similarity 0.5

# JSON output for scripting
kg search "economic policy" --json
```

Each result reports:

| Field | Meaning |
|---|---|
| Similarity | Match score 0–1 against your query |
| Grounding | Evidence signal: positive = supported, negative = contested |
| Diversity | Breadth of support across related concepts (ADR-063) |
| Evidence | Quoted source passages that produced the concept |

If results look thin, the CLI suggests a lower threshold:

```
💡 3 additional concepts available at 60% threshold
   Try: kg search "climate change" --min-similarity 0.6
```

### Search Source Text

`kg search sources` searches the raw source passages rather than the extracted concepts. Use it to find where in your documents a topic appears.

```bash
kg search sources "unified embedding regeneration"
kg search sources "governance framework" --ontology "policy-docs" --limit 5
```

---

## Get Concept Details

Retrieve all evidence, relationships, and grounding for a specific concept by its ID.

```bash
kg search show <concept-id>        # preferred
kg search details <concept-id>     # alias
```

Output includes every source passage that produced the concept and every outgoing relationship.

---

## Traverse Relationships

### Find Related Concepts

Graph traversal from a starting concept, grouped by hop distance.

```bash
kg search related <concept-id>

# Go deeper
kg search related <concept-id> --depth 3

# Filter by relationship type
kg search related <concept-id> --types SUPPORTS
kg search related <concept-id> --types CONTRADICTS IMPLIES

# Filter by epistemic status (ADR-065)
kg search related <concept-id> --include-epistemic AFFIRMATIVE
kg search related <concept-id> --exclude-epistemic HISTORICAL
```

Depth 1–2 is fast. Depth 3–4 is moderate. Depth 5 is slow on large graphs.

Relationship types available in your graph appear under `kg vocab list`.

### Find Paths Between Concepts

```bash
# By natural language phrase (auto-detected)
kg search connect "inflation" "unemployment"

# By exact concept ID
kg search connect <id1> <id2>

# Limit path length
kg search connect "AI models" "production systems" --max-hops 4

# Lower match threshold for phrase matching (default 0.5)
kg search connect "embedding" "migration" --min-similarity 0.3
```

The CLI auto-detects whether arguments are IDs (containing hyphens or underscores) or phrases. Specific 2–3 word phrases match more reliably than single generic words.

A path result looks like:

```
Path 1 (3 hops):
  Embedding Models
     ↓ REQUIRES
  Model Migration
     ↓ ADDRESSES
  Unified Embedding Regeneration
```

### Explore Contradictions

Concepts with grounding near zero or negative have mixed or opposing evidence.

```bash
# Search for a contested topic, then inspect low-grounding results
kg search "vaccination policy"

# Get details to see both sides
kg search show <concept-id>
```

The evidence section on a contested concept shows which sources support and which contradict.

---

## Ontology Operations

```bash
kg ontology list            # List all ontologies
kg ontology info <name>     # Details and statistics
kg ontology files <name>    # Source documents in an ontology
```

Concepts are global across ontologies — a concept mentioned in two ontologies is the same graph node with evidence from both. Relationship paths cross ontology boundaries automatically.

---

## Saved Queries

A saved query is an ordered list of graph operations. Each operation is tagged `+` (add results to graph) or `-` (remove matching nodes). This lets you sculpt a subgraph by building up and trimming down.

```
+ MATCH (c:Concept)-[r*1..2]-(n:Concept) WHERE c.label CONTAINS 'governance' RETURN c, r, n;
+ MATCH (c:Concept)-[r*1..1]-(n:Concept) WHERE c.label CONTAINS 'compliance' RETURN c, r, n;
- MATCH (c:Concept) WHERE c.label CONTAINS 'legacy' RETURN c;
```

### Create a Saved Query

**From the web interface:** Every search, "Add Adjacent," "Remove," and double-click follow you perform in the 2D/3D graph explorer is recorded as a step. When the graph looks right, open the Saved Queries panel (folder icon in the left rail), click **Save Exploration**, and name it. The full step sequence is stored.

**From the Cypher editor:** Write `+`/`-` prefixed statements directly in the editor, then save via the panel.

**From the Flow Editor:** Build the query visually. Block diagrams compile to Cypher and save as `block_diagram` type.

### Manage Saved Queries from the CLI

```bash
# List all saved queries
kg query-def list
kg qd list                          # alias

# Filter by type
kg qd list --type exploration
kg qd list --type polarity

# Show a specific definition
kg qd show <id>

# Delete
kg qd delete <id>
```

Definition types: `exploration`, `cypher`, `search`, `polarity`, `connection`, `block_diagram`, `program`.

### Load in the Web Interface

Open any explorer view, open the Saved Queries panel, and click a saved query. The system replays each `+`/`-` step in order to reconstruct the graph state. The same saved query loads consistently across views:

| Explorer view | What you see |
|---|---|
| 2D Graph | Force-directed node/edge layout |
| 3D Graph | Spatial perspective of the same graph |
| Cypher Editor | The `+/-` statements as editable text |
| Vocabulary Analysis | Relationship type breakdown of the result |
| Document Explorer | Source documents for the query's concepts |
| Polarity Explorer | Semantic axis analysis of the concepts |
| Embedding Landscape | Embedding space projection of the concepts |

### The +/- Operator Algebra

`+` executes a Cypher statement and merges matching nodes/edges into the current graph; duplicate nodes are deduplicated by ID. `-` executes a Cypher statement and removes matching nodes and their connected edges.

Start broad, then subtract noise — it is easier to remove than to find everything piecemeal:

```
# Start with all governance-adjacent concepts (2 hops)
+ MATCH (c:Concept)-[r*1..2]-(n) WHERE c.label CONTAINS 'governance' RETURN c, r, n;

# Add compliance concepts
+ MATCH (c:Concept)-[r*1..1]-(n) WHERE c.label CONTAINS 'compliance' RETURN c, r, n;

# Remove legacy-system noise
- MATCH (c:Concept) WHERE c.label CONTAINS 'legacy' RETURN c;
```

---

## Web Interface Explorers

Access the web interface at `http://localhost:3000` (or your deployment URL).

### 2D Force Graph

Force-directed layout. Concepts are nodes, relationships are edges. Click a concept to focus its neighborhood; double-click to expand it. Filter by ontology, relationship type, or grounding threshold. Color encodes grounding strength.

Best for: initial exploration, spotting hubs with many connections.

### 3D Force Graph

Same data as the 2D graph with spatial depth. Rotate, pan, and zoom.

Best for: large graphs (1000+ concepts) where 2D clusters overlap.

### Embedding Landscape

t-SNE or UMAP projection of all concept embeddings with automatic DBSCAN cluster detection. Toggle cluster visibility, switch color palettes, right-click any concept to inspect it or open it in the force graph.

Best for: global overview of your semantic space before drilling in.

### Document Explorer

Radial tree centered on a source document. Shows exactly which concepts were extracted and how they connect to the wider graph.

Best for: validating extraction quality, tracing claims to sources.

### Polarity Explorer

Projects concepts onto a semantic spectrum between two poles you define (e.g., "centralized" ↔ "distributed"). Shows where each concept falls and which concepts balance opposing viewpoints.

Best for: understanding conceptual dimensions without predefined categories.

### Vocabulary Analysis

Relationship type breakdown for the current query or neighborhood. Compare subgraph vocabulary to system-wide distribution to understand why concepts cluster.

### Edge Explorer

System-wide view of relationship type usage. Identifies dormant vocabulary — types defined but rarely used — and consolidation opportunities.

Best for: vocabulary health monitoring.

### Flow Editor

Visual query builder. Drag and connect blocks; see compiled Cypher alongside the visual design. Save query templates for reuse.

Best for: building complex queries without writing Cypher by hand.

---

## REST API

Authenticate first. The OAuth flow is documented at [Self-Host > Security and Access](../self-host/security.md). The CLI stores tokens in `~/.config/kg/config.json` after `kg login`; for direct API access, use the device-code or client-credentials grant:

```bash
curl -X POST "http://localhost:8000/auth/oauth/token" \
  -d "grant_type=client_credentials&client_id=...&client_secret=..."
```

### Search Concepts

```bash
curl -X POST "http://localhost:8000/query/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "climate change", "limit": 10, "min_similarity": 0.7}'
```

```json
{
  "results": [
    {
      "concept_id": "abc123",
      "name": "Climate change increases extreme weather",
      "similarity": 0.89,
      "grounding_strength": 0.72,
      "source_count": 5
    }
  ]
}
```

### Get Concept Details

```bash
curl "http://localhost:8000/query/concept/abc123" \
  -H "Authorization: Bearer $TOKEN"
```

### Find Related Concepts

```bash
curl -X POST "http://localhost:8000/query/related" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"concept_id": "abc123", "max_depth": 2}'
```

### Find Paths

```bash
# By concept ID
curl -X POST "http://localhost:8000/query/connect" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_id": "abc123", "to_id": "def456", "max_hops": 5}'

# By phrase
curl -X POST "http://localhost:8000/query/connect-by-search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_query": "inflation", "to_query": "unemployment", "max_hops": 5}'
```

Full endpoint reference: [Reference > REST API](../reference/api.md).

---

## MCP

For AI assistants configured via MCP. See [Get Started > Connect via MCP](../get-started/mcp-quickstart.md) for setup. Once configured, the following tools are available:

| Tool | What it does |
|---|---|
| `search` | Find concepts by semantic similarity |
| `concept` | Get details, find related, find paths |
| `source` | Retrieve original source text |
| `ontology` | List and inspect ontologies |
| `ingest` | Add content during a session |

```
Use search tool with query "sleep deprivation effects on memory"
Use concept tool with action "connect", from_query "inflation", to_query "unemployment"
Use concept tool with action "related", concept_id "abc123"
```

Full tool reference: [Reference > MCP Tools](../reference/mcp.md).

---

## Cross-Ontology Queries

Concepts merge across ontologies automatically when similarity exceeds the matching threshold (~70%). A concept mentioned in both a technical spec and an AI research document becomes one graph node with evidence from both sources. Path traversal crosses ontology boundaries without additional configuration.

Search across all ontologies by default, or narrow to one:

```bash
kg search "embedding regeneration"                         # all ontologies
kg search sources "governance" --ontology "policy-docs"   # one ontology
```

**Ontology organization that supports good linking:**

- Group by domain or project, not by file or date.
- Expect concepts to merge — do not try to keep them separate.
- Write with context. More context in the source text produces better concept extraction and more accurate relationships.
- When bridging two domains in one document, explain the connection in prose; the LLM extracts relationship type from that explanation.

---

## Query Patterns

**Verify a claim:** Search for it, check the grounding score, read the source evidence with `kg search show <id>`.

**Map a topic:** Search for the central concept, run `kg search related <id> --depth 2`, look for clusters and bridges.

**Find disagreements:** Search for a contested topic, look for concepts with grounding near or below zero, inspect both sides with `kg search show`.

**Script a pipeline:** Add `--json` to any `kg search` command for machine-readable output.

**Build a focused subgraph:** Use the `+/-` operator algebra to start broad and subtract noise, then save and share via `kg query-def`.
