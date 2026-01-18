# Backup & Restore

Protecting your knowledge graph data.

## What Gets Backed Up

| Component | Contains | Backup Method |
|-----------|----------|---------------|
| PostgreSQL | Concepts, relationships, users, config | `pg_dump` |
| Garage | Original documents | S3-compatible tools |

## Quick Backup

```bash
./operator.sh backup
```

Creates a timestamped SQL dump in the backups directory.

## Backup Locations

Default backup location: `./backups/`

```bash
ls -la backups/
# knowledge_graph_2026-01-18_120000.sql
```

## Manual Database Backup

```bash
# Backup to file
docker exec kg-postgres pg_dump -U admin -d knowledge_graph > backup.sql

# Compressed
docker exec kg-postgres pg_dump -U admin -d knowledge_graph | gzip > backup.sql.gz
```

## Restore

```bash
./operator.sh restore /path/to/backup.sql
```

Or manually:

```bash
# Drop and recreate database
docker exec -i kg-postgres psql -U admin -c "DROP DATABASE IF EXISTS knowledge_graph;"
docker exec -i kg-postgres psql -U admin -c "CREATE DATABASE knowledge_graph;"

# Restore
docker exec -i kg-postgres psql -U admin -d knowledge_graph < backup.sql
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
0 2 * * * cd /path/to/knowledge-graph-system && ./operator.sh backup
```

## Backup Retention

Clean up old backups periodically:

```bash
# Keep last 7 days
find ./backups -name "*.sql" -mtime +7 -delete
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
   ./operator.sh restore /path/to/backup.sql
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

Regularly verify backups work:

```bash
# Create test environment
docker run -d --name backup-test -e POSTGRES_PASSWORD=test postgres:16

# Restore to test
docker exec -i backup-test psql -U postgres < backup.sql

# Verify
docker exec backup-test psql -U postgres -d knowledge_graph -c "SELECT COUNT(*) FROM concepts;"

# Cleanup
docker rm -f backup-test
```
