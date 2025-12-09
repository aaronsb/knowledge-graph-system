# ADR-074 Implementation Checklist

**Status:** In Progress
**Started:** 2025-12-09
**ADR:** [ADR-074: Platform Admin Role](./ADR-074-platform-admin-role.md)

## Phase 1: Database Migration ✅ COMPLETE

- [x] Create migration file `schema/migrations/028_platform_admin_resources.sql`
- [x] Register 15 resource types with available_actions
- [x] Create `platform_admin` role with parent_role = 'admin'
- [x] Grant permissions to `contributor` role (graph:read, ingest:create, etc.)
- [x] Grant permissions to `curator` role (vocabulary:write, ontologies:create)
- [x] Grant permissions to `admin` role (users, oauth_clients, read-only platform)
- [x] Grant permissions to `platform_admin` role (full platform access)
- [x] Test migration is idempotent (can run multiple times safely)
- [x] Apply migration to dev environment

**Results:** 19 resources, 5 roles, ~83 permission grants

## Phase 2: Replace require_role with require_permission ✅ COMPLETE

Replaced `Depends(require_role("admin"))` with `Depends(require_permission("resource", "action"))`:

### Platform Administration (Critical) ✅
- [x] `admin.py` - `/admin/status` → `admin:status`
- [x] `admin.py` - `/admin/backup` → `backups:create`
- [x] `admin.py` - `/admin/backups` → `backups:read`
- [x] `admin.py` - `/admin/restore` → `backups:restore`
- [x] `admin.py` - `/admin/keys` GET → `api_keys:read`
- [x] `admin.py` - `/admin/keys/{provider}` POST → `api_keys:write`
- [x] `admin.py` - `/admin/keys/{provider}` DELETE → `api_keys:delete`

### Embedding Configuration ✅
- [x] `embedding.py` - `/admin/embedding/config` GET → `embedding_config:read`
- [x] `embedding.py` - `/admin/embedding/configs` GET → `embedding_config:read`
- [x] `embedding.py` - `/admin/embedding/config` POST → `embedding_config:create`
- [x] `embedding.py` - `/admin/embedding/config/{id}` DELETE → `embedding_config:delete`
- [x] `embedding.py` - `/admin/embedding/config/{id}/activate` → `embedding_config:activate`
- [x] `embedding.py` - `/admin/embedding/config/reload` → `embedding_config:reload`
- [x] `embedding.py` - `/admin/embedding/regenerate` → `embedding_config:regenerate`
- [x] `embedding.py` - `/admin/embedding/status` → `embedding_config:read`
- [x] `admin.py` - `/admin/regenerate-concept-embeddings` → `embedding_config:regenerate`

### Extraction Configuration ✅
- [x] `extraction.py` - `/admin/extraction/config` GET → `extraction_config:read`
- [x] `extraction.py` - `/admin/extraction/config` POST → `extraction_config:write`

### User Management ✅
- [x] `auth.py` - `/users` GET → `users:read`
- [x] `auth.py` - `/users/{id}` GET → `users:read`
- [x] `auth.py` - `/users/{id}` PUT → `users:write`
- [x] `auth.py` - `/users/{id}` DELETE → `users:delete`

### OAuth Client Management (Admin) ✅
- [x] `oauth.py` - `/auth/oauth/clients` GET → `oauth_clients:read`
- [x] `oauth.py` - `/auth/oauth/clients` POST → `oauth_clients:create`
- [x] `oauth.py` - `/auth/oauth/clients/{id}` GET → `oauth_clients:read`
- [x] `oauth.py` - `/auth/oauth/clients/{id}` PATCH → `oauth_clients:write`
- [x] `oauth.py` - `/auth/oauth/clients/{id}` DELETE → `oauth_clients:delete`
- [x] `oauth.py` - `/auth/oauth/clients/{id}/rotate-secret` → `oauth_clients:write`

### Ontology Management ✅
- [x] `ontology.py` - `/ontology/{name}` DELETE → `ontologies:delete`
- [x] `ontology.py` - `/ontology/{name}/rename` → `ontologies:create`

### RBAC Management ✅
- [x] `rbac.py` - All 17 endpoints → `rbac:read/write/create/delete`

### Vocabulary Configuration ✅
- [x] `vocabulary_config.py` - `/admin/vocabulary/config` GET → `vocabulary_config:read`
- [x] `vocabulary_config.py` - `/admin/vocabulary/config` PUT → `vocabulary_config:write`
- [x] `vocabulary_config.py` - `/admin/vocabulary/profiles` GET → `vocabulary_config:read`
- [x] `vocabulary_config.py` - `/admin/vocabulary/profiles` POST → `vocabulary_config:create`
- [x] `vocabulary_config.py` - `/admin/vocabulary/profiles/{name}` GET → `vocabulary_config:read`
- [x] `vocabulary_config.py` - `/admin/vocabulary/profiles/{name}` DELETE → `vocabulary_config:delete`

### Vocabulary Operations ✅
- [x] `vocabulary.py` - Write operations → `vocabulary:write`

**Results:** 9 route files updated, ~60 endpoints migrated to permission-based auth

## Phase 3: Verify and Test

- [ ] Run API tests to verify permissions work
- [ ] Test role inheritance (platform_admin → admin → curator → contributor)
- [ ] Test explicit deny functionality
- [ ] Verify public endpoints still work without auth
- [ ] Test authenticated-only endpoints (personal OAuth clients, etc.)

## Phase 4: CLI Role Management

- [ ] `kg rbac roles list` - List all roles
- [ ] `kg rbac roles create <name>` - Create custom role
- [ ] `kg rbac roles delete <name>` - Delete custom role
- [ ] `kg rbac resources list` - List all resource types and actions
- [ ] `kg rbac permissions list` - List permissions (filterable)
- [ ] `kg rbac permissions grant <role> <resource> <action>`
- [ ] `kg rbac permissions revoke <role> <resource> <action>`

## Phase 5: Web UI Updates

- [ ] Update AdminDashboard to check permissions per section
- [ ] Hide/disable features based on effective permissions
- [ ] Add visual indicator for platform admin users
- [ ] Show appropriate error messages for permission denied

## Phase 6: Documentation

- [ ] Update `docs/reference/api/ADMIN-ENDPOINTS.md`
- [ ] Add Platform Admin setup to operator docs
- [ ] Document recovery procedure for self-lockout
- [ ] Update CLAUDE.md with platform admin workflow

---

## Progress Log

### 2025-12-09
- Created ADR-074 with full resource inventory (15 resources)
- Updated all API endpoint docstrings with RBAC authorization format
- Implementation checklist created
- **Phase 1 complete:** Migration 028 applied - 19 resources, 5 roles, ~83 permissions
- **Phase 2 complete:** Replaced require_role → require_permission in 9 route files (~60 endpoints)
