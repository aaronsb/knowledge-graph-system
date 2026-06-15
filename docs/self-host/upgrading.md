---
id: 1.O.09
domain: infra
mode: operations
---

# Upgrading

This page covers how to upgrade a running Kappa Graph installation to a new version.

## Update vs upgrade

`operator.sh` follows the apt-style split between fetching and applying:

| Command | What it does | Restarts services? |
|---|---|---|
| `./operator.sh update` | Pull latest images | No |
| `./operator.sh upgrade` | Pull, migrate, restart | Yes |

Run `update` to stage new images without touching a running platform. Run `upgrade` to apply them.

## Standard upgrade

```bash
./operator.sh upgrade
```

The command runs these steps in order:

1. Pulls latest images from GHCR (or builds locally, if `IMAGE_SOURCE=local`)
2. Checks for a PostgreSQL major-version change — aborts if detected (see [Major-version changes](#major-version-changes))
3. Stops the `api` and `web` containers
4. Starts `postgres` and `garage`, waits for readiness
5. Runs database migrations via the operator container
6. Starts `api` and `web` with the new images
7. Polls `http://localhost:8000/health` until the API responds

## Upgrade options

```bash
# Preview what would run without making changes
./operator.sh upgrade --dry-run

# Skip the confirmation prompt
./operator.sh upgrade -y

# Skip the pre-upgrade backup prompt
./operator.sh upgrade --no-backup
```

`--whatif` is an alias for `--dry-run`.

## Before upgrading

Check the changelog for breaking changes, then take a manual backup:

```bash
./operator.sh shell
/workspace/operator/database/backup-database.sh -y
# backup written to /project/backups/ on the host
```

Check what is currently running:

```bash
./operator.sh versions
```

## After upgrading

```bash
# Confirm all services are healthy
./operator.sh status

# Review API logs for startup errors
./operator.sh logs api

# Smoke test with the CLI
kg health
kg search "test"
```

## Rolling back

If the upgrade fails:

1. Stop the platform:
   ```bash
   ./operator.sh stop
   ```

2. Restore the database from the pre-upgrade backup:
   ```bash
   ./operator.sh shell
   /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
   ```

3. Pin the previous image tag in `docker/docker-compose.ghcr.yml` (see [Version pinning](#version-pinning)), then start:
   ```bash
   ./operator.sh start
   ```

## Version pinning

By default, GHCR deployments use `:latest`. To hold a specific release, edit `docker/docker-compose.ghcr.yml`:

```yaml
services:
  api:
    image: ghcr.io/aaronsb/knowledge-graph-system/kg-api:0.5.0
```

To upgrade from a pinned version, update the tag and run:

```bash
./operator.sh update && ./operator.sh upgrade
```

## Major-version changes

A PostgreSQL major-version change (for example, 17 → 18) cannot be applied by swapping the container image. `operator.sh upgrade` detects the mismatch by comparing the `PG_MAJOR` label on the new image against the version recorded in the existing data directory, and aborts before touching any container.

A major-version migration is a separate procedure — see ADR-205 for the rationale and steps. Do not force-recreate the postgres container across a major-version boundary without following that procedure.

## Migration failures

Database migrations run automatically during upgrade. If a migration fails:

```bash
# Check migration output
./operator.sh logs operator

# Run migrations manually
./operator.sh shell
/workspace/operator/database/migrate-db.sh -y
```

If migrations cannot be recovered, restore from backup and report the issue.

## Upgrading the operator

The `operator.sh` script and operator container are updated separately from the platform services:

```bash
sudo ./operator.sh self-update
```

This pulls the latest `kg-operator` image and copies the updated `operator.sh` onto the host.
