"""
Unit tests for catalog-driven vision model selection (ADR-801, task #13).

Vision provider/model selection must come from the dynamic catalog's
per-model supports_vision flag, not hardcoded lists — the same decision
ADR-801 applies to extraction, applied to the vision path where it had
regressed. The catalog boundary is mocked (no DB/network).
"""

import pytest
from unittest.mock import MagicMock, patch

from api.app.lib import vision_providers as vp
from api.app.lib.ai_providers import OpenAIProvider


# ===========================================================================
# _resolve_vision_model — param → catalog → env → error (no literal fallback)
# ===========================================================================

class TestResolveVisionModel:
    def test_should_prefer_explicit_param_over_everything(self):
        assert vp._resolve_vision_model("anthropic", "my-model") == "my-model"

    def test_should_use_catalog_is_default_when_no_param(self):
        rows = [{"model_id": "a", "is_default": False},
                {"model_id": "b", "is_default": True}]
        with patch.object(vp, "_catalog_vision_models", return_value=rows):
            assert vp._resolve_vision_model("openai") == "b"

    def test_should_use_first_catalog_row_when_no_default(self):
        rows = [{"model_id": "first", "is_default": False},
                {"model_id": "second", "is_default": False}]
        with patch.object(vp, "_catalog_vision_models", return_value=rows):
            assert vp._resolve_vision_model("openai") == "first"

    def test_should_fall_back_to_env_when_catalog_empty(self, monkeypatch):
        monkeypatch.setenv("VISION_MODEL", "env-model")
        with patch.object(vp, "_catalog_vision_models", return_value=[]):
            assert vp._resolve_vision_model("ollama") == "env-model"

    def test_should_raise_when_nothing_resolves(self, monkeypatch):
        # No literal fallback: catalog-empty + no env is a configuration error
        # the operator must fix, not something we paper over with a stale id.
        monkeypatch.delenv("VISION_MODEL", raising=False)
        with patch.object(vp, "_catalog_vision_models", return_value=[]):
            with pytest.raises(ValueError, match="No vision model resolved"):
                vp._resolve_vision_model("ollama")

    def test_catalog_lookup_swallows_db_errors_and_returns_empty(
            self, monkeypatch):
        # The helper is the guard: any catalog/DB failure → [] (never raises),
        # so resolution degrades to env. With no env, the resolver itself raises.
        monkeypatch.delenv("VISION_MODEL", raising=False)
        with patch("api.app.lib.model_catalog.list_catalog",
                   side_effect=Exception("db down")):
            assert vp._catalog_vision_models("openai") == []
            with pytest.raises(ValueError, match="No vision model resolved"):
                vp._resolve_vision_model("openai")


# ===========================================================================
# list_available_models — catalog-driven, no hardcoded fallback
# ===========================================================================

class TestListAvailableModelsCatalogOnly:
    def test_openai_should_return_catalog_vision_ids_when_present(self):
        p = object.__new__(vp.OpenAIVisionProvider)
        with patch.object(vp, "_catalog_vision_model_ids",
                          return_value=["gpt-4o", "o3"]):
            assert p.list_available_models() == ["gpt-4o", "o3"]

    def test_openai_should_return_empty_when_catalog_empty(self):
        p = object.__new__(vp.OpenAIVisionProvider)
        with patch.object(vp, "_catalog_vision_model_ids", return_value=[]):
            assert p.list_available_models() == []

    def test_anthropic_should_prefer_catalog(self):
        p = object.__new__(vp.AnthropicVisionProvider)
        with patch.object(vp, "_catalog_vision_model_ids",
                          return_value=["claude-sonnet-4-20250514"]):
            assert p.list_available_models() == ["claude-sonnet-4-20250514"]


# ===========================================================================
# OpenAI catalog vision heuristic — reasoning families are vision-capable
# ===========================================================================

class TestOpenAIVisionHeuristic:
    def _catalog(self, ids):
        p = object.__new__(OpenAIProvider)
        p.client = MagicMock()
        p.client.models.list.return_value = MagicMock(
            data=[MagicMock(id=i, created=0) for i in ids])
        return {e["model_id"]: e for e in p.fetch_model_catalog()}

    def test_should_flag_o_series_and_gpt5_vision_capable(self):
        cat = self._catalog(["gpt-4o", "o1", "o3-mini", "o4", "gpt-5-preview",
                              "gpt-3.5-turbo"])
        assert cat["gpt-4o"]["supports_vision"] is True
        assert cat["o1"]["supports_vision"] is True       # was missed before
        assert cat["o3-mini"]["supports_vision"] is True
        assert cat["o4"]["supports_vision"] is True
        assert cat["gpt-5-preview"]["supports_vision"] is True
        # gpt-3.5 is genuinely not vision-capable.
        assert cat["gpt-3.5-turbo"]["supports_vision"] is False
