"""
Authentication endpoints tests (ADR-027).

Tests for user management and authentication endpoints.

NOTE: ADR-054 (Unified OAuth Architecture) removed several endpoints:
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
    """Test successful user registration"""
    # NOTE: This test requires a clean database. If the user already exists
    # from a previous run, it will get 409 Conflict. Marked for review.
    response = api_client.post("/auth/register", json={
        "username": "testuser",
        "password": "SecurePass123!",
        "role": "contributor"
    })

    # Accept both 201 (new user) and 409 (user exists from previous run)
    # A clean DB would return 201; a dirty DB returns 409.
    if response.status_code == 409:
        pytest.skip("Test user already exists in database (test isolation issue)")

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "contributor"
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
def test_register_user_invalid_role(api_client):
    """Test registration fails with invalid role"""
    response = api_client.post("/auth/register", json={
        "username": "invalidrole",
        "password": "SecurePass123!",
        "role": "superadmin"  # Invalid role
    })

    assert response.status_code == 422  # Validation error


# =============================================================================
# Endpoints removed by ADR-054 (Unified OAuth Architecture):
# - POST /auth/login → OAuth 2.0 flows (api/app/routes/oauth.py)
# - GET /auth/me → GET /users/me (OAuth-authenticated)
# - POST /auth/logout → OAuth token revocation
# - GET/POST/DELETE /auth/api-keys → OAuth client credentials
# =============================================================================
