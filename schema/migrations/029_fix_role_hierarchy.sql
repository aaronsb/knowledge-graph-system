-- Migration 029: Fix Role Hierarchy (ADR-074)
--
-- Sets up proper role inheritance chain:
--   platform_admin -> admin -> curator -> contributor
--
-- This ensures higher roles inherit permissions from lower roles.
-- Idempotent: Safe to run multiple times.

BEGIN;

-- Set up role inheritance chain
-- admin inherits from curator
UPDATE kg_auth.roles
SET parent_role = 'curator'
WHERE role_name = 'admin'
  AND (parent_role IS NULL OR parent_role != 'curator');

-- curator inherits from contributor
UPDATE kg_auth.roles
SET parent_role = 'contributor'
WHERE role_name = 'curator'
  AND (parent_role IS NULL OR parent_role != 'contributor');

-- platform_admin already inherits from admin (set in migration 028)
-- Verify it's still correct
UPDATE kg_auth.roles
SET parent_role = 'admin'
WHERE role_name = 'platform_admin'
  AND (parent_role IS NULL OR parent_role != 'admin');

COMMIT;
