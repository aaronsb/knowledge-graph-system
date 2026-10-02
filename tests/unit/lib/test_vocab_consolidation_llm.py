"""
Unit tests for the vocabulary-consolidation LLM path (#590).

- ``call_llm_sync`` must route Anthropic sampling params through
  ``_anthropic_sampling_kwargs`` (anthropic-sdk v1.0 removed ``temperature``
  from ``messages.create()``), the same contract every other Anthropic call
  site already honours.
- ``llm_evaluate_merge`` must mark a decision ``failed`` when no decision was
  made, so consolidation reports it as a failure rather than a rejection.

The provider SDK client is mocked — no network.
"""

import asyncio
from unittest.mock import MagicMock, patch

from api.app.lib.llm_utils import call_llm_sync
from api.app.lib.pruning_strategies import llm_evaluate_merge


def _anthropic_provider(model="claude-sonnet-5-5", text='{"ok": true}'):
    provider = MagicMock()
    provider.get_provider_name.return_value = "Anthropic"
    provider.extraction_model = model
    message = MagicMock()
    message.content = [MagicMock(text=f"  {text}  ")]
    provider.client.messages.create.return_value = message
    return provider


class TestCallLlmSyncAnthropic:
    def test_temperature_goes_via_extra_body_not_top_level(self):
        provider = _anthropic_provider()
        call_llm_sync(provider, prompt="p", temperature=0.3)
        kwargs = provider.client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs
        assert kwargs["extra_body"] == {"temperature": 0.3}

    def test_request_shape_and_stripped_text(self):
        provider = _anthropic_provider(text='{"should_merge": false}')
        result = call_llm_sync(provider, prompt="the prompt", system_msg="sys", max_tokens=300)
        kwargs = provider.client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-sonnet-5-5"
        assert kwargs["max_tokens"] == 300
        assert kwargs["system"] == "sys"
        assert kwargs["messages"] == [{"role": "user", "content": "the prompt"}]
        assert result == '{"should_merge": false}'

    def test_sampling_params_dropped_for_models_that_reject_them(self):
        provider = _anthropic_provider(model="claude-opus-4-7")
        call_llm_sync(provider, prompt="p", temperature=0.3)
        kwargs = provider.client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs
        assert "extra_body" not in kwargs

    def test_retries_without_sampling_params_when_model_rejects_them(self):
        from api.app.lib import ai_providers

        class Rejected(Exception):
            status_code = 400

        provider = _anthropic_provider(model="claude-test-rejects-sampling")
        message = provider.client.messages.create.return_value
        provider.client.messages.create.side_effect = [
            Rejected("`temperature` is deprecated for this model"),
            message,
        ]
        try:
            result = call_llm_sync(provider, prompt="p", temperature=0.3)
        finally:
            ai_providers._anthropic_no_sampling_models.discard("claude-test-rejects-sampling")
        retry = provider.client.messages.create.call_args_list[1].kwargs
        assert "extra_body" not in retry
        assert result == '{"ok": true}'


def _evaluate():
    return asyncio.run(llm_evaluate_merge(
        type1="DESCRIBES",
        type2="DESCRIBED_BY",
        type1_edge_count=3,
        type2_edge_count=2,
        similarity=0.91,
        ai_provider=MagicMock(),
    ))


class TestLlmEvaluateMergeFailure:
    def test_llm_call_error_is_failed_not_a_decision(self):
        with patch(
            "api.app.lib.pruning_strategies.call_llm_sync",
            side_effect=TypeError("Messages.create() got an unexpected keyword argument 'temperature'"),
        ):
            decision = _evaluate()
        assert decision.failed is True
        assert decision.should_merge is False
        assert "unexpected keyword argument 'temperature'" in decision.reasoning

    def test_unparseable_response_is_failed(self):
        with patch("api.app.lib.pruning_strategies.call_llm_sync", return_value="not json"):
            decision = _evaluate()
        assert decision.failed is True

    def test_real_rejection_is_not_failed(self):
        with patch(
            "api.app.lib.pruning_strategies.call_llm_sync",
            return_value='{"should_merge": false, "reasoning": "directional inverses"}',
        ):
            decision = _evaluate()
        assert decision.failed is False
        assert decision.should_merge is False
        assert decision.reasoning == "directional inverses"
