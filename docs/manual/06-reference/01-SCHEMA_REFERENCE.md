# PostgreSQL Schema Reference

## Overview

The Knowledge Graph system uses a multi-schema PostgreSQL architecture for separation of concerns and performance optimization.

**Related ADRs:**
- ADR-024: Multi-Schema PostgreSQL Architecture
- ADR-025: Dynamic Relationship Vocabulary Management
- ADR-026: Autonomous Vocabulary Curation

## Schema Organization

```
PostgreSQL (knowledge_graph database)
│
├── ag_catalog           # Apache AGE graph data (managed by AGE extension)
│   └── knowledge_graph  # Graph vertices and edges
│
├── kg_api              # API operational state
│   ├── ingestion_jobs           # Job queue (replaces SQLite)
│   ├── relationship_vocabulary  # Canonical relationship types
│   ├── skipped_relationships    # Capture layer for unmatched types
│   ├── edge_usage_stats        # Performance tracking
│   ├── concept_access_stats    # Node-level access patterns
│   ├── ontology_versions       # Formal versioning
│   ├── vocabulary_suggestions  # LLM-assisted curation
│   └── ... (sessions, rate limits, workers)
│
├── kg_auth             # Security and access control
│   ├── users                   # User accounts
│   ├── api_keys               # API authentication
│   ├── oauth_tokens           # OAuth integration (future)
│   └── role_permissions       # RBAC definitions
│
└── kg_logs             # Observability
    ├── audit_trail            # Compliance logging
    ├── api_metrics           # Performance tracking
    ├── job_events            # Detailed job history
    └── health_checks         # System monitoring
```

## Default Credentials

**Username:** `admin`
**Password:** `admin`
**Role:** `admin` (full system access)

⚠️ **IMPORTANT:** Change the default password in production!

```sql
UPDATE kg_auth.users
SET password_hash = 'your_bcrypt_hash_here'
WHERE username = 'admin';
```

## Roles and Permissions

### Role Hierarchy

| Role | Description | Permissions |
|------|-------------|-------------|
| `read_only` | View-only access | Read concepts, vocabulary, jobs |
| `contributor` | Can ingest documents | Read + write concepts, create jobs |
| `curator` | Manages vocabulary | Contributor + approve vocabulary changes |
| `admin` | Full system access | All permissions including user management |

### Permission Structure

```sql
-- Example: Check permissions for a role
SELECT resource, action, granted
FROM kg_auth.role_permissions
WHERE role = 'curator';
```

## Key Tables

### kg_api.ingestion_jobs

Job queue for document ingestion (replaces SQLite jobs.db).

**Key Fields:**
- `job_id` (VARCHAR): Unique job identifier
- `status` (VARCHAR): pending, awaiting_approval, running, completed, failed, cancelled
- `ontology` (VARCHAR): Namespace for concepts
- `progress` (JSONB): Real-time progress updates
- `analysis` (JSONB): Cost estimates (ADR-014)

**Performance:**
- No write-lock contention (PostgreSQL MVCC)
- Indexed by status, ontology, created_at
- Auto-archival after 30 days

### kg_api.relationship_vocabulary

Canonical relationship types with semantic descriptions.

**Builtin Types:** 30 core types (logical, causal, structural, evidential, similarity, temporal, functional, meta)

**Key Fields:**
- `relationship_type` (VARCHAR): Type name (e.g., IMPLIES, SUPPORTS)
- `description` (TEXT): Clear semantic definition
- `category` (VARCHAR): Semantic grouping
- `usage_count` (INTEGER): Number of graph edges using this type
- `is_builtin` (BOOLEAN): Protected core types
- `is_active` (BOOLEAN): Available for new relationships

**Vocabulary Window:**
- Min: 30 (builtin types)
- Max: 100 (active custom types)
- Hard limit: 500 (including deprecated)

### kg_api.skipped_relationships

Capture layer for relationship types that don't match vocabulary.

**Purpose:** Data-driven vocabulary expansion

**Key Fields:**
- `relationship_type` (VARCHAR): Unmatched type
- `occurrence_count` (INTEGER): How often seen
- `sample_context` (JSONB): Example usage
- `ontology` (VARCHAR): Where it appears

**Curator Workflow:**
```bash
# Review skipped types
kg vocabulary review

# Approve as new type
kg vocabulary add ENHANCES --category augmentation

# Or map to existing type
kg vocabulary alias ENHANCES --maps-to SUPPORTS
```

### kg_api.ontology_versions

Formal semantic versioning for vocabulary evolution.

**Version Format:** Semantic versioning (MAJOR.MINOR.PATCH)
- MAJOR: Breaking changes (type removed, semantics changed)
- MINOR: New types added (backward compatible)
- PATCH: Aliases, description updates

**Key Fields:**
- `version_number` (VARCHAR): e.g., "1.2.3"
- `vocabulary_snapshot` (JSONB): Immutable state at version
- `types_added` (TEXT[]): What changed
- `backward_compatible` (BOOLEAN): Migration required?

**Initial Version:** 1.0.0 (30 builtin types)

### kg_auth.users

User account management.

**Roles:**
- `read_only`: View-only
- `contributor`: Can ingest
- `curator`: Can manage vocabulary
- `admin`: Full access

**Password Security:**
- Bcrypt hashed passwords
- No plaintext storage
- Session-based authentication

### kg_logs.audit_trail

Compliance and security logging.

**Retention:** 7 years (compliance requirement)

**Logged Actions:**
- User authentication
- Concept creation/modification
- Vocabulary changes
- Job approval/execution
- User management

**Key Fields:**
- `user_id` (INTEGER): Who performed action
- `action` (VARCHAR): What they did
- `resource_type` / `resource_id`: What was affected
- `outcome` (VARCHAR): success, denied, error
- `ip_address` (INET): Source IP

## Performance Features

### Materialized Views

**kg_api.hot_edges** (top 1000 most-traversed edges):
```sql
-- Refresh cache
REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_edges;
```

**kg_api.hot_concepts** (top 100 most-accessed concepts):
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY kg_api.hot_concepts;
```

### Maintenance Functions

**Clean expired sessions:**
```sql
SELECT cleanup_expired_sessions();
-- Returns: Number of sessions deleted
```

**Archive old jobs:**
```sql
SELECT archive_old_jobs(30);  -- Archive jobs older than 30 days
-- Returns: Number of jobs archived
```

**Refresh performance views:**
```sql
SELECT refresh_hot_edges();
SELECT refresh_hot_concepts();
```

## Connection Information

**Database:** `knowledge_graph`
**Host:** `localhost`
**Port:** `5432`
**User:** `admin`
**Password:** `password` (from .env or default)

**Connection String:**
```
postgresql://admin:password@localhost:5432/knowledge_graph
```

**Python (psycopg2):**
```python
import psycopg2
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="knowledge_graph",
    user="admin",
    password="password"
)
```

**Schema-Specific Queries:**
```python
# Query kg_api schema
cursor.execute("SELECT * FROM kg_api.ingestion_jobs WHERE status = 'running'")

# Query kg_auth schema
cursor.execute("SELECT * FROM kg_auth.users WHERE role = 'admin'")

# Query kg_logs schema
cursor.execute("SELECT * FROM kg_logs.audit_trail ORDER BY timestamp DESC LIMIT 100")
```

## Initialization

### Fresh Environment Setup

On first startup, Docker automatically runs `schema/00_baseline.sql` from `/docker-entrypoint-initdb.d/`:

**What gets initialized:**
1. Apache AGE extension and `knowledge_graph` graph
2. Multi-schema architecture (`kg_api`, `kg_auth`, `kg_logs`)
3. Migration tracking system (`public.schema_migrations`)
4. All tables, indexes, and functions (see full list below)
5. Baseline migration recorded as version 1

**Verify Initialization:**
```bash
# Check schemas were created
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT schemaname, count(*) as table_count
FROM pg_tables
WHERE schemaname IN ('kg_api', 'kg_auth', 'kg_logs')
GROUP BY schemaname;
"

# Check migration system initialized
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT * FROM public.schema_migrations ORDER BY version;
"
# Expected: version=1, name='baseline'
```

### Schema Evolution via Migrations

After initial setup, schema changes are managed via **migrations** (ADR-040).

**Apply pending migrations:**
```bash
./scripts/database/migrate-db.sh -y
```

**Check migration status:**
```bash
./scripts/database/migrate-db.sh --dry-run
```

**See:** `docs/guides/02-DATABASE_MIGRATIONS.md` for complete migration guide

### Verify Seeded Data

**Builtin vocabulary types:**
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT count(*) FROM kg_api.relationship_vocabulary WHERE is_builtin = TRUE;
"
# Expected: 30
```

**Ontology version:**
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT version_number, array_length(types_added, 1) as type_count
FROM kg_api.ontology_versions;
"
# Expected: 1.0.0, 30 types
```

**Default admin user:**
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT username, role FROM kg_auth.users WHERE role = 'admin';
"
# Expected: admin, admin
```

## Migration from Old Schema (Pre-2.0)

If migrating from an existing installation (before baseline consolidation):

1. **Backup existing data:**
```bash
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup.sql
```

2. **Reset and restore approach (recommended):**
```bash
# Reset to fresh baseline
python -m src.admin.reset --auto-confirm

# Restore your data
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph < backup.sql

# Apply any pending migrations
./scripts/database/migrate-db.sh -y
```

3. **Or use migration system:**
- Schema changes now managed via numbered migrations
- See `docs/guides/02-DATABASE_MIGRATIONS.md`
- Migration system automatically applies changes in order

## Schema Version History

| Migration | Date | Changes |
|-----------|------|---------|
| 001 (baseline) | 2025-10-16 | Consolidated baseline schema v2.0.0 (ADR-024, ADR-025, ADR-026, ADR-028, ADR-039, ADR-040) |

**Current migration version:**
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT MAX(version) FROM public.schema_migrations;"
```

**See all applied migrations:**
```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT * FROM public.schema_migrations ORDER BY version;"
```

**For migration history:** See `schema/migrations/` directory and `docs/guides/02-DATABASE_MIGRATIONS.md`

## Troubleshooting

### Cannot connect to database
```bash
# Check container is running
docker ps | grep knowledge-graph-postgres

# Check logs
docker logs knowledge-graph-postgres

# Test connection
docker exec knowledge-graph-postgres pg_isready -U admin -d knowledge_graph
```

### Schema not initialized
```bash
# List all schemas
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "\dn"

# If missing, manually run migration
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph < schema/multi_schema.sql
```

### Permission denied errors
```bash
# Check user role
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT username, role FROM kg_auth.users WHERE username = 'your_user';
"

# Check role permissions
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT * FROM kg_auth.role_permissions WHERE role = 'your_role';
"
```

## References

- ADR-024: Multi-Schema PostgreSQL Architecture
- ADR-025: Dynamic Relationship Vocabulary Management
- ADR-026: Autonomous Vocabulary Curation and Ontology Management
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Apache AGE Documentation: https://age.apache.org/
