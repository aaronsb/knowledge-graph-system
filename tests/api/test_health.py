"""
Health endpoint tests.

Tests for: kg health
Endpoint: GET /health
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
@pytest.mark.smoke
def test_health_endpoint_returns_200(api_client):
    """Test that /health returns 200 OK"""
    response = api_client.get("/health")

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.smoke
def test_health_endpoint_returns_json(api_client):
    """Test that /health returns JSON response"""
    response = api_client.get("/health")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.api
@pytest.mark.smoke
def test_health_endpoint_has_status_field(api_client):
    """Test that /health response contains 'status' field"""
    response = api_client.get("/health")
    data = response.json()

    assert "status" in data
    assert isinstance(data["status"], str)


@pytest.mark.api
@pytest.mark.smoke
def test_health_endpoint_status_is_healthy(api_client):
    """Test that /health reports healthy status"""
    response = api_client.get("/health")
    data = response.json()

    # Must include status: healthy (may include additional fields like components)
    assert data["status"] == "healthy"
