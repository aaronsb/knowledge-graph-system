# API Endpoints Reference

Overview of Knowledge Graph API endpoints organized by access level and functional area.

## Access Levels

| Level | Description | Who Has Access |
|-------|-------------|----------------|
| **Public** | No authentication required | Anyone |
| **Authenticated** | Requires valid login | All logged-in users |
| **Admin** | Requires admin role | Users with `role: admin` |

---

## Public Endpoints

No authentication required.

| Endpoint | Description |
|----------|-------------|
| `GET /` | API info and health check |
| `GET /health` | Simple health check |
| `POST /auth/login` | User login (returns JWT) |
| `POST /auth/token` | OAuth token endpoint |
| `GET /auth/device/code` | Device authorization flow |
| `POST /auth/device/token` | Device token polling |

---

## Authenticated Endpoints

Requires valid JWT token. Available to all logged-in users.

### User Account
| Endpoint | Description |
|----------|-------------|
| `GET /auth/me` | Get current user info |
| `POST /auth/logout` | Logout (invalidate token) |
| `GET /auth/oauth/clients/personal` | List own OAuth clients |
| `POST /auth/oauth/clients/personal/new` | Create personal OAuth client |
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
| `POST /ingest/image` | Ingest image (multimodal) |
| `POST /ingest/url` | Ingest from URL |

### Jobs
| Endpoint | Description |
|----------|-------------|
| `GET /jobs` | List jobs |
| `GET /jobs/{id}` | Get job status |
| `POST /jobs/{id}/approve` | Approve pending job |
| `POST /jobs/{id}/cancel` | Cancel job |

### Sources
| Endpoint | Description |
|----------|-------------|
| `GET /sources/{id}` | Get source content |
| `GET /sources/{id}/image` | Get source image (if applicable) |

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

## Admin Endpoints

Requires admin role. These endpoints can modify system configuration and perform destructive operations.

### User Management
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /auth/admin/users` | List all users | Read |
| `POST /auth/admin/users` | Create user | Low |
| `PATCH /auth/admin/users/{username}` | Update user | Medium |
| `DELETE /auth/admin/users/{username}` | Delete user | High |

### OAuth Client Management (All Clients)
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /auth/oauth/clients` | List all OAuth clients | Read |
| `DELETE /auth/oauth/clients/{id}` | Delete any OAuth client | High |

### Ontology Management
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `DELETE /ontology/{name}` | Delete ontology and all data | **Critical** |
| `POST /ontology/{name}/rename` | Rename ontology | Medium |

### System Status
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/status` | Full system health status | Read |
| `GET /admin/scheduler/status` | Job scheduler status | Read |
| `POST /admin/scheduler/cleanup` | Trigger job cleanup | Low |

### API Key Management
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/keys` | List API keys (masked) | Read |
| `POST /admin/keys/{provider}` | Set/rotate API key | High |
| `DELETE /admin/keys/{provider}` | Delete API key | High |

### Embedding Configuration
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/embedding/config` | Full embedding config | Read |
| `GET /admin/embedding/configs` | List all configs | Read |
| `GET /admin/embedding/status` | Embedding coverage stats | Read |
| `POST /admin/embedding/config` | Create new config | Medium |
| `POST /admin/embedding/config/{id}/activate` | Activate config | **Critical** |
| `POST /admin/embedding/config/{id}/protect` | Set protection flags | Low |
| `DELETE /admin/embedding/config/{id}` | Delete config | High |
| `POST /admin/embedding/config/reload` | Hot reload model | High |
| `POST /admin/embedding/regenerate` | Regenerate embeddings | **Critical** |

### Extraction Configuration
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/extraction/config` | Full extraction config | Read |
| `POST /admin/extraction/config` | Update extraction config | High |

### Vocabulary Configuration
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/vocabulary/config` | Full vocabulary config | Read |
| `PUT /admin/vocabulary/config` | Update vocabulary config | High |
| `GET /admin/vocabulary/profiles` | List aggressiveness profiles | Read |
| `POST /admin/vocabulary/profiles` | Create custom profile | Low |
| `DELETE /admin/vocabulary/profiles/{name}` | Delete custom profile | Medium |

### Backup & Restore
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/backups` | List backups | Read |
| `POST /admin/backup` | Create backup | Low |
| `POST /admin/restore` | Restore from backup | **Critical** |

### RBAC Management
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /admin/rbac/*` | Read RBAC config | Read |
| `POST /admin/rbac/*` | Create roles/permissions | Medium |
| `DELETE /admin/rbac/*` | Delete roles/permissions | High |

### Database Operations
| Endpoint | Description | Impact |
|----------|-------------|--------|
| `GET /database/stats` | Database statistics | Read |
| `POST /admin/regenerate-concept-embeddings` | Regenerate embeddings | **Critical** |

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

- [Authentication (ADR-027)](../../architecture/ADR-027-authentication.md)
- [RBAC (ADR-028)](../../architecture/ADR-028-rbac.md)
- [API Key Management (ADR-031)](../../architecture/ADR-031-api-key-management.md)
