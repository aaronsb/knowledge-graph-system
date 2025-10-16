-- ============================================================================
-- Knowledge Graph System - Apache AGE Initialization
-- ============================================================================
-- This script sets up the PostgreSQL database with Apache AGE extension
-- and creates the unified schema for graph + application data
-- ============================================================================

-- ----------------------------------------------------------------------------
-- STEP 1: Load Extensions
-- ----------------------------------------------------------------------------
-- Load Apache AGE extension for graph database capabilities
CREATE EXTENSION IF NOT EXISTS age;

-- Note: pgvector extension is not included in the base apache/age image
-- For now, we'll store embeddings as JSONB arrays in AGE vertex properties
-- TODO: Add pgvector support by building custom Docker image or using separate vector store

-- ----------------------------------------------------------------------------
-- STEP 2: Configure AGE
-- ----------------------------------------------------------------------------
-- Load AGE into the current session
LOAD 'age';

-- Set search path to include AGE catalog for graph operations
SET search_path = ag_catalog, "$user", public;

-- ----------------------------------------------------------------------------
-- STEP 3: Create Graph
-- ----------------------------------------------------------------------------
-- Create the main knowledge graph
SELECT create_graph('knowledge_graph');

-- ----------------------------------------------------------------------------
-- STEP 4: Graph Schema Notes
-- ----------------------------------------------------------------------------
-- Apache AGE automatically creates vertex and edge labels when they are first used
-- No explicit VLABEL/ELABEL creation needed
--
-- Vertex Labels (created on first use):
--   - Concept: Core knowledge concepts extracted from documents
--   - Source: Document sources or learned knowledge synthesis
--   - Instance: Specific quotes/evidence from sources
--
-- Edge Labels (created on first use):
--   - APPEARS_IN: Concept appears in Source
--   - EVIDENCED_BY: Concept evidenced by Instance
--   - FROM_SOURCE: Instance from Source
--   - Concept Relationships: 30 semantically sparse types organized in 8 categories
--     (see ADR-022: Semantic Relationship Taxonomy)
--
--     Categories: logical_truth, causal, structural, evidential,
--                 similarity, temporal, functional, meta
--
--     Edge Properties:
--       * confidence: FLOAT (0.0-1.0) - LLM confidence score
--       * category: STRING - Semantic category for grouping
--
--     Example types:
--       - IMPLIES, CONTRADICTS, PRESUPPOSES (logical_truth)
--       - CAUSES, ENABLES, PREVENTS, INFLUENCES (causal)
--       - PART_OF, CONTAINS, COMPOSED_OF (structural)
--       - SUPPORTS, REFUTES, EXEMPLIFIES (evidential)
--       - SIMILAR_TO, ANALOGOUS_TO, CONTRASTS_WITH (similarity)
--       - PRECEDES, CONCURRENT_WITH, EVOLVES_INTO (temporal)
--       - USED_FOR, REQUIRES, PRODUCES, REGULATES (functional)
--       - DEFINED_AS, CATEGORIZED_AS (meta)

-- ----------------------------------------------------------------------------
-- STEP 5: Property Indexes (Graph)
-- ----------------------------------------------------------------------------
-- Note: Indexes are created after labels exist (when first vertex is created)
-- These will be added programmatically by the Python client after initial data load
--
-- Planned indexes:
--   - concept_id_idx: ON Concept(properties->>'concept_id')
--   - concept_label_idx: ON Concept(properties->>'label')
--   - source_id_idx: ON Source(properties->>'source_id')
--   - source_document_idx: ON Source(properties->>'document')
--   - instance_id_idx: ON Instance(properties->>'instance_id')

-- ----------------------------------------------------------------------------
-- STEP 6: Vector Index (Semantic Search)
-- ----------------------------------------------------------------------------
-- TODO: Add vector index when pgvector is available
-- For now, embeddings are stored as JSONB arrays in vertex properties
-- Vector similarity search will use PostgreSQL JSONB operators or external library

-- Note: This is a placeholder for future pgvector integration
-- When pgvector is added:
--   CREATE INDEX concept_embedding_idx
--   ON ag_catalog."knowledge_graph"."Concept"
--   USING ivfflat (((properties->>'embedding')::vector(1536)) vector_cosine_ops)
--   WITH (lists = 100);

-- ----------------------------------------------------------------------------
-- STEP 7: Create Application Tables (PostgreSQL)
-- ----------------------------------------------------------------------------
-- Standard PostgreSQL tables for application state and user management

-- Users table: Authentication and role-based access control
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'read_only',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,

    -- Ensure role is one of: read_only, contributor, admin
    CONSTRAINT valid_role CHECK (role IN ('read_only', 'contributor', 'admin'))
);

-- API Keys table: API key management for authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP,
    expires_at TIMESTAMP,

    -- Ensure key has a name
    CONSTRAINT api_key_name CHECK (name IS NOT NULL AND LENGTH(name) > 0)
);

-- Sessions table: User session management
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT
);

-- Ingestion Jobs table: Track document ingestion progress
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    progress JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,

    -- Ensure status is valid
    CONSTRAINT valid_ingestion_status CHECK (
        status IN ('queued', 'pending_approval', 'approved', 'running', 'completed', 'failed', 'cancelled')
    )
);

-- Restore Jobs table: Track backup restore operations
CREATE TABLE IF NOT EXISTS restore_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    backup_filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    progress JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,

    -- Ensure status is valid
    CONSTRAINT valid_restore_status CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
    )
);

-- Audit Log table: Track all operations for security and compliance
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Documents table: Store source documents
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by INTEGER REFERENCES users(id),

    -- Ensure filename is unique
    CONSTRAINT unique_filename UNIQUE (filename)
);

-- Backups metadata table: Track backup history
CREATE TABLE IF NOT EXISTS backups (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id),
    size_bytes BIGINT,
    backup_type VARCHAR(50),
    ontology_filter VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'completed',

    -- Ensure backup type is valid
    CONSTRAINT valid_backup_type CHECK (
        backup_type IN ('full', 'ontology', 'incremental')
    )
);

-- ----------------------------------------------------------------------------
-- STEP 8: Create Indexes (Application Tables)
-- ----------------------------------------------------------------------------
-- Indexes for efficient querying of application tables

-- User indexes
CREATE INDEX IF NOT EXISTS users_username_idx ON users(username);
CREATE INDEX IF NOT EXISTS users_role_idx ON users(role);

-- API key indexes
CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS api_keys_hash_idx ON api_keys(key_hash);

-- Session indexes
CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions(session_token);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions(expires_at);

-- Job indexes
CREATE INDEX IF NOT EXISTS ingestion_jobs_status_idx ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS ingestion_jobs_user_idx ON ingestion_jobs(user_id);
CREATE INDEX IF NOT EXISTS restore_jobs_status_idx ON restore_jobs(status);

-- Audit log indexes
CREATE INDEX IF NOT EXISTS audit_log_user_idx ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS audit_log_action_idx ON audit_log(action);
CREATE INDEX IF NOT EXISTS audit_log_timestamp_idx ON audit_log(timestamp);

-- Document indexes
CREATE INDEX IF NOT EXISTS documents_uploaded_by_idx ON documents(uploaded_by);

-- ----------------------------------------------------------------------------
-- STEP 9: Create Roles and Permissions (RBAC)
-- ----------------------------------------------------------------------------
-- PostgreSQL roles for role-based access control

-- Read-only role: Can query graph and view data
CREATE ROLE kg_read_only;
GRANT CONNECT ON DATABASE knowledge_graph TO kg_read_only;
GRANT USAGE ON SCHEMA ag_catalog, public TO kg_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA ag_catalog TO kg_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO kg_read_only;

-- Contributor role: Can add/modify graph data
CREATE ROLE kg_contributor;
GRANT kg_read_only TO kg_contributor;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA ag_catalog TO kg_contributor;
GRANT INSERT, UPDATE ON ingestion_jobs, documents TO kg_contributor;

-- Admin role: Full access to all operations
CREATE ROLE kg_admin;
GRANT ALL PRIVILEGES ON DATABASE knowledge_graph TO kg_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ag_catalog TO kg_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kg_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kg_admin;

-- ----------------------------------------------------------------------------
-- STEP 10: Create Default Admin User
-- ----------------------------------------------------------------------------
-- Create a default admin user for initial access
-- Password: 'admin' (CHANGE THIS IN PRODUCTION!)

INSERT INTO users (username, password_hash, role)
VALUES (
    'admin',
    -- bcrypt hash of 'admin' (CHANGE THIS!)
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tNi',
    'admin'
) ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- Initialization Complete
-- ============================================================================
-- To verify setup:
--   SELECT * FROM ag_catalog.ag_graph;
--   SELECT * FROM ag_catalog.ag_label WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph');
--   \dt (to list application tables)
--   SELECT * FROM users;
-- ============================================================================
