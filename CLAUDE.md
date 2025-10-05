# Knowledge Graph System - Claude Development Guide

## Project Overview

A multi-dimensional knowledge extraction system that transforms linear documents into interconnected concept graphs using Neo4j, enabling semantic exploration beyond sequential reading.

**Key Components:**
- Neo4j graph database for concept storage
- Modular AI providers (OpenAI GPT-4, Anthropic Claude)
- Python ingestion pipeline with LLM extraction
- MCP server for Claude Desktop integration
- CLI tool for direct graph querying

## Architecture

```
Documents → LLM Extraction → Neo4j Graph → Query Interfaces (MCP + CLI)
```

**Tech Stack:**
- Python 3.11+ (ingestion pipeline)
- Neo4j 5.15 (graph database)
- TypeScript/Node.js (MCP server)
- Docker Compose (infrastructure)
- OpenAI/Anthropic APIs (LLM providers)

## Important Files

### Configuration
- `.env` - API keys and configuration (gitignored)
- `.env.example` - Configuration template
- `docker-compose.yml` - Neo4j container setup
- `schema/init.cypher` - Neo4j schema initialization

### Core Code
- `ingest/ai_providers.py` - Modular AI provider abstraction
- `ingest/llm_extractor.py` - LLM concept extraction
- `ingest/neo4j_client.py` - Graph database operations
- `ingest/ingest.py` - Main ingestion pipeline
- `mcp-server/src/index.ts` - MCP server with tools
- `cli.py` - Direct CLI access to graph

### Management Scripts
- `scripts/setup.sh` - Complete system initialization
- `scripts/configure-ai.sh` - AI provider configuration
- `scripts/ingest.sh` - Document ingestion wrapper
- `scripts/status.sh` - System health check
- `scripts/reset.sh` - Database reset
- `scripts/backup.sh` / `restore.sh` - Data backup/restore

### Documentation
- `docs/ARCHITECTURE.md` - System design
- `docs/QUICKSTART.md` - Getting started guide
- `docs/AI_PROVIDERS.md` - AI configuration details
- `README.md` - Main documentation

## Development Workflow

### Initial Setup

```bash
# Clone and initialize
git clone <repo>
cd knowledge-graph-system
./scripts/setup.sh

# Configure AI provider
./scripts/configure-ai.sh

# Check status
./scripts/status.sh
```

### Daily Development

```bash
# Start services (if not running)
docker-compose up -d

# Activate Python environment
source venv/bin/activate

# Run tests/development
python cli.py stats

# Check logs
docker logs knowledge-graph-neo4j
tail -f logs/ingest_*.log
```

### Making Changes

**When modifying AI extraction:**
1. Edit `ingest/ai_providers.py` or `ingest/llm_extractor.py`
2. Test with: `./scripts/configure-ai.sh` (option 1)
3. Test ingestion: `./scripts/ingest.sh <test-file>`

**When modifying database schema:**
1. Edit `schema/init.cypher`
2. Reset database: `./scripts/reset.sh`
3. Re-ingest test data

**When modifying MCP server:**
1. Edit `mcp-server/src/*.ts`
2. Rebuild: `cd mcp-server && npm run build`
3. Restart Claude Desktop

## Key Concepts

### Concept Extraction Flow

1. **Parse** document into paragraphs
2. **Extract** concepts using LLM (GPT-4 or Claude)
3. **Match** against existing concepts via vector similarity
4. **Upsert** to Neo4j with relationships

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

### Add a New MCP Tool

1. Add tool definition in `mcp-server/src/index.ts`
2. Implement handler function
3. Add corresponding database query in `mcp-server/src/neo4j.ts`
4. Rebuild: `npm run build`
5. Restart Claude Desktop

### Modify Extraction Logic

1. Edit prompt in `ingest/llm_extractor.py` (EXTRACTION_PROMPT)
2. Adjust JSON schema if needed
3. Update concept matching in `neo4j_client.py`
4. Test with: `./scripts/ingest.sh <test-doc>`

### Add New Relationship Types

1. Add to enum in `schema/init.cypher`
2. Update MCP tool descriptions
3. Modify LLM extraction prompt to recognize new type
4. Reset database and re-ingest

## Troubleshooting

### Neo4j Connection Issues
```bash
docker ps  # Check container running
docker logs knowledge-graph-neo4j  # Check logs
./scripts/reset.sh  # Nuclear option
```

### Import Errors
```bash
# Check package imports use prefix
from ingest.module import func  # ✓ Correct
from module import func          # ✗ Wrong (circular import)
```

### LLM Extraction Failures
```bash
# Test provider
./scripts/configure-ai.sh

# Check .env
cat .env | grep API_KEY

# View extraction logs
tail -f logs/ingest_*.log
```

### MCP Server Not Working
```bash
# Check build
ls -la mcp-server/build/

# Rebuild
cd mcp-server && npm run build

# Check Claude config path is absolute
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## Code Style Guidelines

### Python
- Use type hints
- Modular functions (<50 lines)
- Package imports: `from ingest.module import func`
- Environment via `python-dotenv`

### TypeScript
- Async/await for database calls
- Type interfaces for data structures
- Error handling with try/catch
- Return structured JSON for MCP tools

### Shell Scripts
- Use `set -e` for error handling
- Color codes for output clarity
- Validate prerequisites before running
- Interactive confirmations for destructive ops

## Testing Strategy

### Manual Testing
```bash
# Test provider
./scripts/configure-ai.sh

# Test ingestion
./scripts/ingest.sh ingest_source/watts_lecture_1.txt

# Test queries
python cli.py search "linear thinking"
python cli.py stats
```

### Integration Testing
```bash
# Full pipeline test
./scripts/reset.sh
./scripts/ingest.sh <test-file>
python cli.py stats  # Verify counts
```

### MCP Testing
- Configure in Claude Desktop
- Test each tool through conversation
- Verify graph structure in Neo4j Browser

## Performance Considerations

### Ingestion Speed
- LLM calls are slowest part (~2-5s per paragraph)
- Vector search is fast with proper indexing
- Batch processing: adjust `--batch-size`

### Query Performance
- Vector search: O(n log n) with IVF index
- Graph traversal: Limit depth to avoid explosion
- Caching: Consider Redis for frequent queries

## Security Notes

- **API Keys**: Never commit `.env` (in .gitignore)
- **Database**: Neo4j requires auth (default: neo4j/password)
- **MCP Server**: Runs locally, no external exposure
- **Docker**: Containers on isolated network

## Future Enhancements

- [ ] Async ingestion with queues
- [ ] Multi-document batch processing
- [ ] Advanced graph algorithms (PageRank, community detection)
- [ ] 3D graph visualization (React + force-graph-3d)
- [ ] Export to other formats (GraphML, JSON)
- [ ] Incremental updates (avoid re-processing)

## Resources

- Neo4j Cypher: https://neo4j.com/docs/cypher-manual/
- MCP Protocol: https://spec.modelcontextprotocol.io/
- OpenAI API: https://platform.openai.com/docs
- Anthropic API: https://docs.anthropic.com/

## Getting Help

1. Check `./scripts/status.sh` for system health
2. Review `docs/` for detailed documentation
3. Check Docker logs: `docker logs knowledge-graph-neo4j`
4. Review ingestion logs in `logs/` directory
5. Test providers: `./scripts/configure-ai.sh`
