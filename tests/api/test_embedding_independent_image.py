"""
Regression tests for ADR-803: the image embedding slot is an INDEPENDENT
same-modality index, not co-spatial with the text/prose space.

Migration 075 dropped chk_image_dimensions_match and the route/activate
dimension-match guards. A non-multimodal profile may now pair a text model and
an image model of DIFFERENT dimensions, with the image index carrying its own
vector_space. These tests lock that relaxation so the co-spatiality assumption
is not silently reintroduced.

Created profiles are inactive and cleaned up by id (no active-profile churn).
"""

import pytest


@pytest.fixture(autouse=True)
def allow_admin_permissions(monkeypatch):
    def always_admin(user, resource_type, action,
                     resource_id=None, resource_context=None):
        return user.role == "admin"
    monkeypatch.setattr(
        "api.app.dependencies.auth.check_permission", always_admin)


@pytest.fixture
def cleanup_profiles():
    """Delete any embedding profiles created during the test (by id)."""
    created: list[int] = []
    yield created
    from api.app.lib.embedding_config import delete_embedding_config
    for cid in created:
        try:
            delete_embedding_config(cid)
        except Exception:
            pass


class TestIndependentImageDimensions:
    def test_create_allows_mismatched_text_image_dims_and_image_vector_space(
            self, api_client, mock_oauth_validation, auth_headers_admin, cleanup_profiles):
        # text=768, image=1024 — previously rejected ("Dimension mismatch ...
        # must match for non-multimodal profiles"). ADR-803: now valid.
        resp = api_client.post(
            "/admin/embedding/config", headers=auth_headers_admin,
            json={
                "name": "adr803-independent-dims-test",
                "vector_space": "test-text-768",
                "multimodal": False,
                "text_provider": "local",
                "text_model_name": "test/text-768",
                "text_loader": "sentence-transformers",
                "text_dimensions": 768,
                "image_provider": "local",
                "image_model_name": "test/image-1024",
                "image_loader": "transformers",
                "image_dimensions": 1024,
                "image_vector_space": "test-image-1024",
            })
        assert resp.status_code == 200, resp.text
        config_id = resp.json()["config_id"]
        cleanup_profiles.append(config_id)

        # Round-trip: the independent image dims + image_vector_space persist.
        configs = api_client.get("/admin/embedding/configs",
                                 headers=auth_headers_admin).json()
        prof = next(c for c in configs if c["id"] == config_id)
        assert prof["text_dimensions"] == 768
        assert prof["image_dimensions"] == 1024          # independent of text
        assert prof["image_vector_space"] == "test-image-1024"
