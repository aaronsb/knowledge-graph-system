# Knowledge Graph System Architecture

## Overview

The Knowledge Graph System transforms linear documents into interconnected concept graphs, enabling semantic exploration beyond sequential reading.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Ingestion                        │
│  .txt files → Python → LLM Processing → Graph Upsert         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                Neo4j Graph Database                          │
│  • Concepts (nodes with vector embeddings)                   │
│  • Instances (evidence quotes)                               │
│  • Sources (document paragraphs)                             │
│  • Relationships (IMPLIES, SUPPORTS, CONTRADICTS, etc.)      │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    │               │
         ┌──────────▼─────┐  ┌─────▼──────────┐
         │  MCP SERVER    │  │  CLI TOOL      │
         │  (Claude       │  │  (Direct       │
         │   Desktop)     │  │   Access)      │
         └────────────────┘  └────────────────┘
```

## Core Components

### 1. AI Provider Layer (`ingest/ai_providers.py`)

Modular abstraction for LLM providers:

**OpenAI Provider:**
- Extraction: GPT-4o, GPT-4o-mini, o1-preview, o1-mini
- Embeddings: text-embedding-3-small, text-embedding-3-large

**Anthropic Provider:**
- Extraction: Claude Sonnet 4.5, Claude 3.5 Sonnet, Claude 3 Opus
- Embeddings: Delegates to OpenAI (Anthropic doesn't provide embeddings)

### 2. Ingestion Pipeline (`ingest/`)

**Components:**
- `parser.py` - Document parsing (text, PDF, DOCX)
- `llm_extractor.py` - LLM-based concept extraction
- `neo4j_client.py` - Graph database operations
- `ingest.py` - Main orchestration

**Flow:**
1. Parse document → paragraphs
2. For each paragraph:
   - Extract concepts using LLM
   - Generate embeddings
   - Match against existing concepts (vector similarity)
   - Create/update nodes and relationships
   - Store instances (quotes) as evidence

### 3. Graph Database (Neo4j)

**Node Types:**

```cypher
// Concept - Core knowledge unit
(:Concept {
  concept_id: "linear-scanning-system",
  label: "Linear scanning system",
  embedding: [0.123, ...],  // 1536 dims
  search_terms: ["linear thinking", "sequential processing"]
})

// Source - Document location
(:Source {
  source_id: "watts-doc-1-para-4",
  document: "Watts Doc 1",
  paragraph: 4,
  full_text: "..."
})

// Instance - Evidence quote
(:Instance {
  instance_id: "uuid",
  quote: "exact verbatim quote"
})
```

**Relationships:**
- `APPEARS_IN` - Concept → Source
- `EVIDENCED_BY` - Concept → Instance
- `FROM_SOURCE` - Instance → Source
- `IMPLIES` - Concept → Concept (logical implication)
- `CONTRADICTS` - Concept → Concept
- `SUPPORTS` - Concept → Concept
- `PART_OF` - Concept → Concept

### 4. Query Interfaces

**CLI Tool (`cli.py`):**
- Direct database access
- Color-coded output
- Commands: search, details, related, connect, ontology (list/info/files/delete), database (stats/info/health)

**MCP Server (`mcp-server/`):**
- Claude Desktop integration
- Tools: search_concepts, get_concept_details, find_related_concepts, etc.
- Real-time graph exploration through conversation

## Data Flow

### Ingestion Flow

```
Document
  ↓ parse
Paragraphs
  ↓ for each paragraph
  ├→ Extract concepts (LLM)
  │   ├→ concepts: [{id, label, search_terms}]
  │   ├→ instances: [{concept_id, quote}]
  │   └→ relationships: [{from, to, type, confidence}]
  │
  ├→ Generate embeddings (OpenAI)
  │
  ├→ Match existing concepts (vector search)
  │   ├→ similarity > 0.85: use existing
  │   └→ else: create new
  │
  └→ Upsert to Neo4j
      ├→ CREATE/UPDATE concepts
      ├→ CREATE instances
      └→ CREATE relationships
```

### Query Flow

```
User Query
  ↓
Generate embedding
  ↓
Vector similarity search
  ↓
MATCH concepts WHERE similarity > threshold
  ↓
OPTIONAL MATCH related concepts
  ↓
Return structured results
```

## Configuration

### Environment Variables

```bash
# AI Provider Selection
AI_PROVIDER=openai  # or "anthropic"

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_EXTRACTION_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Anthropic (optional)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_EXTRACTION_MODEL=claude-sonnet-4-20250514

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Concept Matching Algorithm

Multi-stage matching to prevent duplicates:

**Stage 1: Exact ID Match**
- LLM predicted existing concept_id → use it
- Confidence: 100%

**Stage 2: Vector Similarity (Primary)**
- Embed: `label + search_terms`
- Cosine similarity search
- Threshold > 0.85 → match
- Confidence: similarity score

**Stage 3: Create New**
- No match found
- Generate new concept_id (kebab-case)

## Scalability Considerations

### Current Design (MVF)
- Single Neo4j instance
- Synchronous processing
- In-memory vector search

### Future Enhancements
- Neo4j cluster for HA
- Async batch processing
- Dedicated vector database (Pinecone, Weaviate)
- Incremental updates
- Caching layer (Redis)

## Security

### API Keys
- Stored in `.env` (gitignored)
- Never committed to version control
- Validated on startup

### Database
- Neo4j auth required (no anonymous access)
- Local development: simple password
- Production: strong auth + TLS

## Testing Strategy

### Unit Tests
- AI provider abstraction
- Concept matching logic
- Graph queries

### Integration Tests
- End-to-end ingestion
- MCP tool functionality
- CLI commands

### Manual Testing
- Use sample Watts documents
- Verify concept extraction quality
- Test relationship accuracy
