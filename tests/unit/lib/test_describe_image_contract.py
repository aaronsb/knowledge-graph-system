"""
Unit tests for the unified AIProvider.describe_image contract (#457, ADR-802 §4).

The parallel VisionProvider hierarchy was collapsed into AIProvider.describe_image.
This pins the behavioural-fidelity contract the collapse had to preserve (ADR-305):

- The signature is parameterized: ``model`` / ``detail`` / ``temperature``.
- ``detail=None`` omits the OpenAI ``detail`` key (provider "auto") — exactly
  how the ingestion worker reproduces the research-validated literal path; the
  route keeps ``detail="high"`` via the default.
- ``temperature`` and an explicit vision ``model`` thread through to the request.
- The return shape is unified: {text, tokens:{...}, model, provider}.

The provider SDK client is mocked — no network.
"""

from unittest.mock import MagicMock

from api.app.lib.ai_providers import OpenAIProvider, AnthropicProvider


def _openai_response(text="described", finish_reason="stop"):
    """Build a mock OpenAI chat-completions response with usage."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].finish_reason = finish_reason
    resp.choices[0].message.content = text
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 40
    resp.usage.total_tokens = 140
    return resp


def _make_openai():
    """OpenAIProvider with a mocked client (bypasses __init__/key loading)."""
    p = object.__new__(OpenAIProvider)
    p.client = MagicMock()
    p.client.chat.completions.create.return_value = _openai_response()
    return p


class TestOpenAIDescribeImageContract:
    def test_default_detail_high_is_sent(self):
        # The route (ingest.py) path: defaults reproduce historical behaviour.
        p = _make_openai()
        p.describe_image(b"\x89PNGfake", "prompt", model="gpt-4o")
        kwargs = p.client.chat.completions.create.call_args.kwargs
        image_part = kwargs["messages"][0]["content"][1]["image_url"]
        assert image_part.get("detail") == "high"
        assert kwargs["temperature"] == 0.3

    def test_detail_none_omits_key(self):
        # The ingestion-worker literal path passes detail=None → key omitted
        # (OpenAI "auto"), reproducing the old vision_providers behaviour.
        p = _make_openai()
        p.describe_image(b"\x89PNGfake", "prompt", model="gpt-4o",
                         detail=None, temperature=0.1)
        kwargs = p.client.chat.completions.create.call_args.kwargs
        image_part = kwargs["messages"][0]["content"][1]["image_url"]
        assert "detail" not in image_part
        assert kwargs["temperature"] == 0.1

    def test_explicit_model_threads_through(self):
        p = _make_openai()
        p.describe_image(b"\x89PNGfake", "prompt", model="gpt-4o-mini")
        assert p.client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"

    def test_mime_detected_from_magic_bytes(self):
        # Regression for the data-URL MIME: a JPEG must be labelled image/jpeg,
        # not hardcoded image/png. The old vision path detected this; the
        # collapsed path must too (PR #457 review item).
        p = _make_openai()
        p.describe_image(b"\xff\xd8\xff\xe0jpegfake", "prompt", model="gpt-4o")
        url = p.client.chat.completions.create.call_args.kwargs[
            "messages"][0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/jpeg;base64,")

    def test_png_mime_default(self):
        p = _make_openai()
        p.describe_image(b"\x89PNG\r\n\x1a\n", "prompt", model="gpt-4o")
        url = p.client.chat.completions.create.call_args.kwargs[
            "messages"][0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

    def test_unified_return_shape(self):
        p = _make_openai()
        out = p.describe_image(b"\x89PNGfake", "prompt", model="gpt-4o")
        assert out["text"] == "described"
        assert out["provider"] == "openai"
        assert out["model"] == "gpt-4o"
        assert out["tokens"] == {
            "input_tokens": 100, "output_tokens": 40, "total_tokens": 140,
        }

    def test_truncation_raises(self):
        p = _make_openai()
        p.client.chat.completions.create.return_value = _openai_response(
            finish_reason="length")
        try:
            p.describe_image(b"\x89PNGfake", "prompt", model="gpt-4o")
            assert False, "expected truncation to raise"
        except Exception as e:
            assert "truncated" in str(e)


def _make_anthropic():
    p = object.__new__(AnthropicProvider)
    p.client = MagicMock()
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "described"
    msg.content = [text_block]
    msg.usage.input_tokens = 80
    msg.usage.output_tokens = 20
    p.client.messages.create.return_value = msg
    return p


class TestAnthropicDescribeImageContract:
    def test_temperature_and_model_thread_through(self):
        # claude-sonnet keeps sampling params (not the Opus 4.7 no-sampling family).
        p = _make_anthropic()
        p.describe_image(b"\xff\xd8jpegfake", "prompt",
                         model="claude-sonnet-4-6", temperature=0.1)
        kwargs = p.client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-sonnet-4-6"
        assert kwargs["temperature"] == 0.1

    def test_unified_return_shape(self):
        p = _make_anthropic()
        out = p.describe_image(b"\xff\xd8jpegfake", "prompt",
                               model="claude-sonnet-4-6")
        assert out["text"] == "described"
        assert out["provider"] == "anthropic"
        assert out["model"] == "claude-sonnet-4-6"
        assert out["tokens"] == {
            "input_tokens": 80, "output_tokens": 20, "total_tokens": 100,
        }
