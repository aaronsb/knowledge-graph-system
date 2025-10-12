# Knowledge Graph System

**Transform documents into queryable concept networks. Not retrieval - understanding.**

## What This Does

This system extracts concepts and relationships from documents, building a persistent knowledge graph you can explore semantically. Instead of searching for similar text, you discover how ideas connect across your entire corpus.

Feed it research papers, meeting notes, code commits, or philosophical texts. The system identifies concepts, understands their relationships, and preserves evidence trails back to source material. Query by meaning, not keywords. Traverse connections between ideas, not just similarity scores.

**The difference matters:** Traditional RAG retrieves text chunks that match your query. Knowledge graphs reveal how concepts *relate* - what enables what, what contradicts what, what emerges from what. The graph grows smarter with each document, automatically connecting new concepts to existing knowledge.

**Built on:** Apache AGE (PostgreSQL graph extension), FastAPI REST architecture, modular LLM providers (OpenAI/Anthropic), TypeScript client tooling, and Model Context Protocol integration.

## How It Works

Documents flow through smart chunking that respects natural boundaries
  ↓
LLM extraction identifies concepts, relationships, and evidence quotes
  ↓
Graph construction in PostgreSQL with Apache AGE extension
  ↓
Vector embeddings enable semantic search across concepts
  ↓
Query interface reveals connections and provides provenance

**The iterative pattern:** Each chunk queries recent concepts before processing. The LLM sees what the graph already knows, enabling cross-chunk relationship detection. Early chunks populate the graph. Later chunks connect to existing concepts. Hit rates climb from 0% to 60%+ as the graph learns your domain.

**Multi-document synthesis:** Concepts automatically merge across files when semantically similar. A term mentioned in chapter 1 links to the same concept in chapter 10, even across different documents in the same ontology.

## Why This Matters

You've invested time (and API tokens) extracting knowledge from documents. Traditional systems rebuild that understanding on every query. This system *remembers*.

**Persistent concept extraction** → Ideas become first-class entities with labels, search terms, and relationships

**Relationship modeling** → Concepts ENABLE, SUPPORT, CONTRADICT, IMPLY each other with confidence scores

**Graph traversal** → Explore connections between ideas across document boundaries

**Evidence provenance** → Every concept links to source quotes with paragraph references

**Cross-ontology enrichment** → Ingest related documents into different ontologies; shared concepts bridge them naturally

**Time as emergent property** → Causal relationships (CAUSES, RESULTS_FROM, ENABLES) create observable time arrows without explicit timestamps

## Quick Start

**Prerequisites:** Docker, Python 3.11+, Node.js 18+

```bash
# 1. Setup infrastructure
./scripts/setup.sh

# 2. Configure AI provider
./scripts/configure-ai.sh

# 3. Start API server
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8000

# 4. Install TypeScript client
cd client && npm install && npm run build && ./install.sh && cd ..

# 5. Ingest documents
kg ingest file document.txt --ontology "My Research"

# 6. Query concepts
kg search query "recursive patterns"
kg ontology list
kg database stats
```

**For Claude Desktop/Code integration:** See [MCP Setup Guide](docs/guides/MCP_SETUP.md)

## Live Example

After ingesting project commit history and pull requests into separate ontologies:

```bash
# Search across both ontologies
kg search query "Apache AGE migration"

# Result: "Apache AGE Migration" concept
#   - 6 evidence instances
#   - Found in: "Knowledge Graph Project History" (commits)
#   - Found in: "Knowledge Graph Project Pull Requests" (PRs)
#   - Relationships:
#       ENABLES → RBAC Capabilities
#       PREVENTS → Dual Database Complexity
#       RESULTS_FROM → Unified Architecture
```

The system understood commits and PRs describe the same architectural change from different perspectives. It merged evidence, enriched relationships, and revealed the strategic narrative without explicit linking.

## When To Use This

**Research exploration** → Navigate philosophical texts by concept relationships, not linear reading

**Codebase understanding** → Trace architectural decisions across commits, PRs, and documentation

**Meeting analysis** → Extract action items, decisions, and dependencies across discussion threads

**Knowledge synthesis** → Discover connections between documents you didn't know were related

**Historical reconstruction** → Build timelines from causal relationships (CAUSES, PRECEDES, EVOLVES_INTO)

**Financial analysis** → Track entities and relationships across transaction records

**Travel journals** → Map locations, experiences, and insights across trip logs

The pattern generalizes: any structured record content can become a queryable knowledge graph.

## Architecture Highlights

- **Apache AGE (PostgreSQL extension)** - Graph database with openCypher query support and production RBAC
- **Unified PostgreSQL architecture** - Graph data, job queue, and application state in one database
- **Job approval workflow** - Pre-ingestion cost estimates, manual or auto-approval, lifecycle management
- **Modular AI providers** - Swap between OpenAI, Anthropic, or implement custom extractors
- **Content deduplication** - SHA-256 hashing prevents reprocessing identical documents
- **Ontology management** - Group related documents; rename or delete with cascading job cleanup
- **Vector search + graph traversal** - Semantic similarity finds concepts, relationships explain connections
- **Evidence preservation** - Every concept links to source quotes with document and paragraph references
- **TypeScript client** - Unified CLI and future MCP server mode for multi-agent access
- **Dry-run capabilities** - Preview ingestion operations before committing API tokens

## What Makes This Different

Not a vector database. Not a new embedding model. A synthesis:

**LLM-powered extraction** → Understands concepts and relationships, not just word patterns

**Graph storage** → Models how ideas connect, not just where they appear

**Evidence-based retrieval** → Provides source quotes with provenance, not isolated chunks

**Persistent knowledge** → Builds understanding over time, not ephemeral query-time synthesis

**Multi-dimensional querying** → Semantic search finds concepts, graph traversal explains relationships

**Emergent temporal structure** → Causal relationships create observable time arrows without explicit ordering

## Technology Stack

- **PostgreSQL 16 + Apache AGE** - Graph database with openCypher support
- **FastAPI** - Async REST API server with job queue
- **Python 3.11+** - Ingestion pipeline, LLM extraction, graph operations
- **TypeScript/Node.js 18+** - Unified client (CLI + future MCP mode)
- **OpenAI / Anthropic** - Modular LLM provider abstraction
- **Docker Compose** - Infrastructure orchestration

## Current Status

**Working (Phase 1):**
- ✅ Apache AGE graph database with vector search
- ✅ FastAPI REST API with async job queue
- ✅ TypeScript CLI (`kg` command)
- ✅ Background processing with progress tracking
- ✅ Content-based deduplication (SHA-256)
- ✅ Cost tracking and pre-ingestion estimates
- ✅ Job approval workflow with auto-approve option
- ✅ Ontology management (create, rename, delete with cascade)
- ✅ Dry-run mode for directory ingestion

**Planned (Phase 2):**
- [ ] MCP server mode in unified TypeScript client
- [ ] Graph query endpoints in API
- [ ] Real-time updates (WebSocket/SSE)
- [ ] API authentication & authorization
- [ ] Rate limiting & request validation

**Future Explorations:**
- [ ] Advanced graph algorithms (PageRank, community detection)
- [ ] Web UI for visual graph exploration
- [ ] Export to GraphML/JSON formats
- [ ] Incremental updates (avoid reprocessing)
- [ ] Phrase-based path finding between concepts

## Learn More

Navigate the documentation by purpose:

**Getting Started:**
- [Quick Start Guide](docs/guides/QUICKSTART.md) - Get running in 5 minutes
- [MCP Setup Guide](docs/guides/MCP_SETUP.md) - Claude Desktop/Code integration
- [AI Provider Configuration](docs/guides/AI_PROVIDERS.md) - OpenAI, Anthropic, or custom

**Understanding the System:**
- [Architecture Overview](docs/architecture/ARCHITECTURE.md) - How components fit together
- [Concept Deep Dive](docs/reference/CONCEPT.md) - Why knowledge graphs vs RAG
- [Enrichment Journey](docs/reference/ENRICHMENT_JOURNEY.md) - How the graph learns from multiple perspectives
- [Concepts & Terminology](docs/reference/CONCEPTS_AND_TERMINOLOGY.md) - Ontologies, stitching, pruning, integrity

**Using the System:**
- [Examples & Demos](docs/guides/EXAMPLES.md) - Real queries with actual results
- [Backup & Restore](docs/guides/BACKUP_RESTORE.md) - Protecting your token investment
- [Documentation Index](docs/README.md) - Browse all documentation by category

**Technical Details:**
- [ADR-016: Apache AGE Migration](docs/architecture/ADR-016-apache-age-migration.md) - Why PostgreSQL + AGE
- [ADR-014: Job Approval Workflow](docs/architecture/ADR-014-job-approval-workflow.md) - Ingestion lifecycle
- [Development Guide](CLAUDE.md) - For contributors and developers

## Project Structure

```
knowledge-graph-system/
├── src/api/              # FastAPI REST server
│   ├── lib/              # Shared ingestion library
│   │   ├── ai_providers.py    # Modular LLM abstraction
│   │   ├── llm_extractor.py   # Concept extraction
│   │   ├── age_client.py      # Apache AGE operations
│   │   └── ingestion.py       # Chunk processing
│   ├── routes/           # REST API endpoints
│   ├── services/         # Job queue, scheduler, deduplication
│   └── workers/          # Background ingestion workers
│
├── client/               # TypeScript unified client
│   └── src/
│       ├── cli/          # CLI commands
│       ├── api/          # HTTP client
│       └── mcp/          # MCP server mode (future)
│
├── scripts/              # Management utilities
│   ├── setup.sh          # Infrastructure setup
│   ├── start-api.sh      # Start API server
│   └── configure-ai.sh   # AI provider config
│
├── schema/
│   └── init.sql          # Apache AGE schema
│
└── docs/                 # Documentation
    ├── architecture/     # ADRs and design
    ├── guides/          # User guides
    ├── reference/       # Concepts and terminology
    └── development/     # Dev journals
```

## Contributing

This is an experimental exploration of knowledge graphs, LLM extraction, and semantic understanding. Feedback, issues, and contributions welcome.

## Acknowledgments

Built with:
- [Apache AGE](https://age.apache.org/) - PostgreSQL graph extension
- [Model Context Protocol](https://modelcontextprotocol.io/) - LLM integration standard
- [OpenAI](https://openai.com/) / [Anthropic](https://anthropic.com/) - LLM providers
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python API framework

---

*Not just retrieval. Understanding.*
