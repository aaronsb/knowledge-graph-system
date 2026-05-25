# API Endpoints Reference

Overview of Knowledge Graph API endpoints organized by access level and functional area.

## Access Levels (ADR-074)

The system uses **fine-grained permission-based access control** instead of simple role checks.

### Role Hierarchy

```
platform_admin → admin → curator → contributor
```

Each role inherits permissions from roles below it in the hierarchy.

### Permission Format

Permissions follow the format `resource:action`. For example:
- `users:read` - Permission to view user list
- `oauth_clients:delete` - Permission to delete OAuth clients
- `admin:status` - Permission to view system status

### Access Levels

| Level | Description | Who Has Access |
|-------|-------------|----------------|
| **Public** | No authentication required | Anyone |
| **Authenticated** | Requires valid OAuth token | All logged-in users |
| **Permission-based** | Requires specific `resource:action` permission | Users with granted permissions |

### Default Role Permissions

| Role | Key Permissions |
|------|-----------------|
| **contributor** | `graph:read`, `ingest:create/read`, `jobs:approve/cancel`, `ontologies:read` |
| **curator** | All contributor + `vocabulary:write`, `ontologies:create` |
| **admin** | All curator + `users:*`, `oauth_clients:*`, `rbac:read` |
| **platform_admin** | All admin + `admin:status`, `backups:*`, `api_keys:*`, `embedding_config:*`, `rbac:*` |

---

## Public Endpoints

No authentication required.

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info and health check |
| `GET /health` | Simple health check |
| `POST /auth/register` | User registration |
| `POST /auth/oauth/token` | OAuth token endpoint (all grant types) |
| `POST /auth/oauth/device` | Device authorization request |
| `GET /auth/oauth/device-status/{user_code}` | Device code status |
| `GET /auth/oauth/authorize` | OAuth authorization code flow |
| `POST /auth/oauth/login-and-authorize` | Combined login + authorize (viz-app) |

---

## Authenticated Endpoints

Requires valid JWT token. Available to all logged-in users.

### User Account
| Endpoint | Description |
|----------|-------------|
| `GET /users/me` | Get current user info (ADR-054) |
| `GET /users/me/permissions` | Get effective permissions (ADR-074) |
| `PUT /auth/me` | Update own profile (password) |
| `POST /auth/oauth/revoke` | Revoke OAuth token |
| `GET /auth/oauth/clients/personal` | List own OAuth clients |
| `POST /auth/oauth/clients/personal` | Create personal OAuth client |
| `POST /auth/oauth/clients/personal/new` | Create additional personal client |
| `POST /auth/oauth/clients/personal/{id}/rotate-secret` | Rotate own client secret |
| `DELETE /auth/oauth/clients/personal/{id}` | Delete own OAuth client |

### Knowledge Graph Queries
| Endpoint | Description |
|----------|-------------|
| `POST /query/search` | Semantic concept search |
| `POST /query/concept` | Get concept details, related, or connections |
| `GET /query/statistics` | Graph statistics |

### Ontology (Read)
| Endpoint | Description |
|----------|-------------|
| `GET /ontology/` | List all ontologies |
| `GET /ontology/{name}` | Get ontology info |
| `GET /ontology/{name}/files` | List files in ontology |

### Ingestion
| Endpoint | Description |
|----------|-------------|
| `POST /ingest` | Upload file for ingestion |
| `POST /ingest/text` | Ingest raw text |
| `POST /ingest/image` | Ingest image (multimodal, ADR-057) |

### Jobs
| Endpoint | Description |
|----------|-------------|
| `GET /jobs` | List jobs |
| `GET /jobs/{id}` | Get job status |
| `GET /jobs/{id}/stream` | Stream job progress (SSE) |
| `POST /jobs/{id}/approve` | Approve pending job |
| `DELETE /jobs/{id}` | Cancel or delete a job |
| `DELETE /jobs` | Bulk delete jobs with filters |

### Sources
| Endpoint | Description |
|----------|-------------|
| `GET /sources` | List source nodes |
| `GET /sources/{id}` | Get source metadata and content |
| `GET /sources/{id}/image` | Retrieve image from source (ADR-057) |
| `GET /sources/{id}/document` | Retrieve original document from Garage (ADR-081) |

### Vocabulary (Read)
| Endpoint | Description |
|----------|-------------|
| `GET /vocabulary/types` | List vocabulary types |
| `GET /vocabulary/categories` | List vocabulary categories |
| `GET /vocabulary/config` | Get vocabulary config (public view) |

### Embedding (Read)
| Endpoint | Description |
|----------|-------------|
| `GET /embedding/config` | Get embedding config (public view) |

### Extraction (Read)
| Endpoint | Description |
|----------|-------------|
| `GET /extraction/config` | Get extraction config (public view) |

---

## Permission-Protected Endpoints (ADR-074)

These endpoints require specific permissions. Each endpoint shows the required `resource:action` permission.

### User Management
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /users/me` | (authenticated) | Get own profile | Read |
| `GET /users/me/permissions` | (authenticated) | Get effective permissions | Read |
| `GET /users` | `users:read` | List all users | Read |
| `POST /users` | `users:create` | Create user | Medium |
| `GET /users/{id}` | `users:read` | Get user details | Read |
| `PUT /users/{id}` | `users:write` | Update user | Medium |
| `DELETE /users/{id}` | `users:delete` | Delete user | High |
| `POST /users/{id}/reset-password` | `users:write` | Admin reset of user password | High |

### OAuth Client Management
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /auth/oauth/clients` | `oauth_clients:read` | List all OAuth clients | Read |
| `POST /auth/oauth/clients` | `oauth_clients:create` | Create OAuth client | Low |
| `GET /auth/oauth/clients/{id}` | `oauth_clients:read` | Get client details | Read |
| `PATCH /auth/oauth/clients/{id}` | `oauth_clients:write` | Update client | Medium |
| `DELETE /auth/oauth/clients/{id}` | `oauth_clients:delete` | Delete client | High |
| `POST /auth/oauth/clients/{id}/rotate-secret` | `oauth_clients:write` | Rotate secret | High |

### Ontology Management
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `DELETE /ontology/{name}` | `ontologies:delete` | Delete ontology and all data | **Critical** |
| `POST /ontology/{name}/rename` | `ontologies:create` | Rename ontology | Medium |

### System Status
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/status` | `admin:status` | Full system health status | Read |
| `GET /admin/scheduler/status` | `admin:status` | Job scheduler status | Read |
| `POST /admin/scheduler/cleanup` | `admin:status` | Trigger job cleanup | Low |

### API Key Management
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/keys` | `api_keys:read` | List API keys (masked) | Read |
| `POST /admin/keys/{provider}` | `api_keys:write` | Set/rotate API key | High |
| `DELETE /admin/keys/{provider}` | `api_keys:delete` | Delete API key | High |

### Embedding Configuration
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/embedding/config` | `embedding_config:read` | Full embedding config | Read |
| `GET /admin/embedding/configs` | `embedding_config:read` | List all configs | Read |
| `GET /admin/embedding/status` | `embedding_config:read` | Embedding coverage stats | Read |
| `POST /admin/embedding/config` | `embedding_config:create` | Create new config | Medium |
| `POST /admin/embedding/config/{id}/activate` | `embedding_config:activate` | Activate config | **Critical** |
| `DELETE /admin/embedding/config/{id}` | `embedding_config:delete` | Delete config | High |
| `POST /admin/embedding/config/reload` | `embedding_config:reload` | Hot reload model | High |
| `POST /admin/embedding/regenerate` | `embedding_config:regenerate` | Regenerate embeddings | **Critical** |

### Extraction Configuration
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/extraction/config` | `extraction_config:read` | Full extraction config | Read |
| `POST /admin/extraction/config` | `extraction_config:write` | Update extraction config | High |

### Vocabulary Configuration
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/vocabulary/config` | `vocabulary_config:read` | Full vocabulary config | Read |
| `PUT /admin/vocabulary/config` | `vocabulary_config:write` | Update vocabulary config | High |
| `GET /admin/vocabulary/profiles` | `vocabulary_config:read` | List aggressiveness profiles | Read |
| `POST /admin/vocabulary/profiles` | `vocabulary_config:create` | Create custom profile | Low |
| `DELETE /admin/vocabulary/profiles/{name}` | `vocabulary_config:delete` | Delete custom profile | Medium |

### Backup & Restore
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /admin/backups` | `backups:read` | List backups | Read |
| `POST /admin/backup` | `backups:create` | Create backup | Low |
| `POST /admin/restore` | `backups:restore` | Restore from backup | **Critical** |

### RBAC Management
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /rbac/resources` | `rbac:read` | List resource types | Read |
| `GET /rbac/roles` | `rbac:read` | List roles | Read |
| `GET /rbac/permissions` | `rbac:read` | List permissions | Read |
| `POST /rbac/resources` | `rbac:create` | Create resource type | Medium |
| `POST /rbac/roles` | `rbac:create` | Create role | Medium |
| `POST /rbac/permissions` | `rbac:create` | Grant permission | Medium |
| `DELETE /rbac/roles/{name}` | `rbac:delete` | Delete role | High |
| `DELETE /rbac/permissions/{id}` | `rbac:delete` | Revoke permission | High |
| `POST /rbac/check-permission` | `rbac:read` | Check user permission | Read |

### Database Operations
| Endpoint | Permission | Description | Impact |
|----------|------------|-------------|--------|
| `GET /database/stats` | `database:read` | Database statistics | Read |
| `POST /admin/regenerate-concept-embeddings` | `embedding_config:regenerate` | Regenerate embeddings | **Critical** |

---

## Impact Levels

| Level | Description |
|-------|-------------|
| **Read** | No changes, safe to call |
| **Low** | Minor changes, easily reversible |
| **Medium** | Moderate changes, may affect operations |
| **High** | Significant changes, requires care |
| **Critical** | Destructive or irreversible, requires confirmation |

---

## CLI Mapping

Admin endpoints are accessible via the `kg` CLI:

```
kg admin status              → GET /admin/status
kg admin keys list           → GET /admin/keys
kg admin keys set <provider> → POST /admin/keys/{provider}
kg admin embedding list      → GET /admin/embedding/configs
kg admin embedding activate  → POST /admin/embedding/config/{id}/activate
kg admin extraction config   → GET /admin/extraction/config
kg admin backup              → POST /admin/backup
kg admin restore             → POST /admin/restore
```

---

## Related Documentation

- [Authentication (ADR-027)](../../architecture/authentication-security/ADR-027-user-management-api.md)
- [RBAC (ADR-028)](../../architecture/authentication-security/ADR-028-dynamic-rbac-system.md)
- [API Key Management (ADR-031)](../../architecture/authentication-security/ADR-031-encrypted-api-key-storage.md)
- [Platform Admin Role (ADR-074)](../../architecture/authentication-security/ADR-074-platform-admin-role.md) - Fine-grained permission model
