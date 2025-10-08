# Apache AGE Migration Tasks

**Status:** In Progress
**Branch:** `feature/apache-age-migration`
**Related:** ADR-016, ADR-015, ADR-012, ADR-013
**Started:** 2025-10-08

## Overview

Complete migration from Neo4j Community Edition to Apache AGE (PostgreSQL graph extension) to unlock production RBAC capabilities and unify graph + application data storage.

**No backward compatibility** - clean break migration.

---

## Task 01: Documentation & Planning [ADR-016]

**Status:** ✅ Complete
**Complexity:** Low

### Sub-tasks:
- [✔] Draft ADR-016 for Apache AGE migration decision
- [✔] Review and accept ADR-016
- [✔] Commit ADR-016 to main branch
- [✔] Create feature/apache-age-migration branch
- [✔] Create persistent tasks.md for migration tracking

---

## Task 02: Infrastructure Setup

**Status:** ✅ Complete
**Complexity:** Medium
**Dependencies:** Task 01 complete

### Sub-tasks:
- [✔] Update docker-compose.yml to use apache/age image
- [✔] Create schema/init_age.sql for extension setup
- [✔] Configure PostgreSQL environment variables in .env.example
- [✔] Remove Neo4j service from docker-compose.yml
- [✔] Update volume mounts (postgres_data instead of neo4j_data)
- [✔] Test Docker Compose startup with AGE image
- [✔] Verify AGE extension loads correctly
- [✔] Update .gitignore for PostgreSQL data directory

**Acceptance Criteria:**
- ✅ `docker-compose up -d` starts PostgreSQL with AGE extension
- ✅ Can connect with `psql` and query `SELECT * FROM ag_catalog.ag_graph;`
- ✅ AGE verified: Created test concept and queried successfully
- ✅ Application tables created (users, api_keys, jobs, etc.)
- ✅ RBAC roles created (kg_read_only, kg_contributor, kg_admin)

**Notes:**
- pgvector not included in base apache/age image - using JSONB for embeddings
- Vertex/edge labels created automatically on first use (no explicit DDL needed)
- Graph indexes will be added after initial data load

---

## Task 03: Schema Migration

**Status:** ✅ Complete (Done via init_age.sql in Task 02)
**Complexity:** High
**Dependencies:** Task 02 complete

### Sub-tasks:

#### Graph Schema (AGE)
- [ ] Create schema/graph_schema.sql with vertex labels (Concept, Source, Instance)
- [ ] Create edge labels (APPEARS_IN, EVIDENCED_BY, FROM_SOURCE, RELATES_TO, etc.)
- [ ] Create vector index for concept embeddings using pgvector
- [ ] Create property indexes for common queries (label, concept_id, source_id)
- [ ] Test graph creation: `SELECT create_graph('knowledge_graph');`

#### Application Schema (PostgreSQL)
- [ ] Create schema/app_schema.sql with users table
- [ ] Create api_keys table with foreign key to users
- [ ] Create sessions table for authentication
- [ ] Create ingestion_jobs table with status tracking
- [ ] Create restore_jobs table (ADR-015 compatibility)
- [ ] Create audit_log table with row-level security policies
- [ ] Create documents table for source text storage
- [ ] Create backups metadata table

#### RBAC Setup
- [ ] Create roles: kg_read_only, kg_contributor, kg_admin
- [ ] Define GRANT statements for each role
- [ ] Create row-level security policies for audit_log
- [ ] Document RBAC model in docs/RBAC.md

**Acceptance Criteria:**
- All schema files execute without errors
- Graph created: `SELECT * FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph';`
- All tables exist: `\dt` shows users, api_keys, jobs, audit_log, documents
- Roles created: `\du` shows kg_read_only, kg_contributor, kg_admin

---

## Task 04: Python Client Rewrite

**Status:** ✅ Complete
**Complexity:** High
**Dependencies:** Task 03 complete

### Sub-tasks:

#### Core Client
- [✔] Create src/api/lib/age_client.py (replaces neo4j_client.py)
- [✔] Implement AGEClient.__init__ with psycopg2 connection pool
- [✔] Implement _setup_age() to load extension and set search_path
- [✔] Implement _execute_cypher() method with AGE SELECT wrapping
- [✔] Implement _extract_column_spec() for preserving column names
- [✔] Implement create_concept_node() method
- [✔] Implement create_source_node() method
- [✔] Implement create_instance_node() method
- [✔] Implement create_concept_relationship() method
- [✔] Implement all 14 methods from Neo4jClient
- [✔] Implement _parse_agtype() for result parsing

#### Vector Search
- [✔] Implement vector_search() using Python numpy (full scan)
- [✔] Implement get_document_concepts() method
- [✔] Implement validate_learned_connection() method
- [ ] Add pgvector support for performance (deferred to Task 06)

#### Query Migration
- [✔] Convert all methods to AGE format (wrap in SELECT)
- [✔] Handle agtype casting for returned values
- [✔] Update imports in src/api/routes/*.py (6 files)
- [✔] Update imports in src/api/workers/*.py
- [✔] Update imports in scripts/graph_to_mermaid.py
- [✔] Update query_service.py to remove Neo4j Session import
- [✔] Test all endpoint functionality

#### Package Dependencies
- [✔] Update requirements.txt: neo4j → psycopg2-binary
- [✔] Update scripts/start-api.sh: check PostgreSQL
- [✔] Install dependencies: pip install psycopg2-binary
- [ ] Update ingest/neo4j_client.py imports → age_client.py (legacy, not used)
- [ ] Update CLI to use AGEClient (deferred to Task 07)

**Acceptance Criteria:**
- ✅ AGEClient can connect to PostgreSQL
- ✅ API server starts without errors
- ✅ Database stats endpoint returns correct counts
- ✅ Ontology list endpoint works
- ✅ Database info endpoint shows PostgreSQL version
- ✅ All 11 API endpoints refactored and tested
- ✅ Column names preserved in query results
- ✅ AGE ORDER BY restrictions handled

**Notes:**
- Completed intelligent column extraction from Cypher RETURN clauses
- Fixed agtype parsing to return proper dicts with column names
- Handled PostgreSQL reserved keywords (count → node_count, etc.)
- All tested endpoints returning 200 status codes
- Vector search uses Python numpy without pgvector (acceptable for now)

---

## Task 05: MCP Server Rewrite

**Status:** Pending
**Complexity:** High
**Dependencies:** Task 04 complete

### Sub-tasks:

#### TypeScript Client
- [ ] Create mcp-server/src/age-client.ts (replace neo4j.ts)
- [ ] Install pg package: `npm install pg @types/pg`
- [ ] Remove neo4j-driver: `npm uninstall neo4j-driver`
- [ ] Implement AGEClient class with Client from pg
- [ ] Implement connect() method with AGE setup
- [ ] Implement executeCypher() method with SELECT wrapping
- [ ] Implement searchConcepts() tool handler
- [ ] Implement getConceptDetails() tool handler
- [ ] Implement findRelatedConcepts() tool handler
- [ ] Implement listOntologies() tool handler
- [ ] Implement getDatabaseStats() tool handler
- [ ] Implement findShortestPath() tool handler

#### MCP Tools Update
- [ ] Update mcp-server/src/index.ts imports
- [ ] Update tool implementations to use AGEClient
- [ ] Handle agtype JSON parsing in TypeScript
- [ ] Update error handling for pg vs neo4j-driver
- [ ] Test all MCP tools through Claude Desktop

#### Build & Deploy
- [ ] Update mcp-server/package.json dependencies
- [ ] Run `npm install` and verify no errors
- [ ] Run `npm run build` and verify build succeeds
- [ ] Test MCP server standalone: `node build/index.js`
- [ ] Update Claude Desktop config with new connection details

**Acceptance Criteria:**
- MCP server builds without errors
- All tools accessible in Claude Desktop
- search_concepts returns results
- get_concept_details shows relationships
- find_shortest_path works between concepts

---

## Task 06: Vector Search Migration

**Status:** Pending
**Complexity:** Medium
**Dependencies:** Task 04 complete

### Sub-tasks:

#### pgvector Setup
- [ ] Verify pgvector extension installed in Docker image
- [ ] Create vector index on concept embeddings
- [ ] Test vector operators: <->, <#>, <=>
- [ ] Benchmark IVF index parameters (lists = 100, 200, 500)
- [ ] Compare pgvector performance to Neo4j vector index

#### Embedding Storage
- [ ] Verify embedding format: JSONB array vs vector type
- [ ] Update concept creation to store embeddings as vector type
- [ ] Migrate existing embeddings format if needed
- [ ] Test embedding retrieval and casting

#### Search Implementation
- [ ] Update LLM extractor to use pgvector search
- [ ] Update concept matching logic in ingestion pipeline
- [ ] Test similarity threshold tuning (0.7, 0.8, 0.9)
- [ ] Verify duplicate concept detection still works

**Acceptance Criteria:**
- Vector search returns top-k similar concepts
- Search performance acceptable (<100ms for 10k concepts)
- Embedding-based concept matching works in ingestion
- No duplicate concepts created

---

## Task 07: CLI Updates

**Status:** Pending
**Complexity:** Medium
**Dependencies:** Task 04 complete

### Sub-tasks:

#### TypeScript Client Config
- [ ] Update client/src/config/index.ts database config
- [ ] Change connection from Neo4j to PostgreSQL
- [ ] Update default port: 7687 → 5432
- [ ] Update connection string format
- [ ] Remove Neo4j-specific config options

#### CLI Commands
- [ ] Update kg database stats command
- [ ] Update kg search command
- [ ] Update kg concept get command
- [ ] Update kg ontology list command
- [ ] Test all CLI commands with AGE backend

#### Environment Variables
- [ ] Update .env.example: NEO4J_* → POSTGRES_*
- [ ] Update documentation for environment variables
- [ ] Test config loading from .env

**Acceptance Criteria:**
- `kg database stats` shows graph statistics
- `kg search "query"` returns concepts
- All CLI commands work with PostgreSQL backend
- Config migration guide documented

---

## Task 08: Ingestion Pipeline Updates

**Status:** Pending
**Complexity:** Medium
**Dependencies:** Task 04, Task 06 complete

### Sub-tasks:

#### Pipeline Integration
- [ ] Update ingest/ingest.py to use AGEClient
- [ ] Update ingest/llm_extractor.py imports
- [ ] Test concept extraction and storage
- [ ] Test relationship creation
- [ ] Test ontology assignment

#### Testing
- [ ] Test ingestion with sample document
- [ ] Verify concepts created in AGE graph
- [ ] Verify relationships created correctly
- [ ] Verify vector embeddings stored
- [ ] Test batch ingestion (multiple documents)

#### Scripts
- [ ] Update scripts/ingest.sh if needed
- [ ] Update scripts/status.sh to check PostgreSQL
- [ ] Update scripts/reset.sh for PostgreSQL cleanup
- [ ] Create scripts/migrate-neo4j-to-age.py for data migration

**Acceptance Criteria:**
- Can ingest document and see concepts in PostgreSQL
- Relationships traversable via Cypher queries
- Vector search finds similar concepts
- Ingestion logs show successful processing

---

## Task 09: Authentication & RBAC Implementation

**Status:** Pending
**Complexity:** High
**Dependencies:** Task 03, Task 04 complete

### Sub-tasks:

#### User Management
- [ ] Create src/api/auth/user_manager.py
- [ ] Implement create_user() with password hashing
- [ ] Implement authenticate_user() with bcrypt
- [ ] Implement get_user_by_username()
- [ ] Implement list_users() for admin

#### API Key Management
- [ ] Create src/api/auth/api_key_manager.py
- [ ] Implement generate_api_key()
- [ ] Implement validate_api_key()
- [ ] Implement revoke_api_key()
- [ ] Implement list_api_keys_for_user()

#### Role-Based Access
- [ ] Implement role checking middleware
- [ ] Create decorators: @require_role('admin'), @require_role('contributor')
- [ ] Implement row-level security policies
- [ ] Test read-only user access
- [ ] Test contributor write access
- [ ] Test admin full access

#### Audit Logging
- [ ] Create src/api/audit/logger.py
- [ ] Implement log_action() for all write operations
- [ ] Implement log_query() for sensitive reads
- [ ] Create audit log query endpoints
- [ ] Test audit trail completeness

**Acceptance Criteria:**
- Can create users with different roles
- API key authentication works
- Read-only users cannot modify data
- All write operations logged to audit_log table
- Admin can query audit logs

---

## Task 10: Data Migration Script

**Status:** Pending
**Complexity:** High
**Dependencies:** Task 04 complete

### Sub-tasks:

#### Export from Neo4j
- [ ] Create scripts/export_neo4j.py
- [ ] Export all Concept nodes to JSON
- [ ] Export all Source nodes to JSON
- [ ] Export all Instance nodes to JSON
- [ ] Export all relationships to JSON
- [ ] Export embeddings and properties
- [ ] Create backup archive with metadata

#### Import to AGE
- [ ] Create scripts/import_to_age.py
- [ ] Parse Neo4j export JSON
- [ ] Create concepts in AGE graph
- [ ] Create sources in AGE graph
- [ ] Create instances in AGE graph
- [ ] Create relationships in AGE graph
- [ ] Store embeddings as pgvector

#### Verification
- [ ] Create scripts/verify_migration.py
- [ ] Compare node counts: Neo4j vs AGE
- [ ] Compare relationship counts
- [ ] Sample random concepts and verify properties
- [ ] Test sample queries match results
- [ ] Generate migration report

#### User-Facing Script
- [ ] Create scripts/migrate.sh wrapper script
- [ ] Add progress bars for long operations
- [ ] Add rollback capability
- [ ] Add dry-run mode
- [ ] Document migration process in docs/MIGRATION.md

**Acceptance Criteria:**
- All Neo4j data exported successfully
- All data imported to AGE without errors
- Concept/source/instance counts match
- Relationship counts match
- Sample queries return identical results
- Migration script documented

---

## Task 11: Testing & Validation

**Status:** Pending
**Complexity:** Medium
**Dependencies:** All previous tasks complete

### Sub-tasks:

#### Integration Testing
- [ ] Test end-to-end ingestion pipeline
- [ ] Test MCP server with all tools
- [ ] Test CLI all commands
- [ ] Test API endpoints (if any)
- [ ] Test authentication and authorization flows
- [ ] Test vector search accuracy

#### Performance Testing
- [ ] Benchmark concept creation (AGE vs Neo4j baseline)
- [ ] Benchmark relationship queries
- [ ] Benchmark vector search
- [ ] Benchmark graph traversal (2-3 hops)
- [ ] Identify performance bottlenecks
- [ ] Tune PostgreSQL settings if needed

#### Edge Cases
- [ ] Test large documents (>100 paragraphs)
- [ ] Test malformed Cypher queries
- [ ] Test connection failures and reconnection
- [ ] Test concurrent ingestion jobs
- [ ] Test backup/restore under load

**Acceptance Criteria:**
- All integration tests pass
- Performance acceptable (within 2x of Neo4j baseline)
- No data corruption under edge cases
- Connection handling robust

---

## Task 12: Documentation Updates

**Status:** Pending
**Complexity:** Low
**Dependencies:** Task 11 complete

### Sub-tasks:

#### User Documentation
- [ ] Update README.md: Replace Neo4j with PostgreSQL + AGE
- [ ] Update docs/QUICKSTART.md with new setup instructions
- [ ] Update docs/ARCHITECTURE.md with unified database diagram
- [ ] Create docs/MIGRATION.md for users migrating from Neo4j
- [ ] Create docs/RBAC.md documenting role model
- [ ] Update docs/BACKUP_RESTORE.md with pg_dump approach (simplify ADR-015)

#### Developer Documentation
- [ ] Update CLAUDE.md with PostgreSQL connection details
- [ ] Update code comments in age_client.py
- [ ] Update MCP server README
- [ ] Document Cypher differences (AGE vs Neo4j) in docs/CYPHER_COMPAT.md
- [ ] Update AI_PROVIDERS.md if needed (no changes expected)

#### Scripts & Config
- [ ] Update .env.example with PostgreSQL variables
- [ ] Update docker-compose.yml comments
- [ ] Update scripts/setup.sh for PostgreSQL
- [ ] Document all new scripts in README

#### Examples
- [ ] Create example queries in docs/EXAMPLES.md
- [ ] Add RBAC usage examples
- [ ] Add vector search examples
- [ ] Add backup/restore examples

**Acceptance Criteria:**
- All documentation reflects AGE instead of Neo4j
- Quickstart guide works for new users
- Migration guide complete for existing users
- All examples tested and verified

---

## Task 13: Cleanup & Release

**Status:** Pending
**Complexity:** Low
**Dependencies:** Task 12 complete

### Sub-tasks:

#### Code Cleanup
- [ ] Remove ingest/neo4j_client.py (replaced by age_client.py)
- [ ] Remove mcp-server/src/neo4j.ts (replaced by age-client.ts)
- [ ] Remove Neo4j-specific imports throughout codebase
- [ ] Remove neo4j-driver from all package.json files
- [ ] Remove neo4j from requirements.txt
- [ ] Clean up unused Neo4j configuration

#### Docker Cleanup
- [ ] Remove Neo4j volumes from docker-compose.yml
- [ ] Update Docker documentation
- [ ] Test clean Docker setup from scratch
- [ ] Remove Neo4j browser references

#### Final Testing
- [ ] Fresh clone and setup on clean machine
- [ ] Run full test suite
- [ ] Verify all scripts work
- [ ] Test migration path one more time
- [ ] Get user acceptance testing

#### Git Workflow
- [ ] Rebase feature branch on latest main
- [ ] Squash commits if needed
- [ ] Write comprehensive PR description
- [ ] Tag release: v0.3.0-rc1 (release candidate)
- [ ] Merge to main after approval
- [ ] Tag release: v0.3.0

**Acceptance Criteria:**
- No Neo4j references in codebase
- Clean setup works from scratch
- All tests pass
- Migration tested by at least one user
- Branch merged to main
- Release tagged

---

## Task 14: Post-Release Monitoring

**Status:** Pending
**Complexity:** Low
**Dependencies:** Task 13 complete

### Sub-tasks:

- [ ] Monitor issue reports for migration problems
- [ ] Track performance in production
- [ ] Gather user feedback on RBAC model
- [ ] Identify optimization opportunities
- [ ] Plan performance tuning based on usage patterns
- [ ] Update documentation based on user questions

**Acceptance Criteria:**
- No critical bugs reported in first 2 weeks
- Performance meets expectations
- Users successfully migrate from Neo4j

---

## Notes

**Branch Strategy:**
- Main branch: Stable with ADR-016 documentation
- Feature branch: `feature/apache-age-migration` for all implementation work
- No incremental merges - complete replacement in one PR

**Testing Strategy:**
- Keep Neo4j running in parallel during development for comparison testing
- Benchmark all operations against Neo4j baseline
- Maintain test data set for validation

**Rollback Plan:**
- Keep Neo4j docker-compose in separate file (docker-compose.neo4j.yml)
- Document rollback procedure in MIGRATION.md
- Keep Neo4j export scripts for emergency data recovery

**Communication:**
- This is a breaking change - major version bump (v0.3.0)
- Users must run migration script
- Provide migration support during release window
