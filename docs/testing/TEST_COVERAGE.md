# Test Coverage Areas

Functional test coverage map for the knowledge graph system. This document outlines what needs testing, expected behaviors, and acceptance criteria.

---

## Philosophy

**We test for functional correctness, not code coverage.**

- ✅ Does the workflow work end-to-end?
- ✅ Does data integrity remain intact?
- ✅ Are edge cases handled gracefully?
- ❌ NOT: Did we execute every line of code?

**Non-deterministic acceptance:**
- LLM extraction varies between runs
- Test ranges, not exact values
- Validate structure and semantics, not specific outputs

**Integration over mocking:**
- Tests run against real API server (no mocks)
- Database tests use real PostgreSQL + Apache AGE
- CLI tests execute actual commands
- Coverage is a guide, not a chase metric

---

## Current Testing Stack

### Python/FastAPI Backend

**Framework:** pytest 8.0+ with pytest-asyncio, httpx, pytest-cov
**Test Location:** `tests/` (with `tests/api/`, `tests/unit/`, `tests/security/`, `tests/manual/`).
Root-level `tests/test_*.py` files cover library/services unit tests (chunker, vocabulary,
synonym detector, query facade, pruning, clustering, etc.).
**Configuration:** `pytest.ini`

**Key Features:**
- Mock AI provider (no API keys needed) — `AI_PROVIDER=mock` set in `pytest.ini`
- Test markers: `unit`, `smoke`, `integration`, `api`, `slow` (registered in `pytest.ini`).
  `security` is registered dynamically in `tests/conftest.py::pytest_configure`.
- Auto-marking based on test location (see `tests/conftest.py::pytest_collection_modifyitems`)
- Coverage reporting (HTML + terminal) against `api/app`
- `tests/manual/` ignored during automated collection (`pytest_ignore_collect` + `norecursedirs`)

**Run Tests (canonical — inside container):**
```bash
# Platform must be running: ./operator.sh start

# Convenience wrapper (auto-detects kg-api-dev / kg-api container)
./tests/run.sh                           # Full suite
./tests/run.sh tests/api/                # Just API tests
./tests/run.sh tests/unit/               # Just unit tests
./tests/run.sh -k "concept"              # Pattern match
./tests/run.sh -m "not slow"             # Skip slow tests

# Equivalent direct invocations (per CLAUDE.md)
docker exec kg-api-dev pytest tests/ -x -q          # full suite
docker exec kg-api-dev pytest tests/unit/ -x -q     # unit tests only
docker exec kg-api-dev pytest tests/api/ -x -q      # route tests only

# By category
./tests/run.sh -m smoke           # Quick sanity checks
./tests/run.sh -m integration     # Integration (require DB)
./tests/run.sh -m api             # All API endpoint tests
./tests/run.sh -m unit            # Unit tests
./tests/run.sh -m security        # Auth/security tests

# Coverage (configured in pytest.ini: --cov=api/app)
./tests/run.sh --cov-report=html
```

### TypeScript/Jest CLI Client

**Framework:** Jest 29.x with ts-jest
**Test Location:** `cli/tests/` (sub-dirs: `cli/`, `lib/`, `mcp/`, plus `helpers/`)
**Configuration:** `cli/jest.config.js`
**Test roots:** `<rootDir>/src` and `<rootDir>/tests`

**Key Features:**
- Auto-starts API server for tests (`globalSetup.ts`/`globalTeardown.ts`)
- Real integration (no mocks)
- Global setup/teardown
- TypeScript support (`ts-jest` preset)
- `testTimeout: 30000`

**Run Tests:**
```bash
cd cli

# Build first (required)
npm run build

# Run tests
npm test

# With coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

---

## 1. Smoke Tests (Fast Sanity Checks)

### ✅ 1.1 Infrastructure Connectivity

**Status:** IMPLEMENTED (16 tests passing)

**Test:** API Health Check
```python
# tests/api/test_health.py
@pytest.mark.smoke
@pytest.mark.api
def test_health_endpoint_returns_200(api_client):
    """API server is running and healthy"""
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

**Test:** API Status Endpoint
```python
# tests/api/test_root.py
@pytest.mark.smoke
@pytest.mark.api
def test_root_endpoint_status_healthy(api_client):
    """Root endpoint returns service info and health"""
    response = api_client.get("/")
    data = response.json()
    assert data["status"] == "healthy"
    assert "queue" in data  # Job queue operational
```

**Test:** Mock AI Provider
```python
# tests/test_mock_provider.py (comprehensive test suite)
def test_mock_provider_deterministic():
    """Mock provider gives same results for same input"""
    provider = MockAIProvider(mode="default")

    text = "Test concept extraction"
    result1 = provider.extract_concepts(text, "test.txt")
    result2 = provider.extract_concepts(text, "test.txt")

    # Same input = same output (deterministic)
    assert result1 == result2
```

**Test:** Job Queue Operations
```python
# tests/api/test_jobs.py
@pytest.mark.smoke
@pytest.mark.api
def test_jobs_list_empty(api_client):
    """Job listing works (in-memory queue)"""
    response = api_client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Expected Results:**
- ✅ All 16 smoke tests pass in <1s
- ✅ No database or LLM API keys required
- ✅ Tests validate API structure and mock systems

---

## 2. Functional Tests (Core Workflows)

### ✅ 2.1 Ingestion Pipeline

**Status:** IMPLEMENTED (14 tests passing)

**Test:** Text Ingestion Workflow
```python
# tests/api/test_ingest.py
@pytest.mark.api
@pytest.mark.smoke
def test_ingest_text_basic(api_client):
    """Submit text → job created → queued for processing"""
    data = {
        "text": "This is a test document.",
        "ontology": "test-ontology"
    }

    response = api_client.post("/ingest/text", data=data)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result
    assert result["status"].startswith("pending")
```

**Test:** File Upload Ingestion
```python
@pytest.mark.api
@pytest.mark.smoke
def test_ingest_file_upload(api_client):
    """Upload file → job created → content hashed"""
    file_content = b"Test file content"
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
    data = {"ontology": "test-upload"}

    response = api_client.post("/ingest", files=files, data=data)

    assert response.status_code == 200
    assert "job_id" in response.json()
    assert "content_hash" in response.json()
```

**Test:** Duplicate Detection
```python
@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_duplicate_detection(api_client):
    """Same content → duplicate detected"""
    data = {"text": "Unique test content", "ontology": "test-dup"}

    # First submission
    response1 = api_client.post("/ingest/text", data=data)
    job_id1 = response1.json()["job_id"]

    # Second submission (same content + ontology)
    response2 = api_client.post("/ingest/text", data=data)
    result2 = response2.json()

    # Should detect duplicate or return same job
    assert "job_id" in result2 or "duplicate" in result2
```

**Test:** Auto-Approve Workflow (ADR-014)
```python
@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_auto_approve(api_client):
    """auto_approve=true skips manual approval step"""
    data = {
        "text": "Auto-approve test",
        "ontology": "test-auto",
        "auto_approve": "true"
    }

    response = api_client.post("/ingest/text", data=data)
    result = response.json()

    assert "auto" in result["status"].lower()
```

**Expected Results:**
- ✅ 14 ingestion tests pass
- ✅ File upload and text ingestion both work
- ✅ Duplicate detection operational
- ✅ ADR-014 approval workflow validated

---

### ✅ 2.2 Job Management

**Status:** IMPLEMENTED (13 tests passing)

**Test:** Job Lifecycle Workflow
```python
# tests/api/test_jobs.py
@pytest.mark.api
@pytest.mark.integration
def test_job_lifecycle_workflow(api_client):
    """
    Full job lifecycle:
    submit → pending → awaiting_approval → approve → processing → completed
    """
    # 1. Submit job
    response = api_client.post("/ingest/text", data={
        "text": "Lifecycle test",
        "ontology": "test-lifecycle"
    })
    job_id = response.json()["job_id"]

    # 2. Check initial status
    status_response = api_client.get(f"/jobs/{job_id}")
    initial_status = status_response.json()["status"]
    assert initial_status in ["pending", "awaiting_approval"]

    # 3. Wait for awaiting_approval (polling simulation)
    # ... wait logic ...

    # 4. Approve job
    approve_response = api_client.post(f"/jobs/{job_id}/approve")
    assert approve_response.status_code == 200

    # 5. Verify transitions to approved/processing
    final_response = api_client.get(f"/jobs/{job_id}")
    final_status = final_response.json()["status"]
    assert final_status in ["approved", "processing", "completed"]
```

**Test:** Job Filtering
```python
@pytest.mark.api
@pytest.mark.smoke
def test_jobs_list_with_status_filter(api_client):
    """Filter jobs by status"""
    response = api_client.get("/jobs?status=completed")

    assert response.status_code == 200
    jobs = response.json()
    # All returned jobs should have status=completed
    assert all(job["status"] == "completed" for job in jobs)
```

**Test:** Job Cancellation
```python
@pytest.mark.api
@pytest.mark.integration
def test_cancel_job(api_client):
    """Cancel job before processing starts"""
    # Create job
    response = api_client.post("/ingest/text", data={...})
    job_id = response.json()["job_id"]

    # Cancel
    cancel_response = api_client.delete(f"/jobs/{job_id}")

    # Should succeed or report already processing
    assert cancel_response.status_code in [200, 409]
```

**Expected Results:**
- ✅ 13 job management tests pass
- ✅ Full lifecycle tested (pending → approval → processing)
- ✅ Job filtering and cancellation work
- ✅ ADR-014 approval workflow validated

---

### ⏳ 2.3 Graph Queries (Pending - Requires Database)

**Status:** PLACEHOLDER TESTS — no `tests/api/test_queries.py` exists yet.
Related current files: `tests/api/test_concepts.py`, `tests/api/test_edges.py`.

**Future Test:** Semantic Search
```python
# tests/api/test_queries.py (to be implemented)
@pytest.mark.integration
@pytest.mark.skip("Requires PostgreSQL + Apache AGE")
def test_semantic_search(api_client, age_client):
    """Vector search finds similar concepts"""
    # Setup: Ingest test documents
    # ...

    # Search
    response = api_client.post("/query/search", json={
        "query": "linear thinking patterns",
        "limit": 10,
        "min_similarity": 0.7
    })

    assert response.status_code == 200
    results = response.json()
    assert "results" in results
    assert len(results["results"]) > 0
```

**Future Test:** Concept Details
```python
@pytest.mark.integration
@pytest.mark.skip("Requires database with test data")
def test_concept_details(api_client):
    """Get concept with instances and relationships"""
    response = api_client.get("/query/concept/test-concept-id")

    assert response.status_code == 200
    data = response.json()
    assert "label" in data
    assert "instances" in data
    assert "relationships" in data
```

**Future Test:** Path Finding
```python
@pytest.mark.integration
@pytest.mark.skip("Requires graph data")
def test_find_connection(api_client):
    """Find shortest path between concepts"""
    response = api_client.post("/query/connect", json={
        "from_id": "concept-a",
        "to_id": "concept-b",
        "max_hops": 5
    })

    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
```

**Expected Results (When Implemented):**
- Query endpoints work with Apache AGE
- Vector search using PostgreSQL extensions
- Graph traversal via AGE Cypher compatibility

---

### ⏳ 2.4 Database Operations (Pending)

**Status:** PLACEHOLDER TESTS — no `tests/api/test_database.py` exists.
`tests/api/test_database_counters.py` exists but is currently empty (no test functions).

**Future Test:** Database Statistics
```python
# tests/api/test_database.py (to be implemented)
@pytest.mark.integration
@pytest.mark.skip("Requires PostgreSQL + AGE")
def test_database_stats(api_client):
    """Get node/relationship counts"""
    response = api_client.get("/database/stats")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "relationships" in data
    assert data["nodes"]["concepts"] >= 0
```

**Future Test:** Database Health Check
```python
@pytest.mark.integration
@pytest.mark.skip("Requires database connection")
def test_database_health(api_client):
    """Check PostgreSQL + AGE extension availability"""
    response = api_client.get("/database/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["checks"]["age_extension"]["installed"] is True
```

---

### ⏳ 2.5 Ontology Management (Pending)

**Status:** PLACEHOLDER TESTS

**Future Test:** List Ontologies
```python
# tests/api/test_ontology.py (to be implemented)
@pytest.mark.integration
@pytest.mark.skip("Requires database with ontologies")
def test_ontology_list(api_client):
    """List all ontologies with concept counts"""
    response = api_client.get("/ontology/")

    assert response.status_code == 200
    data = response.json()
    assert "ontologies" in data
    assert "count" in data
```

---

## 3. CLI Functional Tests

### ✅ 3.1 Health Command

**Status:** IMPLEMENTED (2 tests passing)

**Test:** CLI Health Check
```typescript
// cli/tests/cli/health.test.ts
describe('kg health', () => {
  it('should return healthy status', async () => {
    const { stdout } = await execAsync(`${KG_CLI} health`);
    expect(stdout).toContain('healthy');
  });

  it('should exit with code 0 on success', async () => {
    try {
      await execAsync(`${KG_CLI} health`);
      expect(true).toBe(true);  // No error = success
    } catch (error: any) {
      fail(`Command failed: ${error.message}`);
    }
  });
});
```

**Expected Results:**
- ✅ 2 CLI tests pass
- ✅ API server auto-starts for tests
- ✅ Real integration testing (no mocks)

---

### ⏳ 3.2 Other CLI Commands (Pending)

**Future Tests:**
- [ ] `kg jobs list` - List jobs with filtering
- [ ] `kg jobs status <id>` - Check job status
- [ ] `kg jobs approve <id>` - Approve job
- [ ] `kg ingest <file>` - Upload file
- [ ] `kg ingest text` - Submit text
- [ ] `kg search <query>` - Semantic search
- [ ] `kg concept <id>` - Concept details
- [ ] `kg connect <from> <to>` - Find paths
- [ ] `kg ontology list` - List ontologies
- [ ] `kg database stats` - Database info

---

## 4. Mock AI Provider

### ✅ 4.1 No API Keys Required

**Location:** `api/app/lib/mock_ai_provider.py`

**Features:**
- **Deterministic responses** - Hash-based embeddings
- **Configurable modes** - default, simple, complex, empty
- **1536-dim vectors** - Compatible with OpenAI embeddings
- **No costs** - Perfect for CI/CD

**Configuration:**
```bash
# In .env or pytest.ini
AI_PROVIDER=mock
MOCK_MODE=default
```

**Modes:**
- `default` - Standard concept extraction (3-5 concepts per chunk)
- `simple` - Minimal concepts (1-2 per chunk)
- `complex` - Rich concept graph (5-7 per chunk)
- `empty` - No concepts extracted

**Test:**
```python
# tests/test_mock_provider.py
def test_mock_provider_modes():
    """Different modes produce different concept counts"""
    simple = MockAIProvider(mode="simple")
    complex_provider = MockAIProvider(mode="complex")

    simple_result = simple.extract_concepts("Test text", "test.txt")
    complex_result = complex_provider.extract_concepts("Test text", "test.txt")

    # Complex mode extracts more concepts
    assert len(complex_result["concepts"]) >= len(simple_result["concepts"])
```

---

## 5. Apache AGE Migration Notes

### Database Changes

**Previous:** Neo4j Community Edition 4.x
**Current:** PostgreSQL 16 + Apache AGE 1.5.0

**Why Apache AGE:**
- Open-source graph database
- PostgreSQL compatibility
- Better licensing for production
- SQL + openCypher hybrid queries

**Migration Impact on Tests:**
- ✅ Mock provider unchanged (no database dependency)
- ✅ Smoke tests unchanged (API-level validation)
- ⏳ Integration tests need AGE database running
- ⏳ Query tests pending AGE Cypher compatibility verification

**openCypher Compatibility:**
- AGE implements the openCypher standard (open-source graph query language)
- Some Neo4j proprietary Cypher extensions not available
- Vector search via PostgreSQL extensions (pgvector)
- Relationship syntax slightly different

**Test Database Setup:**
```bash
# Start the platform (PostgreSQL + AGE + API + Web + Garage)
./operator.sh start

# Verify AGE extension
docker exec -it knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -c "SELECT extname FROM pg_extension WHERE extname = 'age';"

# Run integration tests inside the API container
./tests/run.sh -m integration
```

**Graph Schema (Unchanged from Neo4j):**
```cypher
-- Nodes
CREATE (:Concept {concept_id, label, embedding, search_terms})
CREATE (:Source {source_id, document, paragraph, full_text})
CREATE (:Instance {instance_id, quote})

-- Relationships
(:Concept)-[:APPEARS]->(:Source)
(:Concept)-[:EVIDENCED_BY]->(:Instance)
(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS]->(:Concept)
```

---

## 6. Test Coverage Summary

### Current Status

**Python/pytest:** The suite has grown substantially since the original 51-test snapshot.
A recent collection count (excluding `tests/manual/`) puts total test functions at well over
a thousand, spread across:

- `tests/api/` — ~22 files covering health, root, jobs, ingest, ontology, ontology_routes,
  concepts, edges, batch, programs, providers_routes, polarity_axis, backup (streaming +
  integrity), database_counters, auth, auth_utils, auth_dependencies, oauth_utils,
  endpoint_security, job_permissions
- `tests/unit/` — `test_cypher_guard.py`, `test_program_validation.py`,
  `test_program_executor.py`, `test_program_operators.py`, plus subtrees `lib/`,
  `services/`, `workers/`
- `tests/security/` — `test_api_auth_audit.py`, `test_auth_patterns.py`
- `tests/test_*.py` (root) — `test_mock_provider.py`, `test_aggressiveness_curve.py`,
  `test_category_classifier.py`, `test_clustering.py`, `test_datetime_utils.py`,
  `test_hash_utils.py`, `test_pruning_strategies.py`, `test_query_facade.py`,
  `test_query_linter.py`, `test_source_chunker.py`, `test_synonym_detector.py`,
  `test_vocabulary_manager_integration.py`, `test_vocabulary_scoring.py`

Code coverage: configured against `api/app` in `pytest.ini`; current numbers vary by
environment (database fixtures impact integration coverage).

**TypeScript/Jest (`cli/tests/`):**
- `cli/health.test.ts` (2 tests)
- `lib/mcp-allowlist.test.ts` (~36 cases)
- `mcp/graph-operations.test.ts` (~8 cases)

### Functional Coverage by Feature

| Feature | Tests | Status |
|---------|-------|--------|
| API Health | `tests/api/test_health.py` (+ CLI `health.test.ts`) | Implemented |
| API Status | `tests/api/test_root.py` | Implemented |
| Job Management | `tests/api/test_jobs.py`, `test_job_permissions.py` | Implemented |
| Ingestion | `tests/api/test_ingest.py` | Implemented |
| Auth / OAuth | `tests/api/test_auth*.py`, `test_oauth_utils.py`, `test_endpoint_security.py` | Implemented |
| Backup | `tests/api/test_backup_streaming.py`, `test_backup_integrity.py` | Implemented |
| Polarity axis | `tests/api/test_polarity_axis.py` | Implemented |
| Programs (ADR-089) | `tests/api/test_programs.py` + `tests/unit/test_program_*.py` | Implemented (api tests file currently empty) |
| Concepts / Edges (ADR-089) | `tests/api/test_concepts.py`, `test_edges.py` | Files exist, currently empty placeholders |
| Mock AI Provider | `tests/test_mock_provider.py` | Implemented |
| Vocabulary | `tests/test_vocabulary_*.py`, `test_synonym_detector.py` | Implemented |
| Pruning / Clustering | `tests/test_pruning_strategies.py`, `test_clustering.py` | Implemented |
| Query facade / linter | `tests/test_query_facade.py`, `test_query_linter.py` | Implemented |
| Ontology routes | `tests/api/test_ontology.py` (DB-skipped), `test_ontology_routes.py` (empty) | Partial |
| Semantic Search | — | Pending (no `test_queries.py` yet) |
| Database Stats | — | Pending (`test_database_counters.py` empty) |

### Coverage Metrics (Python)

Coverage numbers below are historical and have not been re-measured. Run the suite
in-container to get current metrics:

```bash
./tests/run.sh --cov=api/app --cov-report=term-missing
```

Older snapshot (pre-OAuth / pre-ADR-089 expansion):
- High coverage: `routes/jobs.py` (~95%), `services/job_analysis.py` (~92%),
  `main.py` (~86%), `routes/ingest.py` (~85%), `services/job_queue.py` (~82%)
- Low coverage (DB-dependent): `routes/queries.py`, `routes/database.py`,
  `routes/ontology.py`, `lib/age_client.py`

---

## 7. Test Organization

```
tests/                          # Python/pytest tests
├── conftest.py                 # Shared fixtures + marker registration
├── helpers.py                  # Shared test helpers
├── run.sh                      # Container test runner (kg-api-dev/kg-api)
├── README.md                   # Testing guide
├── api/                        # API endpoint tests (~22 files)
│   ├── test_health.py, test_root.py, test_jobs.py, test_ingest.py
│   ├── test_ontology.py, test_ontology_routes.py
│   ├── test_auth.py, test_auth_utils.py, test_auth_dependencies.py
│   ├── test_oauth_utils.py, test_endpoint_security.py, test_job_permissions.py
│   ├── test_backup_streaming.py, test_backup_integrity.py
│   ├── test_polarity_axis.py, test_programs.py, test_concepts.py,
│   │   test_edges.py, test_batch.py, test_database_counters.py,
│   │   test_providers_routes.py
├── unit/                       # Unit tests (fast, isolated)
│   ├── test_cypher_guard.py, test_program_*.py
│   └── lib/, services/, workers/
├── security/                   # Auth/security tests
│   ├── test_api_auth_audit.py, test_auth_patterns.py
├── manual/                     # Excluded from automated collection
└── test_*.py                   # Root-level lib/service unit tests
    (mock_provider, vocabulary_*, synonym_detector, pruning_strategies,
     clustering, query_facade, query_linter, source_chunker,
     aggressiveness_curve, category_classifier, datetime_utils, hash_utils)

cli/tests/                      # TypeScript/Jest tests
├── setup.ts                    # Global configuration
├── globalSetup.ts              # Start API server
├── globalTeardown.ts           # Stop API server
├── helpers/                    # Server management helpers
├── cli/
│   └── health.test.ts
├── lib/
│   └── mcp-allowlist.test.ts
└── mcp/
    └── graph-operations.test.ts
```

---

## 8. Running Tests

### Python Tests (run inside `kg-api-dev` container)

```bash
# Platform must be running in dev mode first
./operator.sh start

# Via wrapper (auto-detects kg-api-dev / kg-api)
./tests/run.sh                           # All tests
./tests/run.sh tests/api/                # API tests only
./tests/run.sh tests/api/test_jobs.py    # Single file
./tests/run.sh -k "concept"              # Pattern match
./tests/run.sh -m "not slow"             # Skip slow tests
./tests/run.sh -m smoke                  # Only smoke tests

# Equivalent direct docker exec (per CLAUDE.md)
docker exec kg-api-dev pytest tests/ -x -q
docker exec kg-api-dev pytest tests/unit/ -x -q
docker exec kg-api-dev pytest tests/api/ -x -q

# Coverage (configured against api/app in pytest.ini)
./tests/run.sh --cov-report=html
# HTML report: htmlcov/index.html inside the container
```

### TypeScript Tests

```bash
# From cli/
npm run build            # Required before tests

# All tests
npm test

# Specific pattern
npm test -- --testPathPattern=health

# With coverage
npm run test:coverage
open coverage/lcov-report/index.html

# Watch mode (dev)
npm run test:watch
```

---

## 9. CI/CD Integration (Future)

### GitHub Actions (Suggested)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test-python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: apache/age:PG16
        env:
          POSTGRES_DB: knowledge_graph_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run smoke tests
        run: pytest -m smoke -v

      - name: Run integration tests
        run: pytest -m integration -v
        env:
          AI_PROVIDER: mock
          POSTGRES_HOST: localhost
          POSTGRES_PORT: 5432

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  test-typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Install Node dependencies
        run: cd cli && npm install

      - name: Build CLI
        run: cd cli && npm run build

      - name: Run CLI tests
        run: cd cli && npm test
        env:
          AI_PROVIDER: mock
```

---

## 10. Future Test Areas

**Not yet covered:**

### Database Integration Tests
- [ ] Full ingestion workflow with Apache AGE
- [ ] Vector search accuracy (pgvector)
- [ ] Graph traversal performance
- [ ] Concept matching via embeddings
- [ ] Ontology isolation verification

### CLI Coverage
- [ ] All CLI commands (jobs, search, concept, etc.)
- [ ] Error handling and user feedback
- [ ] Argument parsing edge cases
- [ ] Output formatting validation

### Performance & Scale
- [ ] Large document ingestion (1000+ paragraphs)
- [ ] Concurrent job processing
- [ ] Query latency benchmarks
- [ ] Database connection pooling

### Advanced Features
- [ ] MCP server integration (Phase 2)
- [ ] Multi-tenant job isolation
- [ ] Backup/restore workflows
- [ ] Admin operations testing

---

## 11. Success Criteria

**Test suite is successful when:**
- ✅ All smoke tests pass consistently (<1s runtime)
- ✅ Integration tests validate key workflows
- ✅ No LLM API keys required for testing
- ✅ CI passes reliably (< 5% flaky failures)
- ✅ New features include functional tests
- ✅ Test execution time < 5 minutes (smoke + integration)

**Individual test is successful when:**
- ✅ Functional correctness demonstrated
- ✅ Real integration (not mocked services)
- ✅ Edge cases handled gracefully
- ✅ Error messages are actionable

---

## 12. Test Development Guidelines

### Adding New Tests

1. **Determine category:**
   - `smoke` → Fast, no DB, structural validation
   - `integration` → Full workflow, requires services
   - `api` → API endpoint functional tests

2. **Mark appropriately:**
   ```python
   @pytest.mark.smoke
   @pytest.mark.api
   def test_endpoint(api_client):
       """Clear description of what we're testing"""
   ```

3. **Follow naming:**
   - Python: `test_<feature>_<scenario>.py`
   - TypeScript: `<command>.test.ts`

4. **Document intent:**
   ```python
   """
   Tests for: kg health
   Endpoint: GET /health
   Purpose: Validate API health check
   """
   ```

### Writing Functional Tests

Focus on **user workflows**, not code paths:

```python
# ✅ Good - tests user workflow
def test_submit_and_approve_job(api_client):
    """User submits job, waits for analysis, approves, monitors completion"""
    # 1. Submit
    response = api_client.post("/ingest/text", data={...})
    job_id = response.json()["job_id"]

    # 2. Wait for analysis
    # ... polling logic ...

    # 3. Approve
    api_client.post(f"/jobs/{job_id}/approve")

    # 4. Verify
    status = api_client.get(f"/jobs/{job_id}")
    assert status.json()["status"] in ["approved", "processing", "completed"]

# ❌ Avoid - testing implementation
def test_internal_queue_state():
    """Check internal data structures"""
    # Too coupled to implementation
```

---

## Troubleshooting

### Tests Fail with "Connection Refused"

**Problem:** API server or database not running

**Solution:**
```bash
# Check API
curl http://localhost:8000/health

# Check container status
./operator.sh status

# Start the platform
./operator.sh start
```

### Mock Provider Not Working

**Problem:** Tests calling real APIs

**Solution:**
```bash
# Verify env
grep AI_PROVIDER .env
# Should be: AI_PROVIDER=mock

# Or check pytest.ini:
# env = AI_PROVIDER=mock
```

### TypeScript Tests Timeout

**Problem:** API server slow to start

**Solution:**
```bash
# Check the API container is up and healthy
./operator.sh status
docker exec kg-api-dev python -m uvicorn api.app.main:app --version

# Increase timeout in cli/jest.config.js
# testTimeout: 60000
```

---

**Last Updated:** 2026-05-25 (doc/code alignment review)
**Test Framework:** pytest 8.0+, Jest 29.x
**Database:** PostgreSQL 16 + Apache AGE
**Mock Provider:** Deterministic hash-based (no API keys needed)
**Philosophy:** Functional coverage > Line coverage
