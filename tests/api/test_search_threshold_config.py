"""
Tests for the configurable default search similarity threshold (ADR-508).

Covers:
- admin GET/PUT of /admin/config/search-threshold (round-trips via platform_config)
- RBAC: setting requires search_config:write (admin), denied for read_only
- /query/search inherits the configured default when min_similarity is omitted,
  and an explicit min_similarity still overrides it
"""

import pytest

THRESHOLD_URL = "/admin/config/search-threshold"


def _restore_default(api_client, headers, value=0.6):
    api_client.put(THRESHOLD_URL, json={"threshold": value}, headers=headers)


@pytest.mark.api
def test_get_search_threshold_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """Admin can read the configured default threshold."""
    resp = api_client.get(THRESHOLD_URL, headers=auth_headers_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] == "search_default_similarity_threshold"
    assert "threshold" in body and "fallback" in body


@pytest.mark.api
def test_set_search_threshold_roundtrips(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """PUT updates the value; a subsequent GET reflects it."""
    try:
        resp = api_client.put(THRESHOLD_URL, json={"threshold": 0.55}, headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["threshold"] == 0.55

        got = api_client.get(THRESHOLD_URL, headers=auth_headers_admin).json()
        assert got["threshold"] == 0.55
    finally:
        _restore_default(api_client, auth_headers_admin)


@pytest.mark.api
def test_set_search_threshold_validates_range(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """Out-of-range thresholds are rejected by the request model (422)."""
    resp = api_client.put(THRESHOLD_URL, json={"threshold": 1.5}, headers=auth_headers_admin)
    assert resp.status_code == 422


@pytest.mark.api
@pytest.mark.security
def test_set_search_threshold_denied_for_readonly(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """Setting the threshold requires search_config:write; read_only is denied."""
    resp = api_client.put(THRESHOLD_URL, json={"threshold": 0.55}, headers=auth_headers_readonly)
    assert resp.status_code in (401, 403)


@pytest.mark.api
def test_search_inherits_configured_default(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """A search with no min_similarity uses the configured default; explicit overrides it."""
    try:
        api_client.put(THRESHOLD_URL, json={"threshold": 0.72}, headers=auth_headers_admin)

        inherited = api_client.post(
            "/query/search",
            json={"query": "application security", "limit": 3,
                  "include_grounding": False, "include_diversity": False},
            headers=auth_headers_admin,
        )
        assert inherited.status_code == 200
        assert inherited.json()["threshold_used"] == 0.72

        explicit = api_client.post(
            "/query/search",
            json={"query": "application security", "limit": 3, "min_similarity": 0.4,
                  "include_grounding": False, "include_diversity": False},
            headers=auth_headers_admin,
        )
        assert explicit.status_code == 200
        assert explicit.json()["threshold_used"] == 0.4
    finally:
        _restore_default(api_client, auth_headers_admin)
