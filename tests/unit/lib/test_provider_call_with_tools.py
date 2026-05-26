"""
Unit tests for the provider-neutral `call_with_tools` facade.

Covers OpenAI, Anthropic, OpenRouter, Ollama, LlamaCpp, and LocalEmbeddingProvider.
Each provider's SDK client is mocked — no live API calls.
"""

import json
import pytest
from unittest.mock import MagicMock

from api.app.lib.ai_providers import (
    AIProvider,
    AnthropicProvider,
    LlamaCppProvider,
    LocalEmbeddingProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    ToolCallResponse,
    ToolSchema,
    TokenUsage,
)


SAMPLE_TOOL = ToolSchema(
    name="record_decision",
    description="Record an annealing decision verb.",
    params_schema={
        "type": "object",
        "properties": {
            "verb": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["verb", "reason"],
    },
)


def _bare_openai_provider() -> OpenAIProvider:
    p = object.__new__(OpenAIProvider)
    p.client = MagicMock()
    p._extraction_model_cache = "gpt-4o-mini"
    p._extraction_model_override = None
    p.embedding_model = "text-embedding-3-small"
    p.embedding_provider = None
    return p


def _bare_openrouter_provider() -> OpenRouterProvider:
    p = object.__new__(OpenRouterProvider)
    p.client = MagicMock()
    p.api_key = "sk-or-test"
    p.extraction_model = "openai/gpt-4o-mini"
    p.max_tokens = 4096
    p.embedding_provider = None
    return p


def _bare_anthropic_provider() -> AnthropicProvider:
    p = object.__new__(AnthropicProvider)
    p.client = MagicMock()
    p.api_key = "sk-ant-test"
    p.extraction_model = "claude-sonnet-4-20250514"
    p.embedding_provider = None
    return p


def _bare_ollama_provider() -> OllamaProvider:
    p = object.__new__(OllamaProvider)
    p.base_url = "http://localhost:11434"
    p.extraction_model = "mistral:7b-instruct"
    p.temperature = 0.1
    p.top_p = 0.9
    p.thinking_mode = "off"
    p.session = MagicMock()
    p.embedding_provider = None
    return p


def _bare_llamacpp_provider() -> LlamaCppProvider:
    p = object.__new__(LlamaCppProvider)
    p.client = MagicMock()
    p.api_key = "llama.cpp-local"
    p.base_url = "http://localhost:8080/v1"
    p._extraction_model_cache = "test-model"
    p._extraction_model_override = None
    p.extraction_model = "test-model"
    p.embedding_model = ""
    p.embedding_provider = None
    p.max_tokens = None
    p.temperature = 0.1
    return p


def _openai_response(tool_name: str, arguments: dict, finish_reason: str = "tool_calls",
                     prompt_tokens: int = 10, completion_tokens: int = 5):
    tc = MagicMock()
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(arguments)
    message = MagicMock()
    message.tool_calls = [tc]
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


def _openai_response_no_tool(finish_reason: str = "stop"):
    message = MagicMock()
    message.tool_calls = []
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 8
    response.usage.completion_tokens = 0
    return response


def _anthropic_response(tool_name: str, params: dict, stop_reason: str = "tool_use",
                       input_tokens: int = 12, output_tokens: int = 7):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = params
    message = MagicMock()
    message.content = [block]
    message.stop_reason = stop_reason
    message.usage.input_tokens = input_tokens
    message.usage.output_tokens = output_tokens
    message.usage.cache_read_input_tokens = 0
    return message


def _anthropic_response_no_tool(stop_reason: str = "end_turn"):
    text_block = MagicMock()
    text_block.type = "text"
    message = MagicMock()
    message.content = [text_block]
    message.stop_reason = stop_reason
    message.usage.input_tokens = 5
    message.usage.output_tokens = 5
    message.usage.cache_read_input_tokens = 0
    return message


def _ollama_response(tool_name: str, arguments, prompt_eval: int = 6, eval_count: int = 4):
    """`arguments` may be a dict (newer Ollama) or a JSON string (older)."""
    return {
        "message": {
            "tool_calls": [
                {"function": {"name": tool_name, "arguments": arguments}}
            ]
        },
        "prompt_eval_count": prompt_eval,
        "eval_count": eval_count,
    }


def _ollama_response_no_tool():
    return {
        "message": {"content": "I cannot call that tool.", "tool_calls": []},
        "prompt_eval_count": 6,
        "eval_count": 4,
    }


@pytest.mark.unit
class TestOpenAI:
    def test_returns_parsed_tool_call(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "MERGE", "reason": "siblings overlap"}
        )

        result = provider.call_with_tools(
            system_prompt="sys", user_prompt="usr", tools=[SAMPLE_TOOL]
        )

        assert isinstance(result, ToolCallResponse)
        assert result.tool_name == "record_decision"
        assert result.params == {"verb": "MERGE", "reason": "siblings overlap"}
        assert result.stop_reason == "tool_use"
        assert result.tokens == TokenUsage(input_tokens=10, output_tokens=5, cached_input_tokens=0)

    def test_tool_choice_translations(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "NO_ACTION", "reason": "stable"}
        )

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="auto")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == "auto"

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == "required"

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="record_decision")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == {
            "type": "function",
            "function": {"name": "record_decision"},
        }

    def test_translates_params_schema_to_parameters(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "RENAME", "reason": "label drift"}
        )

        provider.call_with_tools("s", "u", [SAMPLE_TOOL])

        sent_tools = provider.client.chat.completions.create.call_args.kwargs["tools"]
        assert sent_tools[0]["function"]["parameters"] == SAMPLE_TOOL.params_schema
        assert sent_tools[0]["function"]["name"] == "record_decision"

    def test_no_tool_when_forced_raises(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response_no_tool(
            finish_reason="stop"
        )
        with pytest.raises(Exception, match="no tool_calls"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")

    def test_max_tokens_finish_reason_raises(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response_no_tool(
            finish_reason="length"
        )
        with pytest.raises(Exception, match="truncated at max_tokens"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL])

    def test_model_override(self):
        provider = _bare_openai_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "DISSOLVE", "reason": "remove cluster"}
        )
        provider.call_with_tools("s", "u", [SAMPLE_TOOL], model="gpt-4o")
        assert provider.client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o"


@pytest.mark.unit
class TestAnthropic:
    def test_returns_parsed_tool_call(self):
        provider = _bare_anthropic_provider()
        provider.client.messages.create.return_value = _anthropic_response(
            "record_decision", {"verb": "CLEAVE", "reason": "split cluster"}
        )

        result = provider.call_with_tools(
            system_prompt="sys", user_prompt="usr", tools=[SAMPLE_TOOL]
        )

        assert result.tool_name == "record_decision"
        assert result.params == {"verb": "CLEAVE", "reason": "split cluster"}
        assert result.stop_reason == "tool_use"
        assert result.tokens.input_tokens == 12
        assert result.tokens.output_tokens == 7

    def test_tool_choice_translations(self):
        provider = _bare_anthropic_provider()
        provider.client.messages.create.return_value = _anthropic_response(
            "record_decision", {"verb": "MERGE", "reason": "x"}
        )

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="auto")
        assert provider.client.messages.create.call_args.kwargs["tool_choice"] == {"type": "auto"}

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")
        assert provider.client.messages.create.call_args.kwargs["tool_choice"] == {"type": "any"}

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="record_decision")
        assert provider.client.messages.create.call_args.kwargs["tool_choice"] == {
            "type": "tool",
            "name": "record_decision",
        }

    def test_translates_params_schema_to_input_schema(self):
        provider = _bare_anthropic_provider()
        provider.client.messages.create.return_value = _anthropic_response(
            "record_decision", {"verb": "MERGE", "reason": "x"}
        )
        provider.call_with_tools("s", "u", [SAMPLE_TOOL])

        sent_tools = provider.client.messages.create.call_args.kwargs["tools"]
        assert sent_tools[0]["input_schema"] == SAMPLE_TOOL.params_schema
        assert sent_tools[0]["name"] == "record_decision"

    def test_no_tool_when_forced_raises(self):
        provider = _bare_anthropic_provider()
        provider.client.messages.create.return_value = _anthropic_response_no_tool(
            stop_reason="end_turn"
        )
        with pytest.raises(Exception, match="no tool_use block"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")

    def test_max_tokens_stop_reason_raises(self):
        provider = _bare_anthropic_provider()
        provider.client.messages.create.return_value = _anthropic_response_no_tool(
            stop_reason="max_tokens"
        )
        with pytest.raises(Exception, match="truncated at max_tokens"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL])

    def test_temperature_dropped_for_opus_47(self):
        provider = _bare_anthropic_provider()
        provider.extraction_model = "claude-opus-4-7-20260101"
        provider.client.messages.create.return_value = _anthropic_response(
            "record_decision", {"verb": "MERGE", "reason": "x"}
        )

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], temperature=0.3)
        kwargs = provider.client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs


@pytest.mark.unit
class TestOpenRouter:
    def test_returns_parsed_tool_call(self):
        provider = _bare_openrouter_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "ESCALATE", "reason": "ambiguous"}
        )

        result = provider.call_with_tools("s", "u", [SAMPLE_TOOL])

        assert result.tool_name == "record_decision"
        assert result.params == {"verb": "ESCALATE", "reason": "ambiguous"}
        assert result.stop_reason == "tool_use"
        assert result.tokens.input_tokens == 10
        assert result.tokens.output_tokens == 5

    def test_tool_choice_translations(self):
        provider = _bare_openrouter_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "NO_ACTION", "reason": "x"}
        )

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="auto")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == "auto"

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == "required"

        provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="record_decision")
        assert provider.client.chat.completions.create.call_args.kwargs["tool_choice"] == {
            "type": "function",
            "function": {"name": "record_decision"},
        }

    def test_no_tool_when_forced_raises(self):
        provider = _bare_openrouter_provider()
        provider.client.chat.completions.create.return_value = _openai_response_no_tool(
            finish_reason="stop"
        )
        with pytest.raises(Exception, match="no tool_calls"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")

    def test_length_finish_reason_raises(self):
        provider = _bare_openrouter_provider()
        provider.client.chat.completions.create.return_value = _openai_response_no_tool(
            finish_reason="length"
        )
        with pytest.raises(Exception, match="truncated at max_tokens"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL])


@pytest.mark.unit
class TestOllama:
    def test_returns_parsed_tool_call_dict_args(self):
        provider = _bare_ollama_provider()
        resp = MagicMock()
        resp.json.return_value = _ollama_response(
            "record_decision", {"verb": "RENAME", "reason": "label clearer"}
        )
        resp.raise_for_status = MagicMock()
        provider.session.post.return_value = resp

        result = provider.call_with_tools("s", "u", [SAMPLE_TOOL])

        assert result.tool_name == "record_decision"
        assert result.params == {"verb": "RENAME", "reason": "label clearer"}
        assert result.stop_reason == "tool_use"
        assert result.tokens.input_tokens == 6
        assert result.tokens.output_tokens == 4

    def test_string_arguments_are_json_decoded(self):
        provider = _bare_ollama_provider()
        resp = MagicMock()
        resp.json.return_value = _ollama_response(
            "record_decision", json.dumps({"verb": "MERGE", "reason": "x"})
        )
        resp.raise_for_status = MagicMock()
        provider.session.post.return_value = resp

        result = provider.call_with_tools("s", "u", [SAMPLE_TOOL])
        assert result.params == {"verb": "MERGE", "reason": "x"}

    def test_sends_openai_style_tool_schema(self):
        provider = _bare_ollama_provider()
        resp = MagicMock()
        resp.json.return_value = _ollama_response(
            "record_decision", {"verb": "MERGE", "reason": "x"}
        )
        resp.raise_for_status = MagicMock()
        provider.session.post.return_value = resp

        provider.call_with_tools("s", "u", [SAMPLE_TOOL])
        body = provider.session.post.call_args.kwargs["json"]
        assert body["tools"][0]["function"]["parameters"] == SAMPLE_TOOL.params_schema
        assert body["tools"][0]["function"]["name"] == "record_decision"

    def test_no_tool_when_forced_raises_with_clear_message(self):
        provider = _bare_ollama_provider()
        resp = MagicMock()
        resp.json.return_value = _ollama_response_no_tool()
        resp.raise_for_status = MagicMock()
        provider.session.post.return_value = resp

        with pytest.raises(Exception, match="does not honor forced tool_choice"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="required")

    def test_no_tool_when_auto_still_raises(self):
        provider = _bare_ollama_provider()
        resp = MagicMock()
        resp.json.return_value = _ollama_response_no_tool()
        resp.raise_for_status = MagicMock()
        provider.session.post.return_value = resp

        with pytest.raises(Exception, match="no tool_calls"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL], tool_choice="auto")


@pytest.mark.unit
class TestLlamaCpp:
    def test_inherits_openai_implementation(self):
        assert LlamaCppProvider.call_with_tools is OpenAIProvider.call_with_tools

    def test_call_with_tools_works_through_inheritance(self):
        provider = _bare_llamacpp_provider()
        provider.client.chat.completions.create.return_value = _openai_response(
            "record_decision", {"verb": "DISSOLVE", "reason": "redundant"}
        )

        result = provider.call_with_tools("s", "u", [SAMPLE_TOOL])
        assert result.tool_name == "record_decision"
        assert result.params == {"verb": "DISSOLVE", "reason": "redundant"}


@pytest.mark.unit
class TestLocalEmbeddingProvider:
    def test_call_with_tools_raises_not_implemented(self):
        provider = object.__new__(LocalEmbeddingProvider)
        with pytest.raises(NotImplementedError, match="embedding-only"):
            provider.call_with_tools("s", "u", [SAMPLE_TOOL])


@pytest.mark.unit
class TestDataclasses:
    def test_tool_schema_minimum_fields(self):
        t = ToolSchema(name="x", description="d", params_schema={"type": "object"})
        assert t.name == "x"
        assert t.params_schema == {"type": "object"}

    def test_token_usage_defaults_zero(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.cached_input_tokens == 0

    def test_tool_call_response_raw_defaults_none(self):
        r = ToolCallResponse(
            tool_name="x", params={}, stop_reason="tool_use", tokens=TokenUsage()
        )
        assert r.raw_response is None

    def test_abstract_method_exists(self):
        assert "call_with_tools" in AIProvider.__abstractmethods__
