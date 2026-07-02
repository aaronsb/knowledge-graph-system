-- Migration 041: Job RBAC Permissions
--
-- Registers 'jobs' as an RBAC resource with scoped permissions for job management.
-- Enables proper access control for viewing, canceling, and deleting jobs.
--
-- Idempotent: Safe to run multiple times (uses ON CONFLICT DO NOTHING)
--
-- Permission Model:
--   - read_only: read own jobs only
--   - contributor: read/cancel own jobs
--   - curator: read all user jobs, cancel own
--   - admin: read/cancel all user jobs, delete own
--   - platform_admin: full access including system jobs

BEGIN;

-- =============================================================================
-- Register Jobs Resource
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES (
    'jobs',
    'Job queue management and monitoring',
    ARRAY['read', 'cancel', 'delete'],
    TRUE,  -- Supports scoping (own vs global vs system)
    'system'
)
ON CONFLICT (resource_type) DO NOTHING;

-- =============================================================================
-- Grant Permissions to Roles
-- =============================================================================

-- read_only: read own jobs only
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('read_only', 'jobs', 'read', 'filter', '{"owner": "self"}', TRUE)
ON CONFLICT DO NOTHING;

-- contributor: read/cancel own jobs
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('contributor', 'jobs', 'read', 'filter', '{"owner": "self"}', TRUE),
    ('contributor', 'jobs', 'cancel', 'filter', '{"owner": "self"}', TRUE)
ON CONFLICT DO NOTHING;

-- curator: read all user jobs, cancel own
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('curator', 'jobs', 'read', 'global', NULL, TRUE),
    ('curator', 'jobs', 'cancel', 'filter', '{"owner": "self"}', TRUE)
ON CONFLICT DO NOTHING;

-- admin: read/cancel all user jobs, delete own
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('admin', 'jobs', 'read', 'global', NULL, TRUE),
    ('admin', 'jobs', 'cancel', 'global', NULL, TRUE),
    ('admin', 'jobs', 'delete', 'filter', '{"owner": "self"}', TRUE)
ON CONFLICT DO NOTHING;

-- platform_admin: full access including system jobs
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    -- Global access to all user jobs
    ('platform_admin', 'jobs', 'read', 'global', NULL, TRUE),
    ('platform_admin', 'jobs', 'cancel', 'global', NULL, TRUE),
    ('platform_admin', 'jobs', 'delete', 'global', NULL, TRUE),
    -- System job access (scheduled jobs, etc.)
    ('platform_admin', 'jobs', 'read', 'filter', '{"is_system": true}', TRUE),
    ('platform_admin', 'jobs', 'cancel', 'filter', '{"is_system": true}', TRUE),
    ('platform_admin', 'jobs', 'delete', 'filter', '{"is_system": true}', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Record Migration (idempotent)
-- =============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (41, 'job_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
