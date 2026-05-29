"""
Regression tests for the two fully-unauthenticated endpoints (#437).

Both previously had NO auth dependency at all:
- GET /vocabulary/category-flows ran two full-graph scans for any anonymous
  caller (the only zero-dependency endpoint in the API). Now requires
  vocabulary:read.
- GET /ingest/image/health exposed GPU/VRAM/model/provider info anonymously.
  Now requires admin:status (admin + platform_admin) — it leaks infra detail.
"""

import pytest


@pytest.mark.api
@pytest.mark.security
def test_category_flows_rejects_anonymous(api_client):
    """The former only-anonymous endpoint now requires authentication."""
    assert api_client.get("/vocabulary/category-flows").status_code in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_image_health_rejects_anonymous(api_client):
    """The image-ingestion health/infra endpoint now requires authentication."""
    assert api_client.get("/ingest/image/health").status_code in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_image_health_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """
    /ingest/image/health leaks GPU/VRAM/provider detail, so it requires
    admin:status (admin/platform_admin). A read_only user is denied (403),
    before the health check runs.
    """
    assert api_client.get(
        "/ingest/image/health", headers=auth_headers_readonly
    ).status_code == 403
