"""Configured max_tokens reaches every provider, capped by the catalog (ADR-800).

Before this, extraction sent a hardcoded budget (OpenAI 4096, Anthropic 16384,
llama.cpp inherited OpenAI's) and the configured value reached only
OpenRouter. OpenAI now sends max_completion_tokens, which reasoning models
require and every chat model accepts.
@verified 859cc8e6f
"""
from unittest.mock import MagicMock, patch

import pytest

from api.app.lib import ai_providers
from api.app.lib.ai_providers import (
    AnthropicProvider,
    LlamaCppProvider,
    OpenAIProvider,
    _output_token_budget,
)


def _catalog_cap(cap):
    """Patch the catalog lookup to report `cap` as max_completion_tokens."""
    ai_providers._OUTPUT_CAP_CACHE.clear()
    cur = MagicMock()
    cur.fetchone.return_value = (cap,)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    client = MagicMock()
    client.pool.getconn.return_value = conn
    return patch.object(ai_providers, "_get_catalog_age_client", return_value=client)


@pytest.mark.unit
class TestOutputTokenBudget:
    def test_should_cap_at_catalog_limit(self):
        with _catalog_cap(128000):
            assert _output_token_budget("anthropic", "m", 200000) == 128000

    def test_should_keep_request_under_the_limit(self):
        with _catalog_cap(128000):
            assert _output_token_budget("anthropic", "m", 16384) == 16384

    def test_should_pass_through_when_catalog_has_no_limit(self):
        with _catalog_cap(None):
            assert _output_token_budget("openai", "m", 4096) == 4096

    def test_should_pass_through_when_catalog_lookup_fails(self):
        with patch.object(ai_providers, "_get_catalog_age_client", side_effect=RuntimeError):
            assert _output_token_budget("openai", "m", 4096) == 4096


def _openai(cls=OpenAIProvider, max_tokens=None):
    p = object.__new__(cls)
    p.extraction_model = "gpt-5"
    p.max_tokens = max_tokens
    p.client = MagicMock()
    p.client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"concepts": []}'))],
        usage=MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    return p


@pytest.mark.unit
class TestProvidersSendConfiguredBudget:
    def test_openai_should_send_configured_budget_as_max_completion_tokens(self):
        p = _openai(max_tokens=16384)
        with _catalog_cap(None):
            try:
                p.extract_concepts("text", "system")
            except Exception:
                pass  # response parsing is not under test
        kwargs = p.client.chat.completions.create.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 16384
        assert "max_tokens" not in kwargs

    def test_openai_should_default_to_4096_when_unconfigured(self):
        p = _openai(max_tokens=None)
        with _catalog_cap(None):
            try:
                p.extract_concepts("text", "system")
            except Exception:
                pass
        assert p.client.chat.completions.create.call_args.kwargs["max_completion_tokens"] == 4096

    def test_llamacpp_should_look_up_its_own_catalog_rows(self):
        assert LlamaCppProvider.CATALOG_PROVIDER == "llamacpp"
        assert OpenAIProvider.CATALOG_PROVIDER == "openai"

    def test_anthropic_should_send_configured_budget_capped_by_catalog(self):
        p = object.__new__(AnthropicProvider)
        p.extraction_model = "claude-sonnet-5"
        p.max_tokens = 200000
        p.client = MagicMock()
        with _catalog_cap(128000):
            try:
                p.extract_concepts("text", "system")
            except Exception:
                pass
        assert p.client.messages.create.call_args.kwargs["max_tokens"] == 128000


@pytest.mark.unit
class TestOpenAIKnownOutputLimits:
    @pytest.mark.parametrize("model_id,limit", [
        ("gpt-4o-mini", 16384),
        ("gpt-4-turbo-2024-04-09", 4096),
        ("gpt-4-1106-preview", 4096),
        ("gpt-4-0613", 8192),
        ("gpt-4.1-mini", 32768),
        ("o1-mini", 65536),
        ("o3-mini", 100000),
        ("gpt-5", 128000),
        ("some-new-model", None),
    ])
    def test_should_map_id_prefix_to_limit(self, model_id, limit):
        assert ai_providers._openai_max_output(model_id) == limit

    def test_should_cache_lookup_per_model(self):
        ai_providers._OUTPUT_CAP_CACHE.clear()
        with _catalog_cap(4096) as get_client:
            _output_token_budget("openai", "gpt-4-turbo", 16384)
            _output_token_budget("openai", "gpt-4-turbo", 16384)
        assert get_client.call_count == 1
        ai_providers._OUTPUT_CAP_CACHE.clear()
