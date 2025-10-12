# ADR-028: Dynamic Role-Based Access Control (RBAC) System

**Status:** Proposed
**Date:** 2025-10-11
**Supersedes:** ADR-027 (Authentication API) - extends with dynamic RBAC

## Context

The current authentication system (ADR-027) has hardcoded roles (`read_only`, `contributor`, `curator`, `admin`) with static permissions seeded in `kg_auth.role_permissions`. As the platform evolves to support:

- AI-generated ontologies
- Structured collaboration graphs
- Tool list graphs
- Memory systems (conversational memory, agent memory, persistent context)
- Multi-tenant workspaces
- Custom resource types

We need a **dynamic, extensible RBAC system** that can:
1. Support new resource types without schema changes
2. Allow administrators to create custom roles
3. Enable fine-grained, scoped permissions (e.g., access to specific ontology)
4. Support role hierarchies and permission inheritance
5. Maintain backwards compatibility with existing roles

## Decision

Implement a **three-tier RBAC system** with dynamic resource registration:

### 1. Resource Registry (Dynamic Resource Types)

**New Table: `kg_auth.resources`**
```sql
CREATE TABLE kg_auth.resources (
    resource_type VARCHAR(100) PRIMARY KEY,
    description TEXT,
    parent_type VARCHAR(100) REFERENCES kg_auth.resources(resource_type),
    available_actions VARCHAR(50)[],  -- ['read', 'write', 'delete', 'approve', 'execute']
    supports_scoping BOOLEAN DEFAULT FALSE,  -- Can permissions be scoped to specific instances?
    metadata JSONB,  -- Custom fields per resource type
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(100)
);
```

**Example Resources:**
```
resource_type         | parent_type | available_actions                         | supports_scoping
----------------------|-------------|-------------------------------------------|------------------
concepts              | NULL        | ['read', 'write', 'delete']              | FALSE
vocabulary            | NULL        | ['read', 'write', 'approve', 'delete']   | FALSE
jobs                  | NULL        | ['read', 'write', 'approve', 'delete']   | FALSE
users                 | NULL        | ['read', 'write', 'delete']              | FALSE
ontologies            | NULL        | ['read', 'write', 'delete', 'manage']    | TRUE
ontologies.ai_generated | ontologies | ['read', 'write', 'approve']            | TRUE
collaboration_graphs  | NULL        | ['read', 'write', 'invite', 'moderate']  | TRUE
tool_lists            | NULL        | ['read', 'write', 'execute', 'share']    | TRUE
memory_systems        | NULL        | ['read', 'write', 'delete', 'search', 'export'] | TRUE
workspaces            | NULL        | ['read', 'write', 'admin']               | TRUE
```

### 2. Dynamic Roles

**New Table: `kg_auth.roles`**
```sql
CREATE TABLE kg_auth.roles (
    role_name VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_builtin BOOLEAN DEFAULT FALSE,  -- System roles (cannot be deleted)
    is_active BOOLEAN DEFAULT TRUE,
    parent_role VARCHAR(50) REFERENCES kg_auth.roles(role_name),  -- Role inheritance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id),
    metadata JSONB  -- Custom fields (e.g., color, icon)
);
```

**Builtin Roles:**
- `read_only` - Read access to public resources
- `contributor` - Can create content
- `curator` - Can approve and manage content
- `admin` - Full system access

**Custom Role Examples:**
- `ontology_manager` - Manages AI-generated ontologies
- `collaboration_lead` - Moderates collaboration graphs
- `tool_executor` - Can execute tools from tool lists
- `workspace_owner` - Owns a specific workspace

### 3. Scoped Permissions

**Enhanced Table: `kg_auth.role_permissions`**
```sql
-- Drop existing and recreate with scoping support
DROP TABLE IF EXISTS kg_auth.role_permissions CASCADE;

CREATE TABLE kg_auth.role_permissions (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,
    resource_type VARCHAR(100) NOT NULL REFERENCES kg_auth.resources(resource_type),
    action VARCHAR(50) NOT NULL,

    -- Scoping support (optional - NULL means applies to all instances)
    scope_type VARCHAR(50),  -- 'global', 'ontology', 'workspace', 'user', 'instance'
    scope_id VARCHAR(200),   -- Specific instance ID (e.g., ontology_name, workspace_id)
    scope_filter JSONB,      -- Complex filters (e.g., {"ontology_type": "ai_generated", "status": "active"})

    granted BOOLEAN NOT NULL DEFAULT TRUE,  -- Explicit deny support
    inherited_from VARCHAR(50) REFERENCES kg_auth.roles(role_name),  -- Track inheritance

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES kg_auth.users(id),

    UNIQUE(role_name, resource_type, action, scope_type, scope_id)
);

CREATE INDEX idx_role_perms_role ON kg_auth.role_permissions(role_name);
CREATE INDEX idx_role_perms_resource ON kg_auth.role_permissions(resource_type, action);
CREATE INDEX idx_role_perms_scope ON kg_auth.role_permissions(scope_type, scope_id);
```

**Permission Examples:**
```sql
-- Global: Admin can read all concepts
('admin', 'concepts', 'read', 'global', NULL, NULL, TRUE, NULL)

-- Scoped: User can manage specific ontology
('ontology_manager', 'ontologies', 'manage', 'instance', 'ml_ontology_v2', NULL, TRUE, NULL)

-- Filtered: Curator can approve AI-generated ontologies
('curator', 'ontologies', 'approve', 'filter', NULL, '{"type": "ai_generated"}', TRUE, NULL)

-- Inherited: Custom role inherits from curator
('custom_curator', 'vocabulary', 'approve', 'global', NULL, NULL, TRUE, 'curator')

-- Explicit deny: Prevent deletion of builtin roles
('contributor', 'roles', 'delete', 'filter', NULL, '{"is_builtin": true}', FALSE, NULL)
```

### 4. User Role Assignments (Multiple Roles)

**Enhanced Table: `kg_auth.user_roles`**
```sql
CREATE TABLE kg_auth.user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    role_name VARCHAR(50) NOT NULL REFERENCES kg_auth.roles(role_name) ON DELETE CASCADE,

    -- Optional: Role assignment can be scoped to workspace/ontology
    scope_type VARCHAR(50),
    scope_id VARCHAR(200),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by INTEGER REFERENCES kg_auth.users(id),
    expires_at TIMESTAMPTZ,  -- Optional: time-limited roles

    UNIQUE(user_id, role_name, scope_type, scope_id)
);

CREATE INDEX idx_user_roles_user ON kg_auth.user_roles(user_id);
CREATE INDEX idx_user_roles_role ON kg_auth.user_roles(role_name);
CREATE INDEX idx_user_roles_scope ON kg_auth.user_roles(scope_type, scope_id);
```

**Update users table:**
```sql
-- Keep primary_role for backwards compatibility and default permissions
ALTER TABLE kg_auth.users
    RENAME COLUMN role TO primary_role;

-- Remove CHECK constraint (roles are now dynamic)
ALTER TABLE kg_auth.users
    DROP CONSTRAINT IF EXISTS users_role_check;
```

### 5. Permission Checking Logic

**Python Permission Checker:**
```python
class PermissionChecker:
    def can_user(self, user_id: int, action: str, resource_type: str,
                 resource_id: Optional[str] = None) -> bool:
        """
        Check if user has permission to perform action on resource.

        Checks in order:
        1. Instance-scoped permissions (most specific)
        2. Filter-scoped permissions
        3. Global permissions
        4. Inherited permissions from parent roles
        5. Deny permissions (explicit denies override grants)
        """

        # Get all user roles (including primary_role and assigned roles)
        roles = self.get_user_roles(user_id, resource_id)

        # Check for explicit deny first
        if self.has_explicit_deny(roles, resource_type, action, resource_id):
            return False

        # Check permissions in order of specificity
        for role in roles:
            # 1. Instance-scoped
            if resource_id and self.has_instance_permission(role, resource_type, action, resource_id):
                return True

            # 2. Filter-scoped
            if self.has_filter_permission(role, resource_type, action, resource_id):
                return True

            # 3. Global
            if self.has_global_permission(role, resource_type, action):
                return True

            # 4. Check parent roles (inheritance)
            if self.check_inherited_permissions(role, resource_type, action, resource_id):
                return True

        return False
```

**FastAPI Dependency:**
```python
def require_permission(resource_type: str, action: str, resource_id: Optional[str] = None):
    """
    Dependency that checks if current user has required permission.

    Usage:
        @app.get("/ontologies/{ontology_id}")
        async def get_ontology(
            ontology_id: str,
            _: Annotated[UserInDB, Depends(require_permission("ontologies", "read", ontology_id))]
        ):
            ...
    """
    def dependency(current_user: Annotated[UserInDB, Depends(get_current_active_user)]):
        checker = PermissionChecker()
        if not checker.can_user(current_user.id, action, resource_type, resource_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {action} on {resource_type}"
            )
        return current_user
    return dependency
```

### 6. API Endpoints

**Resource Management:**
```
GET    /resources                    # List registered resource types
GET    /resources/{resource_type}    # Get resource details
POST   /resources                    # Register new resource type (admin only)
PUT    /resources/{resource_type}    # Update resource definition
DELETE /resources/{resource_type}    # Unregister resource (if no permissions)
```

**Role Management:**
```
GET    /roles                        # List all roles
GET    /roles/{role_name}            # Get role details with permissions
POST   /roles                        # Create new role
PUT    /roles/{role_name}            # Update role
DELETE /roles/{role_name}            # Delete role (if not builtin, no users)
GET    /roles/{role_name}/users      # List users with this role
```

**Permission Management:**
```
GET    /roles/{role_name}/permissions              # List role permissions
POST   /roles/{role_name}/permissions              # Grant permission
DELETE /roles/{role_name}/permissions/{perm_id}    # Revoke permission
PUT    /roles/{role_name}/permissions              # Bulk update permissions
```

**User Role Assignment:**
```
GET    /users/{user_id}/roles        # List user's roles
POST   /users/{user_id}/roles        # Assign role to user
DELETE /users/{user_id}/roles/{role_name}  # Remove role from user
```

### 7. CLI Commands

```bash
# Resource management
kg admin resource list
kg admin resource get <resource_type>
kg admin resource create <type> --actions read,write,delete --scoped

# Role management
kg admin role list
kg admin role get <role>
kg admin role create <name> --description "..." --inherits <parent_role>
kg admin role delete <role>
kg admin role copy <source> <new_name>

# Permission management
kg admin role permissions <role>                    # List all permissions
kg admin role grant <role> <resource> <action>      # Grant permission
kg admin role revoke <role> <resource> <action>     # Revoke permission
kg admin role grant <role> <resource> <action> --scope instance --id <resource_id>

# User role assignment
kg admin user roles <user_id>                       # List user's roles
kg admin user assign <user_id> <role>               # Assign role
kg admin user unassign <user_id> <role>             # Remove role
kg admin user assign <user_id> <role> --scope workspace --id <workspace_id>
```

## Migration Strategy

### Phase 1: Schema Migration (Backwards Compatible)

1. Create new tables: `resources`, `roles`, `user_roles`
2. Migrate existing data:
   ```sql
   -- Create builtin roles
   INSERT INTO kg_auth.roles (role_name, display_name, is_builtin)
   VALUES
       ('read_only', 'Read Only', TRUE),
       ('contributor', 'Contributor', TRUE),
       ('curator', 'Curator', TRUE),
       ('admin', 'Administrator', TRUE);

   -- Register existing resources
   INSERT INTO kg_auth.resources (resource_type, available_actions)
   VALUES
       ('concepts', ARRAY['read', 'write', 'delete']),
       ('vocabulary', ARRAY['read', 'write', 'approve', 'delete']),
       ('jobs', ARRAY['read', 'write', 'approve', 'delete']),
       ('users', ARRAY['read', 'write', 'delete']);

   -- Migrate existing permissions to new schema
   INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
   SELECT role, resource, action, 'global', granted
   FROM kg_auth.role_permissions_old;

   -- Assign primary roles to all users
   INSERT INTO kg_auth.user_roles (user_id, role_name)
   SELECT id, primary_role FROM kg_auth.users;
   ```

3. Update permission checking to use new system
4. Keep `users.primary_role` for backwards compatibility

### Phase 2: Add New Resource Types

As new features are added, register them:
```python
# In ontology feature implementation
register_resource(
    resource_type="ontologies",
    description="AI-generated ontology management",
    available_actions=["read", "write", "delete", "manage", "approve"],
    supports_scoping=True
)

# Grant permissions to existing roles
grant_permission("curator", "ontologies", "approve", scope_type="filter",
                 scope_filter={"type": "ai_generated"})
```

### Phase 3: Custom Roles

Allow administrators to create custom roles for specific use cases:
```bash
# Create workspace admin role
kg admin role create workspace_admin \
    --description "Workspace administrator" \
    --inherits curator

# Grant workspace-specific permissions
kg admin role grant workspace_admin workspaces admin --scope instance --id engineering_team
```

## Benefits

1. **Extensibility**: New resource types can be added without schema changes
2. **Flexibility**: Fine-grained, scoped permissions (workspace-level, ontology-level, etc.)
3. **Hierarchy**: Role inheritance reduces permission duplication
4. **Multi-tenancy Ready**: Scoped permissions enable workspace/tenant isolation
5. **Audit Trail**: Track who granted what permission and when
6. **Explicit Deny**: Support for explicit permission denials
7. **Time-Limited Access**: Roles can expire (temporary access)
8. **Backwards Compatible**: Existing hardcoded roles continue to work

## Examples

### Use Case 1: AI-Generated Ontology Manager

```bash
# Register ontology resource
kg admin resource create ontologies \
    --actions read,write,delete,manage,approve \
    --scoped

# Create specialized role
kg admin role create ontology_curator \
    --description "Curates AI-generated ontologies" \
    --inherits curator

# Grant scoped permissions
kg admin role grant ontology_curator ontologies approve \
    --scope filter --filter '{"type": "ai_generated"}'

# Assign to user
kg admin user assign alice ontology_curator
```

### Use Case 2: Collaboration Graph Moderator

```bash
# Register collaboration resource
kg admin resource create collaboration_graphs \
    --actions read,write,invite,moderate,delete \
    --scoped

# Create moderator role
kg admin role create collab_moderator \
    --description "Moderates collaboration spaces"

# Grant permissions
kg admin role grant collab_moderator collaboration_graphs moderate --scope global
kg admin role grant collab_moderator collaboration_graphs read --scope global

# Assign to specific collaboration space
kg admin user assign bob collab_moderator \
    --scope instance --id research_team_collab
```

### Use Case 3: Tool Executor (Limited Permissions)

```bash
# Register tool list resource
kg admin resource create tool_lists \
    --actions read,execute \
    --scoped

# Create executor role (can run but not modify)
kg admin role create tool_executor \
    --description "Can execute approved tools"

kg admin role grant tool_executor tool_lists read --scope global
kg admin role grant tool_executor tool_lists execute \
    --scope filter --filter '{"approved": true}'

kg admin user assign charlie tool_executor
```

### Use Case 4: Memory System (Conversational Context)

```bash
# Register memory system resource
kg admin resource create memory_systems \
    --actions read,write,delete,search,export \
    --scoped

# Create memory manager role
kg admin role create memory_manager \
    --description "Manages agent memory and persistent context"

# Users can read/write their own memories
kg admin role grant contributor memory_systems read \
    --scope filter --filter '{"owner_id": "$user_id"}'
kg admin role grant contributor memory_systems write \
    --scope filter --filter '{"owner_id": "$user_id"}'

# Memory managers can search across all memories (for support/debugging)
kg admin role grant memory_manager memory_systems search --scope global

# Admin can export memories (backup/compliance)
kg admin role grant admin memory_systems export --scope global

# Assign scoped memory access
kg admin user assign diana memory_manager \
    --scope instance --id agent_workspace_123
```

## Cold Start Initialization

The migration script includes automatic initialization with **minimum viable permissions** for a fresh installation:

**Builtin Roles Created:**
- `read_only` - Can view concepts, vocabulary, jobs
- `contributor` - + Can create/edit concepts and jobs
- `curator` - + Can approve vocabulary and jobs
- `admin` - Full system access including user/role management

**Resources Registered:**
- `concepts`, `vocabulary`, `jobs`, `users`, `roles`, `resources`

**Permissions Seeded:**
- All existing permissions from ADR-027 migrated automatically
- Admin given full access to role/resource management
- Curator given read access to roles/resources (visibility, no modification)

**User Migration:**
- All existing users automatically get their `primary_role` as a `user_roles` assignment
- Backwards compatible: `users.primary_role` column preserved

The system is **immediately functional** after migration - no manual setup required!

## Security Considerations

1. **Explicit Denies**: Denies override grants (prevent privilege escalation)
2. **Builtin Roles**: Cannot be deleted (system stability)
3. **Permission Inheritance**: Clearly tracked (audit trail)
4. **Scope Validation**: Validate scope_id exists before granting permission
5. **Rate Limiting**: Limit permission check queries (cache frequently checked permissions)
6. **Audit Logging**: Log all permission grants/revokes in `kg_logs.audit_trail`

## Performance Optimizations

1. **Permission Cache**: Cache user permissions in Redis (TTL: 5 minutes)
2. **Materialized Views**: Pre-compute effective permissions per user
3. **Index Strategy**: Index on (user_id, resource_type, action) for fast lookups
4. **Lazy Loading**: Only resolve parent role permissions when needed
5. **Batch Checking**: Check multiple permissions in single query

## Future Extensions

1. **Attribute-Based Access Control (ABAC)**:
   - Permissions based on user attributes (department, location, etc.)
   - Dynamic policies: "Allow if user.department == resource.owner_department"

2. **Temporary Elevated Access**:
   - "Break glass" emergency access with automatic audit and expiration

3. **Permission Request Workflow**:
   - Users can request permissions → approval flow → automatic grant

4. **Role Recommendations**:
   - AI suggests roles based on user activity patterns

## References

- NIST RBAC Standard: https://csrc.nist.gov/projects/role-based-access-control
- AWS IAM Best Practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- OAuth 2.0 Scopes: https://oauth.net/2/scope/

## Implementation Checklist

- [ ] Create schema migration SQL
- [ ] Implement Python permission checker
- [ ] Create FastAPI endpoints (resources, roles, permissions)
- [ ] Update existing endpoints to use new permission system
- [ ] Create TypeScript client models
- [ ] Implement CLI commands
- [ ] Write migration script for existing data
- [ ] Add caching layer (Redis)
- [ ] Document permission model
- [ ] Write integration tests
