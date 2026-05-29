"""
Authorization regression tests for the graph query surface (queries.py, #435).

Every /query/* handler depended only on CurrentUser despite docstrings claiming
graph:read — so any authenticated user (incl. read_only) could read concepts,
sources, provenance, and run raw Cypher (POST /query/cypher), and enqueue
auto-approved polarity compute jobs. This locks in:

- read/search/connect/polarity endpoints require graph:read
  (contributor + admin + platform_admin; excludes read_only)
- POST /query/cypher requires graph:execute (platform_admin only)

Gates are declared as route-level dependencies. Denials fire before the handler,
so no search/compute side effects occur in the denial tests.
"""

import pytest

CYPHER_BODY = {"query": "MATCH (n) RETURN n LIMIT 1"}


@pytest.mark.api
@pytest.mark.security
def test_query_rejects_anonymous(api_client):
    """Representative read + raw-cypher endpoints reject anonymous callers."""
    assert api_client.get("/query/concept/does-not-exist").status_code in (401, 403)
    assert api_client.post("/query/cypher", json=CYPHER_BODY).status_code in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_query_read_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """read_only lacks graph:read and is denied the concept read + raw cypher."""
    assert api_client.get(
        "/query/concept/does-not-exist", headers=auth_headers_readonly
    ).status_code == 403
    assert api_client.post(
        "/query/cypher", json=CYPHER_BODY, headers=auth_headers_readonly
    ).status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_query_read_allowed_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """admin holds graph:read (via 040) and passes the gate (404 for a fake id)."""
    response = api_client.get(
        "/query/concept/does-not-exist", headers=auth_headers_admin
    )
    assert response.status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_raw_cypher_denied_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """
    POST /query/cypher requires graph:execute, seeded to platform_admin only.
    A plain admin (graph:read but not execute) must be denied (403).
    """
    response = api_client.post(
        "/query/cypher", json=CYPHER_BODY, headers=auth_headers_admin
    )
    assert response.status_code == 403
