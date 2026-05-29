"""
Authorization regression tests for the Phase 3 consistency fixes (#441).

F18 — POST /admin/workers/jobs/{id}/cancel previously checked only
workers:manage and cancelled ANY running job with no job-level authorization.
It now also runs JobPermissionChecker.can_access_job, the SAME check DELETE
/jobs/{id} uses — defense-in-depth aligning the two cancel paths on one authz
function. (Correction to the audit: admin/platform_admin hold a *global*
jobs:cancel grant per migration 041, so they can cancel system jobs on BOTH
paths by design — there was no real inconsistency. The value here is that a
future workers:manage-only role would now be correctly job-gated.)

F19 — admin held oauth_clients read/create/delete but not write (migration 028
oversight), locking it out of PATCH/rotate/delete-token. Migration 072 seeds
admin oauth_clients:write so admin's client management is consistent.
"""

import pytest

SYS_JOB = "test-441-system-job"
USER_JOB = "test-441-user-job"


@pytest.fixture
def phase3_jobs():
    """Insert one system-lane and one user running job; clean up afterward."""
    from api.app.dependencies.auth import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kg_api.jobs (job_id, job_type, status, job_data, user_id, is_system_job)
                VALUES (%s, 'restore', 'running', '{}'::jsonb, 1000, TRUE),
                       (%s, 'ingestion', 'running', '{}'::jsonb, 100, FALSE)
                ON CONFLICT (job_id) DO NOTHING
                """,
                (SYS_JOB, USER_JOB),
            )
            conn.commit()
        yield SYS_JOB, USER_JOB
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_api.jobs WHERE job_id IN (%s, %s)", (SYS_JOB, USER_JOB))
            conn.commit()
        conn.close()


# --- F18: worker-plane cancel respects system-job scoping ---

@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("which", ["system", "user"])
def test_admin_can_cancel_any_job_via_worker_plane(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin, phase3_jobs, which
):
    """
    admin holds a global jobs:cancel grant (041), so can_access_job passes for
    BOTH system-lane and user jobs — intended per the seeded model. The cancel
    now routes through can_access_job (same as DELETE /jobs), so this also
    confirms the alignment doesn't break admin's legitimate access.
    """
    sys_id, user_job = phase3_jobs
    job_id = sys_id if which == "system" else user_job
    response = api_client.post(f"/admin/workers/jobs/{job_id}/cancel", headers=auth_headers_admin)
    assert response.status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_read_only_denied_worker_cancel(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly, phase3_jobs
):
    """read_only lacks workers:manage entirely — denied at the worker-plane gate."""
    sys_id, _ = phase3_jobs
    response = api_client.post(f"/admin/workers/jobs/{sys_id}/cancel", headers=auth_headers_readonly)
    assert response.status_code == 403


# --- F19: admin can now manage OAuth clients (oauth_clients:write) ---

@pytest.mark.api
@pytest.mark.security
def test_admin_can_modify_oauth_client(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_admin
):
    """After migration 072, admin holds oauth_clients:write — PATCH passes the gate (404 for a missing client)."""
    response = api_client.patch(
        "/auth/oauth/clients/does-not-exist", json={}, headers=auth_headers_admin
    )
    assert response.status_code not in (401, 403)


@pytest.mark.api
@pytest.mark.security
def test_read_only_cannot_modify_oauth_client(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly
):
    """read_only holds no oauth_clients grant — denied (403)."""
    response = api_client.patch(
        "/auth/oauth/clients/does-not-exist", json={}, headers=auth_headers_readonly
    )
    assert response.status_code == 403
