-- Multi-Schema PostgreSQL Architecture
-- Implements ADR-024 (Multi-Schema Architecture), ADR-025 (Dynamic Vocabulary), ADR-026 (Autonomous Curation)
-- Date: 2025-10-10
-- Description: Defines kg_api, kg_auth, kg_logs schemas with operational tables

-- =============================================================================
-- SCHEMA CREATION
-- =============================================================================

-- API State Schema (replaces SQLite jobs.db)
CREATE SCHEMA IF NOT EXISTS kg_api;

-- Security Schema (authentication & authorization)
CREATE SCHEMA IF NOT EXISTS kg_auth;

-- Observability Schema (audit logs, metrics, telemetry)
CREATE SCHEMA IF NOT EXISTS kg_logs;

-- Note: ag_catalog schema is managed by Apache AGE extension

-- =============================================================================
-- KG_API SCHEMA - Operational State
-- =============================================================================

-- Job Queue (replaces SQLite jobs.db)
CREATE TABLE IF NOT EXISTS kg_api.ingestion_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN (
        'pending',
        'awaiting_approval',
        'approved',
        'queued',
        'running',
        'completed',
        'failed',
        'cancelled'
    )),
    ontology VARCHAR(200) NOT NULL,
    client_id VARCHAR(100),
    content_hash VARCHAR(80),  -- Deduplication (sha256: prefix + 64 hex = 71 chars)
    job_data JSONB NOT NULL,   -- Request payload
    progress JSONB,            -- Live updates
    result JSONB,              -- Final stats
    analysis JSONB,            -- Pre-ingestion cost estimates (ADR-014)
    processing_mode VARCHAR(20) DEFAULT 'serial' CHECK (processing_mode IN ('serial', 'parallel')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by VARCHAR(100),
    expires_at TIMESTAMPTZ,
    error_message TEXT
);

-- Indexes for job queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON kg_api.ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_ontology ON kg_api.ingestion_jobs(ontology);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON kg_api.ingestion_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_client_id ON kg_api.ingestion_jobs(client_id);
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON kg_api.ingestion_jobs(content_hash);

-- Active Sessions
CREATE TABLE IF NOT EXISTS kg_api.sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON kg_api.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON kg_api.sessions(expires_at);

-- Rate Limiting
CREATE TABLE IF NOT EXISTS kg_api.rate_limits (
    client_id VARCHAR(100) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (client_id, endpoint, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON kg_api.rate_limits(window_start);

-- Background Workers
CREATE TABLE IF NOT EXISTS kg_api.worker_status (
    worker_id VARCHAR(100) PRIMARY KEY,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_job_id VARCHAR(50),
    status VARCHAR(50) NOT NULL CHECK (status IN ('idle', 'running', 'error', 'stopped')),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_worker_heartbeat ON kg_api.worker_status(last_heartbeat DESC);

-- =============================================================================
-- RELATIONSHIP VOCABULARY MANAGEMENT (ADR-025)
-- =============================================================================

-- Relationship Vocabulary (canonical types)
CREATE TABLE IF NOT EXISTS kg_api.relationship_vocabulary (
    relationship_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    category VARCHAR(50),
    added_by VARCHAR(100),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_builtin BOOLEAN DEFAULT FALSE,
    synonyms VARCHAR(100)[],
    deprecation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_vocab_category ON kg_api.relationship_vocabulary(category);
CREATE INDEX IF NOT EXISTS idx_vocab_active ON kg_api.relationship_vocabulary(is_active);
CREATE INDEX IF NOT EXISTS idx_vocab_usage ON kg_api.relationship_vocabulary(usage_count DESC);

-- Skipped Relationships (capture layer)
CREATE TABLE IF NOT EXISTS kg_api.skipped_relationships (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    from_concept_label VARCHAR(500),
    to_concept_label VARCHAR(500),
    job_id VARCHAR(50),
    ontology VARCHAR(200),
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    occurrence_count INTEGER DEFAULT 1,
    sample_context JSONB,
    UNIQUE(relationship_type, from_concept_label, to_concept_label)
);

CREATE INDEX IF NOT EXISTS idx_skipped_type ON kg_api.skipped_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_skipped_count ON kg_api.skipped_relationships(occurrence_count DESC);
CREATE INDEX IF NOT EXISTS idx_skipped_first_seen ON kg_api.skipped_relationships(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_skipped_ontology ON kg_api.skipped_relationships(ontology);

-- Vocabulary Audit Trail
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_audit (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100),
    action VARCHAR(50) NOT NULL,  -- 'added', 'aliased', 'deprecated', 'backfilled'
    performed_by VARCHAR(100),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_vocab_audit_type ON kg_api.vocabulary_audit(relationship_type);
CREATE INDEX IF NOT EXISTS idx_vocab_audit_performed_at ON kg_api.vocabulary_audit(performed_at DESC);

-- =============================================================================
-- PERFORMANCE OPTIMIZATION TABLES (ADR-025)
-- =============================================================================

-- Edge Usage Statistics (hot paths, traversal frequency)
CREATE TABLE IF NOT EXISTS kg_api.edge_usage_stats (
    from_concept_id VARCHAR(100) NOT NULL,
    to_concept_id VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    traversal_count INTEGER DEFAULT 0,
    last_traversed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    PRIMARY KEY (from_concept_id, to_concept_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_edge_usage_count ON kg_api.edge_usage_stats(traversal_count DESC);
CREATE INDEX IF NOT EXISTS idx_edge_usage_type ON kg_api.edge_usage_stats(relationship_type);
CREATE INDEX IF NOT EXISTS idx_edge_usage_from ON kg_api.edge_usage_stats(from_concept_id);

-- Concept Access Statistics (node-level tracking)
CREATE TABLE IF NOT EXISTS kg_api.concept_access_stats (
    concept_id VARCHAR(100) PRIMARY KEY,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    queries_as_start INTEGER DEFAULT 0,
    queries_as_result INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_concept_access_count ON kg_api.concept_access_stats(access_count DESC);
CREATE INDEX IF NOT EXISTS idx_concept_access_last ON kg_api.concept_access_stats(last_accessed DESC);

-- Hot Edges Materialized View (top 1000 most-traversed edges)
CREATE MATERIALIZED VIEW IF NOT EXISTS kg_api.hot_edges AS
SELECT
    from_concept_id,
    to_concept_id,
    relationship_type,
    traversal_count
FROM kg_api.edge_usage_stats
WHERE traversal_count > 100
ORDER BY traversal_count DESC
LIMIT 1000;

CREATE INDEX IF NOT EXISTS idx_hot_edges_lookup ON kg_api.hot_edges(from_concept_id, to_concept_id);

-- Hot Concepts Materialized View (top 100 most-accessed concepts)
CREATE MATERIALIZED VIEW IF NOT EXISTS kg_api.hot_concepts AS
SELECT
    concept_id,
    access_count,
    queries_as_start
FROM kg_api.concept_access_stats
WHERE access_count > 50
ORDER BY access_count DESC
LIMIT 100;

CREATE INDEX IF NOT EXISTS idx_hot_concepts_id ON kg_api.hot_concepts(concept_id);

-- =============================================================================
-- AUTONOMOUS VOCABULARY MANAGEMENT (ADR-026)
-- =============================================================================

-- Ontology Version Registry (formal versioning)
CREATE TABLE IF NOT EXISTS kg_api.ontology_versions (
    version_id SERIAL PRIMARY KEY,
    version_number VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    change_summary TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    vocabulary_snapshot JSONB NOT NULL,
    types_added TEXT[],
    types_aliased JSONB,
    types_deprecated TEXT[],
    backward_compatible BOOLEAN DEFAULT TRUE,
    migration_required BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_ontology_versions_number ON kg_api.ontology_versions(version_number);
CREATE INDEX IF NOT EXISTS idx_ontology_versions_active ON kg_api.ontology_versions(is_active);

-- Concept Version Metadata (provenance tracking)
CREATE TABLE IF NOT EXISTS kg_api.concept_version_metadata (
    concept_id VARCHAR(100) PRIMARY KEY,
    created_in_version INTEGER REFERENCES kg_api.ontology_versions(version_id),
    last_modified_version INTEGER REFERENCES kg_api.ontology_versions(version_id)
);

-- Vocabulary Suggestions (LLM-assisted curation)
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_suggestions (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    suggestion_type VARCHAR(50) NOT NULL CHECK (suggestion_type IN ('alias', 'new_type')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    suggested_canonical_type VARCHAR(100),  -- If alias
    suggested_category VARCHAR(50),         -- If new_type
    suggested_description TEXT,             -- If new_type
    similar_types JSONB,                    -- Array of {type, similarity, reasoning}
    reasoning TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE,
    curator_decision VARCHAR(50),
    curator_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_vocab_suggestions_type ON kg_api.vocabulary_suggestions(relationship_type);
CREATE INDEX IF NOT EXISTS idx_vocab_suggestions_confidence ON kg_api.vocabulary_suggestions(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_vocab_suggestions_reviewed ON kg_api.vocabulary_suggestions(reviewed);

-- =============================================================================
-- KG_AUTH SCHEMA - Security
-- =============================================================================

-- User Accounts
CREATE TABLE IF NOT EXISTS kg_auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('read_only', 'contributor', 'curator', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    disabled BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_users_username ON kg_auth.users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON kg_auth.users(role);

-- API Keys
CREATE TABLE IF NOT EXISTS kg_auth.api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    name VARCHAR(200),
    scopes TEXT[],  -- ['read:concepts', 'write:ingest', 'admin:vocabulary']
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON kg_auth.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON kg_auth.api_keys(user_id);

-- OAuth Tokens (future)
CREATE TABLE IF NOT EXISTS kg_auth.oauth_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    provider VARCHAR(50),
    scopes TEXT[],
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oauth_user_id ON kg_auth.oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_expires ON kg_auth.oauth_tokens(expires_at);

-- Role Permissions
CREATE TABLE IF NOT EXISTS kg_auth.role_permissions (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    resource VARCHAR(100) NOT NULL,  -- 'concepts', 'vocabulary', 'jobs', 'users'
    action VARCHAR(50) NOT NULL,     -- 'read', 'write', 'delete', 'approve'
    granted BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(role, resource, action)
);

CREATE INDEX IF NOT EXISTS idx_role_perms_role ON kg_auth.role_permissions(role);

-- =============================================================================
-- KG_LOGS SCHEMA - Observability
-- =============================================================================

-- Audit Trail (compliance, security)
CREATE TABLE IF NOT EXISTS kg_logs.audit_trail (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(200),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    outcome VARCHAR(50) NOT NULL CHECK (outcome IN ('success', 'denied', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON kg_logs.audit_trail(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON kg_logs.audit_trail(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON kg_logs.audit_trail(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON kg_logs.audit_trail(resource_type, resource_id);

-- Performance Metrics
CREATE TABLE IF NOT EXISTS kg_logs.api_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms NUMERIC(10,2) NOT NULL,
    client_id VARCHAR(100),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON kg_logs.api_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_metrics_endpoint ON kg_logs.api_metrics(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_metrics_duration ON kg_logs.api_metrics(duration_ms DESC);

-- Job Events (detailed history)
CREATE TABLE IF NOT EXISTS kg_logs.job_events (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON kg_logs.job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_job_events_timestamp ON kg_logs.job_events(timestamp DESC);

-- System Health Checks
CREATE TABLE IF NOT EXISTS kg_logs.health_checks (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('healthy', 'degraded', 'down')),
    metrics JSONB
);

CREATE INDEX IF NOT EXISTS idx_health_timestamp ON kg_logs.health_checks(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_service ON kg_logs.health_checks(service);

-- =============================================================================
-- SEED DATA - Builtin Relationship Types
-- =============================================================================

INSERT INTO kg_api.relationship_vocabulary (relationship_type, description, category, is_builtin, is_active)
VALUES
    ('IMPLIES', 'One concept logically implies another', 'logical', TRUE, TRUE),
    ('SUPPORTS', 'One concept provides evidence for another', 'evidential', TRUE, TRUE),
    ('CONTRADICTS', 'One concept contradicts another', 'logical', TRUE, TRUE),
    ('RESULTS_FROM', 'One concept is a consequence of another', 'causation', TRUE, TRUE),
    ('ENABLES', 'One concept makes another possible', 'causation', TRUE, TRUE),
    ('REQUIRES', 'One concept needs another to exist or function', 'dependency', TRUE, TRUE),
    ('INFLUENCES', 'One concept affects another without direct causation', 'causation', TRUE, TRUE),
    ('COMPLEMENTS', 'One concept works together with another', 'composition', TRUE, TRUE),
    ('OVERLAPS', 'Two concepts share common elements', 'semantic', TRUE, TRUE),
    ('EXTENDS', 'One concept builds upon another', 'composition', TRUE, TRUE),
    ('SPECIALIZES', 'One concept is a specific instance of another', 'hierarchical', TRUE, TRUE),
    ('GENERALIZES', 'One concept is a broader category of another', 'hierarchical', TRUE, TRUE),
    ('PART_OF', 'One concept is a component of another', 'composition', TRUE, TRUE),
    ('HAS_PART', 'One concept contains another as a component', 'composition', TRUE, TRUE),
    ('PRECEDES', 'One concept comes before another in sequence', 'temporal', TRUE, TRUE),
    ('FOLLOWS', 'One concept comes after another in sequence', 'temporal', TRUE, TRUE),
    ('CAUSES', 'One concept directly causes another', 'causation', TRUE, TRUE),
    ('PREVENTS', 'One concept stops another from occurring', 'causation', TRUE, TRUE),
    ('RELATED_TO', 'Generic relationship when specific type unclear', 'semantic', TRUE, TRUE),
    ('OPPOSITE_OF', 'One concept is the inverse or contrary of another', 'semantic', TRUE, TRUE),
    ('ANALOGOUS_TO', 'One concept is similar in structure or function to another', 'semantic', TRUE, TRUE),
    ('DEPENDS_ON', 'One concept relies on another for functionality', 'dependency', TRUE, TRUE),
    ('INSTANTIATES', 'One concept is a concrete example of another', 'hierarchical', TRUE, TRUE),
    ('DEFINES', 'One concept provides the definition or meaning of another', 'semantic', TRUE, TRUE),
    ('IMPLEMENTED_BY', 'One concept is realized through another', 'implementation', TRUE, TRUE),
    ('IMPLEMENTS', 'One concept realizes or executes another', 'implementation', TRUE, TRUE),
    ('COMPOSED_OF', 'One concept is made up of multiple instances of another', 'composition', TRUE, TRUE),
    ('DERIVED_FROM', 'One concept originates from another', 'derivation', TRUE, TRUE),
    ('PRODUCES', 'One concept creates or generates another', 'causation', TRUE, TRUE),
    ('CONSUMES', 'One concept uses or depletes another', 'dependency', TRUE, TRUE)
ON CONFLICT (relationship_type) DO NOTHING;

-- Initial ontology version
INSERT INTO kg_api.ontology_versions (
    version_number,
    created_by,
    change_summary,
    vocabulary_snapshot,
    types_added,
    backward_compatible
)
SELECT
    '1.0.0',
    'system',
    'Initial vocabulary: 30 builtin relationship types',
    jsonb_agg(row_to_json(rv)),
    ARRAY(SELECT relationship_type FROM kg_api.relationship_vocabulary WHERE is_builtin = TRUE),
    TRUE
FROM kg_api.relationship_vocabulary rv
WHERE is_builtin = TRUE
ON CONFLICT (version_number) DO NOTHING;

-- =============================================================================
-- ADMIN USER INITIALIZATION (ADR-027)
-- =============================================================================
--
-- SECURITY: No default admin user is created in the schema.
--
-- To create the admin user, run the initialization script:
--   ./scripts/initialize-auth.sh
--
-- This will:
--   1. Prompt for a secure admin password (with strength validation)
--   2. Generate a cryptographically secure JWT_SECRET_KEY
--   3. Create the admin user with bcrypt-hashed password
--   4. Save JWT_SECRET_KEY to .env file
--
-- For automated/CI environments, you can also create the admin user manually:
--   docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
--     "INSERT INTO kg_auth.users (username, password_hash, role, created_at)
--      VALUES ('admin', crypt('YOUR_PASSWORD', gen_salt('bf', 12)), 'admin', NOW())"
--
-- DO NOT commit default passwords to the schema - this is a security risk!
-- =============================================================================

-- Seed default role permissions
INSERT INTO kg_auth.role_permissions (role, resource, action, granted)
VALUES
    -- read_only role
    ('read_only', 'concepts', 'read', TRUE),
    ('read_only', 'vocabulary', 'read', TRUE),
    ('read_only', 'jobs', 'read', TRUE),

    -- contributor role (can ingest)
    ('contributor', 'concepts', 'read', TRUE),
    ('contributor', 'concepts', 'write', TRUE),
    ('contributor', 'vocabulary', 'read', TRUE),
    ('contributor', 'jobs', 'read', TRUE),
    ('contributor', 'jobs', 'write', TRUE),

    -- curator role (can manage vocabulary)
    ('curator', 'concepts', 'read', TRUE),
    ('curator', 'concepts', 'write', TRUE),
    ('curator', 'vocabulary', 'read', TRUE),
    ('curator', 'vocabulary', 'write', TRUE),
    ('curator', 'vocabulary', 'approve', TRUE),
    ('curator', 'jobs', 'read', TRUE),
    ('curator', 'jobs', 'approve', TRUE),

    -- admin role (full access)
    ('admin', 'concepts', 'read', TRUE),
    ('admin', 'concepts', 'write', TRUE),
    ('admin', 'concepts', 'delete', TRUE),
    ('admin', 'vocabulary', 'read', TRUE),
    ('admin', 'vocabulary', 'write', TRUE),
    ('admin', 'vocabulary', 'approve', TRUE),
    ('admin', 'vocabulary', 'delete', TRUE),
    ('admin', 'jobs', 'read', TRUE),
    ('admin', 'jobs', 'write', TRUE),
    ('admin', 'jobs', 'approve', TRUE),
    ('admin', 'jobs', 'delete', TRUE),
    ('admin', 'users', 'read', TRUE),
    ('admin', 'users', 'write', TRUE),
    ('admin', 'users', 'delete', TRUE)
ON CONFLICT (role, resource, action) DO NOTHING;

-- =============================================================================
-- MAINTENANCE FUNCTIONS
-- =============================================================================

-- Function to refresh hot edges materialized view
CREATE OR REPLACE FUNCTION refresh_hot_edges()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_edges;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh hot concepts materialized view
CREATE OR REPLACE FUNCTION refresh_hot_concepts()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_concepts;
END;
$$ LANGUAGE plpgsql;

-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM kg_api.sessions WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old jobs
CREATE OR REPLACE FUNCTION archive_old_jobs(days_threshold INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Move old completed jobs to job_events (logs)
    INSERT INTO kg_logs.job_events (job_id, timestamp, event_type, details)
    SELECT
        job_id,
        completed_at,
        'archived',
        jsonb_build_object(
            'status', status,
            'ontology', ontology,
            'result', result
        )
    FROM kg_api.ingestion_jobs
    WHERE completed_at < NOW() - (days_threshold || ' days')::INTERVAL
      AND status IN ('completed', 'failed');

    -- Delete archived jobs
    DELETE FROM kg_api.ingestion_jobs
    WHERE completed_at < NOW() - (days_threshold || ' days')::INTERVAL
      AND status IN ('completed', 'failed');

    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================================================

COMMENT ON SCHEMA kg_api IS 'API operational state: jobs, sessions, rate limits, vocabulary management (ADR-024)';
COMMENT ON SCHEMA kg_auth IS 'Security: authentication, authorization, access control (ADR-024)';
COMMENT ON SCHEMA kg_logs IS 'Observability: audit trails, metrics, telemetry (ADR-024)';

COMMENT ON TABLE kg_api.ingestion_jobs IS 'Job queue (replaces SQLite jobs.db) - ADR-024';
COMMENT ON TABLE kg_api.relationship_vocabulary IS 'Canonical relationship types with descriptions - ADR-025';
COMMENT ON TABLE kg_api.skipped_relationships IS 'Capture layer for unmatched relationship types - ADR-025';
COMMENT ON TABLE kg_api.edge_usage_stats IS 'Performance tracking for graph traversals - ADR-025';
COMMENT ON TABLE kg_api.concept_access_stats IS 'Node-level access patterns for caching - ADR-025';
COMMENT ON TABLE kg_api.ontology_versions IS 'Formal ontology versioning with immutable snapshots - ADR-026';
COMMENT ON TABLE kg_api.vocabulary_suggestions IS 'LLM-assisted vocabulary curation suggestions - ADR-026';

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Verification query
DO $$
DECLARE
    schema_count INTEGER;
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO schema_count
    FROM information_schema.schemata
    WHERE schema_name IN ('kg_api', 'kg_auth', 'kg_logs');

    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema IN ('kg_api', 'kg_auth', 'kg_logs');

    RAISE NOTICE 'Migration complete:';
    RAISE NOTICE '  - Schemas created: %', schema_count;
    RAISE NOTICE '  - Tables created: %', table_count;
    RAISE NOTICE '  - Builtin vocabulary types: 30';
    RAISE NOTICE '  - Initial ontology version: 1.0.0';
END $$;
