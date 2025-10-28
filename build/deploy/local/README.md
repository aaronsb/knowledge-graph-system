# Local Deployment Scripts

Deploy components locally for development using locally built artifacts.

## Overview

Local deployment uses source code and local builds. Changes to code are reflected immediately (or after rebuild). This mode is optimized for development speed, not production performance.

## Scripts

### `deploy-all.sh`
Deploy the entire stack:
```bash
./deploy-all.sh [options]
```

Options:
- `--clean` - Stop and remove existing containers/processes
- `--no-api` - Skip API server
- `--no-database` - Skip database (use existing)

### `deploy-database.sh`
Deploy PostgreSQL + Apache AGE:
```bash
./deploy-database.sh [--reset]
```

Options:
- `--reset` - Drop and recreate database

What it does:
- Starts docker-compose with PostgreSQL + AGE
- Waits for database to be ready
- Applies schema migrations
- Seeds builtin vocabulary (if needed)

### `deploy-api.sh`
Deploy the API server:
```bash
./deploy-api.sh [options]
```

Options:
- `--background` - Run as background process
- `--reload` - Enable auto-reload on code changes

What it does:
- Activates Python venv
- Starts Uvicorn server
- Enables hot-reload for development
- Logs to `logs/api_*.log`

### `deploy-viz.sh`
Deploy visualization server:
```bash
./deploy-viz.sh
```

**Status:** Stub - not yet implemented

## Development Workflow

Typical development cycle:

```bash
# 1. Start infrastructure
./deploy-database.sh

# 2. Start API with auto-reload
./deploy-api.sh --reload

# 3. In another terminal, test changes
kg health
kg ingest file -o Test document.txt

# 4. Make code changes
vim ../../../src/api/routes/queries.py

# 5. API auto-reloads, test again
kg search query "test"
```

## Configuration

Local deployment reads from `.env` in repo root:

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

## Stopping Services

```bash
# Stop API
./scripts/stop-api.sh

# Stop database
./scripts/stop-database.sh

# Or stop everything
docker-compose down
pkill -f "uvicorn.*main:app"
```

## Resetting State

```bash
# Reset database (drops all data)
docker-compose down -v
./deploy-database.sh

# Reset API (restart process)
./scripts/stop-api.sh
./deploy-api.sh --background

# Full reset
docker-compose down -v
./deploy-all.sh --clean
```

## Port Management

Local deployment uses default ports:
- PostgreSQL: 5432
- API: 8000
- Visualization: 3000 (future)

To use different ports:
```bash
export KG_API_PORT=8001
./deploy-api.sh
```

## Differences from Production

| Feature | Local | Production |
|---------|-------|----------|
| Auto-reload | ✓ Enabled | ✗ Disabled |
| Debug logs | ✓ Verbose | ✗ INFO only |
| Hot paths | Source code | Compiled |
| Optimization | ✗ None | ✓ Enabled |
| Security | ✗ Permissive | ✓ Strict |

## Troubleshooting

### "Address already in use"
```bash
# Find process using port
lsof -i :8000

# Kill it or use different port
export KG_API_PORT=8001
```

### Auto-reload not working
```bash
# Ensure --reload flag is used
./deploy-api.sh --reload

# Check file watchers
# Sometimes inotify limits are low on Linux
echo 8192 | sudo tee /proc/sys/fs/inotify/max_user_watches
```

### Database connection fails
```bash
# Check database is running
docker ps | grep postgres

# Check connection from API container
docker exec knowledge-graph-postgres psql -U kg_user -d knowledge_graph

# Review logs
docker logs knowledge-graph-postgres
tail -f logs/api_*.log
```

## See Also

- [Build Scripts](../../local/README.md)
- [Remote Deployment](../remote/README.md)
- [Development Guide](../../../CLAUDE.md)
