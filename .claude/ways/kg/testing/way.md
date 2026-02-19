---
match: regex
pattern: \bpytest\b|\bjest\b|\btest\b.*run|coverage|conftest
commands: pytest|npm\s+test|tests/run
---
# Testing Way

## Running Tests (Dev Mode)

Tests run inside containers with live mounts. Platform must be running in dev mode.

```bash
./tests/run.sh                    # Full Python suite
./tests/run.sh tests/api/         # Just API tests
./tests/run.sh -k "concept"       # Pattern match
./tests/run.sh --cov              # With coverage report
./tests/run.sh -m "not slow"      # Skip slow tests
```

**CLI tests** (runs from host, starts own API server):
```bash
cd cli && npm test
```

**Rust tests** (graph-accel core, runs from host):
```bash
cd graph-accel && cargo test           # Core algorithms (fast, no PG)
cd graph-accel && cargo pgrx test pg17 # pgrx extension tests (needs PG)
```

## Test Structure

| Directory | What | Framework |
|-----------|------|-----------|
| `tests/api/` | API endpoint tests | pytest |
| `tests/unit/` | Pure unit tests | pytest |
| `tests/security/` | Auth/security tests | pytest |
| `tests/manual/` | LLM tests (not in CI) | pytest |
| `cli/tests/` | CLI + MCP tests | jest |
| `web/` | (infrastructure ready, no tests yet) | vitest |

## Pytest Markers

```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests
pytest -m api           # API tests
pytest -m security      # Security tests
pytest -m slow          # Slow tests
pytest -m smoke         # Smoke tests
```

## Key Fixtures (conftest.py)

| Fixture | Use |
|---------|-----|
| `api_client` | FastAPI TestClient |
| `mock_provider` | Mock AI provider |
| `auth_headers_user` | OAuth headers (user) |
| `auth_headers_admin` | OAuth headers (admin) |
| `sample_concepts` | Test concept data |

## Coverage

Coverage configured in `pytest.ini`:
- HTML report: `htmlcov/`
- Terminal: `--cov-report=term-missing`
- Target: `src/` directory

## Philosophy

- Functional coverage over LOC targets
- Test behavior at boundaries (routes, services)
- Error paths matter as much as happy paths
- Use LOC metrics for visibility ("what do untested lines do?")
