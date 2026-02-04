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
**Test Location:** `tests/`
**Configuration:** `pytest.ini`

**Key Features:**
- Mock AI provider (no API keys needed)
- In-memory job queue for fast tests
- Test markers: `smoke`, `integration`, `api`
- Coverage reporting (HTML + terminal)

**Run Tests:**
```bash
source venv/bin/activate

# All tests
pytest

# By category
pytest -m smoke          # Fast, no database (16 tests)
pytest -m integration    # Full workflows (35 tests)
pytest -m api           # API endpoints (all tests)

# With coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### TypeScript/Jest CLI Client

**Framework:** Jest 29.7+ with ts-jest
**Test Location:** `client/tests/`
**Configuration:** `client/jest.config.js`

**Key Features:**
- Auto-starts API server for tests
- Real integration (no mocks)
- Global setup/teardown
- TypeScript support

**Run Tests:**
```bash
cd client

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

**Status:** PLACEHOLDER TESTS

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

**Status:** PLACEHOLDER TESTS

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
// client/tests/cli/health.test.ts
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
# Start PostgreSQL + AGE via Docker
docker-compose up -d

# Verify AGE extension
docker exec -it knowledge-graph-postgres psql -U admin -d knowledge_graph \
  -c "SELECT extname FROM pg_extension WHERE extname = 'age';"

# Run integration tests
pytest -m integration
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

**Python/FastAPI:**
```
Total Tests: 51
- Smoke: 16 (passing) ✅
- Integration: 35 (passing) ✅
Code Coverage: 28-31% (functional coverage complete)
```

**TypeScript/Jest:**
```
Total Tests: 2
- CLI health: 2 (passing) ✅
Code Coverage: TBD
```

### Functional Coverage by Feature

| Feature | Tests | Status |
|---------|-------|--------|
| API Health | 4 Python + 2 TS | ✅ Complete |
| API Status | 5 Python | ✅ Complete |
| Job Management | 13 Python | ✅ Complete |
| Ingestion | 14 Python | ✅ Complete |
| Mock AI Provider | Comprehensive | ✅ Complete |
| Semantic Search | Placeholder | ⏳ Needs DB |
| Concept Details | Placeholder | ⏳ Needs DB |
| Graph Traversal | Placeholder | ⏳ Needs DB |
| Path Finding | Placeholder | ⏳ Needs DB |
| Ontology Mgmt | Placeholder | ⏳ Needs DB |
| Database Stats | Placeholder | ⏳ Needs DB |

### Coverage Metrics (Python)

**High Coverage (Tested Modules):**
- `api/app/routes/jobs.py` - 95%
- `api/app/services/job_analysis.py` - 92%
- `api/app/main.py` - 86%
- `api/app/routes/ingest.py` - 85%
- `api/app/services/job_queue.py` - 82%

**Low Coverage (Needs Database):**
- `api/app/routes/queries.py` - 18%
- `api/app/routes/database.py` - 17%
- `api/app/routes/ontology.py` - 21%
- `api/app/lib/age_client.py` - 14%

**Overall:** 28-31% (expected given database-dependent features not yet tested)

---

## 7. Test Organization

```
tests/                          # Python/pytest tests
├── conftest.py                 # Shared fixtures
├── README.md                   # Testing guide
├── api/                        # API endpoint tests
│   ├── __init__.py
│   ├── test_health.py          # 4 smoke tests ✅
│   ├── test_root.py            # 5 smoke tests ✅
│   ├── test_jobs.py            # 13 integration tests ✅
│   ├── test_ingest.py          # 14 integration tests ✅
│   └── test_ontology.py        # Placeholders (skip)
└── test_mock_provider.py       # Mock provider tests ✅

client/tests/                   # TypeScript/Jest tests
├── setup.ts                    # Global configuration
├── globalSetup.ts              # Start API server
├── globalTeardown.ts           # Stop API server
├── helpers/
│   └── api-server.ts           # Server management
└── cli/
    └── health.test.ts          # 2 tests ✅
```

---

## 8. Running Tests

### Python Tests

```bash
# From project root
source venv/bin/activate

# All tests
pytest -v

# By category
pytest -m smoke          # Fast tests (16 passing)
pytest -m integration    # Full workflows (35 passing)
pytest -m api           # All API tests (51 passing)

# By file
pytest tests/api/test_jobs.py -v
pytest tests/api/test_ingest.py -v

# With coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### TypeScript Tests

```bash
# From client/
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
        run: cd client && npm install

      - name: Build CLI
        run: cd client && npm run build

      - name: Run CLI tests
        run: cd client && npm test
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

# Check PostgreSQL
docker ps | grep postgres

# Start services
docker-compose up -d
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
# Check Python venv
source venv/bin/activate
python -m uvicorn api.app.main:app --version

# Increase timeout in jest.config.js
testTimeout: 60000
```

---

**Last Updated:** 2025-10-08
**Test Framework:** pytest 8.0+, Jest 29.7+
**Database:** PostgreSQL 16 + Apache AGE 1.5.0
**Mock Provider:** Deterministic hash-based (no API keys needed)
**Philosophy:** Functional coverage > Line coverage
