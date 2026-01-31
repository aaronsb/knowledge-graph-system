---
match: regex
pattern: hot.?reload|dev.?mode|live.?reload|volume.?mount|container.*watch|rebuild.*container|code.*change.*container
commands: operator\.sh\s+(start|restart|init)
---
# Dev Mode Way

## How It Works

`./operator.sh init` in dev mode sets `DEV_MODE=true` in `.operator.conf`. The dev compose overlay mounts source directories into containers so code changes take effect without rebuilding.

## What Hot Reloads (No Rebuild)

| Service | Mounted Path | Mechanism |
|---------|-------------|-----------|
| **API** (Python/FastAPI) | `api/` → `/app/api` | uvicorn `--reload` watches Python files |
| **Web** (React/Vite) | `web/src/` → `/app/src` | Vite HMR via WebSocket |
| **Operator** (Bash/Python) | repo → `/workspace` | Scripts read fresh on each execution |

Also mounted in dev: `schema/`, `tests/`, `scripts/`, config files (vite.config.ts, tailwind, tsconfig).

Web `node_modules` is an anonymous volume — stays in the container, not mounted from host.

## What Requires a Rebuild

| Change | Why | Command |
|--------|-----|---------|
| `api/requirements.txt` | Python deps baked into image | `./operator.sh restart api` after rebuild |
| `web/package.json` | npm deps baked into image | `./operator.sh restart web` after rebuild |
| `operator/requirements.txt` | Python deps in operator image | `./operator.sh self-update` |
| Dockerfile changes | New system packages, base image | Rebuild with docker compose |
| PyTorch variant (ROCm/CUDA/CPU) | Different base layers | Full rebuild |

## Quick Reference

```bash
./operator.sh start              # Start with dev mounts if DEV_MODE=true
./operator.sh restart api        # Restart API (picks up env var changes)
./operator.sh restart web        # Restart web
./operator.sh logs api -f        # Follow API logs (see reload events)
./operator.sh logs web -f        # Follow Vite output (see HMR events)
```

## Common Gotchas

- **Schema SQL changes** reload automatically (mounted into API container)
- **Web env vars** (like `VITE_API_URL`) require container restart — the entrypoint regenerates `config.js` on start
- **API model downloads** (HuggingFace) persist in a named volume — not lost on restart
- **If hot reload stops working**, check `./operator.sh logs <service> -f` for crash loops
