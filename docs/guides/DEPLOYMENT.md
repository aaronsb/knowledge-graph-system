# Deployment Guide

Comprehensive guide for deploying the Knowledge Graph system using the operator architecture (ADR-061).

## Overview

The Knowledge Graph system uses a **containerized operator architecture** where all infrastructure runs in Docker containers and configuration is managed through a dedicated operator container. This approach works identically for development and production deployments.

**Three deployment scenarios:**

1. **Local Development** - Build from source, use `--dev` secrets, local configuration
2. **Local Production** - Build from source, use production secrets, persistent volumes
3. **Remote Production** - Use pre-built GHCR images, production secrets, orchestrated deployment

## Architecture

The system consists of five core containers:

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Containers                     │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐  │
│  │  PostgreSQL │   │   Garage    │   │   Operator   │  │
│  │  + AGE      │   │  S3 Storage │   │  (Config)    │  │
│  └─────────────┘   └─────────────┘   └──────────────┘  │
│                                                          │
│  ┌─────────────┐   ┌─────────────┐                     │
│  │  API Server │   │   Web UI    │                     │
│  │  (FastAPI)  │   │   (React)   │                     │
│  └─────────────┘   └─────────────┘                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
         ↑
    kg CLI (optional)
```

## Prerequisites

### All Deployments
- Docker or Podman with Docker Compose
- OpenAI API key (or use local embeddings with Ollama)

### Optional
- Node.js 18+ for kg CLI tool
- Ollama for local LLM inference

## Deployment Method 1: Local Development

**Use case:** Active development, testing, rapid iteration

**Characteristics:**
- Build images locally from source
- Simple passwords (`--dev` mode)
- Hot-reload for code changes (via rebuild scripts)
- All services on localhost
- No persistent volume guarantees

### Setup

```bash
# 1. Clone repository
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# 2. Generate development secrets
./operator/lib/init-secrets.sh --dev

# 3. Start infrastructure
./operator/lib/start-infra.sh

# 4. Configure platform
docker exec -it kg-operator python /workspace/operator/configure.py admin
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
docker exec kg-operator python /workspace/operator/configure.py embedding 2
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai

# 5. Start application
./operator/lib/start-app.sh

# 6. Install CLI (optional)
cd cli && ./install.sh && cd ..

# 7. Verify
kg health
```

### Making Changes

When you modify code:

```bash
# Rebuild and restart specific container
./scripts/development/build/rebuild-api.sh
./scripts/development/build/rebuild-web.sh
./scripts/development/build/rebuild-operator.sh

# Or rebuild all
./scripts/development/build/rebuild-all.sh
```

### Stopping

```bash
# Stop services (keeps data)
./operator/lib/stop.sh

# Complete teardown (removes everything)
./operator/lib/teardown.sh

# Keep secrets but remove data
./operator/lib/teardown.sh --keep-env
```

## Deployment Method 2: Local Production

**Use case:** Testing production builds locally, air-gapped deployment, self-hosting

**Characteristics:**
- Build images locally from source OR pull from GHCR
- Strong cryptographic secrets
- Persistent Docker volumes
- Production logging configuration
- Optional TLS/authentication

### Setup with Local Builds

```bash
# 1. Clone repository
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system

# 2. Generate production secrets (no --dev flag)
./operator/lib/init-secrets.sh

# 3. Start infrastructure
./operator/lib/start-infra.sh

# 4. Configure platform with strong passwords
docker exec kg-operator python /workspace/operator/configure.py admin --password "$(openssl rand -base64 32)"
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
docker exec kg-operator python /workspace/operator/configure.py embedding 2
docker exec kg-operator python /workspace/operator/configure.py api-key openai --key "$OPENAI_API_KEY"

# 5. Start application
./operator/lib/start-app.sh
```

### Setup with Pre-built Images (GHCR)

```bash
# 1. Create project directory
mkdir -p ~/knowledge-graph && cd ~/knowledge-graph

# 2. Download docker-compose files
curl -O https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/docker/docker-compose.ghcr.yml

# 3. Download operator scripts
mkdir -p operator/lib
curl -o operator/lib/init-secrets.sh https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/operator/lib/init-secrets.sh
curl -o operator/lib/start-infra.sh https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/operator/lib/start-infra.sh
curl -o operator/lib/start-app.sh https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/operator/lib/start-app.sh
chmod +x operator/lib/*.sh

# 4. Generate secrets
./operator/lib/init-secrets.sh

# 5. Use GHCR images
cd docker
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d postgres garage operator

# 6. Configure platform
docker exec -it kg-operator python /workspace/operator/configure.py admin
# ... (same as above)

# 7. Start application with GHCR images
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d api web
```

### Data Persistence

Docker volumes are used for persistent data:

```bash
# List volumes
docker volume ls | grep knowledge-graph

# Typical volumes:
# - postgres_data       - Database files
# - garage_data         - S3 object storage
# - garage_meta         - Garage metadata

# Backup volumes
docker run --rm \
  -v postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup-$(date +%Y%m%d).tar.gz /data

# Restore volumes
docker run --rm \
  -v postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres-backup-20250108.tar.gz -C /
```

### Database Backups

```bash
# Backup database
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph | gzip > kg-backup-$(date +%Y%m%d).sql.gz

# Restore database
gunzip -c kg-backup-20250108.sql.gz | docker exec -i knowledge-graph-postgres psql -U admin knowledge_graph
```

## Deployment Method 3: Remote Production

**Use case:** Production servers, cloud deployment, orchestrated environments

**Characteristics:**
- Use pre-built GHCR images (versioned releases)
- Orchestrator-managed secrets
- Load balancing and scaling
- Monitoring and alerting
- TLS termination via reverse proxy

### Docker Swarm Deployment

```yaml
# docker-stack.yml
version: '3.8'

services:
  postgres:
    image: apache/age
    deploy:
      replicas: 1
      placement:
        constraints: [node.role == manager]
    volumes:
      - postgres_data:/var/lib/postgresql/data
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

  api:
    image: ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.0.0
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
    secrets:
      - encryption_key
      - oauth_signing_key
    environment:
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key

secrets:
  postgres_password:
    external: true
  encryption_key:
    external: true

volumes:
  postgres_data:
```

Deploy:

```bash
# Create secrets
echo "$POSTGRES_PASSWORD" | docker secret create postgres_password -
echo "$ENCRYPTION_KEY" | docker secret create encryption_key -

# Deploy stack
docker stack deploy -c docker-stack.yml kg
```

### Kubernetes Deployment

```yaml
# kg-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kg-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kg-api
  template:
    metadata:
      labels:
        app: kg-api
    spec:
      containers:
      - name: api
        image: ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          value: postgres-service
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: kg-secrets
              key: encryption-key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

Deploy:

```bash
kubectl create secret generic kg-secrets \
  --from-literal=encryption-key="$ENCRYPTION_KEY" \
  --from-literal=oauth-signing-key="$OAUTH_SIGNING_KEY"

kubectl apply -f kg-deployment.yaml
```

## Configuration Management

### Infrastructure Secrets (`.env`)

Generated once by `init-secrets.sh`, never edited:

- `ENCRYPTION_KEY` - Fernet key for API key encryption
- `OAUTH_SIGNING_KEY` - JWT signing key
- `POSTGRES_PASSWORD` - Database password
- `GARAGE_RPC_SECRET` - Garage cluster secret
- `INTERNAL_KEY_SERVICE_SECRET` - Service authorization

**Backing up secrets:**

```bash
# Copy .env to secure location
cp .env .env.backup-$(date +%Y%m%d)

# For production, use secrets manager
# AWS Secrets Manager, HashiCorp Vault, etc.
```

### Application Configuration (Database)

Managed via operator container:

```bash
# View configuration
docker exec kg-operator python /workspace/operator/configure.py status

# Update AI provider
docker exec kg-operator python /workspace/operator/configure.py ai-provider anthropic --model claude-sonnet-4-20250514

# Rotate API key
docker exec kg-operator python /workspace/operator/admin/manage_api_keys.py delete openai
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai
```

## Networking

### Port Usage

| Component | Port | Protocol | Exposed |
|-----------|------|----------|---------|
| PostgreSQL | 5432 | TCP | Localhost only |
| API Server | 8000 | HTTP | Yes (behind proxy) |
| Web UI | 3000 | HTTP | Yes (behind proxy) |
| Garage API | 3900 | HTTP | Internal only |
| Garage Web | 3903 | HTTP | Internal only |

### Reverse Proxy (Production)

Use Nginx or Caddy for TLS termination:

```nginx
# /etc/nginx/sites-available/kg
server {
    listen 443 ssl http2;
    server_name kg.example.com;

    ssl_certificate /etc/letsencrypt/live/kg.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kg.example.com/privkey.pem;

    # API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Web UI
    location / {
        proxy_pass http://localhost:3000/;
        proxy_set_header Host $host;
    }
}
```

## Security

### Development
- Simple passwords OK (`--dev` mode)
- No TLS required (localhost only)
- Permissive CORS
- Debug logging enabled

### Production
- Strong cryptographic secrets required
- TLS mandatory for external access
- Restrictive CORS
- INFO logging level
- Secrets in secrets manager
- Regular security updates

### API Authentication

The system uses JWT-based authentication:

```bash
# Create admin user
docker exec kg-operator python /workspace/operator/configure.py admin

# Users authenticate via /auth/login endpoint
# JWT tokens in Authorization header
```

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
kg database stats

# Full system check
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Logs

```bash
# API logs
docker logs -f kg-api-dev

# Database logs
docker logs -f knowledge-graph-postgres

# All logs
cd docker && docker-compose logs -f

# Export logs
docker logs kg-api-dev > api-logs-$(date +%Y%m%d).log
```

### Metrics (Future)

Prometheus integration planned:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'kg-api'
    static_configs:
      - targets: ['localhost:8000']
```

## Scaling

### Horizontal Scaling

Multiple API replicas with shared database:

```yaml
# docker-compose.override.yml
services:
  api:
    deploy:
      replicas: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - api
```

Load balancer configuration:

```nginx
upstream kg_api {
    least_conn;
    server kg-api-1:8000;
    server kg-api-2:8000;
    server kg-api-3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://kg_api;
    }
}
```

### Database Scaling

For high-load scenarios:

1. **Read Replicas** - PostgreSQL replication
2. **Connection Pooling** - PgBouncer
3. **Resource Tuning** - See `operator/DATABASE_PROFILES.md`

## Upgrading

### Development

```bash
git pull origin main
./scripts/development/build/rebuild-all.sh
```

### Production (Local Builds)

```bash
# 1. Backup database
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup-pre-upgrade.sql

# 2. Pull latest code
git pull origin main

# 3. Rebuild images
cd docker && docker-compose build

# 4. Restart services
docker-compose up -d

# 5. Verify
kg health
```

### Production (GHCR Images)

```bash
# 1. Backup database
docker exec knowledge-graph-postgres pg_dump -U admin knowledge_graph > backup-pre-upgrade.sql

# 2. Pull new images
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.1.0
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-web:1.1.0
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-operator:1.1.0

# 3. Update docker-compose to use new version tags
# Edit docker-compose.ghcr.yml if using specific versions

# 4. Restart with new images
cd docker
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d

# 5. Verify
kg health
kg database stats
```

## Troubleshooting

### Container Won't Start

```bash
# Check container status
docker ps -a

# Check logs
docker logs <container-name>

# Check resource usage
docker stats

# Verify secrets exist
ls -la .env
cat .env | grep -E "ENCRYPTION_KEY|POSTGRES_PASSWORD"
```

### Health Check Failures

```bash
# API not responding
docker logs kg-api-dev | tail -50

# Check database connectivity
docker exec kg-api-dev ping postgres

# Restart service
cd docker && docker-compose restart api
```

### Database Connection Issues

```bash
# Check postgres running
docker ps | grep postgres

# Test connection
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT 1"

# Check migrations
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "SELECT * FROM schema_migrations ORDER BY applied_at"
```

### Performance Issues

```bash
# Check resource limits
docker stats

# Review database profile
cat operator/DATABASE_PROFILES.md

# Apply appropriate profile
docker exec kg-operator python /workspace/operator/setup/configure-db-profile.sh medium
```

## See Also

- [Quickstart Guide](QUICKSTART.md) - Get started in 10 minutes
- [Container Images Guide](CONTAINER_IMAGES.md) - Pre-built images and versioning
- [Architecture Overview](../architecture/ARCHITECTURE.md) - System design
- [ADR-061: Operator Architecture](../architecture/ADR-061-operator-pattern-lifecycle.md) - Architecture decision
