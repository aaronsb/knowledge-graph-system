"""
Endpoint Security Tests (ADR-060)

Integration tests for endpoint security levels across the API.

Security Levels (ADR-060):
- PUBLIC: No authentication required (health, docs, OAuth flows)
- USER: Requires authentication (queries, ingest, reads)
- ADMIN: Requires admin role (system admin, RBAC, destructive ops)

Tests verify that:
1. PUBLIC endpoints are accessible without authentication
2. USER endpoints require valid OAuth token
3. ADMIN endpoints require admin role
4. Proper error codes (401 Unauthorized, 403 Forbidden)
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# PUBLIC Endpoint Tests (No Authentication Required)
# =============================================================================

@pytest.mark.api
@pytest.mark.security
@pytest.mark.smoke
def test_health_endpoint_public(api_client, mock_oauth_validation):
    """Test /health is accessible without authentication"""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert "status" in response.json()


@pytest.mark.api
@pytest.mark.security
def test_database_health_endpoint_public(api_client, mock_oauth_validation):
    """Test /database/health is accessible without authentication"""
    response = api_client.get("/database/health")

    # May return 200 (healthy) or 503 (unhealthy) depending on DB state
    assert response.status_code in [200, 503]


@pytest.mark.api
@pytest.mark.security
def test_docs_endpoint_public(api_client, mock_oauth_validation):
    """Test /docs is accessible without authentication"""
    response = api_client.get("/docs")

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.security
def test_openapi_json_public(api_client, mock_oauth_validation):
    """Test /openapi.json is accessible without authentication"""
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    assert "openapi" in response.json()


# OAuth endpoints are PUBLIC (part of the authentication flow)
@pytest.mark.api
@pytest.mark.security
def test_oauth_authorize_endpoint_public(api_client, mock_oauth_validation):
    """Test /oauth/authorize is accessible without authentication"""
    # This endpoint typically redirects or shows login UI
    response = api_client.get("/oauth/authorize?client_id=test&response_type=code")

    # Accept various responses (redirect, HTML, or error)
    assert response.status_code in [200, 302, 400, 404]


# =============================================================================
# USER Endpoint Tests (Require Authentication)
# =============================================================================

@pytest.mark.api
@pytest.mark.security
def test_query_search_requires_auth(api_client, mock_oauth_validation):
    """Test /query/search returns 401 without token"""
    response = api_client.post("/query/search", json={"query": "test", "limit": 10})

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_query_search_succeeds_with_user_token(api_client, mock_oauth_validation, auth_headers_user):
    """Test /query/search succeeds with valid user token"""
    response = api_client.post(
        "/query/search",
        json={"query": "test", "limit": 10},
        headers=auth_headers_user
    )

    # Should succeed (200) or may have validation errors (422) depending on query
    assert response.status_code in [200, 422]


@pytest.mark.api
@pytest.mark.security
def test_query_details_requires_auth(api_client, mock_oauth_validation):
    """Test /query/details/{concept_id} returns 401 without token"""
    response = api_client.get("/query/details/test-concept-123")

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_query_details_succeeds_with_user_token(api_client, mock_oauth_validation, auth_headers_user):
    """Test /query/details/{concept_id} succeeds with valid user token"""
    response = api_client.get(
        "/query/details/test-concept-123",
        headers=auth_headers_user
    )

    # May return 404 (not found) or 200 (found) depending on DB state
    assert response.status_code in [200, 404]


@pytest.mark.api
@pytest.mark.security
def test_ingest_text_requires_auth(api_client, mock_oauth_validation):
    """Test /ingest/text returns 401 without token"""
    response = api_client.post("/ingest/text", json={
        "text": "Test content",
        "ontology": "Test",
        "filename": "test.txt"
    })

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_ingest_text_succeeds_with_user_token(api_client, mock_oauth_validation, auth_headers_user):
    """Test /ingest/text succeeds with valid user token"""
    response = api_client.post(
        "/ingest/text",
        json={
            "text": "Test content",
            "ontology": "Test",
            "filename": "test.txt"
        },
        headers=auth_headers_user
    )

    # Should create job (201) or may have validation errors (422)
    assert response.status_code in [201, 422]


@pytest.mark.api
@pytest.mark.security
def test_database_stats_requires_auth(api_client, mock_oauth_validation):
    """Test /database/stats returns 401 without token"""
    response = api_client.get("/database/stats")

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_database_stats_succeeds_with_user_token(api_client, mock_oauth_validation, auth_headers_user):
    """Test /database/stats succeeds with valid user token"""
    response = api_client.get("/database/stats", headers=auth_headers_user)

    # Should succeed (200) or may fail if DB unavailable (503)
    assert response.status_code in [200, 503]


@pytest.mark.api
@pytest.mark.security
def test_ontology_list_requires_auth(api_client, mock_oauth_validation):
    """Test /ontology/list returns 401 without token"""
    response = api_client.get("/ontology/list")

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_ontology_list_succeeds_with_user_token(api_client, mock_oauth_validation, auth_headers_user):
    """Test /ontology/list succeeds with valid user token"""
    response = api_client.get("/ontology/list", headers=auth_headers_user)

    assert response.status_code == 200


# =============================================================================
# ADMIN Endpoint Tests (Require Admin Role)
# =============================================================================

@pytest.mark.api
@pytest.mark.security
def test_admin_status_requires_auth(api_client, mock_oauth_validation):
    """Test /admin/status returns 401 without token"""
    response = api_client.get("/admin/status")

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_admin_status_requires_admin_role(api_client, mock_oauth_validation, auth_headers_user):
    """Test /admin/status returns 403 with non-admin token"""
    response = api_client.get("/admin/status", headers=auth_headers_user)

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


@pytest.mark.api
@pytest.mark.security
def test_admin_status_succeeds_with_admin_token(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /admin/status succeeds with admin token"""
    response = api_client.get("/admin/status", headers=auth_headers_admin)

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.security
def test_admin_reset_requires_admin_role(api_client, mock_oauth_validation, auth_headers_user):
    """Test /admin/reset returns 403 with non-admin token"""
    response = api_client.post(
        "/admin/reset",
        json={"confirm_phrase": "live man switch"},
        headers=auth_headers_user
    )

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_admin_extraction_config_requires_admin(api_client, mock_oauth_validation, auth_headers_user):
    """Test /admin/extraction/config returns 403 with non-admin token"""
    response = api_client.get("/admin/extraction/config", headers=auth_headers_user)

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_admin_extraction_config_succeeds_with_admin(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /admin/extraction/config succeeds with admin token"""
    response = api_client.get("/admin/extraction/config", headers=auth_headers_admin)

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.security
def test_admin_embedding_config_requires_admin(api_client, mock_oauth_validation, auth_headers_user):
    """Test /admin/embedding/config returns 403 with non-admin token"""
    response = api_client.get("/admin/embedding/config", headers=auth_headers_user)

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_admin_embedding_config_succeeds_with_admin(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /admin/embedding/config succeeds with admin token"""
    response = api_client.get("/admin/embedding/config", headers=auth_headers_admin)

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.security
def test_rbac_roles_requires_admin(api_client, mock_oauth_validation, auth_headers_user):
    """Test /rbac/roles returns 403 with non-admin token"""
    response = api_client.get("/rbac/roles", headers=auth_headers_user)

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_rbac_roles_succeeds_with_admin(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /rbac/roles succeeds with admin token"""
    response = api_client.get("/rbac/roles", headers=auth_headers_admin)

    # May succeed (200) or may fail if DB unavailable (503)
    assert response.status_code in [200, 503]


@pytest.mark.api
@pytest.mark.security
def test_vocabulary_config_set_requires_admin(api_client, mock_oauth_validation, auth_headers_user):
    """Test /vocabulary/config/set returns 403 with non-admin token"""
    response = api_client.post(
        "/vocabulary/config/set",
        json={"setting": "test", "value": "test"},
        headers=auth_headers_user
    )

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_vocabulary_config_set_succeeds_with_admin(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /vocabulary/config/set succeeds with admin token"""
    response = api_client.post(
        "/vocabulary/config/set",
        json={"setting": "test", "value": "test"},
        headers=auth_headers_admin
    )

    # May succeed (200) or have validation errors (422) or DB errors (503)
    assert response.status_code in [200, 422, 503]


@pytest.mark.api
@pytest.mark.security
def test_ontology_delete_requires_admin(api_client, mock_oauth_validation, auth_headers_user):
    """Test /ontology/delete returns 403 with non-admin token"""
    response = api_client.delete(
        "/ontology/delete/TestOntology",
        headers=auth_headers_user
    )

    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_ontology_delete_succeeds_with_admin(api_client, mock_oauth_validation, auth_headers_admin):
    """Test /ontology/delete succeeds with admin token"""
    response = api_client.delete(
        "/ontology/delete/TestOntology",
        headers=auth_headers_admin
    )

    # May succeed (200) or not found (404) or DB errors (503)
    assert response.status_code in [200, 404, 503]


# =============================================================================
# Token Validation Edge Cases
# =============================================================================

@pytest.mark.api
@pytest.mark.security
def test_user_endpoint_rejects_expired_token(api_client, mock_oauth_validation, expired_oauth_token):
    """Test USER endpoint rejects expired OAuth token"""
    response = api_client.get(
        "/database/stats",
        headers={"Authorization": f"Bearer {expired_oauth_token}"}
    )

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_admin_endpoint_rejects_expired_token(api_client, mock_oauth_validation, expired_oauth_token):
    """Test ADMIN endpoint rejects expired OAuth token"""
    response = api_client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {expired_oauth_token}"}
    )

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_user_endpoint_rejects_malformed_token(api_client, mock_oauth_validation):
    """Test USER endpoint rejects malformed token"""
    response = api_client.get(
        "/database/stats",
        headers={"Authorization": "Bearer malformed_token_here"}
    )

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_admin_endpoint_rejects_malformed_token(api_client, mock_oauth_validation):
    """Test ADMIN endpoint rejects malformed token"""
    response = api_client.get(
        "/admin/status",
        headers={"Authorization": "Bearer malformed_token_here"}
    )

    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_user_endpoint_rejects_missing_bearer_prefix(api_client, mock_oauth_validation, create_test_oauth_token):
    """Test USER endpoint rejects token without Bearer prefix"""
    token = create_test_oauth_token(user_id=100, role="contributor")

    response = api_client.get(
        "/database/stats",
        headers={"Authorization": token}  # Missing "Bearer " prefix
    )

    assert response.status_code in [401, 403]


# =============================================================================
# Cross-Role Access Tests
# =============================================================================

@pytest.mark.api
@pytest.mark.security
def test_admin_can_access_user_endpoints(api_client, mock_oauth_validation, auth_headers_admin):
    """Test admin users can access USER-level endpoints"""
    response = api_client.get("/database/stats", headers=auth_headers_admin)

    # Admin should be able to access user endpoints
    assert response.status_code in [200, 503]


@pytest.mark.api
@pytest.mark.security
def test_user_cannot_access_admin_endpoints(api_client, mock_oauth_validation, auth_headers_user):
    """Test regular users cannot access ADMIN endpoints"""
    # Test multiple admin endpoints
    admin_endpoints = [
        "/admin/status",
        "/admin/extraction/config",
        "/admin/embedding/config",
        "/rbac/roles"
    ]

    for endpoint in admin_endpoints:
        response = api_client.get(endpoint, headers=auth_headers_user)
        assert response.status_code == 403, f"Endpoint {endpoint} should return 403 for non-admin"
