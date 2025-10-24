# 09 - Common Workflows and Use Cases

**Part:** I - Foundations
**Reading Time:** ~18 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 05 - The Extraction Process](05-the-extraction-process.md)

---

This section shows practical patterns for using the knowledge graph system with different types of documents and workflows. Each pattern demonstrates specific techniques for organizing ontologies, managing incremental updates, and querying results.

## Core Patterns

### Single Document Ingestion

The simplest workflow: ingest one document into one ontology.

```bash
kg ingest file my-document.txt --ontology "My Research"
```

The system chunks the document, extracts concepts, creates graph nodes, and returns statistics. You can query immediately.

**Use when:**
- Testing the system
- Processing a standalone document
- Creating a new ontology

### Multi-Document Collection

Related documents benefit from sharing concept space. Ingest multiple documents into the same ontology.

```bash
kg ingest file chapter-1.md --ontology "Book Title"
kg ingest file chapter-2.md --ontology "Book Title"
kg ingest file chapter-3.md --ontology "Book Title"
```

Documents ingested into the same ontology share concepts. If Chapter 1 mentions "distributed authority" and Chapter 3 mentions "distributed authority," the graph links them to the same concept node automatically.

**Directory ingestion:** The `kg` client supports ingesting entire directories at once, so you don't have to process files one-by-one. Use `kg ingest dir ./chapters --ontology "Book Title"` to process all files in a directory.

**How it works:**

The system performs vector similarity matching on every extracted concept. When a new concept has ≥85% similarity to an existing concept, it links to the existing node instead of creating a duplicate. This happens across all documents in the ontology.

**Use when:**
- Book chapters
- Related research papers
- Project documentation set
- Meeting notes from the same project

### Multi-Ontology Organization

Different knowledge domains should live in separate ontologies. This keeps concepts organized and enables targeted querying.

```bash
# Technical domain
kg ingest file python-guide.md --ontology "Python Documentation"
kg ingest file django-tutorial.md --ontology "Python Documentation"

# Business domain
kg ingest file project-plan.md --ontology "Q4 Projects"
kg ingest file status-update.md --ontology "Q4 Projects"
```

Each ontology maintains its own conceptual space. The graph can still link concepts across ontologies if they're similar enough (cross-ontology matching).

**Use when:**
- Organizing different knowledge areas
- Separating client projects
- Distinguishing time periods (Q3 vs Q4)
- Maintaining clear data lineage

---

## Common Use Cases

### Research Paper Collection

You're analyzing multiple papers on a topic and want to find connections, compare approaches, and identify contradictions.

**Workflow:**

```bash
# Create ontology for related papers
kg ingest file graphrag-microsoft.pdf --ontology "GraphRAG Research"
kg ingest file lightrag-paper.pdf --ontology "GraphRAG Research"
kg ingest file hybridrag-paper.pdf --ontology "GraphRAG Research"

# Query for shared concepts
kg search query "retrieval augmented generation"
kg search details retrieval-augmented-generation

# Find what connects two approaches
kg search connect graph-based-rag vector-based-rag
```

**Note on PDFs:** Direct PDF support is not yet implemented. For best results, convert PDFs to rich markdown format using a hybrid OCR/vision model that preserves structure and formatting, then ingest the markdown files. This produces cleaner extraction than raw PDF text parsing.

**What this enables:**

- See which concepts appear across multiple papers
- Find where papers contradict each other (CONTRADICTS relationships)
- Trace how ideas build on each other (SUPPORTS, IMPLIES relationships)
- Discover connections the authors didn't explicitly state

**Tips:**

- Ingest foundational papers first, then newer ones - this helps the graph build context
- Use paper titles or first authors in filenames for clear provenance
- Check concept details to see which papers contributed evidence

### Book Analysis

You want to understand a book's concepts and how they relate across chapters.

**Workflow:**

```bash
# Ingest all chapters into one ontology
for chapter in book-chapters/*.md; do
  kg ingest file "$chapter" --ontology "Book: Team Topologies"
done

# Explore core concepts
kg search query "team cognitive load"
kg search details team-cognitive-load

# Find concepts that span multiple chapters
kg database stats  # Check total concepts
```

**What this enables:**

- Find where key ideas are introduced and reinforced
- See how concepts build on each other
- Track terminology evolution across chapters
- Query the book semantically instead of searching text

**Tips:**

- Name files with chapter numbers (01-intro.md, 02-fundamentals.md) for ordered processing
- Later chapters reuse more concepts as the graph grows - this is expected
- The book's narrative structure appears in relationship chains

### Project Documentation

Your project has architecture docs, API specs, deployment guides, and decision records spread across files. Unify them.

**Workflow:**

```bash
# Ingest all project docs
kg ingest file docs/architecture.md --ontology "Project Alpha"
kg ingest file docs/api-spec.md --ontology "Project Alpha"
kg ingest file docs/deployment.md --ontology "Project Alpha"
kg ingest file docs/adr/*.md --ontology "Project Alpha"

# Find architectural concepts
kg search query "microservices authentication"

# Trace a decision
kg search details api-gateway-pattern
```

**What this enables:**

- Find where components are mentioned across docs
- Trace architectural decisions to implementation details
- Discover implicit dependencies not documented explicitly
- Onboard new team members with semantic search

**Tips:**

- Ingest architecture decision records (ADRs) - they create rich concept connections
- Use consistent terminology across docs for better concept linking
- Query by component names to see all related documentation

### Meeting Notes and Discussion

Capture decisions and context from meetings, then link them to technical documentation.

**Workflow:**

```bash
# Create ontology for project meetings
kg ingest file meetings/2025-10-01-sprint-planning.md --ontology "Project Alpha Meetings"
kg ingest file meetings/2025-10-08-retrospective.md --ontology "Project Alpha Meetings"
kg ingest file meetings/2025-10-15-architecture-review.md --ontology "Project Alpha Meetings"

# Find decisions made about specific topics
kg search query "authentication implementation decision"

# Link meetings to technical docs
kg search connect meeting-decision api-authentication-spec
```

**What this enables:**

- Trace why decisions were made
- Find which meeting discussed a specific topic
- Connect discussions to implementation
- Avoid re-discussing resolved issues

**Tips:**

- Structure meeting notes with clear sections (Decisions, Action Items, Discussion)
- Include dates in filenames for temporal context
- Reference ticket numbers or feature names for linkage to code docs

### Personal Knowledge Management

You take notes from books, articles, courses, and conversations. Build a personal knowledge graph.

**Workflow:**

```bash
# Organize by source type
kg ingest file notes/books/thinking-fast-slow.md --ontology "Books - Psychology"
kg ingest file notes/articles/graph-databases.md --ontology "Articles - Tech"
kg ingest file notes/courses/system-design.md --ontology "Courses"

# Or organize by topic
kg ingest file notes/distributed-systems-1.md --ontology "Distributed Systems"
kg ingest file notes/distributed-systems-2.md --ontology "Distributed Systems"

# Explore connections
kg search query "consensus algorithms"
kg search related consensus-algorithms --max-depth 2
```

**What this enables:**

- Find connections between ideas from different sources
- Rediscover forgotten notes semantically
- Build on past knowledge instead of relearning
- Generate new insights from concept connections

**Tips:**

- Choose ontology organization scheme early (topic-based vs source-based)
- Add metadata headers (author, date, source URL) to notes
- Regularly query your graph to reinforce learning

### Consulting Reports

You produce assessment reports, recommendations, and implementation plans for clients. Keep knowledge organized per engagement.

**Workflow:**

```bash
# Client Alpha engagement
kg ingest file reports/alpha-assessment.md --ontology "Client Alpha"
kg ingest file reports/alpha-recommendations.md --ontology "Client Alpha"
kg ingest file reports/alpha-implementation-plan.md --ontology "Client Alpha"

# Client Beta engagement
kg ingest file reports/beta-assessment.md --ontology "Client Beta"
kg ingest file reports/beta-recommendations.md --ontology "Client Beta"

# Find patterns across clients
kg search query "organizational silos"
# Check which clients this concept appears in
```

**What this enables:**

- Reuse insights across similar client problems
- Find where you recommended similar approaches
- Track which concepts appear frequently in assessments
- Build firm knowledge base from engagement work

**Tips:**

- One ontology per client for clean separation
- Use consistent section headings across reports
- Query cross-ontology to find reusable patterns

---

## Incremental Updates

The graph deduplicates automatically. You can add new documents to existing ontologies without re-processing everything.

**Add new document to existing ontology:**

```bash
# Original ontology
kg ingest file doc1.txt --ontology "Project Docs"

# Later, add another document
kg ingest file doc2.txt --ontology "Project Docs"
```

The new document's concepts link to existing concepts where similarity ≥85%. The graph grows incrementally.

**Deduplicate content:**

If you accidentally try to ingest the same file twice, the system detects duplicates via SHA-256 hashing and returns cached results without reprocessing.

**Force re-ingestion:**

```bash
kg ingest file doc.txt --ontology "My Docs" --force
```

This bypasses deduplication and re-processes the document. Use when you've updated the document content.

---

## Directory-Based Ingestion

For large collections, organize documents in directories and batch ingest.

**Structure:**

```
project_history/
├── commits/
│   ├── a1b2c3d.txt
│   ├── b4c5d6e.txt
│   └── ...
└── pull_requests/
    ├── pr-1.txt
    ├── pr-2.txt
    └── ...
```

**Ingest:**

```bash
# Ingest all commits
kg ingest file project_history/commits/*.txt --ontology "Project Commits"

# Ingest all pull requests
kg ingest file project_history/pull_requests/*.txt --ontology "Project PRs"
```

This creates two ontologies. Concepts mentioned in both commits and PRs link automatically via cross-ontology matching.

---

## Metadata-Rich Documents

Structure documents with metadata headers. The LLM extracts metadata as concepts.

**Example document:**

```markdown
Title: Sprint Retrospective - October 2025
Author: Jane Doe
Date: 2025-10-15
Tags: retrospective, team-dynamics, process-improvement

# Sprint Retrospective

What went well:
- Team collaboration improved with new tooling
...

What to improve:
- Code review turnaround time
...
```

**What gets extracted:**

The LLM sees the metadata and extracts structured concepts:
- "Sprint Retrospective" (document type)
- "Jane Doe" (author, potentially linked to other docs by same author)
- "October 2025" (temporal context)
- Tags as individual concepts

This enables queries like:
- "Find all retrospectives by Jane Doe"
- "What did we discuss about code review?"
- "Show process improvements from Q4 2025"

---

## Querying Across Ontologies

Once you have multiple ontologies, query across them or focus on specific ones.

**Find concept in all ontologies:**

```bash
kg search query "authentication mechanisms"
```

This searches the entire graph. Results show which ontologies contain matching concepts.

**Check concept details to see ontology distribution:**

```bash
kg search details authentication-token-validation
```

The evidence section shows source documents. If sources come from multiple ontologies, the concept spans domains.

**Find concepts unique to one ontology:**

Use openCypher queries:

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WHERE s.document = "Project Alpha"
WITH c, collect(DISTINCT s.document) as ontologies
WHERE size(ontologies) = 1
RETURN c.label
```

**Find concepts shared across ontologies:**

```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, collect(DISTINCT s.document) as ontologies
WHERE size(ontologies) > 1
RETURN c.label, ontologies
```

---

## Cost Management

Ingestion costs depend on document size, graph size, and provider choice.

### Track Costs Per Ingestion

The system logs token usage and estimated cost after each ingestion:

```
Token Usage:
  Extraction:            1,814 tokens
  Embeddings:            42 tokens
  Total:                 1,856 tokens
  Estimated cost:        $0.0113
```

### Cost Growth Patterns

**First document in ontology:**
- Empty graph, minimal context
- Lower token usage per chunk
- Example: 600-chunk document = $10

**Later documents in ontology:**
- Dense graph with existing concepts
- LLM receives more context per chunk
- Higher token usage
- Example: Same 600-chunk document = $12-15

This is expected. The graph becomes more useful as it grows, but costs increase slightly.

### Budget-Friendly Practices

**Use local models for large corpora:**

If you have 500+ documents, switch to Ollama with Qwen models (see Section 08). Zero ongoing costs.

**Adjust chunking for cost control:**

Smaller chunks = less context per LLM call:

```bash
kg ingest file doc.txt --ontology "My Docs" --target-words 800
```

Default is 1000 words. Reducing to 800 decreases token usage by ~20%.

**Monitor costs in real-time:**

Check API logs during ingestion to see token usage trending.

---

## Best Practices

### Ontology Naming

**Good names:**
- Descriptive: "GraphRAG Research 2024"
- Project-based: "Client Alpha - Q4 2025"
- Topic-based: "Taoist Philosophy"
- Collection-based: "Watts Lecture Series"

**Avoid:**
- Generic: "Documents", "Files"
- Date-only: "2025-10-06"
- Single-document scope (use ontologies for collections)

### Document Preparation

**Before ingestion:**

1. **Group related documents** - Decide which documents share conceptual space
2. **Choose descriptive ontology names** - Clear, specific, unique
3. **Consider ingestion order** - Foundational documents first helps build context
4. **Verify file formats** - .txt and .md supported, PDFs converted to text

**Document structure:**

Add metadata headers when possible:

```markdown
Title: Document Title
Author: Author Name
Date: YYYY-MM-DD
Tags: tag1, tag2, tag3

[Content...]
```

The LLM extracts this as structured information.

### During Ingestion

**Monitor these signals:**

- **Hit rate**: Percentage of concepts matched to existing vs created new
  - First chunks: 0-20% (building context)
  - Later chunks: 50-70% (reusing established concepts)
  - Very high (>80%): May indicate redundant content

- **Token usage**: Growing token costs indicate graph context expanding

- **Relationship formation**: Check logs for relationship types being created

**Pause if:**
- Token costs spike unexpectedly (may indicate chunking issues)
- Hit rate stays at 0% (may indicate isolated domain needing separate ontology)
- Many errors appear (format issues, API problems)

### After Ingestion

**Validate results:**

```bash
# Check ontology stats
kg database stats

# Find top concepts by evidence
kg search query "your-domain-term"

# Verify cross-document linking
kg search details shared-concept-id
```

**Review:**
- Are key concepts extracted?
- Do documents link together via shared concepts?
- Are relationship types meaningful?

---

## Troubleshooting Common Issues

### Concepts Not Linking Across Documents

**Problem:** Two documents mention the same thing but create separate concept nodes.

**Causes:**
- Different terminology ("ML model" vs "machine learning model")
- Vector similarity below 85% threshold
- Documents truly discuss different concepts despite similar words

**Solutions:**
- Check if concepts have overlapping search terms
- Review concept details to see similarity scores
- Consider if documents genuinely share conceptual space

### High Token Costs

**Problem:** Ingestion costs more than expected.

**Causes:**
- Large documents with many chunks
- Graph context growing (later chunks see more concepts)
- Dense relationship extraction

**Solutions:**
- Reduce chunk size (--target-words 800 instead of 1000)
- Use local models (Ollama with Qwen) for zero cost
- Verify document is appropriate for ingestion (not raw data dumps)

### Slow Ingestion

**Problem:** Processing takes a long time.

**Causes:**
- Using local models (60s per chunk for Qwen3)
- Large documents
- Network latency to cloud APIs

**Solutions:**
- Use faster providers (GPT-4o: 2s/chunk vs Qwen3: 60s/chunk)
- Run ingestion overnight for large corpora
- Monitor progress via job status commands

### Duplicate Concepts

**Problem:** Similar concepts appear as separate nodes.

**Causes:**
- LLM uses different labels ("User Auth" vs "User Authentication")
- Similarity threshold too conservative

**Possible solutions:**
- Accept some duplication (relationships often connect them anyway)
- Consider merging manually via openCypher UPDATE queries
- Future enhancement: vocabulary management tools

---

## Advanced Patterns

### Cross-Ontology Analysis

Find concepts that appear in multiple knowledge domains:

```bash
# Search across all ontologies
kg search query "consensus mechanisms"

# Check which ontologies contain this concept
kg search details consensus-mechanisms
# Review evidence section for source ontologies
```

### Temporal Analysis

Structure filenames with dates to track concept evolution:

```
notes/
├── 2025-01-distributed-systems.md
├── 2025-06-distributed-systems.md
├── 2025-12-distributed-systems.md
```

Query concepts and check evidence timestamps to see when ideas appeared or changed.

### Provenance Tracking

Use metadata headers to track information sources:

```markdown
Title: Authentication Best Practices
Source: NIST Guidelines
URL: https://...
Date: 2025-10-15
```

The LLM extracts source information as concepts, enabling queries like "find all concepts from NIST guidelines."

---

## What's Next

Now that you understand common workflows, you can:

- **[Section 10 - AI Extraction Configuration](10-ai-extraction-configuration.md)**: Fine-tune extraction behavior
- **[Section 11 - Embedding Models and Vector Search](11-embedding-models-and-vector-search.md)**: How semantic search works
- **[Section 12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)**: Setup local models

For specific workflows:
- **[Section 07 - Real World Example](07-real-world-example-project-history.md)**: GitHub project history analysis
- **Case Studies:** [Section 60](60-case-study-multi-perspective-enrichment.md), [Section 61](61-case-study-github-project-history.md)

For technical details:
- **Ingestion:** [guides/INGESTION.md](guides/INGESTION.md)
- **Queries:** [Section 06](06-querying-your-knowledge-graph.md)

---

← [Previous: Choosing Your AI Provider](08-choosing-your-ai-provider.md) | [Documentation Index](README.md) | [Next: AI Extraction Configuration →](10-ai-extraction-configuration.md)
