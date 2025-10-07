# Knowledge Graph Ingestion Pipeline

Python-based document ingestion system for Neo4j knowledge graphs with LLM-powered concept extraction.

## Architecture

The ingestion pipeline processes text documents through the following stages:

1. **Parsing** (`parser.py`): Splits documents into paragraphs
2. **Source Creation** (`neo4j_client.py`): Creates Source nodes in Neo4j
3. **Concept Extraction** (`llm_extractor.py`): Uses Claude to extract concepts, instances, and relationships
4. **Embedding Generation** (`llm_extractor.py`): Generates vector embeddings with OpenAI
5. **Vector Search** (`neo4j_client.py`): Finds similar existing concepts
6. **Graph Construction** (`neo4j_client.py`): Creates nodes and relationships

## Graph Model

### Nodes
- **Source**: Document paragraphs with metadata
- **Concept**: Extracted ideas/entities with embeddings
- **Instance**: Specific quotes evidencing concepts

### Relationships
- **APPEARS_IN**: Concept → Source
- **EVIDENCED_BY**: Concept → Instance
- **FROM_SOURCE**: Instance → Source
- **IMPLIES/CONTRADICTS/SUPPORTS/PART_OF**: Concept → Concept

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (copy `.env.example` to `.env`):
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password

   ANTHROPIC_API_KEY=your_key
   OPENAI_API_KEY=your_key
   ```

3. **Start Neo4j** (if using Docker):
   ```bash
   docker-compose up -d
   ```

## Usage

```bash
python ingest/ingest.py <filepath> --document-name "Document Name"
```

### Example

```bash
python ingest/ingest.py ./docs/philosophy.txt --document-name "Philosophy Notes"
```

## Module Details

### `parser.py`
- **Function**: `parse_text_file(filepath) -> List[str]`
- Splits text on double newlines
- Returns cleaned paragraph list

### `neo4j_client.py`
- **Class**: `Neo4jClient`
- **Methods**:
  - `create_source_node()`: Create Source nodes
  - `create_concept_node()`: Create Concept nodes with embeddings
  - `create_instance_node()`: Create Instance nodes
  - `link_concept_to_source()`: APPEARS_IN relationship
  - `link_instance_to_concept_and_source()`: EVIDENCED_BY + FROM_SOURCE
  - `create_concept_relationship()`: Concept-Concept relationships
  - `vector_search()`: Similarity search (threshold=0.85)

### `llm_extractor.py`
- **Functions**:
  - `extract_concepts()`: Claude-based extraction
  - `generate_embedding()`: OpenAI embeddings (text-embedding-3-small)
- **Model**: claude-sonnet-4-20250514

### `ingest.py`
- Main CLI orchestrator
- Tracks statistics (nodes created, concepts linked, etc.)
- Handles existing concept deduplication via vector search
- Progress reporting

## Output

The script provides real-time progress updates:

```
[Paragraph 1] Processing...
  ✓ Created Source node: doc_p1
  ✓ Extracted 3 concepts, 5 instances, 2 relationships
  ✓ Created Concept: Knowledge Graph (concept_001)
  → Matched 'Graph Database' to existing concept 'Database Systems' (similarity: 0.92)

==================================================
INGESTION SUMMARY
==================================================
Paragraphs processed:    10
Source nodes created:    10
Concept nodes created:   15
Concepts linked (reuse): 8
Instance nodes created:  42
Relationships created:   12
==================================================
```

## Error Handling

- File validation before processing
- API error recovery with detailed messages
- Neo4j connection verification
- JSON parsing validation
- Transaction rollback on failures
