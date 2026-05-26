# Troubleshooting

Common issues and how to fix them.

## Container Issues

### Containers Won't Start

**Check logs** (substitute the correct container name — see
[Configuration > Container Naming](configuration.md#container-naming)):
```bash
./operator.sh logs api
docker logs kg-api                          # or kg-api-dev in dev mode
docker logs knowledge-graph-postgres        # or kg-postgres with --container-prefix=kg
```

**Check container status:**
```bash
./operator.sh status
docker ps -a
```

Look for containers in "Exited" state and check their logs.

### Port Already in Use

```
Error: bind: address already in use
```

Something else is using port 3000 (web) or 8000 (api).

**Find what's using the port:**
```bash
lsof -i :3000
lsof -i :8000
```

**Options:**
1. Stop the conflicting service
2. Change ports in `.env` or compose file

### Out of Memory

```
Killed
```
or
```
Container exited with code 137
```

The API container needs memory for ML models.

**Check memory:**
```bash
docker stats
free -h
```

**Solutions:**
- Ensure 8GB+ RAM available
- Reduce `MAX_CONCURRENT_JOBS` in `.env`
- Use CPU mode if GPU memory is limited

### Container Health Check Failing

```bash
./operator.sh status
# Shows containers as "unhealthy"
```

**Check health status:**
```bash
docker inspect kg-api | grep -A 10 Health
```

**Common causes:**
- Database not ready yet (wait longer)
- API startup still in progress (models loading)
- Configuration error (check logs)

## Database Issues

### Database Connection Failed

```
Connection refused
```

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
docker logs $(docker ps --format '{{.Names}}' | grep postgres)
```

**Check network:**
```bash
docker network ls
docker network inspect knowledge-graph-network
```

### Migration Errors

```
Migration failed
```

**Check migration logs:**
```bash
./operator.sh logs operator
```

**Run migrations manually:**
```bash
./operator.sh shell
/workspace/operator/database/migrate-db.sh -y
```

### Database Corrupted

If PostgreSQL won't start due to corruption:

1. **Try recovery mode** (use the postgres container name shown by
   `./operator.sh status`):
   ```bash
   ./operator.sh query 'SELECT version();'
   # If this works, back up immediately
   ```

2. **Restore from backup** (uses `pg_restore` inside the operator container):
   ```bash
   ./operator.sh shell
   /workspace/operator/database/restore-database.sh /project/backups/<file>.dump
   ```

3. **Last resort - reinitialize:**
   ```bash
   ./operator.sh teardown --full  # WARNING: Destroys data (removes volumes)
   ./operator.sh init
   ```

## Authentication Issues

### Can't Log In

**Check OAuth client exists:**
```bash
./operator.sh query \
  "SELECT client_id, redirect_uris FROM kg_auth.oauth_clients;"
```

**Ensure redirect URI matches:**
The registered redirect URI must match your `WEB_HOSTNAME`.

**Reset admin password:**
```bash
./operator.sh admin --username admin --password <new-password>
```

### 500 Error on Login

Check API logs:
```bash
./operator.sh logs api
```

**Common causes:**
- OAuth client missing `scopes` column (fixed in recent versions)
- Database connection issue
- Secret key mismatch

### Token Expired

Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).

**Solution:** Log out and log in again, or increase the timeout in `.env`.

## HTTPS/SSL Issues

### Certificate Not Found

```
SSL_CTX_use_certificate_chain_file failed
```

**Check certificate paths:**
```bash
ls -la /srv/docker/data/knowledge-graph/certs/
```

**Check nginx config matches:**
```bash
cat docker/nginx.prod.conf | grep ssl_certificate
```

### Certificate Expired

**Renew manually:**
```bash
~/.acme.sh/acme.sh --renew -d kg.example.com
~/.acme.sh/acme.sh --install-cert -d kg.example.com \
  --key-file /srv/docker/data/knowledge-graph/certs/kg.example.com.key \
  --fullchain-file /srv/docker/data/knowledge-graph/certs/kg.example.com.fullchain.cer
docker exec kg-web nginx -s reload
```

### Mixed Content Warnings

Browser blocks HTTP requests from HTTPS page.

**Check frontend config:**
```bash
docker exec kg-web cat /usr/share/nginx/html/config.js
```

The `apiUrl` should use `https://` if your site uses HTTPS.

**Fix:** Set correct `WEB_HOSTNAME` and restart:
```bash
./operator.sh restart web
```

## GPU Issues

### GPU Not Detected

**Check NVIDIA runtime:**
```bash
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

**Check container GPU access:**
```bash
docker exec kg-api nvidia-smi
```

**Reinstall NVIDIA Container Toolkit:**
```bash
# Ubuntu/Debian
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### CUDA Out of Memory

```
CUDA out of memory
```

**Reduce batch size** by setting environment variable or reducing concurrent jobs.

**Use CPU fallback:**
Set `GPU_MODE=cpu` in `.operator.conf` and restart.

## Ingestion Issues

### Job Stuck in Pending

Jobs require approval by default.

**Check job status:**
```bash
kg job list
```

**Approve pending jobs:**
```bash
kg job approve <job-id>
```

**Enable auto-approval** in ingestion request:
```bash
kg ingest --auto-approve document.pdf
```

### Extraction Failing

**Check API logs:**
```bash
./operator.sh logs api | grep -i error
```

**Common causes:**
- AI provider API key invalid or expired
- Rate limited by provider
- Document format not supported

### Large Document Timeout

**Increase timeout:**
Edit nginx configuration or API timeout settings.

**Split document:**
Break into smaller files before ingestion.

## CLI Issues

### kg Command Not Found

**Reinstall CLI:**
```bash
cd cli
npm run build
./install.sh
```

**Check PATH:**
```bash
echo $PATH
which kg
```

### CLI Authentication Failed

**Re-authenticate:**
```bash
kg logout
kg login
```

**Check API URL:**
```bash
kg config get
kg config get api_url
```

## Getting More Help

### Collect Diagnostic Info

```bash
./operator.sh status
./operator.sh versions
./operator.sh logs api > logs.txt 2>&1
docker ps -a
docker version
cat .env | grep -v KEY | grep -v SECRET | grep -v PASSWORD
```

### Report an Issue

Open an issue at https://github.com/aaronsb/knowledge-graph-system/issues with:
- What you were trying to do
- What happened instead
- Relevant logs (sanitize secrets!)
- System info (OS, Docker version, GPU)
