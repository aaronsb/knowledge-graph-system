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
