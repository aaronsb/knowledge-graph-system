# ADR-016: Apache AGE Migration (Neo4j Replacement)

**Status:** Proposed
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-012 (API Server), ADR-013 (Unified Client), ADR-015 (Backup/Restore)

## Context

The current Neo4j Community Edition implementation has critical production blockers:

**Licensing Issues:**
1. **No RBAC in Community Edition:** Role-Based Access Control requires Neo4j Enterprise
2. **Enterprise cost:** ~$180,000/year licensing fee (not viable for open-source project)
3. **Community limitations:** Single-user mode, no security features, no audit logging

**Architectural Concerns:**
1. **Dual database complexity:** Neo4j for graph + separate DB needed for:
   - User management and authentication
   - API keys and sessions
   - Job queue (ingestion, restore)
   - Audit logs
   - Document storage
2. **Backup complexity:** Two systems to backup/restore (Neo4j + application DB)
3. **Connection overhead:** Managing multiple connection pools and auth systems
4. **Transaction scope:** Cannot do atomic operations across graph and application state

**Production Requirements:**
- Multi-user access with role-based permissions (read-only users, admin users)
- Audit logging (who modified what, when)
- Secure credential management
- Production-grade security model

## Decision

**Migrate from Neo4j Community Edition to Apache AGE (A Graph Extension for PostgreSQL)**

### What is Apache AGE?

Apache AGE adds graph database capabilities to PostgreSQL using Cypher query language:
- ~90% Cypher compatibility with Neo4j
- Graph data stored as PostgreSQL extension
- Full access to PostgreSQL's mature RBAC system
- Can mix graph queries with relational SQL

### Unified Architecture

```
                    PostgreSQL + AGE
                ┌─────────────────────────┐
                │                         │
                │  Graph Data (AGE)       │
                │  - Concepts (vertices)  │
                │  - Relationships (edges)│
                │  - Vector embeddings    │
                │                         │
                │  Application Tables     │
                │  - users                │
                │  - api_keys             │
                │  - sessions             │
                │  - ingestion_jobs       │
                │  - restore_jobs         │
                │  - audit_log            │
                │  - documents            │
                │                         │
                │  Extensions             │
                │  - AGE (graph)          │
                │  - pgvector (embeddings)│
                │                         │
                └─────────────────────────┘
                          │
                   Single Connection
                   Single Backup
                   Single RBAC System
```

### Key Benefits

1. **RBAC Built-In:**
   ```sql
   -- Create roles with different permissions
   CREATE ROLE read_only;
   GRANT SELECT ON ALL TABLES IN SCHEMA ag_catalog TO read_only;
   GRANT USAGE ON SCHEMA ag_catalog TO read_only;

   CREATE ROLE admin;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ag_catalog TO admin;
   ```

2. **Unified Storage:**
   - Graph data: AGE vertices and edges
   - Application state: Standard PostgreSQL tables
   - Documents: TEXT or BYTEA columns
   - Job queue: PostgreSQL tables (remove Redis/external queue)
   - Audit logs: PostgreSQL tables with row-level security

3. **Atomic Transactions:**
   ```sql
   BEGIN;
   -- Create concept (AGE graph)
   SELECT * FROM cypher('knowledge_graph', $$
       CREATE (c:Concept {label: 'New Concept'})
   $$) as (v agtype);

   -- Log audit entry (PostgreSQL table)
   INSERT INTO audit_log (user_id, action, timestamp)
   VALUES (123, 'concept_created', NOW());

   COMMIT;
   ```

4. **Simplified Backup:**
   ```bash
   # Single command backs up everything
   pg_dump knowledge_graph > backup.sql

   # Or with compression
   pg_dump knowledge_graph | gzip > backup.sql.gz
   ```

5. **Cypher Preservation:**
   ```sql
   -- Existing Neo4j query
   MATCH (c:Concept)-[r:RELATES_TO]->(c2:Concept)
   WHERE c.label = 'Linear Thinking'
   RETURN c2.label

   -- AGE equivalent (wrapped in SELECT)
   SELECT * FROM cypher('knowledge_graph', $$
       MATCH (c:Concept)-[r:RELATES_TO]->(c2:Concept)
       WHERE c.label = 'Linear Thinking'
       RETURN c2.label
   $$) as (label agtype);
   ```

## Implementation

### Phase 1: Infrastructure Setup (Week 1)

**Docker Compose Changes:**
```yaml
# docker-compose.yml
services:
  postgres:
    image: apache/age:PG16_latest
    environment:
      POSTGRES_DB: knowledge_graph
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ./schema/init_age.sql:/docker-entrypoint-initdb.d/01_init.sql
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

**Enable Extensions:**
```sql
-- schema/init_age.sql
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS pgvector;

-- Load AGE into search path
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create graph
SELECT create_graph('knowledge_graph');
```

### Phase 2: Schema Migration (Week 1-2)

**Graph Schema (AGE):**
```sql
-- schema/graph_schema.sql
-- Concept vertices
SELECT * FROM cypher('knowledge_graph', $$
    CREATE VLABEL Concept
$$) as (a agtype);

-- Source vertices
SELECT * FROM cypher('knowledge_graph', $$
    CREATE VLABEL Source
$$) as (a agtype);

-- Instance vertices
SELECT * FROM cypher('knowledge_graph', $$
    CREATE VLABEL Instance
$$) as (a agtype);

-- Relationship types
SELECT * FROM cypher('knowledge_graph', $$
    CREATE ELABEL APPEARS_IN
$$) as (a agtype);

SELECT * FROM cypher('knowledge_graph', $$
    CREATE ELABEL EVIDENCED_BY
$$) as (a agtype);

-- Add vector index for embeddings
CREATE INDEX concept_embedding_idx ON ag_catalog.concept
USING ivfflat (properties->'embedding' vector_cosine_ops)
WITH (lists = 100);
```

**Application Schema (PostgreSQL):**
```sql
-- schema/app_schema.sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'read_only',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP
);

CREATE TABLE ingestion_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    progress JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by INTEGER REFERENCES users(id)
);
```

### Phase 3: Python Client Rewrite (Week 2-3)

**Replace neo4j-driver with psycopg2:**
```python
# src/database/age_client.py
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from typing import List, Dict, Any

class AGEClient:
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        self._setup_age()

    def _setup_age(self):
        """Load AGE extension and set search path"""
        with self.conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, '$user', public;")
        self.conn.commit()

    def execute_cypher(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        """Execute Cypher query via AGE"""
        # AGE requires wrapping Cypher in SELECT
        age_query = f"SELECT * FROM cypher('knowledge_graph', $$ {query} $$) as (result agtype);"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(age_query, params or {})
            return [dict(row) for row in cur.fetchall()]

    def create_concept(self, concept_id: str, label: str, embedding: List[float]) -> Dict:
        """Create concept vertex"""
        query = """
            CREATE (c:Concept {
                concept_id: $concept_id,
                label: $label,
                embedding: $embedding
            })
            RETURN c
        """
        return self.execute_cypher(query, {
            'concept_id': concept_id,
            'label': label,
            'embedding': embedding
        })[0]

    def vector_search(self, embedding: List[float], limit: int = 10) -> List[Dict]:
        """Vector similarity search using pgvector"""
        query = """
            SELECT concept_id, label,
                   properties->>'embedding' <-> %s::vector AS distance
            FROM ag_catalog.concept
            ORDER BY distance
            LIMIT %s
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (embedding, limit))
            return [dict(row) for row in cur.fetchall()]

    def close(self):
        self.conn.close()
```

**Migration from Neo4jClient:**
```python
# Before (Neo4j)
from neo4j import GraphDatabase
driver = GraphDatabase.driver(uri, auth=(user, password))
result = driver.execute_query("MATCH (c:Concept) RETURN c")

# After (AGE)
from database.age_client import AGEClient
client = AGEClient(host, port, database, user, password)
result = client.execute_cypher("MATCH (c:Concept) RETURN c")
```

### Phase 4: MCP Server Rewrite (Week 3)

**Replace neo4j-driver with pg:**
```typescript
// mcp-server/src/age-client.ts
import { Client } from 'pg';

export class AGEClient {
  private client: Client;

  constructor(config: {
    host: string;
    port: number;
    database: string;
    user: string;
    password: string;
  }) {
    this.client = new Client(config);
  }

  async connect(): Promise<void> {
    await this.client.connect();
    await this.client.query("LOAD 'age';");
    await this.client.query("SET search_path = ag_catalog, '$user', public;");
  }

  async executeCypher(query: string, params?: any): Promise<any[]> {
    const ageQuery = `
      SELECT * FROM cypher('knowledge_graph', $1) as (result agtype);
    `;
    const result = await this.client.query(ageQuery, [query]);
    return result.rows.map(row => row.result);
  }

  async searchConcepts(queryText: string, limit: number = 10): Promise<any[]> {
    const query = `
      MATCH (c:Concept)
      WHERE c.label =~ '(?i).*${queryText}.*'
      RETURN c
      LIMIT ${limit}
    `;
    return this.executeCypher(query);
  }

  async close(): Promise<void> {
    await this.client.end();
  }
}
```

### Phase 5: Vector Search Migration (Week 4)

**pgvector Integration:**
```python
# src/database/vector_search.py
def vector_search(client: AGEClient, embedding: List[float], limit: int = 10) -> List[Dict]:
    """
    Use pgvector for similarity search.
    AGE stores properties as JSONB, pgvector handles vector ops.
    """
    query = """
        SELECT
            c.properties->>'concept_id' as concept_id,
            c.properties->>'label' as label,
            (c.properties->>'embedding')::vector <-> %s::vector AS distance
        FROM ag_catalog.concept c
        ORDER BY distance
        LIMIT %s
    """
    with client.conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Convert embedding to PostgreSQL vector format
        vector_str = '[' + ','.join(map(str, embedding)) + ']'
        cur.execute(query, (vector_str, limit))
        return [dict(row) for row in cur.fetchall()]
```

**Index Creation:**
```sql
-- Create IVF index for fast approximate nearest neighbor search
CREATE INDEX concept_embedding_idx
ON ag_catalog.concept
USING ivfflat ((properties->>'embedding')::vector vector_cosine_ops)
WITH (lists = 100);
```

### Phase 6: CLI Updates (Week 4)

**Connection String Changes:**
```typescript
// client/src/config/index.ts
export interface Config {
  database: {
    type: 'postgresql';  // Changed from 'neo4j'
    host: string;
    port: number;
    database: string;
    user: string;
    password: string;
  };
  // ... rest of config
}

// Default config
const DEFAULT_CONFIG: Config = {
  database: {
    type: 'postgresql',
    host: 'localhost',
    port: 5432,
    database: 'knowledge_graph',
    user: 'admin',
    password: process.env.DB_PASSWORD || 'password'
  }
};
```

### Phase 7: Documentation Updates (Week 5)

**Update All References:**
- README.md: Replace Neo4j with PostgreSQL + AGE
- QUICKSTART.md: Update setup instructions
- ARCHITECTURE.md: Document unified database architecture
- AI_PROVIDERS.md: No changes (abstracted from database)
- docs/BACKUP_RESTORE.md: Simplify to pg_dump

## Consequences

### Positive

1. **RBAC Unlocked:**
   - Production-ready multi-user access control
   - Row-level security policies
   - Granular permissions (read, write, admin)
   - Audit logging built-in

2. **Unified Architecture:**
   - Single database connection pool
   - Single backup/restore mechanism (pg_dump)
   - Atomic transactions across graph + application state
   - No data synchronization between systems

3. **Operational Simplicity:**
   - One database to monitor, tune, backup
   - Standard PostgreSQL tooling (pgAdmin, psql)
   - No license costs or compliance tracking
   - Mature ecosystem and documentation

4. **Cost Savings:**
   - Free and open source (Apache 2.0 license)
   - No enterprise licensing fees
   - Lower infrastructure costs (one DB vs two)

5. **Data Integrity:**
   - Foreign key constraints across graph and relational data
   - ACID transactions guarantee consistency
   - Referential integrity enforced by PostgreSQL

6. **Scalability:**
   - PostgreSQL handles billions of rows
   - Proven production reliability
   - Horizontal scaling via Citus extension (if needed)

### Negative

1. **Migration Effort:**
   - Complete rewrite of database client (~3 weeks)
   - MCP server rewrite (~1 week)
   - Schema migration scripts required
   - No backward compatibility

2. **Cypher Differences:**
   - ~10% syntax differences from Neo4j
   - Must wrap queries in SELECT statements
   - AGE-specific quirks and limitations
   - Less mature than Neo4j (newer project)

3. **Performance Unknowns:**
   - AGE performance vs Neo4j for deep graph traversals
   - Vector search performance with pgvector vs Neo4j vector index
   - Need benchmarking and optimization

4. **Learning Curve:**
   - Team must learn AGE specifics
   - Debugging AGE issues vs Neo4j
   - Less community support than Neo4j

5. **Tooling:**
   - No graph visualization like Neo4j Browser
   - Need custom tools or third-party solutions
   - Less polished developer experience

### Neutral

1. **Graph Model:**
   - Same concepts, relationships, properties
   - Cypher queries mostly portable
   - Semantic model unchanged

2. **Vector Embeddings:**
   - pgvector provides similar functionality
   - Different index tuning parameters
   - May need performance optimization

## Alternatives Considered

### 1. Neo4j Enterprise Edition

**Rejected:** $180,000/year licensing cost not viable for open-source project

**Pros:**
- Best-in-class graph database
- Mature RBAC implementation
- Excellent tooling and documentation

**Cons:**
- Prohibitive cost
- License compliance overhead
- Still requires separate application database

### 2. Plain PostgreSQL (No Graph Extension)

**Rejected:** Lose Cypher queries, complex graph traversal logic

**Pros:**
- No additional extensions needed
- Maximum performance for relational queries

**Cons:**
- Recursive CTEs for graph queries are complex
- No Cypher language support
- Complete query rewrite required
- Loss of graph-oriented thinking

### 3. ArangoDB

**Rejected:** Different query language (AQL), complete rewrite required

**Pros:**
- Multi-model database (graph, document, key-value)
- Good performance
- Active development

**Cons:**
- AQL is not Cypher (no query portability)
- Another database system to learn
- Less mature RBAC than PostgreSQL
- Still requires separate application database

### 4. Keep Neo4j Community + Add PostgreSQL

**Rejected:** Dual database complexity, no atomic transactions, backup complexity

**Pros:**
- No migration needed
- Keep existing Neo4j knowledge

**Cons:**
- Still no RBAC for graph data
- Two databases to manage
- Cannot do atomic operations across systems
- Backup/restore complexity

### 5. Neo4j Community + Custom RBAC Layer

**Rejected:** Circumvents Neo4j architecture, fragile, unsupported

**Pros:**
- Keep Neo4j for graph operations
- Custom permission logic

**Cons:**
- Not using Neo4j's intended security model
- Fragile permission enforcement
- Complex to maintain
- No audit trail at database level

## Migration Strategy

### No Backward Compatibility

This is a **clean break migration** with no backward compatibility:
- Feature branch: `feature/apache-age-migration`
- Complete replacement of Neo4j with AGE
- Breaking change for all existing deployments
- Requires data migration script

### Data Migration Script

```python
# scripts/migrate_neo4j_to_age.py
"""
Export Neo4j data and import to Apache AGE.

Steps:
1. Export Neo4j concepts, sources, instances, relationships
2. Transform to AGE-compatible format
3. Import using AGE Python client
4. Verify data integrity
"""

def export_from_neo4j():
    # Use neo4j-driver to export all nodes and relationships
    pass

def import_to_age():
    # Use AGEClient to import data
    pass

def verify_migration():
    # Compare counts and sample queries
    pass
```

### Release Plan

**v0.3.0 - Apache AGE Migration (Target: Q4 2025)**
- Complete migration to PostgreSQL + AGE
- Unified database architecture
- RBAC implementation
- Breaking change: requires data migration
- Documentation updates

**Migration Guide for Users:**
```bash
# Export existing Neo4j data
./scripts/export-neo4j.sh > neo4j_backup.json

# Stop old system
docker-compose down

# Update to v0.3.0
git pull origin main

# Start new PostgreSQL + AGE system
docker-compose up -d

# Import data
./scripts/migrate-neo4j-to-age.py neo4j_backup.json

# Verify
kg database stats
```

## References

- **Apache AGE Documentation:** https://age.apache.org/
- **pgvector Extension:** https://github.com/pgvector/pgvector
- **PostgreSQL RBAC:** https://www.postgresql.org/docs/current/user-manag.html
- **ADR-012:** API Server Architecture (job queue, authentication)
- **ADR-013:** Unified TypeScript Client (configuration)
- **ADR-015:** Backup/Restore Streaming (simplified with pg_dump)

## Notes

### Cypher Compatibility

AGE supports most Cypher constructs but has some differences:

**Supported:**
- MATCH, CREATE, MERGE, DELETE
- WHERE, RETURN, ORDER BY, LIMIT
- Relationship patterns
- Property access
- Aggregation functions

**Not Supported (as of 2025):**
- Some advanced path algorithms
- Certain built-in functions (may need PostgreSQL equivalents)
- APOC procedures (Neo4j-specific)

**Workarounds:**
- Use PostgreSQL functions for missing Cypher features
- Mix Cypher with SQL for complex operations
- Create custom PostgreSQL functions for repeated patterns

### Performance Tuning

**PostgreSQL Settings for Graph Workloads:**
```sql
-- Increase shared buffers for graph data
shared_buffers = 4GB

-- Increase work memory for complex queries
work_mem = 256MB

-- Enable parallel query execution
max_parallel_workers_per_gather = 4

-- Optimize for SSD storage
random_page_cost = 1.1
```

**AGE-Specific Indexes:**
```sql
-- Index vertex labels
CREATE INDEX ON ag_catalog.concept USING gin (properties jsonb_path_ops);

-- Index relationship types
CREATE INDEX ON ag_catalog.appears_in (start_id, end_id);

-- Vector index for embeddings
CREATE INDEX ON ag_catalog.concept
USING ivfflat ((properties->>'embedding')::vector vector_cosine_ops);
```

### RBAC Implementation Example

```sql
-- Create roles
CREATE ROLE kg_read_only;
CREATE ROLE kg_contributor;
CREATE ROLE kg_admin;

-- Grant read access
GRANT CONNECT ON DATABASE knowledge_graph TO kg_read_only;
GRANT USAGE ON SCHEMA ag_catalog TO kg_read_only;
GRANT SELECT ON ALL TABLES IN SCHEMA ag_catalog TO kg_read_only;

-- Grant write access (contributor)
GRANT kg_read_only TO kg_contributor;
GRANT INSERT, UPDATE ON ag_catalog.concept TO kg_contributor;
GRANT INSERT, UPDATE ON ag_catalog.source TO kg_contributor;

-- Grant full access (admin)
GRANT ALL PRIVILEGES ON DATABASE knowledge_graph TO kg_admin;

-- Create user with role
CREATE USER alice WITH PASSWORD 'secure_password';
GRANT kg_contributor TO alice;

-- Row-level security example
CREATE POLICY user_data_policy ON audit_log
    USING (user_id = current_user_id());

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
```

### Backup/Restore Simplification

**Before (Neo4j + separate app DB):**
```bash
# Backup Neo4j
neo4j-admin dump --to=neo4j_backup.dump

# Backup application DB (hypothetical)
mysqldump app_db > app_backup.sql

# Two separate backups to manage
```

**After (PostgreSQL + AGE unified):**
```bash
# Single backup command
pg_dump knowledge_graph | gzip > backup_$(date +%Y%m%d).sql.gz

# Or with parallel processing
pg_dump -Fd knowledge_graph -j 4 -f backup_dir/

# Restore
gunzip -c backup_20251008.sql.gz | psql knowledge_graph
```

This unification directly impacts ADR-015 (Backup/Restore Streaming) by eliminating the need for custom backup logic - standard PostgreSQL tools handle everything.
