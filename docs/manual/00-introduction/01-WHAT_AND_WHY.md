# What is the Knowledge Graph System?

## The Core Innovation

The Knowledge Graph System is a **hybrid graph-vector platform** that transforms documents into queryable, interconnected concept networks. Unlike traditional retrieval systems that find similar text chunks, this system understands and preserves the *relationships* between ideas across your entire document corpus.

At its heart is **recursive upsert** - a unique process where:

1. **Vector embeddings** find semantically similar concepts (the "vector" part)
2. **Graph relationships** connect concepts through typed edges like IMPLIES, CONTRADICTS, ENABLES (the "graph" part)
3. **Recursive enhancement** means each new document doesn't just add data - it enriches existing concepts, discovers new connections, and builds understanding over time (the "recursive" part)

When you ingest a second document mentioning concepts from the first, the system recognizes them through semantic similarity (≥0.85 cosine threshold), merges evidence, and discovers new relationships. By the tenth document, the graph knows your domain - concept hit rates climb from 0% to 60%+ as the system learns.

## Why This Matters for AI Systems

**This platform is purpose-built as a memory and reasoning substrate for AI agents.**

Large language models have vast latent knowledge, but they lack persistent, queryable memory about *your* specific domain knowledge and how concepts relate within it. This system provides that missing layer:

### Activating Latent LLM Knowledge

When an AI agent queries the graph and receives results like:

```
Concept: "Apache AGE Migration"
  ENABLES → "RBAC Capabilities" (confidence: 0.92)
  PREVENTS → "Dual Database Complexity" (confidence: 0.88)
  RESULTS_FROM → "Unified Architecture" (confidence: 0.85)

Evidence from: commits, pull requests, architecture docs
```

...the LLM can activate its latent understanding of PostgreSQL, graph databases, and system architecture to reason about the *specific* architectural decisions in *your* codebase. The graph provides the structured facts and relationships; the LLM provides the reasoning capability.

### Persistent Conceptual Memory

Unlike conversation context that resets, or RAG systems that rebuild understanding on every query:

- **Concepts persist** as first-class entities with embeddings, labels, and search terms
- **Relationships persist** with confidence scores and provenance
- **Evidence persists** with exact quotes and document references
- **Understanding compounds** - each document makes the graph smarter

An AI agent can query "what architectural decisions enabled RBAC?" and receive precise graph-traversal results showing the chain of decisions, their relationships, and source evidence - without re-reading hundreds of pages.

### Multi-Hop Reasoning

Graph traversal enables multi-hop reasoning that's explicit and traceable:

```cypher
MATCH path = (start:Concept {label: 'Linear Scanning'})-[*1..3]->(end:Concept)
WHERE end.label CONTAINS 'Intelligence'
RETURN path
```

The system finds conceptual pathways like: `Linear Scanning → Sequential Processing → Pattern Recognition → Intelligence`, with each hop backed by evidence and confidence scores. This gives AI agents structured reasoning paths instead of implicit token associations.

### Cross-Document Synthesis

When you ingest:
- Project commit messages → "Project History" ontology
- Pull request descriptions → "Project PRs" ontology
- Architecture decision records → "Project ADRs" ontology

...the system automatically merges semantically identical concepts across ontologies. An AI agent asking about "authentication implementation" gets a unified view synthesized from code, discussions, and design docs - without manual linking.

## The Difference from Other Approaches

### vs. Vector Databases (Traditional RAG)

**Vector databases** excel at semantic similarity but lose relational context:
- Find documents *similar to* your query
- No understanding of how concepts relate
- Rebuild context on every query
- Can't traverse relationships or reason about causality

**This system** combines vectors with explicit relationships:
- Find concepts *and their connections*
- IMPLIES, CONTRADICTS, ENABLES relationships are explicit
- Persistent understanding that compounds
- Multi-hop traversal reveals reasoning paths

### vs. Pure Knowledge Graphs

**Pure knowledge graphs** preserve relationships but lack semantic flexibility:
- Require exact entity/predicate matches
- Rigid schema requirements
- Manual concept definition
- Poor fuzzy matching

**This system** adds semantic understanding:
- Vector similarity matches variations ("auth", "authentication", "user login")
- LLM extraction adapts to domain vocabulary
- Automatic concept recognition and merging
- Semantic search finds conceptually related ideas

### vs. GraphRAG Systems

**GraphRAG** is the emerging pattern of combining graphs and vectors - this system is a production implementation of that approach, with critical additions:

- **Job approval workflow** with cost controls (ADR-014)
- **Authentication and RBAC** for production deployment (ADR-018, ADR-019)
- **Custom relationship vocabularies** that evolve with your domain (ADR-025)
- **Visual query builder** and interactive graph exploration (ADR-034)
- **REST API and MCP integration** for agent access
- **Apache AGE + PostgreSQL** - production-grade graph database with openCypher

These aren't just "nice features" - they're what makes the system *usable at scale* in real organizations with multiple users, sensitive data, cost constraints, and integration requirements.

## How It Works (Simplified)

```
1. Document Submission
   ↓
2. Intelligent Chunking (~1000 words, respecting boundaries)
   ↓
3. Vector Embedding (1536-dimensional semantic representation)
   ↓
4. Semantic Matching (query existing concepts, ≥0.75 similarity)
   ↓
5. LLM Extraction (with context from matched concepts)
   ↓
6. Recursive Upsert (merge or create concepts + relationships)
   ↓
7. Graph Storage (Apache AGE with provenance)
   ↓
8. Available for Query (REST API, CLI, MCP, Visual Explorer)
```

The "recursive" part is critical: each chunk queries recent concepts before extraction. Early chunks populate the graph; later chunks connect to existing concepts. The LLM sees what the graph already knows, enabling cross-chunk relationship detection.

## Real-World Example

**Input:** Company ingests 50 meeting transcripts into "Product Discussions" ontology

**After 10 documents:**
- 234 concepts extracted
- 15% hit rate (finding existing concepts)
- Concepts: "User Authentication", "Mobile App", "API Gateway"

**After 30 documents:**
- 612 concepts total
- 52% hit rate (growing recognition)
- New relationships discovered: "API Gateway ENABLES Mobile App", "User Authentication REQUIRED_BY Mobile App"

**After 50 documents:**
- 891 concepts total (growth slowing - domain is learned)
- 64% hit rate (high reuse)
- Cross-document synthesis reveals: "Performance Issues CONTRADICT Mobile First Strategy" with evidence from 8 different meetings

**AI Agent Query:** "What's blocking our mobile strategy?"

**System Response:**
```
Graph traversal found:
  "Mobile First Strategy" ← CONTRADICTS ← "Performance Issues"
  "Performance Issues" ← CAUSED_BY ← "API Gateway Latency"
  "API Gateway" ← DEPENDS_ON ← "Legacy Authentication System"

Evidence:
  - "Our mobile experience suffers from 3-second load times..." (Meeting 12, para 4)
  - "The gateway times out waiting for auth..." (Meeting 24, para 2)
  - "Can't refactor auth without breaking desktop..." (Meeting 38, para 6)

Related concepts: "Authentication Refactoring", "Performance Optimization", "Service Mesh"
```

The AI agent receives structured facts, relationships, and evidence - exactly what it needs to reason about the problem and propose solutions.

## What's Actually Unique

Many systems do graphs. Many do vectors. Some combine them. What makes this system different:

1. **Recursive upsert with LLM context** - extraction sees what the graph already knows
2. **Built for AI agent memory** - persistent, queryable, relationship-rich
3. **Production-ready infrastructure** - auth, RBAC, cost controls, APIs
4. **Evidence provenance** - every concept links to source quotes
5. **Cross-ontology enrichment** - concepts bridge document collections
6. **Interactive exploration** - visual query builder, graph visualization
7. **Apache AGE foundation** - production PostgreSQL with openCypher and full ACID guarantees

The recursive upsert creates a **learning system** - not just storage, but a knowledge base that becomes more valuable with each document because it *understands* more.

## Who Should Use This

**AI Agent Developers**
- Give your agents persistent conceptual memory
- Enable graph-structured reasoning over domain knowledge
- Provide explicit relationship traversal instead of pure similarity

**Research & Knowledge Work**
- Navigate philosophical or scientific texts by concept relationships
- Discover connections across papers you didn't know were related
- Build synthetic understanding that compounds over time

**Development Teams**
- Ingest commit history, PRs, and ADRs into queryable knowledge
- Understand why architectural decisions enabled or prevented features
- Create living documentation that evolves with your codebase

**Organizations with Knowledge Silos**
- Connect meeting notes, reports, and strategy docs through shared concepts
- Discover implicit dependencies and contradictions across teams
- Build institutional knowledge that doesn't reset when people leave

## What This Documentation Covers

The rest of this manual walks through:

- **Getting Started** - Installation, first ingestion, basic queries
- **Configuration** - AI providers (OpenAI, Anthropic, Ollama), embeddings, extraction tuning
- **Integration** - MCP setup for Claude Desktop/Code, vocabulary management
- **Security & Access** - Authentication, RBAC, encrypted API keys
- **Maintenance** - Backup/restore, schema migrations
- **Reference** - Complete schema docs, query patterns, examples

The infrastructure (auth, RBAC, API, visualizer) exists to support the recursive upsert approach at production scale - it's mentioned where relevant but not the focus.

## Next Steps

Ready to try it? Start with [Quickstart](../01-getting-started/01-QUICKSTART.md) to get running in 5 minutes.

Want to understand the architecture? See [Architecture Overview](../../architecture/ARCHITECTURE_OVERVIEW.md) and [ADR-016: Apache AGE Migration](../../architecture/ADR-016-apache-age-migration.md).

Curious about the recursive upsert pattern in depth? See [Recursive Upsert Architecture](../../architecture/RECURSIVE_UPSERT_ARCHITECTURE.md) (referenced in the knowledge graph) and [Enrichment Journey](../06-reference/07-ENRICHMENT_JOURNEY.md) for a real example.
