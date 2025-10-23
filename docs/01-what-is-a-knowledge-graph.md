# 01 - What Is a Knowledge Graph?

**Part:** I - Foundations
**Reading Time:** ~15 minutes
**Prerequisites:** None

---

## Introduction

You're probably familiar with searching through documents, skimming text, and hoping you find what you need. Maybe you've used RAG (Retrieval-Augmented Generation) systems that throw similar text chunks at an LLM and cross your fingers. These approaches work... sometimes. But they have fundamental limitations.

What if, instead of searching for *text*, you could explore *ideas*? What if concepts could connect to each other across documents, preserving their relationships and evidence? What if knowledge could accumulate and grow smarter over time, instead of being rebuilt from scratch for every query?

That's what a knowledge graph does.

---

## The Problem with Traditional Text Retrieval

### How RAG Systems Work

Traditional Retrieval-Augmented Generation (RAG) systems follow a simple pattern:

1. Break documents into chunks
2. Create vector embeddings for each chunk
3. Find chunks similar to your query
4. Stuff those chunks into LLM context
5. Hope the LLM can figure it out

This works for quick lookups, but it has serious limitations:

###  **Ephemeral Knowledge**

Every query rebuilds understanding from scratch. There's no persistent structure, no accumulated insight. Each search is like reading the document for the first time. The system has no memory of what it learned before.

### **Similarity ≠ Understanding**

Vector similarity finds "related text" but doesn't understand *how* ideas relate:
- Does concept A support concept B?
- Does it contradict it?
- Does it depend on it?
- Is it a prerequisite?

RAG can't tell you. It just knows the vectors are close in 1536-dimensional space.

### **No Cross-Document Synthesis**

RAG treats documents as silos. If two papers discuss the same concept using different terminology, RAG won't connect them unless the vectors happen to align. You lose the synthesis across your knowledge base.

### **Lost Provenance**

When you get an answer, where did it come from? Which specific quote? From what paragraph? In what context? RAG gives you chunks and vague citations, not precise evidence trails.

### **No Traversal**

You can't ask:
- "Show me what connects to this concept"
- "Explore related ideas"
- "Trace the argument chain"

RAG is search-only, not exploration.

---

## The Knowledge Graph Approach

A knowledge graph system thinks about documents fundamentally differently. Instead of treating text as the primary unit, it extracts and models the *ideas* within that text as first-class entities.

### Concepts Are Explicit

Instead of "chunk 47 from document X," you have:

```
Concept: "Requisite Variety"
Label: "Requisite Variety"
Search Terms: ["Ashby's Law", "system control", "variety matching"]
Relationships:
  - SUPPORTS → "AI Sandwich Systems Model"
  - IMPLIES → "Control requires matching complexity"
Evidence:
  - "A control system must have variety...at least equal to the variety
     of the system being controlled" (Source: cybernetics_101.md, ¶3)
  - "You can't control what you can't match" (Source: systems_thinking.pdf, ¶12)
```

This concept is *persistent*. It exists as a node in the graph, connected to other concepts, backed by evidence.

### Relationships Model Understanding

The system captures *how* ideas connect, not just that they're "similar":

- **IMPLIES**: Concept A logically leads to Concept B
- **SUPPORTS**: Concept A provides evidence for Concept B
- **CONTRADICTS**: Concept A conflicts with Concept B
- **DEPENDS_ON**: Concept A requires understanding Concept B first
- **EXEMPLIFIES**: Concept A is a specific instance of Concept B

These aren't just links—they represent the document's argument structure. When you explore the graph, you're following the author's reasoning, not just vector similarity.

### Persistent, Growing Knowledge

Once extracted, concepts persist. New documents:
- Add new concepts
- Connect to existing concepts
- Merge with similar concepts automatically
- Provide additional evidence for existing ideas

The graph becomes smarter with each document ingested. It's not ephemeral—it's cumulative.

### Evidence-Based Retrieval

Every concept links back to the source quotes that support it:

```
Concept: "Value of Uselessness"
Evidence Instance 1:
  Quote: "The whole notion of something of life...being useful...
          is to a Taoist absurd."
  Source: Alan Watts - Tao of Philosophy - 02, paragraph 1

Evidence Instance 2:
  Quote: "The moment you make something useful, you've destroyed its
          intrinsic value."
  Source: Alan Watts - Tao of Philosophy - 04, paragraph 7
```

You can trace any claim back to its origins. You can *verify*, not just trust.

### Graph Traversal

You can explore the knowledge space:
- "What concepts support this idea?"
- "What does this contradict?"
- "Show me the evidence chain from A to B"
- "Find all concepts 2 hops away from this one"
- "What connects these two seemingly unrelated concepts?"

This is **exploration**, not just search.

---

## What This Enables

### For Human Learning

**Exploration, Not Just Search**
Start with one concept, traverse relationships, discover connections you didn't know to look for. Learn the way your brain actually works—by association and connection, not linear text.

**Provenance & Trust**
Every claim traces back to specific quotes. You can verify, question, and understand the source of knowledge.

**Concept Maps**
Visualize how ideas connect across an entire document collection. See the big picture and the details simultaneously.

**Multi-Perspective Understanding**
When you ingest a 500-page codebase and 280 commits, you can explore from multiple angles:
- "Show me all authentication-related concepts"
- "What architectural decisions led to this design?"
- "How did the approach evolve over time?"

(See [Section 60](60-case-study-multi-perspective-enrichment.md) for a real example of this.)

### For AI Assistants (LLMs)

**Semantic Grounding**
Instead of "here's some similar text," the LLM receives:
- "Here's the concept of Requisite Variety"
- "It SUPPORTS the AI Sandwich model with 0.85 confidence"
- "Evidence: [3 exact quotes with sources]"
- "It's related to these 5 other concepts via these relationship types"

**Relationship Awareness**
The LLM can reason about how concepts connect, not just what they say. It understands the argument structure, not just the content.

**Multi-Document Synthesis**
Concepts from different sources automatically link. The LLM can synthesize across your entire knowledge base, not just similar chunks from a single document.

---

## The Hybrid Architecture

This system doesn't replace other approaches—it combines them:

1. **Vector Search** - Find concepts semantically similar to a query (like RAG)
2. **Graph Traversal** - Explore relationships between concepts (unique to graphs)
3. **Full-Text Search** - Find exact quotes or terminology (classic search)

RAG only has #1. This system has all three.

You get the semantic power of embeddings, the structural power of graphs, and the precision of exact search.

---

## Core Terminology

Before we go further, let's define the core terms you'll see throughout this documentation:

**Knowledge Graph**
A data structure that represents information as nodes (concepts) connected by edges (relationships), rather than as linear text or flat tables.

**Concept**
A core idea, entity, or principle extracted from source text. Examples: "Linear Thinking", "Microservices Architecture", "Requisite Variety".

**Relationship**
A typed connection between concepts that captures how they relate. Examples: IMPLIES, SUPPORTS, CONTRADICTS, DEPENDS_ON.

**Evidence / Instance**
A specific quote from source text that supports or exemplifies a concept. Every concept has one or more evidence instances linking it to the original text.

**Source**
The original document, paragraph, or text unit from which concepts and evidence were extracted.

**Ontology**
In this system: a thematic collection of related documents that form a knowledge domain. Examples: "Alan Watts Lectures", "Company Architecture Docs", "Research Papers - Cognitive Science".

**Extraction**
The process of using an LLM (GPT-4, Claude, local models) to read text and identify concepts, relationships, and evidence.

**Embedding**
A 1536-dimensional vector representation of a concept's meaning, used for semantic similarity search.

**Graph Traversal**
The process of following relationships from concept to concept, exploring the knowledge structure.

---

## What We're Not Claiming

Let's be clear about what this system is and isn't.

This is **not**:
- A replacement for reading (you still need to engage with ideas)
- Perfect extraction (LLMs make mistakes in identification and relationships)
- A solved problem (this is experimental and evolving)
- The only way to do knowledge graphs (many approaches exist)
- Faster than RAG for simple queries (the graph takes time to build)

This **is**:
- A different paradigm: persistent concepts vs. ephemeral retrieval
- A synthesis of LLM extraction + graph storage + semantic search
- An experiment in what becomes possible when you model ideas, not just text
- A tool for long-term knowledge building, not one-off queries

---

## When to Use Each Approach

### Use RAG When:
- You need quick, one-off queries
- Documents are homogeneous and well-structured
- You don't need to understand relationships between concepts
- You're okay rebuilding context every time
- Query speed is more important than knowledge depth

### Use Knowledge Graphs When:
- You're building long-term knowledge bases
- Relationships between ideas matter
- You need provenance and evidence tracking
- You want to explore, not just retrieve
- You're synthesizing across multiple documents or sources
- The cost of initial extraction is worth the long-term value

---

## The Vision: What Becomes Possible

Imagine ingesting:
- **Your entire codebase** - Concepts = architectural decisions, components, dependencies, design patterns
- **Research paper collections** - Concepts = theories, findings, methodologies, experimental results
- **Company documentation** - Concepts = policies, procedures, best practices, tribal knowledge
- **Historical texts** - Concepts = events, figures, philosophical ideas, cultural movements
- **Meeting transcripts** - Concepts = decisions made, action items, strategic directions

Then querying:
- "Show me all architectural decisions related to authentication"
- "What research findings contradict the embodied cognition hypothesis?"
- "Trace the evolution of our deployment policy across all document versions"
- "How do Stoic and Taoist concepts of acceptance relate to each other?"
- "What design patterns led to our current microservices architecture?"

Not just finding similar text. **Understanding the knowledge.**

---

## Implementation Reality

This system:
- Uses LLMs for extraction (OpenAI GPT-4, Anthropic Claude, local Ollama models)
- Stores concepts in Apache AGE (PostgreSQL graph extension) with vector embeddings
- Deduplicates concepts via vector similarity (concepts merge automatically across documents)
- Preserves evidence links to source quotes with exact paragraph references
- Provides multiple query interfaces:
  - MCP server (Claude Desktop integration)
  - CLI (`kg` command)
  - REST API
  - Direct openCypher queries

It's not magic. It's:
1. Structured extraction by LLMs
2. Graph storage with relationships
3. Semantic retrieval via embeddings
4. Evidence preservation for trust

But the combination creates something qualitatively different from RAG.

---

## What's Next

Now that you understand the conceptual foundation, let's see how this system actually works:

- **[Section 02 - System Overview](02-system-overview.md)**: Architecture and components
- **[Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md)**: Build your first graph in 5 minutes
- **[Section 07 - Real World Example](07-real-world-example-project-history.md)**: See it in action with a real codebase

Or jump ahead to see the evidence:
- **[Section 60 - Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)**: How 280 commits and 31 PRs become navigable knowledge

---

**The goal isn't to replace RAG. It's to explore what becomes possible when we move from retrieving text to modeling knowledge.**

← [Documentation Index](README.md) | [Next: System Overview →](02-system-overview.md)
