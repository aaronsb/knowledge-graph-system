# Knowledge Graph System

## What It Does

Converts documents and images into a graph where concepts are nodes and relationships are edges. LLMs extract both from your content. The graph stores them in PostgreSQL with Apache AGE. You query by meaning, traverse by relationships, and trace back to source material.

**TLDR:**
```bash
# Put text documents in
kg ingest file research_paper.pdf --ontology "Research"

# Put images in (vision model generates descriptions → concepts)
kg ingest file whiteboard_diagram.jpg --ontology "Research"

# Get concepts out, with relationships
kg search query "recursive patterns"
# Returns: Concepts with ENABLES, SUPPORTS, CONTRADICTS relationships

# See how they connect across documents and images
kg search details concept-id-123
# Shows: Evidence quotes, source locations, related concepts
```

**Four components:**
1. **Apache AGE + PostgreSQL** - Graph storage with openCypher queries, vector embeddings, RBAC
2. **FastAPI REST API** - Extraction pipeline with job management and cost estimates
3. **TypeScript CLI + MCP Server** - Command-line interface and agent integration
4. **React Visualization** - Interactive graph exploration with multiple query modes

**Multimodal ingestion:**
- **Text sources** - Research papers, meeting notes, code commits, documentation, lecture transcripts
- **Image sources** - Whiteboard photos, diagrams, screenshots, slides, charts
- **Processing flow** - Images → S3 storage (Garage) → Vision model description → Concept extraction pipeline
- **Storage architecture** - Original images in S3-compatible object storage, descriptions and concepts in PostgreSQL
- **Ground truth preservation** - Vision descriptions are derived evidence; original images remain queryable via S3 URLs

Images and text flow into the same concept graph. A whiteboard photo from a brainstorming session connects to meeting notes from the same project. Lecture slides link to transcripts. Cross-modal discovery through shared concepts.

## How It Works

---

📚 **[Read the full documentation →](https://aaronsb.github.io/knowledge-graph-system/)**

Complete guides, architecture decisions, and API reference hosted on GitHub Pages.

---

## Visual Overview

### Interactive Graph Visualization

Explore concept relationships through interactive force-directed graphs with advanced visual features including 3D-style shadows, dynamic legend, context menus, and real-time node information.

![Force Graph 2D Advanced Features](docs/media/screenshots/force_graph_2d_advanced_features.png)

*Force-directed graph with 3D shadows, reference grid, nested context menus, collapsible legend, and interactive info boxes showing concept details and relationships.*

Search semantically, find paths between ideas, and visualize how knowledge connects across your corpus.

![Concept Pathing and Compounding](docs/media/screenshots/concept_pathing_and_compounding.png)

*Finding paths between concepts and exploring relationship neighborhoods reveals how ideas connect across documents.*

### Multiple Query Interfaces

**Smart Search** - Semantic concept search with similarity tuning and neighborhood exploration

![Smart Search](docs/media/screenshots/smart_search.png)

**Visual Query Builder** - Drag-and-drop block-based openCypher query construction

![Visual Query Builder](docs/media/screenshots/visual_opencypher_query_builder.png)

**Direct openCypher** - Write openCypher queries directly for advanced graph traversal

![openCypher Editor](docs/media/screenshots/bare_opencypher_query.png)

### Command-Line Interface

Full-featured CLI for ingestion, querying, and system management.

![Command Line Interface](docs/media/screenshots/command_line.png)

### REST API Documentation

Interactive API documentation with OpenAPI (Swagger) and ReDoc interfaces.

![ReDoc API Documentation](docs/media/screenshots/redoc-api-doc.png)

### MCP Server Integration

Connect to Claude Desktop or Claude Code for agent-driven graph operations.

![MCP Server Tools](docs/media/screenshots/mcp_server.png)

### Ingestion Pipeline

Documents split into chunks at semantic boundaries. Each chunk:

1. **Queries recent concepts** - LLM sees what the graph already knows
2. **Extracts new concepts** - Identifies ideas and relationships from text
3. **Generates embeddings** - Vector representations for similarity matching
4. **Matches existing concepts** - Cosine similarity ≥0.85 merges with existing nodes
5. **Stores with evidence** - Creates nodes, edges, and preserves source quotes

Early chunks populate the graph from scratch. Later chunks match existing concepts and add new relationships. Hit rates climb from 0% to 60%+ as the graph learns your domain.

Concepts merge across documents when semantically similar. A term in chapter 1 connects to the same concept in chapter 10, even across files in the same ontology.

### How Concepts Govern Themselves

The graph tracks evidence for each concept through relationship edges:

**Grounding strength** - Calculated from incoming edges at query time:
```
Concept "System uses Apache AGE":
  ← 47 SUPPORTS edges (weight: 33.8)
  ← 12 CONTRADICTS edges (weight: 10.2)
  → Grounding: 33.8 / 44.0 = 76.8% (well-grounded)

Concept "System uses Neo4j":
  ← 12 SUPPORTS edges (weight: 10.2)
  ← 47 CONTRADICTS edges (weight: 33.8)
  → Grounding: 10.2 / 44.0 = 23.2% (weakly-grounded)
```

Filter queries by grounding threshold:
- `≥ 80%` - High confidence (production use)
- `≥ 50%` - Medium confidence (general use)
- `≥ 20%` - Low confidence (exploratory)
- `< 20%` - Contradicted (review needed)

As documents evolve, grounding shifts automatically. When you ingest updated documentation, contradiction edges accumulate and grounding scores adjust. No manual curation needed.

### How Vocabulary Learns

The system starts with 30 seed relationship types (ENABLES, SUPPORTS, CONTRADICTS, etc.). LLMs create new types as needed during extraction.

**New vocabulary gets three properties:**

1. **Category** (computed from embeddings):
```
"FACILITATES" → Compare to seed types
  → Most similar to "ENABLES" (causation category)
  → Assign category: "causation"
```

2. **Confidence** (per relationship, LLM-determined):
```
"Meditation FACILITATES enlightenment" → confidence: 0.85
```

3. **Direction** (per type, LLM reasoning):
```
"FACILITATES" → LLM reasons: "meditation acts on enlightenment"
  → direction: "outward" (from acts on to)
```

Vocabulary patterns emerge over time. After 100 documents, the system learns "*_FROM suffix → usually inward direction" through statistical observation of LLM choices.

### How It Scales

**Evidence accumulation** - Each document adds edges without reprocessing existing concepts. A concept mentioned in 50 documents has 50 evidence links, strengthening or weakening its grounding.

**Vocabulary convergence** - Custom types with high usage survive. Low-usage types with <20% grounding get filtered. The vocabulary naturally compacts to high-value relationships.

**Query-time calculation** - Grounding strength computes from current edge weights, not stored snapshots. The graph always reflects latest evidence without batch recalculation jobs.

**Bounded computation** - Grounding uses direct edges only (depth=1). Relationship traversal limits to 3 hops. Performance stays consistent as the graph grows to millions of concepts.

## What You Get

**Concepts as entities** - Ideas become first-class nodes with labels, search terms, embeddings, and grounding scores. Query them, traverse from them, filter by reliability.

**Relationships with semantics** - 30 base types (ENABLES, SUPPORTS, CONTRADICTS, IMPLIES, etc.) plus custom vocabulary the LLM creates. Each edge has category, confidence, and direction.

**Evidence preservation** - Every concept links to source quotes with document name, paragraph number, and full text. Trace claims back to original context.

**Cross-document synthesis** - A concept mentioned in 20 files has 20 evidence nodes, all connected. Query once, see all occurrences.

**Emergent temporal structure** - Causal relationships (CAUSES, RESULTS_FROM, ENABLES, PRECEDES) create observable time arrows. No timestamps needed; time emerges from graph topology.

**Grounding scores** - See which concepts have strong vs weak evidence. Filter by confidence threshold. Watch truth shift as documents evolve.

## Quick Start

**Prerequisites:** Docker or Podman with Compose, (optional) Node.js 18+ for kg CLI

```bash
# 1. Generate infrastructure secrets (encryption keys, database password, etc.)
./operator/lib/init-secrets.sh --dev

# 2. Start infrastructure (PostgreSQL + Garage storage + operator container)
./operator/lib/start-infra.sh

# 3. Configure via operator container (no local Python needed!)
docker exec -it kg-operator python /workspace/operator/configure.py admin
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
docker exec kg-operator python /workspace/operator/configure.py embedding 2  # Activate local embeddings
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai

# 4. Start application containers (API + web UI)
./operator/lib/start-app.sh
# API docs: http://localhost:8000/docs
# Web UI: http://localhost:3000

# 5. Install TypeScript CLI (optional, for command-line convenience)
cd cli && ./install.sh && cd ..

# 6. Ingest documents
kg ingest file document.txt --ontology "My Research"

# 7. Query concepts
kg search query "recursive patterns"
kg ontology list
kg database stats
```

**Three ways to explore your graph:**
- **CLI:** Use `kg` commands for querying and management
- **Visualization Explorer:** Open http://localhost:3000 for interactive graph exploration
- **MCP Server:** Connect via Claude Desktop/Code - See [MCP Setup Guide](docs/guides/MCP_SETUP.md)

### Container Images

Pre-built container images are available from GitHub Container Registry:

```bash
# Use published images instead of building locally
cd docker
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d

# Or pull specific versions
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-web:latest
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest
```

**Available tags:**
- `latest` - Most recent build from main branch (always stable)
- `1.2.3` - Specific release versions
- `1.2` - Latest patch for major.minor version

**Works with both Docker and Podman!** See [Container Images Guide](docs/guides/CONTAINER_IMAGES.md) for versioning, releases, and deployment options.

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

Embedding similarity matched "Apache AGE Migration" across both ontologies (commits ≥0.85 similarity to PRs). The graph merged evidence and connected relationships. Same concept, different perspectives.

## When To Use This

### Core Use Cases

**🤖 Agent Memory System**
- Persistent memory for AI agents across sessions and conversations
- Store observations, decisions, and learned patterns as queryable concepts
- Retrieve context by semantic meaning or relationship traversal
- Build institutional knowledge that doesn't reset with each chat

**⚙️ CI/CD Intelligence**
- Add to GitHub Actions pipeline to analyze every commit and pull request
- Build rational concept understanding of architectural changes over time
- Discover what features enable what capabilities, what fixes prevent what bugs
- Create living documentation that evolves with your codebase

**📚 Research & Knowledge Work**
- Navigate philosophical texts by concept relationships, not linear reading
- Discover connections between documents you didn't know were related
- Build timelines from causal relationships (CAUSES, PRECEDES, EVOLVES_INTO)
- Synthesize insights across your entire corpus

**💼 Business & Analysis**
- Extract action items, decisions, and dependencies across meeting threads
- Track entities and relationships in financial records
- Map customer feedback to feature requests and product improvements
- Build knowledge bases that grow smarter with each document

The pattern generalizes: any text-based content can become a queryable knowledge graph with relationship-based understanding.

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

## Key Mechanisms

**LLM-powered extraction** - Understands concepts and relationships from text. Generates embeddings for semantic matching. Creates custom vocabulary as needed.

**Graph storage** - Apache AGE stores concepts, relationships, and evidence as nodes and edges. OpenCypher queries traverse connections. Vector search finds similar concepts.

**Evidence-based retrieval** - Each concept links to source quotes with document references. Trace claims back to paragraphs. Verify with original text.

**Persistent knowledge** - The graph accumulates across documents. Early ingestions populate. Later ingestions connect. No rebuilding on every query.

**Multi-dimensional querying** - Search by embedding similarity. Traverse by relationship type. Filter by grounding threshold. Combine all three in one query.

**Self-governing vocabulary** - Relationships get categories from embedding similarity. Directions from LLM reasoning. Grounding from evidence accumulation. Patterns emerge through usage.

## Technology Stack

- **PostgreSQL 16 + Apache AGE** - Graph database with openCypher support and production RBAC
- **FastAPI** - Async REST API server with job queue and lifecycle management
- **Python 3.11+** - Ingestion pipeline, LLM extraction, graph operations
- **TypeScript/Node.js 18+** - Unified client (CLI + MCP server mode)
- **React + Vite** - Interactive visualization explorer with force-directed graphs
- **React Flow** - Visual query builder with drag-and-drop blocks
- **D3.js / react-force-graph** - 2D/3D/VR graph visualizations
- **OpenAI / Anthropic** - Modular LLM provider abstraction
- **Docker Compose** - Infrastructure orchestration

## System Features

### Production-Ready Infrastructure

**Job Management** - Comprehensive ingestion lifecycle with cost controls and progress tracking

![Job Management](docs/media/screenshots/jobs-management.png)

**RBAC & Administration** - Role-based access control, backup/restore, and scheduled operations

![Administrative Features](docs/media/screenshots/administrative-backups-restore-scheduler-user-rbac.png)

**Custom Vocabularies** - Define domain-specific relationship types and reduce catastrophic forgetting

![Custom Edge Vocabulary](docs/media/screenshots/custom_edge_vocabulary.png)

### Current Status

**✅ Completed (Phase 1 & 2):**
- Apache AGE graph database with vector search and openCypher queries
- FastAPI REST API with async job queue and lifecycle management
- TypeScript CLI (`kg` command) with full ingestion and query capabilities
- MCP server mode for Claude Desktop/Code integration
- React visualization explorer with multiple query modes
- Interactive graph visualization (force-directed, 2D/3D, VR)
- Visual query builder (drag-and-drop openCypher construction)
- Smart search with semantic similarity and path finding
- Background processing with progress tracking and cost estimates
- Content-based deduplication (SHA-256)
- Job approval workflow with auto-approve option
- Ontology management (create, rename, delete with cascade)
- Custom relationship vocabulary system
- Production RBAC with user/role management
- Backup, restore, and scheduled operations

**🚀 Future Explorations:**
- Advanced graph algorithms (PageRank, community detection)
- Real-time updates (WebSocket/SSE for live collaboration)
- Export to GraphML/JSON/CSV formats
- Incremental updates (avoid reprocessing identical content)
- Multi-language support for extraction
- API authentication & rate limiting for public deployment

## Learn More

Navigate the documentation by purpose:

**Getting Started:**
- [Quick Start Guide](docs/guides/QUICKSTART.md) - Operator architecture setup in 10 minutes
- [MCP Setup Guide](docs/manual/03-integration/01-MCP_SETUP.md) - Claude Desktop/Code integration
- [AI Provider Configuration](docs/manual/02-configuration/01-AI_PROVIDERS.md) - OpenAI, Anthropic, or custom

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
│       └── mcp/          # MCP server mode
│
├── viz-app/              # React visualization explorer
│   └── src/
│       ├── components/   # UI components
│       │   ├── blocks/   # Visual query builder
│       │   ├── layout/   # App layout and navigation
│       │   └── shared/   # Reusable components
│       ├── explorers/    # Visualization plugins (2D/3D/VR)
│       ├── hooks/        # React hooks for data fetching
│       ├── lib/          # Block compiler, utilities
│       └── store/        # Zustand state management
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
    ├── media/           # Screenshots and diagrams
    └── development/     # Dev journals
```

## Contributing

This is an experimental exploration of knowledge graphs, LLM extraction, and semantic understanding. Feedback, issues, and contributions welcome.

## License

This project is licensed under the **Elastic License 2.0**.

### What This Means

✅ **Free for individuals** - Homelab, learning, experimentation
✅ **Free for companies** - Internal use at any scale
✅ **Free for product integration** - Incorporate into your own products

❌ **Not permitted** - Offering as "Knowledge Graph as a Service" to third parties for a fee

### When You Need a Commercial License

If you want to provide the Knowledge Graph System as a managed service or SaaS offering to third parties, you'll need a commercial license.

For commercial licensing inquiries, see [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md) or contact the repository owner.

### Why This License

The goal is to keep this platform accessible for learning, experimentation, and internal business use while preventing silent appropriation by commercial platforms. If you're building something valuable with this system and want to offer it as a service, let's talk about how to make that work fairly.

## Acknowledgments

Built with:
- [Apache AGE](https://age.apache.org/) - PostgreSQL graph extension
- [Model Context Protocol](https://modelcontextprotocol.io/) - LLM integration standard
- [OpenAI](https://openai.com/) / [Anthropic](https://anthropic.com/) - LLM providers
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python API framework
