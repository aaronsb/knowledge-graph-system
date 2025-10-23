# 03 - Quick Start: Your First Knowledge Graph

**Part:** I - Foundations
**Reading Time:** ~10 minutes
**Prerequisites:** Docker, Python 3.11+, Node.js 18+, OpenAI API key

---

This guide gets you from zero to a working knowledge graph in about 10 minutes.

## What You'll Do

1. Start the database (PostgreSQL + Apache AGE)
2. Start the API server
3. Install the `kg` CLI tool
4. Ingest a test document
5. Query your first knowledge graph

## Step 1: Start the Database

The system uses PostgreSQL with the Apache AGE graph extension.

```bash
git clone <repository-url>
cd knowledge-graph-system
docker-compose up -d
```

This starts PostgreSQL on port 5432. The database will auto-create the graph schema on first run.

**Verify it's running:**
```bash
docker ps
# You should see: knowledge-graph-postgres
```

## Step 2: Configure API Keys

Create a `.env` file in the project root:

```bash
# AI Provider
AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_EXTRACTION_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database (default values, change if needed)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_graph
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
AGE_GRAPH_NAME=knowledge_graph
```

**Test your configuration:**
```bash
./scripts/configure-ai.sh
# Choose option 1 to test OpenAI connection
```

## Step 3: Start the API Server

The API server processes ingestion requests and handles queries.

```bash
# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start API server
./scripts/start-api.sh
```

The server starts on `http://localhost:8000`.

**Verify it's running:**
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

The API server runs in the background. Check logs:
```bash
tail -f logs/api_*.log
```

## Step 4: Install the CLI

The `kg` command is a TypeScript client that talks to the API server.

```bash
cd client
./install.sh
```

This installs the `kg` command globally.

**Verify installation:**
```bash
kg health
# Should show: API connection successful
```

## Step 5: Ingest Your First Document

Let's ingest a test document to create your first knowledge graph.

```bash
kg ingest file ingest_source/watts_lecture_1.txt --ontology "Test Ontology"
```

This command:
1. Reads the file
2. Submits it to the API server
3. Creates a background job
4. Polls for progress
5. Shows you the results

**What happens during ingestion:**
- Document is split into ~1000-word chunks
- LLM extracts concepts from each chunk
- Concepts are embedded and deduplicated
- Graph nodes and relationships are created
- Evidence quotes are linked to sources

A small document takes 2-5 minutes. You'll see progress updates:

```
Processing chunk 3/12 (25%)
Concepts created: 45
```

When complete, you'll see stats:
```
✓ Ingestion complete!
  Concepts created: 127
  Relationships: 89
  Chunks processed: 12
  Cost: $0.23
  Duration: 3m 42s
```

## Step 6: Query the Graph

Now that you have concepts in the graph, you can query them.

**Search for concepts:**
```bash
kg search query "linear thinking"
```

This shows concepts semantically similar to "linear thinking" with their similarity scores.

**Get concept details:**
```bash
kg search details <concept-id>
```

Replace `<concept-id>` with an ID from the search results. This shows:
- The concept label and search terms
- Related concepts and relationship types
- Evidence quotes with source references

**Check database stats:**
```bash
kg database stats
```

Shows total concepts, relationships, sources, and ontologies in your graph.

**List ontologies:**
```bash
kg ontology list
```

Shows all ontology collections you've created.

## Example Session

Here's a complete workflow:

```bash
# Start services
docker-compose up -d
./scripts/start-api.sh

# Ingest a document
kg ingest file my_document.txt --ontology "My Research"

# Search for a concept
kg search query "machine learning"

# Get details on the top result
kg search details machine-learning-paradigm

# See what you have
kg database stats
kg ontology list
```

## Common Operations

### Ingest Multiple Documents

Add documents to the same ontology to build a larger knowledge base:

```bash
kg ingest file doc1.txt --ontology "Project Docs"
kg ingest file doc2.txt --ontology "Project Docs"
kg ingest file doc3.txt --ontology "Project Docs"
```

Concepts from all three documents merge automatically. If doc1 and doc2 both mention "authentication," they'll link to the same concept node.

### Avoid Duplicate Ingestion

The system deduplicates automatically. If you try to ingest the same file twice:

```bash
kg ingest file doc.txt --ontology "My Docs"
# First time: processes document
kg ingest file doc.txt --ontology "My Docs"
# Second time: returns cached result, no processing
```

To force re-ingestion:
```bash
kg ingest file doc.txt --ontology "My Docs" --force
```

### Check Job Status

Ingestion runs as a background job. If you lose connection, check the job:

```bash
kg jobs list
# Shows recent jobs

kg jobs status <job-id>
# Shows progress for a specific job
```

### Query with Text Input

Instead of a file, you can ingest text directly:

```bash
kg ingest text --ontology "Quick Notes"
# Prompts for text input (paste and hit Ctrl-D when done)
```

Or pipe text:

```bash
echo "Your text content here" | kg ingest text --ontology "Notes"
```

## Troubleshooting

### Database won't start
```bash
docker logs knowledge-graph-postgres
# Check for errors

docker-compose restart
# Try restarting
```

### API server not responding
```bash
tail -f logs/api_*.log
# Check API logs for errors

./scripts/stop-api.sh
./scripts/start-api.sh
# Restart the server
```

### API key errors
```bash
# Test your provider
./scripts/configure-ai.sh

# Check your .env file
cat .env | grep OPENAI_API_KEY
```

### kg command not found
```bash
cd client
./install.sh
# Reinstall CLI

# Or use directly:
cd client
npm run build
node dist/index.js health
```

### Ingestion fails
Check the API logs:
```bash
tail -f logs/api_*.log
```

Common issues:
- Invalid API key
- LLM rate limits
- Malformed document (PDF parsing issues)

## What You've Built

You now have:
- A running graph database (PostgreSQL + AGE)
- An API server processing requests
- A CLI tool for interaction
- One or more documents ingested as concept graphs
- The ability to search and explore relationships

## Next Steps

Learn more about the system:

- **[Section 04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md)**: Deep dive into the graph structure
- **[Section 05 - The Extraction Process](05-the-extraction-process.md)**: How LLMs create concepts
- **[Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)**: All query capabilities

Configure for your needs:

- **[Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md)**: Compare OpenAI, Anthropic, Ollama
- **[Section 10 - AI Extraction Configuration](10-ai-extraction-configuration.md)**: Fine-tune extraction
- **[Section 12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)**: Run completely local

See it in action:

- **[Section 07 - Real World Example](07-real-world-example-project-history.md)**: Project history analysis
- **[Section 60 - Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)**: 280 commits case study

---

← [Previous: System Overview](02-system-overview.md) | [Documentation Index](README.md) | [Next: Understanding Concepts and Relationships →](04-understanding-concepts-and-relationships.md)
