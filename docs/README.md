# Documentation Index

This directory contains all documentation for the Knowledge Graph System, organized by category.

## Directory Structure

### 📚 `manual/`
Complete user manual organized into numbered sections for natural reading order.

- **01-getting-started/** - Quickstart, CLI usage, ingestion basics
- **02-configuration/** - AI providers, extraction, embeddings
- **03-integration/** - MCP setup, vocabulary management
- **04-security-and-access/** - Authentication, RBAC, security
- **05-maintenance/** - Backup/restore, migrations
- **06-reference/** - Schema, concepts, examples, query patterns

See `manual/README.md` for detailed navigation.

### 📐 `architecture/`
Architecture decisions, design documents, and ADRs (Architectural Decision Records).

- **ARCHITECTURE_DECISIONS.md** - Consolidated architecture decisions index
- **ARCHITECTURE_OVERVIEW.md** - System architecture overview
- **ADR-###-*.md** - Individual architecture decision records

### 📖 `guides/`
Standalone guides for specific topics and workflows.

- **DEPLOYMENT.md** - Comprehensive deployment guide for all environments
- **VOCABULARY_CATEGORIES.md** - Understanding vocabulary category scores and confidence

### 🔨 `development/`
Development journals, learnings, and internal notes.

- **DEV_JOURNAL_chunked_ingestion.md** - Chunked ingestion development journal
- **LEARNED_KNOWLEDGE_MCP.md** - MCP integration learnings

### 🧪 `testing/`
Test coverage specifications and testing documentation.

- **TEST_COVERAGE.md** - Comprehensive test coverage plan and philosophy

### 🖼️ `media/`
Images, diagrams, and other media assets.

## Quick Navigation

### New Users
1. Start with [QUICKSTART.md](manual/01-getting-started/01-QUICKSTART.md)
2. Learn about [AI Providers](manual/02-configuration/01-AI_PROVIDERS.md)
3. Read [INGESTION.md](manual/01-getting-started/03-INGESTION.md) for document ingestion workflow
4. See [VOCABULARY_CONSOLIDATION.md](manual/03-integration/02-VOCABULARY_CONSOLIDATION.md) for managing edge vocabulary growth
5. Read [VOCABULARY_CATEGORIES.md](guides/VOCABULARY_CATEGORIES.md) for understanding category scores and confidence levels
6. See [ENRICHMENT_JOURNEY.md](manual/06-reference/07-ENRICHMENT_JOURNEY.md) for a real example of multi-perspective learning
7. Review [Examples](manual/06-reference/03-EXAMPLES.md) and [Use Cases](manual/06-reference/02-USE_CASES.md)

### Administrators
1. Read [DEPLOYMENT.md](guides/DEPLOYMENT.md) for deployment strategies and production setup
2. Read [AUTHENTICATION.md](manual/04-security-and-access/01-AUTHENTICATION.md) for login and session management
3. **Important:** Keep [PASSWORD_RECOVERY.md](manual/04-security-and-access/04-PASSWORD_RECOVERY.md) handy for account recovery
4. Review [RBAC.md](manual/04-security-and-access/02-RBAC.md) for user and permission management
5. **Important:** Read [SECURITY.md](manual/04-security-and-access/03-SECURITY.md) for encrypted API key management and security infrastructure
6. Learn about [BACKUP_RESTORE.md](manual/05-maintenance/01-BACKUP_RESTORE.md) for data protection
7. Reference [MCP_SETUP.md](manual/03-integration/01-MCP_SETUP.md) for service account configuration

### Developers
1. Read [ARCHITECTURE_OVERVIEW.md](architecture/ARCHITECTURE_OVERVIEW.md)
2. Review [ADR-016](architecture/ADR-016-apache-age-migration.md) for current database architecture
3. Learn about [DATABASE_MIGRATIONS.md](manual/05-maintenance/02-DATABASE_MIGRATIONS.md) for schema evolution (ADR-040)
4. Reference [SCHEMA_REFERENCE.md](manual/06-reference/01-SCHEMA_REFERENCE.md) for complete schema documentation
5. Check [TEST_COVERAGE.md](testing/TEST_COVERAGE.md) for testing guidelines
6. Reference [CYPHER_PATTERNS.md](manual/06-reference/09-CYPHER_PATTERNS.md) for query development

### Contributors
1. Read architecture decisions in `architecture/`
2. Follow test guidelines in `testing/`
3. Review development journals in `development/`
4. Understand system concepts in `reference/`
