---
id: 1.O.01
domain: infra
mode: operations
---

# Backup and Restore

This page covers backing up and restoring a Kappa Graph installation: the PostgreSQL database (graph, config, users) and the Garage document store. It also explains how schema migrations work and how to apply them manually when needed.

---

## What gets backed up

| Component | Contains | Method |
|---|---|---|
| PostgreSQL 18 + Apache AGE 1.7.0 | Concepts, relationships, ontologies, users, config, migration state | `pg_dump --format=custom` |
| Garage S3 | Original source documents | S3-compatible sync or filesystem copy |

PostgreSQL backups use the custom binary format because Apache AGE graph data is OID-coupled to the schema; `pg_dump`/`pg_restore` handles that correctly. A plain SQL dump is not safe for cross-version restores of AGE graphs — see the testing section below.

---

## Back up the database

### Via the operator shell (recommended)

Backup and restore scripts run inside the operator container, which has the correct `pg_dump` version and credentials pre-configured.

```bash
./operator.sh shell
/workspace/operator/database/backup-database.sh -y
```

The dump lands at `./backups/backup_knowledge_graph_<timestamp>.dump` on the host. The host `./backups/` directory is mounted into the operator at `/project/backups`.

### Via `docker exec` without entering the shell

```bash
docker exec -it kg-operator /workspace/operator/database/backup-database.sh -y

# Custom output path
docker exec -it kg-operator /workspace/operator/database/backup-database.sh \
  -y -o /project/backups/my-backup.dump
```

### Manual pg_dump (advanced)

```bash
# Resolve the postgres container name
PG=$(docker ps --format '{{.Names}}' | grep postgres | head -1)

docker exec "$PG" pg_dump -U admin -d knowledge_graph --format=custom > backup.dump
```

### Via the CLI (application-level)

The `kg admin` commands produce a JSON-format backup of graph data through the API (ADR-036). These are useful for sharing ontologies or protecting against expensive re-ingestion costs, but they are not a substitute for a full `pg_dump` for disaster recovery.

```bash
# Full database backup (non-interactive)
kg admin backup --type full

# Single-ontology backup
kg admin backup --type ontology --ontology "My Ontology"

# List available backups
kg admin list-backups
```

---

## Restore the database

### Via the operator shell

```bash
./operator.sh shell
/workspace/operator/database/restore-database.sh /project/backups/<file>.dump
```

### Via `docker exec`

```bash
docker exec -it kg-operator \
  /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
```

### Manual pg_restore (advanced)

AGE graphs are OID-coupled. Restoring across PostgreSQL major versions requires care — see ADR-205 for details.

```bash
PG=$(docker ps --format '{{.Names}}' | grep postgres | head -1)
docker exec -i "$PG" pg_restore -U admin -d knowledge_graph --clean < backup.dump
```

### Via the CLI

```bash
# Restore from a JSON backup (requires admin auth; prompts for password)
kg admin restore --file <backup-file>
```

CLI restores validate integrity automatically after loading. If cross-ontology relationship targets are missing, the system offers repair options (prune dangling edges, stitch from instances, or defer).

---

## Cross-ontology integrity

Ontology-scoped backups can leave dangling relationship targets if the backup does not include every ontology the restored concepts reference. The CLI backup command reports this before writing the file:

```
Relationship Integrity:
  Internal: 10/14
  External: 4/14 (28.6%)

⚠ Restoring this backup may create dangling references!
  Consider one of these strategies:
    1. Restore into a database that already has these dependencies
    2. Use --prune-external to skip external relationships
    3. Back up dependent ontologies together
```

**Full database backup** (`--type full`) avoids this entirely. For partial restores, back up all mutually-dependent ontologies together and restore dependencies first.

---

## Back up Garage document storage

```bash
# AWS CLI pointed at the local Garage endpoint
aws --endpoint-url http://localhost:3900 s3 sync s3://kg-storage ./garage-backup/

# rclone
rclone sync garage:kg-storage ./garage-backup/

# Filesystem copy (when Garage is stopped)
cp -r /srv/docker/data/knowledge-graph/garage ./garage-backup/
```

---

## Automated backups

```bash
crontab -e

# Daily backup at 2 AM
0 2 * * * docker exec kg-operator /workspace/operator/database/backup-database.sh -y
```

Clean up old dumps:

```bash
# Keep last 7 days
find ./backups -name "*.dump" -mtime +7 -delete
```

---

## Disaster recovery

Full recovery from bare metal:

1. **Install Kappa Graph:**
   ```bash
   git clone https://github.com/aaronsb/knowledge-graph-system.git
   cd knowledge-graph-system
   ./operator.sh init --headless ...
   ```

2. **Stop services:**
   ```bash
   ./operator.sh stop
   ```

3. **Restore database:**
   ```bash
   docker exec -it kg-operator \
     /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
   ```

4. **Restore Garage data:**
   ```bash
   cp -r /path/to/garage-backup/* /srv/docker/data/knowledge-graph/garage/
   ```

5. **Start services:**
   ```bash
   ./operator.sh start
   ```

6. **Verify:**
   ```bash
   ./operator.sh status
   kg health
   ```

---

## Test your backups

Test restores using an image that includes Apache AGE. The stock `postgres:18` image does not have the AGE extension; `apache/age` does.

```bash
# Spin up a test instance
docker run -d --name backup-test -e POSTGRES_PASSWORD=test apache/age:release_PG18_1.7.0

# Restore the custom-format dump
docker exec -i backup-test pg_restore -U postgres -d postgres --create < backup.dump

# Verify AGE graphs loaded
docker exec backup-test psql -U postgres -d knowledge_graph \
  -c "SELECT count(*) FROM ag_catalog.ag_graph;"

# Tear down
docker rm -f backup-test
```

---

## Schema migrations

Kappa Graph manages schema evolution through numbered SQL migration files in `schema/migrations/`. The migration runner tracks applied versions in the `public.schema_migrations` table, applies pending files in order, and wraps each migration in a transaction so a failure rolls back automatically.

### How it runs

`./operator.sh start` runs pending migrations automatically before the API starts. You can also run the migration script directly:

```bash
# Preview pending migrations (no changes)
./operator/database/migrate-db.sh --dry-run

# Apply all pending migrations with confirmation
./operator/database/migrate-db.sh

# Apply without confirmation (CI/CD)
./operator/database/migrate-db.sh -y

# Verbose: show SQL as it executes
./operator/database/migrate-db.sh -y --verbose
```

### Check current migration state

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -c "SELECT version, name, applied_at FROM public.schema_migrations ORDER BY version;"
```

The baseline (`00_baseline.sql`) seeds the table at version 1. Migrations are numbered sequentially from 001. As of this writing, migrations run through 078; run `ls schema/migrations/ | sort` to see the current set.

### Fresh database flow

```
docker-compose up -d
  → PostgreSQL runs schema/00_baseline.sql
  → Creates all tables, indexes, functions
  → Records version 1 ('baseline') in schema_migrations
  → migrate-db.sh applies any pending numbered migrations
```

### Writing a migration

Every migration file follows this structure:

```sql
-- Migration: 003_add_user_preferences
-- Description: Add user preference storage
-- Date: YYYY-MM-DD

BEGIN;

CREATE TABLE IF NOT EXISTS kg_api.user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES kg_auth.users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Required: record this migration or it will be re-applied on next run
INSERT INTO public.schema_migrations (version, name)
VALUES (3, 'add_user_preferences')
ON CONFLICT (version) DO NOTHING;

COMMIT;
```

Key rules:

- Use `IF NOT EXISTS` / `IF EXISTS` in all DDL so migrations are safe to re-run.
- Always wrap in `BEGIN`/`COMMIT`. PostgreSQL's transactional DDL rolls back the entire migration on any error.
- Always insert into `schema_migrations` before `COMMIT`. Omitting this causes the migration to run again on the next invocation.
- One migration = one logical change. Do not combine unrelated features.

### Version conflicts (parallel development)

If two branches both create migration 003, the second developer to merge renames their file to 004 and updates the version in the `INSERT` statement. Coordinate via git merge/rebase.

### Rollback

The system is forward-only. To reverse a migration, write a new migration that undoes the change. This avoids the data-loss risk of automatic rollback.

### Backup before migrating

Take a full `pg_dump` before applying migrations to production:

```bash
docker exec -it kg-operator /workspace/operator/database/backup-database.sh -y
./operator/database/migrate-db.sh -y
```

The `schema_migrations` table is included in every `pg_dump`, so a restored database knows exactly which migrations are applied and which are pending.

---

## Related

- [ADR-040: Database Schema Migration Management](../architecture/INDEX.md)
- [ADR-205: AGE graph OID coupling across PostgreSQL major versions](../architecture/INDEX.md)
- [Backup Object Format](../reference/backup-object-spec.md)
- [Upgrading](upgrading.md)
