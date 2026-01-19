# Production Deployment

Full guide for deploying the knowledge graph system in production.

## Overview

Production deployment differs from quick start:
- Pre-built container images from GitHub Container Registry (GHCR)
- Headless (non-interactive) initialization
- HTTPS with real certificates
- Proper hostname configuration for OAuth
- GPU acceleration configured explicitly

## Prerequisites

- Linux server (Ubuntu 20.04+ or Debian 11+ recommended)
- 16GB+ RAM (8GB minimum)
- NVIDIA GPU recommended for faster extraction
- A domain name (for HTTPS)
- DNS control (for certificate issuance)

Docker will be installed automatically if not present.

---

## Recommended: Standalone Installer

The easiest way to deploy to a production server:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

This interactive installer:
- Installs Docker if needed
- Downloads pre-built images from GHCR
- Generates secure secrets
- Configures SSL/HTTPS
- Sets up admin user and AI provider

### Headless Installer

For fully automated deployments:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash -s -- \
  --hostname kg.example.com \
  --ssl letsencrypt \
  --ssl-email admin@example.com \
  --ai-provider anthropic \
  --ai-key "$ANTHROPIC_API_KEY" \
  --gpu nvidia
```

**SSL options:**
- `--ssl offload` - HTTP only (behind reverse proxy that handles SSL)
- `--ssl selfsigned` - Generate self-signed certificate
- `--ssl letsencrypt` - Auto-generate via Let's Encrypt (requires `--ssl-email`)
- `--ssl manual` - Use existing certificates (requires `--ssl-cert` and `--ssl-key`)

### After Installation

```bash
cd ~/knowledge-graph   # Default install location

./operator.sh status   # Verify everything is running
./operator.sh logs api # Check API logs
./operator.sh shell    # Configuration shell
```

---

## Alternative: Git Clone + Operator

If you prefer to work from the git repository:

```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
./operator.sh init --headless ...
```

### Headless Initialization

```bash
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --gpu=nvidia \
  --web-hostname=kg.example.com \
  --ai-provider=anthropic \
  --ai-model=claude-sonnet-4 \
  --ai-key="$ANTHROPIC_API_KEY"
```

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `--headless` | Enable non-interactive mode |

### Infrastructure Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--image-source` | `local`, `ghcr` | `local` | Where to get container images |
| `--gpu` | `auto`, `nvidia`, `amd`, `amd-host`, `mac`, `cpu` | `auto` | GPU acceleration mode |
| `--container-prefix` | `kg`, `knowledge-graph` | `knowledge-graph` | Container name prefix |
| `--compose-file` | path | `docker-compose.yml` | Base compose file |

### Web Configuration

| Parameter | Description |
|-----------|-------------|
| `--web-hostname` | Public hostname for web access (e.g., `kg.example.com`) |

The hostname is used for:
- OAuth redirect URIs
- API URL in frontend configuration
- SSL certificate common name

### AI Configuration

| Parameter | Description |
|-----------|-------------|
| `--ai-provider` | `openai`, `anthropic`, or `openrouter` |
| `--ai-model` | Model name (e.g., `gpt-4o`, `claude-sonnet-4`) |
| `--ai-key` | API key for the provider |
| `--skip-ai-config` | Skip AI configuration entirely |

### Other Options

| Parameter | Description |
|-----------|-------------|
| `--password-mode` | `random` (secure) or `simple` (dev defaults) |
| `--container-mode` | `regular` or `dev` (hot reload) |
| `--skip-cli` | Skip CLI installation |

## GPU Configuration

### NVIDIA GPU

```bash
./operator.sh init --headless --gpu=nvidia ...
```

Requires NVIDIA Container Toolkit installed on the host.

### AMD GPU (ROCm)

```bash
./operator.sh init --headless --gpu=amd ...
```

Uses ROCm PyTorch wheels inside the container.

### AMD GPU (Host ROCm)

```bash
./operator.sh init --headless --gpu=amd-host ...
```

Uses ROCm installed on the host system.

### CPU Only

```bash
./operator.sh init --headless --gpu=cpu ...
```

No GPU acceleration. Slower but works everywhere.

## HTTPS Configuration

### Using Let's Encrypt with DNS Validation

1. **Install acme.sh on the host:**
   ```bash
   curl https://get.acme.sh | sh
   ```

2. **Configure your DNS provider** (example: Porkbun):
   ```bash
   export PORKBUN_API_KEY="your-api-key"
   export PORKBUN_SECRET_API_KEY="your-secret-key"
   ```

3. **Issue the certificate:**
   ```bash
   ~/.acme.sh/acme.sh --issue \
     --dns dns_porkbun \
     -d kg.example.com
   ```

4. **Install to a location the container can access:**
   ```bash
   mkdir -p /srv/docker/data/knowledge-graph/certs
   ~/.acme.sh/acme.sh --install-cert -d kg.example.com \
     --key-file /srv/docker/data/knowledge-graph/certs/kg.example.com.key \
     --fullchain-file /srv/docker/data/knowledge-graph/certs/kg.example.com.fullchain.cer
   ```

5. **Configure nginx** - edit `docker/nginx.prod.conf`:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name kg.example.com;

       ssl_certificate /etc/nginx/certs/kg.example.com.fullchain.cer;
       ssl_certificate_key /etc/nginx/certs/kg.example.com.key;

       # ... rest of config
   }
   ```

6. **Mount certificates in compose** - the `docker-compose.prod.yml` mounts:
   ```yaml
   volumes:
     - /srv/docker/data/knowledge-graph/certs:/etc/nginx/certs:ro
   ```

### Certificate Renewal

acme.sh sets up automatic renewal via cron. After renewal, reload nginx:

```bash
docker exec kg-web nginx -s reload
```

## Example: Full Production Deployment

```bash
# On your production server
cd ~/knowledge-graph-system

# Set environment variables
export ANTHROPIC_API_KEY="sk-ant-..."

# Initialize with all production settings
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --gpu=nvidia \
  --web-hostname=kg.example.com \
  --ai-provider=anthropic \
  --ai-model=claude-sonnet-4 \
  --ai-key="$ANTHROPIC_API_KEY"

# Verify everything is running
./operator.sh status

# Check the web interface
curl -I https://kg.example.com
```

## Secrets and Security

### Generated Secrets

During initialization, these are generated and stored in `.env`:

| Secret | Purpose |
|--------|---------|
| `ENCRYPTION_KEY` | Encrypts API keys at rest |
| `OAUTH_SIGNING_KEY` | Signs JWT tokens |
| `POSTGRES_PASSWORD` | Database password |
| `INTERNAL_KEY_SERVICE_SECRET` | Service-to-service auth |
| `GARAGE_RPC_SECRET` | Storage cluster coordination |

**Never commit `.env` to version control.**

### AI Provider Keys

AI provider API keys (OpenAI, Anthropic) are stored encrypted in the database, not in `.env`. They're configured via:

```bash
./operator.sh shell
configure.py api-key anthropic --key "sk-ant-..."
```

Or via the `--ai-key` flag during headless init.

## Data Locations

Default data paths (can be customized in compose files):

| Data | Location |
|------|----------|
| PostgreSQL database | `/srv/docker/data/knowledge-graph/postgres` |
| Garage object storage | `/srv/docker/data/knowledge-graph/garage` |
| Model cache | `/srv/docker/data/knowledge-graph/hf_cache` |
| SSL certificates | `/srv/docker/data/knowledge-graph/certs` |

## Upgrading

See [Upgrading](upgrading.md) for version upgrade procedures.

```bash
# Quick upgrade
./operator.sh upgrade

# See what would change first
./operator.sh upgrade --dry-run
```

## Monitoring

### Container Health

```bash
./operator.sh status          # Quick status
docker ps                     # Detailed container info
./operator.sh logs api        # API logs
./operator.sh logs --follow   # Tail all logs
```

### API Health Check

```bash
curl http://localhost:8000/health
# Or via HTTPS:
curl https://kg.example.com/api/health
```

## Next Steps

- [Configuration Reference](configuration.md) - All settings explained
- [Backup & Restore](backup-restore.md) - Protect your data
- [Troubleshooting](troubleshooting.md) - When things go wrong
