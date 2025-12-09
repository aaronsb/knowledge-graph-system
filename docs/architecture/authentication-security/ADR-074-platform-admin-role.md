# ADR-074: Platform Admin Role

**Status:** Proposed
**Date:** 2025-12-09
**Extends:** [ADR-028: Dynamic RBAC System](./ADR-028-dynamic-rbac-system.md)

## Context

The current RBAC system (ADR-028) provides four builtin roles:
- `read_only` - Read access to public resources
- `contributor` - Can create and modify content
- `curator` - Can approve and manage content
- `admin` - Full system access

However, "admin" currently covers both routine administrative tasks (user management, job queue management) and critical platform operations (API key management, embedding configuration, backups). These have significantly different risk profiles:

| Operation Type | Examples | Risk Level |
|----------------|----------|------------|
| User Admin | Create/delete users, assign roles | Medium |
| Content Admin | Delete OAuth clients, manage job queue | Medium |
| Platform Admin | API keys, embedding regeneration, restore backups | **Critical** |

Additionally, platform admins have full power over the RBAC system itself. If they misconfigure permissions (including their own), recovery requires operational intervention - re-running the migration script to restore default permissions. This is intentional: there is no "magic bypass" that could be exploited.

## Decision

### Goals

1. **Register missing resource types** - Platform operations need RBAC protection
2. **Provide sensible defaults** - Out-of-box role mappings that work for common use cases
3. **Enable customization** - Platform admins can create custom roles with any permission set
4. **CLI management** - Full role/permission management via `kg` CLI

The RBAC system (ADR-028) is already fully flexible. This ADR adds the missing pieces to make it useful for platform administration.

### Default Admin Tiers (Customizable)

These are **default** role configurations. Platform admins can create additional roles with any combination of permissions:

1. **Regular User** - Manage own resources (OAuth clients, personal settings)
2. **Admin** - Existing role for user/content management
3. **Platform Admin** - New default role for critical operations

**Example customization:** A platform admin could create a `backup_operator` role with only `backups:read` and `backups:create` permissions (but not `restore`), or a `readonly_admin` role that can view but not modify platform settings.

### New Resource Types

Register 6 new resource types with **domain-specific actions** (not generic CRUD):

| Resource | Actions | Description |
|----------|---------|-------------|
| `api_keys` | read, write, delete | Manage AI provider API keys |
| `embedding_config` | read, create, delete, activate, reload, regenerate | Embedding system |
| `extraction_config` | read, write | AI extraction provider settings |
| `oauth_clients` | read, create, delete | OAuth client management (all clients) |
| `ontologies` | read, create, delete | Ontology management (no update - names immutable) |
| `backups` | read, create, restore | Backup/restore (restore ≠ create!) |

**Why domain-specific actions?**

Generic "write" conflates different operations:
- `POST /admin/backup` = **create** a backup
- `POST /admin/restore` = **restore** from backup (very different!)
- `POST /admin/embedding/config/{id}/activate` = **activate** (not create or update)
- `POST /admin/embedding/regenerate` = **regenerate** all embeddings

Each action maps 1:1 to an API operation. Permission check is a direct tuple lookup - no joins:

```python
require_permission("backups", "restore")      # Direct lookup
require_permission("embedding_config", "activate")
```

**Action-to-Endpoint Mapping:**

| Resource | Action | Endpoint | HTTP |
|----------|--------|----------|------|
| `api_keys` | read | `/admin/keys` | GET |
| `api_keys` | write | `/admin/keys/{provider}` | POST |
| `api_keys` | delete | `/admin/keys/{provider}` | DELETE |
| `embedding_config` | read | `/admin/embedding/config` | GET |
| `embedding_config` | create | `/admin/embedding/config` | POST |
| `embedding_config` | delete | `/admin/embedding/config/{id}` | DELETE |
| `embedding_config` | activate | `/admin/embedding/config/{id}/activate` | POST |
| `embedding_config` | reload | `/admin/embedding/config/reload` | POST |
| `embedding_config` | regenerate | `/admin/embedding/regenerate` | POST |
| `extraction_config` | read | `/admin/extraction/config` | GET |
| `extraction_config` | write | `/admin/extraction/config` | POST |
| `oauth_clients` | read | `/auth/oauth/clients` | GET |
| `oauth_clients` | create | `/auth/oauth/clients` | POST |
| `oauth_clients` | delete | `/auth/oauth/clients/{id}` | DELETE |
| `ontologies` | read | `/ontology/` | GET |
| `ontologies` | create | `/ontology/` | POST (via ingest) |
| `ontologies` | delete | `/ontology/{name}` | DELETE |
| `backups` | read | `/admin/backups` | GET |
| `backups` | create | `/admin/backup` | POST |
| `backups` | restore | `/admin/restore` | POST |

### New Role: `platform_admin`

- **Parent Role:** `admin` (inherits all admin permissions)
- **Is Builtin:** TRUE (cannot be deleted)
- **Description:** Full platform access including critical operations

### No Hardcoded Bypass (Security Decision)

The `platform_admin` role has **no special bypass** in the permission checker. All access is validated through the normal RBAC system. This means:

1. **Full auditability** - All platform_admin actions go through permission checks
2. **No hidden privileges** - Permissions work exactly as documented
3. **Self-lockout is possible** - If platform_admin deletes their own permissions, they lose access

**Recovery procedure** if locked out:
```bash
# Re-run the idempotent migration to restore default permissions
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -f /workspace/schema/migrations/NNN_platform_admin_resources.sql

# Or via operator container
docker exec kg-operator python /workspace/operator/admin/apply_migration.py \
  NNN_platform_admin_resources.sql
```

The migration uses `ON CONFLICT DO NOTHING`, so it safely restores any missing permissions without affecting existing ones.

### Default Permission Mapping

These are the **default** permissions seeded by the migration. They can be modified via CLI or API.

#### Admin Role (existing, extended)
```
api_keys:         read
embedding_config: read
extraction_config: read
oauth_clients:    read, create, delete
ontologies:       read, create
backups:          read
```

#### Platform Admin Role (new default)
```
api_keys:         read, write, delete
embedding_config: read, create, delete, activate, reload, regenerate
extraction_config: read, write
oauth_clients:    read, create, delete
ontologies:       read, create, delete
backups:          read, create, restore
```

Note: `platform_admin` inherits from `admin`, so it also has all admin permissions. Explicit permissions are still granted for clarity and to ensure the role works even if inheritance is modified.

### CLI Role Management

The `kg` CLI should support full RBAC management:

```bash
# List roles and resources
kg rbac roles list
kg rbac resources list

# Create custom role
kg rbac roles create backup_operator --description "Can create backups only"

# Grant permissions to role
kg rbac permissions grant backup_operator backups read
kg rbac permissions grant backup_operator backups create
# Note: NOT granting 'restore' - this role can only create, not restore

# List permissions for a role
kg rbac permissions list --role backup_operator

# Assign role to user
kg admin users assign-role alice backup_operator

# Revoke permission
kg rbac permissions revoke backup_operator backups create

# Delete custom role (fails if users assigned)
kg rbac roles delete backup_operator
```

This enables platform admins to create arbitrary role configurations without code changes.

## Implementation Checklist

### Phase 1: Database Migration

- [ ] Create migration file `schema/migrations/NNN_platform_admin_resources.sql`
- [ ] Register new resource types (idempotent with `ON CONFLICT DO NOTHING`)
- [ ] Create `platform_admin` role with parent_role = 'admin'
- [ ] Grant default permissions to `admin` role for new resources
- [ ] Grant default permissions to `platform_admin` role for new resources
- [ ] Test migration is idempotent (can run multiple times safely)
- [ ] Document recovery procedure in operator guide

### API Documentation Standard

All endpoint docstrings should follow this authorization documentation format:

```python
"""
Endpoint description...

**Authorization:** Requires `resource:action` permission

Example...
"""
```

For authenticated-but-not-admin endpoints:
```python
"""
**Authorization:** Authenticated users (any valid token)
"""
```

This replaces the legacy "Requires admin role" text with specific resource:action requirements,
making the API self-documenting for RBAC.

### Phase 2: CLI Role Management

Add RBAC management commands to `kg` CLI:

- [ ] `kg rbac roles list` - List all roles with their properties
- [ ] `kg rbac roles create <name>` - Create custom role
- [ ] `kg rbac roles delete <name>` - Delete custom role (not builtin)
- [ ] `kg rbac resources list` - List all resource types and actions
- [ ] `kg rbac permissions list` - List permissions (filterable by role/resource)
- [ ] `kg rbac permissions grant <role> <resource> <action>` - Grant permission
- [ ] `kg rbac permissions revoke <role> <resource> <action>` - Revoke permission
- [ ] `kg admin users assign-role <user> <role>` - Assign role to user
- [ ] `kg admin users revoke-role <user> <role>` - Revoke role from user

### Phase 3: API Endpoint Protection

Update endpoints to use RBAC permission checks:

- [ ] `/admin/keys/*` - require `api_keys` resource permissions
- [ ] `/admin/embedding/*` - require `embedding_config` resource permissions
- [ ] `/admin/extraction/*` - require `extraction_config` resource permissions
- [ ] `/auth/oauth/clients` (admin view) - require `oauth_clients` resource permissions
- [ ] `/ontology/{name}` DELETE - require `ontologies:delete` permission
- [ ] `/admin/backup` and `/admin/restore` - require `backups` resource permissions

### Phase 4: Web UI Updates

- [ ] Update AdminDashboard to check permissions for each tab/section
- [ ] Hide/disable features based on user's effective permissions
- [ ] Add visual indicator for platform admin users
- [ ] Show appropriate error messages for permission denied

### Phase 5: Documentation

- [ ] Update `docs/reference/api/ADMIN-ENDPOINTS.md` with new access levels
- [ ] Add Platform Admin setup to operator documentation
- [ ] Document CLI role management commands
- [ ] Update CLAUDE.md with platform admin workflow

## Migration SQL

```sql
-- Migration: Platform Admin Resources and Role (ADR-074)
-- Idempotent: Safe to run multiple times
-- Recovery: Re-run this migration to restore default permissions if locked out

BEGIN;

-- =============================================================================
-- Register New Resource Types
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES
    ('api_keys', 'API key management for AI providers',
     ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('embedding_config', 'Embedding model configuration and operations',
     ARRAY['read', 'create', 'delete', 'activate', 'reload', 'regenerate'], FALSE, 'system'),
    ('extraction_config', 'AI extraction provider configuration',
     ARRAY['read', 'write'], FALSE, 'system'),
    ('oauth_clients', 'OAuth client management (all clients)',
     ARRAY['read', 'create', 'delete'], FALSE, 'system'),
    ('ontologies', 'Ontology management including deletion',
     ARRAY['read', 'create', 'delete'], FALSE, 'system'),
    ('backups', 'System backup and restore operations',
     ARRAY['read', 'create', 'restore'], FALSE, 'system')
ON CONFLICT (resource_type) DO NOTHING;

-- =============================================================================
-- Create Platform Admin Role
-- =============================================================================

INSERT INTO kg_auth.roles (role_name, display_name, description, is_builtin, is_active, parent_role)
VALUES (
    'platform_admin',
    'Platform Administrator',
    'Full platform access including critical operations. Recovery requires re-running migration.',
    TRUE,
    TRUE,
    'admin'
)
ON CONFLICT (role_name) DO NOTHING;

-- =============================================================================
-- Grant Permissions to Admin Role (read-only for most platform resources)
-- =============================================================================

-- Admin can view but not modify critical platform settings
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- API Keys: read only
    ('admin', 'api_keys', 'read', 'global', TRUE),
    -- Embedding Config: read only
    ('admin', 'embedding_config', 'read', 'global', TRUE),
    -- Extraction Config: read only
    ('admin', 'extraction_config', 'read', 'global', TRUE),
    -- OAuth Clients: full access (admin manages clients)
    ('admin', 'oauth_clients', 'read', 'global', TRUE),
    ('admin', 'oauth_clients', 'create', 'global', TRUE),
    ('admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Ontologies: read and create, but not delete
    ('admin', 'ontologies', 'read', 'global', TRUE),
    ('admin', 'ontologies', 'create', 'global', TRUE),
    -- Backups: read only
    ('admin', 'backups', 'read', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Full Permissions to Platform Admin Role
-- =============================================================================

-- Platform admin has full access to all platform resources
INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- API Keys: full access
    ('platform_admin', 'api_keys', 'read', 'global', TRUE),
    ('platform_admin', 'api_keys', 'write', 'global', TRUE),
    ('platform_admin', 'api_keys', 'delete', 'global', TRUE),
    -- Embedding Config: full access
    ('platform_admin', 'embedding_config', 'read', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'create', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'delete', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'activate', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'reload', 'global', TRUE),
    ('platform_admin', 'embedding_config', 'regenerate', 'global', TRUE),
    -- Extraction Config: full access
    ('platform_admin', 'extraction_config', 'read', 'global', TRUE),
    ('platform_admin', 'extraction_config', 'write', 'global', TRUE),
    -- OAuth Clients: full access
    ('platform_admin', 'oauth_clients', 'read', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'create', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Ontologies: full access including delete
    ('platform_admin', 'ontologies', 'read', 'global', TRUE),
    ('platform_admin', 'ontologies', 'create', 'global', TRUE),
    ('platform_admin', 'ontologies', 'delete', 'global', TRUE),
    -- Backups: full access including restore
    ('platform_admin', 'backups', 'read', 'global', TRUE),
    ('platform_admin', 'backups', 'create', 'global', TRUE),
    ('platform_admin', 'backups', 'restore', 'global', TRUE)
ON CONFLICT DO NOTHING;

COMMIT;
```

## Consequences

### Positive
- **Fully customizable** - default roles are starting points, not constraints
- **CLI management** - platform admins can create/modify roles without code changes
- **Full auditability** - no hidden bypasses, all access through RBAC
- **No security backdoors** - platform_admin follows same rules as everyone
- Extensible: new platform resources can be added to migration
- Backwards compatible: existing `admin` users retain their access level
- Recovery is explicit and auditable (requires operational access to run migration)

### Negative
- More concepts to understand (resources, roles, permissions, scopes)
- Migration adds ~35 new permission rows as defaults
- **Self-lockout is possible** - users can delete their own permissions
- Recovery requires container/database access (not self-service)

### Neutral
- Existing admin users need manual upgrade to platform_admin for critical access
- Web UI needs updates to reflect permission-based visibility
- Operators must document and practice recovery procedure
- Default roles serve as templates, not enforced structures

## Alternatives Considered

### 1. Add Actions to Existing Resources
Instead of new resources, add actions like `manage_api_keys` to existing `users` resource.

**Rejected:** Conflates unrelated concerns and makes permission auditing harder.

### 2. Single Super-Admin Flag
Add `is_super_admin` boolean to users table.

**Rejected:** Doesn't integrate with RBAC system, harder to audit and manage.

### 3. Hardcoded Bypass for platform_admin
Add code in PermissionChecker that always returns `True` for platform_admin role.

**Rejected:** Creates security backdoor that bypasses audit trail. If attacker gains platform_admin role, they have invisible unrestricted access. Self-lockout prevention is not worth the security tradeoff - recovery via migration is acceptable.

### 4. Immutable Core Permissions
Use database triggers to prevent deletion of platform_admin permissions.

**Rejected:** Adds complexity without meaningful benefit. If platform_admin wants to lock themselves out, the trigger would need to be bypassed anyway. Migration-based recovery is simpler.

## Related ADRs

- [ADR-027: Authentication](./ADR-027-authentication.md) - User authentication
- [ADR-028: Dynamic RBAC System](./ADR-028-dynamic-rbac-system.md) - Core RBAC implementation
- [ADR-031: API Key Management](./ADR-031-api-key-management.md) - Encrypted API key storage
