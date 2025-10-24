# Database Migrations Guide

**ADR-040: Database Schema Migration Management**

This guide explains how to safely evolve the database schema using the knowledge graph system's migration framework.

---

## Quick Reference

```bash
# Apply all pending migrations
./scripts/migrate-db.sh

# Preview what would be applied (dry run)
./scripts/migrate-db.sh --dry-run

# Apply without confirmation (for CI/CD)
./scripts/migrate-db.sh -y

# Show SQL being executed
./scripts/migrate-db.sh -y --verbose
```

---

## Overview

The knowledge graph uses a **migration-based schema management system** that:

✅ **Tracks applied changes** via `schema_migrations` table
✅ **Applies changes in order** (001, 002, 003, ...)
✅ **Safe to re-run** (idempotent operations)
✅ **Automatic rollback** on failure (PostgreSQL transactional DDL)
✅ **Works on fresh AND existing databases**
✅ **Zero external dependencies** (just bash + Docker's psql)

---

## Why Migrations?

### The Problem

**Without migrations:**
- Schema changes added directly to `schema/00_baseline.sql`
- Developers with existing databases must manually extract and run SQL snippets
- No tracking of which changes were applied
- Risk of applying changes out of order or duplicating them
- Different results on fresh vs. existing databases

**With migrations:**
- Each change is a numbered file: `002_add_feature_x.sql`
- `./scripts/migrate-db.sh` applies pending changes automatically
- `schema_migrations` table tracks what's applied
- Migrations apply in correct order
- Idempotent and transactional
- **Same experience for everyone** (fresh or existing database)

---

## How It Works

### Fresh Database Initialization

```bash
docker-compose up -d
↓
PostgreSQL runs schema/00_baseline.sql automatically
↓
Creates all tables, indexes, functions
↓
Creates schema_migrations table
↓
Records: version=1, name='baseline'
↓
Database ready!
```

### Applying Migrations to Existing Database

```bash
./scripts/migrate-db.sh
↓
Checks schema_migrations table
↓
Compares with schema/migrations/*.sql files
↓
Applies pending migrations in order (002, 003, ...)
↓
Records each migration in schema_migrations
↓
Database updated!
```

### Automatic Migration on Startup

```bash
./scripts/start-db.sh
↓
Starts PostgreSQL container
↓
Automatically runs ./scripts/migrate-db.sh -y
↓
Applies any pending migrations
↓
Shows current schema version
```

---

## Migration File Structure

### Naming Convention

**Format:** `{version}_{description}.sql`

- **Version:** `001`, `002`, `003`, ... (zero-padded 3 digits, sequential)
- **Description:** `snake_case`, descriptive

**Examples:**
```
001_baseline.sql
002_add_query_cache.sql
003_add_user_preferences.sql
010_consolidate_auth_tables.sql
```

### Required Template

Every migration must follow this structure:

```sql
-- Migration: {version}_{description}
-- Description: Brief explanation
-- ADR: Link to related ADR (if applicable)
-- Date: YYYY-MM-DD

BEGIN;

-- ============================================================================
-- Schema Changes
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.my_table (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_my_table_data
ON kg_api.my_table USING gin(data);

-- ============================================================================
-- Record Migration (REQUIRED)
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_my_feature')  -- Update version and name!
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

**⚠️ Important:** Every migration MUST include the `INSERT INTO schema_migrations` statement, or it won't be tracked!

---

## Creating a New Migration

### Step 1: Determine Next Version

```bash
ls schema/migrations/ | sort | tail -1
# Output: 002_example_add_query_cache.sql
# Next version: 003
```

### Step 2: Create Migration File

```bash
cat > schema/migrations/003_add_user_preferences.sql <<'EOF'
-- Migration: 003_add_user_preferences
-- Description: Add user preference storage for UI customization
-- Date: 2025-10-21

BEGIN;

-- ============================================================================
-- Add User Preferences Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    language VARCHAR(10) DEFAULT 'en',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_prefs_updated
ON kg_api.user_preferences(updated_at DESC);

COMMENT ON TABLE kg_api.user_preferences IS 'User UI preferences and settings';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (3, 'add_user_preferences')
ON CONFLICT (version) DO NOTHING;

COMMIT;
EOF
```

### Step 3: Test Migration

```bash
# Preview what would happen (dry run)
./scripts/migrate-db.sh --dry-run

# Output:
# Pending Migrations:
#   → Migration 003 - add_user_preferences

# Apply migration
./scripts/migrate-db.sh -y

# Verify it worked
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT * FROM public.schema_migrations ORDER BY version;"
```

### Step 4: Verify Schema Changes

```bash
# Check table was created
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "\d kg_api.user_preferences"

# Check indexes
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "\di kg_api.*"
```

### Step 5: Commit to Git

```bash
git add schema/migrations/003_add_user_preferences.sql
git commit -m "feat: add user preferences table (migration 003)"
git push
```

---

## Team Workflow

### Developer A: Create and Apply Migration

```bash
# Create migration
cat > schema/migrations/003_add_cache.sql <<'EOF'
-- Migration: 003_add_cache
-- ...
EOF

# Test locally
./scripts/migrate-db.sh -y

# Commit
git add schema/migrations/003_add_cache.sql
git commit -m "feat: add result caching"
git push
```

### Developer B: Pull and Apply

```bash
# Pull changes
git pull

# Migrations apply automatically on next db start
./scripts/start-db.sh

# Or apply manually
./scripts/migrate-db.sh -y
```

---

## Common Migration Patterns

### Adding a Table

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.query_cache (
    query_hash VARCHAR(64) PRIMARY KEY,
    query_text TEXT NOT NULL,
    result JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_cache_expires
ON kg_api.query_cache(expires_at);

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_query_cache')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding a Column

```sql
BEGIN;

-- PostgreSQL 9.6+ syntax (preferred)
ALTER TABLE kg_auth.users
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;

-- Or with DO block for older PostgreSQL
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_auth'
          AND table_name = 'users'
          AND column_name = 'email_verified'
    ) THEN
        ALTER TABLE kg_auth.users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

COMMENT ON COLUMN kg_auth.users.email_verified IS 'Whether user email has been verified';

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_email_verification')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding an Index

```sql
BEGIN;

CREATE INDEX IF NOT EXISTS idx_jobs_created_at
ON kg_api.ingestion_jobs(created_at DESC);

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_jobs_created_index')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Modifying a Column (Safe Pattern)

```sql
BEGIN;

-- Add new column with desired type
ALTER TABLE kg_api.jobs
ADD COLUMN IF NOT EXISTS status_new VARCHAR(50);

-- Copy data with transformation
UPDATE kg_api.jobs
SET status_new = UPPER(status)
WHERE status_new IS NULL;

-- (Optional) Drop old column after code migration
-- ALTER TABLE kg_api.jobs DROP COLUMN IF EXISTS status;
-- ALTER TABLE kg_api.jobs RENAME COLUMN status_new TO status;

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'normalize_job_status')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding Seed/Default Data

```sql
BEGIN;

-- Insert default configuration
INSERT INTO kg_api.system_config (key, value)
VALUES
    ('max_upload_size_mb', '100'::jsonb),
    ('enable_telemetry', 'false'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_default_config')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

---

## Best Practices

### 1. Idempotent Operations

Always use conditional statements to make migrations safe to re-run:

```sql
-- ✅ Good: Safe to run multiple times
CREATE TABLE IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;

-- ❌ Bad: Fails if already exists
CREATE TABLE ...;
ALTER TABLE ... ADD COLUMN ...;
CREATE INDEX ...;
```

### 2. Transactional Migrations

**ALWAYS** wrap migrations in `BEGIN/COMMIT`:

```sql
BEGIN;

-- All schema changes here
-- If ANY statement fails, PostgreSQL automatically rolls back EVERYTHING

COMMIT;
```

PostgreSQL's **transactional DDL** ensures all-or-nothing execution. This is a unique PostgreSQL feature - MySQL doesn't have this!

### 3. Record Every Migration

Every migration MUST include:

```sql
INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'descriptive_name')
ON CONFLICT (version) DO NOTHING;
```

**Why `ON CONFLICT DO NOTHING`?** Makes the migration idempotent - safe to re-run even if already recorded.

### 4. Test on Both Fresh and Existing Databases

```bash
# Test on fresh database
docker-compose down -v && docker-compose up -d
./scripts/migrate-db.sh -y

# Test on existing database (with data)
# (Use your development database)
./scripts/migrate-db.sh -y
```

### 5. One Migration = One Logical Change

Don't combine unrelated changes:

```sql
-- ❌ Bad: Two unrelated features
-- 002_add_cache_and_auth.sql

-- ✅ Good: Separate migrations
-- 002_add_query_cache.sql
-- 003_add_oauth_provider.sql
```

---

## Troubleshooting

### Migration Fails Mid-Execution

**What happens:**
```bash
./scripts/migrate-db.sh -y
→ Applying migration 002 (add_query_cache)...
ERROR: syntax error at line 15
✗ Migration 002 failed - stopping
```

**PostgreSQL's transactional DDL automatically rolled back ALL changes.**

Your database is in the **same state as before the migration started**.

**To fix:**
1. Edit `schema/migrations/002_*.sql` to fix the error
2. Run `./scripts/migrate-db.sh -y` again
3. Migration will apply from scratch

### Migration Not Recorded

**Symptom:** Migration runs but shows "⚠️ Warning: Migration not recorded in schema_migrations table"

**Cause:** Migration file is missing the `INSERT INTO schema_migrations` statement

**Fix:** Add this at the end of your migration (before `COMMIT`):

```sql
INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'descriptive_name')
ON CONFLICT (version) DO NOTHING;
```

### Version Number Conflicts

**Scenario:** Two developers create migration 003 in parallel

**Solution:**
1. Last developer to push renames their migration to 004
2. Update version in SQL: `VALUES (4, 'add_preferences')`
3. Coordinate via git merge/rebase

### Check Current Migration Status

```bash
# What's applied?
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT * FROM public.schema_migrations ORDER BY version;"

# What's pending?
./scripts/migrate-db.sh --dry-run
```

---

## Advanced Topics

### Rollback Strategy (Forward-Only)

The current system is **forward-only** (no automatic rollback migrations).

**To reverse a migration:**
1. Create a new migration that undoes the changes
2. Example: Migration 003 added a table, migration 004 drops it

**Why no automatic rollback?**
- Simpler implementation
- Data loss risk (rollback may delete data)
- Most production systems are forward-only
- Can always create a new migration to reverse changes

### Large Data Migrations

For migrations that modify lots of data:

```sql
BEGIN;

-- Update in batches to avoid locking entire table
DO $$
DECLARE
    batch_size INTEGER := 1000;
    updated INTEGER;
BEGIN
    LOOP
        UPDATE kg_api.concepts
        SET new_field = old_field
        WHERE id IN (
            SELECT id FROM kg_api.concepts
            WHERE new_field IS NULL
            LIMIT batch_size
        );

        GET DIAGNOSTICS updated = ROW_COUNT;
        EXIT WHEN updated = 0;

        RAISE NOTICE 'Updated % rows', updated;
    END LOOP;
END $$;

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'backfill_new_field')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Renaming Tables/Columns (Zero-Downtime)

**Phase 1: Add new column, copy data**
```sql
-- Migration 002
BEGIN;
ALTER TABLE users ADD COLUMN email_address TEXT;
UPDATE users SET email_address = email WHERE email_address IS NULL;
INSERT INTO public.schema_migrations (version, name) VALUES (2, 'add_email_address');
COMMIT;
```

**Phase 2: Update application to use new column**
(Deploy new code that uses `email_address`)

**Phase 3: Drop old column**
```sql
-- Migration 003
BEGIN;
ALTER TABLE users DROP COLUMN IF EXISTS email;
INSERT INTO public.schema_migrations (version, name) VALUES (3, 'remove_old_email');
COMMIT;
```

---

## PostgreSQL-Specific Features

### Why PostgreSQL is Perfect for Migrations

**1. Transactional DDL**
```sql
BEGIN;
CREATE TABLE users (...);
CREATE TABLE posts (...);
-- If posts fails, users table is NOT created
COMMIT;
```

**2. IF NOT EXISTS Clauses**
```sql
CREATE TABLE IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;  -- PostgreSQL 9.6+
```

**3. DO Blocks (Anonymous PL/pgSQL)**
```sql
DO $$
BEGIN
    IF NOT EXISTS (...) THEN
        -- Conditional DDL
    END IF;
END $$;
```

**4. Information Schema**
```sql
SELECT 1 FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'email';
```

---

## Migration System Files

### Key Files

```
schema/
├── 00_baseline.sql                 # Base schema (includes schema_migrations table)
└── migrations/
    ├── README.md                   # Detailed migration guide
    ├── 001_baseline.sql            # Reference snapshot
    ├── 002_example_add_query_cache.sql  # Example migration
    └── 003_your_feature.sql        # Your migrations

scripts/
└── migrate-db.sh                   # Migration runner (~200 lines)
```

### Migration Runner Options

```bash
./scripts/migrate-db.sh              # Interactive (asks for confirmation)
./scripts/migrate-db.sh -y           # Auto-confirm (for CI/CD)
./scripts/migrate-db.sh --dry-run    # Preview only (no changes)
./scripts/migrate-db.sh -v           # Verbose (show SQL)
./scripts/migrate-db.sh --help       # Show usage
```

---

## Integration with Existing Tools

### Reset Database (Triggers Fresh Init)

```bash
python -m src.admin.reset --auto-confirm
# OR
./scripts/teardown.sh  # Choose option 2 (delete data)
docker-compose up -d
```

**What happens:**
1. Removes Docker volumes (deletes all data)
2. Creates fresh volumes
3. Runs `schema/00_baseline.sql` automatically
4. Records migration version 1 (baseline)
5. Ready to use!

### Backup/Restore (Includes Migration State)

```bash
# Backup (includes schema_migrations table)
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup.sql

# Restore
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph < backup.sql
```

The `schema_migrations` table is included in backups, so restored databases know which migrations are applied.

---

## Related Documentation

- **ADR-040:** Database Schema Migration Management (design decisions)
- **schema/migrations/README.md:** Detailed migration reference (550+ lines)
- **ADR-024:** Multi-Schema PostgreSQL Architecture
- **01-SCHEMA_REFERENCE.md:** Complete schema documentation

---

## Quick Examples

### View Applied Migrations

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT version, name, applied_at FROM public.schema_migrations ORDER BY version;"
```

### Check Pending Migrations

```bash
./scripts/migrate-db.sh --dry-run
```

### Apply All Pending Migrations

```bash
./scripts/migrate-db.sh -y
```

### Create and Apply a Migration

```bash
# 1. Create file
cat > schema/migrations/003_add_feature.sql <<'EOF'
-- Migration: 003_add_feature
-- Description: Add feature X
-- Date: 2025-10-21

BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.feature_x (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

INSERT INTO public.schema_migrations (version, name)
VALUES (3, 'add_feature')
ON CONFLICT (version) DO NOTHING;

COMMIT;
EOF

# 2. Apply
./scripts/migrate-db.sh -y

# 3. Commit
git add schema/migrations/003_add_feature.sql
git commit -m "feat: add feature X (migration 003)"
```

---

**Last Updated:** 2025-10-20
**Current Schema Version:** 001 (baseline) + any applied migrations
