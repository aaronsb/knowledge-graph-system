"""
Unit tests for `_anthropic_create`, the reshape-and-retry wrapper around
Anthropic `messages.create`.

The client is a MagicMock whose `messages.create` raises fake 400 errors
shaped like the SDK's BadRequestError (a `status_code` attribute and the API
message in `str(err)`). No live API calls.
"""

import pytest
from unittest.mock import MagicMock

from api.app.lib import ai_providers
from api.app.lib.ai_providers import _anthropic_create


class FakeAPIError(Exception):
    """Stands in for anthropic.APIStatusError: carries `status_code`."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


SAMPLING_400 = "invalid_request_error: `temperature` is deprecated for this model"
TOOL_CHOICE_400 = (
    'invalid_request_error: tool_choice: type "tool" and "any" are not '
    "supported for this model"
)


@pytest.fixture(autouse=True)
def clear_learned_models():
    ai_providers._anthropic_no_sampling_models.clear()
    ai_providers._anthropic_auto_tool_choice_models.clear()
    yield
    ai_providers._anthropic_no_sampling_models.clear()
    ai_providers._anthropic_auto_tool_choice_models.clear()


def _request(model: str = "claude-test-1") -> dict:
    return {
        "model": model,
        "max_tokens": 1024,
        "system": "You extract concepts.",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"name": "record", "input_schema": {"type": "object"}}],
        "tool_choice": {"type": "tool", "name": "record"},
        "extra_body": {"temperature": 0.3},
    }


def _client(*side_effects) -> MagicMock:
    client = MagicMock()
    client.messages.create.side_effect = list(side_effects)
    return client


def _sent(client: MagicMock, call: int) -> dict:
    return client.messages.create.call_args_list[call].kwargs


def test_should_return_first_response_when_request_accepted():
    client = _client("ok")

    assert _anthropic_create(client, _request(), tool_name="record") == "ok"
    assert _sent(client, 0)["tool_choice"] == {"type": "tool", "name": "record"}
    assert _sent(client, 0)["extra_body"] == {"temperature": 0.3}


def test_should_drop_sampling_params_when_model_rejects_them():
    client = _client(FakeAPIError(SAMPLING_400), "ok")

    assert _anthropic_create(client, _request(), tool_name="record") == "ok"
    assert "extra_body" not in _sent(client, 1)
    assert _sent(client, 1)["tool_choice"] == {"type": "tool", "name": "record"}
    assert "claude-test-1" in ai_providers._anthropic_no_sampling_models


def test_should_switch_to_auto_tool_choice_when_forced_choice_rejected():
    client = _client(FakeAPIError(TOOL_CHOICE_400), "ok")

    assert _anthropic_create(client, _request(), tool_name="record") == "ok"
    retry = _sent(client, 1)
    assert retry["tool_choice"] == {"type": "auto"}
    assert retry["system"] == (
        "You extract concepts.\n\nRespond only by calling the record tool."
    )
    assert retry["extra_body"] == {"temperature": 0.3}
    assert "claude-test-1" in ai_providers._anthropic_auto_tool_choice_models


def test_should_handle_both_rejections_in_sequence():
    client = _client(FakeAPIError(SAMPLING_400), FakeAPIError(TOOL_CHOICE_400), "ok")

    assert _anthropic_create(client, _request(), tool_name="record") == "ok"
    final = _sent(client, 2)
    assert "extra_body" not in final
    assert final["tool_choice"] == {"type": "auto"}
    assert final["system"].count("Respond only by calling") == 1


def test_should_reraise_unrelated_400_without_learning_model():
    err = FakeAPIError("invalid_request_error: messages: field required")
    client = _client(err)

    with pytest.raises(FakeAPIError):
        _anthropic_create(client, _request(), tool_name="record")
    assert client.messages.create.call_count == 1
    assert not ai_providers._anthropic_no_sampling_models
    assert not ai_providers._anthropic_auto_tool_choice_models


def test_should_reraise_non_400_even_when_message_matches():
    client = _client(FakeAPIError(SAMPLING_400, status_code=500))

    with pytest.raises(FakeAPIError):
        _anthropic_create(client, _request(), tool_name="record")
    assert not ai_providers._anthropic_no_sampling_models


def test_should_send_accepted_shape_first_when_model_already_learned():
    ai_providers._anthropic_no_sampling_models.add("claude-test-1")
    ai_providers._anthropic_auto_tool_choice_models.add("claude-test-1")
    client = _client("ok")

    assert _anthropic_create(client, _request(), tool_name="record") == "ok"
    first = _sent(client, 0)
    assert "extra_body" not in first
    assert first["tool_choice"] == {"type": "auto"}


def test_should_name_any_tool_when_tool_name_omitted():
    request = _request()
    request["tool_choice"] = {"type": "any"}
    client = _client(FakeAPIError(TOOL_CHOICE_400), "ok")

    _anthropic_create(client, request)
    assert _sent(client, 1)["system"].endswith(
        "Respond only by calling one of the provided tools."
    )


def test_should_not_fail_when_tool_choice_is_none():
    request = _request()
    request["tool_choice"] = None
    client = _client("ok")

    assert _anthropic_create(client, request) == "ok"
