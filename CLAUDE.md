# Knowledge Graph System - Claude Development Guide

## Project Overview

A multi-dimensional knowledge extraction system that transforms documents into interconnected concept graphs using Apache AGE (PostgreSQL graph extension).

**Fully Containerized** - no local Python installation required.

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Containers                       │
├─────────────────────────────────────────────────────────────┤
│  Documents → [API Container] → LLM Extraction → [Postgres]  │
│                      ↓                               ↓      │
│              [Garage S3 Storage]         [Apache AGE Graph] │
│                      ↓                               ↓      │
│               [Web Container] ← REST API ← [API Container]  │
│                                                             │
│  Configuration: [Operator Container] → [Postgres Config]    │
└─────────────────────────────────────────────────────────────┘
                            ↑
                   kg CLI (optional)
                   MCP Server (optional)
```

**Tech Stack:**
- Python 3.11+ FastAPI (REST API server)
- Apache AGE / PostgreSQL 16 (graph database, openCypher)
- TypeScript/Node.js (CLI + MCP)
- React/Next.js (web visualization)
- Garage (S3-compatible storage)
- Docker Compose (orchestration)

## Quick Start

**Production deployment** (standalone installer):
```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

**Development setup** (from repo):
```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
./operator.sh init    # Guided setup
./operator.sh start   # Daily start
```

**Optional CLI**:
```bash
cd cli && npm run build && ./install.sh
kg health
```

## Platform Lifecycle

**operator.sh** is the primary management tool (apt-style commands):

```bash
# Updates (pull images, no restart)
./operator.sh update             # Pull all images
./operator.sh update api         # Pull specific service

# Upgrades (pull, migrate, restart)
./operator.sh upgrade            # Full upgrade
./operator.sh upgrade --dry-run  # Preview changes

# Daily operations
./operator.sh start              # Start platform
./operator.sh stop               # Stop platform
./operator.sh status             # Check health
./operator.sh logs api -f        # Follow API logs
./operator.sh shell              # Configuration shell
```

## Contextual Documentation

This project uses **ways** for contextual guidance. When you work with specific areas, relevant documentation loads automatically:

| Area | Trigger | What You Get |
|------|---------|--------------|
| CLI/MCP | `kg `, `cli/src` | Source locations, build commands |
| Operator | `operator.sh`, docker | Container names, common commands |
| API | `api/app/`, routes | Structure, query safety patterns |
| Web | `web/src/`, Zustand | Store patterns, component structure |
| Schema | `schema/`, migrations | Migration patterns, Cypher notes |
| ADR | `ADR-\d` | Key ADRs, index location |

Ways are in `.claude/ways/kg/`.

## Key Concepts

### Concept Extraction Flow

1. Submit document → POST `/ingest`
2. Job created with cost estimate → Requires approval
3. Chunk into ~1000 word segments
4. Extract concepts via LLM (GPT-4/Claude)
5. Match against existing concepts (vector similarity)
6. Upsert to Apache AGE with relationships

### Graph Data Model

```cypher
(:Concept)-[:APPEARS]->(:Source)
(:Concept)-[:EVIDENCED_BY]->(:Instance)
(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS]->(:Concept)
```

### AI Providers

- **OpenAI** - GPT-4o, GPT-4o-mini
- **Anthropic** - Claude Sonnet 4, Claude 3.5 Sonnet
- **Ollama** - Local inference (Mistral, Llama, Qwen)

Configure via: `./operator.sh shell` then `configure.py ai-provider`

## Development → Deployment Flow

**Development (workstation):**
```bash
./operator.sh init        # First time setup
./operator.sh start       # Start platform
# ... develop, test locally ...
git add . && git commit && git push
```

**Release (workstation):**
```bash
# Check auth status and versions
./publish.sh status

# Publish Docker images (api, web)
./publish.sh images -m "Description of changes"

# Publish CLI/MCP to npm
./publish.sh cli

# Publish FUSE driver to PyPI
./publish.sh fuse

# Publish everything
./publish.sh all -m "Release v1.2.3"

# If operator.sh or operator/* changed, rebuild operator too
docker build -t ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest -f operator/Dockerfile .
docker push ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest
```

**Deploy (standalone installs like cube):**
```bash
sudo ./operator.sh upgrade      # Pull images, migrate, restart apps
sudo ./operator.sh self-update  # Update operator container (if needed)
```

**Image registry:** `ghcr.io/aaronsb/knowledge-graph-system/kg-{api,web,operator}`

**Build strategy:** Local builds are faster than GitHub Actions runners. Only the operator container could optionally use remote CI (it's small and changes less frequently), but for speed we build all containers locally and push directly to GHCR.

## Security Notes

**Infrastructure Secrets (`.env`)** - Generated by `./operator.sh init`, never edit manually:
- `ENCRYPTION_KEY` - Fernet key for API key encryption
- `OAUTH_SIGNING_KEY` - JWT signing
- `POSTGRES_PASSWORD` - Database password
- `INTERNAL_KEY_SERVICE_SECRET` - Service auth token

**Application Config** - Stored encrypted in PostgreSQL:
- OpenAI/Anthropic API keys
- Admin passwords

## Resources

- Apache AGE: https://age.apache.org/
- openCypher: https://opencypher.org/
- FastAPI: https://fastapi.tiangolo.com/
- MCP Protocol: https://spec.modelcontextprotocol.io/
- ADR Index: `docs/architecture/ARCHITECTURE_DECISIONS.md`
