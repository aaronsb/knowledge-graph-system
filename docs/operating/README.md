# Operating the Knowledge Graph System

Guides for deploying, configuring, and maintaining the platform.

## Choose Your Path

| I want to... | Go to |
|--------------|-------|
| Try it locally in 5 minutes | [Quick Start](quick-start.md) |
| Deploy for real use | [Production Deployment](production.md) |
| Deploy on a dedicated LAN IP | [Macvlan Headless Install](macvlan-headless-install.md) |
| Understand all the settings | [Configuration Reference](configuration.md) |
| Upgrade to a new version | [Upgrading](upgrading.md) |
| Back up my data | [Backup & Restore](backup-restore.md) |
| Fix something broken | [Troubleshooting](troubleshooting.md) |

## Architecture Overview

The system runs as Docker containers:

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Containers                        │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   postgres   │    garage    │     api      │      web       │
│  (database)  │  (storage)   │   (backend)  │  (frontend)    │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

- **postgres**: Apache AGE (PostgreSQL with graph extensions) - stores concepts, relationships, metadata
- **garage**: S3-compatible object storage - stores original documents
- **api**: Python FastAPI server - handles extraction, queries, authentication
- **web**: React frontend - visual exploration interface

An **operator** container manages setup, migrations, and maintenance tasks.

## Deployment Modes

### Interactive (Default)
Run `./operator.sh init` and follow the prompts. Good for first-time setup on a single machine.

### Headless
Run `./operator.sh init --headless` with command-line flags. Good for:
- Automated deployments
- CI/CD pipelines
- Multi-machine setups
- Scripted configuration

### Development
Run `./operator.sh init` with dev mode enabled. Adds:
- Hot reload for code changes
- Simple default passwords
- Local image builds

### Production
Deploy with GHCR images, HTTPS, and proper secrets. Covered in [Production Deployment](production.md).

## What You'll Need

**Required:**
- Docker and Docker Compose
- 8GB RAM minimum (16GB+ recommended for GPU acceleration)
- 20GB disk space for system, more for documents

**Optional:**
- NVIDIA GPU for faster extraction
- Domain name for HTTPS access
- AI provider API key (OpenAI or Anthropic)

## Quick Commands

```bash
# First-time setup
./operator.sh init

# Daily start
./operator.sh start

# Stop everything
./operator.sh stop

# Check status
./operator.sh status

# View logs
./operator.sh logs api      # API logs
./operator.sh logs          # All logs

# Maintenance
./operator.sh upgrade       # Pull updates and migrate
./operator.sh backup        # Backup database
./operator.sh shell         # Enter operator shell for admin tasks
```

## Next Steps

- [Quick Start](quick-start.md) - Get running in 5 minutes
- [Production Deployment](production.md) - Full deployment guide
