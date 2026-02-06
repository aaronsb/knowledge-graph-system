---
match: regex
pattern: \bmake\b|makefile|run.*(test|suite|lint)|static.?analysis|code.?quality|docstring.?coverage|todo.?marker|scan.?for.*(antipattern|slop)|generate.?docs|build.?doc|reference.?doc|mkdocs|publish|release.?version|platform.?(health|status|start|stop|restart)|follow.?logs|diagnos|rebuild.?container|\bpytest\b|python3?\s.*pytest|PYTHONPATH|\.?/?venv|pip\s+install|npm\s+(test|run)|cargo\s+(test|pgrx)|docker\s+exec\s+kg-|operator\.sh
commands: ^make\s|^pytest|^python3?\s|^PYTHONPATH|^docker exec kg-|^npm (test|run)|^cargo (test|pgrx)|^\./operator\.sh
scope: agent, subagent
---
# Make Targets Way

**You're seeing this because you're about to run a raw command that make
already handles.** Use `make <target>` from the project root instead.
All test targets verify the container is running before execution.

If no make target covers what you need, use your judgement and run the
command directly — this guidance isn't a cage.

## Stop — use make, not raw commands

Do NOT reach for these directly. Make handles container checks, paths, and
flags so you don't have to.

| Instead of | Use |
|------------|-----|
| `pytest tests/` | `make test` |
| `python3 -m pytest tests/unit/` | `make test-unit` |
| `PYTHONPATH=. pytest ...` | `make test-unit` or `make test` |
| `docker exec kg-api-dev pytest ...` | `make test` (checks container for you) |
| `npm test` (from cli/) | `make test` covers Python; CLI tests are `cd cli && npm test` |
| `cargo test` (from graph-accel/) | `make build-graph-accel` for builds; Rust tests are `cd graph-accel && cargo test` |
| `cargo pgrx test pg17` | Run manually only when working on the extension |
| `python3 scripts/development/lint/...` | `make lint`, `make coverage`, `make todos`, `make slopscan` |
| `./operator.sh start/stop/status` | `make start`, `make stop`, `make status` |
| `pip install ...` or `venv` | Everything runs in containers — no local Python env needed |

## Testing (runs inside kg-api-dev container)

```bash
make test              # Full test suite
make test-unit         # Unit tests only
make test-api          # API route tests only
make test-program      # GraphProgram validation spec
make test-verbose      # Full suite, verbose
make test-list         # Show available test suites
```

## Static Analysis

```bash
make lint              # All static analysis
make lint-queries      # Cypher query safety
make coverage          # Docstring coverage (Python, TS, Rust)
make coverage-verbose  # Each undocumented item with file:line
make coverage-staleness # Check @verified tag freshness
make todos             # TODO/FIXME/HACK/XXX markers
make todos-verbose     # Every marker with file:line
make todos-age         # Include git blame age per marker
make slopscan          # SLOPSCAN 9000: detect agent antipatterns
```

## Documentation

```bash
make docs              # Generate all reference docs (CLI + MCP)
make docs-cli          # CLI command reference
make docs-mcp          # MCP server tool reference
make docs-site         # Build MkDocs site
```

## Publishing

```bash
make publish           # Interactive publish wizard
make publish-status    # Current versions and auth status
```

## Platform

```bash
make start             # Start the platform
make stop              # Stop the platform
make restart           # Restart the platform
make status            # Platform health
make logs              # Follow API logs (Ctrl-C to stop)
make diagnose          # Database and storage diagnostics
```

## Build

```bash
make rebuild-api       # Rebuild and restart API container
make rebuild-web       # Rebuild and restart web container
make rebuild-all       # Rebuild all containers
```
