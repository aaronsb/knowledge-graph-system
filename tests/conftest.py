"""
Pytest fixtures for Knowledge Graph System tests.

Provides common fixtures for:
- Mock AI provider
- Test database setup/teardown
- FastAPI test client
- Sample test data
"""

import pytest
import os
from typing import Generator, Dict, Any
from fastapi.testclient import TestClient

# Set test environment before imports
os.environ["AI_PROVIDER"] = "mock"
os.environ["MOCK_MODE"] = "default"
os.environ["POSTGRES_DB"] = "knowledge_graph_test"

from src.api.lib.mock_ai_provider import MockAIProvider, get_mock_provider
from src.api.lib.ai_providers import get_provider


# ============================================================================
# AI Provider Fixtures
# ============================================================================

@pytest.fixture
def mock_provider() -> MockAIProvider:
    """
    Provide a mock AI provider for testing.

    Returns fresh provider instance for each test.
    """
    return get_mock_provider("default")


@pytest.fixture
def simple_mock_provider() -> MockAIProvider:
    """
    Provide a simple mock provider (minimal concepts).

    Useful for tests that need predictable, minimal output.
    """
    return get_mock_provider("simple")


@pytest.fixture
def complex_mock_provider() -> MockAIProvider:
    """
    Provide a complex mock provider (rich concept graph).

    Useful for tests that need multiple concepts and relationships.
    """
    return get_mock_provider("complex")


@pytest.fixture
def empty_mock_provider() -> MockAIProvider:
    """
    Provide an empty mock provider (no concepts).

    Useful for edge case testing.
    """
    return get_mock_provider("empty")


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================

@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    """
    Provide FastAPI test client.

    Creates a test client for API endpoint testing without running the server.

    Usage:
        def test_health(api_client):
            response = api_client.get("/health")
            assert response.status_code == 200
    """
    from src.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_api_client():
    """
    Provide async FastAPI test client.

    For tests that need async/await support.

    Usage:
        @pytest.mark.asyncio
        async def test_async_endpoint(async_api_client):
            response = await async_api_client.get("/health")
            assert response.status_code == 200
    """
    import httpx
    from src.api.main import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_text() -> str:
    """Provide sample text for extraction testing"""
    return """
    Knowledge graphs represent information as interconnected concepts.
    Each concept has properties and relationships to other concepts.
    This enables semantic search and graph traversal.
    """


@pytest.fixture
def sample_concepts() -> list[Dict[str, Any]]:
    """Provide sample existing concepts for testing"""
    return [
        {
            "concept_id": "test-concept-1",
            "label": "Knowledge Graph",
            "search_terms": ["knowledge", "graph", "semantic"]
        },
        {
            "concept_id": "test-concept-2",
            "label": "Semantic Search",
            "search_terms": ["semantic", "search", "query"]
        }
    ]


@pytest.fixture
def sample_embedding() -> list[float]:
    """Provide sample embedding vector for testing"""
    provider = get_mock_provider()
    result = provider.generate_embedding("test embedding")
    return result["embedding"]


# ============================================================================
# Database Fixtures (Placeholder - will be implemented when testing DB)
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """
    Provide test database connection.

    TODO: Implement database setup/teardown when ready for integration tests.

    Should:
    - Create test database
    - Run migrations/schema
    - Yield connection
    - Clean up after test
    """
    pytest.skip("Database fixtures not yet implemented")


@pytest.fixture(scope="function")
def clean_db(test_db):
    """
    Provide clean database for each test.

    TODO: Implement database cleanup between tests.

    Should:
    - Truncate all tables
    - Reset sequences
    - Clear test data
    """
    pytest.skip("Database cleanup not yet implemented")


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration.

    Returns test-specific settings that override production config.
    """
    return {
        "ai_provider": "mock",
        "mock_mode": "default",
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "knowledge_graph_test",
            "user": "test",
            "password": "test"
        },
        "job_db_path": ":memory:",  # In-memory SQLite for tests
        "testing": True
    }


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def temp_file(tmp_path):
    """
    Provide temporary file for testing file uploads.

    Uses pytest's tmp_path fixture to create isolated temp directories.

    Usage:
        def test_file_upload(temp_file):
            file_path = temp_file("test.txt", "content here")
            # Use file_path in test
    """
    def _create_file(filename: str, content: str) -> str:
        file_path = tmp_path / filename
        file_path.write_text(content)
        return str(file_path)

    return _create_file


# ============================================================================
# Pytest Configuration Hooks
# ============================================================================

def pytest_configure(config):
    """
    Pytest configuration hook.

    Called once at the start of the test session.
    """
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (require database)")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "smoke: Smoke tests (quick sanity checks)")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection.

    Auto-mark tests based on their location or name.
    """
    for item in items:
        # Auto-mark API tests
        if "api" in item.nodeid:
            item.add_marker(pytest.mark.api)

        # Auto-mark integration tests
        if "integration" in item.nodeid or "test_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Auto-mark unit tests (default for tests not in other categories)
        if not any(marker.name in ["integration", "api", "slow"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
