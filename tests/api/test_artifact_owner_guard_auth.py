"""
Regression tests for the #439 fixes:

1. NULL-owner artifact bypass — DELETE/regenerate guarded with
   `if owner_id is not None and owner_id != user_id` skipped the check entirely
   for system-owned artifacts (owner_id IS NULL), letting any authenticated user
   delete/regenerate them. Now non-admins are denied on NULL-owner artifacts.
2. get_current_user -> get_current_active_user across artifacts/programs/grants
   (disabled-account bypass). The disabled-rejection behavior of
   get_current_active_user is unit-tested in test_auth_dependencies.py; here we
   confirm these endpoints still require authentication after the swap.
"""

import pytest


@pytest.fixture
def system_artifact_id():
    """Insert a system-owned (owner_id IS NULL) artifact; yield id; clean up."""
    from api.app.dependencies.auth import get_db_connection

    conn = get_db_connection()
    artifact_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kg_api.artifacts
                    (artifact_type, representation, owner_id, graph_epoch, parameters, inline_result)
                VALUES ('query_result', 'api_direct', NULL, 0, '{}'::jsonb, '{}'::jsonb)
                RETURNING id
                """
            )
            artifact_id = cur.fetchone()[0]
            conn.commit()
        yield artifact_id
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_api.artifacts WHERE id = %s", (artifact_id,))
            conn.commit()
        conn.close()


@pytest.mark.api
@pytest.mark.security
def test_delete_system_artifact_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly,
    system_artifact_id,
):
    """A non-admin must NOT be able to delete a system-owned (NULL-owner) artifact."""
    response = api_client.delete(
        f"/artifacts/{system_artifact_id}", headers=auth_headers_readonly
    )
    assert response.status_code == 403, (
        f"read_only could reach DELETE on a NULL-owner artifact ({response.status_code})"
    )


@pytest.mark.api
@pytest.mark.security
def test_regenerate_system_artifact_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly,
    system_artifact_id,
):
    """Likewise for regenerate on a system-owned artifact."""
    response = api_client.post(
        f"/artifacts/{system_artifact_id}/regenerate", headers=auth_headers_readonly
    )
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("method,path", [
    ("delete", "/artifacts/1"),
    ("post", "/artifacts/1/regenerate"),
    ("post", "/programs"),
    ("get", "/groups"),
])
def test_swapped_endpoints_still_require_auth(api_client, method, path):
    """After the get_current_active_user swap, these endpoints still reject anonymous."""
    fn = getattr(api_client, method)
    assert fn(path).status_code in (401, 403)
