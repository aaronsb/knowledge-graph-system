# Operator Architecture

## Overview

The Knowledge Graph platform uses two main tools for installation and operation:

1. **install.sh** - One-time bootstrapper that sets up the platform
2. **operator.sh** - Thin shim that delegates to operator container

## Architecture: Thin Shim + Container Delegation

**Principle: Minimal host logic, delegate everything possible to operator container**

```
install.sh (one-time bootstrap)
    │
    ├─► Downloads: operator.sh, compose files, schema
    ├─► Generates: .env (secrets)
    ├─► Configures: SSL (certs, nginx config)
    ├─► Bootstraps: docker compose up postgres garage operator
    ├─► Delegates config to container
    └─► Shows summary

operator.sh (thin shim on HOST, ~200 lines)
    │
    ├─► HOST-ONLY: start_infra, stop, teardown, update, logs, restart, status
    │
    └─► DELEGATED TO CONTAINER (docker exec kg-operator ...):
        ├─► start → /workspace/operator/lib/start-platform.sh
        ├─► upgrade → /workspace/operator/lib/upgrade.sh
        └─► admin, ai-provider, embedding, api-key → configure.py

kg-operator container (has ALL logic)
    │
    ├─► docker.io CLI (controls sibling containers via socket)
    ├─► docker compose v2 plugin (for compose operations)
    ├─► postgresql-client (psql for migrations)
    ├─► /workspace/operator/lib/*.sh scripts
    ├─► /workspace/operator/database/*.sh (migrate, backup, restore)
    └─► /workspace/operator/configure.py
```

## Current Architecture (Legacy)

### install.sh Responsibilities

| Step | Action | Runs On | Artifacts Created |
|------|--------|---------|-------------------|
| 1. Prerequisites | Check OS, curl, ports | Host | - |
| 2. Docker | Install/verify Docker | Host | Docker engine |
| 3. Macvlan | Create/detect network | Host | Docker network |
| 4. Download files | Fetch compose files, operator scripts | Host | `docker-compose*.yml`, `operator/lib/*.sh` |
| 5. Secrets | Generate passwords, keys | Host | `.env` |
| 6. SSL | Obtain/generate certificates | Host | `certs/`, `nginx.ssl.conf` |
| 7. Start | Pull images, start containers | Host→Docker | Running containers |
| 8. Configure | Set admin password, OAuth, embeddings | Container (operator) | Database config |

### operator.sh Command Matrix

| Command | Runs On | Uses | Description |
|---------|---------|------|-------------|
| `init` | Host | `lib/guided-init.sh` or `lib/headless-init.sh` | Interactive / headless setup (repo mode only) |
| `start` | Host | `cmd_start_infra` + container `database/migrate-db.sh` | Start platform (infra + migrations + app) |
| `stop` | Host | docker compose stop | Stop platform or specific service (`--keep-infra` available) |
| `restart` | Host | docker compose restart | Restart a service (or `all`) |
| `upgrade` | Host | inline upgrade flow + `check_pg_major_compatibility` | Pull/build, migrate, restart with PG major-version safety gate |
| `update` | Host | docker compose pull / build | Pull (or build, in local mode) images only |
| `status` | Host | docker ps | Show container status |
| `versions` | Host | OCI labels + GHCR API | Show running/local/remote image versions |
| `logs` | Host | docker compose logs | View logs (default service: api) |
| `shell` | Container | `docker exec -it kg-operator /bin/bash` | Enter operator container |
| `teardown` | Host | docker compose down (`--full` adds `-v`) | Remove containers (optionally volumes) |
| `recert` | Container | `operator/lib/recert.sh` | Renew SSL certificates |
| `admin` | Container | configure.py admin | Admin user management |
| `ai-provider` | Container | configure.py ai-provider | Configure AI extraction |
| `embedding` | Container | configure.py embedding | Configure embeddings |
| `api-key` | Container | configure.py api-key | Manage API keys |
| `query` / `pg` | Host | docker compose exec postgres psql | Run an SQL query against PostgreSQL |
| `garage` | Container | `operator/lib/garage-manager.sh` | Manage Garage storage (status, init, repair) |
| `self-update` | Host | `docker cp` + `docker pull` | Update operator.sh from container + pull latest operator image |

### Execution Locations

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST                                     │
│                                                                  │
│  install.sh ─────────────────────────────────────────────────►  │
│       │                                                          │
│       ├─► Downloads: operator.sh, operator/lib/*.sh              │
│       ├─► Creates: .env, docker-compose.ssl.yml, certs/          │
│       └─► Runs: docker compose up                                │
│                                                                  │
│  operator.sh ────────────────────────────────────────────────►  │
│       │                                                          │
│       ├─► Host scripts: start, stop, upgrade, logs, status       │
│       │       Uses: operator/lib/*.sh (downloaded by install.sh) │
│       │                                                          │
│       └─► Container exec: shell, admin, ai-provider, embedding   │
│               │                                                  │
│               ▼                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    kg-operator CONTAINER                    │ │
│  │                                                             │ │
│  │   /workspace/operator/configure.py ── Database config       │ │
│  │   /workspace/operator/lib/*.sh ─────── Helper scripts       │ │
│  │   /workspace/operator/database/*.sh ── Migrations/backups   │ │
│  │   /etc/kg/operator.sh ──────────────── Trusted shim copy    │ │
│  │                                                             │ │
│  │   WORKDIR is /workspace. In dev mode the host repo is       │ │
│  │   bind-mounted to /workspace; in standalone mode the same   │ │
│  │   paths are baked into the image (no separate /app/         │ │
│  │   prefix).                                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Issues with Current Architecture

### 1. Script Duplication (standalone installs)
- In **standalone** installs, `operator/lib/*.sh` exists in two places:
  - Host filesystem (downloaded by install.sh)
  - Operator container image (baked in at build)
- They must be kept in sync.
- In **dev** installs the host repo is bind-mounted to `/workspace`, so the
  container sees the same files as the host and there is no duplication.

### 2. Permission Problems
- install.sh downloads scripts via curl (no execute bit)
- Fixed by adding chmod, but fragile

### 3. Mixed Execution Model
- Some commands run on host (start/stop/restart/upgrade/teardown/update/status/
  versions/logs/query), others in container (admin/ai-provider/embedding/
  api-key/garage/recert/shell).
- Host scripts need Docker socket access via the local Docker CLI; container
  scripts use the mounted `/var/run/docker.sock` to manage sibling containers.

## Proposed Architecture (Future)

### Option A: Container-First
Move all operations into the operator container:

```
operator.sh (thin shim)
    └─► ALL commands → docker exec kg-operator operator-cli <command>

kg-operator container:
    ├─► operator-cli start/stop/upgrade (controls sibling containers)
    ├─► operator-cli admin/ai-provider/embedding (database config)
    └─► Mounts docker socket for container control
```

**Pros**: Single execution environment, simpler install.sh, no permission issues
**Cons**: Requires docker socket mount, security considerations

### Option B: Clear Host/Container Split
Make the split explicit and intentional:

```
operator.sh:
    ├─► Infrastructure commands (start/stop/upgrade) → Host scripts
    └─► Configuration commands (admin/ai-provider) → Container exec

Host scripts bundled in operator.sh itself (no separate lib/ files)
```

**Pros**: No downloaded scripts, clear separation
**Cons**: Large operator.sh, still mixed model

### Option C: Install-time vs Runtime Split
```
install.sh:
    └─► Full installation including first start

operator.sh:
    └─► Runtime management only (all via container exec)
    └─► For infrastructure changes, re-run install.sh with flags
```

**Pros**: Clean separation, operator.sh is trivial
**Cons**: install.sh becomes the primary tool

## Files Inventory

### Downloaded by install.sh to Host (standalone installs)
```
knowledge-graph/
├── .env                          # Secrets (generated)
├── .operator.conf                # Operator configuration (DEV_MODE, GPU_MODE,
│                                 # IMAGE_SOURCE, etc.)
├── operator.sh                   # Management shim (also embeds VERSION)
├── docker/
│   ├── docker-compose.yml        # Base compose (postgres, garage, api, web,
│   │                             # operator)
│   ├── docker-compose.prod.yml   # Production overrides
│   ├── docker-compose.ghcr.yml   # GHCR image references
│   ├── docker-compose.standalone.yml  # Removes dev mounts (standalone mode)
│   ├── docker-compose.ssl.yml    # SSL overlay (if SSL configured)
│   ├── docker-compose.gpu-*.yml  # GPU overlays (nvidia / amd / amd-host)
│   ├── docker-compose.override.mac.yml  # macOS (MPS) overlay
│   └── nginx.prod.conf
├── certs/                        # SSL certificates (if SSL configured)
├── operator/
│   ├── configure.py              # Python config tool
│   ├── lib/                      # common, start-{infra,app,platform},
│   │                             # stop, upgrade, teardown, garage-manager,
│   │                             # guided-init, headless-init,
│   │                             # init-secrets, image-tag, operator-help
│   └── database/                 # migrate-db.sh, backup-database.sh,
│                                 # restore-database.sh
├── schema/
│   ├── 00_baseline.sql
│   ├── 11_graph_accel.sql
│   ├── init.cypher
│   ├── migrations/*.sql
│   └── migrations-warm/*.sql
└── config/
    └── garage.toml               # Garage server config
```

In **dev (repo) installs**, the same files are checked out in-place from the
repo and the operator container bind-mounts the repo root to `/workspace`,
so there is no separate "downloaded" copy.

### Baked into kg-operator Container Image
```
/workspace/                          # WORKDIR (also bind-mounted in dev mode)
├── operator/
│   ├── configure.py
│   ├── lib/*.sh                     # common, start-*, stop, upgrade, teardown,
│   │                                # garage-manager, guided-init, headless-init,
│   │                                # init-secrets, image-tag, operator-help
│   └── database/                    # migrate-db.sh, backup-database.sh,
│                                    # restore-database.sh
├── api/app/lib/                     # Subset of API libs imported by configure.py
├── schema/
│   ├── 00_baseline.sql
│   ├── 11_graph_accel.sql
│   ├── migrations/*.sql             # Forward migrations (numbered)
│   └── migrations-warm/*.sql        # Warm-cluster migrations
└── scripts/development/             # Diagnostics for shell sessions

/etc/kg/
└── operator.sh                      # Trusted copy for self-update extraction
```

### File path note: `/app/` vs `/workspace/`

The operator container's `WORKDIR` is `/workspace`. Earlier drafts of this
document referenced `/app/operator/...`; that path does not exist in the
shipping image. All operator code (scripts, configure.py, database tools) lives
under `/workspace/operator/`, which is what `operator.sh` invokes via
`docker exec kg-operator ...`.
