# API Authentication Testing Research

**Date:** 2025-11-04
**Branch:** `feature/api-auth-middleware-coverage`
**Purpose:** Establish comprehensive authentication testing for all API endpoints

## Current Authentication Stack

### Implementation Overview

We have a **mature OAuth 2.0 + RBAC authentication system** (ADR-054, ADR-028):

**Authentication Methods:**
- OAuth 2.0 access tokens (primary)
- API keys (secondary, starts with `kg_sk_`)
- Client credentials flow
- Device code flow
- Personal client flow

**Authorization:**
- Dynamic RBAC with permission checking
- Role-based access control (`require_role()`)
- Fine-grained permissions (`require_permission()`)
- Scope support (global, instance, filter-scoped)

**Key Files:**
- `src/api/dependencies/auth.py` - FastAPI dependency injection for auth
- `src/api/lib/auth.py` - Core auth logic
- `src/api/middleware/auth.py` - Legacy placeholder (Phase 1)
- `src/api/models/auth.py` - Auth data models
- `src/api/routes/auth.py` - Auth endpoints
- `src/api/routes/oauth.py` - OAuth endpoints
- `src/api/routes/rbac.py` - RBAC management

## FastAPI Auth Testing Best Practices (2025)

### 1. Fixture-Based Test Clients

**Pattern:**
```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def authenticated_client(app):
    """Create test client with valid auth token"""
    client = TestClient(app)

    # Create test user and get token
    user = create_test_user("testuser", "admin")
    token = create_access_token_for_user(user.id)

    # Inject token into client headers
    client.headers = {
        "Authorization": f"Bearer {token}"
    }
    return client

@pytest.fixture
def anonymous_client(app):
    """Create test client without authentication"""
    return TestClient(app)
```

**Benefits:**
- Reusable across tests
- Clear separation of authenticated vs anonymous
- Can scope fixtures (function, class, module, session)

### 2. Dependency Override Pattern

**Pattern:**
```python
from fastapi import Depends
from src.api.dependencies.auth import get_current_user

@pytest.fixture
def override_auth(app):
    """Override auth dependency to bypass real authentication"""
    def mock_current_user():
        return UserInDB(
            id=1,
            username="testuser",
            role="admin",
            disabled=False
        )

    app.dependency_overrides[get_current_user] = mock_current_user
    yield
    app.dependency_overrides.clear()
```

**Benefits:**
- Faster tests (skip real auth flow)
- Test business logic independently
- Easy to test different user roles/permissions

### 3. Router-Level Dependencies Over Middleware

**Why:** FastAPI recommends router-level dependencies for authentication:
- Better code readability
- Easier to test individual routes
- More maintainable than conditional middleware

**Implementation:**
```python
# ✅ Good: Router-level dependency
router = APIRouter(dependencies=[Depends(get_current_user)])

# ❌ Avoid: Global middleware for auth
# (middleware is better for logging, CORS, etc.)
```

### 4. Systematic Endpoint Coverage Testing

**Approach: OpenAPI Schema Introspection**

FastAPI generates an OpenAPI schema accessible via `app.openapi()`. We can:
1. Parse all endpoints from schema
2. Categorize by auth requirements
3. Verify protected endpoints actually require auth
4. Ensure test coverage for all endpoints

**Pattern:**
```python
def test_all_protected_endpoints_require_auth(app, anonymous_client):
    """Verify all protected endpoints reject unauthenticated requests"""

    # Get all routes from OpenAPI schema
    openapi_schema = app.openapi()

    for path, methods in openapi_schema["paths"].items():
        for method, details in methods.items():
            # Check if endpoint requires auth (has security scheme)
            if "security" in details:
                response = anonymous_client.request(method.upper(), path)
                assert response.status_code in [401, 403], \
                    f"{method.upper()} {path} should require auth"
```

### 5. Test Coverage with pytest-cov

**Installation:**
```bash
pip install pytest-cov
```

**Usage:**
```bash
# Run tests with coverage report
pytest --cov=src/api --cov-report=html

# Focus on specific modules
pytest tests/test_auth.py --cov=src/api/dependencies/auth --cov-report=term-missing
```

### 6. Integration vs Unit Testing

**Unit Tests:**
- Use `dependency_overrides` to mock auth
- Test business logic in isolation
- Fast, no database required

**Integration Tests:**
- Use real auth flow (create user, get token)
- Test end-to-end authentication
- Slower, requires database

**Best Practice:** Use both! Unit tests for coverage, integration tests for confidence.

## Testing Strategy for Knowledge Graph System

### Phase 1: Audit Current State

1. **Inventory all API endpoints**
   - List all route files
   - Extract all endpoints with method + path
   - Document current auth requirements

2. **Categorize endpoints by auth needs**
   - Public (no auth): health checks, public queries
   - Authenticated: most CRUD operations
   - Admin-only: database reset, user management
   - Permission-based: resource-specific actions

3. **Identify gaps**
   - Which endpoints should have auth but don't?
   - Which endpoints have auth but shouldn't?
   - Are auth requirements documented?

### Phase 2: Design Test Suite

1. **Create test fixtures**
   - `authenticated_client` (admin role)
   - `user_client` (regular user role)
   - `anonymous_client` (no auth)

2. **Write systematic tests**
   - Test all public endpoints work without auth
   - Test all protected endpoints require auth
   - Test role-based restrictions
   - Test permission-based restrictions

3. **Add OpenAPI schema validation**
   - Verify schema correctly marks protected endpoints
   - Ensure security schemes are documented
   - Test that schema matches implementation

### Phase 3: Automate and Enforce

1. **CI/CD Integration**
   - Add auth tests to test suite
   - Require passing auth tests for merges
   - Generate coverage reports

2. **Documentation**
   - Document auth requirements per endpoint
   - Add testing guide for developers
   - Create ADR for auth testing strategy

3. **Continuous Improvement**
   - Monitor for new endpoints without tests
   - Update tests when auth requirements change
   - Periodic security audits

## Tools and Resources

**Python Packages:**
- `pytest` - Test framework
- `pytest-cov` - Coverage measurement
- `pytest-asyncio` - Async test support
- `fastapi.testclient.TestClient` - Built-in test client

**Useful Patterns:**
- Fixtures for reusable test clients
- Dependency overrides for mocking
- Parametrized tests for multiple scenarios
- Schema introspection for validation

**References:**
- FastAPI Testing Docs: https://fastapi.tiangolo.com/tutorial/testing/
- pytest-cov: https://pytest-cov.readthedocs.io/
- ADR-054: OAuth 2.0 Authentication
- ADR-028: Dynamic RBAC

## Next Steps

1. Create endpoint inventory script
2. Audit current auth coverage
3. Design test fixtures and utilities
4. Write comprehensive auth test suite
5. Document findings in ADR
6. Integrate into CI/CD pipeline

---

**Status:** Research complete, ready for implementation
**Owner:** Engineering Team
**Priority:** High (security-critical)
