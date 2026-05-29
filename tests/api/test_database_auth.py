"""
Authorization regression tests for the /database router (ADR-400, #433).

Every /database/* handler previously depended only on CurrentUser (auth, no
authZ), so any authenticated user — including a freshly self-registered
read_only/contributor — could run arbitrary Cypher (POST /database/query) and
read full-graph data, despite docstrings claiming database:read / database:execute.

This locks in the gating:
- reads (stats/info/counters) require database:read   (admin + platform_admin)
- query + counters/refresh require database:execute    (platform_admin only)
- /database/epoch stays authenticated-by-design (cache-invalidation poll for all
  authenticated clients), so it must remain reachable by a contributor.

Real RBAC runs here (no bypass) against the seeded grants from migration 028.
"""

import pytest

VALID_QUERY = {"query": "MATCH (n) RETURN n LIMIT 1"}


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("method,path,body", [
    ("get", "/database/stats", None),
    ("get", "/database/info", None),
    ("get", "/database/counters", None),
    ("post", "/database/counters/refresh", None),
    ("post", "/database/query", VALID_QUERY),
])
def test_database_rejects_anonymous(api_client, method, path, body):
    """No /database/* data/query endpoint may be reached without authentication."""
    fn = getattr(api_client, method)
    response = fn(path, json=body) if body is not None else fn(path)
    assert response.status_code in (401, 403), (
        f"anonymous {method.upper()} {path} returned {response.status_code}"
    )


@pytest.mark.api
@pytest.mark.security
def test_database_read_denied_for_contributor(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_user
):
    """A contributor lacks database:read and is denied the stats read."""
    response = api_client.get("/database/stats", headers=auth_headers_user)
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_database_read_allowed_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """An admin holds database:read and passes the auth gate on stats."""
    response = api_client.get("/database/stats", headers=auth_headers_admin)
    assert response.status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_raw_cypher_denied_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """
    Arbitrary Cypher requires database:execute, seeded to platform_admin only.
    A plain admin (database:read but not execute) must be denied (403).
    """
    response = api_client.post(
        "/database/query", json=VALID_QUERY, headers=auth_headers_admin
    )
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_counters_refresh_denied_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """The state-mutating counters refresh also requires database:execute."""
    response = api_client.post(
        "/database/counters/refresh", headers=auth_headers_admin
    )
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_epoch_allowed_for_contributor(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_user
):
    """
    /database/epoch is authenticated-by-design: a contributor (and any
    authenticated role) must still be able to poll it — it is NOT gated on
    database:read.
    """
    response = api_client.get("/database/epoch", headers=auth_headers_user)
    assert response.status_code not in (401, 403)
