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

Register **15 resource types** with **domain-specific actions** (not generic CRUD):

#### Platform Administration Resources (Critical)

| Resource | Actions | Description |
|----------|---------|-------------|
| `api_keys` | read, write, delete | Manage AI provider API keys |
| `embedding_config` | read, create, delete, activate, reload, regenerate | Embedding system |
| `extraction_config` | read, write | AI extraction provider settings |
| `backups` | read, create, restore | Backup/restore (restore ≠ create!) |

#### Content & Data Resources

| Resource | Actions | Description |
|----------|---------|-------------|
| `ontologies` | read, create, delete | Ontology management (no update - names immutable) |
| `graph` | read, execute | Query the knowledge graph (execute = raw Cypher) |
| `ingest` | create | Submit documents for ingestion |
| `sources` | read | Retrieve source documents and images |
| `vocabulary` | read, write | Vocabulary type management |
| `vocabulary_config` | read, write, create, delete | Vocabulary profiles and settings |
| `database` | read, execute | Database stats and direct queries |

#### Identity & Access Resources

| Resource | Actions | Description |
|----------|---------|-------------|
| `users` | read, write, delete | User account management |
| `oauth_clients` | read, write, create, delete | OAuth client management (all clients) |
| `rbac` | read, write, create, delete | RBAC roles, resources, and permissions |

#### System Resources

| Resource | Actions | Description |
|----------|---------|-------------|
| `admin` | status | View admin dashboard status |

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

#### Platform Administration

| Resource | Action | Endpoint | HTTP |
|----------|--------|----------|------|
| `api_keys` | read | `/admin/keys` | GET |
| `api_keys` | write | `/admin/keys/{provider}` | POST |
| `api_keys` | delete | `/admin/keys/{provider}` | DELETE |
| `embedding_config` | read | `/admin/embedding/config`, `/admin/embedding/configs` | GET |
| `embedding_config` | create | `/admin/embedding/config` | POST |
| `embedding_config` | delete | `/admin/embedding/config/{id}` | DELETE |
| `embedding_config` | activate | `/admin/embedding/config/{id}/activate` | POST |
| `embedding_config` | reload | `/admin/embedding/config/reload` | POST |
| `embedding_config` | regenerate | `/admin/embedding/regenerate` | POST |
| `extraction_config` | read | `/admin/extraction/config` | GET |
| `extraction_config` | write | `/admin/extraction/config` | POST |
| `backups` | read | `/admin/backups` | GET |
| `backups` | create | `/admin/backup` | POST |
| `backups` | restore | `/admin/restore` | POST |
| `admin` | status | `/admin/status` | GET |

#### Content & Data

| Resource | Action | Endpoint | HTTP |
|----------|--------|----------|------|
| `ontologies` | read | `/ontology/`, `/ontology/{name}`, `/ontology/{name}/files` | GET |
| `ontologies` | create | (via ingest) | POST |
| `ontologies` | delete | `/ontology/{name}` | DELETE |
| `graph` | read | `/query/search`, `/query/concept/{id}`, `/query/related`, `/query/connect`, `/query/connect-by-search`, `/query/sources/search`, `/query/polarity-axis` | GET/POST |
| `graph` | execute | `/query/cypher` | POST |
| `ingest` | create | `/ingest`, `/ingest/text` | POST |
| `sources` | read | `/sources/{id}`, `/sources/{id}/image` | GET |
| `vocabulary` | read | `/vocabulary/status`, `/vocabulary/types`, `/vocabulary/similar/{type}`, `/vocabulary/analyze/{type}`, `/vocabulary/category-scores/{type}`, `/vocabulary/epistemic-status`, `/vocabulary/epistemic-status/{type}` | GET |
| `vocabulary` | write | `/vocabulary/types`, `/vocabulary/merge`, `/vocabulary/consolidate`, `/vocabulary/generate-embeddings`, `/vocabulary/refresh-categories`, `/vocabulary/epistemic-status/measure` | POST |
| `vocabulary_config` | read | `/admin/vocabulary/config`, `/admin/vocabulary/profiles`, `/admin/vocabulary/profiles/{name}` | GET |
| `vocabulary_config` | write | `/admin/vocabulary/config` | PUT |
| `vocabulary_config` | create | `/admin/vocabulary/profiles` | POST |
| `vocabulary_config` | delete | `/admin/vocabulary/profiles/{name}` | DELETE |
| `database` | read | `/database/stats`, `/database/info` | GET |
| `database` | execute | `/database/query` | POST |

#### Identity & Access

| Resource | Action | Endpoint | HTTP |
|----------|--------|----------|------|
| `users` | read | `/users`, `/users/{id}` | GET |
| `users` | write | `/users/{id}` | PUT |
| `users` | delete | `/users/{id}` | DELETE |
| `oauth_clients` | read | `/auth/oauth/clients`, `/auth/oauth/clients/{id}` | GET |
| `oauth_clients` | write | `/auth/oauth/clients/{id}`, `/auth/oauth/clients/{id}/rotate-secret` | PATCH/POST |
| `oauth_clients` | create | `/auth/oauth/clients` | POST |
| `oauth_clients` | delete | `/auth/oauth/clients/{id}` | DELETE |
| `rbac` | read | `/rbac/resources`, `/rbac/resources/{type}`, `/rbac/roles`, `/rbac/roles/{name}`, `/rbac/permissions`, `/rbac/user-roles/{id}` | GET |
| `rbac` | write | `/rbac/resources/{type}`, `/rbac/roles/{name}` | PUT |
| `rbac` | create | `/rbac/resources`, `/rbac/roles`, `/rbac/permissions`, `/rbac/user-roles` | POST |
| `rbac` | delete | `/rbac/resources/{type}`, `/rbac/roles/{name}`, `/rbac/permissions/{id}`, `/rbac/user-roles/{id}` | DELETE |

#### No Permission Required (Authenticated Only)

These endpoints require a valid token but no specific permission:

| Endpoint | HTTP | Description |
|----------|------|-------------|
| `/users/me` | GET | Get current user profile |
| `/auth/me` | PUT | Update own profile |
| `/auth/oauth/clients/personal/*` | ALL | Manage own OAuth clients |
| `/auth/oauth/tokens`, `/auth/oauth/tokens/{hash}` | GET/DELETE | Manage own tokens |
| `/rbac/check-permission` | POST | Check own permissions |

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

#### Contributor Role (existing, extended)
```
graph:            read
ingest:           create
sources:          read
vocabulary:       read
ontologies:       read
```

#### Curator Role (existing, extended)
```
(inherits from contributor)
vocabulary:       read, write
ontologies:       read, create
```

#### Admin Role (existing, extended)
```
(inherits from curator)
api_keys:         read
embedding_config: read
extraction_config: read
oauth_clients:    read, create, delete
ontologies:       read, create
backups:          read
users:            read, write, delete
rbac:             read
vocabulary_config: read
database:         read
admin:            status
```

#### Platform Admin Role (new default)
```
(inherits from admin)
api_keys:         read, write, delete
embedding_config: read, create, delete, activate, reload, regenerate
extraction_config: read, write
oauth_clients:    read, write, create, delete
ontologies:       read, create, delete
backups:          read, create, restore
rbac:             read, write, create, delete
vocabulary_config: read, write, create, delete
database:         read, execute
graph:            read, execute
```

Note: Role inheritance means `platform_admin` gets all permissions from `admin`, which gets all from `curator`, which gets all from `contributor`. Explicit permissions are still granted for clarity and to ensure roles work even if inheritance is modified.

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
-- Register All Resource Types
-- =============================================================================

INSERT INTO kg_auth.resources (resource_type, description, available_actions, supports_scoping, registered_by)
VALUES
    -- Platform Administration (Critical)
    ('api_keys', 'API key management for AI providers',
     ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('embedding_config', 'Embedding model configuration and operations',
     ARRAY['read', 'create', 'delete', 'activate', 'reload', 'regenerate'], FALSE, 'system'),
    ('extraction_config', 'AI extraction provider configuration',
     ARRAY['read', 'write'], FALSE, 'system'),
    ('backups', 'System backup and restore operations',
     ARRAY['read', 'create', 'restore'], FALSE, 'system'),
    ('admin', 'Admin dashboard and status',
     ARRAY['status'], FALSE, 'system'),

    -- Content & Data
    ('ontologies', 'Ontology management including deletion',
     ARRAY['read', 'create', 'delete'], FALSE, 'system'),
    ('graph', 'Knowledge graph queries',
     ARRAY['read', 'execute'], FALSE, 'system'),
    ('ingest', 'Document ingestion',
     ARRAY['create'], FALSE, 'system'),
    ('sources', 'Source document retrieval',
     ARRAY['read'], FALSE, 'system'),
    ('vocabulary', 'Vocabulary type management',
     ARRAY['read', 'write'], FALSE, 'system'),
    ('vocabulary_config', 'Vocabulary configuration and profiles',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system'),
    ('database', 'Database statistics and queries',
     ARRAY['read', 'execute'], FALSE, 'system'),

    -- Identity & Access
    ('users', 'User account management',
     ARRAY['read', 'write', 'delete'], FALSE, 'system'),
    ('oauth_clients', 'OAuth client management (all clients)',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system'),
    ('rbac', 'RBAC roles, resources, and permissions',
     ARRAY['read', 'write', 'create', 'delete'], FALSE, 'system')
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
-- Grant Permissions to Contributor Role (content access)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('contributor', 'graph', 'read', 'global', TRUE),
    ('contributor', 'ingest', 'create', 'global', TRUE),
    ('contributor', 'sources', 'read', 'global', TRUE),
    ('contributor', 'vocabulary', 'read', 'global', TRUE),
    ('contributor', 'ontologies', 'read', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Permissions to Curator Role (content management)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    ('curator', 'vocabulary', 'write', 'global', TRUE),
    ('curator', 'ontologies', 'create', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Permissions to Admin Role (user/system management, read-only platform)
-- =============================================================================

INSERT INTO kg_auth.role_permissions (role_name, resource_type, action, scope_type, granted)
VALUES
    -- Platform resources: read only
    ('admin', 'api_keys', 'read', 'global', TRUE),
    ('admin', 'embedding_config', 'read', 'global', TRUE),
    ('admin', 'extraction_config', 'read', 'global', TRUE),
    ('admin', 'backups', 'read', 'global', TRUE),
    ('admin', 'admin', 'status', 'global', TRUE),
    -- OAuth Clients: full access
    ('admin', 'oauth_clients', 'read', 'global', TRUE),
    ('admin', 'oauth_clients', 'create', 'global', TRUE),
    ('admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Users: full access
    ('admin', 'users', 'read', 'global', TRUE),
    ('admin', 'users', 'write', 'global', TRUE),
    ('admin', 'users', 'delete', 'global', TRUE),
    -- RBAC: read only
    ('admin', 'rbac', 'read', 'global', TRUE),
    -- Vocabulary config: read only
    ('admin', 'vocabulary_config', 'read', 'global', TRUE),
    -- Database: read only
    ('admin', 'database', 'read', 'global', TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grant Full Permissions to Platform Admin Role
-- =============================================================================

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
    ('platform_admin', 'oauth_clients', 'write', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'create', 'global', TRUE),
    ('platform_admin', 'oauth_clients', 'delete', 'global', TRUE),
    -- Ontologies: full access including delete
    ('platform_admin', 'ontologies', 'delete', 'global', TRUE),
    -- Backups: full access including restore
    ('platform_admin', 'backups', 'read', 'global', TRUE),
    ('platform_admin', 'backups', 'create', 'global', TRUE),
    ('platform_admin', 'backups', 'restore', 'global', TRUE),
    -- RBAC: full access
    ('platform_admin', 'rbac', 'read', 'global', TRUE),
    ('platform_admin', 'rbac', 'write', 'global', TRUE),
    ('platform_admin', 'rbac', 'create', 'global', TRUE),
    ('platform_admin', 'rbac', 'delete', 'global', TRUE),
    -- Vocabulary config: full access
    ('platform_admin', 'vocabulary_config', 'read', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'write', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'create', 'global', TRUE),
    ('platform_admin', 'vocabulary_config', 'delete', 'global', TRUE),
    -- Database: full access including execute
    ('platform_admin', 'database', 'read', 'global', TRUE),
    ('platform_admin', 'database', 'execute', 'global', TRUE),
    -- Graph: execute (raw Cypher)
    ('platform_admin', 'graph', 'execute', 'global', TRUE)
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
