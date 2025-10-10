# ADR-024: Multi-Schema PostgreSQL Architecture

**Status:** Proposed
**Date:** 2025-10-10
**Supersedes:** Partial aspects of ADR-016 (schema organization)
**Related:** ADR-016 (Apache AGE Migration), ADR-014 (Job Approval Workflow)

## Context

ADR-016 established PostgreSQL + Apache AGE as our unified database, giving us "relational SQL for free" alongside graph capabilities. However, the current implementation mixes all concerns into a single schema namespace (`public`), which creates several challenges:

### Current Pain Points

1. **Write-Lock Contention:**
   - Active jobs constantly write to SQLite `jobs.db`
   - `kg jobs list` blocks for 3-6 seconds waiting for write locks
   - Single-threaded SQLite inadequate for concurrent operations

2. **Unclear Separation of Concerns:**
   - Graph data (token-expensive, immutable) mixed with ephemeral job state
   - User/security tables alongside operational metrics
   - Difficult to apply different backup/retention policies

3. **Schema Complexity:**
   - Single `public` schema contains 15+ tables with different purposes
   - Hard to understand system boundaries
   - Migrations affect unrelated subsystems

4. **Security & Isolation:**
   - Cannot easily apply different access controls to different data types
   - Audit logs mixed with application state
   - User credentials in same namespace as graph data

### Why PostgreSQL Over SQLite for Jobs?

From ADR-016, we already have PostgreSQL running for Apache AGE. The "dual-use benefit" means:
- ✅ No additional infrastructure (PostgreSQL already required)
- ✅ No write-lock contention (PostgreSQL's MVCC handles concurrent writes)
- ✅ JSONB for progress/result fields (better than JSON strings)
- ✅ Proper indexes and query performance
- ✅ Atomic transactions across graph operations and job updates
- ✅ Single backup/restore workflow

**Key Insight:** Data created by spending inference tokens (graph) has fundamentally different characteristics than operational state (jobs, sessions). They deserve architectural separation.

## Decision

**Organize PostgreSQL into four isolated schemas, each with distinct purpose, lifecycle, and access patterns:**

### 1. Graph Schema (`ag_catalog`)

**Purpose:** Apache AGE graph data - the "expensive" data created by LLM inference

**Managed By:** Apache AGE extension (automatic)

**Contents:**
- Graph vertices: `Concept`, `Source`, `Instance`
- Graph edges: `APPEARS_IN`, `EVIDENCED_BY`, `IMPLIES`, `SUPPORTS`, etc.
- Vector embeddings (JSONB arrays, future: pgvector)

**Characteristics:**
- **Immutable** after creation (concepts don't change, only accumulate)
- **Token-expensive** to create (each concept costs ~$0.01-0.05 in LLM calls)
- **Persistent** (never auto-delete)
- **Read-heavy** (queries >> writes)
- **Requires full backups** (complete graph state)

**Access Pattern:**
- Read: All users (kg CLI, MCP server, web UI)
- Write: Ingestion workers only
- Never: Direct user modification

### 2. API State Schema (`kg_api`)

**Purpose:** Operational state for API server (job queue, sessions, rate limits)

**Managed By:** Application code (Python FastAPI)

**Contents:**
```sql
-- Job Queue (replaces SQLite jobs.db)
kg_api.ingestion_jobs (
    job_id VARCHAR PRIMARY KEY,
    job_type VARCHAR,
    status VARCHAR CHECK (status IN ('pending', 'awaiting_approval', ...)),
    ontology VARCHAR,
    client_id VARCHAR,
    content_hash VARCHAR(64),  -- Deduplication
    job_data JSONB,            -- Request payload
    progress JSONB,            -- Live updates
    result JSONB,              -- Final stats
    analysis JSONB,            -- Pre-ingestion cost estimates (ADR-014)
    processing_mode VARCHAR,   -- serial | parallel
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    approved_at TIMESTAMP,
    approved_by VARCHAR,
    expires_at TIMESTAMP
)

-- Active Sessions
kg_api.sessions (
    session_id VARCHAR PRIMARY KEY,
    user_id INTEGER,
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    last_activity TIMESTAMP,
    metadata JSONB
)

-- Rate Limiting
kg_api.rate_limits (
    client_id VARCHAR,
    endpoint VARCHAR,
    window_start TIMESTAMP,
    request_count INTEGER,
    PRIMARY KEY (client_id, endpoint, window_start)
)

-- Background Workers
kg_api.worker_status (
    worker_id VARCHAR PRIMARY KEY,
    last_heartbeat TIMESTAMP,
    current_job_id VARCHAR,
    status VARCHAR
)
```

**Characteristics:**
- **Ephemeral** (jobs auto-delete after 30 days)
- **Write-heavy** (constant progress updates)
- **Fast queries required** (no blocking on list operations)
- **Retention policy:** Keep completed jobs 30 days, failed jobs 90 days
- **Backup priority:** Low (can rebuild from graph if needed)

**Access Pattern:**
- Read/Write: API server
- Read: Monitoring tools
- Write: Background workers

### 3. Security Schema (`kg_auth`)

**Purpose:** Authentication, authorization, and access control

**Managed By:** Application code (Python FastAPI)

**Contents:**
```sql
-- User Accounts
kg_auth.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE,
    password_hash VARCHAR,
    role VARCHAR CHECK (role IN ('read_only', 'contributor', 'admin')),
    created_at TIMESTAMP,
    last_login TIMESTAMP,
    disabled BOOLEAN DEFAULT FALSE
)

-- API Keys
kg_auth.api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR UNIQUE,
    user_id INTEGER REFERENCES kg_auth.users(id),
    name VARCHAR,
    scopes TEXT[],  -- ['read:concepts', 'write:ingest']
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    expires_at TIMESTAMP
)

-- OAuth Tokens (future)
kg_auth.oauth_tokens (
    token_hash VARCHAR PRIMARY KEY,
    user_id INTEGER,
    provider VARCHAR,
    scopes TEXT[],
    expires_at TIMESTAMP
)

-- Role Permissions
kg_auth.role_permissions (
    role VARCHAR,
    resource VARCHAR,
    action VARCHAR,
    granted BOOLEAN
)
```

**Characteristics:**
- **Highly sensitive** (password hashes, API keys)
- **Low write volume** (occasional user changes)
- **Must encrypt at rest** (production requirement)
- **Strict retention** (GDPR: user data deletion on request)
- **Backup priority:** CRITICAL (encrypted backups only)

**Access Pattern:**
- Read: Authentication middleware only
- Write: User management endpoints only
- Audit: All access logged to `kg_logs`

### 4. Observability Schema (`kg_logs`)

**Purpose:** Audit trails, telemetry, and operational metrics

**Managed By:** Application code (Python FastAPI)

**Contents:**
```sql
-- Audit Log (compliance, security)
kg_logs.audit_trail (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    user_id INTEGER,
    action VARCHAR,          -- 'concept_created', 'job_approved', 'user_login'
    resource_type VARCHAR,   -- 'concept', 'job', 'user'
    resource_id VARCHAR,
    details JSONB,           -- Full request context
    ip_address INET,
    user_agent TEXT,
    outcome VARCHAR          -- 'success', 'denied', 'error'
)

-- Performance Metrics
kg_logs.api_metrics (
    timestamp TIMESTAMP,
    endpoint VARCHAR,
    method VARCHAR,
    status_code INTEGER,
    duration_ms FLOAT,
    client_id VARCHAR,
    error_message TEXT
)

-- Job Events (detailed history)
kg_logs.job_events (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR,
    timestamp TIMESTAMP,
    event_type VARCHAR,      -- 'created', 'approved', 'started', 'progress', 'completed'
    details JSONB
)

-- System Health
kg_logs.health_checks (
    timestamp TIMESTAMP,
    service VARCHAR,         -- 'api', 'postgres', 'age'
    status VARCHAR,          -- 'healthy', 'degraded', 'down'
    metrics JSONB
)
```

**Characteristics:**
- **Append-only** (never update, only insert)
- **High write volume** (every API call logged)
- **Time-series data** (partitioned by month)
- **Retention policy:**
  - Audit trail: 7 years (compliance)
  - Metrics: 90 days
  - Job events: 1 year
- **Backup priority:** Medium (important for forensics)

**Access Pattern:**
- Write: All application code (via logging middleware)
- Read: Monitoring dashboards, compliance audits
- Never: User-initiated writes

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL Instance                      │
│                                                              │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  ag_catalog   │  │   kg_api     │  │    kg_auth      │  │
│  │  (AGE Graph)  │  │ (API State)  │  │  (Security)     │  │
│  │               │  │              │  │                 │  │
│  │ • Concept     │  │ • jobs       │  │ • users         │  │
│  │ • Source      │  │ • sessions   │  │ • api_keys      │  │
│  │ • Instance    │  │ • rate_limits│  │ • permissions   │  │
│  │ • APPEARS_IN  │  │ • workers    │  │                 │  │
│  │ • EVIDENCED_BY│  │              │  │                 │  │
│  │ • IMPLIES     │  │              │  │                 │  │
│  └───────────────┘  └──────────────┘  └─────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               kg_logs (Observability)                 │  │
│  │                                                        │  │
│  │  • audit_trail     • api_metrics                      │  │
│  │  • job_events      • health_checks                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Cross-Schema Transactions:                                 │
│  BEGIN;                                                      │
│    -- Graph write (ag_catalog)                              │
│    SELECT * FROM cypher('knowledge_graph', $$...$$);        │
│    -- Job update (kg_api)                                   │
│    UPDATE kg_api.ingestion_jobs SET status='completed';     │
│    -- Audit log (kg_logs)                                   │
│    INSERT INTO kg_logs.audit_trail VALUES (...);            │
│  COMMIT;                                                     │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Schema Creation (No Code Changes)

1. Create new schemas:
   ```sql
   CREATE SCHEMA IF NOT EXISTS kg_api;
   CREATE SCHEMA IF NOT EXISTS kg_auth;
   CREATE SCHEMA IF NOT EXISTS kg_logs;
   ```

2. Move existing tables to appropriate schemas:
   ```sql
   -- Security → kg_auth
   ALTER TABLE public.users SET SCHEMA kg_auth;
   ALTER TABLE public.api_keys SET SCHEMA kg_auth;
   ALTER TABLE public.sessions SET SCHEMA kg_auth;

   -- Observability → kg_logs
   ALTER TABLE public.audit_log SET SCHEMA kg_logs;

   -- API State → kg_api (will be created new)
   -- (ingestion_jobs stays in public for now, migrate later)
   ```

3. Create new `kg_api.jobs` table with enhanced schema
4. Migrate data from `data/jobs.db` (SQLite) to `kg_api.jobs`

### Phase 2: Replace SQLite with PostgreSQL

1. Create `PostgreSQLJobQueue` class (parallel to `InMemoryJobQueue`)
2. Implement same `JobQueue` interface
3. Use connection pooling (psycopg2.pool)
4. Keep in-memory cache for active jobs (performance)
5. Query `kg_api.jobs` directly (no write-lock contention)

**Key Difference:**
```python
# Old (SQLite) - BLOCKS on concurrent writes
def list_jobs(self, status=None):
    cursor = self.db.execute("SELECT * FROM jobs WHERE ...")  # BLOCKED!
    return rows

# New (PostgreSQL) - No blocking
def list_jobs(self, status=None):
    with self.pool.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM kg_api.jobs WHERE ...")
        return rows  # Instant!
```

### Phase 3: Schema-Aware Permissions

1. Create PostgreSQL roles per schema:
   ```sql
   CREATE ROLE kg_api_reader;
   GRANT USAGE ON SCHEMA kg_api TO kg_api_reader;
   GRANT SELECT ON ALL TABLES IN SCHEMA kg_api TO kg_api_reader;

   CREATE ROLE kg_api_writer;
   GRANT kg_api_reader TO kg_api_writer;
   GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA kg_api TO kg_api_writer;

   CREATE ROLE kg_auth_manager;
   GRANT ALL ON SCHEMA kg_auth TO kg_auth_manager;

   CREATE ROLE kg_logs_writer;
   GRANT INSERT ON ALL TABLES IN SCHEMA kg_logs TO kg_logs_writer;
   ```

2. Assign application roles to connection pools:
   - API server: `kg_api_writer`, `kg_logs_writer`
   - Background workers: `kg_api_writer`, `ag_catalog` write
   - Monitoring: `kg_api_reader`, `kg_logs` reader
   - User management: `kg_auth_manager`

## Benefits

### 1. Performance
- ✅ **No write-lock contention** on job listings (PostgreSQL MVCC)
- ✅ **Instant queries** even during heavy ingestion
- ✅ **Connection pooling** for concurrent workers
- ✅ **Better indexing** than SQLite (B-tree, BRIN for time-series)

### 2. Separation of Concerns
- ✅ **Clear boundaries** between data types
- ✅ **Independent migration** of each schema
- ✅ **Different retention policies** per schema
- ✅ **Easier to understand** system architecture

### 3. Security
- ✅ **Role-based access** at schema level
- ✅ **Audit all access** to `kg_auth` schema
- ✅ **Encrypted backups** for sensitive data only
- ✅ **Compliance-ready** (GDPR, SOC2)

### 4. Operations
- ✅ **Schema-specific backups** (graph full, jobs incremental, logs archived)
- ✅ **Selective restore** (restore jobs without touching graph)
- ✅ **Table partitioning** for time-series data (`kg_logs` by month)
- ✅ **Cost optimization** (archive old logs to S3, keep graph hot)

### 5. Atomic Transactions
- ✅ **Cross-schema ACID** transactions still work
- ✅ **Consistent state** across graph, jobs, and audit logs
- ✅ **Rollback safety** (job + graph update in same transaction)

## Trade-offs

### Advantages Over Current Approach

| Aspect | Current (SQLite) | Proposed (Multi-Schema PostgreSQL) |
|--------|------------------|-------------------------------------|
| Job list query | 3-6 seconds (blocked) | <10ms (no contention) |
| Concurrent writes | Single-threaded | MVCC (unlimited) |
| Backup complexity | 2 systems (SQLite + Postgres) | 1 system, 4 logical parts |
| Schema clarity | Mixed in `public` | Clear separation |
| Access control | File permissions | PostgreSQL RBAC |
| Retention policy | Manual cleanup | Schema-specific rules |

### Disadvantages

1. **Initial migration effort** (~2-4 hours)
   - Create schemas
   - Move tables
   - Update connection strings
   - Test

2. **Slightly more complex queries** when joining across schemas:
   ```sql
   -- Need to prefix schema
   SELECT j.*, u.username
   FROM kg_api.jobs j
   JOIN kg_auth.users u ON j.user_id = u.id;
   ```

3. **More connection pools** (one per schema role)
   - But still fewer than separate databases

4. **Learning curve** for developers
   - Need to know which schema for which data
   - Mitigated by clear documentation

## Alternatives Considered

### Alternative 1: Single `public` Schema (Status Quo)

**Rejected:** Write-lock contention on job listings, unclear separation of concerns, difficult to apply different policies.

### Alternative 2: Separate PostgreSQL Databases

```
- knowledge_graph_db (graph only)
- application_db (jobs, users, logs)
```

**Rejected:**
- Cannot use atomic transactions across databases
- More connection overhead
- More backup complexity
- Loses "dual-use benefit" from ADR-016

### Alternative 3: Keep SQLite for Jobs

**Rejected:**
- Write-lock contention persists
- Two database systems to manage
- Cannot do cross-database transactions
- Already have PostgreSQL running

### Alternative 4: Use Redis for Job Queue

**Considered for Phase 2:**
- Good for distributed systems
- Better for pub/sub patterns
- But adds another system to manage
- PostgreSQL adequate for current scale

Decision: Use PostgreSQL now, consider Redis if we need true distributed queue (10+ workers).

## Success Metrics

**Performance:**
- `kg jobs list` response time: <50ms (vs 3-6s currently)
- Job update latency: <10ms (vs SQLite commit times)
- Concurrent job processing: 10+ simultaneous ingestions

**Operational:**
- Schema-specific backup strategy implemented
- Access control policies per schema
- 30-day job retention automated
- 90-day metrics retention automated

**Developer Experience:**
- Clear schema documentation
- Migration guide for existing jobs
- Updated connection pooling examples

## Open Questions

1. **Connection Pool Sizing:**
   - How many connections per schema?
   - Answer: Start with 10/schema, tune based on load

2. **Job Archival:**
   - Move old completed jobs to `kg_logs.job_events`?
   - Answer: Yes, after 30 days. Keeps `kg_api.jobs` hot.

3. **Cross-Schema Foreign Keys:**
   - Should `kg_api.jobs` reference `kg_auth.users` directly?
   - Answer: No. Use `client_id` VARCHAR to avoid tight coupling. Join at application layer.

4. **pgvector Migration:**
   - Which schema for vector indexes when we add pgvector?
   - Answer: `ag_catalog` (embeddings are graph properties)

## References

- ADR-016: Apache AGE Migration (establishes PostgreSQL as unified database)
- ADR-014: Job Approval Workflow (job queue requirements)
- PostgreSQL Multi-Schema Design: https://www.postgresql.org/docs/current/ddl-schemas.html
- PostgreSQL MVCC: https://www.postgresql.org/docs/current/mvcc-intro.html

## Decision Log

- **2025-10-10:** Proposed multi-schema architecture
- **TBD:** Review and approval
- **TBD:** Implementation start

---

**Next Steps:**
1. Review this ADR with team
2. Create schema migration scripts
3. Implement `PostgreSQLJobQueue`
4. Test concurrent write performance
5. Migrate existing jobs from SQLite
6. Update documentation
