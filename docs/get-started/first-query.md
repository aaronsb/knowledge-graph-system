---
id: 05.002.T
domain: query
mode: tutorial
---

# Your First Query

This tutorial walks through querying a Kappa Graph knowledge graph with real commands and real output. By the end you will have searched for concepts, examined evidence, traversed relationships, and found a path between two ideas.

The examples below use a graph built from two documents: Alan Watts lectures on Taoism and a technical paper on AI systems and human variety. The commands and output patterns are the same regardless of what is in your graph.

**Prerequisites:** Kappa Graph is running (`kg health` returns OK) and at least one document has been ingested. If you have not done that yet, complete [Your First Graph](first-graph.md) first.

---

## Search for concepts

`kg search` finds concepts by semantic similarity — it matches meaning, not keywords.

```bash
kg search query "uselessness" --limit 3
```

```
Found 2 concepts:

● 1. Value of Uselessness
   ID: watts_taoism_02_chunk1_603de879
   Similarity: 89.5%
   Documents: Watts Taoism 02
   Evidence: 1 instances
   Grounding: ✓ Well-supported [82% conf]

● 2. Ideal Useless Man
   ID: watts_taoism_02_chunk1_22a1d512
   Similarity: 81.3%
   Documents: Watts Taoism 02
   Evidence: 1 instances
   Grounding: ⚡ Some support (limited data) [61% conf]
```

The search returned concepts related to uselessness as a philosophical idea — not just text containing the word. The similarity score measures how close each concept's embedding is to your query. The grounding score measures how consistently the concept is supported across the corpus.

If you get fewer results than expected, lower the similarity threshold:

```bash
kg search query "uselessness" --min-similarity 0.5
```

---

## Examine evidence

Take the concept ID from the search result and retrieve its full detail: all evidence quotes, source references, and outgoing relationships.

```bash
kg search show watts_taoism_02_chunk1_603de879
```

```
Concept Details: Value of Uselessness

ID: watts_taoism_02_chunk1_603de879
Search Terms: useless life, purposeless universe, Taoist view on usefulness
Documents: Watts Taoism 02
Grounding: ✓ Well-supported [82% conf]

Evidence (1 instances)
────────────────────────────────────────────────────────────────────────────────

1. Watts Taoism 02 (para 1)
   "The whole notion of something of life, any moment in life or any
    event in life being useful, that is to say serving the end of some
    future event in life, is to a Taoist absurd."

Relationships (2)
────────────────────────────────────────────────────────────────────────────────
  → SUPPORTS → Admiration of Nature (watts_taoism_02_chunk1_5f1c14d3) [85%]
  → IMPLIES  → Ideal Useless Man    (watts_taoism_02_chunk1_22a1d512)  [80%]
```

Each evidence entry carries the exact quote and its document location. Every claim is verifiable: document name, paragraph number, and the text itself.

`kg search show` accepts `details` as an alias if you prefer that form.

---

## Traverse the graph

Once you have a concept ID, follow its relationships outward. `kg search related` does a breadth-first traversal and groups results by distance.

```bash
kg search related watts_taoism_02_chunk1_603de879 --depth 2
```

```
Related Concepts from: watts_taoism_02_chunk1_603de879
Max depth: 2

✓ Found 4 related concepts:

Distance 1:
  ● Admiration of Nature (watts_taoism_02_chunk1_5f1c14d3)
    Path: SUPPORTS
  ● Ideal Useless Man (watts_taoism_02_chunk1_22a1d512)
    Path: IMPLIES

Distance 2:
  ● Zhuangzi (watts_taoism_02_chunk2_a9b34c11)
    Path: SUPPORTS → ASSOCIATED_WITH
  ● Taoist Philosophy (watts_taoism_02_chunk3_7d2ef001)
    Path: IMPLIES → PART_OF
```

Increase `--depth` to expand the traversal. Depths beyond 3 slow noticeably on large graphs. Filter by relationship type when you want to follow only one kind of edge:

```bash
kg search related watts_taoism_02_chunk1_603de879 --depth 3 --types IMPLIES SUPPORTS
```

---

## Find a path between two concepts

`kg search connect` finds the shortest path between two concepts. Pass concept IDs for an exact lookup, or natural-language phrases for semantic matching.

**By concept ID:**

```bash
kg search connect \
  watts_taoism_02_chunk1_603de879 \
  variety_as_a_fulcrum_chunk2_8e05c87e
```

**By phrase (the system resolves to the closest matching concepts):**

```bash
kg search connect "value of uselessness" "requisite variety"
```

```
Finding Connection

  From: Value of Uselessness (matched: "value of uselessness")
        Match: 89%
  To:   Requisite Variety    (matched: "requisite variety")
        Match: 83%
  Max hops: 5

✓ Found 1 path:

Path 1 (4 hops):
  Value of Uselessness  (watts_taoism_02_chunk1_603de879)
    ↓ IMPLIES
  Ideal Useless Man     (watts_taoism_02_chunk1_22a1d512)
    ↓ SUPPORTS
  Human Variety         (ai_paper_chunk3_b2c9f104)
    ↓ ENABLES
  Requisite Variety     (variety_as_a_fulcrum_chunk2_8e05c87e)
```

This path crosses documents — from the Watts lecture to the AI paper — because both were ingested into the same graph and the extractor found overlapping concepts.

If phrase matching does not resolve to the concept you want, pass `--min-similarity 0.4` to broaden the match or use explicit IDs.

---

## Query the raw source text

`kg search sources` searches the original source chunks by embedding similarity rather than concept embeddings. Use it to find where in the raw text a topic appears.

```bash
kg search sources "human variety adaptive capacity" --limit 5
```

```
Source Search: human variety adaptive capacity

✓ Found 3 source(s):

● 1. Variety as a Fulcrum (para 2)
   Source ID: src_ai_paper_chunk2_d49e1a0c
   Similarity: 82.1%
   Matched chunk: [0:847]
   "For a human, variety is built through experience, training, and
    critical thinking..."
   Concepts: (3 extracted)
     → Requisite Variety (variety_as_a_fulcrum_chunk2_8e05c87e)
     → Human Variety     (ai_paper_chunk3_b2c9f104)
     → Adaptive Capacity (ai_paper_chunk2_f3b20011)
```

The output shows the matched text chunk, the concepts extracted from it, and the source ID you can use in other commands.

---

## Access the same graph three ways

Every query above uses the CLI. The same data is accessible via MCP (for LLM agents) and via direct Cypher (for custom analysis):

**CLI:**

```bash
kg search query "adoption valley"
```

**MCP — in an MCP-connected client such as Claude Desktop:**

```
search_concepts("adoption valley")
→ Returns concept list with relationships and evidence
```

**Cypher — direct query against Apache AGE / PostgreSQL 18:**

```cypher
MATCH (c:Concept {label: "Adoption Valley"})-[r]->(related:Concept)
RETURN c, r, related
```

All three read the same persistent graph. The web interface at `http://localhost:3000` renders Cypher results as an interactive graph.

---

## What can go wrong

**LLM extraction errors.** The extractor occasionally misidentifies concepts or creates weak relationships. During ingestion you may see:

```
⚠ Skipping relationship: concept not found
```

Check the concept detail afterward with `kg search show <id>` to see whether the evidence supports the label.

**Over-merging.** The deduplication step merges concepts that look similar. If a concept you expect to be distinct is missing, it may have merged with a neighbor. Review its evidence:

```bash
kg search show <concept-id>
```

Multiple unrelated quotes in the evidence block indicate a merge.

**Low-confidence relationships.** Relationships with a confidence score below 0.5 may be spurious:

```
→ IMPLIES → SomeOtherConcept [30%]  # treat with caution
```

The confidence score is shown in all output — use it to weight traversal results.

---

## Next steps

- Ingest your own documents: [Ingest Documents](../how-to/ingest.md)
- Explore and filter what is in the graph: [Explore and Query](../how-to/query.md)
- Connect an LLM agent via MCP: [Connect via MCP](mcp-quickstart.md)
- Understand what grounding and confidence measure: [Grounding and Epistemic Confidence](../explanation/grounding.md)
