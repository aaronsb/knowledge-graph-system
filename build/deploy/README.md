# Deployment Scripts

Scripts for deploying the Knowledge Graph system in different environments.

## Overview

Deployment scripts handle starting, stopping, and managing running instances of the system. They work with either locally built artifacts or GitHub release artifacts.

## Deployment Modes

### Local Deployment (`local/`)
Deploy from locally built artifacts for development:
- Hot-reload enabled
- Debug logging
- Development databases
- Uses source code directly

**Use case:** Active development, debugging, testing changes

### Remote Deployment (`remote/`)
Deploy from GitHub release artifacts:
- Production-ready builds
- Optimized containers
- Published Docker images
- Versioned releases

**Use case:** Production deployment, end-user installation

## Directory Structure

```
deploy/
├── README.md          # This file
├── local/             # Local development deployment
│   ├── deploy-all.sh
│   ├── deploy-database.sh
│   ├── deploy-api.sh
│   ├── deploy-viz.sh
│   └── README.md
└── remote/            # Remote artifact deployment
    ├── deploy-from-release.sh
    └── README.md
```

## Quick Start

### Deploy Everything Locally
```bash
# Build first
../local/build-all.sh

# Deploy
./local/deploy-all.sh
```

### Deploy from GitHub Release
```bash
./remote/deploy-from-release.sh --version v0.2.0
```

## Component Dependencies

Deployment order matters due to dependencies:

```
Database (PostgreSQL + AGE)
    ↓
API Server (requires database)
    ↓
Visualization (requires API)
    ↓
CLI Tool (requires API)
    ↓
MCP Server (requires API)
```

## Environment Variables

Both deployment modes use environment variables for configuration:

```bash
# Database
POSTGRES_USER=kg_user
POSTGRES_PASSWORD=***
POSTGRES_DB=knowledge_graph

# API
KG_API_PORT=8000
LOG_LEVEL=INFO
AI_PROVIDER=openai

# Client
KG_API_URL=http://localhost:8000
KG_CLIENT_ID=dev-client
```

See `.env.example` for full configuration.

## Health Checks

After deployment, verify system health:

```bash
# Check API
curl http://localhost:8000/health

# Check database
docker exec knowledge-graph-postgres psql -U kg_user -d knowledge_graph -c "SELECT * FROM ag_graph;"

# Check CLI
kg health

# Check full system
kg database stats
```

## Logging

Deployment logs are stored in different locations by mode:

**Local deployment:**
- API: `logs/api_*.log`
- Database: `docker logs knowledge-graph-postgres`
- CLI: stdout/stderr

**Remote deployment:**
- All components: Docker container logs
- View with: `docker-compose logs -f`

## Ports

Default ports used by components:

| Component | Port | Configurable |
|-----------|------|-------------|
| PostgreSQL | 5432 | Yes (POSTGRES_PORT) |
| API Server | 8000 | Yes (KG_API_PORT) |
| Visualization | 3000 | Yes (VIZ_PORT) |

## Troubleshooting

### Port conflicts
```bash
# Check what's using port
lsof -i :8000

# Stop conflicting service or change port
export KG_API_PORT=8001
```

### Database won't start
```bash
# Check logs
docker logs knowledge-graph-postgres

# Reset database
./local/deploy-database.sh --reset
```

### API can't connect to database
```bash
# Verify database is running
docker ps | grep postgres

# Check connection settings
cat .env | grep POSTGRES

# Test connection
docker exec knowledge-graph-postgres psql -U kg_user -d knowledge_graph -c "SELECT 1"
```

## See Also

- [Build Scripts](../local/README.md)
- [Installation Scripts](../install/README.md)
- [Deployment Guide](../../docs/guides/DEPLOYMENT.md)
