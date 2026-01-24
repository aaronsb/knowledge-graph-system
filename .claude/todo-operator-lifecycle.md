# Operator Lifecycle Implementation

Tracking file for ADR-061 update/upgrade lifecycle improvements.

## Completed (2026-01-19)

- [x] Add `update` command to operator.sh
  - [x] Pull all images: `./operator.sh update`
  - [x] Pull specific service: `./operator.sh update operator`
  - [x] Helpful messaging for postgres/garage (pinned versions)
  - [x] GHCR overlay support for standalone installs

- [x] Fix operator.sh for standalone installs
  - [x] Auto-detect DOCKER_DIR (repo vs standalone)
  - [x] install.sh creates `.operator.conf`
  - [x] common.sh and upgrade.sh use detected paths

- [x] install.sh improvements
  - [x] Download all operator scripts (upgrade.sh, start-*.sh, etc.)
  - [x] Create `.operator.conf` with container naming
  - [x] Updated completion message referencing operator.sh

- [x] Update ADR-061 with update/upgrade lifecycle section

## In Progress

- [x] Test Let's Encrypt with Porkbun DNS on cube.broccoli.house
  - Tested with acme.sh DNS-01 challenge (ZeroSSL via Porkbun)
  - Existing cert detection and reuse working
  - Fixed fullchain.crt usage in nginx (0.6.0-dev.28)

## Future Evolution

### Version Manifest (operator as source of truth)

The operator container should become the single source of truth for version compatibility:

```
operator container
├── /etc/kg/versions.json   # Compatible image versions
├── schema/migrations/       # Database migrations
└── configure.py            # Configuration tools
```

**versions.json example:**
```json
{
  "operator": "0.5.0",
  "compatible": {
    "api": ["0.5.0", "0.4.x"],
    "web": ["0.5.0", "0.4.x"],
    "postgres": ["apache/age:PG16-1.5.0"],
    "garage": ["dxflrs/garage:v1.0.0", "dxflrs/garage:v1.0.1"]
  }
}
```

**Benefits:**
- `./operator.sh update` checks compatibility before pulling
- Prevents mismatched versions causing runtime errors
- Rollback support with version pinning

### Tasks for Version Manifest

- [ ] Create `/etc/kg/versions.json` in operator container
- [ ] Add `/versions` API endpoint to operator (optional)
- [ ] Update `cmd_update` to check compatibility
- [ ] Add `--version` flag to update specific version
- [ ] Add rollback command: `./operator.sh rollback api 0.4.5`

### Operator Container as Control Plane

Long-term vision: operator.sh becomes minimal shim, all logic in container:

```
operator.sh (host)
  │
  └─► docker exec kg-operator operator-cli <command>
```

**Tasks:**
- [ ] Create `operator-cli` Python entrypoint in container
- [ ] Move upgrade logic from shell to Python
- [ ] Move start/stop logic to container (via Docker socket)
- [ ] operator.sh becomes ~50 lines of delegation

### Infrastructure Version Updates

For postgres/garage updates (breaking changes):

- [ ] Add `./operator.sh backup --pre-upgrade`
- [ ] Add migration guides for major version bumps
- [ ] Consider pg_upgrade automation for PostgreSQL
