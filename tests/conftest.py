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
# AI provider mocking (always mock for tests)
os.environ["AI_PROVIDER"] = "mock"
os.environ["MOCK_MODE"] = "default"
# Database config comes from container env vars (set in docker-compose)

from api.app.lib.mock_ai_provider import MockAIProvider, get_mock_provider
from api.app.lib.ai_providers import get_provider


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
    from api.app.main import app

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
    from api.app.main import app

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
# OAuth 2.0 Authentication Fixtures (ADR-054, ADR-060)
# ============================================================================

@pytest.fixture
def test_user_credentials() -> Dict[str, Any]:
    """
    Provide test user credentials.

    Returns credentials for a regular contributor role test account.
    """
    from datetime import datetime, timezone

    return {
        "id": 100,
        "username": "testuser",
        "password_hash": "$2b$12$...",  # Mock hash
        "role": "contributor",
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
        "last_login": None
    }


@pytest.fixture
def test_admin_credentials() -> Dict[str, Any]:
    """
    Provide test admin credentials.

    Returns credentials for an ADMIN role test account.
    """
    from datetime import datetime, timezone

    return {
        "id": 101,
        "username": "testadmin",
        "password_hash": "$2b$12$...",  # Mock hash
        "role": "admin",
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
        "last_login": None
    }


@pytest.fixture
def create_test_oauth_token():
    """
    Factory fixture for creating test OAuth 2.0 tokens.

    Returns a function that creates tokens with custom properties.

    Usage:
        def test_something(create_test_oauth_token):
            token = create_test_oauth_token(user_id=1, role="admin")
            # Use token in test
    """
    def _create_token(
        user_id: int = 100,
        username: str = "testuser",
        role: str = "contributor",
        disabled: bool = False,
        expired: bool = False,
        client_id: str = "test_client"
    ) -> str:
        """
        Create a test OAuth 2.0 access token.

        Args:
            user_id: User ID to embed in token
            username: Username to embed in token
            role: User role (read_only, contributor, curator, admin)
            disabled: Whether user is disabled
            expired: Whether token should be expired
            client_id: OAuth client ID

        Returns:
            Mock OAuth token string (not a real JWT, just a test identifier)
        """
        # Create a simple test token (not a real JWT since we're mocking)
        # Real OAuth tokens are validated against database
        parts = [
            f"user_{user_id}",
            role,
            "expired" if expired else "valid",
            client_id
        ]
        return f"test_oauth_token:{'|'.join(parts)}"

    return _create_token


@pytest.fixture
def auth_headers_user(create_test_oauth_token):
    """
    Provide authorization headers for a regular contributor role.

    Returns headers dict with valid OAuth token for testing USER endpoints.
    """
    token = create_test_oauth_token(user_id=100, role="contributor")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(create_test_oauth_token):
    """
    Provide authorization headers for an ADMIN role.

    Returns headers dict with valid OAuth token for testing ADMIN endpoints.
    """
    token = create_test_oauth_token(user_id=101, role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def expired_oauth_token(create_test_oauth_token):
    """
    Provide an expired OAuth token for testing token expiration.
    """
    return create_test_oauth_token(user_id=100, role="contributor", expired=True)


@pytest.fixture
def mock_oauth_validation(monkeypatch, test_user_credentials, test_admin_credentials):
    """
    Mock OAuth token validation for testing without database.

    Patches validate_oauth_access_token to return test users based on token.
    This allows testing authentication flows without a live database.

    Usage:
        def test_endpoint(api_client, mock_oauth_validation):
            # OAuth validation is now mocked
            response = api_client.get("/protected", headers=auth_headers_user)
    """
    from api.app.models.auth import UserInDB
    from datetime import datetime, timezone

    def mock_validate(token: str):
        """Mock validate_oauth_access_token function"""
        # Parse test token
        if not token.startswith("test_oauth_token:"):
            return None

        try:
            parts = token.replace("test_oauth_token:", "").split("|")
            user_id_str = parts[0]  # e.g., "user_100"
            role = parts[1]
            validity = parts[2]

            if validity == "expired":
                return None

            # Extract user ID
            user_id = int(user_id_str.replace("user_", ""))

            # Return appropriate test user
            if role == "admin":
                creds = test_admin_credentials.copy()
                creds["id"] = user_id
                return UserInDB(**creds)
            else:
                creds = test_user_credentials.copy()
                creds["id"] = user_id
                creds["role"] = role
                return UserInDB(**creds)

        except Exception:
            return None

    def mock_get_scopes(token: str):
        """Mock get_token_scopes to return all kg scopes for test tokens."""
        if token.startswith("test_oauth_token:"):
            # Return all scopes for testing
            return ["kg:read", "kg:write", "kg:edit", "kg:import"]
        return []

    # Patch the validation function
    monkeypatch.setattr(
        "api.app.dependencies.auth.validate_oauth_access_token",
        mock_validate
    )
    # Patch scope checking for ADR-089 routes
    monkeypatch.setattr(
        "api.app.dependencies.auth.get_token_scopes",
        mock_get_scopes
    )


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
    config.addinivalue_line("markers", "security: Security and authentication tests")


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
