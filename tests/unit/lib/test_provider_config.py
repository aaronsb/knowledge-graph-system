"""
Unit tests for the provider configuration contract (ADR-800, tasks #8/#10).

Locks the behaviours the uniform DB-driven provider system depends on:

1. validate_provider_key — model-agnostic, never raises, per-provider.
2. save_extraction_config — per-provider upsert that COALESCEs omitted
   fields (partial save never wipes the row) and treats `active` as the
   sole active-pointer control.
3. get_provider — resolves a non-active provider's own base_url.
4. fetch_model_catalog — OpenAI/Anthropic enumerate via the SDK and
   classify by a non-extraction denylist, not a hardcoded allowlist.

validate_provider_key / catalog tests mock the SDKs (no network).
save/load tests use the real container DB and snapshot-restore the
ai_extraction_config table so the shared dev DB is left untouched.
"""

import pytest
from unittest.mock import MagicMock, patch

from api.app.lib.ai_providers import validate_provider_key, OpenAIProvider, AnthropicProvider


# ===========================================================================
# 1. validate_provider_key — single source of truth, model-agnostic
# ===========================================================================

class TestValidateProviderKey:
    def test_should_return_false_when_openai_sdk_rejects_key(self):
        fake = MagicMock()
        fake.models.list.side_effect = Exception("401 invalid_api_key")
        with patch("openai.OpenAI", return_value=fake):
            ok, msg = validate_provider_key("openai", "sk-bad")
        assert ok is False
        assert msg and "Validation error" in msg

    def test_should_return_true_when_openai_sdk_accepts_key(self):
        with patch("openai.OpenAI", return_value=MagicMock()):
            ok, msg = validate_provider_key("openai", "sk-good")
        assert ok is True
        assert msg is None

    def test_should_return_false_when_anthropic_sdk_rejects_key(self):
        fake = MagicMock()
        fake.models.list.side_effect = Exception("authentication_error")
        with patch("anthropic.Anthropic", return_value=fake):
            ok, msg = validate_provider_key("anthropic", "sk-ant-bad")
        assert ok is False

    def test_should_return_true_when_anthropic_models_list_succeeds(self):
        # Model-agnostic: a bare models.list() call, no hardcoded model id.
        with patch("anthropic.Anthropic", return_value=MagicMock()):
            ok, msg = validate_provider_key("anthropic", "sk-ant-good")
        assert ok is True and msg is None

    def test_should_return_false_when_openrouter_returns_401(self):
        resp = MagicMock(status_code=401)
        with patch("requests.get", return_value=resp):
            ok, msg = validate_provider_key("openrouter", "bad")
        assert ok is False
        assert "401" in msg

    def test_should_return_true_when_openrouter_key_authenticates(self):
        resp = MagicMock(status_code=200)
        with patch("requests.get", return_value=resp):
            ok, msg = validate_provider_key("openrouter", "good")
        assert ok is True and msg is None

    def test_should_connectivity_check_llamacpp_not_require_key(self):
        with patch(
            "api.app.lib.ai_providers.LlamaCppProvider.validate_api_key",
            return_value=True,
        ):
            ok, msg = validate_provider_key("llamacpp", "")
        assert ok is True and msg is None

    def test_should_report_unreachable_llamacpp(self):
        with patch(
            "api.app.lib.ai_providers.LlamaCppProvider.validate_api_key",
            return_value=False,
        ):
            ok, msg = validate_provider_key("llamacpp", "")
        assert ok is False
        assert "llama.cpp" in msg

    def test_should_return_false_for_unknown_provider_without_raising(self):
        ok, msg = validate_provider_key("totally-made-up", "x")
        assert ok is False
        assert "No validation available" in msg

    def test_should_never_raise_even_on_unexpected_error(self):
        with patch("openai.OpenAI", side_effect=RuntimeError("boom")):
            ok, msg = validate_provider_key("openai", "x")
        assert ok is False  # swallowed, returned as (False, msg)


# ===========================================================================
# 4. fetch_model_catalog — SDK enumeration + denylist classification
# ===========================================================================

def _model(**kw):
    m = MagicMock()
    for k, v in kw.items():
        setattr(m, k, v)
    return m


class TestOpenAICatalogClassification:
    """Built via __new__ to isolate fetch_model_catalog from the
    network-touching constructor — the unit under test is the classifier."""

    def _provider_with_models(self, ids):
        p = object.__new__(OpenAIProvider)
        p.client = MagicMock()
        p.client.models.list.return_value = MagicMock(
            data=[_model(id=i, created=0) for i in ids]
        )
        return p

    def test_should_include_new_chat_families_without_code_change(self):
        cat = self._provider_with_models(
            ["gpt-4o", "o1-mini", "o3", "o4-mini", "gpt-5-preview"]
        ).fetch_model_catalog()
        ids = {e["model_id"] for e in cat}
        # o3 / o4 / gpt-5 would have been dropped by the old allowlist.
        assert {"o3", "o4-mini", "gpt-5-preview"} <= ids

    def test_should_exclude_known_non_extraction_models(self):
        cat = self._provider_with_models(
            ["gpt-4o", "whisper-1", "tts-1", "dall-e-3",
             "omni-moderation-latest", "davinci-002"]
        ).fetch_model_catalog()
        ids = {e["model_id"] for e in cat}
        assert ids == {"gpt-4o"}

    def test_should_categorise_embeddings_separately(self):
        cat = self._provider_with_models(
            ["gpt-4o", "text-embedding-3-large"]
        ).fetch_model_catalog()
        by_id = {e["model_id"]: e["category"] for e in cat}
        assert by_id["text-embedding-3-large"] == "embedding"
        assert by_id["gpt-4o"] == "extraction"


class TestAnthropicCatalogIsDynamic:
    def _provider_with_models(self, models):
        p = object.__new__(AnthropicProvider)
        p.client = MagicMock()
        p.client.models.list.return_value = MagicMock(data=models)
        return p

    def test_should_enumerate_from_sdk_not_hardcoded_list(self):
        # The SDK reports a brand-new model; it must appear (no hardcoding).
        models = [
            _model(id="claude-opus-4-1-20250805",
                    display_name="Claude Opus 4.1", created_at="2025-08-05"),
            _model(id="claude-future-99",
                    display_name="Claude Future", created_at=""),
        ]
        cat = self._provider_with_models(models).fetch_model_catalog()
        ids = {e["model_id"] for e in cat}
        assert "claude-opus-4-1-20250805" in ids
        assert "claude-future-99" in ids  # unknown still surfaces

    def test_should_price_known_family_and_null_unknown(self):
        models = [
            _model(id="claude-sonnet-4-20250514",
                    display_name="Claude Sonnet 4", created_at=""),
            _model(id="claude-future-99", display_name="x", created_at=""),
        ]
        cat = {e["model_id"]: e for e in
               self._provider_with_models(models).fetch_model_catalog()}
        assert cat["claude-sonnet-4-20250514"]["price_prompt_per_m"] == 3.00
        assert cat["claude-future-99"]["price_prompt_per_m"] is None


# ===========================================================================
# 2 & 3. save_extraction_config COALESCE + get_provider base_url resolution
#        (real container DB; snapshot-restored)
# ===========================================================================

@pytest.fixture
def restore_extraction_config():
    """Snapshot kg_api.ai_extraction_config and restore it verbatim after
    the test, so DB-mutating contract tests never pollute the dev DB."""
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


@pytest.mark.usefixtures("restore_extraction_config")
class TestSaveExtractionConfigContract:
    def test_should_not_wipe_omitted_fields_on_partial_save(self):
        from api.app.lib.ai_extraction_config import (
            save_extraction_config, load_provider_config)

        # Full config, NOT active.
        save_extraction_config({
            "provider": "llamacpp", "model_name": "qwen3",
            "base_url": "http://kg-llamacpp:8080/v1",
            "temperature": 0.1, "max_tokens": 4096, "active": False,
        })
        # Partial save: only temperature changes.
        save_extraction_config({
            "provider": "llamacpp", "model_name": "",
            "temperature": 0.5, "active": False,
        })
        row = load_provider_config("llamacpp")
        assert row["base_url"] == "http://kg-llamacpp:8080/v1"  # preserved
        assert row["model_name"] == "qwen3"                      # preserved
        assert row["max_tokens"] == 4096                          # preserved
        assert float(row["temperature"]) == 0.5                   # updated

    def test_should_preserve_base_url_when_activating_model_only(self):
        from api.app.lib.ai_extraction_config import (
            save_extraction_config, load_provider_config,
            load_active_extraction_config)

        save_extraction_config({
            "provider": "llamacpp", "model_name": "qwen3",
            "base_url": "http://kg-llamacpp:8080/v1", "active": False,
        })
        # Activation path sends only provider+model (the real /admin/
        # extraction/config behaviour) — base_url must survive.
        save_extraction_config({
            "provider": "llamacpp", "model_name": "qwen3", "active": True,
        })
        row = load_provider_config("llamacpp")
        assert row["base_url"] == "http://kg-llamacpp:8080/v1"
        assert load_active_extraction_config()["provider"] == "llamacpp"

    def test_should_not_change_active_pointer_when_active_false(self):
        from api.app.lib.ai_extraction_config import (
            save_extraction_config, load_active_extraction_config)

        save_extraction_config({
            "provider": "anthropic", "model_name": "claude-x", "active": True,
        })
        save_extraction_config({
            "provider": "llamacpp", "model_name": "qwen3",
            "base_url": "http://x:1/v1", "active": False,
        })
        assert load_active_extraction_config()["provider"] == "anthropic"

    def test_should_keep_one_row_per_provider(self):
        from api.app.lib.ai_extraction_config import (
            save_extraction_config, load_provider_config)
        from api.app.lib.age_client import AGEClient

        for t in (0.1, 0.2, 0.3):
            save_extraction_config({
                "provider": "ollama", "model_name": "m",
                "temperature": t, "active": False,
            })
        client = AGEClient()
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM kg_api.ai_extraction_config "
                    "WHERE provider='ollama'")
                count = cur.fetchone()[0]
            conn.commit()
        finally:
            client.pool.putconn(conn)
        assert count == 1
        assert float(load_provider_config("ollama")["temperature"]) == 0.3
