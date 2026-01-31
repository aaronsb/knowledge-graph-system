// ============================================================================
// Knowledge Graph Schema Initialization
// ============================================================================
// This script sets up the core schema for the knowledge graph system:
// - Unique constraints to ensure data integrity
// - Indexes for query performance
// - Vector index for semantic search capabilities
// - Enhanced Source nodes for learned knowledge synthesis
// ============================================================================
//
// SOURCE NODE SCHEMA:
// Document sources (extracted from ingested files):
//   - source_id: unique identifier
//   - document: document name
//   - paragraph: paragraph number
//   - full_text: complete paragraph text
//   - type: "DOCUMENT"
//
// Learned sources (AI/human synthesized knowledge):
//   - source_id: "learned_YYYY-MM-DD_NNN"
//   - document: "User synthesis" | "AI synthesis"
//   - paragraph: 0
//   - full_text: evidence/rationale text
//   - type: "LEARNED"
//   - created_by: "username" | "claude-mcp" | "claude-code"
//   - created_at: ISO timestamp
//   - similarity_score: float (smell test result)
//   - cognitive_leap: "LOW" | "MEDIUM" | "HIGH"
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

// Ontology nodes: Each ontology must have a unique identifier (ADR-200)
CREATE CONSTRAINT ontology_id_unique IF NOT EXISTS
FOR (o:Ontology)
REQUIRE o.ontology_id IS UNIQUE;

// Ontology nodes: Each ontology name must be unique
CREATE CONSTRAINT ontology_name_unique IF NOT EXISTS
FOR (o:Ontology)
REQUIRE o.name IS UNIQUE;

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

// Index on Source type for filtering document vs learned knowledge
CREATE INDEX source_type_index IF NOT EXISTS
FOR (s:Source)
ON (s.type);

// Index on Source creator for filtering learned knowledge by author
CREATE INDEX source_creator_index IF NOT EXISTS
FOR (s:Source)
ON (s.created_by);

// Index on Instance text for full-text search (optional, can be replaced with full-text index)
CREATE INDEX instance_text_index IF NOT EXISTS
FOR (i:Instance)
ON (i.text);

// Index on Ontology name for fast ontology lookups (ADR-200)
CREATE INDEX ontology_name_index IF NOT EXISTS
FOR (o:Ontology)
ON (o.name);

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

// Ontology embeddings — same vector space as concepts (ADR-200)
// Enables cosine similarity between ontologies and concepts
CREATE VECTOR INDEX `ontology-embeddings` IF NOT EXISTS
FOR (o:Ontology)
ON (o.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

// ----------------------------------------------------------------------------
// FULL-TEXT SEARCH INDEX
// ----------------------------------------------------------------------------
// Enables advanced full-text search on Instance quotes
// Supports: phrase queries, fuzzy matching, stemming, boolean operators
// Use: CALL db.index.fulltext.queryNodes('instance_fulltext', 'query')

CREATE FULLTEXT INDEX instance_fulltext IF NOT EXISTS
FOR (i:Instance)
ON EACH [i.quote];

// Full-text search on Concept labels and search terms
CREATE FULLTEXT INDEX concept_fulltext IF NOT EXISTS
FOR (c:Concept)
ON EACH [c.label, c.search_terms];

// ----------------------------------------------------------------------------
// ONTOLOGY NODE SCHEMA (ADR-200)
// ----------------------------------------------------------------------------
// Ontology nodes are first-class graph entities in the same embedding space
// as concepts. They represent knowledge domains that organize Source nodes
// via :SCOPED_BY edges. See ADR-200 for the full data model.
//
// Properties:
//   - ontology_id: unique identifier (ont_<uuid>)
//   - name: ontology name (matches s.document on Source nodes)
//   - description: what this knowledge domain covers
//   - embedding: 1536-dim vector in the SAME space as concepts
//   - search_terms: alternative names for similarity matching
//   - creation_epoch: global epoch when created
//   - lifecycle_state: 'active' | 'pinned' | 'frozen'
//
// Edges:
//   (:Source)-[:SCOPED_BY]->(:Ontology)        — source membership
//   (:Ontology)-[:ANCHORED_BY]->(:Concept)     — promoted from concept (Phase 4)
//   (:Ontology)-[:OVERLAPS]->(:Ontology)       — significant concept overlap (Phase 5)
//   (:Ontology)-[:SPECIALIZES]->(:Ontology)    — coherent subset relationship (Phase 5)
//   (:Ontology)-[:GENERALIZES]->(:Ontology)    — superset relationship (Phase 5)
//
// Edge properties (OVERLAPS, SPECIALIZES, GENERALIZES):
//   source: 'annealing_worker' | 'manual'
//   score: affinity strength (0.0-1.0)
//   shared_concept_count: concepts in common
//   computed_at_epoch: global epoch when derived
// ----------------------------------------------------------------------------

// ============================================================================
// Schema initialization complete
// ============================================================================
// To verify schema:
// - SHOW CONSTRAINTS;
// - SHOW INDEXES;
// ============================================================================
