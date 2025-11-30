# ADR-016: Apache AGE Migration (Neo4j Replacement)

**Status:** In Progress
**Date:** 2025-10-08
**Updated:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-012 (API Server), ADR-013 (Unified Client), ADR-015 (Backup/Restore)

**Implementation Progress:**
- ✅ Tasks 01-04 Complete: Infrastructure, Schema, Python Client, API Routes
- 🔄 Next: Task 05 (MCP Server), Task 07 (CLI), Task 08 (Ingestion) for functional parity
- 📍 Current branch: `feature/apache-age-migration`

## Overview

Imagine you're building a knowledge system that needs to remember who created what, who's allowed to see what, and provide detailed audit logs of all activities. This is basic table-stakes functionality for any production system. But here's the catch: our graph database (Neo4j Community Edition) doesn't support any of these features unless we pay $180,000 per year for the Enterprise license.

We faced a fundamental architectural dilemma. We needed two separate databases: Neo4j for the graph data (concepts and their relationships), and another database (like PostgreSQL) for everything else—user accounts, security permissions, API keys, job queues, and audit logs. This dual-database setup created its own problems: we couldn't perform atomic operations across both systems, backups became twice as complex, and we had to manage two completely different connection systems.

The solution? Apache AGE, a PostgreSQL extension that brings graph database capabilities directly into PostgreSQL. Think of it as getting the best of both worlds: we keep our graph query language (Cypher) for exploring concept relationships, but now everything lives in a single, production-grade database that includes enterprise-level security features for free. Instead of juggling two databases, we get one unified system where a graph query and a user authentication check can happen in the same transaction.

This migration preserves our existing graph model and query patterns while unlocking critical production capabilities like multi-user access control, comprehensive audit logging, and dramatically simpler backup procedures. It's not just a database swap—it's an architectural consolidation that makes the entire system simpler, more secure, and ready for real-world deployment.

---

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

Apache AGE adds graph database capabilities to PostgreSQL using **openCypher** query language:
- openCypher is an open-source variant of Cypher, the declarative graph query language
- openCypher is the foundation for **ISO/IEC 39075:2024 GQL (Graph Query Language)** standard
- ~90% compatibility with Neo4j's proprietary Cypher implementation
- Graph data stored as PostgreSQL extension
- Full access to PostgreSQL's mature RBAC system
- Can mix openCypher graph queries with relational SQL

**Note:** Syntax differences between AGE and Neo4j stem from AGE implementing openCypher rather than Neo4j's proprietary Cypher extensions. See "Cypher Compatibility" section below for specific differences.

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

### openCypher Compatibility

Apache AGE implements **openCypher**, the open-source graph query language standard that serves as the foundation for **ISO/IEC 39075:2024 GQL (Graph Query Language)**.

**Key Distinction:**
- **openCypher:** Open-source specification maintained by the openCypher project
- **Neo4j Cypher:** Proprietary implementation with Neo4j-specific extensions
- **GQL Standard:** ISO/IEC standardized graph query language based on openCypher

AGE supports most openCypher constructs but differs from Neo4j's proprietary extensions:

**Supported (openCypher standard):**
- MATCH, CREATE, MERGE, DELETE
- WHERE, RETURN, ORDER BY, LIMIT
- Relationship patterns
- Property access
- Aggregation functions

**Not Supported (Neo4j-specific extensions):**
- `ON CREATE SET` / `ON MATCH SET` in MERGE (Neo4j proprietary)
- Some advanced path algorithms
- Certain built-in functions (may need PostgreSQL equivalents)
- APOC procedures (Neo4j-specific library)

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

### pgvector Adoption for Embeddings Management

**Why pgvector:**

pgvector is a PostgreSQL extension purpose-built for vector similarity search, providing the foundation for our semantic concept search capabilities.

**Key Advantages:**
1. **Native PostgreSQL Integration:** No external vector database needed
2. **ACID Transactions:** Vector operations within PostgreSQL transactions
3. **Multiple Distance Metrics:** Cosine, L2 (Euclidean), Inner Product
4. **Approximate Nearest Neighbor (ANN):** IVFFlat and HNSW indexes for fast search
5. **Hybrid Queries:** Mix vector search with graph traversal in single query
6. **Mature & Production-Ready:** Used by companies like Supabase, Neon

**Installation & Setup:**

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**Embedding Storage Strategy:**

AGE stores concept properties as JSONB, embeddings are stored as JSONB arrays and cast to vector type for similarity operations:

```sql
-- Concept vertex with embedding (AGE)
SELECT * FROM cypher('knowledge_graph', $$
    CREATE (c:Concept {
        concept_id: 'linear-thinking',
        label: 'Linear Thinking Pattern',
        embedding: [0.123, -0.456, 0.789, ...]  -- Stored as JSONB array
    })
$$) as (result agtype);

-- Extract and index embeddings (PostgreSQL + pgvector)
CREATE INDEX concept_embedding_idx
ON ag_catalog.concept
USING ivfflat ((properties->>'embedding')::vector(1536) vector_cosine_ops)
WITH (lists = 100);
```

**Vector Search Implementation:**

```python
# src/api/lib/age_client.py
def vector_search(
    self,
    embedding: List[float],
    top_k: int = 10,
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Semantic search using pgvector cosine similarity.

    Args:
        embedding: Query embedding vector (1536 dims for OpenAI)
        top_k: Number of results to return
        threshold: Minimum similarity score (0.0-1.0)

    Returns:
        List of concepts with similarity scores
    """
    # Convert embedding to PostgreSQL vector literal
    vector_str = '[' + ','.join(map(str, embedding)) + ']'

    # pgvector uses <-> for cosine distance (lower is more similar)
    # Convert to similarity: 1 - distance
    query = """
        SELECT
            properties->>'concept_id' as concept_id,
            properties->>'label' as label,
            1 - ((properties->>'embedding')::vector <-> %s::vector) as similarity
        FROM ag_catalog.concept
        WHERE 1 - ((properties->>'embedding')::vector <-> %s::vector) >= %s
        ORDER BY (properties->>'embedding')::vector <-> %s::vector
        LIMIT %s
    """

    results = self._execute_sql(
        query,
        (vector_str, vector_str, threshold, vector_str, top_k)
    )

    return [
        {
            'concept_id': row['concept_id'],
            'label': row['label'],
            'similarity': float(row['similarity'])
        }
        for row in results
    ]
```

**Index Types and Performance:**

pgvector provides two index types for approximate nearest neighbor (ANN) search:

**1. IVFFlat (Inverted File Flat):**
- Best for: Medium-sized datasets (10K-1M vectors)
- Faster index build time
- Lower memory usage
- Good recall/performance balance

```sql
-- IVFFlat index (current implementation)
CREATE INDEX concept_embedding_ivf
ON ag_catalog.concept
USING ivfflat ((properties->>'embedding')::vector(1536) vector_cosine_ops)
WITH (lists = 100);

-- Tuning parameter: lists
-- - Rule of thumb: lists = rows / 1000 (between 10-10000)
-- - 10K concepts: lists = 10
-- - 100K concepts: lists = 100
-- - 1M concepts: lists = 1000
```

**2. HNSW (Hierarchical Navigable Small World):**
- Best for: Large datasets (>1M vectors)
- Slower index build, but faster queries
- Higher memory usage
- Better recall than IVFFlat

```sql
-- HNSW index (recommended for production at scale)
CREATE INDEX concept_embedding_hnsw
ON ag_catalog.concept
USING hnsw ((properties->>'embedding')::vector(1536) vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Tuning parameters:
-- - m: Number of connections per layer (default 16)
--   Higher = better recall but slower build and more memory
-- - ef_construction: Size of dynamic candidate list (default 64)
--   Higher = better recall but slower index build
```

**Distance Metrics:**

pgvector supports three distance operators:

```sql
-- Cosine distance: <-> (RECOMMENDED for normalized embeddings)
-- Range: 0 (identical) to 2 (opposite)
-- Convert to similarity: 1 - distance
SELECT 1 - (embedding <-> query::vector) as cosine_similarity;

-- L2 (Euclidean) distance: <->
-- Range: 0 (identical) to ∞
SELECT embedding <-> query::vector as l2_distance;

-- Inner product (negative): <#>
-- Range: -∞ to 0
-- For normalized vectors, equivalent to cosine similarity
SELECT -(embedding <#> query::vector) as inner_product;
```

**For OpenAI embeddings (normalized), use cosine distance (`<->`) with `vector_cosine_ops` index.**

**Hybrid Queries (Vector + Graph):**

Combine pgvector similarity search with AGE graph traversal:

```sql
-- Find similar concepts and traverse relationships
WITH similar_concepts AS (
    SELECT
        properties->>'concept_id' as concept_id,
        1 - ((properties->>'embedding')::vector <-> %s::vector) as similarity
    FROM ag_catalog.concept
    ORDER BY (properties->>'embedding')::vector <-> %s::vector
    LIMIT 10
)
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (c:Concept)-[r]->(related:Concept)
    WHERE c.concept_id IN $similar_ids
    RETURN c.concept_id, c.label, type(r), related.label
$$) as (concept_id agtype, label agtype, rel_type agtype, related_label agtype);
```

**Performance Benchmarks:**

Expected performance characteristics (based on pgvector documentation):

| Dataset Size | Index Type | Build Time | Query Time (k=10) | Recall@10 |
|--------------|-----------|------------|-------------------|-----------|
| 10K vectors  | IVFFlat   | ~1s        | ~10ms             | 95%       |
| 100K vectors | IVFFlat   | ~10s       | ~20ms             | 93%       |
| 1M vectors   | IVFFlat   | ~100s      | ~50ms             | 90%       |
| 1M vectors   | HNSW      | ~300s      | ~10ms             | 98%       |
| 10M vectors  | HNSW      | ~3000s     | ~15ms             | 97%       |

**Memory Requirements:**

```
IVFFlat: ~4 bytes per dimension × dataset size
HNSW: ~4 bytes per dimension × dataset size × (m + 1)

For 1536-dimensional embeddings (OpenAI):
- 100K concepts with IVFFlat: ~600 MB
- 100K concepts with HNSW (m=16): ~10 GB
```

**Monitoring and Maintenance:**

```sql
-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE indexname LIKE '%embedding%';

-- Rebuild index after bulk inserts
REINDEX INDEX CONCURRENTLY concept_embedding_idx;

-- Analyze table for query planner
ANALYZE ag_catalog.concept;

-- Monitor query performance
EXPLAIN ANALYZE
SELECT properties->>'concept_id'
FROM ag_catalog.concept
ORDER BY (properties->>'embedding')::vector <-> '[...]'::vector
LIMIT 10;
```

**Migration Path:**

**Phase 1 (Current - IVFFlat):**
- Use IVFFlat for development and initial production
- Simple setup, good enough for <100K concepts
- Tune `lists` parameter based on dataset growth

**Phase 2 (Production Scale - HNSW):**
- Switch to HNSW when dataset exceeds 500K concepts
- Monitor query latency and recall metrics
- Tune `m` and `ef_construction` for optimal performance

**Future Optimization:**

```sql
-- Pre-filter with graph constraints THEN vector search
-- More efficient than vector search over entire corpus
SELECT * FROM cypher('knowledge_graph', $$
    MATCH (c:Concept)-[:APPEARS_IN]->(s:Source)
    WHERE s.ontology = 'philosophy'
    RETURN c
$$) as concept_subgraph
JOIN LATERAL (
    SELECT
        1 - ((properties->>'embedding')::vector <-> %s::vector) as similarity
    FROM ag_catalog.concept
    WHERE id = concept_subgraph.id
    ORDER BY similarity DESC
    LIMIT 10
) vector_results ON true;
```

**References:**
- pgvector Documentation: https://github.com/pgvector/pgvector
- Performance Tuning Guide: https://github.com/pgvector/pgvector#performance
- HNSW Paper: https://arxiv.org/abs/1603.09320
- IVFFlat Algorithm: https://hal.inria.fr/inria-00514462/document
