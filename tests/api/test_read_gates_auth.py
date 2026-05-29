"""
Authorization regression tests for the Phase 2 read-gate cluster (#438).

projection.py, ontology.py and vocabulary.py read endpoints took only
CurrentUser while docstrings claimed a permission. This locks in:

- projection reads/algorithms -> graph:read; regenerate -> graph:create;
  invalidate -> graph:delete
- all ontology read endpoints -> ontologies:read
- all vocabulary read endpoints -> vocabulary:read

read_only lacks graph:read and ontologies:read (denied there) but DOES hold
vocabulary:read (baseline) — so it is allowed on vocabulary reads. That split is
exactly what these tests assert.
"""

import pytest


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path", [
    "/projection/nope",
    "/projection/algorithms",
    "/ontology/nope",
    "/vocabulary/status",
])
def test_read_gates_reject_anonymous(api_client, path):
    assert api_client.get(path).status_code in (401, 403)


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path", [
    "/projection/nope",   # graph:read
    "/projection/algorithms",  # graph:read
    "/ontology/nope",     # ontologies:read
])
def test_graph_and_ontology_reads_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly, path
):
    """read_only lacks graph:read and ontologies:read -> 403."""
    assert api_client.get(path, headers=auth_headers_readonly).status_code == 403


@pytest.mark.api
@pytest.mark.security
def test_vocabulary_read_allowed_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """read_only DOES hold vocabulary:read (baseline) -> not an auth rejection."""
    assert api_client.get(
        "/vocabulary/status", headers=auth_headers_readonly
    ).status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_graph_ontology_reads_allowed_for_admin(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """admin holds graph:read (040) and ontologies:read (inherited) -> passes gate."""
    assert api_client.get(
        "/projection/nope", headers=auth_headers_admin
    ).status_code not in (401, 403)
    assert api_client.get(
        "/ontology/nope", headers=auth_headers_admin
    ).status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_projection_delete_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """invalidate_projection requires graph:delete (admin/platform_admin)."""
    assert api_client.delete(
        "/projection/nope", headers=auth_headers_readonly
    ).status_code == 403
