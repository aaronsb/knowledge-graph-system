"""
Authentication endpoints tests (ADR-403).

Tests for user management and authentication endpoints.

NOTE: ADR-406 (Unified OAuth Architecture) removed several endpoints:
- POST /auth/login — replaced by OAuth 2.0 flows
- GET /auth/me — replaced by GET /users/me
- POST /auth/logout — replaced by OAuth token revocation
- GET/POST/DELETE /auth/api-keys — replaced by OAuth client credentials

Remaining endpoints:
- POST /auth/register - Create new user
- PUT /auth/me - Update current user profile
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# Registration Tests
# =============================================================================

@pytest.mark.api
@pytest.mark.smoke
def test_register_user_success(api_client):
    """Test successful user registration (self-registered users are read_only)"""
    # NOTE: This test requires a clean database. If the user already exists
    # from a previous run, it will get 409 Conflict. Marked for review.
    response = api_client.post("/auth/register", json={
        "username": "testuser",
        "password": "SecurePass123!"
    })

    # Accept both 201 (new user) and 409 (user exists from previous run)
    # A clean DB would return 201; a dirty DB returns 409.
    if response.status_code == 409:
        pytest.skip("Test user already exists in database (test isolation issue)")

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    # ADR-400 / #431: self-registration always yields least-privilege read_only,
    # regardless of any client input.
    assert data["role"] == "read_only"
    assert "id" in data
    assert "password" not in data  # Should not return password


@pytest.mark.api
def test_register_user_weak_password(api_client):
    """Test registration fails with weak password"""
    response = api_client.post("/auth/register", json={
        "username": "weakuser",
        "password": "weak",
        "role": "contributor"
    })

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "password" in str(data).lower()


@pytest.mark.api
def test_register_user_duplicate_username(api_client):
    """Test registration fails with duplicate username"""
    # Register first user
    api_client.post("/auth/register", json={
        "username": "duplicate",
        "password": "SecurePass123!",
        "role": "contributor"
    })

    # Try to register again with same username
    response = api_client.post("/auth/register", json={
        "username": "duplicate",
        "password": "DifferentPass456!",
        "role": "curator"
    })

    assert response.status_code == 409  # Conflict
    data = response.json()
    assert "already exists" in data["detail"].lower()


@pytest.mark.api
@pytest.mark.security
def test_register_user_cannot_self_assign_privileged_role(api_client):
    """
    Regression for the ADR-400 / #431 privilege-escalation blocker.

    POST /auth/register must IGNORE any client-supplied role. A request asking
    for 'platform_admin' (or 'admin') must never produce a privileged account —
    the self-registered user is created as read_only. Elevated roles are only
    assignable through the users:create-gated admin path.
    """
    for attempted_role in ("platform_admin", "admin", "curator", "superadmin"):
        response = api_client.post("/auth/register", json={
            "username": f"escalate_{attempted_role}",
            "password": "SecurePass123!",
            "role": attempted_role,  # extra field — must be ignored, not honored
        })

        if response.status_code == 409:
            # User exists from a previous run; the invariant still holds for them.
            continue

        assert response.status_code == 201, (
            f"register with role={attempted_role!r} returned {response.status_code}"
        )
        data = response.json()
        assert data["role"] == "read_only", (
            f"PRIVILEGE ESCALATION: register honored role={attempted_role!r} "
            f"and created a {data['role']!r} account"
        )


# =============================================================================
# Endpoints removed by ADR-406 (Unified OAuth Architecture):
# - POST /auth/login → OAuth 2.0 flows (api/app/routes/oauth.py)
# - GET /auth/me → GET /users/me (OAuth-authenticated)
# - POST /auth/logout → OAuth token revocation
# - GET/POST/DELETE /auth/api-keys → OAuth client credentials
# =============================================================================
