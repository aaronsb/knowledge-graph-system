# Database Migrations

**ADR-040: Database Schema Migration Management**

This directory contains numbered migration files that evolve the database schema safely and incrementally.

---

## Quick Start

### Apply All Pending Migrations

```bash
./scripts/migrate-db.sh
```

### Preview Pending Migrations

```bash
./scripts/migrate-db.sh --dry-run
```

### Apply Without Confirmation (CI/CD)

```bash
./scripts/migrate-db.sh -y
```

---

## Migration Naming Convention

**Format:** `{version}_{description}.sql`

- **Version:** `001`, `002`, `003`, ... (zero-padded 3 digits, sequential)
- **Description:** `snake_case`, descriptive name

**Examples:**
- `001_baseline.sql` - Initial schema snapshot (v2.0.0)
- `002_add_query_cache.sql` - Add query result caching
- `003_add_user_preferences.sql` - Add user preference storage
- `010_consolidate_auth_tables.sql` - Major auth refactor

---

## Migration File Structure

Every migration follows this template:

```sql
-- Migration: {version}_{description}
-- Description: Brief explanation of what this migration does
-- ADR: Link to related ADR (if applicable)
-- Date: YYYY-MM-DD

BEGIN;

-- ============================================================================
-- Schema Changes
-- ============================================================================

-- Add tables
CREATE TABLE IF NOT EXISTS kg_api.my_new_table (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

-- Add columns to existing tables
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'existing_table'
          AND column_name = 'new_column'
    ) THEN
        ALTER TABLE kg_api.existing_table ADD COLUMN new_column TEXT;
    END IF;
END $$;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_my_new_table_data ON kg_api.my_new_table USING gin(data);

-- Add comments
COMMENT ON TABLE kg_api.my_new_table IS 'Description of what this table stores';

-- ============================================================================
-- Data Migrations (if needed)
-- ============================================================================

-- Insert default/seed data
INSERT INTO kg_api.my_new_table (data)
VALUES ('{"default": true}'::jsonb)
ON CONFLICT DO NOTHING;

-- Update existing rows
UPDATE kg_api.existing_table
SET new_column = 'default_value'
WHERE new_column IS NULL;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_query_cache')  -- Update version and name!
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

---

## Migration Best Practices

### 1. **Idempotent Operations**

Always use conditional statements to make migrations safe to re-run:

```sql
-- Tables
CREATE TABLE IF NOT EXISTS ...;

-- Columns (PostgreSQL 9.6+)
ALTER TABLE my_table ADD COLUMN IF NOT EXISTS ...;

-- Columns (older PostgreSQL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'my_table' AND column_name = 'my_column'
    ) THEN
        ALTER TABLE my_table ADD COLUMN my_column TEXT;
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_name ON my_table(column);

-- Constraints
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'my_constraint'
    ) THEN
        ALTER TABLE my_table ADD CONSTRAINT my_constraint ...;
    END IF;
END $$;
```

### 2. **Transactional Migrations**

**ALWAYS** wrap migrations in `BEGIN/COMMIT`:

```sql
BEGIN;

-- All schema changes here

COMMIT;
```

**Why?** PostgreSQL's transactional DDL ensures all-or-nothing execution. If ANY statement fails, the entire migration rolls back automatically.

### 3. **Self-Documenting**

```sql
-- Bad
ALTER TABLE t ADD COLUMN c TEXT;

-- Good
-- Add user email column for notification preferences
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
COMMENT ON COLUMN users.email IS 'User email for notifications and account recovery';
```

### 4. **Atomic Changes**

One migration = one logical change. Don't combine unrelated changes:

```sql
-- Bad: Two unrelated changes
-- 002_add_cache_and_auth.sql (don't do this!)

-- Good: Separate migrations
-- 002_add_query_cache.sql
-- 003_add_oauth_provider.sql
```

### 5. **Test on Both Fresh and Existing Databases**

```bash
# Test on fresh database
docker-compose down -v && docker-compose up -d
./scripts/migrate-db.sh --dry-run  # Preview
./scripts/migrate-db.sh -y         # Apply

# Test on existing database (with data)
# (Use your development database)
./scripts/migrate-db.sh --dry-run  # Preview
./scripts/migrate-db.sh -y         # Apply
```

### 6. **Verify Migration Was Recorded**

Every migration MUST include the `INSERT INTO schema_migrations` statement:

```sql
INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'descriptive_name')
ON CONFLICT (version) DO NOTHING;
```

Without this, the migration won't be tracked and may run multiple times.

---

## Common Migration Patterns

### Adding a New Table

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.query_cache (
    query_hash VARCHAR(64) PRIMARY KEY,
    query_text TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON kg_api.query_cache(expires_at);

COMMENT ON TABLE kg_api.query_cache IS 'Cache for frequently executed queries - ADR-XXX';

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_query_cache')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding a Column

```sql
BEGIN;

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

### Renaming a Column (with backward compatibility)

```sql
BEGIN;

-- Step 1: Add new column
ALTER TABLE kg_api.jobs ADD COLUMN IF NOT EXISTS new_name TEXT;

-- Step 2: Copy data
UPDATE kg_api.jobs SET new_name = old_name WHERE new_name IS NULL;

-- Step 3: Drop old column (only after code updated)
-- ALTER TABLE kg_api.jobs DROP COLUMN IF EXISTS old_name;
-- (Leave commented until code migration complete)

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'rename_column_old_to_new')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding an Index

```sql
BEGIN;

CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON kg_api.ingestion_jobs(created_at DESC);

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_jobs_created_index')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Adding Seed/Default Data

```sql
BEGIN;

-- Insert default configuration
INSERT INTO kg_api.system_config (key, value)
VALUES ('feature_flag_xyz', 'true'::jsonb)
ON CONFLICT (key) DO NOTHING;

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_feature_flag_xyz')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

---

## Migration Workflow

### Creating a New Migration

**1. Determine next version number**

```bash
ls schema/migrations/ | sort | tail -1
# Output: 001_baseline.sql
# Next version: 002
```

**2. Create migration file**

```bash
cat > schema/migrations/002_add_feature_x.sql <<'EOF'
-- Migration: 002_add_feature_x
-- Description: Add support for feature X
-- Date: 2025-10-21

BEGIN;

-- Your schema changes here

INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'add_feature_x')
ON CONFLICT (version) DO NOTHING;

COMMIT;
EOF
```

**3. Test migration**

```bash
# Dry run first
./scripts/migrate-db.sh --dry-run

# Apply to development database
./scripts/migrate-db.sh -y
```

**4. Verify migration**

```bash
# Check migration was recorded
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT * FROM public.schema_migrations ORDER BY version;"

# Verify schema changes
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "\dt kg_api.*"  # List tables
```

**5. Commit to git**

```bash
git add schema/migrations/002_add_feature_x.sql
git commit -m "feat: add feature X (migration 002)"
```

### Team Workflow

**Developer A adds migration 002:**
```bash
git add schema/migrations/002_add_cache.sql
git commit -m "feat: add query cache"
git push
```

**Developer B pulls and applies:**
```bash
git pull
./scripts/migrate-db.sh  # Applies migration 002 automatically
```

---

## Troubleshooting

### Migration Fails Mid-Execution

**PostgreSQL's transactional DDL** automatically rolls back failed migrations:

```bash
./scripts/migrate-db.sh -y
# → Applying migration 002 (add_query_cache)...
# ERROR: syntax error at line 15
# ✗ Migration 002 failed - stopping
```

**What happened:**
- Migration 002 started in a `BEGIN` transaction
- Error occurred at line 15
- PostgreSQL rolled back ALL changes
- Database is in same state as before migration

**To fix:**
1. Edit `schema/migrations/002_*.sql`
2. Fix the syntax error
3. Run `./scripts/migrate-db.sh -y` again

### Migration Not Recorded in schema_migrations

**Symptom:** Migration runs but is reported as "not recorded"

**Cause:** Migration file is missing the `INSERT INTO schema_migrations` statement

**Fix:**
```sql
-- Add this at the end of your migration (before COMMIT)
INSERT INTO public.schema_migrations (version, name)
VALUES (2, 'descriptive_name')  -- Update version and name!
ON CONFLICT (version) DO NOTHING;
```

### Version Number Conflicts

**Scenario:** Two developers create migration 003 in parallel

**Developer A:** `003_add_cache.sql`
**Developer B:** `003_add_preferences.sql`

**Solution:**
1. Developer B renames their migration to `004_add_preferences.sql`
2. Update version in SQL: `VALUES (4, 'add_preferences')`
3. Coordinate via git merge/rebase

---

## Migration vs. Seed Data

**Migrations:** Schema structure (tables, columns, indexes, constraints)

**Seed Data:** Default/required data for schema to function

**Include in migrations when:**
- Default admin user (required for system to work)
- Default configuration values (required for features)
- Enum-like lookup tables (list of valid statuses)

**Don't include in migrations:**
- Test data
- User-specific data
- Large datasets

---

## PostgreSQL-Specific Features We Use

### 1. Transactional DDL

Unlike MySQL, PostgreSQL DDL is transactional:

```sql
BEGIN;
CREATE TABLE users (...);
CREATE TABLE posts (...);
-- If posts fails, users table is NOT created
COMMIT;
```

### 2. IF NOT EXISTS Clauses

```sql
CREATE TABLE IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;  -- PostgreSQL 9.6+
```

### 3. DO Blocks (Anonymous PL/pgSQL)

```sql
DO $$
BEGIN
    IF NOT EXISTS (...) THEN
        -- Conditional DDL
    END IF;
END $$;
```

### 4. Information Schema Introspection

```sql
SELECT 1 FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'email';
```

---

## Future Enhancements

When the project grows, consider:

- **Rollback migrations** (reverse.sql files)
- **Migration dependencies** (requires 002 before 003)
- **Timestamp-based versions** (20251021_add_cache.sql)
- **Up/Down migration pairs** (like Rails)
- **Migration tooling** (upgrade to Alembic/Flyway if needed)

See **ADR-040** for future migration system evolution.

---

## Related Documentation

- **ADR-040:** Database Schema Migration Management
- **ADR-024:** Multi-Schema PostgreSQL Architecture
- **schema/00_baseline.sql:** Current baseline schema
- **scripts/migrate-db.sh:** Migration runner implementation

---

**Last Updated:** 2025-10-20
**Current Schema Version:** 001 (baseline)
