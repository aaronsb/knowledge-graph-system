---
status: Proposed
date: 2025-10-20
deciders:
  - Development Team
---

# ADR-040: Database Schema Migration Management

## Overview

Every software system evolves over time. You add a new feature that needs a new database table, or you realize an existing column needs a different data type, or you need to add an index for better performance. This is normal and healthy—but it creates a practical problem: how do you safely apply these changes to existing databases without breaking things?

In the early days of our system, we used a single `schema/init.sql` file that worked great for fresh installations but became a coordination nightmare as the project grew. When a developer added a new table, they'd manually edit this monolithic file. If you already had a database running, you'd have to figure out which parts of the file you'd already applied and which were new, then carefully run just the new bits. Miss a dependency? Your database breaks. Run something twice? You might get errors or, worse, silent data corruption.

The core insight is simple: databases need version control just like code. When you pull the latest code from git, you want a command that safely applies any new schema changes—whether it's your first time setting up or you've been running the system for months. The solution is a migration system: numbered SQL files (001, 002, 003...) combined with a tracking table that remembers which migrations have already been applied.

We chose to build a simple bash-based migration runner rather than adopting heavyweight tools like Flyway or Alembic. It's about 100 lines of code, has zero external dependencies beyond the PostgreSQL tools already in our Docker containers, and perfectly fits our linear development model. Each migration is an idempotent SQL file that can safely run multiple times, and the system automatically skips migrations you've already applied. It's simple, transparent, and exactly powerful enough for our needs without the complexity of enterprise migration frameworks.

---

## Context

As the knowledge graph system evolves, we're adding incremental schema changes (new tables, columns, constraints, etc.). Currently, we use a monolithic `schema/init.sql` file that's executed on fresh database initialization.

**The Problem:**
- Each feature adds schema patches directly to `init.sql`
- No tracking of which migrations have been applied
- No safe way to apply schema changes to existing databases
- Manual coordination required to merge patches into stable schema versions
- Risk of applying patches out of order or duplicating changes

**Recent Example:**
Adding `kg_api.embedding_config` table for ADR-039 required manual insertion into `init.sql`. If a developer has an existing database, they must:
1. Manually run the new SQL
2. Hope they don't miss any dependencies
3. Track which patches they've applied vs. which are missing

**This doesn't scale.**

---

## Decision

Implement a **simple, bash-based migration system** using a `schema_migrations` tracking table and numbered migration files.

**Key Components:**

1. **schema_migrations table** - Tracks applied migrations
2. **schema/migrations/** directory - Ordered SQL migration files
3. **scripts/migrate-db.sh** - Migration runner script
4. **Numbered migrations** - `001_baseline.sql`, `002_add_embedding_config.sql`, etc.

**Migration Filename Convention:**
```
{version}_{description}.sql

Examples:
001_baseline.sql
002_add_embedding_config.sql
003_add_user_preferences.sql
```

**Migration Runner Behavior:**
```bash
./scripts/database/migrate-db.sh

# Checks schema_migrations table
# Applies only unapplied migrations in order
# Records each migration in schema_migrations
# Idempotent: safe to run multiple times
```

**Example Migration File:**
```sql
-- Migration: 002_add_embedding_config.sql
-- Description: Add embedding configuration table for ADR-039

BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.embedding_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(200),
    ...
);

-- Insert default config
INSERT INTO kg_api.embedding_config (provider, active)
VALUES ('openai', TRUE);

COMMIT;
```

---

## Alternatives Considered

### Alternative 1: Flyway (Java-based)

**Pros:**
- Industry standard
- Robust feature set
- Good tooling (Flyway Desktop in 2025)
- SQL-based migrations (familiar)

**Cons:**
- Requires Java runtime (adds dependency to Docker image)
- Heavyweight for our simple use case
- Rollback only in paid version
- More complex than we need

**Verdict:** ❌ Too heavyweight for current needs

### Alternative 2: Liquibase (Java-based)

**Pros:**
- Very flexible (SQL, XML, YAML, JSON formats)
- Excellent for complex branching/merging migrations
- Built-in rollback support
- 2025 flow enhancements for orchestration

**Cons:**
- Requires Java runtime
- Steeper learning curve than Flyway
- XML/YAML overhead for simple migrations
- Higher resource consumption

**Verdict:** ❌ Overengineered for our use case

### Alternative 3: Alembic (Python-based)

**Pros:**
- Python-native (matches our stack)
- SQLAlchemy integration
- Programmatic migrations (Python code)
- Active Python community support

**Cons:**
- Requires SQLAlchemy (we use direct psycopg2)
- PostgreSQL + Apache AGE may not map well to SQLAlchemy ORM
- AGE graph structures don't fit ORM paradigm
- Adds Python dependency overhead

**Verdict:** ⚠️ Good option, but SQLAlchemy mismatch with AGE

### Alternative 4: shmig (BASH tool)

**Pros:**
- Simple BASH script (~400 lines)
- POSIX-compatible
- Supports PostgreSQL, MySQL, SQLite3
- Minimal dependencies (just psql)

**Cons:**
- External dependency (another tool to install)
- Feature set beyond our needs
- Would need to maintain if project becomes inactive

**Verdict:** ⚠️ Good, but custom script is simpler

### Alternative 5: Custom Bash Script (CHOSEN)

**Pros:**
- Zero external dependencies (uses Docker's psql)
- ~100 lines of code (easy to understand)
- Matches our existing bash script patterns
- Simple schema_migrations tracking table
- Perfect for linear schema evolution
- Can evolve to Alembic/Flyway later if needed

**Cons:**
- No rollback support (forward-only)
- Manual SQL writing (no ORM abstraction)
- Less battle-tested than Flyway/Liquibase

**Verdict:** ✅ **Best fit for current requirements**

---

## Implementation Plan

### Phase 1: Migration Infrastructure (This ADR)

**1. Create schema_migrations table**
```sql
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**2. Create schema/migrations/ directory structure**
```
schema/
├── init.sql                    # Keep for backward compat (calls migrate-db.sh)
└── migrations/
    ├── 001_baseline.sql        # Current schema as of ADR-040
    ├── 002_add_embedding_config.sql
    └── README.md               # Migration conventions
```

**3. Build migration runner: scripts/migrate-db.sh**
```bash
#!/bin/bash
# Migration runner for PostgreSQL schema changes
#
# Usage:
#   ./scripts/database/migrate-db.sh              # Apply all pending migrations
#   ./scripts/database/migrate-db.sh --dry-run    # Show what would be applied
#
# Idempotent: Safe to run multiple times

set -e

# Check which migrations have been applied
# Apply pending migrations in order
# Record in schema_migrations table
```

**4. Update schema/init.sql**
```bash
#!/bin/bash
# Initialize database schema
# This script now delegates to the migration runner

./scripts/database/migrate-db.sh
```

**5. Update docker-compose.yml (if needed)**
- Ensure init.sql still runs on container creation
- No changes needed if init.sql just calls migrate-db.sh

### Phase 2: Extract Baseline (Immediate)

**Extract current schema as 001_baseline.sql:**
```bash
# Capture current schema/init.sql as baseline migration
cp schema/init.sql schema/migrations/001_baseline.sql
```

**Create 002_add_embedding_config.sql:**
```sql
-- Migration: Add embedding configuration table
-- ADR: ADR-039 Local Embedding Service
-- Date: 2025-10-20

BEGIN;

-- embedding_config table already in baseline
-- This migration is a no-op for fresh installs
-- But allows existing DBs to add the table

CREATE TABLE IF NOT EXISTS kg_api.embedding_config (
    -- ... (full table definition from ADR-039)
);

COMMIT;
```

### Phase 3: Future Migrations

**Workflow for adding schema changes:**

1. Create new migration file: `schema/migrations/003_description.sql`
2. Write SQL changes (use BEGIN/COMMIT for safety)
3. Test on fresh database: `./scripts/database/migrate-db.sh`
4. Test on existing database: `./scripts/database/migrate-db.sh`
5. Commit migration file to git

**Periodically consolidate:**
- When schema stabilizes (e.g., release milestones)
- Merge all migrations into new baseline: `schema/migrations/stable_v2_baseline.sql`
- Archive old migrations in `schema/migrations/archived/`

---

## Consequences

### Positive

✅ **Safe schema evolution**
- Track which migrations have been applied
- Idempotent migrations (safe to re-run)
- Clear audit trail of schema changes

✅ **Developer productivity**
- `./scripts/database/migrate-db.sh` works on fresh and existing databases
- No manual SQL coordination
- Git history shows schema evolution

✅ **Simple and maintainable**
- ~100 lines of bash code
- No external dependencies
- Easy to debug and modify

✅ **Compatible with current workflow**
- Docker container init still works
- Existing databases can migrate forward
- Backward compatible with init.sql approach

### Negative

⚠️ **No automatic rollback**
- Forward-only migrations
- Manual rollback SQL required if needed
- Mitigation: Use BEGIN/COMMIT and test thoroughly

⚠️ **Manual SQL writing**
- No ORM abstraction for schema changes
- Developer must write PostgreSQL SQL
- Mitigation: We already do this, no change

⚠️ **Linear migration path only**
- No branching/merging support (unlike Liquibase)
- Works for our current development model
- Mitigation: Can switch to Alembic/Flyway later if needed

### Risks and Mitigation

**Risk: Migration fails mid-execution**
- **Mitigation:** Wrap migrations in `BEGIN/COMMIT` transactions
- **Mitigation:** Test on fresh database before production

**Risk: Developer forgets to create migration**
- **Mitigation:** Code review checklist includes migration check
- **Mitigation:** CI/CD could compare schema vs. migrations

**Risk: Migration file numbering conflicts**
- **Mitigation:** Use timestamp prefixes if parallel development
- **Mitigation:** Currently single developer, low risk

---

## Migration File Conventions

### Naming

```
{version}_{description}.sql

Version: 001, 002, 003, ... (zero-padded 3 digits)
Description: snake_case, descriptive (e.g., add_user_roles)

Examples:
001_baseline.sql
002_add_embedding_config.sql
003_add_concept_metadata.sql
010_consolidate_auth_tables.sql
```

### Structure

```sql
-- Migration: {version}_{description}
-- Description: Brief explanation of changes
-- ADR: Link to related ADR (if applicable)
-- Date: YYYY-MM-DD

BEGIN;

-- Schema changes here
-- Use CREATE TABLE IF NOT EXISTS for safety
-- Use ALTER TABLE ADD COLUMN IF NOT EXISTS (PostgreSQL 9.6+)

-- Data migrations (if needed)
-- Insert default data
-- Update existing rows

COMMIT;
```

### Best Practices

1. **Idempotent migrations**
   - Use `IF NOT EXISTS` / `IF EXISTS`
   - Check before altering

2. **Transactional**
   - Wrap in `BEGIN/COMMIT`
   - All-or-nothing execution

3. **Self-documenting**
   - Comment purpose and ADR reference
   - Explain complex changes

4. **Tested**
   - Test on fresh database
   - Test on database with existing data

5. **Atomic**
   - One migration = one logical change
   - Don't combine unrelated changes

---

## Comparison to Other Projects

**Ruby on Rails:** Uses ActiveRecord migrations with timestamps
**Django:** Uses numbered migrations per app (0001, 0002, ...)
**Node.js (Knex):** Uses timestamp prefixes (20250120_add_users.js)
**Flyway:** Uses V1__, V2__ version prefixes

**Our approach:** Closest to Django's numbered migrations, adapted for PostgreSQL with bash runner.

---

## Related ADRs

- **ADR-039:** Local Embedding Service (triggered need for migration system)
- **ADR-016:** Apache AGE Migration (major schema change that would have benefited from migrations)

---

## References

- Tutorial: https://www.sheshbabu.com/posts/demystifying-postgres-schema-migrations/
- pg_migrate.sh: https://github.com/maxpoletaev/pg_migrate.sh (inspiration)
- shmig: https://github.com/mbucc/shmig (reference implementation)
- Flyway vs. Liquibase comparison: https://www.bytebase.com/blog/flyway-vs-liquibase/

---

## Notes

**Why not just version control init.sql?**
- Git history shows *what* changed, not *what's applied*
- Developer with existing DB can't tell if they need to run a snippet
- No atomic "apply this change" operation

**When to upgrade to Alembic/Flyway?**
- When we need programmatic migrations (Python logic in migrations)
- When we need branching/merging support (multiple parallel dev branches)
- When we need automated rollback
- Not needed for current development pace

**Migration vs. Seed Data?**
- Migrations: Schema structure (tables, columns, constraints)
- Seed data: Default/initial data (admin user, default config)
- Migrations can include seed data if required for schema to work
