# Local Development Scripts

**⚠️ WARNING: These scripts are NOT the recommended way to run the platform.**

**Use the operator architecture instead:**
- `./operator/lib/init-secrets.sh --dev` - Generate secrets
- `./operator/lib/start-infra.sh` - Start infrastructure
- `./operator/lib/start-app.sh` - Start application

See `docs/guides/QUICKSTART.md` for the official workflow.

---

## What are these scripts?

These scripts allow you to run individual services manually outside of Docker Compose. They're useful for:
- Deep debugging and development investigation
- Testing individual components in isolation
- Running the API/web app locally against containerized infrastructure

## Scripts

**Run Services:**
- `run-api-local.sh` - Run FastAPI server locally (requires local Python venv)
- `run-viz-local.sh` - Run web UI locally (requires local Node.js)
- `run-database-local.sh` - Start PostgreSQL + AGE container
- `run-garage-local.sh` - Start Garage S3 storage container

**Stop Services:**
- `stop-api-local.sh` - Stop local API server
- `stop-viz-local.sh` - Stop local web UI
- `stop-database-local.sh` - Stop database container
- `stop-garage-local.sh` - Stop garage container

## When to use these

**Use these scripts when:**
- Debugging API code with a local Python debugger
- Testing frontend changes with hot module reload
- Investigating infrastructure issues in isolation

**Do NOT use these for:**
- Normal development workflow (use docker-compose)
- Production deployments (use docker-compose)
- Getting started (use the quickstart guide)

## Example: Run API locally for debugging

```bash
# 1. Start infrastructure containers
./scripts/development/local/run-database-local.sh -y
./scripts/development/local/run-garage-local.sh -y

# 2. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run API locally with hot reload
./scripts/development/local/run-api-local.sh -y --reload

# 4. Clean up
./scripts/development/local/stop-api-local.sh
./scripts/development/local/stop-database-local.sh
./scripts/development/local/stop-garage-local.sh
```

## Note on "local" naming

The `-local.sh` suffix means "run this service manually outside the normal Docker Compose workflow." It doesn't necessarily mean the service runs without Docker (database and garage still use containers, but you're managing them individually rather than through docker-compose).
