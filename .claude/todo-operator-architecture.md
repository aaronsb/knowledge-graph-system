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

## Architecture Decision Needed

Choose one of three approaches:

### Option A: Container-First
- [ ] Move all operator commands into kg-operator container
- [ ] operator.sh becomes thin shim: `docker exec kg-operator operator-cli $@`
- [ ] Mount docker socket in operator container for start/stop/upgrade
- [ ] Remove need for host-side lib/*.sh downloads

### Option B: Clear Host/Container Split
- [ ] Keep infrastructure commands on host (start/stop/upgrade)
- [ ] Keep config commands in container (admin/ai-provider/embedding)
- [ ] Bundle host scripts directly in operator.sh (no separate lib/ files)
- [ ] Make the split explicit in documentation

### Option C: Install/Runtime Split
- [ ] install.sh handles all setup including first start
- [ ] operator.sh is trivial (just docker exec for config)
- [ ] For infrastructure changes, re-run install.sh with flags

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
