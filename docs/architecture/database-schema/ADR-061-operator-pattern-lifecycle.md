---
status: Accepted
date: 2025-01-07
---

# ADR-061: Operator Pattern for Platform Lifecycle Management

## Overview

Imagine a platform with 35 different shell scripts scattered across multiple directories, each handling some piece of setup or configuration. Want to get started? Well, first run this script to set up secrets, then that script to start the database, then another to configure AI providers, then... wait, which order were they supposed to run in again? And did you remember to edit the `.env` file before starting the API, or was that supposed to happen automatically?

This was the reality we faced: script sprawl had made the system nearly impossible to use. Worse, the scripts violated fundamental architectural boundaries—some tried to both generate infrastructure secrets (like encryption keys) AND configure application settings (like which AI model to use), mixing concerns that should have been cleanly separated. The result was brittle, confusing, and frequently broke when scripts ran in the wrong order.

We needed a single, clear entry point that understood the proper layers of system initialization. Think of it like the Kubernetes operator pattern: one unified interface that knows infrastructure comes before schema, schema comes before configuration, and configuration must happen before the application starts. The solution is `kg-operator`, a command-line tool that orchestrates the entire platform lifecycle through four distinct layers: infrastructure secrets (generated once), database schema (automatically applied), application configuration (stored in the database, not files), and finally the running application.

The key insight is separating what belongs in environment variables (infrastructure secrets that never change) from what belongs in database records (application configuration that changes frequently). With this boundary clear, Docker images can be completely clean—no runtime file editing, no secrets baked into containers. Everything follows the twelve-factor app model: infrastructure secrets flow from the environment, application config loads from the database at startup, and the operator container itself can manage the platform using standard Docker APIs. It's a dramatic simplification that turns chaos into clarity.

---

## Context

### The Problem: Script Sprawl and Architectural Confusion

The system evolved 35+ shell scripts across multiple directories (`scripts/services/`, `scripts/setup/`, `scripts/admin/`, etc.), creating several critical problems:

1. **No clear entry point** - Users had to understand which script to run when
2. **Unclear responsibility boundaries** - Scripts mixed infrastructure setup (.env file editing) with application configuration (database records)
3. **Wrong execution order** - Easy to start API before database was configured, leading to inconsistent state
4. **Duplicate logic** - Multiple scripts doing similar things (start-api.sh, start-database.sh, bootstrap.sh, initialize-platform.sh)
5. **Docker vs host confusion** - Scripts tried to support both modes, making them complex and fragile

### The Core Architectural Problem

**initialize-platform.sh tried to do two incompatible things:**
1. Edit infrastructure files (.env, docker-compose.yml) - Infrastructure layer
2. Configure database records (admin users, AI providers) - Application layer

This violated separation of concerns and made it impossible to have clean Docker builds where **all secrets come from the environment, not files that get edited at runtime**.

### What We Learned

From the failed `feature/containerization-strategy` branch (6000+ lines changed), we learned:

1. **Bootstrap sequencing is critical**: Database → Migrations → **Configuration** → API start (config MUST happen before API boots)
2. **The operator pattern works**: Single CLI that orchestrates everything
3. **Configuration belongs in the database**: Not in .env files that get edited post-deployment
4. **Simplicity wins**: Too many abstraction layers (operator → bootstrap → initialize → config managers) made debugging impossible

## Decision

### Adopt the Kubernetes Operator Pattern

Create a **single user-facing CLI** (`kg-operator`) that manages the entire platform lifecycle through clean, layered architecture.

### The Four Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Infrastructure (One-Time Setup)                    │
│ ─────────────────────────────────────────────────────────── │
│ • Generate secrets: ENCRYPTION_KEY, OAUTH_SIGNING_KEY       │
│ • Set database password: POSTGRES_PASSWORD                  │
│ • Configure Garage RPC secret: GARAGE_RPC_SECRET            │
│                                                              │
│ Tool: kg-operator init --dev                                │
│ Output: .env file (NEVER edited again)                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Schema (Automatic)                                 │
│ ─────────────────────────────────────────────────────────── │
│ • Postgres container starts                                 │
│ • Auto-runs migrations from schema/migrations/              │
│ • Creates tables: kg_api.users, ai_provider_config, etc.    │
│                                                              │
│ Tool: docker-compose up -d postgres (migrations automatic)  │
│ Output: Database schema ready                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Configuration (Operator's Job)                     │
│ ─────────────────────────────────────────────────────────── │
│ • Create admin user in database                             │
│ • Configure AI providers (OpenAI/Anthropic for extraction)  │
│ • Configure embedding provider (OpenAI/Local)               │
│ • Store encrypted API keys (using ENCRYPTION_KEY from env)  │
│ • Configure Garage credentials (encrypted)                  │
│                                                              │
│ Tool: kg-operator config <subcommand>                       │
│ Output: Database records (application config)               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Application (After Config Ready)                   │
│ ─────────────────────────────────────────────────────────── │
│ • API server starts                                         │
│ • Reads ENCRYPTION_KEY from environment (to decrypt keys)   │
│ • Reads all other config from database                      │
│ • Viz app starts (talks to API)                             │
│                                                              │
│ Tool: kg-operator start --app-only                          │
│ Output: Running application                                 │
└─────────────────────────────────────────────────────────────┘
```

### The kg-operator CLI

**Single user interface for everything:**

```bash
# kg-operator is a shell script that delegates to the operator container
# Example: kg-operator config admin → docker exec kg-operator configure.py admin

# Initial setup (one time)
kg-operator init --dev              # Generate .env secrets (host-side script)
kg-operator start --infra-only      # Start postgres + garage
kg-operator config admin            # Configure admin (via container)
kg-operator config ai-provider openai
kg-operator config embedding local
kg-operator start --app-only        # Start API + viz

# Daily workflow
kg-operator start                   # Start everything
kg-operator status                  # Check health (queries containers)
kg-operator stop                    # Clean shutdown

# Maintenance
kg-operator backup                  # Backup database (via container)
kg-operator restore backup.sql      # Restore from backup (via container)
```

**How delegation works:**

```bash
# operator/kg-operator (shell wrapper)
case $command in
    init)
        # Run init-secrets.sh on host (needs to write .env)
        exec operator/lib/init-secrets.sh "$@"
        ;;
    config)
        # Delegate to operator container
        docker exec kg-operator python /app/configure.py "$@"
        ;;
    start)
        # Operator container uses Docker socket to start others
        docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            kg-operator:latest start "$@"
        ;;
esac
```

### Container Architecture

**The operator runs as a container in the cluster:**

```
Docker Network: knowledge-graph-system
├── kg-postgres-dev       (PostgreSQL + AGE)
├── kg-garage-dev         (S3-compatible storage)
├── kg-api-dev            (FastAPI server) ← exposed :8000
├── kg-viz-dev            (React app) ← exposed :3000
└── kg-operator           (Operator container)
    ├── Access to Docker socket (/var/run/docker.sock)
    ├── Can start/stop other containers
    ├── Connects to postgres via network
    └── Runs configuration commands
```

**Why operator-as-container:**
1. **Consistent environment** - Same Python/tools everywhere
2. **Network access** - Can connect to postgres directly (no localhost/port mapping)
3. **Docker socket access** - Can manage other containers via Docker API
4. **Clean separation** - Operator is infrastructure, not application
5. **Future: nginx** - Easy to add reverse proxy to the cluster

**Repository Structure (Post-Restructure):**

```
/
├── api/                     # FastAPI server (was src/)
├── operator/                # Platform lifecycle (was scripts/)
│   ├── kg-operator          # 👈 User-facing CLI wrapper
│   ├── lib/                 # Internal implementation (hidden from users)
│   │   ├── init-secrets.sh  # Generate infrastructure secrets
│   │   ├── start-infra.sh   # Start postgres + garage
│   │   ├── start-app.sh     # Start api + viz (after config)
│   │   ├── stop.sh          # Clean shutdown
│   │   ├── backup-db.sh
│   │   └── restore-db.sh
│   ├── configure.py         # Python database config tool
│   ├── Dockerfile           # Operator container (future)
│   ├── requirements.txt     # Python dependencies
│   ├── development/         # Developer tools
│   │   └── test/
│   └── diagnostics/         # Debugging tools
├── cli/                     # kg CLI + MCP server (was client/)
├── web/                     # React visualization (was viz-app/)
├── docker/                  # Docker compose files
│   ├── docker-compose.yml
│   └── docker-compose.ollama.yml
├── schema/                  # Database schemas & migrations
└── docs/                    # Documentation
```

### Configuration Responsibility Boundaries

#### Infrastructure Layer (.env file)
**Managed by:** `kg-operator init`
**Set once, never edited:**
- `ENCRYPTION_KEY` - Master key for encrypting API keys at rest
- `OAUTH_SIGNING_KEY` - Secret for signing JWT tokens
- `POSTGRES_PASSWORD` - Database admin password
- `GARAGE_RPC_SECRET` - Garage cluster coordination

#### Application Layer (Database records)
**Managed by:** `kg-operator config`
**Changed frequently:**
- Admin user credentials (`kg_api.users`)
- AI provider settings (`kg_api.ai_provider_config`)
- Embedding provider (`kg_api.embedding_config`)
- API keys - encrypted (`kg_api.system_api_keys`)
- Garage credentials - encrypted (`kg_api.system_api_keys`)

### The configure.py Tool

**Python tool that ONLY talks to the database:**

```python
# operator/configure.py
import psycopg2
from api.app.lib.encryption import encrypt_credential

class Operator:
    def __init__(self):
        # Reads connection info from environment
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            password=os.getenv("POSTGRES_PASSWORD")
        )

    def config_admin(self, username, password):
        """Create/update admin user in database"""
        hashed = bcrypt.hashpw(password.encode())
        self.conn.execute(
            "UPDATE kg_api.users SET password_hash = %s WHERE username = %s",
            (hashed, username)
        )

    def config_ai_provider(self, provider, model):
        """Configure AI extraction provider in database"""
        self.conn.execute(
            "INSERT INTO kg_api.ai_provider_config (provider, model, active) "
            "VALUES (%s, %s, true)",
            (provider, model)
        )

    def store_api_key(self, provider, key):
        """Encrypt and store API key in database"""
        # Uses ENCRYPTION_KEY from environment to encrypt
        encrypted = encrypt_credential(key)
        self.conn.execute(
            "INSERT INTO kg_api.system_api_keys (provider, encrypted_key) "
            "VALUES (%s, %s)",
            (provider, encrypted)
        )
```

**Key principle:** The operator NEVER edits .env files or docker-compose.yml. It only writes to the database.

### Clean Docker Builds

With this architecture, Docker images are completely clean:

**API Server Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY api/ ./api/
COPY schema/ ./schema/

# No secrets in image!
# All secrets come from environment at runtime

CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0"]
```

**docker-compose.yml:**
```yaml
services:
  api:
    build: .
    environment:
      # Infrastructure secrets (from .env or CI/CD)
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      OAUTH_SIGNING_KEY: ${OAUTH_SIGNING_KEY}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

      # Database connection
      POSTGRES_HOST: postgres

      # Application config comes from database, not environment!
```

**API server reads config at startup:**
```python
# api/api/main.py
from api.app.lib.config import load_config

# Infrastructure secrets from environment
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # For decrypting API keys

# Application config from database
config = load_config()  # Reads kg_api.ai_provider_config, etc.
ai_provider = config.extraction_provider  # e.g., "openai"
api_key_encrypted = config.api_keys["openai"]  # From database
api_key = decrypt(api_key_encrypted, ENCRYPTION_KEY)  # Decrypt
```

### The .env File Role

**.env is relegated to "override for host-mode development only":**

**Docker mode (primary):**
- Secrets come from Docker secrets, CI/CD environment, or .env sourced by docker-compose
- .env file exists but is ONLY read by docker-compose, not edited by scripts

**Host mode (fallback):**
- Developers running API on host (not in Docker) can use .env
- Allows local development without Docker
- Still follows same pattern: infrastructure secrets in .env, app config in database

## Consequences

### Positive

1. **Single entry point** - Users only learn `kg-operator`, not 35 different scripts
2. **Clear layer separation** - Infrastructure setup is separate from application configuration
3. **Correct execution order** - Operator enforces: infra → schema → config → app
4. **Clean Docker builds** - No runtime file editing, all secrets from environment
5. **Easier debugging** - `kg-operator status` shows entire system state
6. **Better testing** - Internal lib scripts can be tested independently
7. **Host mode still works** - .env fallback preserves local development workflow

### Negative

1. **Users must learn new workflow** - Existing bootstrap.sh users need to migrate
2. **More upfront architecture** - Requires discipline to maintain layer boundaries
3. **Python dependency** - configure.py requires Python + psycopg2 (acceptable tradeoff)

### Migration Path

**Deprecated (to be removed):**
- ❌ `operator/setup/bootstrap.sh` → Use `kg-operator init && kg-operator start`
- ❌ `operator/setup/initialize-platform.sh` → Use `kg-operator config`
- ❌ `operator/admin/set-admin-password.sh` → Use `kg-operator config admin`
- ❌ `operator/garage/init-garage.sh` → Use `kg-operator config garage`

**Moved to development tools:**
- 📦 `operator/services/start-*.sh` (8 files) → `scripts/development/local/run-*-local.sh` (for manual debugging only)

**Kept (developer tools):**
- ✅ `operator/development/test/` - Testing tools
- ✅ `scripts/development/diagnostics/` - Debugging tools (monitor-db.sh, garage-status.sh, lint_queries.py)
- ✅ `scripts/development/local/` - Manual service scripts for deep debugging (not for normal workflow)

**Moved to internal lib:**
- 📦 `operator/database/backup-database.sh` → `operator/lib/backup-db.sh`
- 📦 `operator/database/restore-database.sh` → `operator/lib/restore-db.sh`
- 📦 `operator/database/migrate-db.sh` → Automatic (postgres runs on startup)

### Rollout Plan

**Phase 1: Create operator infrastructure** ✅ COMPLETE
- [x] Create `operator/kg-operator` CLI
- [x] Create `operator/lib/init-secrets.sh`
- [x] Restructure repository (src→api, scripts→operator, client→cli, viz-app→web)
- [x] Create `operator/configure.py` (Python database config tool)
- [x] Create `operator/lib/start-infra.sh`
- [x] Create `operator/lib/start-app.sh`
- [x] Create `operator/lib/stop.sh`

**Phase 2: Update Docker builds** ✅ COMPLETE
- [x] Create `operator/Dockerfile` (operator container)
- [x] Update `docker/docker-compose.yml` to include all services (postgres, garage, api, web, operator)
- [x] Create clean API Dockerfile (no secrets baked in)
- [x] Update `web/Dockerfile` to be clean (already was clean)

**Phase 3: Documentation**
- [ ] Update `docs/guides/GETTING-STARTED.md` to use kg-operator
- [ ] Update `CLAUDE.md` with new workflow
- [ ] Create migration guide for existing users

**Phase 4: Deprecation**
- [ ] Mark old scripts as deprecated
- [ ] Remove after one release cycle

### Update/Upgrade Lifecycle (Added 2026-01-19)

Following the familiar Linux package manager pattern:

```bash
./operator.sh update [service]   # Pull latest images (like apt update)
./operator.sh upgrade            # Pull, migrate, restart (like apt upgrade)
```

**Update** - Fetch without applying:
```bash
./operator.sh update             # Pull all images from GHCR
./operator.sh update operator    # Pull only operator image
./operator.sh update api         # Pull only API image
```

**Upgrade** - Full lifecycle:
1. Pre-flight checks (verify .env, .operator.conf)
2. Optional pre-upgrade backup
3. Pull new images
4. Stop application containers (keep postgres/garage running)
5. Run database migrations
6. Start application with new images
7. Health check

**Version Management Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│  operator.sh (host)                                         │
│  - Thin shim, rarely changes                                │
│  - Delegates to operator container for logic                │
│  - Handles: start/stop, exec into container, compose calls  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  operator container (source of truth)                       │
│                                                             │
│  Contains:                                                  │
│    - Database migration scripts                             │
│    - Configuration tools (configure.py)                     │
│    - Version compatibility knowledge (future: manifest)     │
│                                                             │
│  Future evolution:                                          │
│    - /versions endpoint for compatible image versions       │
│    - Automatic compatibility checking during upgrade        │
│    - Rollback support with version pinning                  │
└─────────────────────────────────────────────────────────────┘
```

**Standalone Install Support:**

For deployments via `install.sh` (not from git repo), operator.sh detects the environment:

1. **`.operator.conf`** - Created by installer with:
   - `CONTAINER_PREFIX=kg` (container naming)
   - `IMAGE_SOURCE=ghcr` (pull from registry)
   - `DEV_MODE=false`

2. **DOCKER_DIR detection** - Scripts auto-detect:
   - Repo install: `$PROJECT_ROOT/docker/`
   - Standalone: `$PROJECT_ROOT/` (compose files in root)

3. **GHCR overlay** - Standalone uses `docker-compose.ghcr.yml` for image paths

**Infrastructure vs Application Updates:**

| Component | Update Method | Notes |
|-----------|--------------|-------|
| api, web, operator | `update` + `restart` | Our images, freely updatable |
| postgres, garage | Manual | Versions pinned in compose, require careful migration |

For postgres/garage, operator provides guidance:
```bash
$ ./operator.sh update postgres
postgres version is pinned in docker-compose.yml

To update postgres:
  1. Edit docker-compose.yml and update the image tag
  2. ./operator.sh update postgres  # Pull new version
  3. ./operator.sh restart postgres # Apply (caution: may need migration)

Warning: PostgreSQL upgrades may require data migration
Back up your data before upgrading: operator/database/backup-database.sh
```

## Related ADRs

- **ADR-031:** Encrypted Credential Storage (ENCRYPTION_KEY usage)
- **ADR-054:** OAuth 2.0 Authentication (OAUTH_SIGNING_KEY usage)
- **ADR-040:** Database Schema Migration Management (automatic migrations)
- **ADR-057:** Garage Object Storage (configuration via operator)
- **ADR-086:** Deployment Topology (standalone installer, GHCR images)

## References

- Kubernetes Operator Pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- 12-Factor App - Config: https://12factor.net/config
- Docker Secrets: https://docs.docker.com/engine/swarm/secrets/

---

**Why this matters:** This ADR establishes the foundational pattern for how the platform is deployed, configured, and managed. Getting this right enables clean Docker builds, CI/CD automation, and a vastly simpler user experience.
