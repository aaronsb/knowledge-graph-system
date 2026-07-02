-- Migration 028: Platform Admin Resources and Role (ADR-074)
--
-- Registers RBAC resources for all API endpoints and creates platform_admin role.
--
-- Idempotent: Safe to run multiple times (uses ON CONFLICT DO NOTHING)
-- Recovery: Re-run this migration to restore default permissions if locked out
--
-- Resources registered:
--   Platform Administration: api_keys, embedding_config, extraction_config, backups, admin
--   Content & Data: ontologies, graph, ingest, sources, vocabulary, vocabulary_config, database
--   Identity & Access: users, oauth_clients, rbac

BEGIN;

-- =============================================================================
-- Register All Resource Types
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES
    -- Platform Administration (Critical)
    ('api_keys', 'API key management for AI providers',
     ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('embedding_config', 'Embedding model configuration and operations',
     ARRAY['read', 'create', 'delete', 'activate', 'reload', 'regenerate'], FALSE, 'system'),
    ('extraction_config', 'AI extraction provider configuration',
     ARRAY['read', 'write'], FALSE, 'system'),
    ('backups', 'System backup and restore operations',
     ARRAY['read', 'create', 'restore'], FALSE, 'system'),
    ('admin', 'Admin dashboard and status',
     ARRAY['status'], FALSE, 'system'),

    -- Content & Data
    ('ontologies', 'Ontology management including deletion',
     ARRAY['read', 'create', 'delete'], FALSE, 'system'),
    ('graph', 'Knowledge graph queries',
     ARRAY['read', 'execute'], FALSE, 'system'),
    ('ingest', 'Document ingestion',
     ARRAY['create'], FALSE, 'system'),
    ('sources', 'Source document retrieval',
     ARRAY['read'], FALSE, 'system'),
    ('vocabulary', 'Vocabulary type management',
     ARRAY['read', 'write'], FALSE, 'system'),
    ('vocabulary_config', 'Vocabulary configuration and profiles',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system'),
    ('database', 'Database statistics and queries',
     ARRAY['read', 'execute'], FALSE, 'system'),

    -- Identity & Access
    ('users', 'User account management',
     ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('oauth_clients', 'OAuth client management (all clients)',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system'),
    ('rbac', 'RBAC roles, resources, and permissions',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system')
ON CONFLICT (resource_type) DO NOTHING;

-- =============================================================================
-- Create Platform Admin Role
-- =============================================================================

INSERT INTO kg_auth.roles (role_name, display_name, description, is_builtin, is_active, parent_role)
VALUES (
    'platform_admin',
    'Platform Administrator',
    'Full platform access including critical operations. Recovery requires re-running migration.',
    TRUE,
    TRUE,
    'admin'
)
ON CONFLICT (role_name) DO NOTHING;

-- =============================================================================
-- Grant Permissions to Contributor Role (content access)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('contributor', 'graph', 'read', 'global', TRUE),
    ('contributor', 'ingest', 'create', 'global', TRUE),
    ('contributor', 'sources', 'read', 'global', TRUE),
    ('contributor', 'vocabulary', 'read', 'global', TRUE),
    ('contributor', 'ontologies', 'read', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Permissions to Curator Role (content management)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('curator', 'vocabulary', 'write', 'global', TRUE),
    ('curator', 'ontologies', 'create', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Permissions to Admin Role (user/system management, read-only platform)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- Platform resources: read only
    ('admin', 'api_keys', 'read', 'global', TRUE),
    ('admin', 'embedding_config', 'read', 'global', TRUE),
    ('admin', 'extraction_config', 'read', 'global', TRUE),
    ('admin', 'backups', 'read', 'global', TRUE),
    ('admin', 'admin', 'status', 'global', TRUE),
    -- OAuth Clients: full access
    ('admin', 'oauth_clients', 'read', 'global', TRUE),
    ('admin', 'oauth_clients', 'create', 'global', TRUE),
    ('admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Users: full access
    ('admin', 'users', 'read', 'global', TRUE),
    ('admin', 'users', 'write', 'global', TRUE),
    ('admin', 'users', 'delete', 'global', TRUE),
    -- RBAC: read only
    ('admin', 'rbac', 'read', 'global', TRUE),
    -- Vocabulary config: read only
    ('admin', 'vocabulary_config', 'read', 'global', TRUE),
    -- Database: read only
    ('admin', 'database', 'read', 'global', TRUE),
    -- Ontologies: delete (admins manage ontology lifecycle)
    ('admin', 'ontologies', 'delete', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Full Permissions to Platform Admin Role
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- API Keys: full access
    ('platform_admin', 'api_keys', 'read', 'global', TRUE),
    ('platform_admin', 'api_keys', 'write', 'global', TRUE),
    ('platform_admin', 'api_keys', 'delete', 'global', TRUE),
    -- Embedding Config: full access
    ('platform_admin', 'embedding_config', 'read', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'create', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'delete', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'activate', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'reload', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'regenerate', 'global', TRUE),
    -- Extraction Config: full access
    ('platform_admin', 'extraction_config', 'read', 'global', TRUE),
    ('platform_admin', 'extraction_config', 'write', 'global', TRUE),
    -- OAuth Clients: full access
    ('platform_admin', 'oauth_clients', 'read', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'write', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'create', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Ontologies: full access including delete
    ('platform_admin', 'ontologies', 'delete', 'global', TRUE),
    -- Backups: full access including restore
    ('platform_admin', 'backups', 'read', 'global', TRUE),
    ('platform_admin', 'backups', 'create', 'global', TRUE),
    ('platform_admin', 'backups', 'restore', 'global', TRUE),
    -- RBAC: full access
    ('platform_admin', 'rbac', 'read', 'global', TRUE),
    ('platform_admin', 'rbac', 'write', 'global', TRUE),
    ('platform_admin', 'rbac', 'create', 'global', TRUE),
    ('platform_admin', 'rbac', 'delete', 'global', TRUE),
    -- Vocabulary config: full access
    ('platform_admin', 'vocabulary_config', 'read', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'write', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'create', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'delete', 'global', TRUE),
    -- Database: full access including execute
    ('platform_admin', 'database', 'read', 'global', TRUE),
    ('platform_admin', 'database', 'execute', 'global', TRUE),
    -- Graph: execute (raw Cypher)
    ('platform_admin', 'graph', 'execute', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (28, 'platform_admin_resources')
ON CONFLICT (version) DO NOTHING;

COMMIT;
