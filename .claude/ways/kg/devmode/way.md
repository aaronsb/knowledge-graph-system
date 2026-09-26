---
pattern: hot.?reload|dev.?mode|live.?reload|volume.?mount|container.*watch|rebuild.*container|code.*change.*container
commands: operator\.sh\s+(start|restart|init)
description: Dev mode volume mounts, hot reload behavior, and when container rebuilds are needed
vocabulary: dev mode hot reload volume mount container restart rebuild watch live
scope: agent, subagent
---
# Dev Mode Way

## How It Works

`./operator.sh init` in dev mode sets `DEV_MODE=true` in `.operator.conf`. The dev compose overlay mounts source directories into containers so code changes take effect without rebuilding.

## API: Hot Reload

Dev runs uvicorn with `--reload --reload-dir /app/api`: one app process, matching production's single worker. Edits under `api/` restart the process in a few seconds, including the embedding model load. Edits to `tests/` and `scripts/` don't trigger a reload.

A reload waits for the old process to exit. An edit made while an ingest job runs holds the API down until the job finishes; `./operator.sh restart api` cuts that short.

## What Hot Reloads (No Rebuild)

| Service | Mounted Path | Mechanism |
|---------|-------------|-----------|
| **API** (Python/FastAPI) | `api/` → `/app/api` | uvicorn `--reload` (WatchFiles) |
| **Web** (React/Vite) | `web/src/` → `/app/src` | Vite HMR via WebSocket |
| **Operator** (Bash/Python) | repo → `/workspace` | Scripts read fresh on each execution |

Also mounted in dev: `schema/`, `tests/`, `scripts/`, config files (vite.config.ts, tsconfig).

Web `node_modules` is an anonymous volume — stays in the container, not mounted from host. Compose reuses it across recreates, so `./operator.sh start` rebuilds the web image and renews the volume in dev mode.

## What Requires a Rebuild

| Change | Why | Command |
|--------|-----|---------|
| `api/requirements.txt` | Python deps baked into image | `./operator.sh upgrade` (rebuilds in dev) |
| `web/package.json` | npm deps baked into image | `./operator.sh start` (not `restart web`, which keeps the old volume) |
| `operator/requirements.txt` | Python deps in operator image | `./operator.sh self-update` |
| Dockerfile changes | New system packages, base image | Rebuild with docker compose |
| PyTorch variant (ROCm/CUDA/CPU) | Different base layers | Full rebuild |

## Quick Reference

```bash
./operator.sh start              # Start with dev mounts if DEV_MODE=true
./operator.sh restart api        # Force-restart API (e.g. to cut short a reload waiting on a job)
./operator.sh restart web        # Restart web (does not refresh node_modules)
./operator.sh logs api -f        # Follow API logs
./operator.sh logs web -f        # Follow Vite output (see HMR events)
```

## Common Gotchas

- **API code changes** hot-reload; a reload during a running job waits for it
- **Schema SQL changes** are mounted but not watched — run migrations, then `./operator.sh restart api`
- **Web env vars** (like `VITE_API_URL`) require container restart — the entrypoint regenerates `config.js` on start
- **API model downloads** (HuggingFace) persist in a named volume — not lost on restart
