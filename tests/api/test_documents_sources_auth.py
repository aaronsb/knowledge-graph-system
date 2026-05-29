"""
Authorization regression tests for the document/source content surface (#436).

documents.py and sources.py handlers depended only on get_current_active_user
with no permission check, so any authenticated user (incl. read_only) could pull
original document bytes, raw image bytes, internal storage keys, and graph
metadata. This locks in:

- sources.py reads + GET /documents/{id}/content require sources:read
  (contributor + inheritance; excludes read_only)
- documents.py metadata/search/linkage require graph:read
  (contributor/admin/platform_admin; excludes read_only)

Denials fire in the route dependency, before the handler, so no content is read.
"""

import pytest


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path", [
    "/sources/nope",
    "/sources/nope/document",
    "/sources/nope/image",
    "/documents/nope/content",
    "/documents",
])
def test_content_surface_rejects_anonymous(api_client, path):
    """Document/source reads must require authentication."""
    assert api_client.get(path).status_code in (401, 403)


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path", [
    "/sources/nope",            # sources:read
    "/documents/nope/content",  # sources:read
    "/documents",               # graph:read
])
def test_content_surface_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly, path
):
    """read_only lacks both sources:read and graph:read — denied (403)."""
    assert api_client.get(path, headers=auth_headers_readonly).status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_content_surface_allowed_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """
    admin holds sources:read (inherited from contributor) and graph:read (040),
    so it passes the gates — a missing id yields 404, not an auth rejection.
    """
    assert api_client.get(
        "/sources/nope", headers=auth_headers_admin
    ).status_code not in (401, 403)
    assert api_client.get(
        "/documents/nope/content", headers=auth_headers_admin
    ).status_code not in (401, 403)
