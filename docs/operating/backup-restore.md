# Backup & Restore

Protecting your knowledge graph data.

## What Gets Backed Up

| Component | Contains | Backup Method |
|-----------|----------|---------------|
| PostgreSQL | Concepts, relationships, users, config (incl. Apache AGE graph) | `pg_dump --format=custom` |
| Garage | Original documents | S3-compatible tools |

Backups use the PostgreSQL custom binary format because Apache AGE graph data
relies on schema OIDs and is best preserved by `pg_dump`/`pg_restore`.

## Quick Backup

Backup and restore run inside the operator container (which has the right
`psql`/`pg_dump` versions and credentials). From the host:

```bash
./operator.sh shell
/workspace/operator/database/backup-database.sh -y
```

The dump lands at `./backups/backup_knowledge_graph_<timestamp>.dump` on the
host (the directory is mounted into the operator as `/project/backups`).

You can also drive backup/restore from outside the shell via `docker exec`:

```bash
docker exec -it kg-operator /workspace/operator/database/backup-database.sh -y
docker exec -it kg-operator /workspace/operator/database/backup-database.sh \
  -y -o /project/backups/my-backup.dump
```

## Backup Locations

Default backup location: `./backups/` (on the host, inside your install dir).

```bash
ls -la backups/
# backup_knowledge_graph_2026-05-25_120000.dump
```

## Manual Database Backup

```bash
# Resolve the postgres container name (kg-postgres or knowledge-graph-postgres)
PG=$(docker ps --format '{{.Names}}' | grep postgres | head -1)

# Backup (custom format - preserves AGE graph data)
docker exec "$PG" pg_dump -U admin -d knowledge_graph --format=custom > backup.dump
```

## Restore

Restore also runs inside the operator container:

```bash
./operator.sh shell
/workspace/operator/database/restore-database.sh /project/backups/<file>.dump
```

Or from the host:

```bash
docker exec -it kg-operator \
  /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
```

Manual restore (advanced — note that AGE graphs are OID-coupled and may need
careful handling across PostgreSQL major versions; see ADR-205):

```bash
PG=$(docker ps --format '{{.Names}}' | grep postgres | head -1)
docker exec -i "$PG" pg_restore -U admin -d knowledge_graph --clean < backup.dump
```

## Garage (Document Storage) Backup

Garage uses S3-compatible storage. Back up using standard S3 tools:

```bash
# Using AWS CLI (configured for Garage)
aws --endpoint-url http://localhost:3900 s3 sync s3://kg-storage ./garage-backup/

# Using rclone
rclone sync garage:kg-storage ./garage-backup/
```

Or copy the Garage data directory:
```bash
cp -r /srv/docker/data/knowledge-graph/garage ./garage-backup/
```

## Automated Backups

Set up a cron job for regular backups:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * docker exec kg-operator /workspace/operator/database/backup-database.sh -y
```

## Backup Retention

Clean up old backups periodically:

```bash
# Keep last 7 days
find ./backups -name "*.dump" -mtime +7 -delete
```

## Disaster Recovery

Full recovery procedure:

1. **Fresh installation:**
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

## Testing Backups

Regularly verify backups work. Use an image with Apache AGE installed (the
stock `postgres:18` image lacks the AGE extension that knowledge-graph dumps
depend on):

```bash
# Create test environment (apache/age provides PostgreSQL + AGE)
docker run -d --name backup-test -e POSTGRES_PASSWORD=test apache/age

# Restore to test (custom-format dump)
docker exec -i backup-test pg_restore -U postgres -d postgres --create < backup.dump

# Verify (AGE graphs live in named schemas; concepts is a label inside a graph)
docker exec backup-test psql -U postgres -d knowledge_graph \
  -c "SELECT count(*) FROM ag_catalog.ag_graph;"

# Cleanup
docker rm -f backup-test
```
