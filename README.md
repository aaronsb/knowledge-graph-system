# Knowledge Graph System

A multi-dimensional knowledge extraction system that transforms linear documents into interconnected concept graphs, enabling Claude to understand and traverse ideas beyond sequential reading.

## Prerequisites

Before starting, ensure you have:

- **Docker** (20.10+) - [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose** (2.0+) - [Install Docker Compose](https://docs.docker.com/compose/install/)
- **Python** (3.11+) - [Install Python](https://www.python.org/downloads/)
- **Node.js** (18+) - [Install Node.js](https://nodejs.org/)
- **npm** (9+) - Included with Node.js

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd knowledge-graph-system
   ```

2. **Run the initialization script:**
   ```bash
   ./init.sh
   ```

   The script will:
   - Check all prerequisites
   - Create `.env` file from template
   - Start Neo4j database
   - Initialize database schema
   - Set up Python virtual environment
   - Install and build MCP server

3. **Edit `.env` with your API keys:**
   ```bash
   nano .env
   ```

   Add your keys:
   - `OPENAI_API_KEY` - For embeddings and LLM processing
   - `ANTHROPIC_API_KEY` - For Claude integration

4. **Ingest a test document:**
   ```bash
   source venv/bin/activate
   python ingest/ingest.py docs/watts_lecture_1.txt --document-name "Watts Doc 1"
   ```

5. **Configure Claude Desktop** (see below)

## Claude Desktop Configuration

Add the MCP server to your Claude Desktop configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": [
        "/absolute/path/to/knowledge-graph-system/mcp-server/build/index.js"
      ],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "OPENAI_API_KEY": "your-openai-api-key-here"
      }
    }
  }
}
```

**Important:** Replace `/absolute/path/to/knowledge-graph-system` with your actual project path.

After configuration:
1. Restart Claude Desktop
2. Look for the 🔌 MCP tools icon in the chat interface
3. The knowledge graph tools should be available

## Usage Examples

### Via Command Line (CLI)

The CLI provides direct access to the knowledge graph without needing Claude Desktop. It's useful for:
- Testing and debugging
- Understanding how the system works
- Inspecting query results
- Quick exploration

```bash
# Activate Python environment first
source venv/bin/activate

# Search for concepts
python cli.py search "linear thinking" --limit 5

# Get concept details with evidence
python cli.py details linear-scanning-system

# Find related concepts (graph traversal)
python cli.py related intelligence-limitation --depth 3

# Find connection between concepts
python cli.py connect linear-scanning-system genetic-intervention

# List all documents
python cli.py list-documents

# Show database statistics
python cli.py stats
```

**CLI Commands:**
- `search <query>` - Semantic search for concepts
  - `--limit N` - Max results (default: 10)
  - `--min-similarity X` - Min similarity score (default: 0.7)
- `details <concept-id>` - Show concept with all evidence and relationships
- `related <concept-id>` - Find related concepts via graph traversal
  - `--depth N` - Max traversal depth (default: 2)
  - `--types TYPE1 TYPE2` - Filter by relationship types
- `connect <from-id> <to-id>` - Find shortest path between concepts
  - `--max-hops N` - Max path length (default: 5)
- `list-documents` - List all documents with concept counts
- `stats` - Show database statistics

### Via Claude Desktop

Once configured, you can ask Claude:

**Search for concepts:**
```
"What concepts are related to 'linear scanning'?"
```

**Find connections:**
```
"Show me how 'human intelligence' connects to 'genetic intervention'"
```

**Explore a concept:**
```
"What does the knowledge graph say about 'consciousness'?"
```

**Get evidence:**
```
"Find all quotes about 'limitations of linear thinking'"
```

### Via Neo4j Browser

Access the graph directly:

1. Open: http://localhost:7474
2. Login: `neo4j` / `password`
3. Run queries:

```cypher
// Find all concepts
MATCH (c:Concept) RETURN c LIMIT 25

// Find concept relationships
MATCH (c1:Concept)-[r]->(c2:Concept)
WHERE c1.label CONTAINS 'intelligence'
RETURN c1, r, c2

// Get concept with evidence
MATCH (c:Concept {label: 'linear scanning'})-[:EVIDENCED_BY]->(i:Instance)
RETURN c, i.quote
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Desktop                         │
│                  (User Interface Layer)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                   MCP Server (Node.js)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tools: search_concepts, find_connections,           │  │
│  │         get_concept_evidence, traverse_graph         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │ Cypher Queries
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                    Neo4j Graph Database                     │
│  ┌──────────────┬──────────────────┬───────────────────┐   │
│  │   Concepts   │   Relationships  │   Instances       │   │
│  │   (Nodes)    │    (Edges)       │   (Evidence)      │   │
│  └──────────────┴──────────────────┴───────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      ↑
                      │ Document Ingestion
                      │
┌─────────────────────────────────────────────────────────────┐
│              Python Ingestion Pipeline                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Parse document (TXT/PDF/DOCX)                    │  │
│  │  2. Extract concepts (Claude API)                    │  │
│  │  3. Generate embeddings (OpenAI)                     │  │
│  │  4. Detect relationships (LLM reasoning)             │  │
│  │  5. Store in Neo4j                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

Data Flow:
  Documents → Ingestion → Neo4j → MCP Server → Claude Desktop
```

## Project Structure

```
knowledge-graph-system/
├── init.sh                 # Setup script
├── docker-compose.yml      # Neo4j service definition
├── .env                    # Environment variables (API keys)
│
├── schema/
│   └── init.cypher        # Neo4j schema and constraints
│
├── ingest/
│   ├── ingest.py          # Main ingestion pipeline
│   ├── extractors.py      # Concept extraction logic
│   └── embeddings.py      # Vector embedding generation
│
├── mcp-server/
│   ├── package.json       # Node.js dependencies
│   ├── tsconfig.json      # TypeScript configuration
│   └── src/
│       ├── index.ts       # MCP server entry point
│       ├── tools.ts       # MCP tool definitions
│       └── database.ts    # Neo4j connection
│
└── docs/
    └── watts_lecture_1.txt  # Sample test document
```

## Management Scripts

The `scripts/` directory contains utilities for managing the knowledge graph system:

### Setup & Initialization

```bash
# Initial setup (run once)
./scripts/setup.sh
```

Sets up the entire system:
- Checks prerequisites (Docker, Python, Node.js)
- Creates `.env` from template
- Starts Neo4j database
- Initializes database schema
- Sets up Python virtual environment
- Builds MCP server
- Prints Claude Desktop configuration

### System Status

```bash
# Check system status
./scripts/status.sh
```

Shows:
- Docker container status
- Database connection health
- Node/relationship counts
- Python environment status
- MCP server build status
- Configuration validation
- Disk usage
- Access URLs

### Reset Database

```bash
# Reset database to empty state
./scripts/reset.sh
```

**Warning:** Deletes all graph data!
- Stops containers
- Removes database volumes
- Restarts with fresh database
- Reinitializes schema

### Teardown

```bash
# Clean up system
./scripts/teardown.sh
```

Interactive teardown:
- Stops Docker containers
- Optionally removes data volumes
- Optionally removes Python venv
- Optionally removes node_modules
- Preserves source code and `.env`

### Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh
```

Backup features:
- Exports all graph data to Cypher format
- Saves to `backups/` directory with timestamp
- Preserves environment template (without API keys)

Restore features:
- Lists available backups
- Clears existing data
- Restores selected backup
- Verifies restoration

## Development

### Useful Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f neo4j

# Access Neo4j shell
docker exec -it neo4j-kg cypher-shell -u neo4j -p password

# Activate Python environment
source venv/bin/activate

# Rebuild MCP server
cd mcp-server && npm run build

# Run ingestion with debug output
LOG_LEVEL=DEBUG python ingest/ingest.py docs/your_document.txt
```

### Troubleshooting

**Neo4j won't start:**
- Check if port 7474 or 7687 is already in use: `lsof -i :7474`
- View logs: `docker-compose logs neo4j`
- Reset database: `docker-compose down -v` (WARNING: deletes data)

**MCP server not showing in Claude:**
- Verify the path in `claude_desktop_config.json` is absolute
- Check MCP server built successfully: `ls mcp-server/build/index.js`
- Restart Claude Desktop completely
- Check Claude Desktop logs (macOS: `~/Library/Logs/Claude/`)

**Ingestion fails:**
- Verify API keys in `.env` are correct
- Check Neo4j is running: `docker ps | grep neo4j`
- Test Neo4j connection: `docker exec neo4j cypher-shell -u neo4j -p password "RETURN 1;"`
- Enable debug logging: `LOG_LEVEL=DEBUG python ingest/ingest.py ...`

**Embeddings not working:**
- Verify `OPENAI_API_KEY` is set correctly
- Check API quota/billing: https://platform.openai.com/account/usage
- Try reducing batch size in ingestion script

**Concept deduplication issues:**
- Lower similarity threshold in extraction config
- Check embedding quality (view in Neo4j)
- Manually merge concepts via Cypher:
  ```cypher
  MATCH (c1:Concept {label: 'old'}), (c2:Concept {label: 'new'})
  CALL apoc.refactor.mergeNodes([c1, c2]) YIELD node
  RETURN node
  ```

### Running Tests

```bash
# Python tests
source venv/bin/activate
pytest tests/

# MCP server tests
cd mcp-server
npm test

# Integration test (full pipeline)
./test_pipeline.sh
```

### Adding New Document Types

To support additional document formats:

1. Add parser to `ingest/parsers.py`
2. Register in `ingest/ingest.py`
3. Update `requirements.txt` if needed
4. Test with sample document

### Performance Tuning

**Neo4j:**
- Increase memory: Edit `docker-compose.yml` → `NEO4J_dbms_memory_heap_max__size`
- Add indexes: Create for frequently queried properties
- Monitor: http://localhost:7474 → Database Information

**Ingestion:**
- Batch processing: Use `--batch-size` flag
- Parallel workers: Use `--workers` flag
- Cache embeddings: Enable in config

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/knowledge-graph-system/issues)
- Documentation: [Wiki](https://github.com/yourusername/knowledge-graph-system/wiki)
- Discussions: [GitHub Discussions](https://github.com/yourusername/knowledge-graph-system/discussions)
