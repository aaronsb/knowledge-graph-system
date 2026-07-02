-- Migration 042: Storage Admin RBAC Permissions
--
-- Registers 'storage' as an RBAC resource with read-only permissions
-- for the storage diagnostics API (/admin/storage/*).
--
-- Idempotent: Safe to run multiple times (uses ON CONFLICT DO NOTHING)
--
-- Permission Model:
--   - admin: read storage diagnostics
--   - platform_admin: read storage diagnostics

BEGIN;

-- =============================================================================
-- Register Storage Resource
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES (
    'storage',
    'Object storage diagnostics and inspection (S3-compatible backend)',
    ARRAY['read'],
    FALSE,  -- No scoping needed — read-only admin surface
    'system'
)
ON CONFLICT (resource_type) DO NOTHING;

-- =============================================================================
-- Grant Permissions to Roles
-- =============================================================================

-- admin: read storage diagnostics
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('admin', 'storage', 'read', 'global', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- platform_admin: read storage diagnostics
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, scope_filter, granted)
VALUES
    ('platform_admin', 'storage', 'read', 'global', NULL, TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Record Migration (idempotent)
-- =============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (42, 'storage_admin_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
