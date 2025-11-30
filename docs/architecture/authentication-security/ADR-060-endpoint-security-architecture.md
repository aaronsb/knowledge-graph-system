# ADR-060: API Endpoint Security Architecture

**Status:** Proposed
**Date:** 2025-01-05
**Deciders:** Engineering Team
**Related ADRs:**
- [ADR-028: Dynamic RBAC System](./ADR-028-dynamic-rbac-system.md) - RBAC implementation
- [ADR-054: OAuth Client Management](./ADR-054-oauth-client-management.md) - OAuth 2.0 authentication
- [ADR-027: User Management API](./ADR-027-user-management-api.md) - User operations

## Overview

Imagine building a house room by room, deciding whether each room needs a lock as you build it. You might remember to lock the front door and your bedroom, but forget about the window in the garage or the basement entrance. That's essentially what happened with our API - we built 112 endpoints, remembered to secure 6 of them, and left 52 completely unprotected. Anyone could delete ontologies, grant themselves admin privileges, or reset the entire database.

This isn't a made-up scenario - this was the actual state discovered in a security audit. We had OAuth 2.0 authentication (ADR-054) and a sophisticated RBAC system (ADR-028), but they were optional components that developers had to remember to use. Most didn't. The admin database reset endpoint? No authentication. User management? Open to everyone. Critical RBAC operations? Completely unprotected.

The core problem is architectural: should authentication be applied at the endpoint level (each endpoint declares what it needs) or at the infrastructure level (middleware that intercepts all requests)? Different frameworks make different choices. We researched production FastAPI patterns and found that the official FastAPI Full-Stack Template uses per-endpoint dependency injection, not middleware. This makes security requirements visible in API documentation and type-checked by Python.

This ADR adopts that proven pattern with one addition: a central security policy file that documents what each endpoint should require. This gives us both explicitness (each endpoint declares its requirements) and auditability (we can verify the implementation matches the policy). Think of it like building codes for houses - each room declares whether it needs fire safety equipment, but inspectors can check compliance against a central standard.

---

## Context

### Problem Statement

An API authentication audit (2025-01-05) revealed critical security gaps:

- **112 total API endpoints** exist in the system
- **Only 6 endpoints (5%)** have proper authentication
- **52 endpoints (46%)** completely lack authentication but require it
- **Critical endpoints unprotected:** Admin operations, user management, RBAC, database reset, Cypher queries

**Risk Assessment:** Anyone can currently delete ontologies, grant themselves admin roles, or reset the entire database. This is a **CRITICAL** security vulnerability blocking production deployment.

### Current State

**Scattered Security Implementation:**
- Some endpoints use `Depends(get_current_user)` manually
- Most endpoints have no authentication checks at all
- No consistent pattern across routes
- Security requirements not documented centrally
- Easy for developers to forget authentication on new endpoints

**Deferred Architecture:**
Prior ADRs (ADR-028, ADR-054) implemented authentication and RBAC components but deferred the overall security architecture. This ADR addresses that gap.

### Research: Industry Standards

We researched production FastAPI security patterns to avoid inventing custom approaches:

**FastAPI Full-Stack Template** (official reference implementation by @tiangolo):
- Uses per-endpoint dependency injection
- No middleware for authentication
- Type-annotated dependencies (`CurrentUser`, `SessionDep`)
- Superuser dependency for admin routes: `dependencies=[Depends(get_current_active_superuser)]`
- Public endpoints have no dependencies

**Key Sources:**
- [FastAPI Full-Stack Template](https://github.com/fastapi/full-stack-fastapi-template)
- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [FastAPI OAuth2 with JWT](https://testdriven.io/blog/fastapi-jwt-auth/)

**Consensus:** Production FastAPI apps use **per-endpoint dependency injection** rather than middleware for authentication. This provides better OpenAPI documentation, testability, and explicitness.

---

## Decision

We adopt the **FastAPI Full-Stack Template security pattern** with per-endpoint dependency injection:

### 1. Security Levels

```python
# Three security levels (no custom invention)
PUBLIC    # No authentication required
USER      # Authenticated user required
ADMIN     # Admin role required
```

### 2. Type-Annotated Dependencies

```python
# From src/api/dependencies/auth.py (already exists, needs refinement)

# Type alias for authenticated user
CurrentUser = Annotated[dict, Depends(get_current_user)]

# Public endpoints - no dependencies
@router.get("/health")
async def health():
    return {"status": "healthy"}

# User endpoints - CurrentUser parameter
@router.get("/users/me")
async def get_my_profile(current_user: CurrentUser):
    return current_user

# Admin endpoints - superuser dependency
@router.post("/admin/reset")
async def reset_database(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    return await reset_db()
```

### 3. Per-Endpoint Dependencies (Not Router-Level)

**Pattern from FastAPI Template:**
```python
# ❌ NOT router-level (would be invisible in OpenAPI)
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]  # Don't do this
)

# ✅ Per-endpoint (visible in OpenAPI docs)
@router.post("/admin/reset")
async def reset_database(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    ...
```

**Rationale:** Per-endpoint dependencies appear in OpenAPI/Swagger documentation, making security requirements visible to API consumers.

### 4. Central Security Policy (Our Addition)

While the FastAPI template doesn't mandate a central config, we add one for auditability:

```python
# src/api/config/endpoint_security.py
"""
Central documentation of endpoint security requirements.
Actual enforcement happens via per-endpoint dependencies.
This file serves as:
1. Documentation/audit reference
2. Validation source for startup checks
3. Guide for enhanced audit script
"""

ENDPOINT_SECURITY_REQUIREMENTS = {
    # Public endpoints
    "/health": "public",
    "/auth/*": "public",
    "/docs": "public",

    # User endpoints
    "/query/*": "user",
    "/ontology/*": "user",
    "/jobs/*": "user",

    # Admin endpoints
    "/admin/*": "admin",
    "/rbac/*": "admin",
    "/users/{user_id}": "admin",  # Other users
}

# Default for unlisted endpoints
DEFAULT_SECURITY = "user"  # Secure by default
```

### 5. Startup Validation

```python
# src/api/main.py

@app.on_event("startup")
async def validate_endpoint_security():
    """
    Validate all endpoints have appropriate dependencies.
    Logs warnings for endpoints missing auth.
    """
    from src.api.config.endpoint_security import validate_security

    results = validate_security(app)

    if results["missing_auth"]:
        logger.error(f"❌ {len(results['missing_auth'])} endpoints missing auth!")
        for endpoint in results["missing_auth"]:
            logger.error(f"   {endpoint}")

        # Optionally fail startup in production
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("Security validation failed")
```

---

## Implementation Pattern

### Route Structure

```python
# src/api/routes/admin.py
"""
Admin routes - all require admin role.
Pattern: CurrentUser + require_role("admin") on each endpoint.
"""
from fastapi import APIRouter, Depends
from src.api.dependencies.auth import CurrentUser, require_role

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/status")
async def get_system_status(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """Admin only - visible in OpenAPI docs"""
    return await get_status()

@router.post("/reset")
async def reset_database(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """DANGEROUS: Admin only"""
    return await reset_db()
```

```python
# src/api/routes/users.py
"""
User routes - authenticated users can access their own data.
Pattern: CurrentUser parameter with ownership checks in handler.
"""
from fastapi import APIRouter, HTTPException
from src.api.dependencies.auth import CurrentUser, require_role

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
async def get_my_profile(current_user: CurrentUser):
    """Any authenticated user"""
    return current_user

@router.get("/{user_id}")
async def get_user(user_id: str, current_user: CurrentUser):
    """User can see their own profile, admins can see any"""
    if user_id != current_user["user_id"]:
        # Check for admin role
        if "admin" not in current_user.get("roles", []):
            raise HTTPException(403, "Can only view your own profile")

    return await db.get_user(user_id)

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """Admin only - delete any user"""
    return await db.delete_user(user_id)
```

```python
# src/api/routes/public.py
"""
Public routes - no authentication required.
Pattern: No dependencies.
"""
from fastapi import APIRouter

router = APIRouter(tags=["public"])

@router.get("/health")
async def health():
    """Public endpoint - no auth"""
    return {"status": "healthy"}
```

### Dependency Definitions

```python
# src/api/dependencies/auth.py (refine existing)
"""
Authentication dependencies following FastAPI Full-Stack Template pattern.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from src.api.core.config import settings
from src.api.models.user import User
from src.api.lib.db import get_db

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/oauth/token"
)

# Type aliases (FastAPI template pattern)
TokenDep = Annotated[str, Depends(oauth2_scheme)]
SessionDep = Annotated[Session, Depends(get_db)]

async def get_current_user(
    token: TokenDep,
    session: SessionDep
) -> dict:
    """
    Decode JWT token and return current user.
    Raises 401 if token invalid, 404 if user not found.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if not user.is_active:
        raise HTTPException(400, "Inactive user")

    return user

# Type alias for authenticated user (FastAPI template pattern)
CurrentUser = Annotated[dict, Depends(get_current_user)]

def require_role(role: str):
    """
    Dependency factory for role-based access control.
    Usage: Depends(require_role("admin"))
    """
    def check_role(current_user: CurrentUser) -> None:
        if role not in current_user.get("roles", []):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' required"
            )
    return check_role

def require_permission(permission: str):
    """
    Dependency factory for permission-based access control.
    Usage: Depends(require_permission("ontology:delete"))
    """
    def check_permission(current_user: CurrentUser) -> None:
        if permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
    return check_permission
```

---

## Migration Path

### Phase 1: Critical Endpoints

**Priority:** CRITICAL - Block production deployment

Add authentication to endpoints that can cause immediate damage:

```
✅ /admin/* - All admin operations
✅ /rbac/* - Role/permission management
✅ /users/{user_id} - User management (other users)
✅ /ontology/{name}/rename - Ontology deletion/modification
✅ /vocabulary/merge - Vocabulary write operations
✅ /vocabulary/consolidate
```

**Acceptance Criteria:**
- All admin endpoints require `CurrentUser + require_role("admin")`
- All user management endpoints have ownership checks or admin requirement
- RBAC endpoints require admin role
- Audit script shows 0 unprotected admin endpoints

### Phase 2: All Endpoints

Add authentication to remaining endpoints:

```
✅ /query/* - USER level (authenticated user required)
✅ /ontology/* - USER level (read operations)
✅ /jobs/* - USER level (see own jobs)
✅ /ingest/* - USER level (with job approval workflow)
✅ /sources/* - USER level (read-only)
```

**Acceptance Criteria:**
- All non-public endpoints have `CurrentUser` parameter
- Central security policy documented
- Startup validation passes
- Audit script shows proper classification

### Phase 3: Testing & Validation

```
✅ Unit tests for all dependencies
✅ Integration tests for protected endpoints
✅ OpenAPI schema validation
✅ Security regression tests in CI/CD
```

---

## Testing Strategy

### Dependency Override Pattern

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from src.api.dependencies.auth import get_current_user

@pytest.fixture
def admin_user():
    return {
        "user_id": "test-admin",
        "email": "admin@example.com",
        "roles": ["admin"],
        "is_active": True
    }

@pytest.fixture
def regular_user():
    return {
        "user_id": "test-user",
        "email": "user@example.com",
        "roles": ["user"],
        "is_active": True
    }

@pytest.fixture
def admin_client(app, admin_user):
    """Test client with admin authentication"""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def user_client(app, regular_user):
    """Test client with regular user authentication"""
    app.dependency_overrides[get_current_user] = lambda: regular_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def anonymous_client(app):
    """Test client without authentication"""
    with TestClient(app) as client:
        yield client
```

### Security Tests

```python
# tests/test_security.py
def test_admin_endpoint_requires_admin(admin_client, user_client, anonymous_client):
    """Admin endpoints reject non-admin users"""

    # Anonymous: 401 Unauthorized
    response = anonymous_client.post("/admin/reset")
    assert response.status_code == 401

    # Regular user: 403 Forbidden
    response = user_client.post("/admin/reset")
    assert response.status_code == 403

    # Admin: 200 OK
    response = admin_client.post("/admin/reset")
    assert response.status_code == 200

def test_user_endpoint_requires_auth(user_client, anonymous_client):
    """User endpoints reject unauthenticated requests"""

    # Anonymous: 401
    response = anonymous_client.get("/users/me")
    assert response.status_code == 401

    # Authenticated: 200
    response = user_client.get("/users/me")
    assert response.status_code == 200

def test_public_endpoint_allows_anonymous(anonymous_client):
    """Public endpoints work without auth"""
    response = anonymous_client.get("/health")
    assert response.status_code == 200
```

---

## Consequences

### Positive

1. **✅ Industry Standard Pattern:** Following official FastAPI template - well-understood by community
2. **✅ OpenAPI Documentation:** Security requirements visible in Swagger/ReDoc
3. **✅ Easy Testing:** Dependency overrides make testing straightforward
4. **✅ Explicit Security:** Each endpoint declares its auth requirements in code
5. **✅ Type Safety:** Type-annotated dependencies provide IDE autocompletion
6. **✅ Flexible:** Can have different auth requirements per endpoint
7. **✅ No Custom Invention:** Using proven patterns, not custom solutions

### Negative

1. **⚠️ Verbose:** Each endpoint must declare dependencies (more code)
2. **⚠️ Easy to Forget:** Developers might forget to add dependencies to new endpoints
3. **⚠️ Scattered:** Security requirements across multiple route files

### Mitigations

1. **Startup Validation:** Catch missing dependencies at app startup
2. **Central Policy Document:** Single source of truth for audit
3. **Enhanced Audit Script:** Continuous monitoring of endpoint security
4. **CI/CD Integration:** Block PRs with unprotected endpoints
5. **Code Review Checklist:** Require security review for new endpoints

---

## Alternatives Considered

### Alternative 1: Middleware-Based Authentication

**Approach:** Use middleware to enforce admin role by default on all endpoints, with explicit relaxations.

```python
class DefaultAdminMiddleware:
    """Default: all endpoints require admin"""

    RELAXATIONS = {
        "/users/*": "user",
        "/health": "public"
    }
```

**Rejected Because:**
- ❌ Not standard FastAPI pattern (less common in production)
- ❌ Security requirements not visible in OpenAPI documentation
- ❌ More complex testing (override middleware + dependencies)
- ❌ Path matching adds complexity
- ❌ Against FastAPI's design philosophy (dependencies over middleware)

### Alternative 2: Router-Level Dependencies

**Approach:** Apply dependencies at router level rather than per-endpoint.

```python
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]
)
```

**Partially Accepted:**
- ✅ Could use this for routers where ALL endpoints have same requirements
- ⚠️ FastAPI template uses per-endpoint pattern
- ⚠️ Less flexible (can't vary auth within router)

**Decision:** Use per-endpoint pattern as primary approach, optionally use router-level for consistency.

### Alternative 3: Decorator-Based Registry

**Approach:** Custom decorators that register security requirements.

```python
@router.get("/admin/status")
@require_admin
async def get_status():
    ...
```

**Rejected Because:**
- ❌ Custom invention (not standard FastAPI pattern)
- ❌ Doesn't integrate with OpenAPI like `Depends()` does
- ❌ More code to maintain (custom decorator system)
- ❌ FastAPI template doesn't use this pattern

---

## References

### Official FastAPI Resources

- [FastAPI Full-Stack Template](https://github.com/fastapi/full-stack-fastapi-template) - Official production template
- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) - JWT authentication
- [Dependencies API Reference](https://fastapi.tiangolo.com/reference/dependencies/)

### Our Implementation

- [API Auth Audit Summary](../../testing/API_AUTH_AUDIT_SUMMARY.md) - Security findings
- [API Auth Testing Research](../../testing/API_AUTH_TESTING_RESEARCH.md) - Testing patterns
- Audit Tool: `scripts/development/audit-api-auth.sh`

### Related ADRs

- [ADR-028: Dynamic RBAC System](./ADR-028-dynamic-rbac-system.md) - Role/permission system
- [ADR-054: OAuth Client Management](./ADR-054-oauth-client-management.md) - OAuth 2.0 flow
- [ADR-027: User Management API](./ADR-027-user-management-api.md) - User operations
- [ADR-017: Sensitive Auth Verification](./ADR-017-sensitive-auth-verification.md) - Password verification

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-01-05 | Adopt FastAPI Full-Stack Template pattern | Industry standard, well-documented, proven in production |
| 2025-01-05 | Use per-endpoint dependencies (not router-level) | Matches official template, visible in OpenAPI |
| 2025-01-05 | Add central security policy document | Auditability, validation, documentation |
| 2025-01-05 | Reject middleware-based approach | Not standard pattern, against FastAPI philosophy |
| 2025-01-05 | 3-phase implementation (4 weeks) | Critical endpoints first, comprehensive coverage second, testing third |

---

## Approval

- [ ] Security Review
- [ ] Engineering Review
- [ ] Documentation Updated
- [ ] Implementation Plan Approved

**Next Steps:**
1. Review and approve this ADR
2. Update ADR-028 and ADR-054 with references to this ADR
3. Begin Phase 1 implementation (critical endpoints)
4. Update audit script to validate against this architecture
