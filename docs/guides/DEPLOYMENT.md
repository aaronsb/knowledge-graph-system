# Deployment Guide

Comprehensive guide for deploying the Knowledge Graph system in various environments.

## Overview

The Knowledge Graph system can be deployed in three main ways:

1. **Development** - Local source-based deployment with hot-reload
2. **Local Production** - Production-like deployment from local builds
3. **Remote Production** - End-user deployment from GitHub releases

## Quick Start

### For Developers
```bash
# Clone and setup
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# Build and deploy locally
./build/local/build-all.sh
./build/deploy/local/deploy-all.sh

# Verify
kg health
```

### For End Users
```bash
# Install from GitHub release (future)
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/build/install/install-remote.sh | bash

# Verify
kg health
```

## Architecture

The system consists of five components:

```
┌──────────────┐
│  CLI Tool    │  (TypeScript binary)
└───────┬──────┘
        │ HTTP
┌───────▼──────┐     ┌──────────────┐
│  API Server  │────►│   Database   │
│   (Python)   │     │ PostgreSQL + │
└───────┬──────┘     │  Apache AGE  │
        │            └──────────────┘
┌───────▼──────┐
│ MCP Server   │  (TypeScript binary)
└──────────────┘

┌──────────────┐
│ Visualization│  (React/Vue + Nginx)
│    Server    │  [Future]
└──────────────┘
```

## Deployment Methods

### 1. Development Deployment

**Use case:** Active development, testing changes

**Components:**
- Source code mounted directly
- Hot-reload enabled
- Debug logging
- Development database (no persistence guarantees)

**Setup:**
```bash
# Build from source
cd build/local
./build-all.sh --verbose

# Deploy with hot-reload
cd ../deploy/local
./deploy-all.sh

# Services start in background
# API logs: logs/api_*.log
# Database logs: docker logs knowledge-graph-postgres
```

**Configuration:**
Edit `.env` in project root:
```bash
# .env
POSTGRES_USER=kg_user
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=knowledge_graph

KG_API_PORT=8000
LOG_LEVEL=DEBUG

AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

**Stopping:**
```bash
./scripts/stop-api.sh
./scripts/stop-database.sh
```

### 2. Local Production Deployment

**Use case:** Testing production build locally, air-gapped deployment

**Components:**
- Built artifacts (optimized)
- Docker containers
- Production logging
- Persistent data volumes

**Setup:**
```bash
# Build production artifacts
./build/local/build-all.sh --clean

# Install to system
./build/install/install-local.sh

# Services managed by systemd/launchd
systemctl status kg-api
```

**Configuration:**
System-wide: `/etc/kg/config.yml`
User-specific: `~/.kg/config.yml`

**Stopping:**
```bash
systemctl stop kg-api
docker-compose down
```

### 3. Remote Production Deployment

**Use case:** End-user installation, production servers

**Components:**
- Pre-built Docker images from GHCR
- Signed binaries from GitHub releases
- Official configuration

**Setup:**
```bash
# One-command install
curl -fsSL https://... | bash

# Or with specific version
./build/install/install-remote.sh --version v0.2.0

# Services auto-start
```

**Configuration:**
During installation:
```bash
./install-remote.sh --configure
```

After installation:
```bash
kg config set api.url http://localhost:8000
kg config set ai.provider openai
```

**Stopping:**
```bash
systemctl stop kg-*
# or
docker-compose -f /opt/kg/docker-compose.yml down
```

## Component Details

### Database (PostgreSQL + Apache AGE)

**Development:**
- Started via docker-compose
- Data in Docker volume
- Accessible on localhost:5432

**Production:**
- Docker container or native install
- Data persistence mandatory
- Backup strategy required

**Migrations:**
```bash
# Apply migrations
./scripts/migrate-db.sh

# Check migration status
kg database stats
```

### API Server (Python FastAPI)

**Development:**
- Runs from venv
- Hot-reload with `--reload` flag
- Logs to `logs/api_*.log`

**Production (Future):**
- Docker container
- Systemd service
- Log rotation configured
- Health checks enabled

**Monitoring:**
```bash
# Health check
curl http://localhost:8000/health

# View logs
tail -f logs/api_*.log
# or
journalctl -u kg-api -f
```

### CLI Tool (TypeScript)

**Development:**
- Built from `client/`
- Installed with `cd client && ./install.sh`
- Updates with rebuild

**Production:**
- Binary from GitHub release
- Installed to /usr/local/bin/kg
- Auto-update support (future)

**Usage:**
```bash
kg --version
kg health
kg database stats
```

### MCP Server (TypeScript)

**Development:**
- Built with CLI
- Configured in Claude Desktop
- Points to dist/mcp-server.js

**Production:**
- Binary from GitHub release
- Installed to /usr/local/bin/kg-mcp-server
- Claude Desktop integration

**Configuration:**
```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "/usr/local/bin/kg-mcp-server"
    }
  }
}
```

### Visualization (Future)

**Development:**
- React/Vue dev server
- Hot-reload enabled
- Proxies to API server

**Production:**
- Static build
- Served by Nginx
- Docker container

## Networking

### Port Usage

| Component | Port | Configurable |
|-----------|------|-------------|
| PostgreSQL | 5432 | Yes |
| API Server | 8000 | Yes |
| Visualization | 3000 | Yes |

### Firewall Configuration

**Development:** All ports localhost only

**Production:**
```bash
# Allow API (if exposing publicly)
ufw allow 8000/tcp

# Database should NOT be exposed
# Only allow from API container
```

## Data Persistence

### Volumes

**Docker:**
- `postgres_data` - Database files
- `api_logs` - Application logs
- `kg_cache` - Embeddings cache

**Native:**
- `/var/lib/postgresql/data` - Database
- `/var/log/kg/` - Logs
- `~/.kg/cache/` - User cache

### Backup

**Database:**
```bash
# Backup
docker exec knowledge-graph-postgres pg_dump -U kg_user knowledge_graph > backup.sql

# Restore
docker exec -i knowledge-graph-postgres psql -U kg_user knowledge_graph < backup.sql
```

**Full System:**
```bash
# Backup volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data

# Restore volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

## Security

### Development
- No authentication (localhost only)
- Debug logging enabled
- Permissive CORS

### Production
- API authentication required
- TLS/SSL mandatory for remote access
- Secrets in environment or secrets manager
- Restrictive CORS
- Regular security updates

**Securing API:**
```bash
# Generate API keys
kg admin create-api-key --name production

# Configure TLS
# Use reverse proxy (nginx, Caddy)
# Let's Encrypt for certificates
```

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
kg database stats

# Full system check
kg admin health-check
```

### Logs

**Centralized Logging (Production):**
- Use log aggregation (ELK, Loki)
- Configure log shipping
- Set retention policies

**Development:**
```bash
# API logs
tail -f logs/api_*.log

# Database logs
docker logs -f knowledge-graph-postgres

# All logs
docker-compose logs -f
```

### Metrics

**Future: Prometheus Integration**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'kg-api'
    static_configs:
      - targets: ['localhost:8000']
```

## Scaling

### Horizontal Scaling

**API Server:**
- Run multiple replicas
- Load balancer (nginx, HAProxy)
- Shared database

**Example with Docker Compose:**
```yaml
api:
  image: ghcr.io/aaronsb/kg-api:latest
  deploy:
    replicas: 3
```

### Database Scaling

**Read Replicas:**
- Configure PostgreSQL replication
- Route read queries to replicas
- Master for writes only

**Connection Pooling:**
- Use PgBouncer
- Reduce connection overhead
- Handle connection spikes

## Troubleshooting

### Common Issues

**Can't connect to database:**
```bash
# Check database running
docker ps | grep postgres

# Check connection settings
cat .env | grep POSTGRES

# Test connection
docker exec knowledge-graph-postgres psql -U kg_user -d knowledge_graph -c "SELECT 1"
```

**API won't start:**
```bash
# Check logs
tail -f logs/api_*.log

# Check dependencies
source venv/bin/activate
pip install -r requirements.txt

# Check port availability
lsof -i :8000
```

**CLI commands fail:**
```bash
# Check API connectivity
kg health

# Check configuration
kg config show

# Reinstall CLI
cd client && ./uninstall.sh && ./install.sh
```

## Upgrading

### Development
```bash
git pull origin main
./build/local/build-all.sh
./build/deploy/local/deploy-all.sh
```

### Production
```bash
# Backup first!
pg_dump ... > backup.sql

# Install new version
./build/install/install-remote.sh --upgrade --version v0.2.1

# Verify
kg --version
kg health
```

## See Also

- [Architecture Overview](../architecture/ARCHITECTURE_OVERVIEW.md) - System design and architecture
- [Architecture Decisions](../architecture/ARCHITECTURE_DECISIONS.md) - ADR index
- [API Reference](../reference/api/README.md) - REST API documentation
- **Developer Resources** (in source repository):
  - `CLAUDE.md` - Developer workflow guide for Claude Code
  - `README.md` - Project overview and quick start
