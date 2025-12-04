# Knowledge Graph System

A concept-level knowledge graph that extracts semantic units from documents and stores them in a queryable graph database.

## The Idea

Meta's Large Concept Models (December 2024) showed that language models can operate on sentence-level semantic representations rather than tokens - predicting the next *concept* autoregressively in embedding space.

This system takes a similar approach but stores concepts in a deterministic structure rather than a neural model:

- **Meta's LCM**: Concepts exist in embedding space; the model predicts the next concept
- **This system**: Concepts exist as graph nodes; relationships are explicit edges; openCypher handles traversal; query facades compute embedding-derived properties (grounding, diversity, similarity) at query time

Both operate above the token level. Meta's is generative; this is a queryable knowledge store backed by PostgreSQL with Apache AGE (a graph extension providing native openCypher support).

## What It Does

When you ingest a document, the system:

1. **Extracts concepts** - Named entities, processes, tools, ideas mentioned in the text
2. **Extracts relationships** - How concepts connect (ENABLES, SUPPORTS, CONTAINS, etc.)
3. **Preserves evidence** - The actual source text that generated each extraction
4. **Stores embeddings** - Vector representations at three levels: concepts, relationships, and evidence

When you query, the system:

1. **Finds concepts by meaning** - Semantic search, not keyword matching
2. **Traverses relationships** - Shows how concepts connect across documents
3. **Computes grounding scores** - Confidence based on supporting vs. contradicting evidence
4. **Links to sources** - Every concept traces back to original text (or images)

The graph accumulates knowledge across documents. Later ingestions match existing concepts by semantic similarity (≥85% threshold) rather than string matching, so "User Authentication" and "Auth System" become the same node if they share semantic space.

## How It Differs from Standard RAG

Standard RAG retrieves text chunks by vector similarity and passes them to an LLM. This works, but:

- **No relationships**: RAG finds similar chunks but doesn't know how they connect
- **No accumulation**: Each query starts fresh; the system doesn't build domain knowledge
- **No confidence signals**: All retrieved chunks are treated as equally valid

This system builds a persistent graph where relationships are explicit, evidence accumulates across documents, and confidence scores reflect the weight of evidence.

## How It Differs from GraphRAG

Microsoft's GraphRAG also builds knowledge graphs from text, but with different design choices:

| Aspect | GraphRAG | This System |
|--------|----------|-------------|
| Updates | Batch community detection | Immediate recursive upsert |
| Summaries | Generated at build time | Computed at query time |
| Truth model | Assumed true | Probabilistic (support/contradiction) |
| Identity | String matching | Semantic similarity (85% threshold) |

## Architecture

### Graph Database

The system uses PostgreSQL with [Apache AGE](https://age.apache.org/), an extension that adds native graph capabilities with openCypher query support. This means:

- Graph traversals execute as database queries, not application code
- Concepts and relationships are first-class graph entities (vertices and edges)
- Complex path queries (find all paths between X and Y within 3 hops) run in the database

### Query Facades

On top of openCypher traversal, query facades compute embedding-derived properties:

- **Similarity** - Vector distance between concept embeddings for semantic search
- **Grounding** - Polarity axis projection across evidence embeddings
- **Diversity** - Entropy calculation over neighbor embedding vectors
- **Evidence retrieval** - Fetching and ranking source text by relevance

The API workers orchestrate this: openCypher returns graph structure, facades compute vector properties, MCP exposes the unified result to agents.

### Three Embedding Layers

The system stores embeddings at three levels, enabling semantic operations throughout:

**Concept nodes** contain:
- Concept name and description
- Embedding vector for semantic matching
- Links to evidence sources

**Relationship edges** contain:
- Relationship type (from an evolving vocabulary)
- Embedding of the relationship type
- Confidence score per instance

**Evidence sources** contain:
- Original extracted text
- Embedding for semantic grounding
- Document reference (file, paragraph, page)
- Original image when extracted from visual content

### Grounding Score Calculation

Rather than classifying relationships as binary "supports" or "contradicts," the system computes continuous grounding scores.

The challenge: SUPPORTS and CONTRADICTS are 81% similar in embedding space, so classification fails. Instead:

1. Define opposing concept pairs (SUPPORTS/CONTRADICTS, ENABLES/PREVENTS)
2. Compute a "polarity axis" from their difference vectors
3. Project each relationship embedding onto this axis

The result is a score from -1.0 (contradicted) to +1.0 (well-supported). A concept with 47 supporting edges and 12 contradicting edges gets grounding ≈ 0.77, reflecting the actual evidence distribution.

### Vocabulary Expansion

The system starts with ~30 seed relationship types. During extraction, the LLM creates new types as needed - FACILITATES, UNDERPINS, CONSTRAINS, whatever the domain requires.

New vocabulary gets:
- **Category** from embedding similarity to seeds (FACILITATES → similar to ENABLES → "causation")
- **Direction** from LLM reasoning (outward: "from acts on to"; inward: "from receives from to")

After ingestion, consolidation merges semantically similar types and prunes unused ones.

### Semantic Diversity

The system measures conceptual diversity by calculating entropy across a concept's neighbor embeddings:

- **High diversity**: Concept connects to physics, geology, engineering, optics
- **Low diversity**: Concept connects only to closely related terms

This metric helps distinguish well-grounded concepts from echo chambers - authentic knowledge tends to connect to diverse independent domains.

## What It Looks Like

### Concept Search

```
$ kg search query "quarterly planning"

Found 6 concepts (threshold: 70%)

## 1. PI/Quarterly Planning
A planning process that occurs every quarter, often involving 
Program Increments in agile frameworks.

Documents: EPOM-Model, Contoso-Apptio
Evidence: 4 instances
Grounding: Weak (0.000, 0%)
Diversity: 43.9% (33 related concepts)
```

### Concept Details

```
$ kg concept details sha256:bfc80_chunk1_814fee0b

## Evidence (4 instances)

1. EPOM-Model (para 1): "Orange arrow: 'PI/Quarterly Planning'"
   [IMAGE AVAILABLE]

2. Contoso-Apptio (para 2): "PI is a planning increment. It used
   to be a programming increment, but they changed the terminology."

3. Contoso-Apptio (para 3): "PI planning, which is a two-day
   ceremony that is pivotal."

## Relationships (3)

ENABLES -> Agile Release Train (90%)
CONTAINS -> Inspect and Adapt Event (90%)
INFLUENCES -> Calendar Management (80%)
```

### Related Concepts

```
$ kg concept related sha256:390f3_chunk1_71a51abb

From: Apptio Targetprocess
Found: 71 concepts

## Distance 1
- Apptio Cost Transparency (PROVIDES)
- Enterprise Agile Planning (CONTAINS)
- Extendable Data Model (ENABLES)
- Strategic Portfolio Management (SUPPORTS -> INTEGRATES)

## Distance 2
- Atlassian Jira (CONNECTED_TO -> CONNECTED_TO)
- ServiceNow CMDB (PROVIDES -> PROVIDES)
- Lean Portfolio Management (CONTAINS -> IMPLEMENTED_BY)
...
```

### Image Evidence

The system extracts concepts from images and preserves the original for verification:

```
$ kg source image sha256:bfc80_chunk1
```

Returns the original slide/diagram that generated the concept, enabling a verification loop: visual inspection → refined description → improved graph.

## Quick Start

### Automated Setup

```bash
./quickstart.sh
```

Interactive script that generates secrets, starts containers, configures defaults, installs the CLI, and prompts for your OpenAI API key.

### Manual Setup

**Prerequisites:** Docker or Podman with Compose

```bash
# 1. Generate secrets
./operator/lib/init-secrets.sh --dev

# 2. Start infrastructure
./operator/lib/start-infra.sh

# 3. Configure
docker exec -it kg-operator python /workspace/operator/configure.py admin
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
docker exec kg-operator python /workspace/operator/configure.py embedding 2
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai

# 4. Start application
./operator/lib/start-app.sh

# 5. Install CLI
cd client && ./install.sh && cd ..

# 6. Ingest and query
kg ingest file document.pdf --ontology "Research"
kg search query "your topic"
```

**Access points:**
- API: http://localhost:8000/docs
- Web UI: http://localhost:3000
- CLI: `kg` commands
- MCP Server: Claude Desktop/Code integration

## Use Cases

**Agent memory** - Store observations and decisions as queryable concepts. Build institutional knowledge that persists across conversations.

**Research synthesis** - Navigate documents by concept relationships. Discover connections across papers. The system merges semantically similar concepts from different sources automatically.

**Technical documentation** - Extract architecture concepts from diagrams, meeting transcripts, design docs. Query how components relate.

**Business analysis** - Track entities and relationships from financial records, meeting notes, customer feedback. The graph accumulates context over time.

## Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 16 + Apache AGE | Graph storage with native openCypher queries |
| API | FastAPI (Python) | Extraction pipeline, openCypher query execution |
| CLI | TypeScript/Node.js | Command-line interface |
| MCP Server | TypeScript | Claude Desktop/Code integration |
| Web UI | React + Vite | Interactive visualization |
| Visualization | D3.js, react-force-graph | Graph rendering |

## Project Structure

```
knowledge-graph-system/
├── src/api/              # FastAPI server + extraction
├── client/               # CLI + MCP server
├── viz-app/              # React visualization
├── operator/             # Configuration management
├── schema/               # Database migrations
└── docs/                 # Documentation (67 ADRs)
```

## Key Design Decisions

The [docs/architecture/](docs/architecture/) directory contains 67 Architecture Decision Records. Notable ones:

- **ADR-044**: Probabilistic truth from contradiction resolution
- **ADR-052**: Vocabulary expansion-consolidation cycle
- **ADR-058**: Polarity axis projection for grounding scores
- **ADR-063**: Semantic diversity as authenticity signal

## Documentation

**📖 [Complete Documentation](https://aaronsb.github.io/knowledge-graph-system/)** - Comprehensive guides, architecture decisions, and API references

- [Quick Start Guide](docs/guides/QUICKSTART.md)
- [Architecture Overview](docs/architecture/ARCHITECTURE_OVERVIEW.md)
- [MCP Setup](docs/manual/03-integration/01-MCP_SETUP.md)
- [AI Providers](docs/manual/02-configuration/01-AI_PROVIDERS.md)
- [Concepts & Terminology](docs/manual/06-reference/04-CONCEPTS_AND_TERMINOLOGY.md)

## Related Research

This system was built independently, then found to align with several research directions. These references explain *why* the design choices work, not where they came from:

**Concept-level modeling** - Meta's Large Concept Models (Barrault et al., 2024) formalized operating above token-level: predicting sentences as semantic units in embedding space. This system stores those units in a graph rather than predicting them, but the abstraction level is similar.

**Knowledge graph embeddings** - TransE (Bordes et al., 2013) and RotatE (Sun et al., 2019) established that relationships can be modeled as geometric operations in embedding space. The polarity axis projection for grounding scores follows this pattern - relationships as vectors, truth as geometry.

**Probabilistic knowledge** - Knowledge Vault (Dong et al., 2014) showed that calibrated confidence scores outperform binary truth labels at scale. The grounding score calculation reflects accumulated evidence rather than asserting facts.

**Semantic uncertainty** - Semantic entropy for hallucination detection (Farquhar et al., 2024) demonstrated that authentic knowledge exhibits different statistical signatures than fabrication. The diversity metric measures something similar - well-grounded concepts connect to diverse domains.

**Evolutionary epistemology** - The vocabulary expansion/consolidation cycle (generate broadly during extraction, prune during consolidation) mirrors BVSR (blind variation, selective retention) from Campbell (1960). This wasn't intentional; it's just what worked.

Full citations are in the [architecture decisions](docs/architecture/).

## License

**Elastic License 2.0**

- ✓ Free for individuals and companies (internal use)
- ✓ Free for product integration
- ✗ Not permitted: offering as a managed service

See [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md) for commercial licensing.

## Acknowledgments

Built with [Apache AGE](https://age.apache.org/), [Model Context Protocol](https://modelcontextprotocol.io/), [FastAPI](https://fastapi.tiangolo.com/), [OpenAI](https://openai.com/), and [Anthropic](https://anthropic.com/).
