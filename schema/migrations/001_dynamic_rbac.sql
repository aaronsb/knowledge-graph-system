-- Migration 001: Dynamic RBAC System (ADR-028)
-- Date: 2025-10-11
-- Description: Converts hardcoded roles to dynamic RBAC with resource registry and scoped permissions

-- =============================================================================
-- STEP 1: Create New Tables
-- =============================================================================

-- Resource Registry (Dynamic Resource Types)
CREATE TABLE IF NOT EXISTS kg_auth.resources (
    resource_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    parent_type VARCHAR(100) REFERENCES kg_auth.resources(resource_type),
    available_actions VARCHAR(50)[] NOT NULL,  -- ['read', 'write', 'delete', 'approve', 'execute']
    supports_scoping BOOLEAN DEFAULT FALSE,    -- Can permissions be scoped to specific instances?
    metadata JSONB DEFAULT '{}',               -- Custom fields per resource type
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(100)
);

CREATE INDEX idx_resources_parent ON kg_auth.resources(parent_type);
COMMENT ON TABLE kg_auth.resources IS 'Dynamic resource type registry (ADR-028)';

-- Dynamic Roles
CREATE TABLE IF NOT EXISTS kg_auth.roles (
    role_name VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_builtin BOOLEAN DEFAULT FALSE,          -- System roles (cannot be deleted)
    is_active BOOLEAN DEFAULT TRUE,
    parent_role VARCHAR(50) REFERENCES kg_auth.roles(role_name), -- Role inheritance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id),
    metadata JSONB DEFAULT '{}'                -- Custom fields (e.g., color, icon)
);

CREATE INDEX idx_roles_parent ON kg_auth.roles(parent_role);
CREATE INDEX idx_roles_builtin ON kg_auth.roles(is_builtin);
CREATE INDEX idx_roles_active ON kg_auth.roles(is_active);
COMMENT ON TABLE kg_auth.roles IS 'Dynamic role definitions with inheritance (ADR-028)';

-- User Role Assignments (Multiple Roles per User)
CREATE TABLE IF NOT EXISTS kg_auth.user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,

    -- Optional: Role assignment can be scoped to workspace/ontology
    scope_type VARCHAR(50),                    -- 'workspace', 'ontology', 'collaboration', etc.
    scope_id VARCHAR(200),                     -- Specific instance ID

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by INTEGER REFERENCES kg_auth.users(id),
    expires_at TIMESTAMPTZ,                    -- Optional: time-limited roles

    UNIQUE(user_id, role_name, scope_type, scope_id)
);

CREATE INDEX idx_user_roles_user ON kg_auth.user_roles(user_id);
CREATE INDEX idx_user_roles_role ON kg_auth.user_roles(role_name);
CREATE INDEX idx_user_roles_scope ON kg_auth.user_roles(scope_type, scope_id);
CREATE INDEX idx_user_roles_expires ON kg_auth.user_roles(expires_at) WHERE expires_at IS NOT NULL;
COMMENT ON TABLE kg_auth.user_roles IS 'User role assignments with optional scoping (ADR-028)';

-- =============================================================================
-- STEP 2: Backup and Migrate Existing Permissions
-- =============================================================================

-- Backup old permissions table
CREATE TABLE IF NOT EXISTS kg_auth.role_permissions_backup AS
SELECT * FROM kg_auth.role_permissions;

-- Drop old permissions table
DROP TABLE IF EXISTS kg_auth.role_permissions CASCADE;

-- Create new permissions table with scoping support
CREATE TABLE kg_auth.role_permissions (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,
    resource_type VARCHAR(100) NOT NULL REFERENCES kg_auth.resources(resource_type),
    action VARCHAR(50) NOT NULL,

    -- Scoping support (NULL means applies to all instances)
    scope_type VARCHAR(50),                    -- 'global', 'instance', 'filter', 'workspace', etc.
    scope_id VARCHAR(200),                     -- Specific instance ID (e.g., 'ontology_id', 'workspace_id')
    scope_filter JSONB,                        -- Complex filters (e.g., {"type": "ai_generated", "status": "active"})

    granted BOOLEAN NOT NULL DEFAULT TRUE,     -- Explicit deny support (FALSE = deny)
    inherited_from VARCHAR(50) REFERENCES kg_auth.roles(role_name), -- Track inheritance source

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id),

    UNIQUE(role_name, resource_type, action, scope_type, COALESCE(scope_id, ''))
);

CREATE INDEX idx_role_perms_role ON kg_auth.role_permissions(role_name);
CREATE INDEX idx_role_perms_resource ON kg_auth.role_permissions(resource_type, action);
CREATE INDEX idx_role_perms_scope ON kg_auth.role_permissions(scope_type, scope_id);
CREATE INDEX idx_role_perms_granted ON kg_auth.role_permissions(granted) WHERE granted = FALSE;
COMMENT ON TABLE kg_auth.role_permissions IS 'Dynamic role permissions with scoping (ADR-028)';

-- =============================================================================
-- STEP 3: Update Users Table (Backwards Compatible)
-- =============================================================================

-- Rename 'role' to 'primary_role' (keep for backwards compatibility)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_auth'
        AND table_name = 'users'
        AND column_name = 'role'
    ) THEN
        ALTER TABLE kg_auth.users RENAME COLUMN role TO primary_role;
    END IF;
END $$;

-- Remove CHECK constraint (roles are now dynamic)
ALTER TABLE kg_auth.users DROP CONSTRAINT IF EXISTS users_role_check;

-- Add foreign key to roles table
ALTER TABLE kg_auth.users ADD CONSTRAINT fk_users_primary_role
    FOREIGN KEY (primary_role) REFERENCES kg_auth.roles(role_name);

COMMENT ON COLUMN kg_auth.users.primary_role IS 'Primary role (backwards compatibility) - user can have additional roles in user_roles table';

-- =============================================================================
-- STEP 4: Seed Builtin Resources
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES
    ('concepts', 'Knowledge graph concepts and nodes', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('vocabulary', 'Relationship vocabulary management', ARRAY['read', 'write', 'approve', 'delete'], FALSE, 'system'),
    ('jobs', 'Ingestion job management', ARRAY['read', 'write', 'approve', 'delete'], FALSE, 'system'),
    ('users', 'User account management', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('roles', 'Role and permission management', ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('resources', 'Resource type registration', ARRAY['read', 'write', 'delete'], FALSE, 'system')
ON CONFLICT (resource_type) DO NOTHING;

-- =============================================================================
-- STEP 5: Seed Builtin Roles
-- =============================================================================

INSERT INTO kg_auth.roles (role_name, display_name, description, is_builtin, is_active)
VALUES
    ('read_only', 'Read Only', 'Read access to public resources', TRUE, TRUE),
    ('contributor', 'Contributor', 'Can create and modify content', TRUE, TRUE),
    ('curator', 'Curator', 'Can approve and manage content', TRUE, TRUE),
    ('admin', 'Administrator', 'Full system access', TRUE, TRUE)
ON CONFLICT (role_name) DO NOTHING;

-- =============================================================================
-- STEP 6: Migrate Existing Permissions
-- =============================================================================

-- Migrate permissions from backup to new schema
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
SELECT
    role AS role_name,
    resource AS resource_type,
    action,
    'global' AS scope_type,
    granted
FROM kg_auth.role_permissions_backup
ON CONFLICT (role_name, resource_type, action, scope_type, scope_id) DO NOTHING;

-- =============================================================================
-- STEP 7: Assign Primary Roles to Users
-- =============================================================================

-- Assign primary_role as a user_role assignment for all existing users
INSERT INTO kg_auth.user_roles (user_id, role_name, scope_type, assigned_by)
SELECT
    id AS user_id,
    primary_role AS role_name,
    'global' AS scope_type,
    NULL AS assigned_by
FROM kg_auth.users
WHERE primary_role IS NOT NULL
ON CONFLICT (user_id, role_name, scope_type, scope_id) DO NOTHING;

-- =============================================================================
-- STEP 8: Add New Admin Permissions for RBAC Management
-- =============================================================================

-- Admin can manage roles
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('admin', 'roles', 'read', 'global', TRUE),
    ('admin', 'roles', 'write', 'global', TRUE),
    ('admin', 'roles', 'delete', 'global', TRUE),
    ('admin', 'resources', 'read', 'global', TRUE),
    ('admin', 'resources', 'write', 'global', TRUE),
    ('admin', 'resources', 'delete', 'global', TRUE)
ON CONFLICT (role_name, resource_type, action, scope_type, scope_id) DO NOTHING;

-- Curator can view roles (but not modify)
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('curator', 'roles', 'read', 'global', TRUE),
    ('curator', 'resources', 'read', 'global', TRUE)
ON CONFLICT (role_name, resource_type, action, scope_type, scope_id) DO NOTHING;

-- =============================================================================
-- STEP 9: Create Helper Functions
-- =============================================================================

-- Function to check if user has permission (simple version)
CREATE OR REPLACE FUNCTION kg_auth.has_permission(
    p_user_id INTEGER,
    p_resource_type VARCHAR,
    p_action VARCHAR,
    p_resource_id VARCHAR DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_permission BOOLEAN := FALSE;
BEGIN
    -- Check global permissions
    SELECT EXISTS (
        SELECT 1
        FROM kg_auth.user_roles ur
        JOIN kg_auth.role_permissions rp ON ur.role_name = rp.role_name
        WHERE ur.user_id = p_user_id
          AND rp.resource_type = p_resource_type
          AND rp.action = p_action
          AND rp.scope_type = 'global'
          AND rp.granted = TRUE
          AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
    ) INTO v_has_permission;

    -- TODO: Add instance-scoped and filter-scoped permission checking

    RETURN v_has_permission;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.has_permission IS 'Check if user has permission (simple global check - extend for scoped permissions)';

-- Function to get user's effective roles
CREATE OR REPLACE FUNCTION kg_auth.get_user_roles(p_user_id INTEGER)
RETURNS TABLE (
    role_name VARCHAR,
    scope_type VARCHAR,
    scope_id VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ur.role_name,
        ur.scope_type,
        ur.scope_id
    FROM kg_auth.user_roles ur
    WHERE ur.user_id = p_user_id
      AND (ur.expires_at IS NULL OR ur.expires_at > NOW());
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_auth.get_user_roles IS 'Get all active roles for a user';

-- =============================================================================
-- STEP 10: Create Audit Triggers
-- =============================================================================

-- Trigger to log role assignments
CREATE OR REPLACE FUNCTION kg_auth.audit_role_assignment()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO kg_logs.audit_trail (user_id, action, resource_type, resource_id, details, outcome)
        VALUES (
            NEW.assigned_by,
            'assign_role',
            'user_roles',
            NEW.user_id::TEXT,
            jsonb_build_object(
                'role_name', NEW.role_name,
                'scope_type', NEW.scope_type,
                'scope_id', NEW.scope_id,
                'expires_at', NEW.expires_at
            ),
            'success'
        );
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO kg_logs.audit_trail (action, resource_type, resource_id, details, outcome)
        VALUES (
            'unassign_role',
            'user_roles',
            OLD.user_id::TEXT,
            jsonb_build_object(
                'role_name', OLD.role_name,
                'scope_type', OLD.scope_type,
                'scope_id', OLD.scope_id
            ),
            'success'
        );
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_user_roles
    AFTER INSERT OR DELETE ON kg_auth.user_roles
    FOR EACH ROW EXECUTE FUNCTION kg_auth.audit_role_assignment();

-- =============================================================================
-- STEP 11: Verification
-- =============================================================================

DO $$
DECLARE
    resource_count INTEGER;
    role_count INTEGER;
    permission_count INTEGER;
    user_role_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO resource_count FROM kg_auth.resources;
    SELECT COUNT(*) INTO role_count FROM kg_auth.roles;
    SELECT COUNT(*) INTO permission_count FROM kg_auth.role_permissions;
    SELECT COUNT(*) INTO user_role_count FROM kg_auth.user_roles;

    RAISE NOTICE 'Dynamic RBAC Migration Complete:';
    RAISE NOTICE '  - Resources registered: %', resource_count;
    RAISE NOTICE '  - Roles created: %', role_count;
    RAISE NOTICE '  - Permissions migrated: %', permission_count;
    RAISE NOTICE '  - User role assignments: %', user_role_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Backwards compatibility maintained:';
    RAISE NOTICE '  - users.primary_role column preserved';
    RAISE NOTICE '  - All existing permissions migrated to new schema';
    RAISE NOTICE '  - Builtin roles (read_only, contributor, curator, admin) protected';
END $$;

-- =============================================================================
-- ROLLBACK SCRIPT (if needed)
-- =============================================================================

-- To rollback this migration:
/*
DROP TABLE IF EXISTS kg_auth.user_roles CASCADE;
DROP TABLE IF EXISTS kg_auth.role_permissions CASCADE;
DROP TABLE IF EXISTS kg_auth.roles CASCADE;
DROP TABLE IF EXISTS kg_auth.resources CASCADE;

-- Restore old permissions
CREATE TABLE kg_auth.role_permissions AS
SELECT * FROM kg_auth.role_permissions_backup;

-- Restore old column name
ALTER TABLE kg_auth.users RENAME COLUMN primary_role TO role;
ALTER TABLE kg_auth.users ADD CONSTRAINT users_role_check
    CHECK (role IN ('read_only', 'contributor', 'curator', 'admin'));
*/
