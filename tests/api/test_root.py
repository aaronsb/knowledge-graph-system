"""
Root endpoint tests.

Tests for: API root
Endpoint: GET /
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
@pytest.mark.smoke
def test_root_endpoint_returns_200(api_client):
    """Test that / returns 200 OK"""
    response = api_client.get("/")

    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.smoke
def test_root_endpoint_returns_json(api_client):
    """Test that / returns JSON response"""
    response = api_client.get("/")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.api
@pytest.mark.smoke
def test_root_endpoint_has_status(api_client):
    """Test that / returns status field"""
    response = api_client.get("/")
    data = response.json()

    assert "status" in data


@pytest.mark.api
@pytest.mark.smoke
def test_root_endpoint_has_queue_info(api_client):
    """Test that / returns queue information"""
    response = api_client.get("/")
    data = response.json()

    # Should include queue stats
    assert "queue" in data
    assert "type" in data["queue"]

    # Check for job status counts
    queue = data["queue"]
    assert "pending" in queue or "queued" in queue or "processing" in queue


@pytest.mark.api
@pytest.mark.smoke
def test_root_endpoint_status_healthy(api_client):
    """Test that / reports healthy status"""
    response = api_client.get("/")
    data = response.json()

    assert data["status"] == "healthy"
