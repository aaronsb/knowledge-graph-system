"""
Backup verify endpoint tests (ADR-102).

Endpoint: POST /admin/backup/verify — runs the offline oracle
(scripts/development/lint/lint_backup.py) server-side against an uploaded
kg-backup/2 object and returns its structured report. Read-only, no restore.
"""

import json
import pytest


def _valid_backup(concept_embedding=None):
    """A minimal kg-backup/2 object that passes the offline oracle.

    The single embedding profile declares @3; pass a 3-vector to stay valid or a
    wrong-length vector to trip the dimension check (E_CONCEPT_EMBEDDING_DIM).
    """
    concept = {"concept_id": "c1", "label": "A"}
    if concept_embedding is not None:
        concept["embedding"] = concept_embedding
    return {
        "header": {
            "format_version": "kg-backup/2",
            "source": {"platform": "kg", "version": "1.7.3"},
            "exported_at": "2026-06-01T00:00:00Z",
            "schema_version": 76,
            "embedding_profiles": [{"identity": "test:embed@3"}],
            "default_embedding_profile": 0,
            "relationship_vocabulary": [{"relationship_type": "IMPLIES"}],
            "epoch_kinds": [{"kind": "ingestion"}],
            "actors": ["system"],
            "content_types": ["text/plain"],
            "ontologies": [{"name": "Corpus", "default_embedding_profile": 0}],
        },
        "bulk": {
            "concepts": [concept],
            "sources": [{"source_id": "s1", "content_type": 0}],
            "instances": [{"instance_id": "i1", "source_id": "s1"}],
            "evidence": [{"concept_id": "c1", "instance_id": "i1"}],
            "relationships": [
                {"from": "c1", "to": "c1", "type": 0, "properties": {"learned_id": "s1"}}
            ],
            "vocabulary": [],
        },
    }


def _upload(api_client, headers, obj, filename="backup.json"):
    return api_client.post(
        "/admin/backup/verify",
        files={"file": (filename, json.dumps(obj).encode("utf-8"), "application/json")},
        headers=headers,
    )


@pytest.mark.api
def test_verify_valid_backup_ok(api_client, mock_oauth_validation, auth_headers_admin, bypass_permission_check):
    """A well-formed kg-backup/2 object verifies ok=True with no errors."""
    resp = _upload(api_client, auth_headers_admin, _valid_backup(concept_embedding=[0.1, 0.2, 0.3]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["format_version"] == "kg-backup/2"
    assert body["errors"] == []
    # statistics are best-effort (de-interned view) — present and counting the concept
    assert body.get("statistics", {}).get("concepts") == 1


@pytest.mark.api
def test_verify_surfaces_dimension_mismatch(api_client, mock_oauth_validation, auth_headers_admin, bypass_permission_check):
    """A concept whose vector length != its profile @dims is flagged (not restorable)."""
    resp = _upload(api_client, auth_headers_admin, _valid_backup(concept_embedding=[0.1, 0.2]))  # 2 != @3
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    codes = {e["code"] for e in body["errors"]}
    assert "E_CONCEPT_EMBEDDING_DIM" in codes


@pytest.mark.api
def test_verify_rejects_bad_extension(api_client, mock_oauth_validation, auth_headers_admin, bypass_permission_check):
    """Only .tar.gz / .json are accepted."""
    resp = api_client.post(
        "/admin/backup/verify",
        files={"file": ("backup.txt", b"not a backup", "text/plain")},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 400


@pytest.mark.api
def test_verify_rejects_invalid_json(api_client, mock_oauth_validation, auth_headers_admin, bypass_permission_check):
    """A .json file that isn't valid JSON returns 400."""
    resp = api_client.post(
        "/admin/backup/verify",
        files={"file": ("backup.json", b"{not json", "application/json")},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 400


@pytest.mark.api
def test_verify_refuses_legacy_format(api_client, mock_oauth_validation, auth_headers_admin, bypass_permission_check):
    """A lower-major (legacy) object is refused by the oracle (single-path, no upcast)."""
    resp = _upload(api_client, auth_headers_admin, {"header": {"format_version": "kg-backup/1"}, "bulk": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert any(e["code"] == "E_LOWER_MAJOR" for e in body["errors"])
