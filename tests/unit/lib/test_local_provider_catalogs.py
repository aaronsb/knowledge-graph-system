"""Ollama and llama.cpp catalogs come from the servers' own reports (ADR-800).

Fixtures are trimmed from live responses (Ollama 0.34.4 with qwen2.5:0.5b and
moondream; llama-server serving the same qwen GGUF at -c 4096).
@verified 859cc8e6f
"""
from unittest.mock import MagicMock, patch

import pytest

from api.app.lib.ai_providers import LlamaCppProvider, OllamaProvider

OLLAMA_TAGS = {"models": [
    {"name": "qwen2.5:0.5b", "details": {"family": "qwen2"}},
    {"name": "moondream:latest", "details": {"family": "phi2"}},
    {"name": "nomic-embed-text:latest", "details": {"family": "nomic-bert"}},
    {"name": "gemma3:4b", "details": {"family": "gemma3"}},
]}
OLLAMA_SHOW = {
    "qwen2.5:0.5b": {"capabilities": ["completion", "tools"], "model_info": {
        "general.architecture": "qwen2", "qwen2.context_length": 32768}},
    "moondream:latest": {"capabilities": ["completion", "vision"], "model_info": {
        "general.architecture": "phi2", "phi2.context_length": 2048}},
    "nomic-embed-text:latest": {"capabilities": ["embedding"], "model_info": {
        "general.architecture": "nomic-bert"}},
    "gemma3:4b": {"capabilities": ["completion", "vision"], "model_info": {
        "general.architecture": "gemma3", "gemma3.context_length": 131072}},
}


def _response(payload, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def _ollama(show=OLLAMA_SHOW):
    p = object.__new__(OllamaProvider)
    p.base_url = "http://ollama:11434"
    p.session = MagicMock()
    p.session.get.return_value = _response(OLLAMA_TAGS)

    def post(url, json, timeout):
        if show is None:
            raise ConnectionError("no /api/show")
        return _response(show[json["model"]])
    p.session.post.side_effect = post
    return p


@pytest.mark.unit
class TestOllamaCatalog:
    def test_should_classify_from_capabilities_not_name(self):
        cat = {(e["model_id"], e["category"]): e for e in _ollama().fetch_model_catalog()}
        assert cat[("moondream:latest", "vision")]["supports_vision"] is True  # name has no "llava"
        assert ("qwen2.5:0.5b", "vision") not in cat
        cat = {e["model_id"]: e for e in _ollama().fetch_model_catalog() if e["category"] == "extraction"}
        assert cat["qwen2.5:0.5b"]["category"] == "extraction"
        assert cat["qwen2.5:0.5b"]["supports_tool_use"] is True

    def test_should_read_context_length_under_architecture_key(self):
        cat = {e["model_id"]: e for e in _ollama().fetch_model_catalog()}
        assert cat["qwen2.5:0.5b"]["context_length"] == 32768
        assert cat["moondream:latest"]["context_length"] == 2048

    def test_should_list_multimodal_model_under_extraction_and_vision(self):
        rows = [e for e in _ollama().fetch_model_catalog() if e["model_id"] == "gemma3:4b"]
        assert sorted(e["category"] for e in rows) == ["extraction", "vision"]
        assert all(e["supports_json_mode"] for e in rows)

    def test_should_skip_embedding_only_models(self):
        ids = {e["model_id"] for e in _ollama().fetch_model_catalog()}
        assert "nomic-embed-text:latest" not in ids

    def test_should_fall_back_to_name_when_show_is_unavailable(self):
        cat = {e["model_id"]: e for e in _ollama(show=None).fetch_model_catalog()}
        assert cat["moondream:latest"]["category"] == "extraction"  # old heuristic
        assert cat["qwen2.5:0.5b"]["context_length"] is None


LLAMA_PROPS = {
    "default_generation_settings": {"n_ctx": 4096},
    "modalities": {"vision": False, "video": False, "audio": False},
    "chat_template_caps": {"supports_tools": True, "supports_tool_calls": True},
}


def _llamacpp(props):
    p = object.__new__(LlamaCppProvider)
    p.base_url = "http://llama:8080/v1"
    model = MagicMock(id="qwen05.gguf")
    model.model_dump.return_value = {
        "id": "qwen05.gguf", "meta": {"n_ctx": 4096, "n_ctx_train": 32768}}
    p.client = MagicMock()
    p.client.models.list.return_value = MagicMock(data=[model])
    return p, props


@pytest.mark.unit
class TestLlamaCppCatalog:
    def test_should_take_served_context_vision_and_tools_from_props(self):
        p, props = _llamacpp(LLAMA_PROPS)
        with patch("httpx.get", return_value=_response(props)) as get:
            entry = p.fetch_model_catalog()[0]
        assert get.call_args.args[0] == "http://llama:8080/props"  # server root, not /v1
        assert entry["context_length"] == 4096  # served, not n_ctx_train
        assert entry["supports_vision"] is False
        assert entry["supports_tool_use"] is True

    def test_should_fall_back_to_model_meta_without_props(self):
        p, _ = _llamacpp({})
        with patch("httpx.get", side_effect=ConnectionError("no /props")):
            entry = p.fetch_model_catalog()[0]
        assert entry["context_length"] == 4096
        assert entry["supports_tool_use"] is False
