# Quick Start Guide

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- OpenAI API key (and optionally Anthropic API key)

## 5-Minute Setup

### 1. Clone and Initialize

```bash
git clone <repository-url>
cd knowledge-graph-system
./scripts/setup.sh
```

This will:
- Start PostgreSQL database with Apache AGE extension
- Create Python virtual environment
- Install dependencies
- Build TypeScript client (CLI + MCP)
- Print Claude Desktop configuration

### 2. Configure AI Provider

```bash
./scripts/configure-ai.sh
```

Choose option 1 to test your current provider (OpenAI by default).

### 3. Ingest Documents

**Single document:**
```bash
./scripts/ingest.sh ingest_source/watts_lecture_1.txt --name "Watts Taoism"
```

**Multiple documents into same ontology:**
```bash
# First document creates the ontology
./scripts/ingest.sh ingest_source/file1.md --name "My Ontology"

# Additional documents contribute to the same conceptual graph
./scripts/ingest.sh ingest_source/file2.md --name "My Ontology"
./scripts/ingest.sh ingest_source/file3.md --name "My Ontology"
```

The `--name` parameter is the ontology name (logical grouping). Each file gets unique source tracking while contributing concepts to the shared ontology.

### 4. Query the Graph

**Via CLI:**
```bash
source venv/bin/activate
python cli.py search "linear thinking"
python cli.py details linear-scanning-system
python cli.py stats
```

**Via PostgreSQL (psql):**
```bash
docker exec -it knowledge-graph-postgres psql -U postgres -d knowledge_graph

# Run openCypher queries via AGE
SELECT * FROM cypher('knowledge_graph', $$
  MATCH (c:Concept) RETURN c.label
$$) as (label agtype) LIMIT 25;
```

## Claude Desktop Integration

### 1. Create OAuth Client for MCP

First, authenticate and create OAuth credentials for Claude Desktop:

```bash
# Login with your admin credentials
kg login

# Create OAuth client for MCP server
kg oauth create-mcp
```

This will display your OAuth credentials and ready-to-paste configuration.

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "kg-mcp-server",
      "env": {
        "KG_OAUTH_CLIENT_ID": "your-client-id-from-above",
        "KG_OAUTH_CLIENT_SECRET": "your-client-secret-from-above",
        "KG_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Note:** OAuth credentials are shown only once. Keep them secure!

### 3. Test the Integration

Restart Claude Desktop, then ask:
- "What concepts are in the knowledge graph about linear thinking?"
- "Find connections between 'human intelligence' and 'genetic intervention'"

## Common Commands

### Management Scripts

```bash
# Check system status
./scripts/status.sh

# Reset database (deletes all data)
./scripts/reset.sh

# Backup database
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh

# Clean up everything
./scripts/teardown.sh
```

### AI Provider Configuration

```bash
# Test providers
./scripts/configure-ai.sh

# Switch to Anthropic (in .env)
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Test
./scripts/configure-ai.sh  # Option 3
```

### CLI Queries

```bash
source venv/bin/activate

# Semantic search
python cli.py search "consciousness" --limit 10

# Concept details
python cli.py details concept-id

# Find relationships
python cli.py related concept-id --depth 2

# Find connections
python cli.py connect from-id to-id

# Ontology management
python cli.py ontology list
python cli.py ontology info "My Ontology"
python cli.py ontology files "My Ontology"

# Database operations
python cli.py database stats
python cli.py database info
python cli.py database health

# Learned knowledge synthesis
python cli.py learn connect concept-id-1 concept-id-2 \
  --evidence "Both emphasize data-driven transparency" \
  --creator your-name
python cli.py learn list
python cli.py learn list --creator aaron
python cli.py learn list --cognitive-leap HIGH
python cli.py learn delete learned_2025-10-06_001

# JSON output for tool integration
python cli.py --json ontology list
python cli.py --json database stats
```

## Database Migrations

The knowledge graph uses a **migration system** to safely evolve the database schema:

```bash
# View current migration status
./scripts/database/migrate-db.sh --dry-run

# Apply pending migrations
./scripts/database/migrate-db.sh -y

# Migrations apply automatically when starting database
./scripts/start-db.sh  # Auto-runs migrate-db.sh
```

**See:** `docs/guides/02-DATABASE_MIGRATIONS.md` for complete guide

## Troubleshooting

### PostgreSQL won't start
```bash
# Check logs
docker logs knowledge-graph-postgres

# Restart
docker-compose restart
```

### Schema migrations pending
```bash
# Check what's pending
./scripts/database/migrate-db.sh --dry-run

# Apply migrations
./scripts/database/migrate-db.sh -y
```

### API key invalid
```bash
# Test provider
./scripts/configure-ai.sh  # Option 1

# Check .env
cat .env | grep API_KEY
```

### Import errors
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
```

### MCP server not appearing in Claude
- Check absolute path in config
- Restart Claude Desktop completely
- Check Claude Desktop logs: `~/Library/Logs/Claude/`

## Next Steps

1. **Read the docs:**
   - `docs/ARCHITECTURE.md` - System design
   - `docs/01-AI_PROVIDERS.md` - AI configuration
   - `docs/MCP_TOOLS.md` - MCP server tools

2. **Ingest your documents:**
   ```bash
   ./scripts/ingest.sh path/to/your/document.txt --name "Document Name"
   ```

3. **Explore the graph:**
   - kg CLI: `kg search query "your query"`
   - PostgreSQL: `docker exec -it knowledge-graph-postgres psql -U postgres -d knowledge_graph`
   - Claude Desktop: Ask questions naturally

4. **Customize:**
   - Modify extraction prompt in `src/api/lib/llm_extractor.py`
   - Add relationship types in `schema/init.sql`
   - Create custom API endpoints in `src/api/routes/`
