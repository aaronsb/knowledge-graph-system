-- Migration: 080_search_config_permission
-- Description: RBAC grants for reading/writing search config (ADR-508)
-- Date: 2026-07-01
--
-- The admin API endpoints that read and set the configurable default similarity
-- threshold (ADR-508) gate on ('search_config', 'read'|'write'). Grant those to the
-- admin and platform_admin roles, matching the per-config-resource permission
-- convention used by extraction_config / embedding_config / vocabulary_config.

BEGIN;

-- Register the resource (role_permissions.resource_type FKs to kg_auth.resources).
INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES ('search_config', 'Configurable semantic search settings (default similarity threshold, ADR-508)',
        ARRAY['read', 'write'], FALSE, 'system')
ON CONFLICT (resource_type) DO NOTHING;

DO $$
BEGIN
    -- search_config:read + search_config:write for admin and platform_admin
    INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
    SELECT r.role_name, 'search_config', a.action, 'global', TRUE
    FROM (VALUES ('admin'), ('platform_admin')) AS r(role_name)
    CROSS JOIN (VALUES ('read'), ('write')) AS a(action)
    WHERE NOT EXISTS (
        SELECT 1 FROM kg_auth.role_permissions rp
        WHERE rp.role_name = r.role_name
          AND rp.resource_type = 'search_config'
          AND rp.action = a.action
    );

    RAISE NOTICE 'Migration 080: granted search_config read/write to admin and platform_admin';
END $$;

INSERT INTO public.schema_migrations (version, name)
VALUES (80, 'search_config_permission')
ON CONFLICT (version) DO NOTHING;

COMMIT;
