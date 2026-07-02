-- Migration 030: Add 'create' action to users resource type
-- Supports POST /users endpoint for admin user creation (ADR-074 enhancement)
--
-- Idempotent: Safe to run multiple times

BEGIN;

-- Update users resource to include 'create' action (idempotent - just sets the value)
UPDATE kg_auth.resources
SET available_actions = ARRAY['read', 'write', 'delete', 'create']
WHERE resource_type = 'users';

-- Grant users:create to admin role (inherits to platform_admin)
-- Idempotent: only insert if not exists
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'users', 'create', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin'
      AND resource_type = 'users'
      AND action = 'create'
      AND scope_type = 'global'
      AND scope_id IS NULL
);

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (30, 'users_create_permission')
ON CONFLICT (version) DO NOTHING;

COMMIT;
