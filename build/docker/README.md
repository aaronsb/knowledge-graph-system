# Docker Configurations

Docker configurations for containerizing the Knowledge Graph system.

## Overview

This directory contains Dockerfiles and docker-compose configurations for building and running the system in containers.

## Files

### Dockerfiles

#### `api.Dockerfile`
Builds the API server container:
```dockerfile
FROM python:3.11-slim
# Install dependencies, copy source, configure entrypoint
```

**Image:** `ghcr.io/aaronsb/kg-api:latest`

#### `viz.Dockerfile`
Builds the visualization server container:
```dockerfile
FROM node:18-alpine
# Build frontend, configure nginx
```

**Image:** `ghcr.io/aaronsb/kg-viz:latest`

### Docker Compose Files

#### `compose/docker-compose.local.yml`
Local development stack with hot-reload:
```yaml
services:
  database:    # PostgreSQL + AGE
  api:         # API server with volume mounts
  viz:         # Visualization (future)
```

#### `compose/docker-compose.release.yml`
Production stack using published images:
```yaml
services:
  database:    # From GHCR
  api:         # From GHCR
  viz:         # From GHCR
```

## Building Images

### Locally (Development)
```bash
# Build API server
docker build -f api.Dockerfile -t kg-api:dev ..

# Build with BuildKit features
DOCKER_BUILDKIT=1 docker build -f api.Dockerfile -t kg-api:dev ..

# Build all images
docker-compose -f compose/docker-compose.local.yml build
```

### For Release (CI/CD)
```bash
# Build and tag for GHCR
docker build -f api.Dockerfile \
  -t ghcr.io/aaronsb/kg-api:v0.2.0 \
  -t ghcr.io/aaronsb/kg-api:latest \
  ..

# Push to registry
docker push ghcr.io/aaronsb/kg-api:v0.2.0
docker push ghcr.io/aaronsb/kg-api:latest
```

## Image Details

### API Server Image (`api.Dockerfile`)

**Base:** `python:3.11-slim`

**Layers:**
1. System dependencies (PostgreSQL client, etc.)
2. Python dependencies (requirements.txt)
3. Application code
4. Migrations and initialization scripts

**Size:** ~300MB (optimized)

**Entry Point:**
```bash
uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port ${KG_API_PORT:-8000}
```

**Environment Variables:**
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `AI_PROVIDER`
- `OPENAI_API_KEY` (or other provider keys)

### Visualization Image (`viz.Dockerfile`)

**Base:** `node:18-alpine`

**Layers:**
1. Build dependencies
2. Frontend build (React/Vue/etc.)
3. Nginx for serving
4. Configuration

**Size:** ~50MB (optimized)

**Entry Point:**
```bash
nginx -g 'daemon off;'
```

**Environment Variables:**
- `KG_API_URL` - API server URL

## Docker Compose Usage

### Development Stack
```bash
# Start all services
docker-compose -f compose/docker-compose.local.yml up -d

# View logs
docker-compose -f compose/docker-compose.local.yml logs -f api

# Stop services
docker-compose -f compose/docker-compose.local.yml down

# Reset (delete volumes)
docker-compose -f compose/docker-compose.local.yml down -v
```

### Production Stack
```bash
# Pull images from GHCR
docker-compose -f compose/docker-compose.release.yml pull

# Start services
docker-compose -f compose/docker-compose.release.yml up -d

# Health check
docker-compose -f compose/docker-compose.release.yml ps
```

## Multi-Architecture Support

Images are built for multiple architectures:
- `linux/amd64` - Intel/AMD (x86_64)
- `linux/arm64` - ARM (Apple Silicon, Pi, etc.)

### Building Multi-Arch Images
```bash
# Create buildx builder
docker buildx create --name kg-builder --use

# Build and push multi-arch
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f api.Dockerfile \
  -t ghcr.io/aaronsb/kg-api:v0.2.0 \
  --push \
  ..
```

## Optimization

### Image Size Reduction
- Multi-stage builds
- Alpine base where possible
- Remove build dependencies
- Minimize layers

### Build Speed
- Layer caching
- BuildKit features
- Parallel builds
- Remote cache

## Security

### Best Practices
- Non-root user in containers
- No secrets in images
- Scan for vulnerabilities
- Pin dependency versions

### Vulnerability Scanning
```bash
# Scan with Trivy
trivy image ghcr.io/aaronsb/kg-api:latest

# Scan with Docker Scout
docker scout cves ghcr.io/aaronsb/kg-api:latest
```

## Networking

### Service Communication
Services communicate via Docker network:
- API → Database: `postgres://database:5432/knowledge_graph`
- Viz → API: `http://api:8000`

### External Access
Ports exposed to host:
- API: `8000:8000`
- Database: `5432:5432` (optional, for dev only)
- Viz: `3000:80`

## Volumes

### Data Persistence
- `postgres_data` - Database files
- `kg_logs` - Application logs
- `kg_cache` - Embeddings cache

### Volume Management
```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect postgres_data

# Backup volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data

# Restore volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

## Health Checks

Containers include health checks:

### API Server
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Database
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
  CMD pg_isready -U $POSTGRES_USER || exit 1
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs kg-api

# Check health
docker inspect --format='{{json .State.Health}}' kg-api | jq

# Interactive debugging
docker exec -it kg-api /bin/bash
```

### Network issues
```bash
# Inspect network
docker network inspect kg_default

# Test connectivity
docker exec kg-api ping database
docker exec kg-api curl http://api:8000/health
```

### Volume issues
```bash
# Check volume mounts
docker inspect kg-api | jq '.[].Mounts'

# Check permissions
docker exec kg-api ls -la /app
```

## See Also

- [Build Scripts](../local/README.md)
- [Deployment Guide](../../docs/guides/DEPLOYMENT.md)
- [Docker Documentation](https://docs.docker.com/)
