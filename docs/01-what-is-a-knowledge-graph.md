# 01 - What Is a Knowledge Graph?

**Part:** I - Foundations
**Reading Time:** ~15 minutes
**Prerequisites:** None

---

## Introduction

This system extracts concepts from documents and represents them as nodes in a graph, connected by typed relationships. Instead of searching for similar text chunks (like RAG systems do), you can explore how ideas connect, accumulate knowledge over time, and trace claims back to their source evidence.

This section explains what knowledge graphs are, how they differ from text retrieval systems, and what that difference enables.

---

## How RAG Systems Work

Most document retrieval systems follow this pattern:

1. Split documents into chunks (usually 500-2000 words)
2. Generate vector embeddings for each chunk
3. When queried, find chunks with similar embeddings
4. Pass those chunks to an LLM for synthesis
5. Return an answer

This works well for quick lookups in well-structured documents.

## Limitations of Text Chunk Retrieval

### Knowledge Gets Rebuilt Every Time

Each query starts from scratch. The system doesn't remember what it learned from previous queries or accumulate understanding. If you ask the same question twice, it does the same work twice.

### Similarity Doesn't Capture Relationships

Vector embeddings tell you that two chunks of text are semantically similar. They don't tell you *how* the ideas relate. Does concept A support concept B? Contradict it? Depend on it? You can't tell from similarity scores alone.

### Documents Stay Isolated

If two papers discuss the same concept using different terminology, RAG won't connect them unless their embedding vectors happen to be close. You lose cross-document synthesis.

### Evidence Gets Lost

When RAG returns an answer, you get chunks with rough citations. You don't get precise quotes, paragraph references, or the ability to verify the source directly.

### No Graph Traversal

You can search, but you can't explore. Questions like "show me what connects these two concepts" or "what supports this idea" don't have answers in pure retrieval systems.

---

## Knowledge Graph Approach

A knowledge graph treats concepts as first-class entities with explicit relationships.

### Concepts as Nodes

Instead of storing "chunk 47 from document X," you store:

```
Concept ID: c_20240315_1523
Label: "Requisite Variety"
Search Terms: ["Ashby's Law", "system control", "variety matching"]
Embedding: [0.023, -0.145, 0.891, ... 1533 more dimensions]

Relationships:
  SUPPORTS → "Control System Design" (c_20240315_1524)
  IMPLIES → "Complexity Matching" (c_20240315_1525)

Evidence:
  Instance 1: "A control system must have variety at least equal
               to the variety of the system being controlled"
    Source: cybernetics_101.md, paragraph 3

  Instance 2: "You can't control what you can't match"
    Source: systems_thinking.pdf, paragraph 12
```

This concept persists. It's not ephemeral. When you ingest a new document that mentions requisite variety, it can link to this existing concept rather than creating a duplicate.

### Relationships Are Typed

The system records how concepts relate using semantic types:

- **IMPLIES** - Concept A logically leads to Concept B
- **SUPPORTS** - Concept A provides evidence for Concept B
- **CONTRADICTS** - Concept A conflicts with Concept B
- **DEPENDS_ON** - Understanding A requires understanding B first
- **EXEMPLIFIES** - A is a specific instance of B

These relationships come from the extraction process—the LLM identifies them while reading the text. When you traverse the graph, you're following the document's argument structure.

### Knowledge Accumulates

New documents add concepts, create new relationships, and provide additional evidence for existing ideas. The graph grows denser and more connected over time. Concepts that appear across multiple documents accumulate evidence instances, making them more central to the knowledge base.

### Evidence Links to Source

Every concept includes quoted text from source documents:

```
Concept: "Value of Uselessness"

Evidence Instance 1:
  Quote: "The whole notion of something of life being useful
          is to a Taoist absurd."
  Source: Alan Watts - Tao of Philosophy - 02, paragraph 1
  Ingested: 2024-03-15

Evidence Instance 2:
  Quote: "The moment you make something useful, you've destroyed
          its intrinsic value."
  Source: Alan Watts - Tao of Philosophy - 04, paragraph 7
  Ingested: 2024-03-17
```

You can verify claims by reading the original quotes in context.

### Graph Traversal

You can query relationships explicitly:

- "What concepts support this idea?"
- "Show me the path between concepts A and B"
- "Find concepts 2 relationships away from this one"
- "What evidence supports this claim?"

This is exploration, not just search.

---

## What This Enables

### For Research and Learning

When you ingest a large document set (like a 500-page codebase or 200 research papers), you can explore from multiple angles. Start with one concept, follow relationships, and discover connections that weren't obvious from linear reading.

You can see which architectural decisions led to specific design patterns, or how theoretical findings from different papers relate to each other. The graph makes implicit connections explicit.

### For Verification

Every claim traces to source quotes. If the system says "Concept A supports Concept B," you can read the evidence instances to verify that relationship makes sense. You're not trusting an LLM's synthesis—you're verifying against quoted text.

### For AI Assistants

When an LLM queries the graph, it receives structured information:

- The concept label and search terms
- Relationship types and targets
- Exact quotes with sources
- Connected concepts

This is more precise than passing similar text chunks and hoping the LLM figures out the structure.

---

## The Hybrid Approach

This system combines three query methods:

**Vector Search**
Find concepts semantically similar to a query. Uses the same embedding approach as RAG but returns concepts, not chunks.

**Graph Traversal**
Follow relationships between concepts. This is unique to graph structures.

**Full-Text Search**
Find exact quotes or terminology in evidence instances. Useful for precise lookups.

You're not replacing one approach with another. You're using all three where appropriate.

---

## Core Terminology

**Knowledge Graph**: A data structure representing information as nodes connected by typed edges.

**Concept**: An idea extracted from text. Examples: "Linear Thinking", "Microservices Architecture", "Requisite Variety".

**Relationship**: A typed connection between concepts (IMPLIES, SUPPORTS, CONTRADICTS, etc.).

**Evidence Instance**: A quoted passage from source text that supports a concept. Links concepts to original documents.

**Source**: The original document/paragraph where text was extracted.

**Ontology**: A thematic collection of documents forming a knowledge domain. Examples: "Alan Watts Lectures", "Company Docs".

**Extraction**: Using an LLM to identify concepts, relationships, and evidence in text.

**Embedding**: A 1536-dimensional vector representing a concept's meaning, used for similarity search.

**Graph Traversal**: Following relationships from concept to concept.

---

## Practical Differences

### RAG Strengths
- Fast for one-off queries
- No extraction cost upfront
- Works well with homogeneous documents
- Good for quick lookups

### Knowledge Graph Strengths
- Relationships are explicit and typed
- Knowledge accumulates across documents
- Concepts deduplicate automatically
- Evidence is precisely cited
- You can explore, not just search
- Cross-document synthesis works

### RAG Weaknesses
- No persistent knowledge structure
- Relationships are implicit (inferred by LLM)
- Documents stay isolated
- Same work repeated for each query

### Knowledge Graph Weaknesses
- Initial extraction takes time and costs tokens
- LLMs can make mistakes during extraction
- Requires more infrastructure (graph database)
- Slower for simple lookups

Different tools for different needs.

---

## What You Can Build

Once you have a knowledge graph, you can query:

**In a codebase:**
- "Show me all architectural decisions related to authentication"
- "What design patterns led to the current microservices structure?"
- "Trace the evolution of our API design across commits"

**In research papers:**
- "What findings contradict the embodied cognition hypothesis?"
- "How do these three theoretical frameworks relate?"
- "What evidence supports this claim?"

**In documentation:**
- "Trace our deployment policy changes over time"
- "What concepts connect security and performance?"
- "Show me all procedures that depend on this one"

**In ongoing knowledge collection:**
- Call transcripts from customer support
- Forum posts and community discussions
- Selected curated incremental discussions from meetings or Slack threads

The graph makes it possible to ask relationship questions, not just similarity questions.

---

## Implementation Notes

This system uses:
- **LLMs for extraction**: OpenAI GPT-4, Anthropic Claude, or local Ollama models
- **Apache AGE for storage**: PostgreSQL graph extension with openCypher queries
- **Vector embeddings**: For semantic similarity (OpenAI or local sentence-transformers)
- **Deduplication**: Concepts merge automatically when similarity exceeds threshold
- **Multiple interfaces**: MCP server (Claude Desktop), CLI (`kg` command), REST API

The extraction process:
1. Document is split into semantic chunks (~1000 words)
2. LLM reads each chunk and outputs structured JSON with concepts, relationships, evidence
3. Concepts are embedded and matched against existing concepts
4. Similar concepts merge; new concepts are added
5. Relationships and evidence instances are stored in the graph

This isn't magic—it's structured prompting + graph storage + semantic retrieval. But the combination produces different capabilities than text-chunk RAG. When coupled with tool-calling AI systems (like Claude with MCP access to the graph), it can appear remarkably intelligent: the AI queries precise relationships rather than retrieving vague chunks, leading to higher accuracy and lower context consumption.

---

## Limitations

**Extraction isn't perfect**: LLMs make mistakes. They might miss concepts, misidentify relationships, or extract the wrong level of granularity.

**It's not fast**: Initial ingestion takes time. A 100-page document might take 5-10 minutes to process and cost $0.50-$2.00 in API calls.

**You still need to think**: The graph organizes information. It doesn't think for you.

**This is experimental**: The field is evolving. Best practices aren't established yet.

---

## When to Use This

**Use knowledge graphs when:**
- You're building a long-term knowledge base
- Relationships between ideas matter
- You need precise evidence tracking
- You're synthesizing across multiple documents
- Exploration is as important as search
- The extraction cost is worth the long-term value

**Use RAG when:**
- You need quick, one-off answers
- Documents are well-structured and homogeneous
- Relationships don't matter much
- Speed is more important than depth

---

## Next Steps

Now that you understand what knowledge graphs are and how they differ from text retrieval, you can:

- **[Section 02 - System Overview](02-system-overview.md)**: See how the components fit together
- **[Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md)**: Build your first graph in 5 minutes
- **[Section 07 - Real World Example](07-real-world-example-project-history.md)**: See it working with actual data

Or jump to a case study:
- **[Section 60 - Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)**: How 280 commits become navigable knowledge

---

← [Documentation Index](README.md) | [Next: System Overview →](02-system-overview.md)
