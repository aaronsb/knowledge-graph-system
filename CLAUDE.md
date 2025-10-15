# Knowledge Graph System - Claude Development Guide

## Project Overview

A multi-dimensional knowledge extraction system that transforms linear documents into interconnected concept graphs using Apache AGE (PostgreSQL graph extension), enabling semantic exploration beyond sequential reading.

**Key Components:**
- Apache AGE (PostgreSQL) graph database for concept storage
- Modular AI providers (OpenAI GPT-4, Anthropic Claude)
- Python FastAPI server with LLM extraction pipeline
- TypeScript hybrid client (CLI + MCP server)
- REST API for all graph operations

## Architecture

```
Documents → REST API → LLM Extraction → Apache AGE Graph
                ↓
         TypeScript Client (kg CLI + MCP Server)
```

**Tech Stack:**
- Python 3.11+ FastAPI (REST API server + ingestion pipeline)
- Apache AGE / PostgreSQL 16 (graph database using openCypher)
- TypeScript/Node.js (unified CLI + MCP client)
- Docker Compose (infrastructure)
- OpenAI/Anthropic APIs (LLM providers)

**Query Language:**
- **openCypher:** Open-source graph query language implemented by Apache AGE
- **ISO/IEC 39075:2024 GQL:** Standardized graph query language based on openCypher
- **Important:** AGE uses openCypher, not Neo4j's proprietary Cypher implementation
  - This explains syntax differences (e.g., no `ON CREATE SET` / `ON MATCH SET`)
  - See ADR-016 "openCypher Compatibility" section for details

## Important Files

### Configuration
- `.env` - API keys and configuration (gitignored)
- `.env.example` - Configuration template
- `docker-compose.yml` - PostgreSQL + Apache AGE container setup
- `schema/init.sql` - Apache AGE schema initialization

### Core Code (API Server)
- `src/api/main.py` - FastAPI application entry point
- `src/api/lib/ai_providers.py` - Modular AI provider abstraction
- `src/api/lib/llm_extractor.py` - LLM concept extraction
- `src/api/lib/age_client.py` - Apache AGE database operations
- `src/api/lib/ingestion.py` - Ingestion pipeline
- `src/api/routes/` - REST API endpoints (queries, jobs, ontology, admin)

### Core Code (TypeScript Client)
- `client/src/index.ts` - Unified CLI entry point
- `client/src/cli/` - CLI command implementations
- `client/src/api/client.ts` - REST API client
- `client/install.sh` - Installs `kg` command globally

### Management Scripts
- `scripts/start-api.sh` - Start FastAPI server
- `scripts/stop-api.sh` - Stop API server
- `scripts/configure-ai.sh` - AI provider configuration
- `client/install.sh` - Install kg CLI globally

### Documentation
- `docs/README.md` - Documentation index
- `docs/architecture/ARCHITECTURE.md` - System design
- `docs/architecture/ADR-016-apache-age-migration.md` - Apache AGE migration
- `docs/guides/QUICKSTART.md` - Getting started guide
- `docs/guides/AI_PROVIDERS.md` - AI configuration details
- `README.md` - Main documentation

## Development Workflow

### Initial Setup

```bash
# Clone and initialize
git clone <repo>
cd knowledge-graph-system

# Start PostgreSQL + AGE
docker-compose up -d

# Create Python venv and install API dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure AI provider
./scripts/configure-ai.sh

# Start API server
./scripts/start-api.sh

# Install kg CLI globally
cd client && ./install.sh && cd ..
```

### Daily Development

```bash
# Start database (if not running)
docker-compose up -d

# Start API server (if not running)
./scripts/start-api.sh

# Use kg CLI for operations
kg database stats
kg search query "recursive depth"
kg ingest file -o "My Ontology" document.txt

# Check logs
docker logs knowledge-graph-postgres
tail -f logs/api_*.log
```

### Making Changes

**When modifying AI extraction:**
1. Edit `src/api/lib/ai_providers.py` or `src/api/lib/llm_extractor.py`
2. Restart API: `./scripts/stop-api.sh && ./scripts/start-api.sh`
3. Test with: `./scripts/configure-ai.sh` (option 1)
4. Test ingestion: `kg ingest file -o "Test" -y <test-file>`

**When modifying database schema:**
1. Edit `schema/init.sql`
2. Rebuild Docker container: `docker-compose down && docker-compose up -d`
3. Restart API and re-ingest test data

**When modifying API endpoints:**
1. Edit files in `src/api/routes/`
2. Restart API: `./scripts/stop-api.sh && ./scripts/start-api.sh`
3. Test with kg CLI commands

**When modifying kg CLI:**
1. Edit files in `client/src/cli/`
2. Rebuild: `cd client && npm run build`
3. Test: `kg <command>`

**When modifying MCP server:**
1. Edit `client/src/mcp/` (if separate from CLI)
2. Rebuild: `cd client && npm run build`
3. Restart Claude Desktop

## Key Concepts

### Concept Extraction Flow

1. **Submit** document via kg CLI → POST `/ingest` endpoint
2. **Job created** with cost estimate → Requires approval (ADR-014)
3. **Chunk** document into semantic chunks (~1000 words)
4. **Extract** concepts using LLM (GPT-4 or Claude) per chunk
5. **Match** against existing concepts via vector similarity
6. **Upsert** to Apache AGE with relationships
7. **Stream** progress updates via job status endpoint

### Graph Data Model

```cypher
// Nodes
(:Concept {concept_id, label, embedding, search_terms})
(:Source {source_id, document, paragraph, full_text})
(:Instance {instance_id, quote})

// Relationships
(:Concept)-[:APPEARS_IN]->(:Source)
(:Concept)-[:EVIDENCED_BY]->(:Instance)
(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS]->(:Concept)
```

### AI Provider System

**Environment Variables:**
```bash
AI_PROVIDER=openai  # or "anthropic"
OPENAI_API_KEY=sk-...
OPENAI_EXTRACTION_MODEL=gpt-4o  # optional
ANTHROPIC_API_KEY=sk-ant-...  # if using Anthropic
```

**Switching Providers:**
- Set `AI_PROVIDER` in `.env`
- Test with `./scripts/configure-ai.sh`
- Both use OpenAI for embeddings

## Common Tasks

### Add a New AI Provider

1. Create class extending `AIProvider` in `ai_providers.py`
2. Implement required methods:
   - `extract_concepts()`
   - `generate_embedding()`
   - `validate_api_key()`
   - `list_available_models()`
3. Update `get_provider()` factory function
4. Add to documentation

### Add a New API Endpoint

1. Create route handler in `src/api/routes/` (e.g., `queries.py`)
2. Add request/response models in route file
3. Implement AGEClient method in `src/api/lib/age_client.py`
4. Add endpoint to router in `src/api/main.py`
5. Restart API and test with curl or kg CLI

### Add a New kg CLI Command

1. Create command file in `client/src/cli/` (e.g., `search.ts`)
2. Add client method in `client/src/api/client.ts`
3. Register command in `client/src/index.ts`
4. Rebuild: `cd client && npm run build`
5. Test: `kg <new-command>`

### Modify Extraction Logic

1. Edit prompt in `src/api/lib/llm_extractor.py` (EXTRACTION_PROMPT)
2. Adjust JSON schema if needed
3. Update concept matching in `src/api/lib/ingestion.py`
4. Restart API and test with: `kg ingest file -o "Test" -y <test-doc>`

### Add New Relationship Types

1. Add to Cypher queries in `src/api/lib/age_client.py`
2. Update API response models
3. Modify LLM extraction prompt to recognize new type
4. Test with sample ingestion

### Create a New ADR (Architecture Decision Record)

When making significant architectural decisions:

1. Create new ADR file: `docs/architecture/ADR-###-descriptive-name.md`
   - Use the next sequential number (check existing ADRs)
   - Follow the format from existing ADRs
   - Include: Status, Date, Context, Decision, Consequences, Alternatives Considered
2. **IMPORTANT:** Update `docs/architecture/ARCHITECTURE_DECISIONS.md`
   - Add new entry to the ADR Index table with title, status, and brief summary
   - Update "Last Updated" date
   - This file serves as the master index for all ADRs
3. Reference the new ADR in related documentation:
   - Update `docs/README.md` if it's a major user-facing change
   - Link from related ADRs using "Related ADRs" section
   - Update CLAUDE.md if it affects development workflow

## Troubleshooting

### Database Connection Issues
```bash
docker ps  # Check PostgreSQL container running
docker logs knowledge-graph-postgres  # Check logs
docker-compose restart  # Restart database
```

### API Server Issues
```bash
# Check if API is running
curl http://localhost:8000/health

# View API logs
tail -f logs/api_*.log

# Restart API
./scripts/stop-api.sh && ./scripts/start-api.sh
```

### kg CLI Issues
```bash
# Check installation
which kg
kg --version

# Check API connection
kg health

# Reinstall
cd client && ./uninstall.sh && ./install.sh
```

### LLM Extraction Failures
```bash
# Test provider
./scripts/configure-ai.sh

# Check .env
cat .env | grep API_KEY

# View API logs for extraction errors
tail -f logs/api_*.log | grep -i error
```

### MCP Server Not Working
```bash
# Check build
ls -la client/dist/

# Rebuild
cd client && npm run build

# Check Claude config points to correct path
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## Code Style Guidelines

### Python (API Server)
- Use type hints for all functions
- Modular functions (<50 lines)
- Package imports: `from src.api.lib.module import func`
- FastAPI route handlers in `src/api/routes/`
- Environment via `python-dotenv` (.env file)

### TypeScript (kg CLI + MCP)
- Async/await for HTTP API calls
- Type interfaces for API request/response models
- Commander.js for CLI argument parsing
- Error handling with try/catch and colored output
- Axios client for REST API communication

### Shell Scripts
- Use `set -e` for error handling
- Color codes for output clarity (see scripts/start-api.sh)
- Validate prerequisites before running
- Background process management for API server

## Testing Strategy

### Manual Testing
```bash
# Test API health
curl http://localhost:8000/health
kg health

# Test provider
./scripts/configure-ai.sh

# Test ingestion
kg ingest file -o "Test Ontology" -y ingest_source/watts_lecture_1.txt

# Test queries
kg search query "linear thinking"
kg database stats
kg search details <concept-id>
```

### Integration Testing
```bash
# Full pipeline test
docker-compose restart
./scripts/stop-api.sh && ./scripts/start-api.sh
kg ontology delete "Test Ontology"
kg ingest file -o "Test Ontology" -y <test-file>
kg database stats  # Verify counts
```

### MCP Testing
- Build client: `cd client && npm run build`
- Configure in Claude Desktop (point to client/dist/index.js)
- Test each tool through Claude conversation
- Verify graph structure via kg CLI or direct AGE queries

## Performance Considerations

### Ingestion Speed
- LLM calls are slowest part (~2-5s per chunk)
- Job approval workflow (ADR-014) provides cost estimates
- Smart chunking optimizes chunk boundaries (~1000 words)
- Background job processing via FastAPI scheduler

### Query Performance
- Vector search: Python numpy cosine similarity (full scan)
- Graph traversal: AGE Cypher queries, limit depth to avoid explosion
- REST API adds ~10-50ms overhead vs direct DB queries
- Consider pgvector extension for faster vector search at scale

## Security Notes

- **API Keys**: Never commit `.env` (in .gitignore)
- **Database**: PostgreSQL requires auth (env: POSTGRES_USER/POSTGRES_PASSWORD)
- **API Server**: No authentication by default - add if exposing publicly
- **kg CLI**: Communicates with localhost:8000 by default
- **MCP Server**: Runs locally via Claude Desktop, no external exposure
- **Docker**: Containers on isolated network

## Future Enhancements

- [ ] Phrase-based path finding (kg search connect "phrase 1" "phrase 2")
- [ ] Async job queue with Redis/Celery
- [ ] Multi-document batch processing
- [ ] Advanced graph algorithms (PageRank, community detection)
- [ ] 3D graph visualization web UI
- [ ] Export to other formats (GraphML, JSON, CSV)
- [ ] Incremental updates (avoid re-processing)
- [ ] API authentication and rate limiting

## Resources

### Graph Database & Query Language
- Apache AGE: https://age.apache.org/
- AGE Manual: https://age.apache.org/age-manual/master/intro/overview.html
- openCypher: https://opencypher.org/
- ISO/IEC 39075 GQL Standard: https://www.iso.org/standard/76120.html
- openCypher Language Reference: https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf

### Frameworks & APIs
- FastAPI: https://fastapi.tiangolo.com/
- MCP Protocol: https://spec.modelcontextprotocol.io/
- OpenAI API: https://platform.openai.com/docs
- Anthropic API: https://docs.anthropic.com/

## Getting Help

1. Check API health: `kg health` or `curl http://localhost:8000/health`
2. Review `docs/` for detailed documentation
3. Check Docker logs: `docker logs knowledge-graph-postgres`
4. Review API logs: `tail -f logs/api_*.log`
5. Test providers: `./scripts/configure-ai.sh`
