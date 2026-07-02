-- Migration 037: Grant admin role backup create/restore permissions
--
-- Per user request: admin role should have backup capabilities
-- Previously only platform_admin had backups:create and backups:restore
-- This allows admins to perform backup/restore without requiring platform_admin
--
-- Idempotent: Safe to run multiple times

BEGIN;

-- Grant backups:create to admin role
-- Idempotent: only insert if not exists
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'backups', 'create', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin'
      AND resource_type = 'backups'
      AND action = 'create'
      AND scope_type = 'global'
      AND scope_id IS NULL
);

-- Grant backups:restore to admin role
-- Idempotent: only insert if not exists
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'backups', 'restore', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin'
      AND resource_type = 'backups'
      AND action = 'restore'
      AND scope_type = 'global'
      AND scope_id IS NULL
);

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (37, 'admin_backup_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
