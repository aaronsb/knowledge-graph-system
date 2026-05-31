"""
Route + persistence tests for the vision provider config contract (ADR-802 / #378).

Locks the HTTP surface the vision capability slot depends on:

- GET  /vision/config           — effective provider/model (public)
- GET  /admin/vision/config     — active row + effective resolution
- POST /admin/vision/config     — set/activate, with vision-capable guard
- GET  /admin/vision/providers  — per-provider supports_vision metadata

DB-mutating tests snapshot-restore kg_api.ai_vision_config so the shared dev
DB is left untouched (mirrors test_providers_routes.py).
"""

import pytest


@pytest.fixture(autouse=True)
def allow_admin_permissions(monkeypatch):
    """Admin token passes RBAC; mirrors test_providers_routes.py."""
    def always_admin(user, resource_type, action,
                     resource_id=None, resource_context=None):
        return user.role == "admin"
    monkeypatch.setattr(
        "api.app.dependencies.auth.check_permission", always_admin)


@pytest.fixture
def restore_vision_config():
    """Snapshot/restore kg_api.ai_vision_config around a mutating test."""
    from api.app.lib.age_client import AGEClient
    client = AGEClient()
    conn = client.pool.getconn()
    cols = "provider, model_name, max_tokens, temperature, updated_by, active"
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {cols} FROM kg_api.ai_vision_config")
            snapshot = cur.fetchall()
        conn.commit()
        yield
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kg_api.ai_vision_config")
                if snapshot:
                    ph = "(" + ",".join(["%s"] * 6) + ")"
                    cur.execute(
                        f"INSERT INTO kg_api.ai_vision_config ({cols}) "
                        f"VALUES {','.join([ph] * len(snapshot))}",
                        [v for row in snapshot for v in row],
                    )
            conn.commit()
        finally:
            client.pool.putconn(conn)


class TestVisionProvidersMetadata:
    def test_should_require_authentication(self, api_client, mock_oauth_validation):
        assert api_client.get("/admin/vision/providers").status_code == 401

    def test_should_report_supports_vision_per_provider(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        resp = api_client.get("/admin/vision/providers", headers=auth_headers_admin)
        assert resp.status_code == 200
        providers = {p["provider"]: p for p in resp.json()["providers"]}
        # vllm is a placeholder with no connector — never surfaced.
        assert "vllm" not in providers
        # Every entry carries the data-driven capability flag + model list.
        for p in providers.values():
            assert isinstance(p["supports_vision"], bool)
            assert isinstance(p["vision_models"], list)


@pytest.mark.usefixtures("restore_vision_config")
class TestVisionConfigRoundTrip:
    def test_should_set_activate_and_reflect_in_effective(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        # Activate openai for vision with an explicit model (bypasses the
        # catalog guard so the test doesn't depend on catalog state).
        save = api_client.post(
            "/admin/vision/config", headers=auth_headers_admin,
            json={"provider": "openai", "model_name": "gpt-4o", "active": True})
        assert save.status_code == 200, save.text
        eff = save.json()["effective"]
        assert eff["provider"] == "openai"
        assert eff["source"] == "vision_config"

        got = api_client.get("/admin/vision/config", headers=auth_headers_admin).json()
        assert got["config"]["provider"] == "openai"
        assert got["config"]["model_name"] == "gpt-4o"
        assert got["config"]["active"] is True

    def test_partial_save_does_not_wipe_model(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        api_client.post("/admin/vision/config", headers=auth_headers_admin,
                        json={"provider": "openai", "model_name": "gpt-4o", "active": True})
        # Re-save without model_name (only temperature) — model must survive.
        api_client.post("/admin/vision/config", headers=auth_headers_admin,
                        json={"provider": "openai", "temperature": 0.2, "active": True})
        cfg = api_client.get("/admin/vision/config", headers=auth_headers_admin).json()["config"]
        assert cfg["model_name"] == "gpt-4o"
        assert cfg["temperature"] == 0.2

    def test_should_reject_unsupported_provider(
            self, api_client, mock_oauth_validation, auth_headers_admin):
        resp = api_client.post("/admin/vision/config", headers=auth_headers_admin,
                               json={"provider": "vllm", "model_name": "x"})
        assert resp.status_code == 400

    def test_should_reject_activation_without_vision_capable_model(
            self, api_client, mock_oauth_validation, auth_headers_admin, monkeypatch):
        # No explicit model + no catalog vision model → 400, not a silent
        # activation that fails loud at the first image.
        monkeypatch.setattr(
            "api.app.routes.vision._catalog_vision_model_ids", lambda p: [])
        resp = api_client.post("/admin/vision/config", headers=auth_headers_admin,
                               json={"provider": "ollama", "active": True})
        assert resp.status_code == 400
