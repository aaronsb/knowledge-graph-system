# Neo4j → Apache AGE Migration Audit

**Generated:** 2025-10-08
**Status:** Migration incomplete - legacy references found

## ✅ MIGRATED (Using AGEClient)

The following files have been successfully migrated to use Apache AGE via `AGEClient`:

- `src/api/routes/database.py` - Database stats and queries
- `src/api/routes/ontology.py` - Ontology management
- `src/api/routes/queries.py` - Graph queries
- `src/api/services/admin_service.py` - Admin operations
- `src/api/workers/ingestion_worker.py` - Background ingestion
- `src/api/lib/ingestion.py` - Core ingestion logic
- `src/api/lib/age_client.py` - **New:** Apache AGE client implementation

## ❌ LEGACY CODE (Still using Neo4j driver)

**CRITICAL:** The following files still import and use the Neo4j Python driver. These need to be verified for current usage and migrated if still active.

### Core Library Files
1. **`src/lib/neo4j_ops.py`** - Legacy Neo4j operations class
   - Contains `Neo4jConnection` and `Neo4jQueries` classes
   - Used by all admin tools below
   - **Action:** Migrate to AGEClient or archive if unused

2. **`src/lib/integrity.py`** - Integrity checking utilities
   - Imports: `from neo4j import Session`
   - **Action:** Verify usage, migrate if needed

3. **`src/lib/restitching.py`** - Graph stitching operations
   - Imports: `from neo4j import Session`, `from .neo4j_ops import Neo4jConnection`
   - **Action:** Verify usage, migrate if needed

4. **`src/lib/serialization.py`** - Serialization utilities
   - Imports: `from neo4j import Session`
   - **Action:** Verify usage, migrate if needed

### Admin Tools
5. **`src/admin/backup.py`** - Database backup tool
   - Imports: `from src.lib.neo4j_ops import Neo4jConnection, Neo4jQueries`
   - **Action:** **HIGH PRIORITY** - Backup is critical, needs AGE migration

6. **`src/admin/restore.py`** - Database restore tool
   - Imports: `from src.lib.neo4j_ops import Neo4jConnection, Neo4jQueries`
   - **Action:** **HIGH PRIORITY** - Restore is critical, needs AGE migration

7. **`src/admin/check_integrity.py`** - Integrity checker
   - Imports: `from src.lib.neo4j_ops import Neo4jConnection`
   - **Action:** Verify if still used, migrate if needed

8. **`src/admin/prune.py`** - Prune orphaned nodes
   - Imports: `from src.lib.neo4j_ops import Neo4jConnection`
   - **Action:** Verify if still used, migrate if needed

9. **`src/admin/stitch.py`** - Graph stitching tool
   - Imports: `from src.lib.neo4j_ops import Neo4jConnection`
   - **Action:** Verify if still used, migrate if needed

## 📄 DOCUMENTATION (Needs updating)

### Critical Documentation
These docs are user-facing and need immediate updates:

- **`README.md`** - Main project README
  - Update: Database setup, connection details, architecture overview

- **`docs/guides/QUICKSTART.md`** - Getting started guide
  - Update: Setup instructions, environment variables, connection strings

- **`docs/guides/MCP_SETUP.md`** - MCP setup instructions
  - Update: Database connection configuration

- **`docs/architecture/ARCHITECTURE.md`** - System architecture
  - Update: Database layer description, connection pooling

- **`docs/architecture/ADR-012-api-server-architecture.md`** - API design
  - Update: Database client references

- **`docs/api/NEO4J_QUERIES.md`** - Query documentation
  - **Action:** Rename to `AGE_QUERIES.md` or `GRAPH_QUERIES.md`
  - Update: All query examples to use AGE syntax

- **`docs/api/CYPHER_PATTERNS.md`** - Cypher patterns
  - Update: Note AGE-specific differences from Neo4j

### Reference Documentation
Lower priority but should be updated for accuracy:

- `docs/reference/CONCEPTS_AND_TERMINOLOGY.md` - Terminology guide
- `docs/development/LEARNED_KNOWLEDGE_MCP.md` - MCP development notes
- `docs/development/DEV_JOURNAL_chunked_ingestion.md` - Development journal
- `docs/architecture/ARCHITECTURE_DECISIONS.md` - ADR index

### Already Updated
- ✅ `docs/architecture/ADR-016-apache-age-migration.md` - Migration guide
- ✅ `CLAUDE.md` - Development guide (updated with PostgreSQL references)

## 🔧 SCRIPTS (Need verification)

Shell scripts that may reference Neo4j:

- `scripts/setup.sh` - Initial setup script
- `scripts/reset.sh` - Database reset script
- `scripts/teardown.sh` - Cleanup script
- `scripts/graph_to_mermaid.py` - Graph visualization
- `reorganize_ingest.sh` - File reorganization

**Action:** Verify scripts work with PostgreSQL/AGE, update references

## ⚙️ CONFIG FILES

- `.env` - Environment variables
  - May contain: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - Should use: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, etc.

- `.mcp.json` - MCP server configuration
  - Verify: Points to correct database connection

## 📊 OTHER FILES

- `tasks.md` - Project task tracking (may reference Neo4j tasks)
- `research/llm-knowledge-extraction-research-2024-2025.md` - Research notes
- `htmlcov/status.json` - Auto-generated coverage report (low priority)

## 🎯 Recommendations

### Immediate Actions (High Priority)
1. ✅ **DONE:** Update `admin_service.py` to use AGEClient
2. **TODO:** Update critical user-facing documentation (README, QUICKSTART)
3. **TODO:** Verify admin tools (backup/restore) are still functional
4. **TODO:** Migrate backup/restore to AGEClient if still used

### Short Term (Medium Priority)
1. Update architecture and API documentation
2. Rename `NEO4J_QUERIES.md` to reflect AGE
3. Update scripts to use PostgreSQL connection strings
4. Clean up `.env` to remove Neo4j variables

### Long Term (Low Priority)
1. Update reference documentation and research notes
2. Archive or remove `src/lib/neo4j_ops.py` if unused
3. Remove legacy admin tools if no longer needed
4. Update MCP server (currently legacy/broken) to use AGE

## 🔍 Next Steps

1. **Audit admin tools:** Determine if backup/restore/integrity tools are still used
2. **Document migration:** Update critical docs (can use agents for parallel execution)
3. **Test functionality:** Ensure all migrated code works correctly with AGE
4. **Clean up:** Remove or archive unused legacy code

---

**Last Updated:** 2025-10-08
**Migration Status:** ~40% complete (API layer done, admin tools pending)
