# Operator Architecture Cleanup

## Context
The current install.sh and operator.sh have overlapping responsibilities and mixed execution models (host vs container). This creates permission issues, duplication, and confusion.

See: `docs/architecture/OPERATOR_ARCHITECTURE.md`

## Chosen Architecture: Thin Shim + Container Delegation

**Principle: Minimal host logic, delegate everything possible to operator container**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  install.sh (one-time guided bootstrap)                                     │
│                                                                             │
│  1. Downloads: operator.sh, compose files, schema                           │
│  2. Generates: .env (secrets)                                               │
│  3. Configures: SSL (certs, nginx config)                                   │
│  4. Bootstraps: docker compose up postgres garage operator                  │
│  5. Delegates config to container (admin password, AI provider, etc.)       │
│  6. Shows summary                                                           │
│                                                                             │
│  Supports both interactive mode and --flags for automation                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  operator.sh (thin shim on HOST, ~200 lines)                                │
│                                                                             │
│  HOST-ONLY (bootstrap, can't run in container):                             │
│    start_infra - docker compose up postgres garage operator                 │
│    stop        - docker compose stop                                        │
│    teardown    - docker compose down [-v]                                   │
│    update      - docker compose pull                                        │
│    logs        - docker logs <container>                                    │
│    restart     - docker restart <container>                                 │
│    status      - docker ps                                                  │
│                                                                             │
│  DELEGATED TO CONTAINER (via docker exec kg-operator ...):                  │
│    start       - /workspace/operator/lib/start-platform.sh                  │
│    upgrade     - /workspace/operator/lib/upgrade.sh                         │
│    admin       - python /workspace/operator/configure.py admin              │
│    ai-provider - python /workspace/operator/configure.py ai-provider        │
│    embedding   - python /workspace/operator/configure.py embedding          │
│    api-key     - python /workspace/operator/configure.py api-key            │
│    recert      - /workspace/operator/lib/recert.sh                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  kg-operator container (TOOLBOX - has ALL logic and dependencies)           │
│                                                                             │
│  Dependencies (no host installation required):                              │
│    - Python 3.11 + libraries (encryption, DB access, configure.py)          │
│    - docker.io CLI (controls sibling containers via socket mount)           │
│    - postgresql-client (psql, pg_isready for migrations)                    │
│    - curl (health checks)                                                   │
│    - Future: acme.sh, backup tools, etc.                                    │
│                                                                             │
│  Scripts:                                                                   │
│    /workspace/operator/lib/start-platform.sh - migrations, garage, api/web  │
│    /workspace/operator/lib/upgrade.sh - pull, stop, migrate, restart        │
│    /workspace/operator/database/migrate-db.sh - schema migrations           │
│    /workspace/operator/configure.py - admin, ai-provider, embedding, keys   │
│                                                                             │
│  Mounts:                                                                    │
│    /var/run/docker.sock - Control sibling containers                        │
│    /workspace           - Project root (compose files, .env, scripts)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture

1. **Thin shim avoids permission issues** - No downloaded scripts need chmod
2. **All complex logic in container** - Easy to update, test, version
3. **Container is the toolbox** - Python, psql, docker CLI all pre-installed
4. **Host only needs bash + docker** - No other dependencies required
5. **Like Watchtower** - Container manages siblings via docker socket
6. **install.sh is just bootstrap** - Not an ongoing dependency

## Implementation Tasks

### Phase 1: Thin operator.sh ✅ DONE
- [x] Rewrite operator.sh as thin shim (~200 lines)
- [x] Create /workspace/operator/lib/start-platform.sh
- [x] Fix paths to use /workspace (not /app)

### Phase 2: Container Scripts ✅ DONE
- [x] Create start-platform.sh for container-side startup
- [x] Verify paths work (/workspace/operator/lib/*)
- [x] upgrade.sh works (uses common.sh, auto-detects paths)

### Phase 3: Install.sh Simplification ✅ DONE
- [x] Remove lib/*.sh downloads from install.sh (container has them)
- [x] install.sh delegates config to container after bootstrap
- [x] Fix container naming (dev vs standalone modes)
- [x] Fix TTY handling for non-interactive contexts

### Phase 4: Testing ← CURRENT
- [x] Local dev environment - operator.sh commands work
- [x] Fresh standalone install on cube (2026-01-20)
- [x] Macvlan install with static IP (DHCP mode has Docker MAC limitations)
- [ ] Push new operator image to GHCR (requires merge to release)
- [ ] Upgrade from 0.5.0 to 0.6.0

**Macvlan findings (2026-01-20):**
- Docker's `mac_address` compose option doesn't work for multi-network containers
- Each network interface gets a random MAC, breaking DHCP reservations
- Solution: Use static IP (`ipv4_address`) in compose overlay instead of DHCP
- Host cannot reach its own macvlan containers (expected layer 2 isolation)
- Documented in `docs/operating/macvlan-headless-install.md`

## Other Tasks

### Immediate Issues
- [ ] Fix cube nginx.prod.conf directory issue
- [ ] Decide: Should prod.yml reference nginx config at all, or only ssl.yml?

### Compose File Cleanup
- [ ] Audit compose file stack order and dependencies
- [ ] Ensure SSL mode doesn't conflict with prod.yml nginx mount
- [ ] Document compose file relationships

### Release/Version Alignment
- [x] Create docs/RELEASES.md with version matrix
- [ ] Tag kg-operator with version numbers (currently only 'latest' and '0.4.0')
- [ ] Merge to release branch to trigger operator build
- [ ] Ensure all three images have matching version tags

### Documentation
- [x] Create OPERATOR_ARCHITECTURE.md
- [x] Create docs/operating/macvlan-headless-install.md (2026-01-20)
- [ ] Update installation docs after architecture finalized
