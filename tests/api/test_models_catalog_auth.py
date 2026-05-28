"""
Authorization regression tests for the model-catalog router (ADR-400, #432).

The entire /admin/models/catalog router was historically wired with no auth
dependency at all — anonymous callers could read the catalog, trigger outbound
provider fetches, toggle model availability, and overwrite pricing that feeds
ingest cost-estimation. These tests lock in the fix:

- reads require extraction_config:read  (admin + platform_admin)
- every mutation requires extraction_config:write  (platform_admin only)

Real RBAC runs here (no bypass_permission_check) against the seeded grants from
migration 028, with mock OAuth users from the conftest fixtures.
"""

import pytest


MUTATIONS = [
    ("post", "/admin/models/catalog/refresh", {"provider": "openai"}),
    ("put", "/admin/models/catalog/999999/enable", None),
    ("put", "/admin/models/catalog/999999/disable", None),
    ("put", "/admin/models/catalog/999999/default", None),
    ("put", "/admin/models/catalog/999999/price", {"price_prompt_per_m": 1.0}),
]


def _call(api_client, method, path, body, headers=None):
    fn = getattr(api_client, method)
    if body is None:
        return fn(path, headers=headers)
    return fn(path, json=body, headers=headers)


@pytest.mark.api
@pytest.mark.security
def test_catalog_read_rejects_anonymous(api_client):
    """GET /admin/models/catalog must require authentication (was fully open)."""
    response = api_client.get("/admin/models/catalog")
    assert response.status_code in (401, 403), (
        f"anonymous catalog read returned {response.status_code} — router is not gated"
    )


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("method,path,body", MUTATIONS)
def test_catalog_mutations_reject_anonymous(api_client, method, path, body):
    """Every catalog mutation must reject unauthenticated callers."""
    response = _call(api_client, method, path, body)
    assert response.status_code in (401, 403), (
        f"anonymous {method.upper()} {path} returned {response.status_code} — not gated"
    )


@pytest.mark.api
@pytest.mark.security
def test_catalog_read_denied_for_contributor(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_user
):
    """A contributor lacks extraction_config:read and must be denied (403)."""
    response = api_client.get("/admin/models/catalog", headers=auth_headers_user)
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_catalog_read_allowed_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """An admin holds extraction_config:read and must pass the auth gate."""
    response = api_client.get("/admin/models/catalog", headers=auth_headers_admin)
    # Auth must succeed; the handler may return 200 or a 5xx depending on catalog
    # state, but never an auth rejection.
    assert response.status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_catalog_mutation_denied_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """
    Mutations require extraction_config:write, seeded to platform_admin only.
    A plain admin must be denied (403) even though it can read.
    """
    response = api_client.put(
        "/admin/models/catalog/999999/enable", headers=auth_headers_admin
    )
    assert response.status_code == 403
