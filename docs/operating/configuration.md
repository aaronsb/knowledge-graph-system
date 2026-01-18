# Configuration Reference

All configuration options for the knowledge graph system.

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables (secrets, database, AI provider) |
| `.operator.conf` | Operator settings (container names, compose files) |
| `docker/nginx.prod.conf` | Nginx configuration (for HTTPS) |

## Environment Variables (.env)

### Core Secrets

Generated during initialization. **Never edit manually.**

| Variable | Purpose |
|----------|---------|
| `ENCRYPTION_KEY` | Fernet key for encrypting API keys at rest |
| `OAUTH_SIGNING_KEY` | Signs JWT access tokens |
| `INTERNAL_KEY_SERVICE_SECRET` | Service-to-service authentication |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | Database host (use `postgres` in containers) |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `knowledge_graph` | Database name |
| `POSTGRES_USER` | `admin` | Database user |
| `POSTGRES_PASSWORD` | (generated) | Database password |

### Web Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_HOSTNAME` | `localhost:3000` | Public hostname for web access |

Used for:
- OAuth redirect URIs (`https://{WEB_HOSTNAME}/callback`)
- API URL in frontend (`https://{WEB_HOSTNAME}/api`)
- OAuth client registration

### AI Provider

These settings only apply if `DEVELOPMENT_MODE=true`. Otherwise, configuration is loaded from the database.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVELOPMENT_MODE` | `false` | Load config from .env (true) or database (false) |
| `AI_PROVIDER` | `openai` | `openai`, `anthropic`, or `mock` |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | - | Anthropic API key |

Model configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_EXTRACTION_MODEL` | `gpt-4o` | Model for concept extraction |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Model for embeddings |
| `ANTHROPIC_EXTRACTION_MODEL` | `claude-sonnet-4-20250514` | Anthropic extraction model |

### Object Storage (Garage)

| Variable | Default | Description |
|----------|---------|-------------|
| `GARAGE_S3_ENDPOINT` | `http://garage:3900` | Garage S3 endpoint |
| `GARAGE_REGION` | `garage` | Garage region name |
| `GARAGE_BUCKET` | `kg-storage` | Default bucket name |
| `GARAGE_RPC_SECRET` | (generated) | Cluster coordination secret |

### Job Scheduler

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_CLEANUP_INTERVAL` | `3600` | Cleanup interval (seconds) |
| `JOB_APPROVAL_TIMEOUT` | `24` | Cancel unapproved jobs after (hours) |
| `JOB_COMPLETED_RETENTION` | `48` | Delete completed jobs after (hours) |
| `JOB_FAILED_RETENTION` | `168` | Delete failed jobs after (hours) |
| `MAX_CONCURRENT_JOBS` | `4` | Maximum parallel ingestion jobs |

### OAuth Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token validity period |

### AMD GPU (Optional)

Only set if needed for AMD GPU detection:

| Variable | Description |
|----------|-------------|
| `HSA_OVERRIDE_GFX_VERSION` | Override GPU architecture (e.g., `10.3.0`) |
| `ROCR_VISIBLE_DEVICES` | Limit visible GPUs (e.g., `0`) |
| `ROCM_VERSION` | ROCm wheel version (`rocm60`, `rocm61`) |

## Operator Configuration (.operator.conf)

Created during initialization. Controls operator behavior.

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTAINER_PREFIX` | `knowledge-graph` | Container name prefix |
| `CONTAINER_SUFFIX` | - | Container name suffix (e.g., `-dev`) |
| `COMPOSE_FILE` | `docker-compose.yml` | Base compose file |
| `IMAGE_SOURCE` | `local` | `local` or `ghcr` |
| `GPU_MODE` | `auto` | GPU mode |

### Container Naming

Container names follow these patterns:

| Service | Development | Production |
|---------|-------------|------------|
| PostgreSQL | `knowledge-graph-postgres` | `kg-postgres` |
| Garage | `knowledge-graph-garage` | `kg-garage` |
| API | `kg-api-dev` | `kg-api` |
| Web | `kg-web-dev` | `kg-web` |
| Operator | `kg-operator` | `kg-operator` |

The `--container-prefix=kg` flag gives production naming.

## Compose File Selection

The operator automatically selects compose files based on configuration:

| Configuration | Compose Files Used |
|---------------|-------------------|
| Default | `docker-compose.yml` |
| GHCR images | `docker-compose.yml` + `docker-compose.ghcr.yml` |
| Production | `docker-compose.prod.yml` |
| NVIDIA GPU | + `docker-compose.gpu-nvidia.yml` |
| AMD GPU | + `docker-compose.gpu-amd.yml` |
| Dev mode | + `docker-compose.dev.yml` |

## Runtime Configuration

Some settings are configured at runtime via the operator shell:

```bash
./operator.sh shell
```

### AI Provider Configuration

```bash
# Set extraction provider
configure.py ai-provider --provider anthropic --model claude-sonnet-4

# Store API key (encrypted in database)
configure.py api-key anthropic --key "sk-ant-..."

# View current configuration
configure.py show
```

### User Management

```bash
# Create user
configure.py create-user --username alice --email alice@example.com

# Reset password
configure.py reset-password --username admin

# List users
configure.py list-users
```

## Nginx Configuration

For HTTPS deployments, edit `docker/nginx.prod.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name your-hostname.example.com;

    # SSL certificates
    ssl_certificate /etc/nginx/certs/your-hostname.fullchain.cer;
    ssl_certificate_key /etc/nginx/certs/your-hostname.key;

    # API proxy
    location /api/ {
        proxy_pass http://api:8000/;
        # ... proxy settings
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## Next Steps

- [Production Deployment](production.md) - Full deployment guide
- [Troubleshooting](troubleshooting.md) - Common issues
