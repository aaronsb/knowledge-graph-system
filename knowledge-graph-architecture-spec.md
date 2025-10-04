# Knowledge Graph System Architecture Specification

**Version:** 1.0  
**Date:** October 4, 2025  
**Purpose:** Multi-document knowledge extraction, graph construction, and non-linear exploration

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [System Overview](#system-overview)
4. [Core Concepts](#core-concepts)
5. [Architecture Design](#architecture-design)
6. [Data Models](#data-models)
7. [Document Ingestion Pipeline](#document-ingestion-pipeline)
8. [MCP Server Specification](#mcp-server-specification)
9. [3D Visualization Interface](#3d-visualization-interface)
10. [Implementation Examples](#implementation-examples)
11. [Technology Stack](#technology-stack)
12. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Executive Summary

This specification defines a knowledge graph system designed to extract conceptual relationships from document collections, store them in a queryable graph database, and provide both conversational (via Claude Desktop/MCP) and visual (3D graph) interfaces for exploration.

### Key Capabilities

- **Multi-document ingestion**: Process client documents, white papers, research materials
- **Concept extraction**: Use LLM to identify concepts, relationships, and evidence
- **Graph storage**: Maintain concepts as nodes with full provenance and text instances
- **Conversational queries**: Natural language exploration via Claude Desktop + MCP server
- **3D visualization**: "Step outside" linear thinking to see conceptual structures
- **Semantic search**: Vector embeddings for concept similarity and discovery

### Primary Use Case

Consulting firm document analysis where practitioners need to:
- Quickly understand conceptual relationships across client engagements
- Find patterns and connections between projects
- Explore knowledge non-linearly
- Maintain complete provenance to source documents

---

## 2. Problem Statement

### The Linear Information Problem

As articulated in Alan Watts' critique of human intelligence:

> **Paragraph 4** (Watts Doc 1):
> "So the geneticists are now saying and many others are now saying that man must take the course of his evolution into his own hands. He can no longer trust the wiggly random and unintelligible processes of nature to develop him any further but he must interfere with his own intelligence. And through genetic alterations breed the kind of people who will be viable for human society and that sort of thing. Now this I submit is a ghastly era. Because human intelligence has a very serious limitation. That limitation is. That it is a scanning system, of conscious attention, which is linear. That is to say, it examines the world, in lines. Rather as you would pass the beam of a flashlight across a room or a spotlight. That's why our education takes so long. It takes so long because we have to scan miles of lines of print. And we regard that you see as basic information"

> **Paragraph 5** (Watts Doc 1):
> "Now the universe does not come at us in lines. It comes at us. In a multidimensional continuum in which everything is happening all together everywhere at once. And it comes at us much too quickly, to be translated into lines of print. Or of other information, however fast they may be scanned. And that is our limitation so far as the intellectual life and the scientific life is concerned. The computer will greatly speed up the linear scanning. But it's still linear scanning. And so long as we are stuck with that form of wisdom we cannot deal with more than a few variables at once..."

### The Solution

Build a system that:
1. **Extracts conceptual structure** from linear documents
2. **Preserves relationships** between ideas across documents
3. **Enables non-linear exploration** through graph visualization
4. **Maintains provenance** back to source material
5. **Supports semantic discovery** beyond keyword search

---

## 3. System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCUMENT INGESTION                        │
│                                                              │
│  Client Docs → Parser → LLM Processing → Graph Upsert       │
│  (PDF/DOCX)    (Para)    (JSON Output)    (Database)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH DATABASE                  │
│                                                              │
│  PostgreSQL + pgvector (Phase 1)                            │
│  OR Neo4j + Vector Plugin (Phase 2)                         │
│                                                              │
│  • Concepts as nodes                                         │
│  • Relationships as edges                                    │
│  • Full text instances with quotes                           │
│  • Source provenance tracking                                │
│  • Vector embeddings for semantic search                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    │               │
         ┌──────────▼─────┐  ┌─────▼──────────┐
         │  MCP SERVER    │  │  WEB APP       │
         │  (Claude       │  │  (3D Graph     │
         │   Desktop)     │  │   Visualization)│
         └────────────────┘  └────────────────┘
              │                      │
              ↓                      ↓
         Natural Language      Visual Analysis
         Queries               "Step Outside"
```

### Data Flow

1. **Ingestion**: Documents → Paragraphs → LLM extraction → Structured JSON
2. **Matching**: New concepts → Vector similarity search → Match or create
3. **Storage**: Concepts + Instances + Relationships → Graph database
4. **Query**: Natural language → MCP tools → Graph queries → Structured results
5. **Visualization**: Concept subset → 3D layout → Interactive exploration

---

## 4. Core Concepts

### 4.1 Concept Node

A **Concept** is an abstract idea extracted from text. Concepts can appear in multiple documents.

**Properties:**
- `concept_id` (string, primary key): Kebab-case identifier (e.g., "linear-scanning-system")
- `label` (string): Human-readable name (e.g., "Linear scanning system")
- `embedding` (vector): 1536-dimensional semantic embedding
- `search_terms` (array): Keywords for fallback matching
- `created_at` (timestamp)
- `updated_at` (timestamp)

**Example:**
```json
{
  "concept_id": "linear-scanning-system",
  "label": "Linear scanning system",
  "search_terms": ["linear processing", "sequential thinking", "scanning attention"],
  "created_at": "2025-10-04T10:30:00Z"
}
```

### 4.2 Instance Node

An **Instance** is a specific quote/evidence from a document that supports a concept.

**Properties:**
- `instance_id` (uuid, primary key)
- `concept_id` (foreign key to Concept)
- `source_id` (foreign key to Source)
- `quote` (text): Exact text from document
- `created_at` (timestamp)

**Example:**
```json
{
  "instance_id": "550e8400-e29b-41d4-a716-446655440000",
  "concept_id": "linear-scanning-system",
  "source_id": "watts-doc-1-para-4",
  "quote": "it is a scanning system, of conscious attention, which is linear"
}
```

### 4.3 Source Node

A **Source** represents a specific location in a document (paragraph, section, page).

**Properties:**
- `source_id` (string, primary key): Format: `{document-slug}-para-{number}`
- `document` (string): Document name/identifier
- `paragraph` (integer): Paragraph number
- `section` (string, optional): Section/chapter identifier
- `full_text` (text): Complete paragraph text
- `created_at` (timestamp)

**Example:**
```json
{
  "source_id": "watts-doc-1-para-4",
  "document": "Watts Doc 1",
  "paragraph": 4,
  "full_text": "So the geneticists are now saying..."
}
```

### 4.4 Relationship

A **Relationship** connects two concepts with a typed edge.

**Types:**
- `implies`: Concept A logically implies Concept B
- `contradicts`: Concept A contradicts Concept B
- `supports`: Concept A provides evidence for Concept B
- `part_of`: Concept A is a component of Concept B
- `requires`: Concept A requires Concept B

**Properties:**
- `from_concept_id` (foreign key)
- `to_concept_id` (foreign key)
- `relationship_type` (enum)
- `confidence` (float, 0.0-1.0)
- `created_at` (timestamp)

**Example:**
```json
{
  "from_concept_id": "intelligence-limitation",
  "to_concept_id": "linear-scanning-system",
  "relationship_type": "part_of",
  "confidence": 0.95
}
```

---

## 5. Architecture Design

### 5.1 Component Architecture

```
┌─────────────────────────────────────────┐
│         Document Processor              │
│  - Parse documents into paragraphs      │
│  - Extract metadata                     │
│  - Batch processing support             │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         LLM Extraction Engine           │
│  - Per-paragraph concept extraction     │
│  - Relationship identification          │
│  - Quote/instance extraction            │
│  - Structured JSON output               │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Concept Matching Service        │
│  - Vector similarity search             │
│  - Multi-stage matching algorithm       │
│  - Deduplication logic                  │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Graph Upsert Engine             │
│  - UPSERT concepts (add sources)        │
│  - INSERT instances                     │
│  - CREATE/UPDATE relationships          │
│  - Update vector embeddings             │
└─────────────────────────────────────────┘
```

### 5.2 Matching Algorithm

**Multi-stage concept matching to prevent duplicates:**

```
Stage 1: Exact ID Match
  ├─ If LLM predicted existing concept_id → Use it
  └─ Confidence: 100%

Stage 2: Vector Similarity (Primary)
  ├─ Embed: label + search_terms
  ├─ Cosine similarity search
  ├─ Threshold: > 0.85 → Match
  └─ Confidence: similarity_score

Stage 3: Keyword Overlap (Fallback)
  ├─ Compare search_terms arrays
  ├─ Intersection > 50% → Potential match
  └─ Require manual review or lower confidence

Stage 4: Create New Concept
  ├─ No match found
  └─ Generate new concept_id
```

**Implementation:**
```python
def find_matching_concept(new_concept: dict, threshold: float = 0.85) -> Optional[str]:
    # Stage 1: Exact match
    if concept_exists(new_concept['concept_id']):
        return new_concept['concept_id']
    
    # Stage 2: Vector similarity
    embedding = generate_embedding(
        f"{new_concept['label']} {' '.join(new_concept['search_terms'])}"
    )
    
    results = vector_search(embedding, top_k=5)
    if results and results[0]['score'] > threshold:
        return results[0]['concept_id']
    
    # Stage 3: Keyword overlap
    for existing in get_all_concepts():
        overlap = set(new_concept['search_terms']) & set(existing['search_terms'])
        if len(overlap) / len(new_concept['search_terms']) > 0.5:
            # Flag for review or use with lower confidence
            log_potential_duplicate(new_concept, existing)
    
    # Stage 4: New concept
    return None
```

---

## 6. Data Models

### 6.1 PostgreSQL Schema (Phase 1)

```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- CONCEPTS TABLE
CREATE TABLE concepts (
    concept_id VARCHAR(255) PRIMARY KEY,
    label VARCHAR(500) NOT NULL,
    embedding VECTOR(1536),  -- OpenAI ada-002 dimensions
    search_terms TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity index
CREATE INDEX idx_concept_embedding ON concepts 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Text search index (fallback)
CREATE INDEX idx_search_terms ON concepts USING GIN (search_terms);

-- SOURCES TABLE
CREATE TABLE sources (
    source_id VARCHAR(255) PRIMARY KEY,
    document VARCHAR(255) NOT NULL,
    paragraph INTEGER,
    section VARCHAR(255),
    full_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- INSTANCES TABLE (quotes/evidence)
CREATE TABLE instances (
    instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id VARCHAR(255) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    source_id VARCHAR(255) REFERENCES sources(source_id) ON DELETE CASCADE,
    quote TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- CONCEPT RELATIONSHIPS
CREATE TABLE concept_relationships (
    from_concept_id VARCHAR(255) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    to_concept_id VARCHAR(255) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) CHECK (relationship_type IN ('implies', 'contradicts', 'supports', 'part_of', 'requires')),
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (from_concept_id, to_concept_id, relationship_type)
);

-- CONCEPT SOURCES (many-to-many)
CREATE TABLE concept_sources (
    concept_id VARCHAR(255) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    source_id VARCHAR(255) REFERENCES sources(source_id) ON DELETE CASCADE,
    first_seen TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (concept_id, source_id)
);

-- CONCEPT SEARCH TERMS (for keyword matching)
CREATE TABLE concept_search_terms (
    concept_id VARCHAR(255) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    search_term VARCHAR(255),
    PRIMARY KEY (concept_id, search_term)
);

CREATE INDEX idx_search_term_lookup ON concept_search_terms(search_term);
```

### 6.2 Neo4j Schema (Phase 2, Optional)

```cypher
// CONCEPT NODE
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;

CREATE INDEX concept_label IF NOT EXISTS
FOR (c:Concept) ON (c.label);

// NODE SCHEMA
(:Concept {
  concept_id: STRING,
  label: STRING,
  search_terms: [STRING],
  created_at: DATETIME,
  updated_at: DATETIME
})

(:Source {
  source_id: STRING,
  document: STRING,
  paragraph: INTEGER,
  section: STRING,
  full_text: STRING
})

(:Instance {
  instance_id: STRING,
  quote: STRING,
  created_at: DATETIME
})

// RELATIONSHIPS
(:Concept)-[:APPEARS_IN {first_seen: DATETIME}]->(:Source)
(:Concept)-[:EVIDENCED_BY]->(:Instance)
(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES {confidence: FLOAT}]->(:Concept)
(:Concept)-[:CONTRADICTS {confidence: FLOAT}]->(:Concept)
(:Concept)-[:SUPPORTS {confidence: FLOAT}]->(:Concept)
(:Concept)-[:PART_OF]->(:Concept)
(:Concept)-[:REQUIRES {confidence: FLOAT}]->(:Concept)

// Vector index (Neo4j 5.11+)
CREATE VECTOR INDEX concept_embeddings IF NOT EXISTS
FOR (c:Concept) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

### 6.3 LLM Output Schema

**JSON structure for LLM extraction output:**

```json
{
  "extracted_concepts": [
    {
      "concept_id": "human-directed-evolution",
      "label": "Human-directed evolution",
      "confidence": 0.95,
      "search_terms": [
        "human evolution control",
        "self-directed evolution",
        "evolutionary intervention",
        "genetic control"
      ]
    },
    {
      "concept_id": "nature-unreliable",
      "label": "Nature is unreliable",
      "confidence": 0.88,
      "search_terms": [
        "nature random",
        "natural processes unintelligible",
        "distrust nature"
      ]
    }
  ],
  "instances": [
    {
      "concept_id": "human-directed-evolution",
      "quote": "man must take the course of his evolution into his own hands"
    },
    {
      "concept_id": "nature-unreliable",
      "quote": "He can no longer trust the wiggly random and unintelligible processes of nature"
    }
  ],
  "relationships": [
    {
      "from_concept_id": "human-directed-evolution",
      "to_concept_id": "nature-unreliable",
      "relationship_type": "implies",
      "confidence": 0.90
    },
    {
      "from_concept_id": "nature-unreliable",
      "to_concept_id": "genetic-intervention-needed",
      "relationship_type": "implies",
      "confidence": 0.85
    }
  ]
}
```

---

## 7. Document Ingestion Pipeline

### 7.1 Pipeline Architecture

```python
# ingest/pipeline.py
import asyncio
from pathlib import Path
from typing import List, Dict
import anthropic
import json

class DocumentProcessor:
    """
    Main document ingestion pipeline
    """
    
    def __init__(self, graph_db, vector_db, llm_client):
        self.graph = graph_db
        self.vector = vector_db
        self.llm = llm_client
        self.embedding_model = "text-embedding-3-small"
    
    async def process_document(
        self, 
        doc_path: Path, 
        doc_metadata: Dict[str, str]
    ) -> Dict:
        """
        Process a single document through the pipeline
        
        Args:
            doc_path: Path to document file
            doc_metadata: {"name": "Watts Doc 1", "client": "Research", ...}
        
        Returns:
            Processing statistics
        """
        print(f"Processing document: {doc_metadata['name']}")
        
        # 1. Parse document into paragraphs
        paragraphs = self.parse_document(doc_path)
        print(f"  Found {len(paragraphs)} paragraphs")
        
        # 2. Get current graph state for context
        existing_concepts = await self.get_existing_concepts()
        
        # 3. Process each paragraph
        stats = {
            "paragraphs_processed": 0,
            "concepts_created": 0,
            "concepts_updated": 0,
            "instances_created": 0,
            "relationships_created": 0
        }
        
        for i, para_text in enumerate(paragraphs):
            para_num = i + 1
            source_id = f"{self.slugify(doc_metadata['name'])}-para-{para_num}"
            
            print(f"  Processing paragraph {para_num}...")
            
            # Store source
            await self.store_source(source_id, doc_metadata['name'], para_num, para_text)
            
            # Extract concepts using LLM
            extraction = await self.extract_concepts(
                para_text,
                source_id,
                existing_concepts
            )
            
            # Upsert to graph
            upsert_stats = await self.upsert_to_graph(extraction, source_id)
            
            # Update statistics
            stats["paragraphs_processed"] += 1
            stats["concepts_created"] += upsert_stats["new_concepts"]
            stats["concepts_updated"] += upsert_stats["updated_concepts"]
            stats["instances_created"] += upsert_stats["instances"]
            stats["relationships_created"] += upsert_stats["relationships"]
            
            # Refresh existing concepts for next iteration
            existing_concepts = await self.get_existing_concepts()
        
        print(f"Completed: {stats}")
        return stats
    
    def parse_document(self, doc_path: Path) -> List[str]:
        """Parse document into paragraphs based on file type"""
        if doc_path.suffix == '.txt':
            return self.parse_text(doc_path)
        elif doc_path.suffix == '.pdf':
            return self.parse_pdf(doc_path)
        elif doc_path.suffix in ['.docx', '.doc']:
            return self.parse_docx(doc_path)
        else:
            raise ValueError(f"Unsupported file type: {doc_path.suffix}")
    
    def parse_text(self, doc_path: Path) -> List[str]:
        """Parse plain text file into paragraphs"""
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split on double newlines
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        return paragraphs
    
    async def extract_concepts(
        self, 
        text: str, 
        source_id: str, 
        existing_concepts: List[Dict]
    ) -> Dict:
        """
        Use Claude to extract concepts from paragraph
        
        Returns JSON matching the LLM output schema
        """
        
        # Limit existing concepts shown to LLM (top 50 by relevance)
        concept_context = existing_concepts[:50]
        
        prompt = f"""You are a knowledge graph extraction system. Analyze the provided text and output structured JSON.

CONTEXT - EXISTING CONCEPTS (for matching):
{json.dumps(concept_context, indent=2)}

NEW TEXT TO PROCESS:
Source: {source_id}
Text: \"\"\"
{text}
\"\"\"

TASK:
1. Extract key concepts (ideas, claims, arguments) from the text
2. For EACH concept, provide search terms to help match against existing concepts
3. Identify text instances (quotes) that support each concept
4. Map logical relationships between concepts

MATCHING INSTRUCTIONS:
- If a concept matches an existing one (same core idea, even if worded differently), use the existing concept_id
- If it's a new concept, create a new kebab-case concept_id
- Be conservative: only match if concepts are truly equivalent

OUTPUT REQUIREMENTS:
- Return valid JSON matching the schema below
- Use kebab-case for concept_ids (e.g., "linear-scanning-system")
- Provide 2-5 search terms per concept for semantic matching
- Include confidence scores (0.0-1.0)
- Quote instances should be verbatim from source text
- Only include relationships between concepts in THIS extraction

RESPONSE SCHEMA:
{{
  "extracted_concepts": [
    {{
      "concept_id": "kebab-case-id",
      "label": "Human readable label",
      "confidence": 0.95,
      "search_terms": ["term1", "term2", "term3"]
    }}
  ],
  "instances": [
    {{
      "concept_id": "matches-concept-above",
      "quote": "exact verbatim quote from text"
    }}
  ],
  "relationships": [
    {{
      "from_concept_id": "concept-a",
      "to_concept_id": "concept-b",
      "relationship_type": "implies",
      "confidence": 0.85
    }}
  ]
}}

RELATIONSHIP TYPES:
- implies: A logically implies B
- contradicts: A contradicts B
- supports: A provides evidence for B
- part_of: A is a component of B
- requires: A requires B

Respond ONLY with valid JSON, no other text."""

        response = await self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON response
        json_text = response.content[0].text
        # Strip markdown code blocks if present
        json_text = json_text.replace('```json\n', '').replace('```\n', '').replace('```', '').strip()
        
        return json.loads(json_text)
    
    async def upsert_to_graph(self, extraction: Dict, source_id: str) -> Dict:
        """
        Upsert extracted data to graph database
        
        Returns statistics about what was created/updated
        """
        stats = {
            "new_concepts": 0,
            "updated_concepts": 0,
            "instances": 0,
            "relationships": 0
        }
        
        # Process each extracted concept
        for concept in extraction['extracted_concepts']:
            # Try to match with existing concept
            matched_id = await self.find_matching_concept(concept)
            
            if matched_id:
                # Update existing concept
                concept_id = matched_id
                await self.update_concept(concept_id, source_id)
                stats["updated_concepts"] += 1
            else:
                # Create new concept
                concept_id = concept['concept_id']
                embedding = await self.generate_embedding(
                    f"{concept['label']} {' '.join(concept['search_terms'])}"
                )
                await self.create_concept(concept, embedding, source_id)
                stats["new_concepts"] += 1
            
            # Store search terms
            for term in concept['search_terms']:
                await self.store_search_term(concept_id, term)
        
        # Process instances
        for instance in extraction['instances']:
            await self.create_instance(
                instance['concept_id'],
                source_id,
                instance['quote']
            )
            stats["instances"] += 1
        
        # Process relationships
        for rel in extraction['relationships']:
            await self.create_relationship(
                rel['from_concept_id'],
                rel['to_concept_id'],
                rel['relationship_type'],
                rel['confidence']
            )
            stats["relationships"] += 1
        
        return stats
    
    async def find_matching_concept(self, new_concept: Dict) -> Optional[str]:
        """
        Multi-stage concept matching
        
        Returns: concept_id if match found, None otherwise
        """
        # Stage 1: Exact ID match
        if await self.concept_exists(new_concept['concept_id']):
            return new_concept['concept_id']
        
        # Stage 2: Vector similarity
        embedding = await self.generate_embedding(
            f"{new_concept['label']} {' '.join(new_concept['search_terms'])}"
        )
        
        results = await self.vector_search(embedding, threshold=0.85)
        if results:
            return results[0]['concept_id']
        
        # Stage 3: No match
        return None
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to kebab-case slug"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        text = re.sub(r'^-+|-+$', '', text)
        return text
```

### 7.2 Example Usage

```python
# ingest_documents.py
import asyncio
from pathlib import Path
from pipeline import DocumentProcessor
from database import GraphDatabase
import anthropic

async def main():
    # Initialize components
    db = GraphDatabase("postgresql://user:pass@localhost/knowledge_graph")
    llm = anthropic.AsyncAnthropic(api_key="your-api-key")
    
    processor = DocumentProcessor(db, db, llm)
    
    # Process Watts documents
    docs = [
        {
            "path": Path("./docs/watts_lecture_1.txt"),
            "metadata": {
                "name": "Watts Doc 1",
                "author": "Alan Watts",
                "type": "lecture_transcript"
            }
        }
    ]
    
    for doc in docs:
        stats = await processor.process_document(
            doc["path"],
            doc["metadata"]
        )
        print(f"Processed {doc['metadata']['name']}: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. MCP Server Specification

### 8.1 MCP Server Architecture

The MCP (Model Context Protocol) server provides tools for Claude Desktop to interact with the knowledge graph.

**Location:** `mcp-knowledge-graph-server/`

**Key files:**
- `src/index.ts` - Main server implementation
- `src/database.ts` - Database queries
- `src/tools/` - Individual tool implementations
- `package.json` - Dependencies
- `tsconfig.json` - TypeScript configuration

### 8.2 Tool Definitions

```typescript
// src/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  {
    name: "knowledge-graph-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "search_concepts",
      description: "Search for concepts using semantic similarity or keywords. Returns concepts with their sources and evidence count.",
      inputSchema: {
        type: "object",
        properties: {
          query: { 
            type: "string", 
            description: "Search query - can be keywords or natural language" 
          },
          limit: { 
            type: "number", 
            description: "Maximum number of results to return", 
            default: 10 
          },
          min_similarity: { 
            type: "number", 
            description: "Minimum similarity score (0.0-1.0) for vector search", 
            default: 0.7 
          }
        },
        required: ["query"]
      }
    },
    {
      name: "get_concept_details",
      description: "Get comprehensive details about a specific concept including all instances (quotes), sources, and related concepts.",
      inputSchema: {
        type: "object",
        properties: {
          concept_id: { 
            type: "string",
            description: "The concept_id to retrieve (e.g., 'linear-scanning-system')"
          }
        },
        required: ["concept_id"]
      }
    },
    {
      name: "find_related_concepts",
      description: "Find concepts related to a given concept through various relationship types. Can traverse multiple hops.",
      inputSchema: {
        type: "object",
        properties: {
          concept_id: { 
            type: "string",
            description: "Starting concept_id"
          },
          relationship_types: { 
            type: "array", 
            items: { type: "string" },
            description: "Filter by relationship types: implies, contradicts, supports, part_of, requires. Leave empty for all types."
          },
          max_depth: { 
            type: "number", 
            default: 2,
            description: "Maximum relationship hops to traverse"
          }
        },
        required: ["concept_id"]
      }
    },
    {
      name: "search_by_document",
      description: "Find all concepts that appear in a specific document or paragraph.",
      inputSchema: {
        type: "object",
        properties: {
          document_name: { 
            type: "string",
            description: "Document name to search (e.g., 'Watts Doc 1')"
          },
          paragraph: { 
            type: "number", 
            description: "Optional: specific paragraph number to filter by" 
          }
        },
        required: ["document_name"]
      }
    },
    {
      name: "find_connections",
      description: "Find the shortest path(s) between two concepts in the knowledge graph.",
      inputSchema: {
        type: "object",
        properties: {
          from_concept_id: { 
            type: "string",
            description: "Starting concept"
          },
          to_concept_id: { 
            type: "string",
            description: "Target concept"
          },
          max_hops: { 
            type: "number", 
            default: 5,
            description: "Maximum number of hops to search"
          }
        },
        required: ["from_concept_id", "to_concept_id"]
      }
    },
    {
      name: "get_visualization_url",
      description: "Generate a URL to visualize a subgraph in 3D. Opens in web browser for visual exploration.",
      inputSchema: {
        type: "object",
        properties: {
          concept_ids: { 
            type: "array", 
            items: { type: "string" },
            description: "Concepts to include in visualization. Can be empty to use depth-based expansion."
          },
          depth: { 
            type: "number", 
            default: 1, 
            description: "Include neighbors up to this depth from specified concepts" 
          },
          center_concept: {
            type: "string",
            description: "Optional: concept to center the visualization on"
          }
        }
      }
    },
    {
      name: "list_documents",
      description: "List all documents in the knowledge graph with concept counts.",
      inputSchema: {
        type: "object",
        properties: {}
      }
    }
  ]
}));

// Tool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "search_concepts":
      return await searchConcepts(
        args.query, 
        args.limit ?? 10, 
        args.min_similarity ?? 0.7
      );
    
    case "get_concept_details":
      return await getConceptDetails(args.concept_id);
    
    case "find_related_concepts":
      return await findRelatedConcepts(
        args.concept_id, 
        args.relationship_types ?? [],
        args.max_depth ?? 2
      );
    
    case "search_by_document":
      return await searchByDocument(
        args.document_name, 
        args.paragraph
      );
    
    case "find_connections":
      return await findConnections(
        args.from_concept_id,
        args.to_concept_id,
        args.max_hops ?? 5
      );
    
    case "get_visualization_url":
      return await getVisualizationUrl(
        args.concept_ids ?? [],
        args.depth ?? 1,
        args.center_concept
      );
    
    case "list_documents":
      return await listDocuments();
    
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Knowledge Graph MCP server running on stdio");
}

main().catch(console.error);
```

### 8.3 Tool Implementation Examples

```typescript
// src/database.ts
import { Client } from 'pg';
import OpenAI from 'openai';

const db = new Client({
  connectionString: process.env.DATABASE_URL
});

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

await db.connect();

// Generate embedding for search
async function generateEmbedding(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text,
  });
  return response.data[0].embedding;
}

// Search concepts by semantic similarity
export async function searchConcepts(
  query: string, 
  limit: number, 
  minSimilarity: number
) {
  const embedding = await generateEmbedding(query);
  
  const result = await db.query(`
    SELECT 
      c.concept_id,
      c.label,
      1 - (c.embedding <=> $1::vector) as similarity,
      array_agg(DISTINCT s.document) as documents,
      count(DISTINCT i.instance_id) as evidence_count
    FROM concepts c
    LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
    LEFT JOIN sources s ON cs.source_id = s.source_id
    LEFT JOIN instances i ON c.concept_id = i.concept_id
    WHERE 1 - (c.embedding <=> $1::vector) > $2
    GROUP BY c.concept_id, c.label, c.embedding
    ORDER BY similarity DESC
    LIMIT $3
  `, [JSON.stringify(embedding), minSimilarity, limit]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        query: query,
        results: result.rows
      }, null, 2)
    }]
  };
}

// Get concept details with instances
export async function getConceptDetails(conceptId: string) {
  const conceptResult = await db.query(`
    SELECT c.*, array_agg(DISTINCT s.document) as documents
    FROM concepts c
    LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
    LEFT JOIN sources s ON cs.source_id = s.source_id
    WHERE c.concept_id = $1
    GROUP BY c.concept_id
  `, [conceptId]);

  if (conceptResult.rows.length === 0) {
    throw new Error(`Concept not found: ${conceptId}`);
  }

  const instancesResult = await db.query(`
    SELECT i.quote, s.document, s.paragraph, s.source_id
    FROM instances i
    JOIN sources s ON i.source_id = s.source_id
    WHERE i.concept_id = $1
    ORDER BY s.document, s.paragraph
  `, [conceptId]);

  const relationshipsResult = await db.query(`
    SELECT 
      cr.to_concept_id,
      c.label as to_label,
      cr.relationship_type,
      cr.confidence
    FROM concept_relationships cr
    JOIN concepts c ON cr.to_concept_id = c.concept_id
    WHERE cr.from_concept_id = $1
  `, [conceptId]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        concept: conceptResult.rows[0],
        instances: instancesResult.rows,
        relationships: relationshipsResult.rows
      }, null, 2)
    }]
  };
}

// Find connections between concepts
export async function findConnections(
  fromId: string,
  toId: string,
  maxHops: number
) {
  // Use recursive CTE to find paths
  const result = await db.query(`
    WITH RECURSIVE paths AS (
      -- Base case: direct relationships
      SELECT 
        from_concept_id,
        to_concept_id,
        relationship_type,
        ARRAY[from_concept_id, to_concept_id] as path,
        1 as depth
      FROM concept_relationships
      WHERE from_concept_id = $1
      
      UNION ALL
      
      -- Recursive case: extend paths
      SELECT 
        p.from_concept_id,
        cr.to_concept_id,
        cr.relationship_type,
        p.path || cr.to_concept_id,
        p.depth + 1
      FROM paths p
      JOIN concept_relationships cr ON p.to_concept_id = cr.from_concept_id
      WHERE 
        NOT cr.to_concept_id = ANY(p.path)  -- Prevent cycles
        AND p.depth < $3
    )
    SELECT 
      path,
      depth,
      array_agg(relationship_type) as relationship_types
    FROM paths
    WHERE to_concept_id = $2
    GROUP BY path, depth
    ORDER BY depth
    LIMIT 5
  `, [fromId, toId, maxHops]);

  // Enrich with concept labels
  const enrichedPaths = [];
  for (const row of result.rows) {
    const labels = await db.query(`
      SELECT concept_id, label
      FROM concepts
      WHERE concept_id = ANY($1)
    `, [row.path]);
    
    const labelMap = Object.fromEntries(
      labels.rows.map(r => [r.concept_id, r.label])
    );
    
    enrichedPaths.push({
      path: row.path.map((id: string) => ({
        concept_id: id,
        label: labelMap[id]
      })),
      depth: row.depth,
      relationship_types: row.relationship_types
    });
  }

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        from: fromId,
        to: toId,
        paths: enrichedPaths,
        paths_found: enrichedPaths.length
      }, null, 2)
    }]
  };
}

// Generate visualization URL
export async function getVisualizationUrl(
  conceptIds: string[],
  depth: number,
  centerConcept?: string
) {
  // Generate unique session ID
  const sessionId = Math.random().toString(36).substring(7);
  
  // Store visualization config in temporary table or cache
  await db.query(`
    INSERT INTO visualization_sessions (session_id, concept_ids, depth, center_concept, created_at)
    VALUES ($1, $2, $3, $4, NOW())
  `, [sessionId, conceptIds, depth, centerConcept]);
  
  const baseUrl = process.env.VISUALIZATION_URL || 'http://localhost:3000';
  const url = `${baseUrl}/viz/${sessionId}`;
  
  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        url: url,
        message: "Open this URL in your browser to explore the graph in 3D",
        config: {
          concept_ids: conceptIds,
          depth: depth,
          center: centerConcept
        }
      }, null, 2)
    }]
  };
}
```

### 8.4 Claude Desktop Configuration

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": [
        "/absolute/path/to/mcp-knowledge-graph-server/build/index.js"
      ],
      "env": {
        "DATABASE_URL": "postgresql://user:password@localhost:5432/knowledge_graph",
        "OPENAI_API_KEY": "sk-...",
        "VISUALIZATION_URL": "http://localhost:3000"
      }
    }
  }
}
```

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

---

## 9. 3D Visualization Interface

### 9.1 Visualization Architecture

**Tech Stack:**
- React + TypeScript
- force-graph-3d (Three.js wrapper)
- FastAPI backend
- WebSocket for real-time updates (optional)

### 9.2 Frontend Implementation

```typescript
// src/components/Graph3DViewer.tsx
import React, { useEffect, useState, useRef } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';

interface Node {
  id: string;
  label: string;
  sources: string[];
  evidenceCount: number;
  color?: string;
}

interface Link {
  source: string;
  target: string;
  type: string;
  confidence: number;
}

interface GraphData {
  nodes: Node[];
  links: Link[];
}

interface Graph3DViewerProps {
  sessionId: string;
}

export function Graph3DViewer({ sessionId }: Graph3DViewerProps) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(true);
  const fgRef = useRef<any>();

  useEffect(() => {
    // Fetch graph data from API
    fetch(`/api/graph/session/${sessionId}`)
      .then(res => res.json())
      .then(data => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load graph:', err);
        setLoading(false);
      });
  }, [sessionId]);

  const handleNodeClick = (node: Node) => {
    setSelectedNode(node);
    
    // Fetch full concept details
    fetch(`/api/concept/${node.id}`)
      .then(res => res.json())
      .then(details => {
        // Update side panel with details
        setSelectedNode({ ...node, ...details });
      });
  };

  const getNodeColor = (node: Node) => {
    // Color by number of sources
    const sourceCount = node.sources.length;
    if (sourceCount >= 5) return '#ff6b6b';  // Red: appears in many docs
    if (sourceCount >= 3) return '#ffd93d';  // Yellow: medium frequency
    return '#6bcf7f';  // Green: single or few sources
  };

  const getLinkColor = (link: Link) => {
    // Color by relationship type
    const colors: Record<string, string> = {
      'implies': '#4dabf7',
      'contradicts': '#ff6b6b',
      'supports': '#51cf66',
      'part_of': '#845ef7',
      'requires': '#ffd43b'
    };
    return colors[link.type] || '#adb5bd';
  };

  if (loading) {
    return <div className="loading">Loading graph...</div>;
  }

  return (
    <div className="graph-container">
      <div className="graph-3d">
        <ForceGraph3D
          ref={fgRef}
          graphData={graphData}
          
          // Node configuration
          nodeLabel={(node: any) => `${node.label}\n${node.evidenceCount} instances`}
          nodeAutoColorBy="sources"
          nodeColor={getNodeColor}
          nodeVal={(node: any) => Math.sqrt(node.evidenceCount) * 3}
          
          // Link configuration
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          linkLabel={(link: any) => `${link.type} (${link.confidence})`}
          linkColor={getLinkColor}
          linkWidth={(link: any) => link.confidence * 2}
          
          // Interaction
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => {
            document.body.style.cursor = node ? 'pointer' : 'default';
          }}
          
          // Custom rendering
          nodeThreeObject={(node: any) => {
            const sprite = new THREE.Sprite(
              new THREE.SpriteMaterial({
                map: new THREE.CanvasTexture(
                  generateNodeTexture(node.label)
                ),
                transparent: true
              })
            );
            sprite.scale.set(12, 6, 1);
            return sprite;
          }}
          
          // Camera
          backgroundColor="#1a1a1a"
        />
      </div>
      
      {selectedNode && (
        <div className="side-panel">
          <h2>{selectedNode.label}</h2>
          <div className="node-details">
            <h3>Sources:</h3>
            <ul>
              {selectedNode.sources.map(src => (
                <li key={src}>{src}</li>
              ))}
            </ul>
            
            <h3>Evidence ({selectedNode.evidenceCount} instances):</h3>
            {/* Render instances if available */}
            
            <button onClick={() => {
              // Expand graph from this node
              expandFromNode(selectedNode.id);
            }}>
              Expand from this concept
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function to generate node texture
function generateNodeTexture(label: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  
  canvas.width = 256;
  canvas.height = 128;
  
  // Background
  ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
  ctx.fillRect(0, 0, 256, 128);
  
  // Text
  ctx.fillStyle = 'white';
  ctx.font = '20px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  
  // Word wrap
  const words = label.split(' ');
  let line = '';
  let y = 64;
  const lineHeight = 25;
  
  words.forEach(word => {
    const testLine = line + word + ' ';
    const metrics = ctx.measureText(testLine);
    if (metrics.width > 230 && line !== '') {
      ctx.fillText(line, 128, y);
      line = word + ' ';
      y += lineHeight;
    } else {
      line = testLine;
    }
  });
  ctx.fillText(line, 128, y);
  
  return canvas;
}
```

### 9.3 Backend API

```python
# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncpg
import os

app = FastAPI(title="Knowledge Graph Visualization API")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
async def get_db():
    return await asyncpg.connect(os.getenv("DATABASE_URL"))

@app.get("/api/graph/session/{session_id}")
async def get_session_graph(session_id: str):
    """
    Retrieve graph data for a visualization session
    """
    db = await get_db()
    
    try:
        # Get session config
        session = await db.fetchrow(
            "SELECT * FROM visualization_sessions WHERE session_id = $1",
            session_id
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        concept_ids = session['concept_ids']
        depth = session['depth']
        
        # Build subgraph
        if concept_ids:
            # Start from specified concepts
            query = f"""
            WITH RECURSIVE subgraph AS (
                -- Base: specified concepts
                SELECT concept_id, label, 0 as distance
                FROM concepts
                WHERE concept_id = ANY($1)
                
                UNION
                
                -- Recursive: neighbors
                SELECT c.concept_id, c.label, sg.distance + 1
                FROM subgraph sg
                JOIN concept_relationships cr ON 
                    cr.from_concept_id = sg.concept_id OR
                    cr.to_concept_id = sg.concept_id
                JOIN concepts c ON 
                    c.concept_id = cr.from_concept_id OR
                    c.concept_id = cr.to_concept_id
                WHERE sg.distance < $2
                AND c.concept_id != sg.concept_id
            )
            SELECT DISTINCT 
                c.concept_id,
                c.label,
                array_agg(DISTINCT s.document) as sources,
                count(DISTINCT i.instance_id) as evidence_count
            FROM subgraph sg
            JOIN concepts c ON sg.concept_id = c.concept_id
            LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
            LEFT JOIN sources s ON cs.source_id = s.source_id
            LEFT JOIN instances i ON c.concept_id = i.concept_id
            GROUP BY c.concept_id, c.label
            """
            nodes = await db.fetch(query, concept_ids, depth)
        else:
            # No specific concepts: return top concepts by centrality
            nodes = await db.fetch("""
                SELECT 
                    c.concept_id,
                    c.label,
                    array_agg(DISTINCT s.document) as sources,
                    count(DISTINCT i.instance_id) as evidence_count
                FROM concepts c
                LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
                LEFT JOIN sources s ON cs.source_id = s.source_id
                LEFT JOIN instances i ON c.concept_id = i.concept_id
                GROUP BY c.concept_id, c.label
                ORDER BY count(DISTINCT i.instance_id) DESC
                LIMIT 50
            """)
        
        node_ids = [n['concept_id'] for n in nodes]
        
        # Get relationships between these nodes
        links = await db.fetch("""
            SELECT 
                from_concept_id as source,
                to_concept_id as target,
                relationship_type as type,
                confidence
            FROM concept_relationships
            WHERE from_concept_id = ANY($1)
            AND to_concept_id = ANY($1)
        """, node_ids)
        
        return {
            "nodes": [dict(n) for n in nodes],
            "links": [dict(l) for l in links]
        }
    
    finally:
        await db.close()

@app.get("/api/concept/{concept_id}")
async def get_concept_full(concept_id: str):
    """
    Get full concept details including instances
    """
    db = await get_db()
    
    try:
        concept = await db.fetchrow(
            "SELECT * FROM concepts WHERE concept_id = $1",
            concept_id
        )
        
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        
        instances = await db.fetch("""
            SELECT i.quote, s.document, s.paragraph
            FROM instances i
            JOIN sources s ON i.source_id = s.source_id
            WHERE i.concept_id = $1
            ORDER BY s.document, s.paragraph
        """, concept_id)
        
        relationships = await db.fetch("""
            SELECT 
                to_concept_id,
                c.label as to_label,
                relationship_type,
                confidence
            FROM concept_relationships cr
            JOIN concepts c ON cr.to_concept_id = c.concept_id
            WHERE from_concept_id = $1
        """, concept_id)
        
        return {
            "concept": dict(concept),
            "instances": [dict(i) for i in instances],
            "relationships": [dict(r) for r in relationships]
        }
    
    finally:
        await db.close()

@app.post("/api/graph/expand/{concept_id}")
async def expand_from_concept(concept_id: str, depth: int = 1):
    """
    Expand graph from a specific concept
    Returns additional nodes and links
    """
    # Similar to get_session_graph but starts from one concept
    pass
```

### 9.4 Visualization Features

**Interactive Controls:**
- Mouse drag: Rotate camera
- Scroll: Zoom in/out
- Click node: Show details panel
- Double-click node: Center on node
- Right-click node: Expand from this concept

**Visual Encoding:**
- **Node size**: Proportional to evidence count (number of instances)
- **Node color**: By number of source documents (green=1, yellow=3+, red=5+)
- **Link color**: By relationship type (blue=implies, red=contradicts, etc.)
- **Link thickness**: By confidence score

**UI Elements:**
- Search bar: Find and highlight concepts
- Filters: Show/hide relationship types
- Legend: Explain colors and symbols
- Mini-map: Show overview of large graphs
- Export: Save as image or export data

---

## 10. Implementation Examples

### 10.1 Example: Processing Watts Documents

**Input Files:**
```
docs/
  watts_lecture_1.txt
```

**Content (watts_lecture_1.txt):**
```
So the geneticists are now saying and many others are now saying that man must take the course of his evolution into his own hands. He can no longer trust the wiggly random and unintelligible processes of nature to develop him any further but he must interfere with his own intelligence. And through genetic alterations breed the kind of people who will be viable for human society and that sort of thing. Now this I submit is a ghastly era. Because human intelligence has a very serious limitation. That limitation is. That it is a scanning system, of conscious attention, which is linear. That is to say, it examines the world, in lines. Rather as you would pass the beam of a flashlight across a room or a spotlight. That's why our education takes so long. It takes so long because we have to scan miles of lines of print. And we regard that you see as basic information

Now the universe does not come at us in lines. It comes at us. In a multidimensional continuum in which everything is happening all together everywhere at once. And it comes at us much too quickly, to be translated into lines of print. Or of other information, however fast they may be scanned. And that is our limitation so far as the intellectual life and the scientific life is concerned. The computer will greatly speed up the linear scanning. But it's still linear scanning. And so long as we are stuck with that form of wisdom we cannot deal with more than a few variables at once. Now what do I mean by that. What is a variable? A variable is any one linear process let's take music when you play a bar few. And there are four parts to it you have four variables you have four moving lines and you can take care of that with two hands. An organist using two feet can put into more variables and have six going and you may realize if you've ever tried to play the organ that it's quite difficult to make six independent motions go at once. The average person cannot do that without training the average person cannot deal with more than three variables at once without using a pencil. Now when we study physics we are dealing with processes in which there are millions of variables. This however we handle by statistics in the same way as insurance companies use actuarial tables to predict when most people will die. If the average age of death is sixty five however, this prediction does not apply to any given individual. Any given individual will live to plus or minus sixty five years. And the range of difference may be very wide indeed of course. But this is all right the sixty five guesses all right when you're doing large scale gambling. And that's the way the physicist works in predicting the behavior of nuclear wavicles. But the practical problems of human life deal with variables in the hundreds of thousands. Here statistical methods are very poor. And thinking it out by linear consideration is impossible. With that equipment then we are proposing to interfere with our genes. And with that equipment also be it said we are trying to solve our political economic and social problems. And naturally everybody has the sense of total frustration. And the individual feels 'what what on earth can I do? '
```

**Run ingestion:**
```bash
python ingest_documents.py --file docs/watts_lecture_1.txt --document "Watts Doc 1"
```

**Expected Graph Output (Mermaid visualization):**

```mermaid
graph TD
    A["Human-directed evolution<br/>(Watts Doc 1, Para 1)"] --> B["Nature is unreliable<br/>(Watts Doc 1, Para 1)"]
    B --> C["Genetic intervention needed<br/>(Watts Doc 1, Para 1)"]
    C --> D["Breeding viable people<br/>(Watts Doc 1, Para 1)"]
    
    D --> E["Ghastly era<br/>(Watts Doc 1, Para 1)"]
    
    E --> F["Intelligence limitation<br/>(Watts Doc 1, Para 1, 2)"]
    F --> G["Linear scanning system<br/>(Watts Doc 1, Para 1, 2)"]
    G --> H["Sequential examination<br/>(Watts Doc 1, Para 1)"]
    H --> I["Flashlight metaphor<br/>(Watts Doc 1, Para 1)"]
    
    G --> J["Education takes time<br/>(Watts Doc 1, Para 1)"]
    J --> K["Scanning lines of text<br/>(Watts Doc 1, Para 1)"]
    K --> L["Linear information paradigm<br/>(Watts Doc 1, Para 1)"]
    
    F --> M["Multidimensional reality<br/>(Watts Doc 1, Para 2)"]
    M --> N["Everything simultaneous<br/>(Watts Doc 1, Para 2)"]
    N --> O["Too fast for linear translation<br/>(Watts Doc 1, Para 2)"]
    
    G --> P["Limited variable handling<br/>(Watts Doc 1, Para 2)"]
    P --> Q["Statistics for many variables<br/>(Watts Doc 1, Para 2)"]
    Q --> R["Stats work for large scale<br/>(Watts Doc 1, Para 2)"]
    R --> S["Poor for human complexity<br/>(Watts Doc 1, Para 2)"]
    
    S --> T["Inadequate tools for intervention<br/>(Watts Doc 1, Para 2)"]
    T --> C
    T --> U["Inadequate for social problems<br/>(Watts Doc 1, Para 2)"]
    
    U --> V["Total frustration<br/>(Watts Doc 1, Para 2)"]
    V --> W["Individual helplessness<br/>(Watts Doc 1, Para 2)"]
```

### 10.2 Example: Claude Desktop Conversation

**User query via Claude Desktop:**
```
User: "What concepts appear in Watts Doc 1 about linear thinking?"
```

**Claude uses MCP tool:**
```typescript
search_concepts({
  query: "linear thinking",
  limit: 10,
  min_similarity: 0.7
})
```

**Tool returns:**
```json
{
  "query": "linear thinking",
  "results": [
    {
      "concept_id": "linear-scanning-system",
      "label": "Linear scanning system",
      "similarity": 0.93,
      "documents": ["Watts Doc 1"],
      "evidence_count": 3
    },
    {
      "concept_id": "sequential-examination",
      "label": "Sequential examination",
      "similarity": 0.87,
      "documents": ["Watts Doc 1"],
      "evidence_count": 1
    },
    {
      "concept_id": "limited-variable-handling",
      "label": "Limited variable handling",
      "similarity": 0.82,
      "documents": ["Watts Doc 1"],
      "evidence_count": 2
    }
  ]
}
```

**Claude's response:**
```
I found 3 key concepts in Watts Doc 1 related to linear thinking:

1. **Linear scanning system** (3 instances)
   - Watts describes human intelligence as a "scanning system of conscious attention, which is linear"
   - This is the core limitation he identifies

2. **Sequential examination** (1 instance)
   - The idea that we examine the world "in lines"
   - Like "passing the beam of a flashlight across a room"

3. **Limited variable handling** (2 instances)
   - Because of linear processing, "the average person cannot deal with more than three variables at once"
   - This limitation makes it impossible to handle complex real-world problems

Would you like to see how these concepts relate to each other, or explore the evidence from the text?
```

**User follow-up:**
```
User: "How do these concepts connect to Watts' critique of genetic intervention?"
```

**Claude uses:**
```typescript
find_connections({
  from_concept_id: "linear-scanning-system",
  to_concept_id: "genetic-intervention-needed",
  max_hops: 5
})
```

**Tool returns path:**
```json
{
  "from": "linear-scanning-system",
  "to": "genetic-intervention-needed",
  "paths": [
    {
      "path": [
        {"concept_id": "linear-scanning-system", "label": "Linear scanning system"},
        {"concept_id": "intelligence-limitation", "label": "Intelligence limitation"},
        {"concept_id": "inadequate-tools-for-intervention", "label": "Inadequate tools for intervention"},
        {"concept_id": "genetic-intervention-needed", "label": "Genetic intervention needed"}
      ],
      "depth": 3,
      "relationship_types": ["part_of", "implies", "contradicts"]
    }
  ],
  "paths_found": 1
}
```

**Claude's response:**
```
I found the connection! Watts creates an ironic argument:

Linear scanning system 
  ↓ (part of)
Intelligence limitation 
  ↓ (implies)
Inadequate tools for intervention 
  ↓ (contradicts)
Genetic intervention needed

The irony: We're proposing to use our limited, linear intelligence (which can't handle complex variables) to interfere with our own genetic evolution. As Watts says: "With that equipment then we are proposing to interfere with our genes."

Would you like to visualize this connection in 3D to see the broader context?
```

**User:**
```
Yes, show me the visualization
```

**Claude uses:**
```typescript
get_visualization_url({
  concept_ids: [
    "linear-scanning-system",
    "genetic-intervention-needed",
    "intelligence-limitation",
    "inadequate-tools-for-intervention"
  ],
  depth: 1,
  center_concept: "intelligence-limitation"
})
```

**Response:**
```
View the 3D graph here: http://localhost:3000/viz/a7f3k9m

This visualization shows the concepts and their relationships, centered on "Intelligence limitation". You can:
- Rotate to see different perspectives
- Click nodes to see evidence from the text
- Explore related concepts
```

---

## 11. Technology Stack

### 11.1 Core Technologies

**Document Processing:**
- Python 3.11+
- Anthropic SDK (Claude API)
- PyPDF2 or pypdf (PDF parsing)
- python-docx (Word document parsing)
- Beautiful Soup 4 (HTML parsing)
- asyncio (concurrent processing)

**Graph Database:**
- **Phase 1:** PostgreSQL 15+ with pgvector extension
- **Phase 2:** Neo4j 5+ (optional, for advanced graph queries)

**Vector Search:**
- pgvector (PostgreSQL extension)
- OpenAI Embeddings API (text-embedding-3-small)

**MCP Server:**
- Node.js 18+
- TypeScript 5+
- @modelcontextprotocol/sdk
- pg (PostgreSQL client)
- openai (embeddings)

**Visualization:**
- React 18+
- TypeScript 5+
- force-graph-3d
- Three.js
- D3.js (optional, for layouts)

**Backend API:**
- FastAPI (Python)
- asyncpg (async PostgreSQL)
- Pydantic (data validation)

**Infrastructure:**
- Docker & Docker Compose
- GitHub (version control)
- Environment variable management (.env)

### 11.2 Development Dependencies

```json
// package.json (MCP Server)
{
  "name": "mcp-knowledge-graph-server",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "pg": "^8.11.3",
    "openai": "^4.20.0"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "@types/pg": "^8.10.9",
    "typescript": "^5.3.0",
    "tsx": "^4.7.0"
  }
}
```

```json
// package.json (Visualization)
{
  "name": "knowledge-graph-viz",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-force-graph-3d": "^1.24.0",
    "three": "^0.160.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/three": "^0.160.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

```python
# requirements.txt (Python)
anthropic>=0.18.0
asyncpg>=0.29.0
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.5.0
python-dotenv>=1.0.0
PyPDF2>=3.0.0
python-docx>=1.1.0
beautifulsoup4>=4.12.0
openai>=1.10.0
```

### 11.3 Infrastructure Setup

**Docker Compose:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: knowledge_graph
      POSTGRES_USER: kg_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

  api:
    build: ./api
    environment:
      DATABASE_URL: postgresql://kg_user:${POSTGRES_PASSWORD}@postgres:5432/knowledge_graph
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    volumes:
      - ./api:/app

  viz:
    build: ./visualization
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:8000
    volumes:
      - ./visualization:/app

volumes:
  postgres_data:
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goals:**
- Set up core infrastructure
- Implement basic document ingestion
- Create simple MCP server

**Deliverables:**
1. PostgreSQL + pgvector database
2. Document parser (text files)
3. LLM extraction pipeline (single paragraph)
4. Basic concept storage with vector embeddings
5. MCP server with 3 tools:
   - search_concepts
   - get_concept_details
   - search_by_document
6. Claude Desktop integration working

**Testing:**
- Process Watts documents
- Query via Claude Desktop
- Verify concept deduplication

### Phase 2: Graph & Visualization (Weeks 3-4)

**Goals:**
- Enhance relationship handling
- Build 3D visualization
- Add advanced querying

**Deliverables:**
1. Relationship extraction and storage
2. Graph traversal queries
3. MCP tools for graph navigation:
   - find_related_concepts
   - find_connections
4. 3D visualization web app
5. Session-based visualization URLs
6. Interactive graph controls

**Testing:**
- Visualize Watts concept graph
- Test path finding between concepts
- Verify relationship types display correctly

### Phase 3: Production Features (Weeks 5-6)

**Goals:**
- Multi-document support
- Advanced parsing
- Analytics and insights

**Deliverables:**
1. PDF and DOCX parsing
2. Batch document processing
3. Multi-client/project isolation
4. Graph analytics:
   - Concept centrality
   - Cluster detection
   - Cross-document patterns
5. Export capabilities (JSON, CSV)
6. Search improvements (hybrid vector + keyword)

**Testing:**
- Process 10+ diverse documents
- Test multi-client isolation
- Verify analytics accuracy

### Phase 4: Enhancement (Weeks 7-8)

**Goals:**
- Performance optimization
- Advanced features
- Production hardening

**Deliverables:**
1. Neo4j migration (optional)
2. Caching layer (Redis)
3. Advanced visualization:
   - Time-based filtering
   - Document comparison view
   - Concept evolution tracking
4. API authentication
5. Monitoring and logging
6. Documentation

**Testing:**
- Load testing (1000+ documents)
- Security audit
- User acceptance testing

### Deployment Checklist

**Infrastructure:**
- [ ] Set up production database (PostgreSQL or Neo4j)
- [ ] Configure vector index optimization
- [ ] Set up backup strategy
- [ ] Configure monitoring (logs, metrics)

**Security:**
- [ ] Environment variable management
- [ ] API authentication (if exposing publicly)
- [ ] Database connection security
- [ ] Rate limiting

**Documentation:**
- [ ] API documentation
- [ ] MCP tool usage guide
- [ ] Visualization user guide
- [ ] Administrator guide

---

## Appendix A: Example Queries

### A.1 SQL Queries

**Find concepts with most cross-document appearances:**
```sql
SELECT 
    c.concept_id,
    c.label,
    count(DISTINCT cs.source_id) as source_count,
    array_agg(DISTINCT s.document) as documents
FROM concepts c
JOIN concept_sources cs ON c.concept_id = cs.concept_id
JOIN sources s ON cs.source_id = s.source_id
GROUP BY c.concept_id, c.label
HAVING count(DISTINCT s.document) > 1
ORDER BY source_count DESC;
```

**Find isolated concepts (no relationships):**
```sql
SELECT c.concept_id, c.label
FROM concepts c
LEFT JOIN concept_relationships cr1 ON c.concept_id = cr1.from_concept_id
LEFT JOIN concept_relationships cr2 ON c.concept_id = cr2.to_concept_id
WHERE cr1.from_concept_id IS NULL 
AND cr2.to_concept_id IS NULL;
```

**Concept co-occurrence (appear in same documents):**
```sql
SELECT 
    c1.label as concept_1,
    c2.label as concept_2,
    count(*) as co_occurrence_count,
    array_agg(DISTINCT s.document) as shared_documents
FROM concept_sources cs1
JOIN concept_sources cs2 ON cs1.source_id = cs2.source_id
JOIN concepts c1 ON cs1.concept_id = c1.concept_id
JOIN concepts c2 ON cs2.concept_id = c2.concept_id
JOIN sources s ON cs1.source_id = s.source_id
WHERE cs1.concept_id < cs2.concept_id
GROUP BY c1.label, c2.label
HAVING count(*) > 1
ORDER BY co_occurrence_count DESC;
```

### A.2 Neo4j Cypher Queries

**Find most central concepts (highest degree):**
```cypher
MATCH (c:Concept)
OPTIONAL MATCH (c)-[r]-()
WITH c, count(r) as degree
RETURN c.concept_id, c.label, degree
ORDER BY degree DESC
LIMIT 10;
```

**Find concept clusters (community detection):**
```cypher
CALL gds.louvain.stream('concept-graph')
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId).label as concept, communityId
ORDER BY communityId, concept;
```

**Find contradicting concept pairs:**
```cypher
MATCH (c1:Concept)-[r:CONTRADICTS]->(c2:Concept)
RETURN c1.label, c2.label, r.confidence
ORDER BY r.confidence DESC;
```

---

## Appendix B: Configuration Examples

### B.1 Environment Variables

```bash
# .env
DATABASE_URL=postgresql://kg_user:password@localhost:5432/knowledge_graph
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
VISUALIZATION_URL=http://localhost:3000
LOG_LEVEL=INFO
```

### B.2 Database Initialization

```sql
-- init.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity

-- Run the main schema from section 6.1

-- Create indexes
CREATE INDEX idx_sources_document ON sources(document);
CREATE INDEX idx_instances_concept ON instances(concept_id);
CREATE INDEX idx_concept_labels_trgm ON concepts USING gin(label gin_trgm_ops);

-- Create view for common queries
CREATE VIEW concept_summary AS
SELECT 
    c.concept_id,
    c.label,
    count(DISTINCT cs.source_id) as source_count,
    count(DISTINCT i.instance_id) as instance_count,
    array_agg(DISTINCT s.document) as documents
FROM concepts c
LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
LEFT JOIN sources s ON cs.source_id = s.source_id
LEFT JOIN instances i ON c.concept_id = i.concept_id
GROUP BY c.concept_id, c.label;
```

---

## Appendix C: Troubleshooting

### C.1 Common Issues

**Vector search returns no results:**
- Check that embeddings are being generated correctly
- Verify pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname = 'vector';`
- Lower the similarity threshold
- Check vector dimensions match (1536 for text-embedding-3-small)

**Concept deduplication creating too many duplicates:**
- Lower the similarity threshold (try 0.80 instead of 0.85)
- Improve search_terms quality in LLM prompt
- Add manual review step for borderline matches

**MCP server not appearing in Claude Desktop:**
- Check config file location is correct
- Verify JSON syntax is valid
- Check file permissions on the server build
- Review Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`

**Graph visualization is slow:**
- Limit number of nodes (50-100 max for smooth performance)
- Use WebGL rendering optimizations
- Implement level-of-detail (LOD) for distant nodes
- Add pagination for large graphs

---

## 13. GraphRAG Integration: Borrowing Best Practices

While Microsoft's GraphRAG uses a different storage approach (parquet files vs. graph databases), several of their techniques can significantly enhance our architecture. This section details what to borrow and how to integrate it.

### 13.1 GraphRAG Overview

**What GraphRAG Does Well:**
- Advanced entity extraction with LLM prompting
- Community detection (Leiden algorithm) for concept clustering
- Hierarchical summarization across graph communities
- Global vs. Local query strategies
- Multi-level reasoning over large graphs

**What GraphRAG Doesn't Provide (that we need):**
- Real-time graph database (uses parquet files)
- Interactive graph traversal
- 3D visualization support
- Multi-client isolation
- Direct conversational interface (MCP)

**Our Approach:** Use GraphRAG's algorithms and prompt patterns while keeping our graph database architecture.

---

### 13.2 Community Detection (Leiden Algorithm)

**What it is:** Hierarchical clustering of concepts based on relationship density. Concepts that are highly interconnected form "communities" which can be summarized.

**Why it matters:** In consulting documents, communities represent coherent themes (e.g., "Digital Transformation Challenges", "Change Management Strategies"). This enables better summarization and querying.

#### Implementation

```python
# community_detection.py
import networkx as nx
from graspologic.partition import hierarchical_leiden
import asyncpg

async def detect_communities(db_connection, resolution: float = 1.0):
    """
    Detect hierarchical communities in the concept graph using Leiden algorithm
    
    Args:
        db_connection: PostgreSQL connection
        resolution: Higher values create more, smaller communities
    
    Returns:
        Dictionary mapping concept_id to community assignments at each level
    """
    
    # Build NetworkX graph from database
    G = nx.Graph()
    
    # Add nodes
    nodes = await db_connection.fetch("""
        SELECT concept_id, label
        FROM concepts
    """)
    
    for node in nodes:
        G.add_node(node['concept_id'], label=node['label'])
    
    # Add edges (relationships)
    edges = await db_connection.fetch("""
        SELECT from_concept_id, to_concept_id, confidence
        FROM concept_relationships
    """)
    
    for edge in edges:
        G.add_edge(
            edge['from_concept_id'], 
            edge['to_concept_id'],
            weight=edge['confidence']
        )
    
    # Run hierarchical Leiden
    communities = hierarchical_leiden(G, resolution=resolution)
    
    # Store community assignments in database
    await store_communities(db_connection, communities)
    
    return communities

async def store_communities(db_connection, communities):
    """Store community assignments in database"""
    
    # Create community tables if not exist
    await db_connection.execute("""
        CREATE TABLE IF NOT EXISTS concept_communities (
            concept_id VARCHAR(255) REFERENCES concepts(concept_id),
            level INTEGER,
            community_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (concept_id, level)
        )
    """)
    
    await db_connection.execute("""
        CREATE TABLE IF NOT EXISTS community_summaries (
            level INTEGER,
            community_id INTEGER,
            title VARCHAR(500),
            summary TEXT,
            concept_count INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (level, community_id)
        )
    """)
    
    # Insert community assignments
    for level, level_communities in enumerate(communities):
        for concept_id, community_id in level_communities.items():
            await db_connection.execute("""
                INSERT INTO concept_communities (concept_id, level, community_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (concept_id, level) 
                DO UPDATE SET community_id = $3
            """, concept_id, level, community_id)
```

#### Database Schema Extension

```sql
-- Add to existing schema

-- Community assignments
CREATE TABLE concept_communities (
    concept_id VARCHAR(255) REFERENCES concepts(concept_id),
    level INTEGER,  -- 0 = finest granularity, higher = more general
    community_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (concept_id, level)
);

-- Community summaries (generated by LLM)
CREATE TABLE community_summaries (
    level INTEGER,
    community_id INTEGER,
    title VARCHAR(500),
    summary TEXT,
    concept_count INTEGER,
    key_concepts TEXT[],  -- Top concepts in community
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (level, community_id)
);

CREATE INDEX idx_community_level ON concept_communities(level, community_id);
```

---

### 13.3 Hierarchical Summarization

**What it is:** Generate LLM-based summaries for each community at each hierarchy level.

**Why it matters:** Enables "global" queries that ask about overall themes without retrieving every concept.

#### Implementation

```python
# hierarchical_summarization.py
import anthropic
from typing import List, Dict

async def generate_community_summaries(
    db_connection,
    llm_client: anthropic.AsyncAnthropic,
    level: int = 0
):
    """
    Generate summaries for all communities at a given level
    """
    
    # Get all communities at this level
    communities = await db_connection.fetch("""
        SELECT DISTINCT community_id
        FROM concept_communities
        WHERE level = $1
        ORDER BY community_id
    """, level)
    
    for comm in communities:
        community_id = comm['community_id']
        
        # Get all concepts in this community
        concepts_data = await db_connection.fetch("""
            SELECT c.concept_id, c.label, array_agg(i.quote) as quotes
            FROM concept_communities cc
            JOIN concepts c ON cc.concept_id = c.concept_id
            LEFT JOIN instances i ON c.concept_id = i.concept_id
            WHERE cc.level = $1 AND cc.community_id = $2
            GROUP BY c.concept_id, c.label
        """, level, community_id)
        
        # Prepare data for LLM
        concepts_text = []
        for concept in concepts_data:
            quotes = concept['quotes'][:3] if concept['quotes'] else []  # Max 3 quotes
            concepts_text.append(f"- {concept['label']}: {', '.join(quotes)}")
        
        # Generate summary
        prompt = f"""You are analyzing a cluster of related concepts from documents.

CONCEPTS IN THIS CLUSTER:
{chr(10).join(concepts_text)}

TASK:
1. Create a concise title (5-10 words) that captures the main theme
2. Write a 2-3 sentence summary explaining what these concepts have in common
3. Identify 3-5 key concepts that best represent this cluster

Respond in JSON format:
{{
  "title": "Main theme title",
  "summary": "2-3 sentence summary",
  "key_concepts": ["concept-id-1", "concept-id-2", ...]
}}"""

        response = await llm_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = json.loads(response.content[0].text)
        
        # Store summary
        await db_connection.execute("""
            INSERT INTO community_summaries 
            (level, community_id, title, summary, concept_count, key_concepts)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (level, community_id)
            DO UPDATE SET 
                title = $3, 
                summary = $4, 
                concept_count = $5,
                key_concepts = $6,
                updated_at = NOW()
        """, level, community_id, result['title'], result['summary'], 
             len(concepts_data), result['key_concepts'])

# Run for all hierarchy levels
async def summarize_all_levels(db_connection, llm_client):
    max_level = await db_connection.fetchval(
        "SELECT MAX(level) FROM concept_communities"
    )
    
    for level in range(max_level + 1):
        print(f"Summarizing level {level}...")
        await generate_community_summaries(db_connection, llm_client, level)
```

---

### 13.4 Global vs. Local Query Strategies

**GraphRAG distinguishes two query modes:**

1. **Global Queries:** High-level questions about themes, patterns, overarching concepts
   - "What are the main themes in our client documents?"
   - "What are the biggest challenges mentioned across all projects?"
   - Uses community summaries, not individual concepts

2. **Local Queries:** Specific questions about particular entities or detailed relationships
   - "How does linear thinking relate to genetic intervention in Watts Doc 1?"
   - "What evidence supports the concept of 'inadequate tools'?"
   - Uses traditional graph traversal and vector search

#### Implementation in MCP Server

```typescript
// Add to MCP server tools

{
  name: "global_query",
  description: "Answer high-level questions about themes and patterns across all documents using community summaries",
  inputSchema: {
    type: "object",
    properties: {
      query: { 
        type: "string", 
        description: "High-level question about themes, patterns, or overarching concepts" 
      },
      level: {
        type: "number",
        description: "Hierarchy level to query (0=detailed, higher=more general)",
        default: 1
      }
    },
    required: ["query"]
  }
}

// Implementation
async function globalQuery(query: string, level: number = 1) {
  // Get all community summaries at this level
  const communities = await db.query(`
    SELECT 
      cs.title,
      cs.summary,
      cs.key_concepts,
      array_agg(c.label) as concept_labels
    FROM community_summaries cs
    JOIN concept_communities cc ON 
      cs.level = cc.level AND cs.community_id = cc.community_id
    JOIN concepts c ON cc.concept_id = c.concept_id
    WHERE cs.level = $1
    GROUP BY cs.level, cs.community_id, cs.title, cs.summary, cs.key_concepts
  `, [level]);

  // Build context from community summaries
  const context = communities.rows.map(c => 
    `**${c.title}**\n${c.summary}\nKey concepts: ${c.concept_labels.join(', ')}`
  ).join('\n\n');

  // Use LLM to synthesize answer from community summaries
  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 2000,
    messages: [{
      role: "user",
      content: `Based on these thematic clusters from documents, answer the question.

THEMATIC CLUSTERS:
${context}

QUESTION: ${query}

Provide a comprehensive answer that synthesizes insights across clusters.`
    }]
  });

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        query: query,
        answer: response.content[0].text,
        communities_used: communities.rows.length,
        level: level
      }, null, 2)
    }]
  };
}
```

---

### 13.5 Enhanced Entity Extraction Prompts

**GraphRAG's entity extraction prompts are well-tuned.** Adapt their pattern for better concept extraction:

```python
# Enhanced extraction prompt (inspired by GraphRAG)
EXTRACTION_PROMPT = """You are a knowledge graph extraction expert. Extract concepts, relationships, and claims from the text.

# EXTRACTION GUIDELINES

## Concepts (Entities)
- Extract key IDEAS, ARGUMENTS, CLAIMS, and PHENOMENA
- Each concept should be:
  * Atomic (one clear idea)
  * Generalizable (not overly specific to this text)
  * Meaningful (substantive, not trivial)
- Examples: "Linear thinking", "Human intelligence limitation", "Statistical methods"

## Relationships
- Extract LOGICAL connections between concepts
- Types:
  * IMPLIES: Concept A logically leads to B
  * CONTRADICTS: A is in tension with B
  * SUPPORTS: A provides evidence for B
  * PART_OF: A is a component of B
  * REQUIRES: A needs B to function
- Each relationship needs:
  * Clear directionality (from → to)
  * Confidence score (0.0-1.0)

## Evidence (Instances)
- Quote EXACT text that supports each concept
- Keep quotes focused (1-2 sentences max)
- Multiple quotes OK for same concept

# INPUT TEXT
Source: {source_id}

{text}

# EXISTING CONCEPTS (for matching)
{existing_concepts_json}

# CRITICAL MATCHING RULES
- If a concept MEANS THE SAME as an existing one → USE the existing concept_id
- If it's SIMILAR but DIFFERENT → CREATE a new concept_id
- When unsure → CREATE new (we can merge later)

# OUTPUT FORMAT (JSON only)
{{
  "extracted_concepts": [
    {{
      "concept_id": "kebab-case-id",
      "label": "Human Readable Label",
      "confidence": 0.95,
      "search_terms": ["synonym1", "synonym2", "related-term"],
      "description": "One sentence explaining this concept"
    }}
  ],
  "instances": [
    {{
      "concept_id": "matching-id-above",
      "quote": "exact text from input"
    }}
  ],
  "relationships": [
    {{
      "from_concept_id": "concept-a",
      "to_concept_id": "concept-b",
      "relationship_type": "implies",
      "confidence": 0.85,
      "explanation": "Why this relationship exists"
    }}
  ]
}}

RESPOND WITH ONLY VALID JSON."""
```

---

### 13.6 Integration Workflow

**Complete workflow incorporating GraphRAG techniques:**

```python
# integrated_pipeline.py

async def process_document_with_graphrag_techniques(
    doc_path: Path,
    doc_metadata: Dict,
    db_connection,
    llm_client
):
    """
    Enhanced document processing with GraphRAG-inspired techniques
    """
    
    # Step 1: Standard extraction (our original pipeline)
    print("Step 1: Extracting concepts...")
    paragraphs = parse_document(doc_path)
    for i, para in enumerate(paragraphs):
        source_id = f"{doc_metadata['name']}-para-{i+1}"
        extraction = await extract_concepts(para, source_id, llm_client)
        await upsert_to_graph(extraction, source_id, db_connection)
    
    # Step 2: Community detection (GraphRAG technique)
    print("Step 2: Detecting communities...")
    communities = await detect_communities(db_connection, resolution=1.0)
    
    # Step 3: Hierarchical summarization (GraphRAG technique)
    print("Step 3: Generating community summaries...")
    await summarize_all_levels(db_connection, llm_client)
    
    # Step 4: Update visualization metadata
    print("Step 4: Updating visualization metadata...")
    await update_visualization_communities(db_connection)
    
    print("Processing complete with GraphRAG enhancements!")

async def update_visualization_communities(db_connection):
    """
    Add community colors/groupings to visualization data
    """
    await db_connection.execute("""
        CREATE TABLE IF NOT EXISTS visualization_metadata (
            concept_id VARCHAR(255) PRIMARY KEY REFERENCES concepts(concept_id),
            community_color VARCHAR(7),  -- Hex color code
            community_label VARCHAR(255),
            size_multiplier DECIMAL(3,2) DEFAULT 1.0
        )
    """)
    
    # Assign colors to communities
    colors = ['#ff6b6b', '#4dabf7', '#51cf66', '#ffd43b', '#845ef7', '#ff8787', '#69db7c']
    
    communities = await db_connection.fetch("""
        SELECT cc.concept_id, cc.community_id, cs.title
        FROM concept_communities cc
        JOIN community_summaries cs ON 
            cc.level = cs.level AND cc.community_id = cs.community_id
        WHERE cc.level = 0  -- Use finest level for visualization
    """)
    
    for comm in communities:
        color = colors[comm['community_id'] % len(colors)]
        await db_connection.execute("""
            INSERT INTO visualization_metadata (concept_id, community_color, community_label)
            VALUES ($1, $2, $3)
            ON CONFLICT (concept_id) 
            DO UPDATE SET community_color = $2, community_label = $3
        """, comm['concept_id'], color, comm['title'])
```

---

### 13.7 MCP Tools for GraphRAG Features

**Add these tools to the MCP server:**

```typescript
// Community-based tools

{
  name: "get_communities",
  description: "Get thematic communities/clusters detected in the knowledge graph",
  inputSchema: {
    type: "object",
    properties: {
      level: {
        type: "number",
        description: "Hierarchy level (0=detailed, higher=more general)",
        default: 0
      },
      min_concepts: {
        type: "number",
        description: "Minimum number of concepts in community",
        default: 3
      }
    }
  }
},

{
  name: "explore_community",
  description: "Explore all concepts within a specific thematic community",
  inputSchema: {
    type: "object",
    properties: {
      community_id: { type: "number" },
      level: { type: "number", default: 0 }
    },
    required: ["community_id"]
  }
},

{
  name: "compare_communities",
  description: "Compare concepts and themes across different communities",
  inputSchema: {
    type: "object",
    properties: {
      community_ids: {
        type: "array",
        items: { type: "number" },
        description: "List of community IDs to compare"
      }
    },
    required: ["community_ids"]
  }
}

// Implementations

async function getCommunities(level: number = 0, minConcepts: number = 3) {
  const result = await db.query(`
    SELECT 
      cs.community_id,
      cs.title,
      cs.summary,
      cs.concept_count,
      cs.key_concepts
    FROM community_summaries cs
    WHERE cs.level = $1 AND cs.concept_count >= $2
    ORDER BY cs.concept_count DESC
  `, [level, minConcepts]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        level: level,
        communities: result.rows,
        total_communities: result.rows.length
      }, null, 2)
    }]
  };
}

async function exploreCommunity(communityId: number, level: number = 0) {
  // Get community summary
  const summary = await db.query(`
    SELECT * FROM community_summaries
    WHERE level = $1 AND community_id = $2
  `, [level, communityId]);

  // Get all concepts in community
  const concepts = await db.query(`
    SELECT 
      c.concept_id,
      c.label,
      array_agg(DISTINCT s.document) as documents,
      count(DISTINCT i.instance_id) as evidence_count
    FROM concept_communities cc
    JOIN concepts c ON cc.concept_id = c.concept_id
    LEFT JOIN concept_sources cs ON c.concept_id = cs.concept_id
    LEFT JOIN sources s ON cs.source_id = s.source_id
    LEFT JOIN instances i ON c.concept_id = i.concept_id
    WHERE cc.level = $1 AND cc.community_id = $2
    GROUP BY c.concept_id, c.label
    ORDER BY evidence_count DESC
  `, [level, communityId]);

  // Get internal relationships
  const relationships = await db.query(`
    SELECT 
      cr.from_concept_id,
      c1.label as from_label,
      cr.to_concept_id,
      c2.label as to_label,
      cr.relationship_type
    FROM concept_relationships cr
    JOIN concept_communities cc1 ON cr.from_concept_id = cc1.concept_id
    JOIN concept_communities cc2 ON cr.to_concept_id = cc2.concept_id
    JOIN concepts c1 ON cr.from_concept_id = c1.concept_id
    JOIN concepts c2 ON cr.to_concept_id = c2.concept_id
    WHERE cc1.level = $1 AND cc1.community_id = $2
      AND cc2.level = $1 AND cc2.community_id = $2
  `, [level, communityId]);

  return {
    content: [{
      type: "text",
      text: JSON.stringify({
        community: summary.rows[0],
        concepts: concepts.rows,
        internal_relationships: relationships.rows
      }, null, 2)
    }]
  };
}
```

---

### 13.8 Visualization Updates for Communities

**Update 3D visualization to show communities:**

```typescript
// Graph3DViewer.tsx updates

export function Graph3DViewer({ sessionId }: Graph3DViewerProps) {
  // ... existing code ...

  const getNodeColor = (node: Node) => {
    // Color by community
    if (node.community_color) {
      return node.community_color;
    }
    // Fallback to source count coloring
    const sourceCount = node.sources.length;
    if (sourceCount >= 5) return '#ff6b6b';
    if (sourceCount >= 3) return '#ffd93d';
    return '#6bcf7f';
  };

  const handleCommunityFilter = (communityId: number) => {
    // Filter graph to show only concepts in this community
    fetch(`/api/graph/community/${communityId}`)
      .then(res => res.json())
      .then(data => setGraphData(data));
  };

  return (
    <div className="graph-container">
      <div className="community-legend">
        <h3>Thematic Communities</h3>
        {communities.map(comm => (
          <div 
            key={comm.id} 
            className="community-item"
            onClick={() => handleCommunityFilter(comm.id)}
          >
            <span 
              className="color-box" 
              style={{ backgroundColor: comm.color }}
            />
            <span>{comm.title}</span>
            <span className="count">({comm.concept_count})</span>
          </div>
        ))}
      </div>

      <ForceGraph3D
        // ... existing props ...
        
        nodeColor={getNodeColor}
        
        // Community-based forces
        d3Force="cluster"
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
```

---

### 13.9 Usage Examples with GraphRAG Features

**Example 1: Global Query**

```
User: "What are the main themes across all our client documents?"

Claude uses: global_query({ query: "main themes", level: 1 })

Response: 
"I found 5 major thematic clusters:

1. Digital Transformation Challenges (23 concepts)
   - Legacy system migration, technical debt, organizational resistance

2. Change Management Strategies (18 concepts)  
   - Stakeholder engagement, training programs, communication plans

3. Cloud Infrastructure (15 concepts)
   - AWS migration, containerization, microservices architecture

4. Data Governance (12 concepts)
   - Privacy compliance, data quality, access controls

5. Innovation & AI Adoption (10 concepts)
   - Machine learning pilots, AI ethics, ROI measurement

Would you like to explore any of these clusters in detail?"
```

**Example 2: Community Exploration**

```
User: "Tell me more about the Digital Transformation cluster"

Claude uses: explore_community({ community_id: 1, level: 0 })

Response:
"The Digital Transformation Challenges cluster contains 23 interconnected concepts:

Top concepts by evidence:
• Legacy System Migration (8 instances across 3 documents)
• Technical Debt (6 instances)
• Organizational Resistance (5 instances)

Key relationships:
• Legacy Systems → Technical Debt (implies)
• Technical Debt → Migration Complexity (supports)
• Migration Complexity → Organizational Resistance (implies)

This cluster appears in:
- ACME Corp Assessment (12 concepts)
- TechCo Roadmap (8 concepts)
- Finance Inc Analysis (3 concepts)

The evidence shows organizations struggle with interconnected technical and human challenges when modernizing systems.

Would you like to see specific quotes, or visualize this cluster in 3D?"
```

---

### 13.10 Performance Considerations

**Community detection can be expensive. Optimize:**

```python
# Run community detection asynchronously after indexing
async def schedule_community_detection(db_connection):
    """
    Run community detection as a background task
    """
    # Check if graph has changed significantly since last run
    last_run = await db_connection.fetchval("""
        SELECT MAX(created_at) FROM community_summaries
    """)
    
    new_concepts = await db_connection.fetchval("""
        SELECT COUNT(*) FROM concepts
        WHERE created_at > $1
    """, last_run or datetime.min)
    
    # Only re-run if >10% new concepts
    total_concepts = await db_connection.fetchval("SELECT COUNT(*) FROM concepts")
    
    if new_concepts / total_concepts > 0.1:
        print("Significant changes detected, re-running community detection...")
        await detect_communities(db_connection)
        await summarize_all_levels(db_connection, llm_client)
    else:
        print("No significant changes, skipping community detection")
```

**Caching strategy:**

```python
# Cache community summaries for fast retrieval
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

async def get_community_summary_cached(level: int, community_id: int):
    cache_key = f"community:{level}:{community_id}"
    
    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query database
    summary = await db.fetchrow("""
        SELECT * FROM community_summaries
        WHERE level = $1 AND community_id = $2
    """, level, community_id)
    
    # Cache for 1 hour
    redis_client.setex(cache_key, 3600, json.dumps(dict(summary)))
    
    return summary
```

---

### 13.11 Summary: What We're Borrowing

**From GraphRAG (Algorithms & Patterns):**
✅ Leiden community detection algorithm  
✅ Hierarchical summarization approach  
✅ Global vs. Local query strategy  
✅ Enhanced entity extraction prompts  
✅ Multi-level reasoning patterns  

**Keeping from Our Design (Architecture):**
✅ Real graph database (PostgreSQL/Neo4j)  
✅ MCP server for Claude Desktop  
✅ 3D visualization interface  
✅ Direct provenance tracking  
✅ Multi-client isolation  
✅ Consulting-specific workflows  

**Result:** Best of both worlds - GraphRAG's intelligence with our infrastructure.

---

## Conclusion

This specification provides a complete architecture for building a knowledge graph system that:

1. **Extracts concepts** from documents using LLM analysis
2. **Maintains provenance** with full source tracking
3. **Enables discovery** through semantic search
4. **Supports exploration** via conversational AI (Claude Desktop/MCP)
5. **Visualizes structure** in interactive 3D

The system is designed to help consulting practitioners move beyond linear document scanning to explore conceptual relationships across their entire knowledge base - precisely the kind of non-linear thinking Watts advocates for.

**Next Steps:**
1. Set up development environment (PostgreSQL + pgvector)
2. Implement document ingestion pipeline
3. Build MCP server with core tools
4. Test with Watts documents
5. Develop 3D visualization
6. Expand to production use cases

---

**Document Version:** 1.0  
**Last Updated:** October 4, 2025  
**Maintained By:** Architecture Team
