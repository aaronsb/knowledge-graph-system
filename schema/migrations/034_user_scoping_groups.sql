-- Migration 034: User Scoping and Groups (ADR-082)
--
-- Adds groups-based ownership model with Unix-style ID ranges.
-- - System/reserved IDs: 1-999
-- - Regular users/groups: 1000+
--
-- Creates:
--   kg_auth.groups - Group definitions
--   kg_auth.user_groups - Group membership
--   kg_auth.resource_grants - Instance-level access grants
--
-- Inserts:
--   System user (ID 1) - Owner of system resources
--   public group (ID 1) - All authenticated users
--   admins group (ID 2) - Platform administrators

BEGIN;

-- ============================================================================
-- Groups Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_auth.groups (
    id INTEGER PRIMARY KEY,
    group_name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id)
);

CREATE INDEX IF NOT EXISTS idx_groups_name ON kg_auth.groups(group_name);
CREATE INDEX IF NOT EXISTS idx_groups_system ON kg_auth.groups(is_system);

COMMENT ON TABLE kg_auth.groups IS 'Group definitions for collaborative access control (ADR-082)';
COMMENT ON COLUMN kg_auth.groups.is_system IS 'System groups (public, admins) cannot be deleted';

-- ============================================================================
-- Group Membership Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_auth.user_groups (
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES kg_auth.groups(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by INTEGER REFERENCES kg_auth.users(id),
    PRIMARY KEY (user_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_user_groups_user ON kg_auth.user_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_user_groups_group ON kg_auth.user_groups(group_id);

COMMENT ON TABLE kg_auth.user_groups IS 'Group membership assignments (ADR-082)';

-- ============================================================================
-- Resource Grants Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_auth.resource_grants (
    id SERIAL PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(200) NOT NULL,
    principal_type VARCHAR(20) NOT NULL CHECK (principal_type IN ('user', 'group')),
    principal_id INTEGER NOT NULL,
    permission VARCHAR(20) NOT NULL CHECK (permission IN ('read', 'write', 'admin')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by INTEGER REFERENCES kg_auth.users(id),
    UNIQUE(resource_type, resource_id, principal_type, principal_id, permission)
);

CREATE INDEX IF NOT EXISTS idx_resource_grants_resource
    ON kg_auth.resource_grants(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_grants_principal
    ON kg_auth.resource_grants(principal_type, principal_id);
CREATE INDEX IF NOT EXISTS idx_resource_grants_lookup
    ON kg_auth.resource_grants(resource_type, resource_id, principal_type, principal_id);

COMMENT ON TABLE kg_auth.resource_grants IS 'Instance-level access grants for owned resources (ADR-082)';
COMMENT ON COLUMN kg_auth.resource_grants.resource_type IS 'Type: ontology, artifact, report, etc.';
COMMENT ON COLUMN kg_auth.resource_grants.resource_id IS 'Specific resource identifier';
COMMENT ON COLUMN kg_auth.resource_grants.principal_type IS 'Grant to user or group';
COMMENT ON COLUMN kg_auth.resource_grants.permission IS 'read, write, or admin access';

-- ============================================================================
-- System User (ID 1) - Already Created in Migration 020
-- ============================================================================

-- System user was created in migration 020 (track_authenticated_users_in_jobs)
-- This INSERT is here for idempotency in case migrations run out of order
INSERT INTO kg_auth.users (id, username, password_hash, primary_role, disabled)
VALUES (1, 'system', 'SYSTEM_NO_LOGIN', 'admin', true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- System Groups (IDs 1, 2)
-- ============================================================================

-- public group - all authenticated users are implicit members
INSERT INTO kg_auth.groups (id, group_name, display_name, description, is_system, created_by)
VALUES (1, 'public', 'All Users', 'All authenticated users - implicit membership', true, 1)
ON CONFLICT (id) DO NOTHING;

-- admins group - platform administrators
INSERT INTO kg_auth.groups (id, group_name, display_name, description, is_system, created_by)
VALUES (2, 'admins', 'Administrators', 'Platform administrators with elevated access', true, 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Default Group Memberships
-- ============================================================================

-- Add admin user (id=1000) to admins group
-- Note: admin user is created in migration 020
INSERT INTO kg_auth.user_groups (user_id, group_id, added_by)
SELECT 1000, 2, 1  -- admin user -> admins group, added by system
WHERE EXISTS (SELECT 1 FROM kg_auth.users WHERE id = 1000)
ON CONFLICT (user_id, group_id) DO NOTHING;

-- ============================================================================
-- Sequence Reset for Regular Users/Groups (1000+)
-- ============================================================================

-- Create sequence for groups if not exists
CREATE SEQUENCE IF NOT EXISTS kg_auth.groups_id_seq START WITH 1000;

-- Reset users sequence to start at 1000 (for new users)
-- Only affects new inserts, doesn't change existing IDs
SELECT setval('kg_auth.users_id_seq', GREATEST(1000, (SELECT COALESCE(MAX(id), 0) + 1 FROM kg_auth.users)));

-- Set groups sequence
SELECT setval('kg_auth.groups_id_seq', GREATEST(1000, (SELECT COALESCE(MAX(id), 0) + 1 FROM kg_auth.groups)));

-- Alter groups table to use the sequence for default
ALTER TABLE kg_auth.groups ALTER COLUMN id SET DEFAULT nextval('kg_auth.groups_id_seq');

-- ============================================================================
-- Permission Resolution Function (Extended)
-- ============================================================================

-- Drop existing function to recreate with new signature
DROP FUNCTION IF EXISTS kg_auth.has_access(INTEGER, VARCHAR, VARCHAR, VARCHAR);

CREATE OR REPLACE FUNCTION kg_auth.has_access(
    p_user_id INTEGER,
    p_resource_type VARCHAR,
    p_resource_id VARCHAR,
    p_permission VARCHAR DEFAULT 'read'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_access BOOLEAN := FALSE;
BEGIN
    -- Check 1: Is user the owner? (requires owner_id on resource - checked by caller)
    -- This function doesn't know about ownership, caller should check first

    -- Check 2: Does user have a direct grant?
    SELECT EXISTS (
        SELECT 1 FROM kg_auth.resource_grants
        WHERE resource_type = p_resource_type
          AND resource_id = p_resource_id
          AND principal_type = 'user'
          AND principal_id = p_user_id
          AND permission IN (p_permission, 'admin')  -- admin implies all permissions
    ) INTO v_has_access;

    IF v_has_access THEN
        RETURN TRUE;
    END IF;

    -- Check 3: Is user in a group with a grant?
    SELECT EXISTS (
        SELECT 1 FROM kg_auth.user_groups ug
        JOIN kg_auth.resource_grants rg
            ON rg.principal_type = 'group' AND rg.principal_id = ug.group_id
        WHERE ug.user_id = p_user_id
          AND rg.resource_type = p_resource_type
          AND rg.resource_id = p_resource_id
          AND rg.permission IN (p_permission, 'admin')
    ) INTO v_has_access;

    IF v_has_access THEN
        RETURN TRUE;
    END IF;

    -- Check 4: Is 'public' group granted access? (all authenticated users)
    SELECT EXISTS (
        SELECT 1 FROM kg_auth.resource_grants
        WHERE resource_type = p_resource_type
          AND resource_id = p_resource_id
          AND principal_type = 'group'
          AND principal_id = 1  -- public group ID
          AND permission IN (p_permission, 'admin')
    ) INTO v_has_access;

    RETURN v_has_access;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.has_access IS 'Check if user has access to specific resource via grants (ADR-082)';

-- ============================================================================
-- Helper: Get User Groups (including implicit public)
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_auth.get_user_groups(p_user_id INTEGER)
RETURNS TABLE(group_id INTEGER, group_name VARCHAR) AS $$
BEGIN
    -- Return explicit group memberships
    RETURN QUERY
    SELECT g.id, g.group_name
    FROM kg_auth.groups g
    JOIN kg_auth.user_groups ug ON g.id = ug.group_id
    WHERE ug.user_id = p_user_id

    UNION

    -- Always include public group for all authenticated users
    SELECT 1, 'public'::VARCHAR;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.get_user_groups IS 'Get all groups for user including implicit public membership';

-- ============================================================================
-- Migration Record
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (34, 'user_scoping_groups')
ON CONFLICT (version) DO NOTHING;

COMMIT;
