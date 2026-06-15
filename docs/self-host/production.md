---
id: 1.O.04
domain: infra
mode: operations
---

# Production Deployment

This page covers deploying Kappa Graph on a production server: pulling pre-built images from
GHCR, running a headless initialization, configuring TLS, and verifying the result.

For a quick local install, see [Quick Start](quick-start.md). For upgrading an existing
deployment, see [Upgrading](upgrading.md).

---

## Prerequisites

- Linux server (Ubuntu 22.04+ or Debian 12+ recommended)
- 16 GB RAM minimum (8 GB usable but slow under load)
- A domain name and DNS control (required for TLS)
- Docker with the Compose plugin

Docker will be installed automatically by the installer if it is not already present.
Optional: an NVIDIA GPU with the NVIDIA Container Toolkit, for faster LLM extraction.

---

## Container images

Kappa Graph publishes four pre-built images to GitHub Container Registry:

| Image | Purpose |
|---|---|
| `ghcr.io/aaronsb/knowledge-graph-system/kg-postgres:latest` | PostgreSQL 18 + Apache AGE 1.7.0 + graph acceleration extension |
| `ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest` | FastAPI REST server (ingestion, queries, OAuth) |
| `ghcr.io/aaronsb/knowledge-graph-system/kg-web:latest` | React visualization web app |
| `ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest` | Configuration and management container |

### Tag scheme

| Tag form | Meaning |
|---|---|
| `latest` | Most recent build from `main` — always a functional platform |
| `1.2.3` | Full semantic version (official release) |
| `1.2` | Major.minor alias pointing to the same release image |
| `main-abc1234` | Commit SHA tag — every `main` commit is tagged for traceability |

`latest` is stable: `main` is gated and `latest` only advances when a build passes.
Pin to a semantic version tag (`1.2.3`) when you need reproducible deploys across
restarts.

### Authenticating to GHCR

Public images require no authentication. If you hit rate limits:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### Checking available tags

```bash
curl -s \
  "https://api.github.com/users/aaronsb/packages/container/knowledge-graph-system%2Fkg-api/versions" \
  | jq -r '.[].metadata.container.tags[]'
```

---

## Installation

### Standalone installer (recommended)

The installer handles Docker setup, secret generation, TLS, and first-run configuration:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

For automated (headless) deployment, pass flags directly:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash -s -- \
  --hostname kg.example.com \
  --ssl letsencrypt \
  --ssl-email admin@example.com \
  --ai-provider anthropic \
  --ai-key "$ANTHROPIC_API_KEY" \
  --gpu nvidia
```

SSL options for the installer:

| Flag | Behaviour |
|---|---|
| `--ssl offload` | HTTP inside the VM; an external edge terminates TLS |
| `--ssl selfsigned` | Traefik serves its built-in self-signed certificate |
| `--ssl letsencrypt` | Traefik obtains a Let's Encrypt cert via TLS-ALPN-01 |
| `--ssl manual` | Operator supplies `tls.crt` + `tls.key` (cert issued off-box) |

`install.sh --ssl <mode>` and `operator.sh init --tls=<mode>` configure the same TLS behaviour; the flag names differ because they live in separate tools with separate namespaces.

After installation:

```bash
cd ~/knowledge-graph        # default install directory
./operator.sh status        # confirm all containers are running
./operator.sh logs api      # check API startup
./operator.sh shell         # open the configuration shell
```

### Clone + operator (alternative)

If you prefer to work from the repository:

```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --router=traefik \
  --tls=letsencrypt \
  --le-email=admin@example.com \
  --gpu=nvidia \
  --web-hostname=kg.example.com \
  --ai-provider=anthropic \
  --ai-model=claude-sonnet-4 \
  --ai-key="$ANTHROPIC_API_KEY"
```

Run `./operator.sh init --headless --help` for the full parameter list.

#### Key `--headless` parameters

**Infrastructure**

| Parameter | Values | Default | Notes |
|---|---|---|---|
| `--image-source` | `local`, `ghcr` | `local` | Use `ghcr` for production |
| `--gpu` | `auto`, `nvidia`, `amd`, `amd-host`, `mac`, `cpu` | `auto` | `nvidia` requires NVIDIA Container Toolkit |
| `--container-prefix` | string | `knowledge-graph` | Prefix for container names |
| `--router` | `none`, `traefik` | `none` | `traefik` is required for in-VM TLS |

**TLS** (requires `--router=traefik`)

| `--tls` value | Behaviour |
|---|---|
| `none` | No TLS; plain HTTP |
| `selfsigned` | Traefik built-in self-signed cert |
| `manual` | Cert + key dropped into `docker/certs/tls.crt` and `tls.key` |
| `letsencrypt` | Traefik ACME TLS-ALPN-01; requires `--le-email` and port 443 reachable |
| `offload` | HTTP in-VM; external edge (load balancer, CDN) terminates TLS |

**Web and AI**

| Parameter | Description |
|---|---|
| `--web-hostname` | Public hostname — used for OAuth redirect URIs and the API base URL |
| `--ai-provider` | `openai`, `anthropic`, or `openrouter` |
| `--ai-model` | Model name (e.g., `gpt-4o`, `claude-sonnet-4`) |
| `--ai-key` | API key for the provider |
| `--skip-ai-config` | Defer AI configuration to after startup |

---

## TLS in production

### Let's Encrypt (automated renewal)

Port 443 must be reachable from the internet. Traefik's ACME resolver handles issuance and
renewal automatically; no cron job or external tool is needed.

Set `--tls=letsencrypt` and `--le-email` during init. Test against the staging CA first to
avoid rate limits:

```bash
# add to .env before starting, or pass via --external-url
LE_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory
```

Certs persist in `./acme/acme.json`. Back this file up alongside `.env`.

### Manual cert (cert issued off-box)

Use this path when the server does not hold DNS credentials — for example, when a cert is
issued on a separate machine and copied over.

Drop the cert and key into the location Traefik watches:

```bash
mkdir -p docker/certs
cp /path/to/fullchain.pem docker/certs/tls.crt
cp /path/to/privkey.pem   docker/certs/tls.key
```

Set `--tls=manual` during init (or `TLS_MODE=manual` in `.env` before restarting).
Traefik's file provider watches the directory and hot-reloads the cert without a restart when
you replace the files near expiry.

To trigger or verify renewal: `./operator.sh recert`

### Offload (edge terminates TLS)

When Kappa Graph sits behind a load balancer or CDN that terminates TLS, set
`--tls=offload`. The containers listen on HTTP; the external edge handles encryption.
Pass `--external-url=https://kg.example.com` so OAuth redirect URIs are generated with the
correct public URL.

---

## Secrets

`./operator.sh init` generates `.env` once and never overwrites it. The file contains:

| Variable | Purpose |
|---|---|
| `ENCRYPTION_KEY` | Fernet key — encrypts AI provider API keys at rest |
| `OAUTH_SIGNING_KEY` | Signs JWT tokens |
| `POSTGRES_PASSWORD` | Database password |
| `INTERNAL_KEY_SERVICE_SECRET` | Service-to-service auth token |
| `GARAGE_RPC_SECRET` | Garage cluster coordination |

**Never commit `.env` to version control.** Back it up to a secrets manager or encrypted
storage alongside the database volume. Losing `.env` means losing access to any encrypted
API keys stored in the database.

AI provider keys are stored encrypted in the database, not in `.env`:

```bash
./operator.sh shell
configure.py api-key anthropic --key "sk-ant-..."
```

---

## Data locations

Default bind-mount paths (configured in the compose files):

| Data | Host path |
|---|---|
| PostgreSQL database | `/srv/docker/data/knowledge-graph/postgres` |
| Garage object storage | `/srv/docker/data/knowledge-graph/garage` |
| Model/embedding cache | `/srv/docker/data/knowledge-graph/hf_cache` |
| TLS certs (manual mode) | `docker/certs/` |
| ACME state (Let's Encrypt) | `./acme/acme.json` |

---

## GPU configuration

| Mode | Flag | Requirement |
|---|---|---|
| NVIDIA | `--gpu=nvidia` | NVIDIA Container Toolkit on the host |
| AMD (container ROCm) | `--gpu=amd` | AMD GPU; ROCm wheels inside image |
| AMD (host ROCm) | `--gpu=amd-host` | ROCm installed on the host |
| macOS (MPS) | `--gpu=mac` | Apple Silicon or AMD GPU via Metal Performance Shaders |
| CPU only | `--gpu=cpu` | No GPU required; slower extraction |

---

## Monitoring

```bash
./operator.sh status          # container health summary
./operator.sh logs api        # API logs
./operator.sh logs --follow   # tail all logs
```

API health endpoint:

```bash
curl https://kg.example.com/api/health
```

---

## Orchestrated deployments (Swarm / Kubernetes)

The operator tooling targets single-host Docker Compose. For orchestrated environments,
use the GHCR images directly and supply secrets via the orchestrator's native secrets
mechanism.

**Docker Swarm** — pass infrastructure secrets (encryption key, DB password) via
`docker secret` and reference them with `_FILE` environment variable suffixes.

**Kubernetes** — use `secretKeyRef` in the pod spec. The API container exposes
`GET /health` on port 8000 for liveness and readiness probes.

In both cases, pin image tags to a semantic version for reproducible rollouts:

```
ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.2.3
ghcr.io/aaronsb/knowledge-graph-system/kg-web:1.2.3
ghcr.io/aaronsb/knowledge-graph-system/kg-operator:1.2.3
ghcr.io/aaronsb/knowledge-graph-system/kg-postgres:1.2.3
```

---

## Next steps

- [Configuration Reference](configuration.md) — all `.env` and compose settings
- [Backup and Restore](backup-restore.md) — database and volume backup procedures
- [Upgrading](upgrading.md) — pull new images and run migrations
- [Troubleshooting](troubleshooting.md) — diagnose startup and connectivity issues
