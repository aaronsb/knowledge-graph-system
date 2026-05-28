"""
Authorization regression tests for the ingestion entry points (ADR-400, #434).

POST /ingest, /ingest/text and /ingest/image depended only on CurrentUser and
never enforced the seeded ingest:create grant (contributor), despite docstrings
claiming it. Any authenticated principal — including read_only, or an
anonymous-then-self-registered account — could enqueue LLM-cost-bearing jobs
(denial-of-wallet). These tests lock in require_permission('ingest','create').

A permission denial fires in the dependency, before the handler body, so the
read_only/anonymous cases never enqueue a job — no ingestion side effects.
"""

import pytest

# Minimal valid bodies so the ONLY failure is the auth gate (not 422 form errors).
ENDPOINTS = [
    ("/ingest", {"file": ("t.txt", b"hello world")}, {"ontology": "testonto"}),
    ("/ingest/text", None, {"text": "hello world", "ontology": "testonto"}),
    ("/ingest/image", {"file": ("t.png", b"\x89PNG\r\n\x1a\n")}, {"ontology": "testonto"}),
]


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path,files,data", ENDPOINTS)
def test_ingest_rejects_anonymous(api_client, path, files, data):
    """No ingestion endpoint may be reached without authentication."""
    response = api_client.post(path, files=files, data=data)
    assert response.status_code in (401, 403), (
        f"anonymous POST {path} returned {response.status_code}"
    )


@pytest.mark.api
@pytest.mark.security
@pytest.mark.parametrize("path,files,data", ENDPOINTS)
def test_ingest_denied_for_read_only(
    api_client, mock_oauth_validation, ensure_test_users_in_db, auth_headers_readonly,
    path, files, data
):
    """
    read_only lacks ingest:create, so every ingestion entry point must reject it
    with 403 — closing the denial-of-wallet path for the lowest-privilege account.
    """
    response = api_client.post(path, files=files, data=data, headers=auth_headers_readonly)
    assert response.status_code == 403, (
        f"read_only POST {path} returned {response.status_code} — ingest:create not enforced"
    )
