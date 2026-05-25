# Upgrading

How to upgrade the knowledge graph system to new versions.

## Update vs Upgrade

Following the familiar Linux package manager pattern:

| Command | What it does | Restarts? |
|---------|--------------|-----------|
| `./operator.sh update` | Pull latest images | No |
| `./operator.sh upgrade` | Pull, migrate, restart | Yes |

**Check for updates first:**
```bash
./operator.sh update          # Pull all images
./operator.sh update api      # Pull specific service only
./operator.sh update operator # Update operator (scripts/migrations)
```

**Then apply them:**
```bash
./operator.sh upgrade
```

## Quick Upgrade

```bash
./operator.sh upgrade
```

This command:
1. Pulls latest images (if using GHCR)
2. Backs up the database
3. Stops application containers
4. Runs database migrations
5. Starts containers with new images
6. Verifies health

## Upgrade Options

```bash
# See what would change without doing it (--whatif also works)
./operator.sh upgrade --dry-run

# Skip the pre-upgrade backup prompt (faster, but risky)
./operator.sh upgrade --no-backup

# Skip the confirmation prompt
./operator.sh upgrade -y
```

To pin a specific version, edit the image tag in your compose file (see
[Version Pinning](#version-pinning) below) and then run
`./operator.sh update && ./operator.sh upgrade`.

## Before Upgrading

1. **Check the changelog** for breaking changes
2. **Backup your data** (runs `pg_dump` inside the operator container):
   ```bash
   ./operator.sh shell
   /workspace/operator/database/backup-database.sh -y
   # backup is written to /project/backups/ on the host
   ```
3. **Check your current versions:**
   ```bash
   ./operator.sh versions
   ```

## After Upgrading

1. **Verify health:**
   ```bash
   ./operator.sh status
   ```

2. **Check logs for errors:**
   ```bash
   ./operator.sh logs api
   ```

3. **Test core functionality:**
   ```bash
   kg health
   kg search "test"
   ```

## Rolling Back

If something goes wrong:

1. **Stop containers:**
   ```bash
   ./operator.sh stop
   ```

2. **Restore database** (uses `pg_restore` inside the operator container):
   ```bash
   ./operator.sh shell
   /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
   ```

3. **Use previous image version:**
   Edit compose file to pin previous version tag, then:
   ```bash
   ./operator.sh start
   ```

## Version Pinning

By default, GHCR deployments use `:latest`. To pin a specific version:

Edit `docker-compose.prod.yml`:
```yaml
api:
  image: ghcr.io/aaronsb/knowledge-graph-system/kg-api:0.5.0
```

## Migration Notes

Database migrations run automatically during upgrade. If a migration fails:

1. Check logs:
   ```bash
   ./operator.sh logs operator
   ```

2. Run manually:
   ```bash
   ./operator.sh shell
   /workspace/operator/database/migrate-db.sh -y
   ```

3. If stuck, restore from backup and report the issue.
