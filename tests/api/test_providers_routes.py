"""
Route tests for the provider configuration contract (ADR-800, task #10).

Locks the HTTP surface the uniform DB-driven provider UI depends on:

- GET  /admin/providers              — canonical card list, no hardcoding
- POST /admin/providers/{p}/config   — persist without activating
- GET  /admin/providers/{p}/config   — two-way source of truth round-trip
- GET  /admin/keys                   — AI key providers only (no garage,
                                       no local providers)

DB-mutating tests snapshot-restore kg_api.ai_extraction_config so the
shared dev DB is left untouched.
"""

import pytest

from api.app.constants import (
    EXTRACTION_PROVIDERS, API_KEY_PROVIDERS, LOCAL_PROVIDERS,
)


@pytest.fixture(autouse=True)
def allow_admin_permissions(monkeypatch):
    """Admin token passes RBAC; mirrors tests/api/test_endpoint_security.py."""
    def always_admin(user, resource_type, action,
                      resource_id=None, resource_context=None):
        return user.role == "admin"
    monkeypatch.setattr(
        "api.app.dependencies.auth.check_permission", always_admin)


@pytest.fixture
def restore_extraction_config():
    from api.app.lib.age_client import AGEClient
    client = AGEClient()
    conn = client.pool.getconn()
    cols = ("provider, model_name, supports_vision, supports_json_mode, "
            "max_tokens, updated_by, active, base_url, temperature, top_p, "
            "gpu_layers, num_threads, thinking_mode, max_concurrent_requests, "
            "max_retries")
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {cols} FROM kg_api.ai_extraction_config")
            snapshot = cur.fetchall()
        conn.commit()
        yield
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kg_api.ai_extraction_config")
                if snapshot:
                    ph = "(" + ",".join(["%s"] * 15) + ")"
                    cur.execute(
                        f"INSERT INTO kg_api.ai_extraction_config ({cols}) "
                        f"VALUES {','.join([ph] * len(snapshot))}",
                        [v for row in snapshot for v in row],
                    )
            conn.commit()
        finally:
            client.pool.putconn(conn)


# ===========================================================================
# GET /admin/providers — canonical, derived, never hardcoded
# ===========================================================================

class TestListProviders:
    def test_should_require_authentication(self, api_client,
                                           mock_oauth_validation):
        assert api_client.get("/admin/providers").status_code == 401

    def test_should_return_one_entry_per_supported_provider(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        resp = api_client.get("/admin/providers", headers=auth_headers_admin)
        assert resp.status_code == 200
        names = {p["provider"] for p in resp.json()["providers"]}
        # Exactly EXTRACTION_PROVIDERS minus the unimplemented placeholder.
        assert names == set(EXTRACTION_PROVIDERS) - {"vllm"}

    def test_should_flag_local_and_key_providers_correctly(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        by = {p["provider"]: p for p in api_client.get(
            "/admin/providers", headers=auth_headers_admin).json()["providers"]}
        assert by["llamacpp"]["is_local"] is True
        assert by["llamacpp"]["requires_key"] is False
        assert by["openai"]["requires_key"] is True
        assert by["openai"]["is_local"] is False
        for name, meta in by.items():
            assert meta["requires_key"] == (name in API_KEY_PROVIDERS)
            assert meta["is_local"] == (name in LOCAL_PROVIDERS)


# ===========================================================================
# /admin/providers/{p}/config — DB is a two-way source of truth
# ===========================================================================

@pytest.mark.usefixtures("restore_extraction_config")
class TestProviderConfigRoundTrip:
    def test_should_round_trip_saved_config(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        save = api_client.post(
            "/admin/providers/llamacpp/config",
            headers=auth_headers_admin,
            json={"base_url": "http://kg-llamacpp:8080/v1",
                  "model_name": "qwen3", "temperature": 0.2,
                  "max_tokens": 4096},
        )
        assert save.status_code == 200

        got = api_client.get("/admin/providers/llamacpp/config",
                             headers=auth_headers_admin)
        assert got.status_code == 200
        cfg = got.json()["config"]
        assert cfg["base_url"] == "http://kg-llamacpp:8080/v1"
        assert cfg["model_name"] == "qwen3"
        assert cfg["active"] is False  # saved, NOT activated

    def test_should_not_wipe_fields_on_partial_save_through_route(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        api_client.post(
            "/admin/providers/llamacpp/config", headers=auth_headers_admin,
            json={"base_url": "http://kg-llamacpp:8080/v1",
                  "model_name": "qwen3", "max_tokens": 4096})
        # Partial: only temperature.
        api_client.post(
            "/admin/providers/llamacpp/config", headers=auth_headers_admin,
            json={"temperature": 0.7})
        cfg = api_client.get("/admin/providers/llamacpp/config",
                             headers=auth_headers_admin).json()["config"]
        assert cfg["base_url"] == "http://kg-llamacpp:8080/v1"
        assert cfg["model_name"] == "qwen3"
        assert cfg["max_tokens"] == 4096
        assert float(cfg["temperature"]) == 0.7

    def test_should_return_null_config_for_unconfigured_provider(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        # Guarantee absence (restore_extraction_config snapshots it back).
        from api.app.lib.age_client import AGEClient
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kg_api.ai_extraction_config "
                            "WHERE provider='ollama'")
            conn.commit()
        finally:
            client.pool.putconn(conn)

        resp = api_client.get("/admin/providers/ollama/config",
                              headers=auth_headers_admin)
        assert resp.status_code == 200
        assert resp.json()["config"] is None

    def test_should_reject_malformed_provider_identifier(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        resp = api_client.get("/admin/providers/BAD!!/config",
                              headers=auth_headers_admin)
        assert resp.status_code == 400


# ===========================================================================
# GET /admin/keys — AI key providers only
# ===========================================================================

class TestListApiKeysScope:
    def test_should_exclude_garage_and_local_providers(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        resp = api_client.get("/admin/keys", headers=auth_headers_admin)
        assert resp.status_code == 200
        names = {k["provider"] for k in resp.json()}
        # garage is a storage bucket key, not a reasoning provider.
        assert "garage" not in names
        # local providers are connectivity-tested, not key-bearing.
        assert names.isdisjoint(set(LOCAL_PROVIDERS))
        # key-requiring AI providers are present.
        assert "openai" in names and "anthropic" in names
