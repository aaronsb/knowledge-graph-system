# Operator Architecture Cleanup

## Context
The current install.sh and operator.sh have overlapping responsibilities and mixed execution models (host vs container). This creates permission issues, duplication, and confusion.

See: `docs/architecture/OPERATOR_ARCHITECTURE.md`

## Immediate Issues

- [ ] Fix cube upgrade failure (nginx.prod.conf became directory)
- [ ] Decide: Should prod.yml reference nginx config at all, or only ssl.yml?

## Script Permission Issues

- [x] Add chmod +x for downloaded .sh files in install.sh
- [ ] Verify all operator/lib/*.sh are executable in repo (they are: 755)
- [ ] Test fresh install to confirm permissions work

## Chosen Approach: Self-Contained operator.sh

**Principle: Host controls infrastructure, container handles configuration**

```
┌─────────────────────────────────────────────────────────────┐
│  install.sh (one-time bootstrap)                            │
│    - Downloads: operator.sh, compose files, schema          │
│    - Creates: .env, certs, nginx config                     │
│    - Pulls images, starts containers                        │
│    - Does NOT download operator/lib/*.sh                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  operator.sh (self-contained, no external lib files)        │
│                                                             │
│  Infrastructure (inline bash):     Config (container exec): │
│    start    - docker compose up      admin                  │
│    stop     - docker compose down    ai-provider            │
│    restart  - stop + start           embedding              │
│    logs     - docker compose logs    api-key                │
│    status   - docker compose ps      shell                  │
│    upgrade  - pull + migrate + up                           │
│                                                             │
│  Migrations: docker exec kg-operator migrate-db.sh          │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Tasks

- [ ] Consolidate operator/lib/*.sh logic into operator.sh
  - start-infra.sh → inline start_infrastructure()
  - start-app.sh → inline start_application()
  - stop.sh → inline stop_platform()
  - upgrade.sh → inline upgrade_platform()
  - teardown.sh → inline teardown_platform()
- [ ] Remove operator/lib/*.sh downloads from install.sh
- [ ] Keep operator/database/*.sh in container only (migrations)
- [ ] Update install.sh to only download: operator.sh, compose files, schema
- [ ] Test that all commands still work after consolidation

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
- [ ] Tag kg-operator with version numbers (currently only has 'latest')
- [ ] Merge main to release branch to trigger operator build
- [ ] Ensure all three images have matching version tags

## Testing

- [ ] Fresh install on clean system (validate full flow)
- [ ] Upgrade from 0.5.0 to 0.6.0
- [ ] Macvlan install with DHCP mode
- [ ] Macvlan install with static IP mode

## Documentation

- [x] Create OPERATOR_ARCHITECTURE.md
- [ ] Update installation docs after architecture decision
- [ ] Document compose file relationships
