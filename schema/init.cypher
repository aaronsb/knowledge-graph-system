// ============================================================================
// Knowledge Graph Schema Initialization
// ============================================================================
// This script sets up the core schema for the knowledge graph system:
// - Unique constraints to ensure data integrity
// - Indexes for query performance
// - Vector index for semantic search capabilities
// ============================================================================

// ----------------------------------------------------------------------------
// UNIQUE CONSTRAINTS
// ----------------------------------------------------------------------------
// Constraints ensure that key identifier fields are unique across nodes
// and automatically create indexes for fast lookups

// Concept nodes: Each concept must have a unique identifier
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
FOR (c:Concept)
REQUIRE c.concept_id IS UNIQUE;

// Source nodes: Each source document must have a unique identifier
CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (s:Source)
REQUIRE s.source_id IS UNIQUE;

// Instance nodes: Each instance must have a unique identifier
CREATE CONSTRAINT instance_id_unique IF NOT EXISTS
FOR (i:Instance)
REQUIRE i.instance_id IS UNIQUE;

// ----------------------------------------------------------------------------
// PROPERTY INDEXES
// ----------------------------------------------------------------------------
// Additional indexes for commonly queried properties to improve performance

// Index on Concept labels for fast concept name lookups
CREATE INDEX concept_label_index IF NOT EXISTS
FOR (c:Concept)
ON (c.label);

// Index on Source documents for fast source filtering
CREATE INDEX source_document_index IF NOT EXISTS
FOR (s:Source)
ON (s.document);

// Index on Instance text for full-text search (optional, can be replaced with full-text index)
CREATE INDEX instance_text_index IF NOT EXISTS
FOR (i:Instance)
ON (i.text);

// ----------------------------------------------------------------------------
// VECTOR INDEX
// ----------------------------------------------------------------------------
// Vector index enables semantic similarity search using embeddings
// Configured for OpenAI's text-embedding-3-small (1536 dimensions)
// Uses cosine similarity for comparing concept embeddings

CREATE VECTOR INDEX `concept-embeddings` IF NOT EXISTS
FOR (c:Concept)
ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

// ----------------------------------------------------------------------------
// OPTIONAL: Full-Text Search Index
// ----------------------------------------------------------------------------
// Uncomment if you need advanced full-text search on Instance text
// This enables phrase queries, fuzzy matching, and stemming

// CREATE FULLTEXT INDEX instance_fulltext IF NOT EXISTS
// FOR (i:Instance)
// ON EACH [i.text];

// ============================================================================
// Schema initialization complete
// ============================================================================
// To verify schema:
// - SHOW CONSTRAINTS;
// - SHOW INDEXES;
// ============================================================================
