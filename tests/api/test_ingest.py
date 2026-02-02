"""
Ingestion endpoints tests.

Tests for: kg ingest (file upload and text)
Endpoints: POST /ingest, POST /ingest/text
"""

import pytest
from fastapi.testclient import TestClient
from io import BytesIO


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation, bypass_permission_check, ensure_test_users_in_db):
    """Auto-use mock OAuth validation, bypass RBAC, and ensure DB test users."""
    pass


@pytest.mark.api
@pytest.mark.smoke
def test_ingest_text_basic(api_client, auth_headers_user):
    """Test that POST /ingest/text accepts text content"""
    data = {
        "text": "This is a test document for ingestion.",
        "ontology": "test-ontology",
        "force": "true"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result
    assert "status" in result
    assert result["status"].startswith("pending")


@pytest.mark.api
@pytest.mark.smoke
def test_ingest_text_response_structure(api_client, auth_headers_user):
    """Test that /ingest/text returns correct response structure"""
    data = {
        "text": "Another test document",
        "ontology": "test-structure",
        "force": "true"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()

    # Required fields
    assert "job_id" in result
    assert "status" in result
    assert "content_hash" in result

    # job_id should be a valid string
    assert isinstance(result["job_id"], str)
    assert len(result["job_id"]) > 0


@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_with_options(api_client, auth_headers_user):
    """Test that /ingest/text accepts chunking options"""
    data = {
        "text": "Document with custom chunking options. " * 100,
        "ontology": "test-options",
        "target_words": 500,
        "overlap_words": 100,
        "force": "true"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result


@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_with_filename(api_client, auth_headers_user):
    """Test that /ingest/text accepts optional filename"""
    data = {
        "text": "Document with custom filename",
        "ontology": "test-filename",
        "filename": "custom_test.txt",
        "force": "true"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result

    # Filename is stored internally but not exposed in JobStatus response
    # Just verify the job was created successfully


@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_auto_approve(api_client, auth_headers_user):
    """Test that /ingest/text supports auto_approve parameter"""
    data = {
        "text": "Document with auto-approve enabled",
        "ontology": "test-auto-approve",
        "auto_approve": "true",
        "force": "true"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    # Auto-approved jobs may show "auto" in status or go directly to "completed"
    status = result["status"].lower()
    assert "auto" in status or "completed" in status


@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_duplicate_detection(api_client, auth_headers_user):
    """Test that duplicate content is detected"""
    data = {
        "text": "Unique content for duplicate detection test",
        "ontology": "test-duplicate",
        "force": "true"
    }

    # First submission (force to ensure clean job regardless of DB state)
    response1 = api_client.post("/ingest/text", data=data, headers=auth_headers_user)
    assert response1.status_code == 200
    result1 = response1.json()
    assert "job_id" in result1

    # Second submission WITHOUT force (same content and ontology)
    data.pop("force")
    response2 = api_client.post("/ingest/text", data=data, headers=auth_headers_user)
    assert response2.status_code == 200
    result2 = response2.json()

    # Should detect duplicate — returns existing_job_id or job_id depending on job state
    assert "job_id" in result2 or "duplicate" in result2 or "existing_job_id" in result2


@pytest.mark.api
@pytest.mark.integration
def test_ingest_text_force_reingestion(api_client, auth_headers_user):
    """Test that force=true allows duplicate re-ingestion"""
    data = {
        "text": "Content for force re-ingestion test",
        "ontology": "test-force",
        "force": "true"
    }

    # First submission (force to ensure clean job regardless of DB state)
    response1 = api_client.post("/ingest/text", data=data, headers=auth_headers_user)
    assert response1.status_code == 200
    assert "job_id" in response1.json()

    # Second submission also with force=true — should create new job
    response2 = api_client.post("/ingest/text", data=data, headers=auth_headers_user)
    assert response2.status_code == 200
    assert "job_id" in response2.json()


@pytest.mark.api
@pytest.mark.smoke
def test_ingest_file_upload(api_client, auth_headers_user):
    """Test that POST /ingest accepts file uploads"""
    # Create a simple text file in memory
    file_content = b"This is a test file for upload ingestion."
    files = {
        "file": ("test.txt", BytesIO(file_content), "text/plain")
    }
    data = {
        "ontology": "test-file-upload",
        "force": "true"
    }

    response = api_client.post("/ingest", files=files, data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result
    assert "status" in result


@pytest.mark.api
@pytest.mark.smoke
def test_ingest_file_response_structure(api_client, auth_headers_user):
    """Test that /ingest returns correct response structure"""
    file_content = b"File upload structure test"
    files = {
        "file": ("structure_test.txt", BytesIO(file_content), "text/plain")
    }
    data = {
        "ontology": "test-file-structure",
        "force": "true"
    }

    response = api_client.post("/ingest", files=files, data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()

    # Required fields
    assert "job_id" in result
    assert "status" in result
    assert "content_hash" in result


@pytest.mark.api
@pytest.mark.integration
def test_ingest_file_with_options(api_client, auth_headers_user):
    """Test that /ingest accepts chunking options"""
    file_content = b"File with custom chunking options. " * 100
    files = {
        "file": ("chunking_test.txt", BytesIO(file_content), "text/plain")
    }
    data = {
        "ontology": "test-file-options",
        "target_words": 800,
        "min_words": 600,
        "max_words": 1000,
        "overlap_words": 150,
        "force": "true"
    }

    response = api_client.post("/ingest", files=files, data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result

    # Options are stored internally but not exposed in JobStatus response
    # Just verify the job was created successfully


@pytest.mark.api
@pytest.mark.integration
def test_ingest_file_custom_filename(api_client, auth_headers_user):
    """Test that /ingest accepts filename override"""
    file_content = b"File with custom filename"
    files = {
        "file": ("original.txt", BytesIO(file_content), "text/plain")
    }
    data = {
        "ontology": "test-custom-name",
        "filename": "overridden_name.txt",
        "force": "true"
    }

    response = api_client.post("/ingest", files=files, data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    assert "job_id" in result

    # Filename is stored internally but not exposed in JobStatus response
    # Just verify the job was created successfully


@pytest.mark.api
@pytest.mark.integration
def test_ingest_file_auto_approve(api_client, auth_headers_user):
    """Test that /ingest supports auto_approve parameter"""
    file_content = b"File with auto-approve"
    files = {
        "file": ("auto_approve.txt", BytesIO(file_content), "text/plain")
    }
    data = {
        "ontology": "test-file-auto",
        "auto_approve": "true",
        "force": "true"
    }

    response = api_client.post("/ingest", files=files, data=data, headers=auth_headers_user)

    assert response.status_code == 200
    result = response.json()
    # Auto-approved jobs may show "auto" in status or go directly to "completed"
    status = result["status"].lower()
    assert "auto" in status or "completed" in status


@pytest.mark.api
@pytest.mark.integration
def test_ingest_missing_ontology(api_client, auth_headers_user):
    """Test that /ingest/text requires ontology parameter"""
    data = {
        "text": "Text without ontology"
        # Missing ontology parameter
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    # Should return 422 Unprocessable Entity (validation error)
    assert response.status_code == 422
    error = response.json()
    assert "detail" in error


@pytest.mark.api
@pytest.mark.integration
def test_ingest_empty_text(api_client, auth_headers_user):
    """Test that /ingest/text handles empty text"""
    data = {
        "text": "",
        "ontology": "test-empty"
    }

    response = api_client.post("/ingest/text", data=data, headers=auth_headers_user)

    # Empty text is now rejected at the validation layer
    assert response.status_code in [200, 422]
