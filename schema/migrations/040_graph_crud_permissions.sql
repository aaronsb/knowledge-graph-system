-- Migration 040: Graph CRUD Permissions (ADR-089)
--
-- Add graph resource permissions for deterministic graph editing.
-- Uses existing RBAC pattern instead of separate OAuth scopes.
--
-- Idempotent: Safe to run multiple times

BEGIN;

-- Admin role: full graph CRUD access
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'graph', 'read', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'graph' AND action = 'read'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'graph', 'create', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'graph' AND action = 'create'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'graph', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'graph' AND action = 'write'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'graph', 'delete', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'graph' AND action = 'delete'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'graph', 'import', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'graph' AND action = 'import'
);

-- Platform admin role: full graph CRUD access
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'graph', 'read', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'graph' AND action = 'read'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'graph', 'create', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'graph' AND action = 'create'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'graph', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'graph' AND action = 'write'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'graph', 'delete', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'graph' AND action = 'delete'
);

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'graph', 'import', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'graph' AND action = 'import'
);

-- Contributor role: can create graph content (but not delete)
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'contributor', 'graph', 'create', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'contributor' AND resource_type = 'graph' AND action = 'create'
);

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (40, 'graph_crud_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
