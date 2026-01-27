---
status: Draft
---

# ADR-086: Deployment Topology (Dev/Stable Split)

## Status
Implemented

## Context

The knowledge graph system needs a stable environment for long-term document storage and querying, separate from active development. Current infrastructure:

- **north** - Development machine (active feature work)
- **cube** - Stable machine on same subnet (long-term data, older Nvidia GPU)
- Both machines have Docker installed
- **release** branch already builds images to GHCR

The Nvidia GPU on cube could support local LLM inference (Ollama) for ingestion, reducing API costs for bulk document processing.

### Requirements

1. Stable environment that survives frequent updates
2. Data persistence across container updates
3. Clear upgrade path with rollback capability
4. Minimal operational overhead

## Decision

### Branch/Environment Mapping

| Branch | Environment | Image Tag | Update Frequency |
|--------|-------------|-----------|------------------|
| `main` | north (dev) | `sha-*` or local build | Continuous |
| `release` | cube (stable) | `latest` | Planned releases |

### Deployment Model

```
cube (stable)                         north (dev)
┌─────────────────────────┐          ┌─────────────────────────┐
│ GHCR images (:latest)   │◄─────────│ Local builds / main     │
│ docker-compose.prod.yml │  merge   │ docker-compose.yml      │
│ Named volumes (persist) │  to      │ Dev volumes             │
│ External backups        │  release │                         │
└─────────────────────────┘          └─────────────────────────┘
```

### cube Configuration

1. **Clone repo** for docker-compose and operator scripts
2. **Use GHCR images** instead of local builds
3. **Named volumes** for data persistence:
   - `kg-postgres-data` - Graph database
   - `kg-garage-data` - Document storage (S3)
4. **Backup strategy** - Periodic pg_dump + garage sync

### Initial Deployment (cube)

```bash
# Clean headless deployment with GHCR images and NVIDIA GPU
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --gpu=nvidia \
  --ai-provider=openai \
  --ai-model=gpt-4o \
  --ai-key="$OPENAI_API_KEY" \
  --skip-cli

# Or minimal deployment (configure AI later)
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --gpu=nvidia \
  --skip-ai-config
```

### Update Procedure (cube)

```bash
# Graceful upgrade: pull images, run migrations, restart
./operator.sh upgrade

# Or with dry-run to see what would change
./operator.sh upgrade --dry-run
```

### Rollback Procedure

```bash
# 1. Stop services
./operator.sh stop

# 2. Restore from backup
./operator.sh restore <backup-name>

# 3. Pin to previous image version
# Edit docker-compose.prod.yml: image: ghcr.io/.../kg-api:sha-<previous>

# 4. Restart
./operator.sh start
```

### Production Compose Files

The operator automatically selects the right compose files based on configuration:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base config (dev, `knowledge-graph-*` containers) |
| `docker-compose.prod.yml` | Production config (`kg-*` containers, GHCR images) |
| `docker-compose.ghcr.yml` | GHCR image overlay (used with base compose) |
| `docker-compose.gpu-nvidia.yml` | NVIDIA GPU support |

When `--container-prefix=kg` or `--image-source=ghcr` is set, the operator automatically uses `docker-compose.prod.yml`.

### Hybrid AI Configuration (cube)

Cube's Nvidia GPU enables a cost-effective hybrid approach:

| Task | Provider | Model |
|------|----------|-------|
| **Embeddings** | Ollama (local) | nomic-embed-text or similar |
| **Concept extraction** | API (OpenAI/Anthropic) | GPT-4o / Claude Sonnet |

This keeps embedding costs zero (high volume, local GPU) while using API for reasoning tasks that benefit from frontier models.

Configure in cube's operator:
```bash
./operator.sh shell
configure.py ai-provider      # Set extraction LLM (API)
configure.py embedding-model  # Set embedding model (Ollama)
```

## Consequences

### Positive
- Clear separation between dev churn and stable data
- Pre-built images = faster deployments on cube
- Explicit release process prevents accidental updates
- Data persists independently of container lifecycle

### Negative
- Two environments to maintain
- Need to remember to merge to release
- Potential for environments to drift

### Risks
- Schema migrations could break stable environment
- Need monitoring to detect issues post-update

## Related ADRs

- ADR-061: Operator Architecture
- ADR-069: FUSE Filesystem (may run on cube for document access)

## Implementation Tasks

- [x] Create `docker-compose.prod.yml` override
- [x] Add headless init to operator.sh (`--headless` flag)
- [x] Add upgrade command to operator.sh
- [x] Container name configuration via `.operator.conf`
- [x] Auto-select compose file based on container prefix
- [x] Test clean cold start deployment on cube
- [ ] Add backup/restore commands to operator.sh
- [ ] Test upgrade/rollback cycle
