"""
Job RBAC permission tests.

Tests for job management permissions based on role:
- read_only: view own jobs only
- contributor: view/cancel own jobs
- curator: view all user jobs, cancel own
- admin: view/cancel all user jobs, delete own
- platform_admin: full access including system jobs

Endpoints tested:
- GET /jobs - list jobs (filtered by permission)
- GET /jobs/{id} - get job (permission check)
- DELETE /jobs/{id} - cancel/delete job (permission check)
- POST /jobs/{id}/approve - approve job (permission check)
- DELETE /jobs - bulk delete (admin/platform_admin only)
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock


# ============================================================================
# Permission mocking fixtures
# ============================================================================

@pytest.fixture
def mock_job_permissions_admin(monkeypatch):
    """
    Mock JobPermissionContext to simulate admin permissions.

    Admin can bulk delete user jobs, but NOT system jobs.
    """
    class MockJobPermissionChecker:
        def can_access_job(self, user_id, action, job):
            # Admin can access all user jobs
            return not job.get('is_system_job') and not str(job.get('created_by', '')).startswith('system:')

        def get_job_list_filter(self, user_id):
            return {'exclude_system': True}

        def can_delete_in_bulk(self, user_id, include_system=False):
            # Admin can bulk delete user jobs, not system
            return not include_system

    class MockContext:
        def __enter__(self):
            return MockJobPermissionChecker()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "api.app.routes.jobs.JobPermissionContext",
        lambda: MockContext()
    )


@pytest.fixture
def mock_job_permissions_platform_admin(monkeypatch):
    """
    Mock JobPermissionContext to simulate platform_admin permissions.

    Platform admin has full access including system jobs.
    """
    class MockJobPermissionChecker:
        def can_access_job(self, user_id, action, job):
            return True  # Full access

        def get_job_list_filter(self, user_id):
            return {}  # No filter

        def can_delete_in_bulk(self, user_id, include_system=False):
            return True  # Full access

    class MockContext:
        def __enter__(self):
            return MockJobPermissionChecker()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "api.app.routes.jobs.JobPermissionContext",
        lambda: MockContext()
    )


@pytest.fixture
def mock_job_permissions_contributor(monkeypatch):
    """
    Mock JobPermissionContext to simulate contributor permissions.

    Contributor can only access own jobs, no bulk delete.
    """
    class MockJobPermissionChecker:
        def __init__(self):
            self.test_user_id = 100  # Default test user

        def can_access_job(self, user_id, action, job):
            # Only own jobs
            return job.get('user_id') == user_id

        def get_job_list_filter(self, user_id):
            return {'user_id': user_id}

        def can_delete_in_bulk(self, user_id, include_system=False):
            return False  # No bulk delete

    class MockContext:
        def __enter__(self):
            return MockJobPermissionChecker()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "api.app.routes.jobs.JobPermissionContext",
        lambda: MockContext()
    )


# ============================================================================
# Role-specific auth header fixtures
# ============================================================================

@pytest.fixture
def auth_headers_read_only(create_test_oauth_token):
    """Auth headers for read_only role."""
    token = create_test_oauth_token(user_id=100, role="read_only")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_contributor(create_test_oauth_token):
    """Auth headers for contributor role."""
    token = create_test_oauth_token(user_id=100, role="contributor")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_curator(create_test_oauth_token):
    """Auth headers for curator role."""
    token = create_test_oauth_token(user_id=102, role="curator")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(create_test_oauth_token):
    """Auth headers for admin role."""
    token = create_test_oauth_token(user_id=101, role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_platform_admin(create_test_oauth_token):
    """Auth headers for platform_admin role."""
    token = create_test_oauth_token(user_id=103, role="platform_admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_other_user(create_test_oauth_token):
    """Auth headers for a different contributor (user_id=200)."""
    token = create_test_oauth_token(user_id=200, username="otheruser", role="contributor")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Authentication requirement tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_jobs_list_requires_auth(api_client):
    """Test that GET /jobs returns 401 without authentication."""
    response = api_client.get("/jobs")
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_job_status_requires_auth(api_client):
    """Test that GET /jobs/{id} returns 401 without authentication."""
    response = api_client.get("/jobs/some-job-id")
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_job_cancel_requires_auth(api_client):
    """Test that DELETE /jobs/{id} returns 401 without authentication."""
    response = api_client.delete("/jobs/some-job-id")
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_job_approve_requires_auth(api_client):
    """Test that POST /jobs/{id}/approve returns 401 without authentication."""
    response = api_client.post("/jobs/some-job-id/approve")
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.security
def test_jobs_bulk_delete_requires_auth(api_client):
    """Test that DELETE /jobs returns 401 without authentication."""
    response = api_client.delete("/jobs?confirm=true")
    assert response.status_code == 401


# ============================================================================
# List jobs permission tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_contributor_can_list_jobs(api_client, mock_oauth_validation, auth_headers_contributor):
    """Test that contributor can list their jobs."""
    response = api_client.get("/jobs", headers=auth_headers_contributor)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.api
@pytest.mark.security
def test_curator_can_list_all_jobs(api_client, mock_oauth_validation, auth_headers_curator):
    """Test that curator can list all user jobs."""
    response = api_client.get("/jobs", headers=auth_headers_curator)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.api
@pytest.mark.security
def test_admin_can_list_all_jobs(api_client, mock_oauth_validation, auth_headers_admin):
    """Test that admin can list all user jobs."""
    response = api_client.get("/jobs", headers=auth_headers_admin)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ============================================================================
# Get job status permission tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_get_nonexistent_job_returns_404(api_client, mock_oauth_validation, auth_headers_contributor):
    """Test that getting non-existent job returns 404."""
    response = api_client.get("/jobs/nonexistent-job-id", headers=auth_headers_contributor)
    assert response.status_code == 404


# ============================================================================
# Cancel job permission tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_cancel_nonexistent_job_returns_404(api_client, mock_oauth_validation, auth_headers_contributor):
    """Test that canceling non-existent job returns 404."""
    response = api_client.delete("/jobs/nonexistent-job-id", headers=auth_headers_contributor)
    assert response.status_code == 404


# ============================================================================
# Delete job permission tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_delete_nonexistent_job_returns_404(api_client, mock_oauth_validation, auth_headers_admin):
    """Test that deleting non-existent job returns 404."""
    response = api_client.delete(
        "/jobs/nonexistent-job-id?purge=true",
        headers=auth_headers_admin
    )
    assert response.status_code == 404


# ============================================================================
# Bulk delete permission tests
# ============================================================================

@pytest.mark.api
@pytest.mark.security
def test_bulk_delete_requires_confirm(api_client, mock_oauth_validation, mock_job_permissions_admin, auth_headers_admin):
    """Test that bulk delete requires confirm=true."""
    response = api_client.delete("/jobs", headers=auth_headers_admin)
    assert response.status_code == 400
    assert "confirm=true" in response.json()["detail"].lower()


@pytest.mark.api
@pytest.mark.security
def test_bulk_delete_dry_run(api_client, mock_oauth_validation, mock_job_permissions_admin, auth_headers_admin):
    """Test that bulk delete with dry_run=true shows preview."""
    response = api_client.delete(
        "/jobs?dry_run=true",
        headers=auth_headers_admin
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("dry_run") is True
    assert "jobs_to_delete" in data


@pytest.mark.api
@pytest.mark.security
def test_contributor_cannot_bulk_delete(api_client, mock_oauth_validation, mock_job_permissions_contributor, auth_headers_contributor):
    """Test that contributor cannot perform bulk delete."""
    response = api_client.delete(
        "/jobs?confirm=true&status=completed",
        headers=auth_headers_contributor
    )
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_admin_can_bulk_delete_user_jobs(api_client, mock_oauth_validation, mock_job_permissions_admin, auth_headers_admin):
    """Test that admin can bulk delete user jobs (not system)."""
    response = api_client.delete(
        "/jobs?dry_run=true&status=completed",
        headers=auth_headers_admin
    )
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.security
def test_admin_cannot_bulk_delete_system_jobs(api_client, mock_oauth_validation, mock_job_permissions_admin, auth_headers_admin):
    """Test that admin cannot bulk delete system jobs."""
    response = api_client.delete(
        "/jobs?confirm=true&system=true",
        headers=auth_headers_admin
    )
    assert response.status_code == 403
    assert "system" in response.json()["detail"].lower()


@pytest.mark.api
@pytest.mark.security
def test_platform_admin_can_bulk_delete_system_jobs(api_client, mock_oauth_validation, mock_job_permissions_platform_admin, auth_headers_platform_admin):
    """Test that platform_admin can bulk delete system jobs."""
    response = api_client.delete(
        "/jobs?dry_run=true&system=true",
        headers=auth_headers_platform_admin
    )
    assert response.status_code == 200


# ============================================================================
# Integration tests (require actual job creation)
# ============================================================================
# These tests require full infrastructure (database, job queue, etc.)
# and are skipped in CI. Run with: pytest -m integration --run-integration

@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip(reason="Requires full infrastructure - run manually with --run-integration")
def test_create_and_view_own_job(api_client, mock_oauth_validation, auth_headers_contributor):
    """Test that user can create and view their own job."""
    # Create a job via text ingestion
    create_response = api_client.post(
        "/ingest/text",
        data={
            "text": "Test content for permission testing",
            "ontology": "test-permissions"
        },
        headers=auth_headers_contributor
    )

    # Job creation should succeed
    if create_response.status_code == 200:
        job_id = create_response.json()["job_id"]

        # Should be able to view own job
        status_response = api_client.get(
            f"/jobs/{job_id}",
            headers=auth_headers_contributor
        )
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == job_id


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip(reason="Requires full infrastructure - run manually with --run-integration")
def test_create_and_cancel_own_job(api_client, mock_oauth_validation, auth_headers_contributor):
    """Test that user can create and cancel their own job."""
    # Create a job
    create_response = api_client.post(
        "/ingest/text",
        data={
            "text": "Test content for cancel testing",
            "ontology": "test-cancel"
        },
        headers=auth_headers_contributor
    )

    if create_response.status_code == 200:
        job_id = create_response.json()["job_id"]

        # Should be able to cancel own job
        cancel_response = api_client.delete(
            f"/jobs/{job_id}",
            headers=auth_headers_contributor
        )
        # Either success (200) or conflict if job already processed (409)
        assert cancel_response.status_code in [200, 409]


# ============================================================================
# Unit tests for JobPermissionChecker
# ============================================================================

@pytest.mark.unit
def test_job_permission_checker_own_job():
    """Test JobPermissionChecker correctly identifies own jobs."""
    from api.app.lib.job_permissions import JobPermissionChecker

    # Create mock permission checker
    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            # Simulate: user has filter permission for own jobs
            if resource_context and resource_context.get('owner') == 'self':
                return True
            return False

    checker = JobPermissionChecker(MockPermissionChecker())

    # User 100 checking their own job
    own_job = {'user_id': 100, 'job_id': 'test-job'}
    assert checker.can_access_job(100, 'read', own_job) is True

    # User 100 checking someone else's job
    other_job = {'user_id': 200, 'job_id': 'other-job'}
    assert checker.can_access_job(100, 'read', other_job) is False


@pytest.mark.unit
def test_job_permission_checker_system_job():
    """Test JobPermissionChecker correctly identifies system jobs."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            # Only platform_admin (user 103) has system job access
            if resource_context and resource_context.get('is_system'):
                return user_id == 103
            return True  # Global access for non-system

    checker = JobPermissionChecker(MockPermissionChecker())

    system_job = {'is_system_job': True, 'created_by': 'system:scheduler'}

    # Regular user cannot access system job
    assert checker.can_access_job(100, 'read', system_job) is False

    # Platform admin can access system job
    assert checker.can_access_job(103, 'read', system_job) is True


@pytest.mark.unit
def test_job_permission_checker_created_by_system():
    """Test that created_by starting with 'system:' is detected as system job."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            if resource_context and resource_context.get('is_system'):
                return False  # No system access
            return True

    checker = JobPermissionChecker(MockPermissionChecker())

    # Job created by system:scheduler
    job = {'created_by': 'system:scheduler', 'user_id': None}
    assert checker.can_access_job(100, 'read', job) is False

    # Job created by user
    user_job = {'created_by': 'user:testuser', 'user_id': 100}
    assert checker.can_access_job(100, 'read', user_job) is True


@pytest.mark.unit
def test_job_list_filter_contributor():
    """Test get_job_list_filter returns user_id filter for contributors."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            # Contributor has no global read, only filter-scoped
            return False

    checker = JobPermissionChecker(MockPermissionChecker())

    filter_result = checker.get_job_list_filter(100)
    assert filter_result == {'user_id': 100}


@pytest.mark.unit
def test_job_list_filter_curator():
    """Test get_job_list_filter returns exclude_system for curators."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            # Curator has global read but not system
            if resource_context and resource_context.get('is_system'):
                return False
            return True  # Global read

    checker = JobPermissionChecker(MockPermissionChecker())

    filter_result = checker.get_job_list_filter(102)
    assert filter_result == {'exclude_system': True}


@pytest.mark.unit
def test_job_list_filter_platform_admin():
    """Test get_job_list_filter returns empty filter for platform_admin."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            # Platform admin has all access
            return True

    checker = JobPermissionChecker(MockPermissionChecker())

    filter_result = checker.get_job_list_filter(103)
    assert filter_result == {}  # No filter - can see everything


@pytest.mark.unit
def test_can_delete_in_bulk_admin():
    """Test can_delete_in_bulk for admin (user jobs only)."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            if action != 'delete':
                return True
            # Admin has global delete but not system
            if resource_context and resource_context.get('is_system'):
                return False
            return True

    checker = JobPermissionChecker(MockPermissionChecker())

    # Admin can bulk delete user jobs
    assert checker.can_delete_in_bulk(101, include_system=False) is True

    # Admin cannot bulk delete system jobs
    assert checker.can_delete_in_bulk(101, include_system=True) is False


@pytest.mark.unit
def test_can_delete_in_bulk_platform_admin():
    """Test can_delete_in_bulk for platform_admin (all jobs)."""
    from api.app.lib.job_permissions import JobPermissionChecker

    class MockPermissionChecker:
        def can_user(self, user_id, action, resource_type, resource_id=None, resource_context=None):
            return True  # Full access

    checker = JobPermissionChecker(MockPermissionChecker())

    # Platform admin can bulk delete everything
    assert checker.can_delete_in_bulk(103, include_system=False) is True
    assert checker.can_delete_in_bulk(103, include_system=True) is True
