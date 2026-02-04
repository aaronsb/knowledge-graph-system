---
match: regex
pattern: \bmake\b|makefile|run.*(test|suite|lint)|static.?analysis|code.?quality|docstring.?coverage|todo.?marker|scan.?for.*(antipattern|slop)|generate.?docs|build.?doc|reference.?doc|mkdocs|publish|release.?version|platform.?(health|status|start|stop|restart)|follow.?logs|diagnos|rebuild.?container
commands: ^make\s
scope: agent, subagent
---
# Make Targets Way

Use `make <target>` from the project root. The Makefile wraps common workflows.

## Testing (runs inside kg-api-dev container)

```bash
make test              # Full test suite
make test-unit         # Unit tests only
make test-api          # API route tests only
make test-verbose      # Full suite, verbose
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

## Prefer make over raw commands

- `make test` over `./tests/run.sh` — consistent entry point
- `make lint` over running linters individually
- `make start/stop/restart` over `./operator.sh start/stop/restart`
- Run `make help` if unsure what's available
