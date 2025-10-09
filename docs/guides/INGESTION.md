# Document Ingestion Guide

## Overview

The ingestion system transforms documents into a queryable knowledge graph using LLM-powered concept extraction, smart chunking, and ontology-based organization.

## Basic Ingestion

**Single document:**
```bash
./scripts/ingest.sh path/to/document.txt --name "My Ontology"
```

**Parameters:**
- `--name`: Ontology name (required) - logical grouping for documents
- `--resume`: Resume from checkpoint if interrupted
- `--target-words`: Target words per chunk (default: 1000)
- `--min-words`: Minimum words per chunk (default: 800)
- `--max-words`: Maximum words per chunk (default: 1500)
- `--overlap-words`: Overlap between chunks (default: 200)
- `--checkpoint-interval`: Save checkpoint every N chunks (default: 5)

## Ontology-Based Multi-Document Ingestion

### What is an Ontology?

An **ontology** is a named collection of related documents that share conceptual space. Documents ingested into the same ontology:
- Share concept space - similar concepts automatically merge
- Build on each other's context - later documents benefit from earlier extractions
- Query as unified knowledge - "find all concepts in X ontology"

### Multi-Document Pattern

```bash
# First document creates the ontology
./scripts/ingest.sh reports/project-alpha.md --name "Q4 Projects"

# Additional documents contribute to the same conceptual graph
./scripts/ingest.sh reports/project-beta.md --name "Q4 Projects"
./scripts/ingest.sh reports/project-gamma.md --name "Q4 Projects"
```

**Result:**
- 3 documents in "Q4 Projects" ontology
- Concepts automatically connect across documents
- Unique source tracking per file (no collisions)
- Shared concept space enables cross-document queries

### How It Works

**Source Tracking (Unique per file):**
- `source_id`: `{filename}_chunk{N}` (e.g., `project-alpha_chunk1`)
- `file_path`: Full path to source file
- Checkpoints keyed by filename

**Ontology Grouping (Shared across documents):**
- `Source.document`: Ontology name (e.g., "Q4 Projects")
- Graph context queries use ontology name
- Concepts deduplicate across ontology

**Example:**
```cypher
// Sources from multiple files in same ontology
MATCH (s:Source) WHERE s.document = "Q4 Projects"
RETURN DISTINCT s.file_path

// Returns:
// - /path/to/project-alpha.md
// - /path/to/project-beta.md
// - /path/to/project-gamma.md
```

## Iterative Graph Traversal During Ingestion

The ingestion process uses **iterative graph traversal** - each chunk queries the graph for recent concepts and feeds them to the LLM:

**Chunk 1:**
- Empty graph → LLM works in isolation
- Extracts: 6 concepts (0% hit rate)

**Chunk 2:**
- Queries graph for recent concepts
- LLM sees existing context
- Extracts: 4 concepts (50% hit rate - 2 matched, 2 new)

**Chunk 15:**
- Dense graph with growing context
- LLM sees many related concepts
- Extracts: 8 concepts (62.5% hit rate - 5 matched, 3 new)

This creates a **self-reinforcing feedback loop** where the graph becomes more connected as ingestion progresses.

## Concept Matching and Deduplication

During ingestion, each extracted concept goes through a **vector similarity matching** process to prevent duplicates and link related ideas across documents.

### How Matching Works

**For each concept extracted by the LLM:**

1. **Generate embedding** - Convert `label + search_terms` into a 1536-dimensional vector using OpenAI's `text-embedding-3-small`
2. **Vector search** - Query existing concepts using cosine similarity
3. **Match decision**:
   - **Similarity ≥ 85%** → Link to existing concept (reuse)
   - **Similarity < 85%** → Create new concept node

**Example output during ingestion:**
```
LINKED TO EXISTING (5):
  • 'Patterns of Work' → 'Patterns of Work' (99%)
  • 'Traditional Governance' → 'Traditional Governance Challenges' (89%)
  • 'High Performing Agile Organizations' → 'Hierarchy in Agile Organizations' (86%)
  • 'VUCA Environment' → 'VUCA Environment' (99%)
  • 'The Flow System' → 'Design for Flow' (87%)
```

The percentages shown are **cosine similarity scores** - higher means more semantically similar.

### Why This Matters

**Cross-document concept linking:**
- Documents about similar topics automatically share concepts
- "Agile Governance" in Chapter 1 links to "Agile Governance" in Chapter 5
- Relationships span documents without manual intervention

**Prevents fragmentation:**
- Without vector matching, similar concepts would duplicate
- "distributed authority", "authority distribution", "distributed governance" → single concept
- Graph stays coherent as it grows

**Semantic flexibility:**
- Matches concepts even with different wording
- "Legacy governance frameworks" (89%) → "Traditional governance challenges"
- LLM's synonyms in `search_terms` increase match likelihood

### Cross-Ontology Matching Behavior

**Important:** Vector search is **database-wide**, not scoped to the current ontology being ingested.

When ingesting a document, the system searches for similar concepts across **all ontologies** in the database:

**Example scenario:**
```bash
# Existing ontology in database
./scripts/ingest.sh ml-fundamentals.pdf --name "Machine Learning Basics"
# Creates concepts: "Neural Networks", "Gradient Descent", "Overfitting"

# New ontology ingestion
./scripts/ingest.sh deep-learning-guide.pdf --name "Advanced Deep Learning"
# Encounters concept "Neural Networks" (99% match) → links to existing
# Encounters concept "Transformer Architecture" → creates new
```

**Result:** The "Advanced Deep Learning" ontology **shares** the "Neural Networks" concept with "Machine Learning Basics".

**Why this design?**

1. **Knowledge unification** - Related domains naturally connect
2. **Prevents redundancy** - "risk management", "managing risk", "risk mitigation" → single shared concept
3. **Emergent insights** - Discover unexpected connections across domains
4. **Token efficiency** - Reuse existing embeddings instead of duplicating

**When concepts match across ontologies:**
- Both ontologies reference the same concept node
- Relationships within each ontology remain separate
- Evidence (quotes) track back to original sources
- Queries can filter by ontology or explore cross-domain

**Example: Cross-ontology shared concept**

```
Ontology: "Project Management 101"        Ontology: "Startup Operations"
   ↓                                          ↓
Document: pm-basics.pdf                   Document: ops-handbook.md
   ↓                                          ↓
(:Source)-[:APPEARS_IN]-→ (:Concept {label: "Risk Management"}) ←-[:APPEARS_IN]-(:Source)
                              ↑
                         Shared concept node
                         (86% similarity match during ingestion)
```

Both ontologies contribute evidence to the same "Risk Management" concept, but maintain separate source tracking.

**Isolating ontologies:**

If you want ontologies to remain conceptually separate (no cross-matching):
- Ingest into different Neo4j databases
- Use backup/restore to move between environments
- Future enhancement: scope vector search by ontology (see [Issue #12](https://github.com/aaronsb/knowledge-graph-system/issues/12))

**Trade-offs:**

| Approach | Benefits | Drawbacks |
|----------|----------|-----------|
| **Database-wide matching (current)** | Natural knowledge unification, emergent insights, token efficiency | Unintended concept merging if domains use identical terms differently |
| **Ontology-scoped matching (future)** | Clean separation, no cross-contamination | Duplicate concepts, miss legitimate connections, higher token costs |

**When cross-ontology matching causes issues:**

If a term has **different meanings** in different domains:

Example: "Sprint" in "Agile Software" vs. "Track Athletics"
- Software context: time-boxed iteration
- Athletics context: short-distance race

**Current workaround:** Use more specific concept labels and search terms during extraction to prevent false matches.

### Tuning the Threshold

The **0.85 threshold** balances precision vs. recall:

- **Higher (0.90+)**: More new concepts created, less aggressive merging
- **Lower (0.75-0.80)**: More reuse, risk of false matches
- **Current (0.85)**: Sweet spot for most ontologies

**When you might see different match rates:**
- **Domain-specific terminology**: Narrow domains → higher reuse (70-80%)
- **Diverse topics**: Broad ontologies → lower reuse (30-50%)
- **Sequential chapters**: Later chapters reuse more as graph grows

### Technical Details

**Embedding generation:**
```python
# Concatenate label and search terms
text = f"{label} {' '.join(search_terms)}"
embedding = openai.embeddings.create(
    model="text-embedding-3-small",
    input=text
).data[0].embedding  # 1536 dimensions
```

**Vector search query:**
```cypher
CALL db.index.vector.queryNodes('concept-embeddings', $limit, $embedding)
YIELD node, score
WHERE score >= 0.85
RETURN node.concept_id, node.label, score
ORDER BY score DESC
```

**Cost:** Embeddings cost ~$0.02 per 1M tokens (negligible compared to extraction)

## Checkpoint & Resume

For large documents, ingestion automatically saves checkpoints:

```bash
# Start ingestion
./scripts/ingest.sh large-document.txt --name "Big Doc"

# If interrupted (Ctrl+C), resume with:
./scripts/ingest.sh large-document.txt --name "Big Doc" --resume
```

**Checkpoint behavior:**
- Saved every 5 chunks (configurable with `--checkpoint-interval`)
- Keyed by **filename** (not ontology)
- Stores: position, stats, recent concept IDs
- Auto-deleted on successful completion

## Use Cases

### Case 1: Book Chapters

```bash
# Ingest each chapter into "Book Title" ontology
for chapter in chapters/*.md; do
  ./scripts/ingest.sh "$chapter" --name "Governed Agility"
done
```

**Result:** Unified concept graph spanning entire book with chapter-level provenance.

### Case 2: Research Papers

```bash
# Ingest papers on related topic
./scripts/ingest.sh papers/graphrag-microsoft.pdf --name "GraphRAG Research"
./scripts/ingest.sh papers/lightrag-paper.pdf --name "GraphRAG Research"
./scripts/ingest.sh papers/hybridrag-paper.pdf --name "GraphRAG Research"
```

**Result:** Compare approaches, find shared concepts, identify contradictions.

### Case 3: Project Documentation

```bash
# Multiple documents describe same system
./scripts/ingest.sh docs/architecture.md --name "System Design"
./scripts/ingest.sh docs/api-spec.md --name "System Design"
./scripts/ingest.sh docs/deployment.md --name "System Design"
```

**Result:** Unified knowledge graph of system with cross-references.

### Case 4: Consulting Reports

```bash
# Build ontology from client engagement
./scripts/ingest.sh reports/assessment.md --name "Client Alpha"
./scripts/ingest.sh reports/recommendations.md --name "Client Alpha"
./scripts/ingest.sh reports/implementation-plan.md --name "Client Alpha"
```

**Result:** Query all strategic concepts, find dependencies, trace decisions.

## Token Usage and Cost

Ingestion logs track token usage and estimated cost:

```
============================================================
CHUNKED INGESTION SUMMARY
============================================================
Chunks processed:        17
Source nodes created:    17
Concept nodes created:   63
Concepts linked (reuse): 28
Instance nodes created:  96
Relationships created:   84

Token Usage:
  Extraction:            1,814 tokens
  Embeddings:            42 tokens
  Total:                 1,856 tokens
  Estimated cost:        $0.0113
============================================================
```

**Cost factors:**
- Extraction tokens grow with graph size (more context per chunk)
- Embedding tokens scale with unique concepts
- Later documents in ontology may cost more (richer context)

**Cost configuration:** Edit `.env` to update pricing when API costs change:
```bash
TOKEN_COST_GPT4O=6.25              # GPT-4o average cost per 1M tokens
TOKEN_COST_EMBEDDING_SMALL=0.02    # Embedding cost per 1M tokens
```

## Querying Ontologies

**Find all documents in an ontology:**
```cypher
MATCH (s:Source) WHERE s.document = "My Ontology"
RETURN DISTINCT s.file_path
```

**Find concepts unique to one document:**
```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WHERE s.document = "My Ontology" AND s.file_path CONTAINS "file1"
WITH c, collect(DISTINCT s.file_path) as files
WHERE size(files) = 1
RETURN c.label, files[0]
```

**Find concepts spanning multiple documents:**
```cypher
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WHERE s.document = "My Ontology"
WITH c, collect(DISTINCT s.file_path) as files
WHERE size(files) > 1
RETURN c.label, size(files) as document_count
ORDER BY document_count DESC
```

## Best Practices

### Ontology Naming

**Good ontology names:**
- Descriptive: "GraphRAG Research 2024"
- Project-based: "Client Alpha - Q4 2025"
- Topic-based: "Taoist Philosophy"
- Collection-based: "Watts Lecture Series"

**Avoid:**
- Generic names: "Documents", "Files"
- Date-only: "2025-10-06"
- Single-document scope: use ontologies for collections

### Document Organization

**Before ingestion:**
1. Group related documents by topic/project
2. Choose descriptive ontology name
3. Consider ingestion order (foundational → specific)
4. Verify file formats (.txt, .md supported)

**During ingestion:**
- Monitor token usage and costs
- Check logs for relationship formation
- Watch hit rate progression (indicates context building)

**After ingestion:**
- Query ontology to verify concept coverage
- Check cross-document concept connections
- Review relationship formation

### Scaling Considerations

**Current design optimized for:**
- Curated document sets (10-100 documents)
- High-value procedural knowledge
- Agent-consumable ontologies
- Sequential processing per document

**Not optimized for:**
- Massive corpus (thousands of documents)
- Real-time ingestion
- Uncurated data dumps
- Parallel ingestion of multiple documents

See [Issue #8](https://github.com/aaronsb/knowledge-graph-system/issues/8) for batch processing roadmap.

## Troubleshooting

### "source_id constraint violation"

**Cause:** Attempting to re-ingest the same file into same ontology without clearing checkpoints.

**Solution:**
```bash
# Clear checkpoint for specific file
rm .checkpoints/{filename}.json

# Or reset entire database
./scripts/reset.sh
```

### Checkpoint not resuming

**Cause:** Checkpoint keyed by filename, not ontology.

**Solution:** Ensure you're using the exact same file path when resuming.

### High token costs

**Cause:** Graph context grows with document size - later chunks have more context.

**Solution:**
- Adjust chunking parameters (smaller chunks = less context per call)
- Monitor costs in real-time during ingestion
- Consider which documents are essential vs optional

### Concepts not linking across documents

**Cause:** Vector similarity threshold too high, or documents use different terminology.

**Solution:**
- Check deduplication threshold (default: 0.85 cosine similarity)
- Review `search_terms` in concepts - add synonyms if needed
- Consider if documents truly share conceptual space

## Advanced: Custom Chunking

Adjust chunking for different document types:

**Dense technical documents:**
```bash
./scripts/ingest.sh tech-spec.md --name "My Ontology" \
  --target-words 800 \
  --min-words 600 \
  --max-words 1200
```

**Narrative documents:**
```bash
./scripts/ingest.sh lecture.txt --name "My Ontology" \
  --target-words 1200 \
  --min-words 1000 \
  --max-words 1500 \
  --overlap-words 300
```

**Very large documents:**
```bash
./scripts/ingest.sh huge-doc.txt --name "My Ontology" \
  --checkpoint-interval 3  # Save more frequently
```

## Related Documentation

- [Neo4j Query Examples](NEO4J_QUERIES.md) - Query patterns for ontologies
- [Quick Start Guide](QUICKSTART.md) - Basic setup and first ingestion
- [Technical Assessment](ASSESSMENT.md) - Iterative graph traversal analysis
- [GitHub Issue #8](https://github.com/aaronsb/knowledge-graph-system/issues/8) - Batch processing roadmap
