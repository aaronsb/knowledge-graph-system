# Knowledge Graph System

**Transform documents into queryable concept networks, not just retrievable text.**

![Knowledge Graph Visualization](docs/media/neo4j-ui.jpeg)

## What This Is

A knowledge graph system using LLM extraction, Neo4j storage, and vector search. Built on Model Context Protocol (MCP) for multi-agent access.


**Core Pattern:**
Iterative graph traversal during ingestion. Each chunk:
1. Queries recent concepts from graph
2. Feeds context to LLM
3. Extracts new concepts and relationships
4. Upserts to graph
5. Next chunk uses enriched graph

The graph serves as both output and active input. Inspired by how coding agents replay conversation context.

**Measured Results:**
From ingestion logs (`logs/ingest_*.log`):
- 17 chunks, 16,617 words processed
- Chunk 1: 0% hit rate (graph empty)
- Chunk 11: 60% hit rate
- Chunk 15: 62.5% hit rate
- 63 concepts created, 28 linked to existing, 84 relationships

**Architecture:**
- Neo4j graph database with vector indexes
- MCP server for Claude Desktop integration
- Python ingestion pipeline with checkpoint/resume
- CLI for direct queries
- Full-text + vector search

**Production Path:**
- GitHub Actions integration for automated ingestion
- Batch processing for large document sets
- Scale testing and operational hardening

---

## What is This?

Most AI systems retrieve text chunks based on similarity. This system **extracts concepts, understands relationships, and builds a persistent knowledge graph** that can be explored, traversed, and queried semantically.

Instead of asking "what text is similar to my query?", you ask:
- "What concepts relate to uselessness in Taoist philosophy?"
- "Show me evidence for the AI Sandwich model"
- "How does variety connect to human-AI collaboration?"

**The difference:**
- 🔍 **RAG**: Find similar text → stuff into context → hope for the best
- 🕸️ **Knowledge Graph**: Extract concepts → model relationships → traverse connections → provide evidence

## Why Does This Matter?

Traditional RAG systems:
- Rebuild knowledge on every query (ephemeral)
- Retrieve based on vector similarity alone
- Treat documents as isolated text chunks
- Provide no concept-level understanding

This system:
- ✅ **Persistent concept extraction** - ideas become first-class entities with labels and search terms
- ✅ **Relationship modeling** - concepts IMPLY, SUPPORT, CONTRADICT each other
- ✅ **Graph traversal** - explore connections between ideas, not just similarity scores
- ✅ **Evidence provenance** - every concept links back to source quotes
- ✅ **Cross-document synthesis** - concepts from different sources automatically connect
- ✅ **Multi-modal access** - Query via MCP (for LLMs), CLI (for humans), or Neo4j Browser (visual)

## Live Example

After ingesting Alan Watts lectures and a technical paper on AI systems:

```bash
# Query: "uselessness"
→ Found: "Value of Uselessness" (89.5% similarity)
  Evidence: "The whole notion of something of life...being useful...
             is to a Taoist absurd."
  Related to: "Ideal Useless Man" → "Admiration of Nature"

# Query: "variety requisite human capability"
→ Found: "Requisite Variety" (Ashby's Law)
  Relationships: SUPPORTS "AI Sandwich Systems Model"
                IMPLIES "Variety Mismatch" failure patterns
  Evidence: 3 source quotes with paragraph references
```

The system understood:
- Taoist philosophy concepts across multiple lectures
- Technical framework relationships in the AI paper
- How "variety" functions as a mechanism, not just a keyword

## Quick Start

**Prerequisites:** Docker, Python 3.11+, Node.js 18+

### API Server + TypeScript Client

```bash
# 1. Setup system (one-time)
./scripts/setup.sh

# 2. Configure AI provider (OpenAI or Anthropic)
./scripts/configure-ai.sh

# 3. Start the API server
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8000

# 4. In another terminal: Build TypeScript client
cd client
npm install
npm run build
cd ..

# 5. Ingest documents via API
./scripts/kg-cli.sh ingest file document.txt --ontology "My Ontology"

# 6. Monitor job status
./scripts/kg-cli.sh jobs list
./scripts/kg-cli.sh jobs status <job-id>
```

**Current Status:**
- ✅ Async ingestion with job queue (ADR-014)
- ✅ Content deduplication
- ✅ Cost tracking and analysis
- ✅ Background processing with progress tracking
- ✅ Job approval workflow
- ✅ TypeScript CLI client (`kg` command)
- ⏳ Graph query commands (planned for TypeScript client)
- ⏳ MCP server mode (Phase 2)

See [ADR-012](docs/architecture/ADR-012-api-server-architecture.md), [ADR-013](docs/architecture/ADR-013-unified-typescript-client.md), and [ADR-014](docs/architecture/ADR-014-job-approval-workflow.md) for architecture details.

**For Claude Desktop/Code integration:** See [MCP Setup Guide](docs/guides/MCP_SETUP.md)

## How It Works

```
Document → Smart Chunking → LLM Extraction → Graph Construction → Semantic Query
            ↓                ↓                 ↓                   ↓
         Boundaries      Concepts +        Neo4j with          Vector Search
         Detected        Relationships     Evidence Links      + Traversal
```

1. **Smart Chunking**: Breaks documents at natural boundaries (paragraphs, sentences) with context overlap
2. **Concept Extraction**: LLM identifies concepts, evidence quotes, and relationships
3. **Graph Construction**: Stores in Neo4j with vector embeddings for similarity search
4. **Deduplication**: Automatically merges similar concepts across chunks/documents
5. **Query & Traverse**: Semantic search + graph traversal with evidence retrieval

## Architecture Highlights

- **Multi-Document Ontologies**: Group related documents into named ontologies - concepts automatically connect across files
- **Graph-Aware Chunking**: Queries recent concepts before processing new chunks, enabling cross-chunk relationship detection
- **Vector Deduplication**: Uses cosine similarity to merge concepts across document boundaries
- **Checkpoint & Resume**: Position tracking for large documents - resume if interrupted
- **Modular AI Providers**: Swap between OpenAI, Anthropic, or add your own
- **Full-Text + Vector Search**: Combined semantic and exact-match capabilities
- **Evidence Preservation**: Every concept links to source quotes with paragraph references
- **Learned Knowledge Synthesis**: Manually create connections between concepts with provenance tracking and similarity validation

## Learned Knowledge Synthesis

Beyond document extraction, you can create **learned connections** between concepts to capture "aha!" moments and cross-ontology insights:

```bash
# Create a learned relationship with similarity validation
python cli.py learn connect chapter_01_chunk2_c56c2ab3 signals_pillar1_signal1_62e52f23 \
  --evidence "Both emphasize transparency through measurable signals" \
  --creator your-name

# Output shows "smell test" results:
# Similarity to concept 1: 87.23%
# Similarity to concept 2: 84.56%
# Cognitive leap: LOW ✓ (obvious connection)
```

**Features:**
- **Smell Test Validation**: Calculates similarity between evidence and both concepts
- **Cognitive Leap Ratings**:
  - LOW (>85%): Obvious connection - "why didn't we think of this earlier?"
  - MEDIUM (70-85%): Reasonable connection
  - HIGH (<70%): Unusual connection - warns but allows
- **Provenance Tracking**: Every learned connection tracks creator, timestamp, and similarity score
- **Safe Operations**: Only deletes learned knowledge (never document-extracted data)

**Query learned knowledge:**
```bash
python cli.py learn list                      # All learned connections
python cli.py learn list --creator aaron      # Filter by creator
python cli.py learn list --cognitive-leap HIGH  # Find unusual connections
python cli.py learn list --min-similarity 0.8  # High-confidence only
```

**Use cases:**
- Bridge concepts across ontologies (e.g., "Governed Agility" ↔ "Role-Based Intelligence")
- Document expert insights that LLMs missed
- Create synthesis concepts that unify multiple ideas
- Track hypothesis connections for validation

See [Learned Knowledge MCP Plan](docs/development/LEARNED_KNOWLEDGE_MCP.md) for future AI-assisted synthesis features.

## Use Cases

**Research & Learning:**
- Explore philosophical texts by concept relationships, not linear reading
- Connect ideas across multiple papers or books
- Find evidence for specific claims with source attribution

**Documentation Understanding:**
- Navigate large codebases by architectural concepts
- Understand design decisions and their relationships
- Trace dependencies between system components

**Knowledge Synthesis:**
- Find connections between seemingly unrelated documents
- Build concept maps from lecture series or technical documentation
- Generate semantic overviews without reading everything linearly

## What Makes This Different?

This is **not** a new embedding model or vector database. It's a synthesis:

1. **LLM-powered extraction** (not just embeddings) - understands concepts, not just words
2. **Graph storage** (not vector-only) - models relationships between ideas
3. **Evidence-based retrieval** (not just chunks) - provides source quotes for every concept
4. **Persistent knowledge** (not ephemeral RAG) - builds understanding over time
5. **Human + AI queryable** (not just AI) - CLI, MCP, and Neo4j Browser access

## Learn More

- 📖 [Documentation Index](docs/README.md) - Navigate all documentation by category
- 📖 [Concept Deep Dive](docs/reference/CONCEPT.md) - Why knowledge graphs vs RAG
- 🏗️ [Architecture](docs/architecture/ARCHITECTURE.md) - How the system works
- 🚀 [Quick Start Guide](docs/guides/QUICKSTART.md) - Get running in 5 minutes
- 🔌 [MCP Setup Guide](docs/guides/MCP_SETUP.md) - Configure Claude Desktop/Code integration
- 💡 [Examples & Demos](docs/guides/EXAMPLES.md) - Real queries with actual results
- ⚙️ [AI Provider Configuration](docs/guides/AI_PROVIDERS.md) - OpenAI, Anthropic, or custom
- 📚 [Concepts & Terminology](docs/reference/CONCEPTS_AND_TERMINOLOGY.md) - Understanding ontologies, stitching, pruning, and graph integrity
- 💾 [Backup & Restore Guide](docs/guides/BACKUP_RESTORE.md) - Protecting your LLM token investment

## Project Structure

```
knowledge-graph-system/
├── src/                    # Python source code
│   └── api/               # FastAPI server
│       ├── main.py        # API entry point
│       ├── routes/        # REST endpoints
│       ├── services/      # Job queue, scheduler, deduplication
│       ├── workers/       # Background ingestion workers
│       ├── models/        # Pydantic schemas
│       └── lib/           # Shared ingestion library
│           ├── chunker.py         # Smart text chunking
│           ├── llm_extractor.py   # LLM concept extraction
│           ├── neo4j_client.py    # Graph database operations
│           ├── ingestion.py       # Chunk processing & stats
│           ├── ai_providers.py    # Modular AI provider abstraction
│           └── parser.py          # Document parsing
│
├── client/                # TypeScript unified client
│   ├── src/
│   │   ├── index.ts       # Entry point (CLI or MCP mode)
│   │   ├── api/           # HTTP client for API server
│   │   ├── cli/           # CLI commands (Phase 1)
│   │   ├── mcp/           # MCP server mode (Phase 2)
│   │   └── types/         # TypeScript interfaces
│   └── README.md          # Client documentation
│
├── scripts/               # Management scripts
│   ├── setup.sh          # Initial system setup
│   ├── reset.sh          # Clear database and restart
│   ├── kg-cli.sh         # Wrapper for TypeScript CLI
│   └── configure-ai.sh   # Configure AI provider
│
├── mcp-server/           # Legacy MCP server (direct Neo4j)
│   └── src/              # Will migrate to client/src/mcp
│
├── schema/
│   └── init.cypher       # Neo4j schema and indexes
│
├── docs/                 # Documentation
│   ├── README.md         # Documentation index
│   ├── architecture/     # ADRs and design docs
│   ├── guides/          # User and setup guides
│   ├── api/             # API and Cypher query references
│   ├── testing/         # Test coverage specs
│   ├── reference/       # Concept definitions
│   └── development/     # Dev journals and notes
│
└── logs/                 # Application logs
    └── api_*.log         # API server logs
```

## Technology Stack

- **Neo4j 5.15+** - Graph database with vector search
- **FastAPI** - Python REST API server (Phase 1)
- **Python 3.11+** - Ingestion pipeline & API server
- **TypeScript/Node.js 18+** - Unified client (CLI + future MCP)
- **OpenAI / Anthropic** - LLM concept extraction
- **SQLite** - Job queue persistence (Phase 1, will migrate to Redis)
- **Docker Compose** - Infrastructure

## Current Status

**Phase 1 (Current - Working but not production-ready):**
- ✅ FastAPI server with async job queue
- ✅ TypeScript CLI for ingestion & job management
- ✅ Background processing with progress tracking
- ✅ Content-based deduplication (SHA-256)
- ✅ Cost tracking and reporting
- ✅ Logging to files
- ✅ LLM concept extraction (OpenAI & Anthropic)
- ✅ Graph construction with relationships
- ✅ Vector similarity search

**Legacy (Still Functional):**
- ✅ Python CLI for graph querying
- ✅ Direct ingestion via scripts
- ✅ MCP server for Claude Desktop
- ✅ Checkpoint & resume for large documents

**Phase 2 Roadmap:**
- [ ] Redis-based distributed job queue
- [ ] Full API authentication & authorization
- [ ] MCP server mode in unified TypeScript client
- [ ] Graph query endpoints in API
- [ ] Real-time updates (WebSocket/SSE)
- [ ] Rate limiting & request validation

**Future:**
- [ ] Advanced graph algorithms (PageRank, community detection)
- [ ] Web UI for exploration
- [ ] Export to GraphML/JSON
- [ ] Incremental updates (avoid re-processing)

## Contributing

This is an experimental project exploring the boundaries between RAG, knowledge graphs, and LLM-powered extraction. Feedback, issues, and contributions welcome.

## License

[Add your license here]

## Acknowledgments

Built with:
- [Neo4j](https://neo4j.com/) - Graph database platform
- [Model Context Protocol](https://modelcontextprotocol.io/) - LLM integration standard
- [OpenAI](https://openai.com/) / [Anthropic](https://anthropic.com/) - LLM providers

---

*Not just retrieval. Understanding.*
