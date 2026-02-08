# Documentation Index

This directory contains documentation for the Knowledge Graph System.

## Quick Start

**[Quick Start Guide](operating/quick-start.md)** - Operator architecture setup (containerized deployment)

Uses Docker containers with the operator pattern (ADR-061). No local Python installation required.

## Directory Structure

### `manual/`
User manual organized into numbered sections for reading order.

- **01-getting-started/** - Quickstart, CLI usage, ingestion basics
- **02-configuration/** - AI providers, extraction, embeddings
- **03-integration/** - MCP setup, vocabulary management
- **04-security-and-access/** - Authentication, RBAC, security
- **05-maintenance/** - Backup/restore, migrations
- **06-reference/** - Schema, concepts, examples, query patterns

See `manual/README.md` for detailed navigation.

### `architecture/`
Architecture decisions and design documents.

- **INDEX.md** - ADR index (96 decisions)
- **ADR-###-*.md** - Individual architecture decision records (organized in subdirectories)

Key ADRs for understanding the system:
- [ADR-044](architecture/ai-embeddings/ADR-044-probabilistic-truth-convergence.md) - Probabilistic truth convergence
- [ADR-058](architecture/ai-embeddings/ADR-058-polarity-axis-triangulation.md) - Truth as geometric projection
- [ADR-063](architecture/query-search/ADR-063-semantic-diversity-authenticity-signal.md) - Semantic diversity as authenticity
- [ADR-052](architecture/vocabulary-relationships/ADR-052-vocabulary-expansion-consolidation-cycle.md) - Vocabulary expansion-consolidation

### `guides/`
Standalone guides for specific topics.

- **DEPLOYMENT.md** - Deployment strategies for all environments
- **VOCABULARY_CATEGORIES.md** - Vocabulary category scores and confidence
- **SCHEDULED-JOBS.md** - Background maintenance tasks
- **EPISTEMIC-STATUS-FILTERING.md** - Filtering by epistemic status

### `testing/`
Test coverage specifications.

- **TEST_COVERAGE.md** - Test coverage plan and philosophy

### `media/`
Images and diagrams.

## Quick Navigation

### New Users
1. Start with [QUICKSTART.md](operating/quick-start.md) - Operator architecture setup
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
8. Review [SCHEDULED-JOBS.md](guides/SCHEDULED-JOBS.md) for understanding background maintenance tasks

### Developers
1. Read [ARCHITECTURE_OVERVIEW.md](reference/ARCHITECTURE_OVERVIEW.md)
2. Review [ADR-016](architecture/database-schema/ADR-016-apache-age-migration.md) for current database architecture
3. Learn about [DATABASE_MIGRATIONS.md](manual/05-maintenance/02-DATABASE_MIGRATIONS.md) for schema evolution (ADR-040)
4. Reference [SCHEMA_REFERENCE.md](manual/06-reference/01-SCHEMA_REFERENCE.md) for complete schema documentation
5. Check [TEST_COVERAGE.md](testing/TEST_COVERAGE.md) for testing guidelines
6. Reference [CYPHER_PATTERNS.md](manual/06-reference/09-CYPHER_PATTERNS.md) for query development

### Contributors
1. Read architecture decisions in `architecture/`
2. Follow test guidelines in `testing/`
3. Understand system concepts in `concepts/`
