---
id: 1.O.08
domain: infra
mode: operations
---

# Troubleshooting

This page covers common failure modes for Kappa Graph self-hosted deployments, including platform containers and client tools.

---

## Platform containers

### Containers won't start

Check logs for the failing service:

```bash
./operator.sh logs api
docker logs kg-api-dev            # dev mode
docker logs knowledge-graph-postgres
```

Check overall status:

```bash
./operator.sh status
docker ps -a
```

Look for containers in "Exited" state. The exit code in `docker ps -a` output narrows the cause before you read logs.

### Port already in use

```
Error: bind: address already in use
```

Port 3000 (web) or 8000 (API) is occupied by another process.

Find the occupying process:

```bash
lsof -i :3000
lsof -i :8000
```

Either stop the conflicting service or change the ports in `.env`.

### Out of memory (exit code 137)

```
Killed
```
or
```
Container exited with code 137
```

The API container requires memory for ML models. Check current usage:

```bash
docker stats
free -h
```

To address the problem:

- Ensure at least 8 GB RAM is available to Docker.
- Reduce `MAX_CONCURRENT_JOBS` in `.env` (default: `4`).
- Set `GPU_MODE=cpu` in `.operator.conf` if GPU memory is constrained, then restart.

### Container health check failing

```bash
./operator.sh status
# Shows container as "unhealthy"
```

Inspect the health detail:

```bash
docker inspect kg-api | grep -A 10 Health
```

Common causes:

- Database not yet ready — wait and retry.
- API still loading models on startup — allow more time.
- Configuration error — read `./operator.sh logs api`.

---

## Database

### Connection refused

```
Connection refused
```

Confirm PostgreSQL is running:

```bash
docker ps | grep postgres
docker logs $(docker ps --format '{{.Names}}' | grep postgres)
```

Confirm the Docker network is intact:

```bash
docker network ls
docker network inspect knowledge-graph-network
```

### Migration errors

```bash
./operator.sh logs operator
```

To run migrations manually:

```bash
./operator.sh shell
/workspace/operator/database/migrate-db.sh -y
```

### Database corruption

If PostgreSQL fails to start due to corruption:

1. **Try a query first** — if the database responds, back up immediately:
   ```bash
   ./operator.sh query 'SELECT version();'
   ```

2. **Restore from backup:**
   ```bash
   ./operator.sh shell
   /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
   ```
   See [Backup and Restore](backup-restore.md) for backup procedures.

3. **Last resort — reinitialize** (destroys all data):
   ```bash
   ./operator.sh teardown --full   # removes volumes
   ./operator.sh init
   ```

---

## Authentication

### Can't log in

Kappa Graph uses OAuth. The `POST /auth/login` endpoint was removed in ADR-054 — authentication flows through `/auth/oauth/login-and-authorize`.

Check that an OAuth client is registered:

```bash
./operator.sh query \
  "SELECT client_id, redirect_uris FROM kg_auth.oauth_clients;"
```

The registered `redirect_uris` must match your `WEB_HOSTNAME`. If they do not match, re-run `./operator.sh init` or update the client record directly.

Reset the admin password:

```bash
./operator.sh admin --username admin --password <new-password>
```

### 500 error during login

```bash
./operator.sh logs api
```

Common causes:

- OAuth client missing the `scopes` column — fixed in current images; run `./operator.sh upgrade`.
- Database connection failure.
- `OAUTH_SIGNING_KEY` mismatch in `.env`.

### Token expired

Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60). Log out and log in again, or increase the value in `.env` and restart the API:

```bash
./operator.sh restart api
```

---

## TLS and certificates

### Certificate not found

```
SSL_CTX_use_certificate_chain_file failed
```

Kappa Graph uses Traefik for TLS termination. See [TLS and Certificates](tls.md) for certificate setup procedures.

Verify the certificate files exist in the configured path:

```bash
ls -la /srv/docker/data/knowledge-graph/certs/
```

### Mixed content warnings

The browser blocks HTTP sub-requests from an HTTPS page.

Check the frontend runtime config:

```bash
docker exec kg-web-dev cat /usr/share/nginx/html/config.js
```

The `apiUrl` must use `https://` when the site itself is served over HTTPS. Set the correct `WEB_HOSTNAME` in `.env` and restart:

```bash
./operator.sh restart web
```

---

## GPU

### GPU not detected

Verify the NVIDIA runtime works outside the container:

```bash
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

Verify GPU access inside the API container:

```bash
docker exec kg-api nvidia-smi
```

If the runtime is missing:

```bash
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

Set `GPU_MODE` in `.operator.conf` to match your hardware: `nvidia`, `amd-host`, `mac`, or `cpu`.

### CUDA out of memory

```
CUDA out of memory
```

Set `GPU_MODE=cpu` in `.operator.conf` and restart, or reduce `MAX_CONCURRENT_JOBS` in `.env`.

---

## Ingestion

### Job stuck in pending

A job enters `awaiting_approval` state when `--no-approve` was passed at submission time, or when the server configuration requires manual approval. By default, the CLI auto-approves submitted jobs.

List pending jobs:

```bash
kg job list
```

Approve a specific job:

```bash
kg job approve job <job-id>
```

Approve all pending jobs at once:

```bash
kg job approve pending
```

To require manual approval when submitting, pass `--no-approve`:

```bash
kg ingest file --no-approve -o <ontology> document.pdf
```

### Extraction failing

```bash
./operator.sh logs api | grep -i error
```

Common causes:

- AI provider API key is invalid or expired — reconfigure via `./operator.sh shell` then `configure.py ai-provider`.
- Provider rate limit reached — wait and retry.
- Document format not supported.

### Large document timeout

Split the document into smaller files before ingestion, or increase the API worker timeout in `.env` and restart:

```bash
./operator.sh restart api
```

---

## CLI and client tools

### `kg` command not found after installation

If you installed via `npm install -g @aaronsb/kg-cli`, ensure `~/.local/bin` (or the npm global bin directory) is on your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this line to `~/.bashrc` or `~/.zshrc` for persistence.

To rebuild and reinstall from source:

```bash
cd cli
npm run build
./install.sh
```

Requires Node.js 20.12.0 or later. Check with `node --version`.

### CLI authentication failed

Re-authenticate:

```bash
kg logout
kg login
```

Confirm the CLI is pointing at the right API:

```bash
kg config get api_url
```

The CLI stores its configuration at `~/.config/kg/config.json`.

### Connection refused from CLI

```bash
kg config get api_url
curl -s https://kg.example.com/api/health
```

If the health check returns an error, the problem is on the server side — check `./operator.sh status` and `./operator.sh logs api`.

---

## Collecting diagnostic information

Before opening a GitHub issue, gather:

```bash
./operator.sh status
./operator.sh versions
./operator.sh logs api > logs.txt 2>&1
docker ps -a
docker version
cat .env | grep -v KEY | grep -v SECRET | grep -v PASSWORD
```

Open an issue at <https://github.com/aaronsb/knowledge-graph-system/issues> and include:

- What you were trying to do.
- What happened instead.
- Relevant log excerpts (sanitize secrets before posting).
- OS, Docker version, and GPU mode.
