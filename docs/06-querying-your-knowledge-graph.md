# 06 - Querying Your Knowledge Graph

**Part:** I - Foundations
**Reading Time:** ~15 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md)

---

This section explains how to query your knowledge graph using the `kg` CLI and explores the different ways to find and explore concepts.

## The kg CLI

The `kg` command-line tool provides access to all query capabilities. It communicates with the API server which queries the Apache AGE graph database.

**Basic command structure:**

```bash
kg <command> <subcommand> [options] [arguments]
```

**Check connectivity:**

```bash
kg health
```

This returns API server status and version information. If this works, you're ready to query.

---

## Semantic Search

The primary way to find concepts is semantic search: you describe what you're looking for and the system finds similar concepts.

### Basic Search

```bash
kg search query "linear thinking"
```

**What happens:**

1. Your query text is embedded using the configured embedder model (1536 dimensions for OpenAI text-embedding-3-small, or fewer for other models)
2. The system searches all concept embeddings for similarity
3. Results ranked by cosine similarity (0.0-1.0)
4. Concepts above the threshold (default 0.7) are returned

**Example output:**

```
Found 5 concepts:

1. Linear Thinking Pattern (similarity: 0.94)
   ID: linear-thinking-pattern
   Documents: Alan Watts - Tao of Philosophy - 01
   Evidence: 3 instances

2. Sequential Processing (similarity: 0.89)
   ID: sequential-processing
   Documents: Cognitive Science Paper, Alan Watts Lecture
   Evidence: 5 instances

3. Ordered Reasoning (similarity: 0.82)
   ID: ordered-reasoning
   Documents: Logic Textbook
   Evidence: 2 instances

4. Spotlight Attention Model (similarity: 0.78)
   ID: spotlight-attention-model
   Documents: Alan Watts - Tao of Philosophy - 01
   Evidence: 4 instances

5. Reductionist Thinking (similarity: 0.74)
   ID: reductionist-thinking
   Documents: Systems Thinking Book
   Evidence: 3 instances
```

The similarity score indicates how closely each concept matches your query. Scores above 0.90 are very strong matches. Scores 0.70-0.90 are relevant but less direct. Below 0.70 may not be useful.

### Limit Results

```bash
kg search query "authentication" --limit 5
```

Returns only the top 5 matches. Default limit is 10.

### Adjust Threshold

```bash
kg search query "microservices" --min-similarity 0.8
```

Only returns concepts with similarity ≥ 0.8. Higher thresholds give more precise results but may miss relevant concepts.

**When to adjust:**

- **Raise to 0.8-0.9**: Precise technical searches where you want exact matches
- **Lower to 0.5-0.6**: Exploratory searches where you're casting a wider net
- **Default 0.7**: Works well for most queries

### Multi-Word Queries

```bash
kg search query "how does authentication work in microservices"
```

The system embeds the entire query as one semantic unit. Longer queries can be more specific but aren't always better - sometimes simple queries work best.

**Good queries:**

- "error handling patterns"
- "causal relationships"
- "authentication mechanisms"

**Less effective queries:**

- "what is the relationship between X and Y" (too meta)
- "show me everything about architecture" (too broad)
- Single common words like "the" or "is" (no semantic content)

---

## Viewing Concept Details

Once you find a concept, get its full details:

```bash
kg search details linear-thinking-pattern
```

**Returns:**

```
Concept: Linear Thinking Pattern
ID: linear-thinking-pattern

Search Terms:
  - linear thinking
  - sequential processing
  - ordered reasoning

Relationships:
  IMPLIES → Pattern Recognition (confidence: 0.89)
  CONTRADICTS → Parallel Processing (confidence: 0.82)
  PART_OF → Cognitive Frameworks (confidence: 0.87)
  EXEMPLIFIES → Human Intelligence Limitation (confidence: 0.92)

Evidence (3 instances):

  1. "The sequential processing of information through linear stages represents
      a fundamental limitation of conscious attention."
     Source: Cognitive Science Paper, paragraph 7

  2. "Linear thinking follows a step-by-step progression from premises to
      conclusions."
     Source: Systems Thinking Book, paragraph 12

  3. "it is a scanning system, of conscious attention, which is linear"
     Source: Alan Watts - Tao of Philosophy - 01, paragraph 4
```

This shows:
- **Search terms**: Alternative phrases for matching
- **Relationships**: Typed connections to other concepts with confidence scores
- **Evidence**: Exact quotes supporting this concept with source references

You can verify every claim by reading the evidence quotes in their original context.

---

## Finding Related Concepts

Explore concepts connected to a starting concept:

```bash
kg search related linear-thinking-pattern
```

This traverses the graph from the starting concept, following relationships outward.

**Options:**

```bash
kg search related linear-thinking-pattern \
  --max-depth 2 \
  --relationship-types IMPLIES,SUPPORTS
```

- `--max-depth`: How many relationship hops to follow (default: 2, max: 5)
- `--relationship-types`: Filter to specific types (comma-separated)

**Example output:**

```
Related concepts (within 2 hops):

Direct connections (1 hop):
  - Pattern Recognition (IMPLIES, confidence: 0.89)
  - Parallel Processing (CONTRADICTS, confidence: 0.82)
  - Cognitive Frameworks (PART_OF, confidence: 0.87)

Second-degree connections (2 hops):
  - Neural Networks (via Pattern Recognition → ENABLES)
  - Distributed Systems (via Parallel Processing → EXEMPLIFIES)
  - Information Theory (via Cognitive Frameworks → SUPPORTS)
```

This helps discover non-obvious connections. "Linear Thinking" connects to "Neural Networks" through "Pattern Recognition."

---

## Finding Paths Between Concepts

Discover how two concepts connect:

```bash
kg search connect linear-thinking "distributed systems"
```

**Note:** The system supports both exact ID matching and phrase-based matching (searching by natural language phrases instead of exact concept IDs) via the MCP `find_connection_by_search` tool and REST API `/queries/path-by-search` endpoint.

**Example output:**

```
Path found (3 hops):

  Linear Thinking Pattern
    → [CONTRADICTS] Parallel Processing
    → [EXEMPLIFIES] Distributed Systems

Supporting evidence:
  - "Linear thinking follows sequential steps" (Linear Thinking Pattern)
  - "Parallel processing handles multiple operations simultaneously" (Parallel Processing)
  - "Distributed systems exemplify parallel processing at scale" (Distributed Systems)
```

This shows the chain of relationships connecting two concepts.

---

## Database Statistics

Get overview of your knowledge graph:

```bash
kg database stats
```

**Returns:**

```
Knowledge Graph Statistics:

Nodes:
  Concepts: 1,247
  Sources: 342
  Instances: 3,891

Relationships:
  Concept relationships: 2,134
  APPEARS_IN: 2,458
  EVIDENCED_BY: 3,891
  FROM_SOURCE: 3,891

Ontologies:
  - Alan Watts Lectures (347 concepts)
  - Systems Thinking (289 concepts)
  - Architecture Docs (611 concepts)

Storage:
  Database size: 156 MB
  Avg concepts per source: 3.6
  Avg evidence per concept: 3.1
```

This gives you a high-level view of graph contents.

---

## Ontology Management

List all ontologies (collections):

```bash
kg ontology list
```

**Returns:**

```
Ontologies:

  Alan Watts Lectures
    Concepts: 347
    Sources: 89
    Created: 2025-10-15

  Systems Thinking
    Concepts: 289
    Sources: 67
    Created: 2025-10-18

  Architecture Docs
    Concepts: 611
    Sources: 186
    Created: 2025-10-20
```

Get details for a specific ontology:

```bash
kg ontology info "Alan Watts Lectures"
```

**Returns:**

```
Ontology: Alan Watts Lectures

Statistics:
  Concepts: 347
  Sources: 89
  Evidence instances: 1,203
  Relationships: 478
  Created: 2025-10-15
  Last updated: 2025-10-22

Source files:
  - watts_lecture_1.txt (47 concepts)
  - watts_lecture_2.txt (52 concepts)
  - watts_lecture_3.txt (39 concepts)
  ...

Top concepts (by evidence):
  1. Linear Scanning System (15 instances)
  2. Human Variety (12 instances)
  3. Nature vs Intelligence (11 instances)
  ...
```

---

## Job Management

Check ingestion job status:

```bash
kg job status job_abc123
```

List recent jobs:

```bash
kg job list
```

**Returns:**

```
Recent jobs:

  job_def456  completed   Architecture Docs       2025-10-22  100%
  job_abc123  processing  Systems Thinking        2025-10-22   67%
  job_xyz789  completed   Alan Watts Lectures     2025-10-20  100%
  job_ghi012  failed      Research Papers         2025-10-19  N/A
```

Watch a job in real-time:

```bash
kg job status job_abc123 --watch
```

This polls the job every 2 seconds and displays a progress bar until completion.

---

## Advanced Queries with openCypher

For power users, you can write custom openCypher queries via the API or by connecting directly to PostgreSQL.

### Count Concepts by Ontology

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
RETURN s.document as ontology, count(DISTINCT c) as concept_count
ORDER BY concept_count DESC
```

### Find Cross-Document Concepts

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, collect(DISTINCT s.document) as documents
WHERE size(documents) > 1
RETURN c.label, documents, size(documents) as doc_count
ORDER BY doc_count DESC
LIMIT 10
```

### Trace Evidence Chain

```cypher
MATCH path = (c:Concept {label: "Linear Thinking Pattern"})
             -[:EVIDENCED_BY]->(i:Instance)
             -[:FROM_SOURCE]->(s:Source)
RETURN path
LIMIT 10
```

### Find Highly Connected Concepts

```cypher
MATCH (c:Concept)
WITH c, size((c)-[]-()) as connection_count
WHERE connection_count > 5
RETURN c.label, connection_count
ORDER BY connection_count DESC
LIMIT 10
```

### Relationship Type Distribution

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN type(r) as relationship_type, count(*) as count
ORDER BY count DESC
```

These queries return raw results. For more complex analysis, connect to PostgreSQL with your preferred database client.

---

## Query Tips

**Start broad, narrow down:**

Begin with a general semantic search, then use relationship traversal to explore specific areas.

```bash
# Start broad
kg search query "authentication"

# Pick a concept
kg search details auth-token-validation

# Explore relationships
kg search related auth-token-validation --relationship-types REQUIRES,ENABLES
```

**Use concept IDs, not labels:**

Labels might have spaces or special characters. IDs are always kebab-case and URL-safe.

```bash
# Good
kg search details linear-thinking-pattern

# Works but awkward
kg search details "Linear Thinking Pattern"
```

**Check similarity scores:**

A 0.75 similarity might seem close but could be a different concept. Read the evidence to verify.

**Follow evidence trails:**

When you find a concept, read its evidence quotes. They often contain additional concepts worth exploring.

**Use ontologies to scope searches:**

If you have multiple domains in your graph, filter by ontology:

```bash
kg search query "authentication" --ontology "Architecture Docs"
```

(Note: Ontology filtering in search is planned; currently you can list concepts per ontology with `kg ontology info`)

---

## Common Query Patterns

### Find What Causes X

```bash
# Search for X
kg search query "system failure"

# Get details
kg search details system-failure

# Look for CAUSES relationships pointing TO it
kg search related system-failure --relationship-types CAUSES
```

### Find What X Enables

```bash
kg search details api-rate-limiting
# Look for ENABLES relationships pointing FROM it
```

### Find Contradictions

```bash
kg search query "monolithic architecture"
kg search details monolithic-architecture
# Look for CONTRADICTS relationships
```

### Trace a Concept to Sources

```bash
kg search details requisite-variety
# Read the evidence section to see all source quotes
```

### Find Concepts with Lots of Evidence

```bash
kg database stats
# Shows concepts with most evidence

# Or via openCypher:
# MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
# WITH c, count(i) as evidence_count
# RETURN c.label, evidence_count
# ORDER BY evidence_count DESC
# LIMIT 10
```

---

## Query Limitations

**Semantic search is approximate:** Embeddings capture meaning but aren't perfect. A 0.92 similarity doesn't guarantee the concepts are identical - read the evidence to verify.

**Relationship accuracy depends on extraction:** The LLM identified these relationships during extraction. Some might be incorrect or missing. Confidence scores help identify uncertain relationships.

**Traversal can explode:** Following relationships for 3+ hops can return hundreds of concepts. Use `--max-depth` carefully and filter by relationship type.

**No full-text search yet:** You can't search within evidence quotes directly via kg CLI. This requires openCypher queries or connecting to PostgreSQL.

**Path finding requires exact IDs:** The `kg search connect` command needs exact concept IDs. Phrase-based matching (finding paths between two semantic queries) is planned.

---

## What's Next

Now that you understand querying, you can:

- **[Section 07 - Real World Example](07-real-world-example-project-history.md)**: See queries in action with actual data
- **[Section 14 - Advanced Query Patterns](14-advanced-query-patterns.md)**: Complex openCypher queries and analysis
- **[Section 62 - Query Examples Gallery](62-query-examples-gallery.md)**: Library of useful queries

Or explore specific topics:
- **[Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md)**: Different LLMs for extraction
- **[Section 11 - Embedding Models and Vector Search](11-embedding-models-and-vector-search.md)**: How semantic search works
- **[Section 13 - Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md)**: Customizing relationship types

---

← [Previous: The Extraction Process](05-the-extraction-process.md) | [Documentation Index](README.md) | [Next: Real World Example →](07-real-world-example-project-history.md)
