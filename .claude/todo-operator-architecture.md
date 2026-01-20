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
│  operator.sh (thin shim on HOST)                                            │
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
│  kg-operator container (has ALL logic)                                      │
│                                                                             │
│  Includes:                                                                  │
│    - docker.io CLI (controls sibling containers via socket mount)           │
│    - postgresql-client (psql for migrations)                                │
│    - Python + configure.py (admin, ai-provider, embedding, api-key)         │
│    - /workspace/operator/lib/*.sh scripts                                   │
│    - /workspace/operator/database/*.sh migrations                           │
│    - /workspace/schema/*.sql                                                │
│                                                                             │
│  Key scripts:                                                               │
│    start-platform.sh - Wait for infra, run migrations, init garage,         │
│                        start api+web via docker compose                     │
│    upgrade.sh        - Pull images, stop app, migrate, restart              │
│    migrate-db.sh     - Apply schema migrations                              │
│                                                                             │
│  Mounted:                                                                   │
│    /var/run/docker.sock - Control sibling containers                        │
│    /app/.env            - Environment variables                             │
│    /app/docker/         - Compose files (standalone installs)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Architecture

1. **Thin shim avoids permission issues** - No downloaded scripts need chmod
2. **All complex logic in container** - Easy to update, test, version
3. **install.sh is just bootstrap + guided config** - Not ongoing dependency
4. **Operator container is self-sufficient** - Has docker CLI, can manage everything

## Immediate Issues

- [ ] Fix cube nginx.prod.conf directory issue
- [ ] Decide: Should prod.yml reference nginx config at all, or only ssl.yml?

## Implementation Tasks

### Phase 1: Thin operator.sh (DONE)
- [x] Rewrite operator.sh as thin shim (~200 lines)
- [x] Create /workspace/operator/lib/start-platform.sh

### Phase 2: Container Scripts
- [ ] Verify upgrade.sh works with docker socket in container
- [ ] Test start-platform.sh from inside container
- [ ] Fix paths: container uses /workspace not /app

### Phase 3: Install.sh Simplification
- [ ] Remove lib/*.sh downloads from install.sh (not needed)
- [ ] install.sh delegates config to container after bootstrap
- [ ] Verify --headless parameters work with container delegation

### Phase 4: Testing
- [ ] Fresh standalone install on clean system
- [ ] Upgrade from 0.5.0 to 0.6.0
- [ ] Macvlan install with DHCP mode
- [ ] Macvlan install with static IP mode

## Compose File Cleanup

- [ ] Audit what each compose file does:
  - docker-compose.yml (base)
  - docker-compose.prod.yml (production overrides)
  - docker-compose.ghcr.yml (image references)
  - docker-compose.ssl.yml (SSL config)
  - docker-compose.gpu-*.yml (GPU support)
- [ ] Ensure SSL mode doesn't conflict with prod.yml nginx mount
- [ ] Document compose file stacking order

## Release/Version Alignment

- [x] Create docs/RELEASES.md with version matrix
- [ ] Tag kg-operator with version numbers (currently only has 'latest' and '0.4.0')
- [ ] Merge main to release branch to trigger operator build
- [ ] Ensure all three images have matching version tags

## Documentation

- [x] Create OPERATOR_ARCHITECTURE.md
- [ ] Update installation docs after architecture finalized
- [ ] Document compose file relationships
