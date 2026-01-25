-- Migration 038: Upgrade admin user to platform_admin
--
-- The admin user was previously created with primary_role='admin', but
-- platform_admin is the role with full platform permissions (ADR-074).
--
-- This migration upgrades any existing admin user to platform_admin.
-- New installs now create admin with platform_admin directly.
--
-- Idempotent: Safe to run multiple times.

BEGIN;

-- Upgrade admin user to platform_admin role
UPDATE kg_auth.users
SET primary_role = 'platform_admin'
WHERE username = 'admin'
  AND primary_role = 'admin';

-- Record migration (idempotent)
INSERT INTO public.schema_migrations (version, name)
VALUES (38, 'admin_to_platform_admin')
ON CONFLICT (version) DO NOTHING;

COMMIT;
