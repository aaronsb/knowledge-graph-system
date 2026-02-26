# Contributing

Thanks for your interest in contributing to Knowledge Graph System!

## Getting Started

1. Fork and clone the repository
2. Run `./operator.sh init` for guided setup
3. Run `./operator.sh start` to start the platform
4. Make your changes on a feature branch

## Development

The platform is fully containerized. See the [README](README.md) for quick start instructions.

```bash
./operator.sh start          # Start platform
./operator.sh logs api -f    # Follow API logs
./operator.sh status         # Check health
```

### Testing

```bash
# API (Python) — runs inside container
docker exec kg-api-dev pytest tests/ -x -q

# CLI (TypeScript)
cd cli && npm test

# graph-accel (Rust)
cd graph-accel && cargo test
```

### Architecture Decisions

Significant design choices are documented as [Architecture Decision Records](docs/architecture/ARCHITECTURE_DECISIONS.md). If your change introduces a new pattern or approach, consider proposing an ADR.

## Submitting Changes

1. Create a branch from `main`
2. Make focused, well-tested changes
3. Write clear commit messages
4. Open a pull request with a summary of changes and test plan
5. Address any review feedback

## Reporting Bugs

Use the [bug report template](https://github.com/aaronsb/knowledge-graph-system/issues/new?template=bug_report.md) and include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details and relevant logs

## Code Style

- Python: follow existing patterns in `api/app/`
- TypeScript: `npm run lint` in `cli/`
- Rust: `cargo fmt` and `cargo clippy` in `graph-accel/`
- All public functions should have docstrings

## License

By contributing, you agree that your contributions will be licensed under the project's [Apache License 2.0](LICENSE).
