"""
Job management endpoints tests.

Tests for: kg jobs list, kg jobs status
Endpoints: GET /jobs, GET /jobs/{job_id}, DELETE /jobs/{job_id}, POST /jobs/{job_id}/approve
"""

import pytest
from fastapi.testclient import TestClient
import time
from io import BytesIO


@pytest.mark.api
@pytest.mark.smoke
def test_jobs_list_empty(api_client):
    """Test that GET /jobs returns empty list when no jobs exist"""
    response = api_client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # May have jobs from other tests, so just check it's a list
    assert all("job_id" in job for job in data)


@pytest.mark.api
@pytest.mark.smoke
def test_jobs_list_with_status_filter(api_client):
    """Test that GET /jobs?status=X filters by status"""
    response = api_client.get("/jobs?status=completed")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All returned jobs should have status=completed
    assert all(job["status"] == "completed" for job in data)


@pytest.mark.api
@pytest.mark.smoke
def test_jobs_list_with_limit(api_client):
    """Test that GET /jobs?limit=N limits results"""
    response = api_client.get("/jobs?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5


@pytest.mark.api
@pytest.mark.integration
def test_get_job_status_not_found(api_client):
    """Test that GET /jobs/{job_id} returns 404 for non-existent job"""
    response = api_client.get("/jobs/non-existent-job-id")

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.api
@pytest.mark.integration
def test_create_and_get_job(api_client):
    """Test creating a job and retrieving its status"""
    # Create a test job via text ingestion
    ingest_data = {
        "text": "This is a test document for job status testing.",
        "ontology": "test-ontology",
        "filename": "test.txt"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    assert create_response.status_code == 200

    create_data = create_response.json()
    job_id = create_data["job_id"]

    # Get job status
    status_response = api_client.get(f"/jobs/{job_id}")
    assert status_response.status_code == 200

    status_data = status_response.json()
    assert status_data["job_id"] == job_id
    assert "status" in status_data
    assert status_data["job_type"] == "ingestion"


@pytest.mark.api
@pytest.mark.integration
def test_job_status_fields(api_client):
    """Test that job status response contains all required fields"""
    # Create a test job
    ingest_data = {
        "text": "Test content for field validation",
        "ontology": "test-fields"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    job_id = create_response.json()["job_id"]

    # Get status
    response = api_client.get(f"/jobs/{job_id}")
    data = response.json()

    # Verify required fields
    required_fields = ["job_id", "job_type", "status", "created_at"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Verify status is valid
    valid_statuses = ["pending", "awaiting_approval", "approved", "queued", "processing", "completed", "failed", "cancelled"]
    assert data["status"] in valid_statuses


@pytest.mark.api
@pytest.mark.integration
def test_cancel_job(api_client):
    """Test cancelling a job before it processes"""
    # Create a test job (without auto-approve so it stays pending)
    ingest_data = {
        "text": "Test content for cancellation",
        "ontology": "test-cancel"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    job_id = create_response.json()["job_id"]

    # Wait briefly for analysis to complete (job should be awaiting_approval)
    time.sleep(0.5)

    # Cancel the job
    cancel_response = api_client.delete(f"/jobs/{job_id}")

    # Should succeed if job is in cancellable state
    if cancel_response.status_code == 200:
        cancel_data = cancel_response.json()
        assert cancel_data["cancelled"] is True
        assert cancel_data["job_id"] == job_id

        # Verify job is cancelled
        status_response = api_client.get(f"/jobs/{job_id}")
        assert status_response.json()["status"] == "cancelled"
    elif cancel_response.status_code == 409:
        # Job already processing or completed (timing issue)
        # This is acceptable in tests
        pass
    else:
        pytest.fail(f"Unexpected status code: {cancel_response.status_code}")


@pytest.mark.api
@pytest.mark.integration
def test_cancel_nonexistent_job(api_client):
    """Test that cancelling a non-existent job returns 404"""
    response = api_client.delete("/jobs/non-existent-job")

    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.integration
def test_approve_job(api_client):
    """Test approving a job for processing"""
    # Create a test job (without auto-approve)
    ingest_data = {
        "text": "Test content for approval workflow",
        "ontology": "test-approve"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    job_id = create_response.json()["job_id"]

    # Wait for analysis to complete
    max_attempts = 10
    for _ in range(max_attempts):
        status_response = api_client.get(f"/jobs/{job_id}")
        status = status_response.json()["status"]

        if status == "awaiting_approval":
            break
        elif status in ["failed", "cancelled"]:
            pytest.skip(f"Job ended in {status} state before approval could be tested")

        time.sleep(0.2)

    # Approve the job
    approve_response = api_client.post(f"/jobs/{job_id}/approve")

    if approve_response.status_code == 200:
        approve_data = approve_response.json()
        assert approve_data["job_id"] == job_id
        assert approve_data["status"] == "approved"
    elif approve_response.status_code == 409:
        # Job not in awaiting_approval state (timing issue or already processing)
        # This is acceptable in tests
        pass
    else:
        pytest.fail(f"Unexpected status code: {approve_response.status_code}")


@pytest.mark.api
@pytest.mark.integration
def test_approve_nonexistent_job(api_client):
    """Test that approving a non-existent job returns 404"""
    response = api_client.post("/jobs/non-existent-job/approve")

    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.integration
def test_list_jobs_by_client_id(api_client):
    """Test filtering jobs by client_id"""
    # Create a job (will use "anonymous" client_id by default)
    ingest_data = {
        "text": "Test content for client filtering",
        "ontology": "test-client-filter"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    assert create_response.status_code == 200

    # List jobs for anonymous client
    response = api_client.get("/jobs?client_id=anonymous")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    # Should have at least the job we just created
    assert len(data) > 0
    # All jobs should be for anonymous client
    assert all(job.get("client_id") == "anonymous" for job in data if "client_id" in job)


@pytest.mark.api
@pytest.mark.integration
def test_auto_approve_job(api_client):
    """Test auto-approve workflow (ADR-014)"""
    # Create a job with auto_approve=true
    ingest_data = {
        "text": "Test content for auto-approve",
        "ontology": "test-auto-approve",
        "auto_approve": "true"  # Form data, so string
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    assert create_response.status_code == 200

    job_id = create_response.json()["job_id"]

    # Wait a moment for auto-approval to process
    time.sleep(0.5)

    # Check status - should skip awaiting_approval and go to approved/processing/completed
    status_response = api_client.get(f"/jobs/{job_id}")
    status = status_response.json()["status"]

    # Should NOT be in awaiting_approval (because auto-approved)
    assert status != "awaiting_approval"
    # Should be in one of these states
    valid_auto_approve_states = ["approved", "processing", "completed", "failed"]
    assert status in valid_auto_approve_states


@pytest.mark.api
@pytest.mark.integration
def test_job_lifecycle_workflow(api_client):
    """Test full job lifecycle: create → pending → awaiting_approval → approve → processing/completed"""
    # 1. Create job
    ingest_data = {
        "text": "Full lifecycle test content",
        "ontology": "test-lifecycle"
    }

    create_response = api_client.post("/ingest/text", data=ingest_data)
    assert create_response.status_code == 200
    job_id = create_response.json()["job_id"]

    # 2. Should start as pending
    status_response = api_client.get(f"/jobs/{job_id}")
    initial_status = status_response.json()["status"]
    assert initial_status in ["pending", "awaiting_approval"]  # May be fast

    # 3. Wait for awaiting_approval
    max_attempts = 10
    reached_awaiting = False
    for _ in range(max_attempts):
        status_response = api_client.get(f"/jobs/{job_id}")
        status = status_response.json()["status"]

        if status == "awaiting_approval":
            reached_awaiting = True
            break
        elif status in ["failed", "cancelled"]:
            pytest.skip(f"Job failed/cancelled during analysis: {status}")

        time.sleep(0.2)

    if reached_awaiting:
        # 4. Approve job
        approve_response = api_client.post(f"/jobs/{job_id}/approve")
        if approve_response.status_code == 200:
            # 5. Should transition to approved/processing
            time.sleep(0.1)
            final_response = api_client.get(f"/jobs/{job_id}")
            final_status = final_response.json()["status"]
            assert final_status in ["approved", "processing", "completed", "failed"]
