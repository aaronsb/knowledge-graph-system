# Knowledge Graph System - Test Suite

Comprehensive test suite for functional correctness without requiring live API keys.

## Quick Start (Recommended)

Tests run inside the API container (dev mode required):

```bash
./tests/run.sh                           # Full suite
./tests/run.sh tests/api/                # Just API tests
./tests/run.sh tests/api/test_health.py  # Single file
./tests/run.sh -k "concept"              # Pattern match
./tests/run.sh -m "not slow"             # Skip slow tests
```

**Prerequisites:**
- Platform running in dev mode: `./operator.sh start`
- Tests mounted in container (automatic with dev overlay)

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── run.sh                   # Container test runner
├── api/                     # API endpoint tests
│   ├── test_concepts.py     # ADR-089 concept CRUD
│   ├── test_edges.py        # ADR-089 edge CRUD
│   └── ...
├── unit/                    # Unit tests (fast, isolated)
├── security/                # Auth/security tests
├── manual/                  # LLM tests (not in CI)
└── README.md               # This file
```

## Running Tests

### In-Container (Recommended)

```bash
./tests/run.sh                    # All tests
./tests/run.sh tests/api/         # API tests only
./tests/run.sh -v --tb=short      # Verbose with short tracebacks
```

### Direct pytest (Local Development)

```bash
pytest
```

### By Category

```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests (requires database)
pytest -m integration

# API tests
pytest -m api

# Smoke tests (quick sanity checks)
pytest -m smoke
```

### With Coverage

```bash
# Terminal coverage report
pytest --cov=src --cov-report=term-missing

# HTML coverage report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Specific Test Files

```bash
# Run single file
pytest tests/test_mock_provider.py

# Run specific test
pytest tests/test_mock_provider.py::test_deterministic_embeddings

# Run tests matching pattern
pytest -k "embedding"
```

### Verbose Output

```bash
# Detailed output
pytest -v

# Very detailed with print statements
pytest -vv -s
```

## Test Markers

Tests are automatically marked based on location and name:

- **@pytest.mark.unit** - Unit tests (fast, isolated, no external dependencies)
- **@pytest.mark.integration** - Integration tests (require database)
- **@pytest.mark.api** - API endpoint tests
- **@pytest.mark.slow** - Slow running tests (skip for quick runs)
- **@pytest.mark.smoke** - Smoke tests (quick sanity checks)

### Using Markers

```python
import pytest

@pytest.mark.unit
def test_concept_creation():
    """Unit test for concept creation"""
    pass

@pytest.mark.integration
def test_database_query():
    """Integration test requiring database"""
    pass

@pytest.mark.slow
def test_full_ingestion():
    """Slow test for complete ingestion pipeline"""
    pass
```

## Fixtures

Common fixtures available in all tests (from `conftest.py`):

### AI Provider Fixtures

```python
def test_extraction(mock_provider):
    """Use default mock provider"""
    result = mock_provider.extract_concepts("text", "")
    assert result is not None

def test_simple_extraction(simple_mock_provider):
    """Use simple provider (1 concept)"""
    result = simple_mock_provider.extract_concepts("text", "")
    assert len(result["result"]["concepts"]) <= 1
```

### API Client Fixtures

```python
def test_health_endpoint(api_client):
    """Test using synchronous client"""
    response = api_client.get("/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_async_endpoint(async_api_client):
    """Test using async client"""
    response = await async_api_client.get("/health")
    assert response.status_code == 200
```

### Authentication Fixtures

Most API endpoints require authentication. Use `mock_oauth_validation` to bypass database OAuth lookup:

```python
@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation):
    """Auto-use mock OAuth validation for all tests in this module."""
    pass

class TestMyEndpoint:
    def test_requires_auth(self, api_client):
        """No auth returns 401."""
        response = api_client.get("/my-endpoint")
        assert response.status_code == 401

    def test_with_auth(self, api_client, auth_headers_user):
        """With auth succeeds."""
        response = api_client.get("/my-endpoint", headers=auth_headers_user)
        assert response.status_code == 200
```

**Available auth fixtures:**
| Fixture | Description |
|---------|-------------|
| `mock_oauth_validation` | Patches OAuth validation (add to module) |
| `auth_headers_user` | Headers dict with user-level token |
| `auth_headers_admin` | Headers dict with admin-level token |
| `expired_oauth_token` | Token that will fail validation |

The mock validation returns all scopes (`kg:read`, `kg:write`, `kg:edit`, `kg:import`) for test tokens.

### Test Data Fixtures

```python
def test_with_sample_data(sample_text, sample_concepts):
    """Use pre-defined test data"""
    assert len(sample_text) > 0
    assert len(sample_concepts) == 2
```

### Temporary Files

```python
def test_file_upload(temp_file):
    """Create temporary test files"""
    path = temp_file("test.txt", "content")
    assert os.path.exists(path)
```

## Mock AI Provider

All tests use the MockAIProvider by default (configured in `pytest.ini`):

```python
# Environment automatically set for tests
AI_PROVIDER=mock
MOCK_MODE=default
```

### Mock Modes

- **default**: Standard concept generation (3 concepts per chunk)
- **simple**: Minimal concepts (1 concept per chunk)
- **complex**: Rich concept graph (5 concepts per chunk)
- **empty**: No concepts (for edge case testing)

### Override in Tests

```python
import os

def test_with_openai():
    """Test with real OpenAI (requires API key)"""
    os.environ["AI_PROVIDER"] = "openai"
    # ... test code
```

## Configuration

### pytest.ini

Main test configuration:

- Test discovery patterns
- Async support for FastAPI
- Coverage settings
- Default environment variables
- Test markers

### conftest.py

Shared fixtures and hooks:

- AI provider fixtures
- API client fixtures
- Test data fixtures
- Database fixtures (placeholder)
- Auto-marking based on test location

## Writing Tests

### Test File Naming

- **test_*.py** - Main pattern
- ***_test.py** - Alternative pattern

### Test Function Naming

```python
def test_<what_is_being_tested>():
    """Clear description of test purpose"""
    # Arrange
    setup_code()

    # Act
    result = function_under_test()

    # Assert
    assert result == expected
```

### Unit Test Example

```python
import pytest
from src.api.lib.mock_ai_provider import MockAIProvider

@pytest.mark.unit
def test_embedding_determinism(mock_provider):
    """Test that embeddings are deterministic"""
    text = "test input"

    emb1 = mock_provider.generate_embedding(text)
    emb2 = mock_provider.generate_embedding(text)

    assert emb1["embedding"] == emb2["embedding"]
```

### API Test Example

```python
import pytest

@pytest.mark.api
def test_health_endpoint(api_client):
    """Test /health endpoint returns 200"""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.skip("Database fixtures not yet implemented")
def test_concept_persistence(test_db, mock_provider):
    """Test that concepts persist to database"""
    # Will be implemented when database fixtures are ready
    pass
```

## Test Coverage Goals

Based on docs/testing/TEST_COVERAGE.md:

### Priority 1: Smoke Tests (Quick Sanity Checks)

- ✅ Mock AI provider works
- ⏳ API server starts
- ⏳ Database connectivity
- ⏳ Basic concept extraction

### Priority 2: Functional Tests

- ⏳ Document ingestion (with mock AI)
- ⏳ Concept search
- ⏳ Graph traversal
- ⏳ Ontology operations

### Priority 3: Edge Cases

- ⏳ Empty documents
- ⏳ Duplicate content
- ⏳ Invalid inputs
- ⏳ Concurrent operations

### Priority 4: Integration Tests

- ⏳ Full ingestion pipeline
- ⏳ Backup/restore
- ⏳ Multi-user scenarios

## CI/CD Integration

Tests are designed to run in CI without external dependencies:

```bash
# CI test command
pytest -m "unit or smoke" --cov=src --cov-report=xml
```

## Troubleshooting

### ImportError: No module named 'pytest'

```bash
pip install -r requirements.txt
```

### Tests can't find src/ modules

```bash
# Run pytest from project root
cd /path/to/knowledge-graph-system
pytest
```

### Database connection errors

```bash
# Ensure test database is configured
export POSTGRES_DB=knowledge_graph_test
export POSTGRES_USER=test
export POSTGRES_PASSWORD=test
```

### Mock provider not being used

```bash
# Verify environment
pytest -v --showenv
# Should show AI_PROVIDER=mock
```

## Next Steps

1. ✅ Create mock AI provider
2. ✅ Set up pytest framework
3. ⏳ Implement database fixtures
4. ⏳ Write API endpoint tests
5. ⏳ Write integration tests
6. ⏳ Add TypeScript/Jest testing
7. ⏳ Set up CI/CD pipeline

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [httpx Testing](https://www.python-httpx.org/advanced/)
