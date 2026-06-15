# Test Suite

The Kappa Graph test suite spans three runtimes — Python/pytest (API), TypeScript/Jest (CLI), and
Rust/cargo (graph-accel). This page covers how to run each, how tests are organized, and how to add
new ones.

---

## Philosophy

Tests validate functional correctness, not line coverage. A test that exercises a real workflow
against real services is more valuable than one that exercises every code path in isolation.

Practical consequences of this:

- **LLM extraction is non-deterministic.** Tests assert on structure and ranges, not exact outputs.
- **Integration over mocks.** The mock AI provider (`AI_PROVIDER=mock`) eliminates external API
  calls without mocking the API server, the database, or the job queue.
- **Coverage numbers are a guide.** Run the suite to get current numbers; historical snapshots in
  source files are not maintained.

---

## Prerequisites

Start the platform before running Python or CLI tests:

```bash
./operator.sh start
```

The `kg-api-dev` container must be running for Python tests. The TypeScript global setup starts its
own API server connection; verify the container is healthy first.

---

## Python / pytest (API tests)

**Location:** `tests/`  
**Framework:** pytest 8.0+ with pytest-asyncio, httpx, pytest-cov  
**Configuration:** `pytest.ini`

Tests run inside the `kg-api-dev` container. The `tests/run.sh` wrapper auto-detects whether
`kg-api-dev` or `kg-api` is the running container.

### Running tests

```bash
# Full suite
./tests/run.sh

# By directory
./tests/run.sh tests/api/
./tests/run.sh tests/unit/

# By marker
./tests/run.sh -m smoke          # fast sanity checks, no database
./tests/run.sh -m integration    # require database and job queue
./tests/run.sh -m api            # all API endpoint tests
./tests/run.sh -m unit           # unit tests
./tests/run.sh -m security       # auth and security tests

# By pattern
./tests/run.sh -k "concept"
./tests/run.sh -m "not slow"

# Direct docker exec equivalents
docker exec kg-api-dev pytest tests/ -x -q
docker exec kg-api-dev pytest tests/unit/ -x -q
docker exec kg-api-dev pytest tests/api/ -x -q

# Coverage (configured against api/app in pytest.ini)
./tests/run.sh --cov-report=html
# HTML report written to htmlcov/index.html inside the container
```

### Test markers

Markers are registered in `pytest.ini`. The `security` marker is registered dynamically in
`tests/conftest.py::pytest_configure`. Tests are auto-marked by location via
`pytest_collection_modifyitems`.

| Marker | Scope |
|---|---|
| `smoke` | Fast, no database, structural validation |
| `integration` | Full workflow, requires running PostgreSQL + AGE |
| `api` | API endpoint functional tests |
| `unit` | Isolated unit tests |
| `security` | Auth and permission tests |
| `slow` | Long-running; skip with `-m "not slow"` |

### Mock AI provider

`AI_PROVIDER=mock` is set in `pytest.ini`. No API keys are required to run the suite.

The mock provider (`api/app/lib/mock_ai_provider.py`) produces deterministic, hash-based
embeddings and concept extractions. Configure the extraction mode via `MOCK_MODE`:

| Mode | Concepts per chunk |
|---|---|
| `default` | 3–5 |
| `simple` | 1–2 |
| `complex` | 5–7 |
| `empty` | 0 |

### Test layout

```
tests/
├── conftest.py                 # Shared fixtures, marker registration
├── helpers.py                  # Shared test helpers
├── run.sh                      # Container test runner
├── api/                        # API endpoint tests (~25+ files)
│   ├── test_health.py, test_root.py, test_jobs.py, test_ingest.py
│   ├── test_auth.py, test_auth_utils.py, test_auth_dependencies.py
│   ├── test_oauth_utils.py, test_endpoint_security.py, test_job_permissions.py
│   ├── test_backup_streaming.py, test_backup_integrity.py, test_backup_verify.py
│   ├── test_polarity_axis.py, test_programs.py
│   ├── test_concepts.py, test_edges.py, test_batch.py
│   ├── test_catalog.py, test_database_counters.py, test_providers_routes.py
│   ├── test_ontology.py, test_ontology_routes.py
│   ├── test_epoch_reconciliation.py, test_kg_backup_v2_restore.py
│   └── auth sub-tests: test_anonymous_endpoints_auth.py,
│       test_artifact_owner_guard_auth.py, test_database_auth.py,
│       test_documents_sources_auth.py, test_ingestion_auth.py,
│       test_models_catalog_auth.py
├── unit/                       # Fast isolated tests
│   ├── test_cypher_guard.py, test_program_validation.py
│   ├── test_program_executor.py, test_program_operators.py
│   ├── test_id_remap.py, test_lane_control.py
│   ├── test_kg_backup_v2.py, test_kg_backup_v2_reader.py
│   ├── test_restore_modes.py, test_restore_worker_epoch.py
│   └── lib/, services/, workers/ subtrees
├── security/                   # Auth audit tests
│   ├── test_api_auth_audit.py, test_auth_patterns.py
├── manual/                     # Excluded from automated collection
└── test_*.py                   # Root-level lib/service unit tests
    (test_mock_provider.py, test_vocabulary_*.py, test_synonym_detector.py,
     test_pruning_strategies.py, test_clustering.py, test_query_facade.py,
     test_query_linter.py, test_source_chunker.py, test_aggressiveness_curve.py,
     test_category_classifier.py, test_datetime_utils.py, test_hash_utils.py)
```

### Functional coverage

| Feature | Test files | Status |
|---|---|---|
| API health / status | `test_health.py`, `test_root.py` | Implemented |
| Job management | `test_jobs.py`, `test_job_permissions.py` | Implemented |
| Ingestion | `test_ingest.py` | Implemented |
| Auth / OAuth | `test_auth*.py`, `test_oauth_utils.py`, `test_endpoint_security.py` | Implemented |
| Backup (streaming + integrity) | `test_backup_streaming.py`, `test_backup_integrity.py`, `test_backup_verify.py` | Implemented |
| Polarity axis | `test_polarity_axis.py` | Implemented |
| GraphProgram | `test_programs.py`, `test_program_*.py` | Implemented (API file is a placeholder) |
| Concepts / Edges | `test_concepts.py`, `test_edges.py` | Files exist; currently empty placeholders |
| Mock AI provider | `test_mock_provider.py` | Implemented |
| Vocabulary / synonyms | `test_vocabulary_*.py`, `test_synonym_detector.py` | Implemented |
| Pruning / clustering | `test_pruning_strategies.py`, `test_clustering.py` | Implemented |
| Query facade / linter | `test_query_facade.py`, `test_query_linter.py` | Implemented |
| Ontology routes | `test_ontology.py` (DB-skipped), `test_ontology_routes.py` (empty) | Partial |
| Semantic search | — | Pending — no `test_queries.py` yet |
| Database counters | `test_database_counters.py` | Pending — file is currently empty |

---

## TypeScript / Jest (CLI tests)

**Location:** `cli/tests/`  
**Framework:** Jest 29.x with ts-jest  
**Configuration:** `cli/jest.config.js`

The Jest global setup (`globalSetup.ts`) starts an API server connection before the suite runs
and tears it down after (`globalTeardown.ts`). Tests run against the live API — no mocks.

### Running tests

```bash
cd cli

# Build first (required)
npm run build

# Run all tests
npm test

# By pattern
npm test -- --testPathPattern=health

# With coverage
npm run test:coverage
open coverage/lcov-report/index.html

# Watch mode
npm run test:watch
```

### Test layout

```
cli/tests/
├── setup.ts               # Global configuration
├── globalSetup.ts         # Start API server connection
├── globalTeardown.ts      # Stop API server connection
├── helpers/               # Server management helpers
├── cli/
│   └── health.test.ts     # kg health (2 tests)
├── lib/
│   └── mcp-allowlist.test.ts   # MCP allowlist logic (~36 cases)
└── mcp/
    └── graph-operations.test.ts # Graph MCP operations (~8 cases)
```

---

## Rust / cargo (graph-accel)

**Location:** `graph-accel/`  
**Framework:** cargo test (core unit tests), pgrx-tests (PostgreSQL extension tests)

`graph-accel/core` contains pure Rust graph traversal logic with inline unit tests.
`graph-accel/ext` is the pgrx PostgreSQL extension; its tests run inside a managed PostgreSQL
instance via the pgrx test harness.

### Running tests

```bash
# Core unit tests (no database required)
cd graph-accel && cargo test

# pgrx extension tests (requires pgrx environment)
cd graph-accel && cargo pgrx test pg18
```

---

## Writing new tests

### Python

Determine the marker category first, then place the file:

- `smoke` — Fast, no database, validates structure. Lives in `tests/api/` or `tests/test_*.py`.
- `integration` — Full workflow, requires PostgreSQL + AGE. Lives in `tests/api/`.
- `unit` — Isolated library or service test. Lives in `tests/unit/` or `tests/test_*.py`.
- `security` — Auth and permission coverage. Lives in `tests/security/`.

Mark and document tests explicitly:

```python
@pytest.mark.smoke
@pytest.mark.api
def test_endpoint_returns_200(api_client):
    """
    Tests for: GET /health
    Purpose: API server is running and healthy
    """
    response = api_client.get("/health")
    assert response.status_code == 200
```

File naming: `test_<feature>_<scenario>.py` for Python, `<command>.test.ts` for TypeScript.

Write tests around user workflows, not implementation details:

```python
# Good — tests a user workflow
def test_submit_and_approve_job(api_client):
    response = api_client.post("/ingest/text", data={...})
    job_id = response.json()["job_id"]
    api_client.post(f"/jobs/{job_id}/approve")
    status = api_client.get(f"/jobs/{job_id}")
    assert status.json()["status"] in ["approved", "processing", "completed"]

# Avoid — testing internal state
def test_internal_queue_length():
    ...
```

---

## Troubleshooting

**Connection refused**

The API server or database is not running. Verify:

```bash
curl http://localhost:8000/health
./operator.sh status
./operator.sh start
```

**Mock provider not active**

Tests are hitting real AI APIs. Confirm `AI_PROVIDER=mock` is set in `pytest.ini` or `.env`:

```bash
grep AI_PROVIDER tests/pytest.ini
```

**TypeScript tests time out**

The API container is slow to respond. Check its health before running:

```bash
./operator.sh status
```

Increase the timeout in `cli/jest.config.js` (`testTimeout`) if the container is healthy but slow.
