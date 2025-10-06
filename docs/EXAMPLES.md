# Examples: Real Queries, Real Results

This document shows actual queries run against a knowledge graph containing:
- Alan Watts lectures on Taoism
- A technical paper on AI systems and human variety

All examples use real data from the system.

## Example 1: Semantic Concept Search

**Query:** "uselessness"

**What RAG would do:** Find text chunks containing "useless" or similar words

**What the Knowledge Graph does:**

```bash
$ python cli.py search "uselessness" --limit 3

Found 2 concepts:

1. Value of Uselessness
   ID: watts_taoism_02_chunk1_603de879
   Similarity: 89.5%
   Documents: Watts Taoism 02
   Evidence: 1 instances

2. Ideal Useless Man
   ID: watts_taoism_02_chunk1_22a1d512
   Similarity: 81.3%
   Documents: Watts Taoism 02
   Evidence: 1 instances
```

**Why this matters:** The system identified *concepts* related to uselessness, not just text containing the word. It understood "Value of Uselessness" as a philosophical idea.

## Example 2: Evidence and Provenance

**Query:** Get details on "Value of Uselessness"

```bash
$ python cli.py details watts_taoism_02_chunk1_603de879

Concept Details: watts_taoism_02_chunk1_603de879

Label: Value of Uselessness
ID: watts_taoism_02_chunk1_603de879
Search Terms: useless life, purposeless universe, Taoist view on usefulness
Documents: Watts Taoism 02

Evidence (1 instances):

1. Watts Taoism 02 (para 1):
   "The whole notion of something of life, any moment in life or any
    event in life being useful, that is to say serving the end of some
    future event in life, is to a Taoist absurd."

Relationships (2):
  → SUPPORTS → Admiration of Nature (watts_taoism_02_chunk1_5f1c14d3)
                [confidence: 0.85]
  → IMPLIES → Ideal Useless Man (watts_taoism_02_chunk1_22a1d512)
              [confidence: 0.8]
```

**What you get:**
- The exact quote from the source text
- Document and paragraph reference (verifiable)
- Relationships to other concepts with confidence scores
- Search terms for alternative ways to find this concept

## Example 3: Cross-Document Concept Discovery

**Query:** "variety requisite human capability"

After ingesting both Watts lectures AND a technical paper on AI systems, the graph connected concepts across documents:

```
Results: 10 concepts

1. Requisite Variety (83.7% similarity)
   - From: "Variety as a fulcrum" (AI paper)
   - Search terms: ["Ashby's Law", "system control", "variety matching"]
   - Evidence: 3 quotes about variety requirements

2. Variety (79.7% similarity)
   - Search terms: ["adaptive capacity", "mental models", "skills"]
   - Evidence: "For a human, variety is built through experience,
               training, and critical thinking..."

3. Human Variety (79.1% similarity)
   - Relationships: SUPPORTS → "AI Sandwich Systems Model"
   - Evidence: "System capability collapses to human limitations"
```

**Cross-document synthesis:** The system understood that "variety" in the technical paper and "adaptive capacity" in discussions of human cognition refer to the same underlying concept, even though they use different terminology.

## Example 4: Relationship Traversal

**Query via MCP (in Claude Desktop):**

```
User: "How is variety implicated in the AI Sandwich model?"

Claude using knowledge graph tools:
- search_concepts("variety")
- get_concept_details("variety_as_a_fulcrum_chunk2_8e05c87e")
- find_related_concepts(max_depth=2)

Response: "Variety functions as the fundamental constraint (Ashby's Law)...
           AI is a variety amplifier, not a creator...
           The system identified 7 ways variety is implicated..."
```

The graph enabled the LLM to:
1. Find the core "Variety" concept
2. Retrieve evidence quotes
3. Traverse relationships to "AI Sandwich", "Requisite Variety", "Borrowed Variety"
4. Synthesize a structured answer with provenance

**This is impossible with pure RAG** - RAG can't traverse concept relationships or understand how ideas mechanistically connect.

## Example 5: Exploring Unknown Connections

**Scenario:** You've ingested a document but don't know what's in it.

**Query:** "What are the main concepts?"

```bash
$ python cli.py search "system design organization" --limit 10

Found 10 concepts:

1. Variety-Centric System Design (76.9%)
2. AI Sandwich Systems Model (71.6%)
3. Organizational Investment in Human Variety (69.5%)
4. Prompt Engineering Limitations (69.4%)
5. Variety-Appropriate Deployment (67.9%)
...
```

**Then traverse:**

```bash
$ python cli.py related variety_as_a_fulcrum_chunk1_27613d66 --depth 2

Related concepts from: AI Sandwich Systems Model

Distance 1:
  • Variety → path: [SUPPORTS]
  • Human-in-the-Loop → path: [PART_OF]

Distance 2:
  • Requisite Variety → path: [SUPPORTS, IMPLIES]
  • Variety Mismatch → path: [SUPPORTS, CAUSES]
  • Borrowed Variety → path: [PART_OF, CONTRADICTS]
```

You discover the argument structure without reading the document linearly.

## Example 6: Evidence-Based Learning

**Use case:** Understanding a philosophical argument

**Query:** "What does Zhuangzi say about humor?"

```bash
$ python cli.py search "Zhuangzi humor philosophy"

1. Humor in Philosophy
   Evidence: "He's almost the only philosopher from the whole of
              antiquity who has real humor."
   Source: Watts Taoism 02, para 1

Related concepts:
  • Zhuangzi (author concept)
  • Taoist Philosophy
  • Value of Uselessness
```

The system:
- Found the concept of "Humor in Philosophy"
- Provided the exact quote as evidence
- Connected it to related Taoist concepts
- Gave source attribution (verifiable)

## Example 7: Multi-Modal Access

The same knowledge graph can be queried three ways:

**Via CLI (humans):**
```bash
$ python cli.py search "adoption valley"
→ Returns: "Adoption Valley" concept with evidence
```

**Via MCP (LLMs in Claude Desktop):**
```
Claude: Let me search the knowledge graph for "adoption valley"...
→ Uses: mcp__knowledge-graph__search_concepts
→ Gets: Full concept details with relationships
```

**Via Neo4j Browser (visual):**
```cypher
MATCH (c:Concept {label: "Adoption Valley"})-[r]->(related:Concept)
RETURN c, r, related
```
→ Shows: Interactive graph visualization of concept relationships

All three query the same persistent knowledge structure.

## Example 8: Failure Mode Analysis

**Not everything works perfectly.** Here's what can go wrong:

**LLM Extraction Errors:**
Sometimes the LLM misidentifies concepts or creates poor relationships. You'll see:
```
⚠ Skipping relationship: concept not found
```

**Deduplication Over-Merging:**
Occasionally, similar but distinct concepts merge when they shouldn't. Check with:
```bash
$ python cli.py details <concept-id>
→ Review evidence to see if multiple ideas were merged
```

**Relationship Confidence:**
Low-confidence relationships (< 0.5) may be spurious:
```
→ IMPLIES → SomeOtherConcept [confidence: 0.3]  # Questionable
```

The system shows you the confidence scores so you can judge.

## Example 9: Real-World Performance

**Document:** 40KB transcript with no paragraph breaks (7,789 words)

**Ingestion stats:**
```
Chunks: 25
Concepts extracted: 127
Concepts created (new): 89
Concepts linked (existing): 38
Relationships: 156
Time: ~4 minutes (GPT-4o)

Vector search hit rate: Increased from 0% (chunk 1) to 83% (chunk 15)
→ Graph became "denser" as it learned the document's concepts
```

**Query performance:**
```
Semantic search: ~200ms (including vector similarity)
Graph traversal: ~150ms (2-hop relationships)
Evidence retrieval: ~100ms (with source quotes)
```

Fast enough for interactive exploration.

## Example 10: What This Enables

After building a knowledge graph, you can:

**Ask conceptual questions:**
- "What are the failure modes of AI systems?" → Get concepts, not text chunks
- "How do Taoist ideas relate to purposelessness?" → See relationship graph

**Validate claims:**
- "Where does the paper say variety is a constraint?" → Get exact quotes with sources

**Explore unknown territory:**
- Start at "Requisite Variety" → traverse to related concepts → discover "Adoption Valley"

**Synthesize across documents:**
- Concepts from Watts + AI paper automatically connected
- "Uselessness" (philosophy) links to "Value" (systems design)

**Build on knowledge:**
- Each new document adds to the graph
- Similar concepts merge automatically
- Relationships compound over time

---

## Try It Yourself

```bash
# Ingest your own document
./scripts/ingest.sh your-document.txt --name "My Document"

# Search for concepts
python cli.py search "your query"

# Explore relationships
python cli.py details <concept-id>
python cli.py related <concept-id>

# Visual exploration
# Open http://localhost:7474 in browser
# Run: MATCH (c:Concept)-[r]->(related) RETURN c, r, related LIMIT 50
```

The graph grows with every document. The connections emerge over time.

*Not retrieval. Understanding.*
