-- ============================================================================
-- Knowledge Graph System - Consolidated Baseline Schema
-- ============================================================================
-- PostgreSQL + Apache AGE unified schema
-- Date: 2025-10-16
-- Version: 2.0.0 (Baseline Consolidation)
--
-- This script consolidates all schema definitions and migrations into a single
-- baseline. It replaces the previous multi-file approach with a single source
-- of truth for the database schema.
--
-- Includes:
--   - Apache AGE extension initialization
--   - Multi-schema architecture (kg_api, kg_auth, kg_logs)
--   - Dynamic RBAC system (ADR-028)
--   - Vocabulary management (ADR-025, ADR-026, ADR-032)
--   - All applied migrations
-- ============================================================================

-- ----------------------------------------------------------------------------
-- STEP 1: Extensions and Configuration
-- ----------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- ----------------------------------------------------------------------------
-- STEP 2: Create Knowledge Graph
-- ----------------------------------------------------------------------------

SELECT create_graph('knowledge_graph');

-- ============================================================================
-- STEP 3: Create Schemas
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS kg_api;     -- API operational state
CREATE SCHEMA IF NOT EXISTS kg_auth;    -- Authentication & authorization
CREATE SCHEMA IF NOT EXISTS kg_logs;    -- Audit logs & observability

COMMENT ON SCHEMA kg_api IS 'API operational state: jobs, sessions, vocabulary (ADR-024, ADR-025)';
COMMENT ON SCHEMA kg_auth IS 'Security: authentication, authorization, RBAC (ADR-024, ADR-028)';
COMMENT ON SCHEMA kg_logs IS 'Observability: audit trails, metrics, telemetry (ADR-024)';

-- ============================================================================
-- Migration Tracking (ADR-040)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied ON public.schema_migrations(applied_at DESC);

COMMENT ON TABLE public.schema_migrations IS 'Tracks applied schema migrations for safe schema evolution - ADR-040';
COMMENT ON COLUMN public.schema_migrations.version IS 'Sequential migration number (001, 002, 003, ...)';
COMMENT ON COLUMN public.schema_migrations.name IS 'Descriptive migration name (e.g., baseline, add_embedding_config)';
COMMENT ON COLUMN public.schema_migrations.applied_at IS 'Timestamp when migration was applied';

-- ============================================================================
-- KG_API SCHEMA - Operational State
-- ============================================================================

-- Job Queue (ADR-014, ADR-024)
CREATE TABLE kg_api.ingestion_jobs (
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
    content_hash VARCHAR(80),  -- sha256: prefix (7) + 64 hex = 71 chars (fixed in migration 002)
    job_data JSONB NOT NULL,
    progress JSONB,
    result JSONB,
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

CREATE INDEX idx_jobs_status ON kg_api.ingestion_jobs(status);
CREATE INDEX idx_jobs_ontology ON kg_api.ingestion_jobs(ontology);
CREATE INDEX idx_jobs_created_at ON kg_api.ingestion_jobs(created_at DESC);
CREATE INDEX idx_jobs_client_id ON kg_api.ingestion_jobs(client_id);
CREATE INDEX idx_jobs_content_hash ON kg_api.ingestion_jobs(content_hash);

COMMENT ON TABLE kg_api.ingestion_jobs IS 'Job queue (replaces SQLite jobs.db) - ADR-014, ADR-024';

-- Active Sessions
CREATE TABLE kg_api.sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_sessions_user_id ON kg_api.sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON kg_api.sessions(expires_at);

-- Rate Limiting
CREATE TABLE kg_api.rate_limits (
    client_id VARCHAR(100) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (client_id, endpoint, window_start)
);

CREATE INDEX idx_rate_limits_window ON kg_api.rate_limits(window_start);

-- Background Workers
CREATE TABLE kg_api.worker_status (
    worker_id VARCHAR(100) PRIMARY KEY,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_job_id VARCHAR(50),
    status VARCHAR(50) NOT NULL CHECK (status IN ('idle', 'running', 'error', 'stopped')),
    metadata JSONB
);

CREATE INDEX idx_worker_heartbeat ON kg_api.worker_status(last_heartbeat DESC);

-- ============================================================================
-- Relationship Vocabulary Management (ADR-025, ADR-032)
-- ============================================================================

-- Relationship Vocabulary (canonical types with embeddings)
CREATE TABLE kg_api.relationship_vocabulary (
    relationship_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    category VARCHAR(50),
    added_by VARCHAR(100),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_builtin BOOLEAN DEFAULT FALSE,
    synonyms VARCHAR(100)[],
    deprecation_reason TEXT,
    -- ADR-032 additions:
    embedding JSONB,                      -- Cached vector as JSON array
    embedding_model VARCHAR(100),         -- Model used (e.g., text-embedding-ada-002)
    embedding_generated_at TIMESTAMPTZ
);

CREATE INDEX idx_vocab_category ON kg_api.relationship_vocabulary(category);
CREATE INDEX idx_vocab_active ON kg_api.relationship_vocabulary(is_active);
CREATE INDEX idx_vocab_usage ON kg_api.relationship_vocabulary(usage_count DESC);
CREATE INDEX idx_vocab_embedding_model ON kg_api.relationship_vocabulary(embedding_model)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE kg_api.relationship_vocabulary IS 'Canonical relationship types with embeddings - ADR-025, ADR-032';
COMMENT ON COLUMN kg_api.relationship_vocabulary.embedding IS 'Cached embedding vector (JSONB array) for synonym detection (ADR-032)';

-- Skipped Relationships (capture layer)
CREATE TABLE kg_api.skipped_relationships (
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

CREATE INDEX idx_skipped_type ON kg_api.skipped_relationships(relationship_type);
CREATE INDEX idx_skipped_count ON kg_api.skipped_relationships(occurrence_count DESC);
CREATE INDEX idx_skipped_first_seen ON kg_api.skipped_relationships(first_seen DESC);
CREATE INDEX idx_skipped_ontology ON kg_api.skipped_relationships(ontology);

COMMENT ON TABLE kg_api.skipped_relationships IS 'Capture layer for unmatched relationship types - ADR-025';

-- Vocabulary Audit Trail
CREATE TABLE kg_api.vocabulary_audit (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100),
    action VARCHAR(50) NOT NULL,
    performed_by VARCHAR(100),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB
);

CREATE INDEX idx_vocab_audit_type ON kg_api.vocabulary_audit(relationship_type);
CREATE INDEX idx_vocab_audit_performed_at ON kg_api.vocabulary_audit(performed_at DESC);

-- Vocabulary History (ADR-032 detailed tracking)
CREATE TABLE kg_api.vocabulary_history (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('added', 'merged', 'pruned', 'deprecated', 'reactivated')),
    performed_by VARCHAR(100) NOT NULL,
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_type VARCHAR(100),
    reason TEXT,
    metadata JSONB,
    aggressiveness NUMERIC(4,3),
    zone VARCHAR(20),
    vocab_size_before INTEGER,
    vocab_size_after INTEGER
);

CREATE INDEX idx_vocab_history_type ON kg_api.vocabulary_history(relationship_type);
CREATE INDEX idx_vocab_history_action ON kg_api.vocabulary_history(action);
CREATE INDEX idx_vocab_history_performed_at ON kg_api.vocabulary_history(performed_at DESC);
CREATE INDEX idx_vocab_history_performed_by ON kg_api.vocabulary_history(performed_by);

COMMENT ON TABLE kg_api.vocabulary_history IS 'Detailed vocabulary change tracking with context (ADR-032)';

-- Pruning Recommendations (ADR-032)
CREATE TABLE kg_api.pruning_recommendations (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('merge', 'prune', 'deprecate', 'skip')),
    review_level VARCHAR(20) NOT NULL CHECK (review_level IN ('none', 'ai', 'human')),
    reasoning TEXT NOT NULL,
    similarity NUMERIC(4,3),
    value_score NUMERIC(10,2),
    metadata JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(100),
    reviewer_notes TEXT,
    executed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_pruning_recs_type ON kg_api.pruning_recommendations(relationship_type);
CREATE INDEX idx_pruning_recs_status ON kg_api.pruning_recommendations(status);
CREATE INDEX idx_pruning_recs_review_level ON kg_api.pruning_recommendations(review_level);
CREATE INDEX idx_pruning_recs_created_at ON kg_api.pruning_recommendations(created_at DESC);
CREATE INDEX idx_pruning_recs_expires_at ON kg_api.pruning_recommendations(expires_at)
    WHERE expires_at IS NOT NULL;

COMMENT ON TABLE kg_api.pruning_recommendations IS 'Pending vocabulary management actions - ADR-032';

-- Vocabulary Configuration
CREATE TABLE kg_api.vocabulary_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(100)
);

CREATE INDEX idx_vocab_config_updated_at ON kg_api.vocabulary_config(updated_at DESC);
COMMENT ON TABLE kg_api.vocabulary_config IS 'System configuration for automatic vocabulary management (ADR-032)';

-- ============================================================================
-- Performance Optimization (ADR-025)
-- ============================================================================

-- Edge Usage Statistics
CREATE TABLE kg_api.edge_usage_stats (
    from_concept_id VARCHAR(100) NOT NULL,
    to_concept_id VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    traversal_count INTEGER DEFAULT 0,
    last_traversed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    PRIMARY KEY (from_concept_id, to_concept_id, relationship_type)
);

CREATE INDEX idx_edge_usage_count ON kg_api.edge_usage_stats(traversal_count DESC);
CREATE INDEX idx_edge_usage_type ON kg_api.edge_usage_stats(relationship_type);
CREATE INDEX idx_edge_usage_from ON kg_api.edge_usage_stats(from_concept_id);

COMMENT ON TABLE kg_api.edge_usage_stats IS 'Performance tracking for graph traversals - ADR-025';

-- Concept Access Statistics
CREATE TABLE kg_api.concept_access_stats (
    concept_id VARCHAR(100) PRIMARY KEY,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    avg_query_time_ms NUMERIC(10,2),
    queries_as_start INTEGER DEFAULT 0,
    queries_as_result INTEGER DEFAULT 0
);

CREATE INDEX idx_concept_access_count ON kg_api.concept_access_stats(access_count DESC);
CREATE INDEX idx_concept_access_last ON kg_api.concept_access_stats(last_accessed DESC);

COMMENT ON TABLE kg_api.concept_access_stats IS 'Node-level access patterns for caching - ADR-025';

-- Hot Edges Materialized View
CREATE MATERIALIZED VIEW kg_api.hot_edges AS
SELECT
    from_concept_id,
    to_concept_id,
    relationship_type,
    traversal_count
FROM kg_api.edge_usage_stats
WHERE traversal_count > 100
ORDER BY traversal_count DESC
LIMIT 1000;

CREATE INDEX idx_hot_edges_lookup ON kg_api.hot_edges(from_concept_id, to_concept_id);

-- Hot Concepts Materialized View
CREATE MATERIALIZED VIEW kg_api.hot_concepts AS
SELECT
    concept_id,
    access_count,
    queries_as_start
FROM kg_api.concept_access_stats
WHERE access_count > 50
ORDER BY access_count DESC
LIMIT 100;

CREATE INDEX idx_hot_concepts_id ON kg_api.hot_concepts(concept_id);

-- ============================================================================
-- Autonomous Vocabulary Management (ADR-026)
-- ============================================================================

-- Ontology Version Registry
CREATE TABLE kg_api.ontology_versions (
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

CREATE INDEX idx_ontology_versions_number ON kg_api.ontology_versions(version_number);
CREATE INDEX idx_ontology_versions_active ON kg_api.ontology_versions(is_active);

COMMENT ON TABLE kg_api.ontology_versions IS 'Formal ontology versioning with immutable snapshots - ADR-026';

-- Concept Version Metadata
CREATE TABLE kg_api.concept_version_metadata (
    concept_id VARCHAR(100) PRIMARY KEY,
    created_in_version INTEGER REFERENCES kg_api.ontology_versions(version_id),
    last_modified_version INTEGER REFERENCES kg_api.ontology_versions(version_id)
);

-- Vocabulary Suggestions (LLM-assisted curation)
CREATE TABLE kg_api.vocabulary_suggestions (
    id SERIAL PRIMARY KEY,
    relationship_type VARCHAR(100) NOT NULL,
    suggestion_type VARCHAR(50) NOT NULL CHECK (suggestion_type IN ('alias', 'new_type')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    suggested_canonical_type VARCHAR(100),
    suggested_category VARCHAR(50),
    suggested_description TEXT,
    similar_types JSONB,
    reasoning TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE,
    curator_decision VARCHAR(50),
    curator_notes TEXT
);

CREATE INDEX idx_vocab_suggestions_type ON kg_api.vocabulary_suggestions(relationship_type);
CREATE INDEX idx_vocab_suggestions_confidence ON kg_api.vocabulary_suggestions(confidence DESC);
CREATE INDEX idx_vocab_suggestions_reviewed ON kg_api.vocabulary_suggestions(reviewed);

COMMENT ON TABLE kg_api.vocabulary_suggestions IS 'LLM-assisted vocabulary curation suggestions - ADR-026';
-- Embedding Configuration - Moved to migration 003 (ADR-039)
-- See: schema/migrations/003_add_embedding_config.sql

-- ============================================================================
-- KG_AUTH SCHEMA - Security (ADR-028 Dynamic RBAC)
-- ============================================================================

-- Resource Registry
CREATE TABLE kg_auth.resources (
    resource_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    parent_type VARCHAR(100) REFERENCES kg_auth.resources(resource_type),
    available_actions VARCHAR(50)[] NOT NULL,
    supports_scoping BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(100)
);

CREATE INDEX idx_resources_parent ON kg_auth.resources(parent_type);
COMMENT ON TABLE kg_auth.resources IS 'Dynamic resource type registry (ADR-028)';

-- Dynamic Roles
CREATE TABLE kg_auth.roles (
    role_name VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_builtin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    parent_role VARCHAR(50) REFERENCES kg_auth.roles(role_name),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER,  -- Will reference users.id after users table is created
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_roles_parent ON kg_auth.roles(parent_role);
CREATE INDEX idx_roles_builtin ON kg_auth.roles(is_builtin);
CREATE INDEX idx_roles_active ON kg_auth.roles(is_active);
COMMENT ON TABLE kg_auth.roles IS 'Dynamic role definitions with inheritance (ADR-028)';

-- User Accounts
CREATE TABLE kg_auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    primary_role VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    disabled BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_users_username ON kg_auth.users(username);
CREATE INDEX idx_users_primary_role ON kg_auth.users(primary_role);

COMMENT ON COLUMN kg_auth.users.primary_role IS 'Primary role (backwards compatibility) - user can have additional roles in user_roles table';

-- Now that users table exists, add the foreign key to roles.created_by
ALTER TABLE kg_auth.roles ADD CONSTRAINT fk_roles_created_by
    FOREIGN KEY (created_by) REFERENCES kg_auth.users(id);

-- User Role Assignments (multiple roles per user)
CREATE TABLE kg_auth.user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,
    scope_type VARCHAR(50),
    scope_id VARCHAR(200),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by INTEGER REFERENCES kg_auth.users(id),
    expires_at TIMESTAMPTZ,
    UNIQUE(user_id, role_name, scope_type, scope_id)
);

CREATE INDEX idx_user_roles_user ON kg_auth.user_roles(user_id);
CREATE INDEX idx_user_roles_role ON kg_auth.user_roles(role_name);
CREATE INDEX idx_user_roles_scope ON kg_auth.user_roles(scope_type, scope_id);
CREATE INDEX idx_user_roles_expires ON kg_auth.user_roles(expires_at) WHERE expires_at IS NOT NULL;

COMMENT ON TABLE kg_auth.user_roles IS 'User role assignments with optional scoping (ADR-028)';

-- Role Permissions (scoped permissions)
CREATE TABLE kg_auth.role_permissions (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,
    resource_type VARCHAR(100) NOT NULL REFERENCES kg_auth.resources(resource_type),
    action VARCHAR(50) NOT NULL,
    scope_type VARCHAR(50),
    scope_id VARCHAR(200),
    scope_filter JSONB,
    granted BOOLEAN NOT NULL DEFAULT TRUE,
    inherited_from VARCHAR(50) REFERENCES kg_auth.roles(role_name),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id)
);

CREATE UNIQUE INDEX idx_role_perms_unique_with_scope
    ON kg_auth.role_permissions(role_name, resource_type, action, scope_type, scope_id)
    WHERE scope_id IS NOT NULL;

CREATE UNIQUE INDEX idx_role_perms_unique_without_scope
    ON kg_auth.role_permissions(role_name, resource_type, action, scope_type)
    WHERE scope_id IS NULL;

CREATE INDEX idx_role_perms_role ON kg_auth.role_permissions(role_name);
CREATE INDEX idx_role_perms_resource ON kg_auth.role_permissions(resource_type, action);
CREATE INDEX idx_role_perms_scope ON kg_auth.role_permissions(scope_type, scope_id);
CREATE INDEX idx_role_perms_granted ON kg_auth.role_permissions(granted) WHERE granted = FALSE;

COMMENT ON TABLE kg_auth.role_permissions IS 'Dynamic role permissions with scoping (ADR-028)';

-- API Keys
CREATE TABLE kg_auth.api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    name VARCHAR(200),
    scopes TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_key_hash ON kg_auth.api_keys(key_hash);
CREATE INDEX idx_api_keys_user_id ON kg_auth.api_keys(user_id);

-- OAuth Tokens (future)
CREATE TABLE kg_auth.oauth_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    provider VARCHAR(50),
    scopes TEXT[],
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_oauth_user_id ON kg_auth.oauth_tokens(user_id);
CREATE INDEX idx_oauth_expires ON kg_auth.oauth_tokens(expires_at);

-- ============================================================================
-- KG_LOGS SCHEMA - Observability
-- ============================================================================

-- Audit Trail
CREATE TABLE kg_logs.audit_trail (
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

CREATE INDEX idx_audit_timestamp ON kg_logs.audit_trail(timestamp DESC);
CREATE INDEX idx_audit_user_id ON kg_logs.audit_trail(user_id);
CREATE INDEX idx_audit_action ON kg_logs.audit_trail(action);
CREATE INDEX idx_audit_resource ON kg_logs.audit_trail(resource_type, resource_id);

-- API Performance Metrics
CREATE TABLE kg_logs.api_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms NUMERIC(10,2) NOT NULL,
    client_id VARCHAR(100),
    error_message TEXT
);

CREATE INDEX idx_api_metrics_timestamp ON kg_logs.api_metrics(timestamp DESC);
CREATE INDEX idx_api_metrics_endpoint ON kg_logs.api_metrics(endpoint);
CREATE INDEX idx_api_metrics_duration ON kg_logs.api_metrics(duration_ms DESC);

-- Job Events
CREATE TABLE kg_logs.job_events (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    details JSONB
);

CREATE INDEX idx_job_events_job_id ON kg_logs.job_events(job_id);
CREATE INDEX idx_job_events_timestamp ON kg_logs.job_events(timestamp DESC);

-- System Health Checks
CREATE TABLE kg_logs.health_checks (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('healthy', 'degraded', 'down')),
    metrics JSONB
);

CREATE INDEX idx_health_timestamp ON kg_logs.health_checks(timestamp DESC);
CREATE INDEX idx_health_service ON kg_logs.health_checks(service);

-- ============================================================================
-- MAINTENANCE FUNCTIONS
-- ============================================================================

-- Refresh hot edges materialized view
CREATE OR REPLACE FUNCTION refresh_hot_edges()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_edges;
END;
$$ LANGUAGE plpgsql;

-- Refresh hot concepts materialized view
CREATE OR REPLACE FUNCTION refresh_hot_concepts()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_concepts;
END;
$$ LANGUAGE plpgsql;

-- Clean expired sessions
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

-- Archive old jobs
CREATE OR REPLACE FUNCTION archive_old_jobs(days_threshold INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
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

    DELETE FROM kg_api.ingestion_jobs
    WHERE completed_at < NOW() - (days_threshold || ' days')::INTERVAL
      AND status IN ('completed', 'failed');

    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- Expire old pruning recommendations (ADR-032)
CREATE OR REPLACE FUNCTION expire_old_recommendations(days_threshold INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE kg_api.pruning_recommendations
    SET status = 'expired'
    WHERE status = 'pending'
      AND created_at < NOW() - (days_threshold || ' days')::INTERVAL
      AND expires_at IS NULL;

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_recommendations IS 'Expire pending recommendations older than threshold (ADR-032)';

-- Check if user has permission (ADR-028)
CREATE OR REPLACE FUNCTION kg_auth.has_permission(
    p_user_id INTEGER,
    p_resource_type VARCHAR,
    p_action VARCHAR,
    p_resource_id VARCHAR DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_permission BOOLEAN := FALSE;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM kg_auth.user_roles ur
        JOIN kg_auth.role_permissions rp ON ur.role_name = rp.role_name
        WHERE ur.user_id = p_user_id
          AND rp.resource_type = p_resource_type
          AND rp.action = p_action
          AND rp.scope_type = 'global'
          AND rp.granted = TRUE
          AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
    ) INTO v_has_permission;

    RETURN v_has_permission;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.has_permission IS 'Check if user has permission (simple global check - extend for scoped permissions)';

-- Get user's effective roles (ADR-028)
CREATE OR REPLACE FUNCTION kg_auth.get_user_roles(p_user_id INTEGER)
RETURNS TABLE (
    role_name VARCHAR,
    scope_type VARCHAR,
    scope_id VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ur.role_name,
        ur.scope_type,
        ur.scope_id
    FROM kg_auth.user_roles ur
    WHERE ur.user_id = p_user_id
      AND (ur.expires_at IS NULL OR ur.expires_at > NOW());
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.get_user_roles IS 'Get all active roles for a user';

-- ============================================================================
-- AUDIT TRIGGERS (ADR-028)
-- ============================================================================

-- Audit role assignments
CREATE OR REPLACE FUNCTION kg_auth.audit_role_assignment()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO kg_logs.audit_trail (user_id, action, resource_type, resource_id, details, outcome)
        VALUES (
            NEW.assigned_by,
            'assign_role',
            'user_roles',
            NEW.user_id::TEXT,
            jsonb_build_object(
                'role_name', NEW.role_name,
                'scope_type', NEW.scope_type,
                'scope_id', NEW.scope_id,
                'expires_at', NEW.expires_at
            ),
            'success'
        );
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO kg_logs.audit_trail (action, resource_type, resource_id, details, outcome)
        VALUES (
            'unassign_role',
            'user_roles',
            OLD.user_id::TEXT,
            jsonb_build_object(
                'role_name', OLD.role_name,
                'scope_type', OLD.scope_type,
                'scope_id', OLD.scope_id
            ),
            'success'
        );
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_user_roles
    AFTER INSERT OR DELETE ON kg_auth.user_roles
    FOR EACH ROW EXECUTE FUNCTION kg_auth.audit_role_assignment();

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Seed builtin resources (ADR-028)
INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES
    ('concepts', 'Knowledge graph concepts and nodes', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('vocabulary', 'Relationship vocabulary management', ARRAY['read', 'write', 'approve', 'delete'], FALSE, 'system'),
    ('jobs', 'Ingestion job management', ARRAY['read', 'write', 'approve', 'delete'], FALSE, 'system'),
    ('users', 'User account management', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('roles', 'Role and permission management', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('resources', 'Resource type registration', ARRAY['read', 'write', 'delete'], FALSE, 'system')
ON CONFLICT (resource_type) DO NOTHING;

-- Seed builtin roles (ADR-028)
INSERT INTO kg_auth.roles (role_name, display_name, description, is_builtin, is_active)
VALUES
    ('read_only', 'Read Only', 'Read access to public resources', TRUE, TRUE),
    ('contributor', 'Contributor', 'Can create and modify content', TRUE, TRUE),
    ('curator', 'Curator', 'Can approve and manage content', TRUE, TRUE),
    ('admin', 'Administrator', 'Full system access', TRUE, TRUE)
ON CONFLICT (role_name) DO NOTHING;

-- Seed role permissions (ADR-028)
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- read_only role
    ('read_only', 'concepts', 'read', 'global', TRUE),
    ('read_only', 'vocabulary', 'read', 'global', TRUE),
    ('read_only', 'jobs', 'read', 'global', TRUE),
    -- contributor role
    ('contributor', 'concepts', 'read', 'global', TRUE),
    ('contributor', 'concepts', 'write', 'global', TRUE),
    ('contributor', 'vocabulary', 'read', 'global', TRUE),
    ('contributor', 'jobs', 'read', 'global', TRUE),
    ('contributor', 'jobs', 'write', 'global', TRUE),
    -- curator role
    ('curator', 'concepts', 'read', 'global', TRUE),
    ('curator', 'concepts', 'write', 'global', TRUE),
    ('curator', 'vocabulary', 'read', 'global', TRUE),
    ('curator', 'vocabulary', 'write', 'global', TRUE),
    ('curator', 'vocabulary', 'approve', 'global', TRUE),
    ('curator', 'jobs', 'read', 'global', TRUE),
    ('curator', 'jobs', 'approve', 'global', TRUE),
    ('curator', 'roles', 'read', 'global', TRUE),
    ('curator', 'resources', 'read', 'global', TRUE),
    -- admin role
    ('admin', 'concepts', 'read', 'global', TRUE),
    ('admin', 'concepts', 'write', 'global', TRUE),
    ('admin', 'concepts', 'delete', 'global', TRUE),
    ('admin', 'vocabulary', 'read', 'global', TRUE),
    ('admin', 'vocabulary', 'write', 'global', TRUE),
    ('admin', 'vocabulary', 'approve', 'global', TRUE),
    ('admin', 'vocabulary', 'delete', 'global', TRUE),
    ('admin', 'jobs', 'read', 'global', TRUE),
    ('admin', 'jobs', 'write', 'global', TRUE),
    ('admin', 'jobs', 'approve', 'global', TRUE),
    ('admin', 'jobs', 'delete', 'global', TRUE),
    ('admin', 'users', 'read', 'global', TRUE),
    ('admin', 'users', 'write', 'global', TRUE),
    ('admin', 'users', 'delete', 'global', TRUE),
    ('admin', 'roles', 'read', 'global', TRUE),
    ('admin', 'roles', 'write', 'global', TRUE),
    ('admin', 'roles', 'delete', 'global', TRUE),
    ('admin', 'resources', 'read', 'global', TRUE),
    ('admin', 'resources', 'write', 'global', TRUE),
    ('admin', 'resources', 'delete', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- Seed builtin relationship vocabulary (ADR-025)
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

-- Seed vocabulary configuration (ADR-032)
INSERT INTO kg_api.vocabulary_config (key, value, description, updated_by)
VALUES
    ('vocab_min', '30', 'Minimum vocabulary size (protected core types)', 'system'),
    ('vocab_max', '90', 'Maximum vocabulary size (soft limit)', 'system'),
    ('vocab_emergency', '200', 'Emergency threshold (aggressive pruning)', 'system'),
    ('aggressiveness_profile', 'aggressive', 'Bezier curve profile for pruning aggressiveness', 'system'),
    ('pruning_mode', 'hitl', 'Decision mode: naive, hitl, aitl', 'system'),
    ('embedding_model', 'text-embedding-ada-002', 'OpenAI model for embeddings', 'system'),
    ('auto_expand_enabled', 'false', 'Enable automatic vocabulary expansion', 'system'),
    ('synonym_threshold_strong', '0.90', 'Strong synonym threshold (auto-merge)', 'system'),
    ('synonym_threshold_moderate', '0.70', 'Moderate synonym threshold (review)', 'system'),
    ('low_value_threshold', '1.0', 'Value score threshold for pruning consideration', 'system')
ON CONFLICT (key) DO NOTHING;

-- Seed initial ontology version (ADR-026)
INSERT INTO kg_api.ontology_versions (
    version_number,
    created_by,
    change_summary,
    vocabulary_snapshot,
    types_added,
    backward_compatible
)
SELECT
    '2.0.0',
    'system',
    'Baseline schema consolidation: 30 builtin relationship types',
    jsonb_agg(row_to_json(rv)),
    ARRAY(SELECT relationship_type FROM kg_api.relationship_vocabulary WHERE is_builtin = TRUE),
    TRUE
FROM kg_api.relationship_vocabulary rv
WHERE is_builtin = TRUE
ON CONFLICT (version_number) DO NOTHING;

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
DECLARE
    schema_count INTEGER;
    table_count INTEGER;
    vocab_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO schema_count
    FROM information_schema.schemata
    WHERE schema_name IN ('kg_api', 'kg_auth', 'kg_logs');

    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema IN ('kg_api', 'kg_auth', 'kg_logs');

    SELECT COUNT(*) INTO vocab_count
    FROM kg_api.relationship_vocabulary
    WHERE is_builtin = TRUE;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Baseline Schema Initialization Complete';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Version: 2.0.0 (Consolidated Baseline)';
    RAISE NOTICE 'Date: 2025-10-16';
    RAISE NOTICE '';
    RAISE NOTICE 'Schemas created: %', schema_count;
    RAISE NOTICE 'Tables created: %', table_count;
    RAISE NOTICE 'Builtin vocabulary types: %', vocab_count;
    RAISE NOTICE 'Initial ontology version: 2.0.0';
    RAISE NOTICE '';
    RAISE NOTICE 'Includes:';
    RAISE NOTICE '  - Apache AGE graph database';
    RAISE NOTICE '  - Multi-schema architecture (ADR-024)';
    RAISE NOTICE '  - Dynamic RBAC system (ADR-028)';
    RAISE NOTICE '  - Vocabulary management (ADR-025, ADR-026, ADR-032)';
    RAISE NOTICE '  - Migration tracking system (ADR-040)';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- Record Baseline Migration (ADR-040)
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (1, 'baseline')
ON CONFLICT (version) DO NOTHING;
