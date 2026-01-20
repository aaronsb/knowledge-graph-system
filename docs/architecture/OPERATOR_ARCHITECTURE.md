# Operator Architecture

## Overview

The Knowledge Graph platform uses two main tools for installation and operation:

1. **install.sh** - One-time bootstrapper that sets up the platform
2. **operator.sh** - Day-to-day management tool

## Current Architecture

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
| `init` | Host | `lib/guided-init.sh` | Interactive setup (dev mode) |
| `start` | Host | `lib/start-infra.sh`, `lib/start-app.sh` | Start platform |
| `stop` | Host | `lib/stop.sh` | Stop platform |
| `restart` | Host | stop + start | Restart platform |
| `upgrade` | Host | `lib/upgrade.sh` | Pull images, migrate, restart |
| `update` | Host | docker compose pull | Pull images only |
| `status` | Host | docker compose ps | Show container status |
| `logs` | Host | docker compose logs | View logs |
| `shell` | Container | docker exec | Enter operator container |
| `teardown` | Host | `lib/teardown.sh` | Remove platform |
| `recert` | Host | acme.sh | Renew SSL certificates |
| `admin` | Container | configure.py | Admin user management |
| `ai-provider` | Container | configure.py | Configure AI extraction |
| `embedding` | Container | configure.py | Configure embeddings |
| `api-key` | Container | configure.py | Manage API keys |

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
│  │   configure.py ─── Direct database/API access               │ │
│  │   /app/operator/lib/*.sh ─── Baked into image               │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Issues with Current Architecture

### 1. Script Duplication
- `operator/lib/*.sh` exists in both:
  - Host filesystem (downloaded by install.sh)
  - Operator container image (baked in at build)
- Must keep both in sync

### 2. Permission Problems
- install.sh downloads scripts via curl (no execute bit)
- Fixed by adding chmod, but fragile

### 3. Mixed Execution Model
- Some commands run on host, some in container
- Confusing mental model
- Host scripts need docker socket access

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

### Downloaded by install.sh to Host
```
knowledge-graph/
├── .env                          # Secrets
├── .operator.conf                # Configuration
├── docker-compose.yml            # Base compose
├── docker-compose.prod.yml       # Production overrides
├── docker-compose.ghcr.yml       # GHCR image references
├── docker-compose.ssl.yml        # SSL configuration
├── nginx.ssl.conf                # Nginx HTTPS config
├── certs/                        # SSL certificates
├── operator.sh                   # Management shim
├── operator/
│   ├── configure.py              # Python config tool
│   ├── lib/
│   │   ├── common.sh
│   │   ├── start-infra.sh
│   │   ├── start-app.sh
│   │   ├── stop.sh
│   │   ├── upgrade.sh
│   │   └── teardown.sh
│   └── database/
│       ├── migrate-db.sh
│       └── backup-database.sh
└── schema/
    └── 00_baseline.sql
```

### Baked into kg-operator Container Image
```
/app/
├── operator/
│   ├── configure.py
│   └── lib/*.sh
└── schema/
    ├── 00_baseline.sql
    └── migrations/*.sql
```
