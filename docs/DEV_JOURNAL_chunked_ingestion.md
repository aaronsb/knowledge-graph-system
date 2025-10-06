# Development Journal: Chunked Ingestion System

**Date**: 2025-10-05
**Status**: Experimental / In Development
**Purpose**: Enable ingestion of large documents without natural paragraph breaks

---

## Overview

Implemented a smart chunking system to process large documents (transcripts, books, continuous text) that don't have clear paragraph boundaries. The system intelligently breaks documents at natural boundaries while maintaining context across chunks through graph awareness.

## The Problem

Original ingestion pipeline (`ingest/ingest.py`) splits on `\n\n` (paragraph breaks):
- ❌ Fails on transcripts with no paragraph structure
- ❌ No position tracking - can't resume if interrupted
- ❌ No context awareness - each paragraph processed independently
- ❌ LLM generates non-unique concept IDs causing collisions

## The Solution

New chunked ingestion system with:
- ✅ Smart boundary detection (sentences, pauses, natural breaks)
- ✅ Character-level checkpointing with resume capability
- ✅ Graph context awareness (queries recent concepts before processing)
- ✅ UUID-based concept IDs (prevents collisions)
- ✅ Real-time progress monitoring with vector search statistics

---

## How It Works

### 1. Smart Chunking (`ingest/chunker.py`)

Finds natural boundaries instead of hard cuts:

```
Target: 1000 words per chunk
Process:
  1. Start at word 1000
  2. Scan forward/backward for:
     - Paragraph break (\n\n) - highest priority
     - Sentence ending (. ! ?) - medium priority
     - Natural pause (... — ;) - low priority
  3. If no boundary within 200 words, hard cut at max (1500)
  4. Include 200-word overlap with next chunk for context
```

**Example**:
```
Chunk 1: words 0-1050   (ended at sentence boundary)
Chunk 2: words 850-1900 (200 word overlap, ended at pause)
Chunk 3: words 1700-2750 (200 word overlap, ended at paragraph)
```

### 2. Position Tracking (`ingest/checkpoint.py`)

Saves progress every N chunks:

```json
{
  "document_name": "Watts Taoism 02",
  "file_path": "/absolute/path/to/file.md",
  "file_hash": "sha256:abc123...",
  "char_position": 45320,
  "chunks_processed": 12,
  "recent_concept_ids": ["id1", "id2", "id3"],
  "timestamp": "2025-10-05T...",
  "stats": {
    "concepts_created": 45,
    "concepts_linked": 23,
    ...
  }
}
```

**Resume logic**:
- Validates file hasn't changed (hash check)
- Starts reading from `char_position`
- Continues chunk numbering from where it left off

### 3. Graph Context Awareness

Before processing each chunk, queries Neo4j for recent concepts:

```python
# Get concepts from last 3 chunks of this document
recent_concepts = neo4j_client.get_document_concepts(
    document_name="Watts Taoism 02",
    recent_chunks_only=3
)

# Pass to LLM for context-aware extraction
extraction = extract_concepts(
    text=chunk.text,
    existing_concepts=recent_concepts  # LLM sees these
)
```

**Result**: LLM is more likely to link new concepts to existing ones instead of creating duplicates.

### 4. Vector Search Deduplication

Every extracted concept is checked against the graph:

```python
# LLM extracts: "Value of the Useless Life"
embedding = generate_embedding("Value of the Useless Life")

# Search for similar concepts
matches = neo4j_client.vector_search(
    embedding=embedding,
    threshold=0.85  # 85% similarity required
)

if matches:
    # Found "Value of Uselessness" at 94% similarity
    # → Link to existing concept
else:
    # No match → Create new concept
```

### 5. Real-Time Progress Monitoring

Each chunk shows vector search performance:

```
📈 VECTOR SEARCH PERFORMANCE:
  New concepts (miss):       3 ( 50.0%)
  Matched existing (hit):    3 ( 50.0%)
  Trend: 🔗 Connecting ideas - balanced creation and linking
```

**Trends**:
- 🌱 0% hits: Building foundation (early chunks)
- 📚 <20% hits: Early growth phase
- 🔗 20-50% hits: Balanced linking and creation
- 🕸️ 50-80% hits: Maturing graph
- ✨ >80% hits: Dense, highly interconnected

---

## Usage Examples

### Basic Ingestion

```bash
# Using wrapper script (recommended)
./scripts/ingest-chunked.sh \
  "ingest_source/Alan Watts - Taoism - 02 - Wisdom of the Ridiculous.md" \
  --name "Watts Taoism 02"

# Direct Python invocation
python -m ingest.ingest_chunked \
  "path/to/document.txt" \
  --document-name "Document Name"
```

### Custom Chunking Parameters

```bash
# Smaller chunks (faster processing, more checkpoints)
./scripts/ingest-chunked.sh "document.txt" \
  --name "Doc" \
  --target-words 500 \
  --max-words 700 \
  --checkpoint-interval 2

# Larger chunks (fewer API calls, less overlap)
./scripts/ingest-chunked.sh "document.txt" \
  --name "Doc" \
  --target-words 2000 \
  --max-words 2500 \
  --overlap-words 300
```

### Resume After Interruption

```bash
# Interrupt with Ctrl+C during ingestion
# Resume from last checkpoint:
./scripts/ingest-chunked.sh "document.txt" \
  --name "Doc" \
  --resume
```

### Clean Reset

```bash
# Reset database and clear checkpoints/logs
./scripts/reset.sh

# Verify clean state
python cli.py stats  # Should show 0 nodes
```

---

## Querying the Knowledge Graph

### 1. Semantic Search (Vector Similarity)

```bash
# Search finds concepts by MEANING, not keywords
python cli.py search "foolishness wisdom" --limit 5

# Results:
#   1. Fool as Sage (81.4% similarity)
#   2. Daoist Sage (67.8%)
#   3. Value of Uselessness (67.6%)

# Even though "foolishness wisdom" doesn't appear in any label!
```

### 2. Concept Details with Evidence

```bash
# Get full details and quotes
python cli.py details watts_taoism_02_chunk1_82207f75

# Shows:
#   - Concept label
#   - Search terms (aliases)
#   - Evidence quotes from source
#   - Relationships to other concepts
```

### 3. Graph Traversal

```bash
# Find related concepts (depth 2 hops)
python cli.py related watts_taoism_02_chunk1_82207f75 --depth 2

# Shows concept network expanding outward
```

### 4. Direct Cypher Queries

```bash
# Most powerful - query Neo4j directly
docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "
  MATCH (c:Concept)-[r]->(c2:Concept)
  WHERE r.confidence > 0.8
  RETURN c.label, type(r), c2.label, r.confidence
  ORDER BY r.confidence DESC
  LIMIT 10
" --format plain
```

**Example queries to try**:

```cypher
// Find concepts with most evidence
MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
RETURN c.label, count(i) as evidence_count
ORDER BY evidence_count DESC
LIMIT 10

// Show concept relationships
MATCH (c1:Concept)-[r]->(c2:Concept)
RETURN c1.label, type(r), c2.label, r.confidence
ORDER BY r.confidence DESC

// Find contradictory concepts
MATCH (c1:Concept)-[r:CONTRADICTS]->(c2:Concept)
RETURN c1.label, c2.label, r.confidence

// Concepts appearing in multiple chunks
MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
WITH c, count(DISTINCT s) as chunk_count
WHERE chunk_count > 1
RETURN c.label, chunk_count
ORDER BY chunk_count DESC
```

### 5. Neo4j Browser (Visual)

Open http://localhost:7474
- Username: `neo4j`
- Password: `password`

Try visualizing:
```cypher
// Show all concepts and relationships
MATCH (c:Concept)-[r]->(c2:Concept)
RETURN c, r, c2
LIMIT 50
```

---

## How Embeddings Enable Semantic Search

### The Magic of Vector Similarity

When you search "foolishness wisdom":

1. **Query → Embedding**
   ```
   Text: "foolishness wisdom"
   OpenAI API → Vector: [0.15, -0.23, 0.87, 0.45, ..., 0.12]
                        (1536 dimensions)
   ```

2. **Vector Search in Neo4j**
   ```cypher
   CALL db.index.vector.queryNodes(
     'concept-embeddings',
     10,                    // limit
     $search_embedding      // your query vector
   )
   YIELD node, score
   WHERE score >= 0.65      // similarity threshold
   ```

3. **Results Ranked by Similarity**
   ```
   Concept              | Cosine Similarity | Why It Matched
   ---------------------|-------------------|------------------
   Fool as Sage         | 0.814            | Captures the paradox
   Daoist Sage          | 0.678            | Related philosophy
   Value of Uselessness | 0.676            | Thematic connection
   ```

### Real Examples from Your Data

**Alternate spellings/names**:
```bash
python cli.py search "Chuang Tzu"
# → Finds "Zhuangzi" (83.4% similar)
# Different romanization, same person!
```

**Synonyms**:
```bash
python cli.py search "purposeless"
# → Finds "Value of Uselessness" (high similarity)
# Different words, same concept!
```

**Conceptual relationships**:
```bash
python cli.py search "freedom from purpose"
# → Finds "Wu Wei", "Present Moment and Dao"
# Thematically related concepts!
```

### Deduplication in Action

During ingestion, you saw:
```
Chunk 1: Created "Value of Uselessness"
Chunk 5: LLM extracts "Uselessness"
         → Vector search: 94% match to "Value of Uselessness"
         → LINKED instead of creating duplicate
```

**Without embeddings**: Would create both concepts separately
**With embeddings**: Automatically detects they're the same thing

---

## Experimentation Ideas

### 1. Test Different Chunk Sizes

```bash
# Very small chunks (high granularity)
--target-words 300 --max-words 400

# Very large chunks (broader context)
--target-words 2000 --max-words 2500
```

**Question**: Does chunk size affect concept quality or relationship detection?

### 2. Adjust Similarity Thresholds

Edit `ingest/ingest_chunked.py` line ~165:
```python
matches = neo4j_client.vector_search(
    embedding=embedding,
    threshold=0.85  # Try: 0.75, 0.80, 0.90, 0.95
)
```

**Question**: What threshold gives best deduplication vs. false positives?

### 3. Multi-Document Concept Linking

```bash
# Ingest multiple related documents
./scripts/ingest-chunked.sh "watts_lecture_1.txt" --name "Watts 01"
./scripts/ingest-chunked.sh "watts_lecture_2.txt" --name "Watts 02"

# Query cross-document concepts
docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "
  MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
  WITH c, collect(DISTINCT s.document) as docs
  WHERE size(docs) > 1
  RETURN c.label, docs
"
```

**Question**: Do concepts link across documents automatically?

### 4. Semantic Search Experiments

Try searches that wouldn't work with keywords:
```bash
# Abstract concepts
python cli.py search "acceptance of paradox"
python cli.py search "skill without effort"
python cli.py search "being vs doing"

# Cross-cultural terms
python cli.py search "non-action meditation"
python cli.py search "spontaneous naturalness"
```

**Question**: What's the recall quality for abstract/philosophical queries?

### 5. Relationship Quality Analysis

```bash
# Check relationship confidence distribution
docker exec knowledge-graph-neo4j cypher-shell -u neo4j -p password "
  MATCH ()-[r:SUPPORTS|IMPLIES|CONTRADICTS]->()
  RETURN type(r) as rel_type,
         avg(r.confidence) as avg_conf,
         count(*) as count
"
```

**Question**: Are LLM-generated relationships reliable? What confidence threshold is useful?

---

## Known Limitations

### Current Issues

1. **No sentence-level chunking** - Current implementation chunks at word boundaries with boundary detection, but doesn't use sophisticated NLP for perfect sentence segmentation

2. **LLM context window** - Each chunk is processed independently (though with recent concept context). Very long-range connections might be missed.

3. **Embedding API costs** - Every concept generates an embedding (OpenAI API call). Large documents = many concepts = $$$.

4. **No overlap analysis** - Overlapping text between chunks is re-processed. Could extract concepts from overlap and skip embedding generation.

5. **Single-threaded** - Processes one chunk at a time. Could parallelize for speed.

6. **Neo4j warnings on empty DB** - First run shows warnings (now suppressed with friendly message, but still noisy in stderr).

### Potential Improvements

- [ ] Implement proper sentence tokenization (spaCy, NLTK)
- [ ] Add parallel chunk processing
- [ ] Cache embeddings for overlap regions
- [ ] Add incremental updates (re-process only changed chunks)
- [ ] Implement chunk-level provenance (track which chunk created which concept)
- [ ] Add graph visualization export (Mermaid, GraphML)
- [ ] Multi-document comparison queries
- [ ] Concept merging UI (for false negatives in deduplication)

---

## Files Modified/Created

```
ingest/
  ├── chunker.py              # NEW: Smart text chunking
  ├── checkpoint.py           # NEW: Position tracking & resume
  ├── ingest_chunked.py       # NEW: Main chunked ingestion
  └── neo4j_client.py         # MODIFIED: Added get_document_concepts()

scripts/
  ├── ingest-chunked.sh       # NEW: Wrapper script
  └── reset.sh                # MODIFIED: Clear logs/checkpoints, better validation

.checkpoints/                 # NEW: Checkpoint storage (gitignored)
logs/                         # MODIFIED: Now cleared on reset
```

---

## Test Data

**Sample document**: `ingest_source/Alan Watts - Taoism - 02 - Wisdom of the Ridiculous.md`
- Size: 44KB (7,789 words)
- Type: Continuous transcript (no paragraph breaks)
- Chunks generated: ~7-8 (at default 1000 word target)
- Processing time: ~5-10 minutes (depends on LLM API speed)

**Test ingestion**:
```bash
./scripts/reset.sh  # Start clean
./scripts/ingest-chunked.sh \
  "ingest_source/Alan Watts - Taoism - 02 - Wisdom of the Ridiculous.md" \
  --name "Watts Taoism 02"
```

---

## Next Steps for Experimentation

1. **Ingest the full transcript** and analyze:
   - Vector search hit rate progression
   - Concept clustering by chunk
   - Relationship network density

2. **Test resume capability**:
   - Start ingestion
   - Ctrl+C after 3 chunks
   - Resume and verify continuity

3. **Query experiments**:
   - Semantic search for abstract concepts
   - Cross-document concept linking
   - Relationship path finding

4. **Parameter tuning**:
   - Optimal chunk size for this content type
   - Best similarity threshold for deduplication
   - Checkpoint interval vs. risk tolerance

5. **Visualization**:
   - Export to Mermaid diagram
   - Analyze concept clusters
   - Identify central/hub concepts

---

## Questions to Answer

- [ ] What chunk size gives best concept quality?
- [ ] Does overlap help or hurt concept linking?
- [ ] What's the optimal similarity threshold for deduplication?
- [ ] How well does semantic search work for philosophical content?
- [ ] Can we predict relationship types from embedding similarity?
- [ ] Does graph density correlate with source material coherence?
- [ ] What's the false positive rate on concept matching?

---

**Status**: Ready for experimentation
**Next Session**: Run full ingestion, analyze results, tune parameters
