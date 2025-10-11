"""
Authentication endpoints tests (ADR-027).

Tests for user management and authentication endpoints.

Endpoints tested:
- POST /auth/register - Create new user
- POST /auth/login - User login
- GET /auth/me - Get current user
- PUT /auth/me - Update current user
- POST /auth/logout - Logout
- GET /auth/api-keys - List API keys
- POST /auth/api-keys - Create API key
- DELETE /auth/api-keys/{key_id} - Revoke API key
- GET /users - List all users (admin)
- GET /users/{user_id} - Get user details (admin)
- PUT /users/{user_id} - Update user (admin)
- DELETE /users/{user_id} - Delete user (admin)
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
    response = api_client.post("/auth/register", json={
        "username": "testuser",
        "password": "SecurePass123!",
        "role": "contributor"
    })

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
# Login Tests
# =============================================================================

@pytest.mark.api
@pytest.mark.smoke
def test_login_success(api_client):
    """Test successful login returns JWT token"""
    # Register user first
    api_client.post("/auth/register", json={
        "username": "loginuser",
        "password": "SecurePass123!",
        "role": "contributor"
    })

    # Login
    response = api_client.post("/auth/login", data={
        "username": "loginuser",
        "password": "SecurePass123!"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert "user" in data
    assert data["user"]["username"] == "loginuser"


@pytest.mark.api
def test_login_wrong_password(api_client):
    """Test login fails with wrong password"""
    # Register user first
    api_client.post("/auth/register", json={
        "username": "wrongpass",
        "password": "SecurePass123!",
        "role": "contributor"
    })

    # Try to login with wrong password
    response = api_client.post("/auth/login", data={
        "username": "wrongpass",
        "password": "WrongPassword456!"
    })

    assert response.status_code == 401  # Unauthorized
    data = response.json()
    assert "invalid" in data["detail"].lower() or "incorrect" in data["detail"].lower()


@pytest.mark.api
def test_login_nonexistent_user(api_client):
    """Test login fails for non-existent user"""
    response = api_client.post("/auth/login", data={
        "username": "nonexistent",
        "password": "SecurePass123!"
    })

    assert response.status_code == 401  # Unauthorized


@pytest.mark.api
def test_login_disabled_user(api_client):
    """Test login fails for disabled user"""
    # TODO: Implement after user admin endpoints are ready
    pytest.skip("Requires admin endpoints to disable user")


# =============================================================================
# Current User Tests (Authenticated)
# =============================================================================

@pytest.mark.api
@pytest.mark.smoke
def test_get_current_user(api_client):
    """Test GET /auth/me returns current user"""
    # Register and login
    api_client.post("/auth/register", json={
        "username": "currentuser",
        "password": "SecurePass123!",
        "role": "curator"
    })
    login_response = api_client.post("/auth/login", data={
        "username": "currentuser",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Get current user
    response = api_client.get("/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "currentuser"
    assert data["role"] == "curator"
    assert "password" not in data


@pytest.mark.api
def test_get_current_user_no_token(api_client):
    """Test GET /auth/me fails without token"""
    response = api_client.get("/auth/me")

    assert response.status_code == 401  # Unauthorized


@pytest.mark.api
def test_get_current_user_invalid_token(api_client):
    """Test GET /auth/me fails with invalid token"""
    response = api_client.get("/auth/me", headers={
        "Authorization": "Bearer invalid_token_here"
    })

    assert response.status_code == 401  # Unauthorized


@pytest.mark.api
def test_update_current_user_password(api_client):
    """Test PUT /auth/me updates password"""
    # Register and login
    api_client.post("/auth/register", json={
        "username": "updateuser",
        "password": "OldPass123!",
        "role": "contributor"
    })
    login_response = api_client.post("/auth/login", data={
        "username": "updateuser",
        "password": "OldPass123!"
    })
    token = login_response.json()["access_token"]

    # Update password
    response = api_client.put("/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "NewPass456!"}
    )

    assert response.status_code == 200

    # Try to login with old password (should fail)
    response = api_client.post("/auth/login", data={
        "username": "updateuser",
        "password": "OldPass123!"
    })
    assert response.status_code == 401

    # Login with new password (should succeed)
    response = api_client.post("/auth/login", data={
        "username": "updateuser",
        "password": "NewPass456!"
    })
    assert response.status_code == 200


# =============================================================================
# API Key Tests
# =============================================================================

@pytest.mark.api
def test_create_api_key(api_client):
    """Test POST /auth/api-keys creates new API key"""
    # Register and login
    api_client.post("/auth/register", json={
        "username": "apikeyuser",
        "password": "SecurePass123!",
        "role": "contributor"
    })
    login_response = api_client.post("/auth/login", data={
        "username": "apikeyuser",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Create API key
    response = api_client.post("/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Key", "scopes": ["read:concepts"]}
    )

    assert response.status_code == 201
    data = response.json()
    assert "key" in data  # Plaintext key shown once
    assert data["key"].startswith("kg_sk_")
    assert data["name"] == "Test Key"
    assert data["scopes"] == ["read:concepts"]


@pytest.mark.api
def test_list_api_keys(api_client):
    """Test GET /auth/api-keys lists user's API keys"""
    # Register and login
    api_client.post("/auth/register", json={
        "username": "listkeys",
        "password": "SecurePass123!",
        "role": "contributor"
    })
    login_response = api_client.post("/auth/login", data={
        "username": "listkeys",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Create API key
    api_client.post("/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Key 1"}
    )

    # List API keys
    response = api_client.get("/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "key" not in data[0]  # Should NOT show plaintext key in list


@pytest.mark.api
def test_use_api_key_for_authentication(api_client):
    """Test API key can be used for authentication"""
    # Register and login
    api_client.post("/auth/register", json={
        "username": "apiauth",
        "password": "SecurePass123!",
        "role": "contributor"
    })
    login_response = api_client.post("/auth/login", data={
        "username": "apiauth",
        "password": "SecurePass123!"
    })
    token = login_response.json()["access_token"]

    # Create API key
    key_response = api_client.post("/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Auth Key"}
    )
    api_key = key_response.json()["key"]

    # Use API key to access protected endpoint
    response = api_client.get("/auth/me",
        headers={"Authorization": f"Bearer {api_key}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "apiauth"


# =============================================================================
# Admin User Management Tests
# =============================================================================

@pytest.mark.api
@pytest.mark.integration
def test_admin_list_users(api_client):
    """Test GET /users lists all users (admin only)"""
    # TODO: Implement after admin routes are ready
    pytest.skip("Requires admin user management endpoints")


@pytest.mark.api
@pytest.mark.integration
def test_admin_update_user_role(api_client):
    """Test PUT /users/{user_id} updates role (admin only)"""
    # TODO: Implement after admin routes are ready
    pytest.skip("Requires admin user management endpoints")


@pytest.mark.api
@pytest.mark.integration
def test_admin_delete_user(api_client):
    """Test DELETE /users/{user_id} deletes user (admin only)"""
    # TODO: Implement after admin routes are ready
    pytest.skip("Requires admin user management endpoints")


@pytest.mark.api
def test_non_admin_cannot_list_users(api_client):
    """Test non-admin users cannot list all users"""
    # TODO: Implement after admin routes are ready
    pytest.skip("Requires admin user management endpoints")
