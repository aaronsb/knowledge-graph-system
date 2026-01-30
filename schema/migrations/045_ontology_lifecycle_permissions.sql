-- Migration 045: Ontology Lifecycle Permissions (ADR-200 Phase 2)
--
-- Add 'write' action to ontologies resource for lifecycle state changes.
-- Grants ontologies:write to curator, admin, platform_admin.
--
-- Idempotent: Safe to run multiple times

BEGIN;

-- Curator role: can change ontology lifecycle state
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'curator', 'ontologies', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'curator' AND resource_type = 'ontologies' AND action = 'write'
);

-- Admin role: can change ontology lifecycle state
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'admin', 'ontologies', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'admin' AND resource_type = 'ontologies' AND action = 'write'
);

-- Platform admin role: can change ontology lifecycle state
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT 'platform_admin', 'ontologies', 'write', 'global', TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM kg_auth.role_permissions
    WHERE role_name = 'platform_admin' AND resource_type = 'ontologies' AND action = 'write'
);

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (45, 'ontology_lifecycle_permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
