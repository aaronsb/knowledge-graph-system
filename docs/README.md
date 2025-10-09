# Documentation Index

This directory contains all documentation for the Knowledge Graph System, organized by category.

## Directory Structure

### 📐 `architecture/`
Architecture decisions, design documents, and ADRs (Architectural Decision Records).

- **ARCHITECTURE.md** - System architecture overview
- **ARCHITECTURE_DECISIONS.md** - Consolidated architecture decisions
- **ADR-012-api-server-architecture.md** - FastAPI REST server design
- **ADR-013-unified-typescript-client.md** - TypeScript client consolidation
- **ADR-014-job-approval-workflow.md** - Job approval and queue management
- **ADR-015-backup-restore-streaming.md** - Database backup/restore strategy
- **ADR-016-apache-age-migration.md** - Neo4j to Apache AGE migration

### 🧪 `testing/`
Test coverage specifications and testing documentation.

- **TEST_COVERAGE.md** - Comprehensive test coverage plan and philosophy

### 🔌 `api/`
API documentation and query pattern references.

- **CYPHER_PATTERNS.md** - AGE Cypher query patterns and compatibility notes
- **NEO4J_QUERIES.md** - Legacy Neo4j query reference (being deprecated)

### 📚 `guides/`
User and developer guides for getting started and working with the system.

- **QUICKSTART.md** - Quick start guide for new users
- **AI_PROVIDERS.md** - AI provider configuration (OpenAI, Anthropic)
- **MCP_SETUP.md** - MCP server setup for Claude Desktop integration
- **BACKUP_RESTORE.md** - Backup and restore operations guide
- **INGESTION.md** - Document ingestion workflow and configuration
- **EXAMPLES.md** - Usage examples and common patterns

### 📖 `reference/`
Conceptual documentation and terminology reference.

- **CONCEPT.md** - Core concept definitions
- **CONCEPTS_AND_TERMINOLOGY.md** - System terminology and glossary

### 🔨 `development/`
Development journals, learnings, and internal notes.

- **DEV_JOURNAL_chunked_ingestion.md** - Chunked ingestion development journal
- **LEARNED_KNOWLEDGE_MCP.md** - MCP integration learnings

### 🖼️ `media/`
Images, diagrams, and other media assets.

## Quick Navigation

### New Users
1. Start with [QUICKSTART.md](guides/QUICKSTART.md)
2. Learn about [AI Providers](guides/AI_PROVIDERS.md)
3. Review [Examples](guides/EXAMPLES.md)

### Developers
1. Read [ARCHITECTURE.md](architecture/ARCHITECTURE.md)
2. Review [ADR-016](architecture/ADR-016-apache-age-migration.md) for current database architecture
3. Check [TEST_COVERAGE.md](testing/TEST_COVERAGE.md) for testing guidelines
4. Reference [CYPHER_PATTERNS.md](api/CYPHER_PATTERNS.md) for query development

### Contributors
1. Read architecture decisions in `architecture/`
2. Follow test guidelines in `testing/`
3. Review development journals in `development/`
4. Understand system concepts in `reference/`

## Migration Notes

This documentation was reorganized on 2025-10-08 to improve organization and maintainability. Previous flat structure has been split into logical categories.

**Breaking Changes:**
- All documentation links in code and README files may need updating
- File paths have changed (e.g., `docs/ARCHITECTURE.md` → `docs/architecture/ARCHITECTURE.md`)

**Migration TODO:**
- [ ] Update main README.md links
- [ ] Update CLAUDE.md references
- [ ] Update any hardcoded documentation paths in code
- [ ] Rename NEO4J_QUERIES.md to AGE_QUERIES.md (pending Apache AGE migration completion)
