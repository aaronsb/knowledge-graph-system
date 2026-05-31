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
# _catalog_vision_model_ids — catalog-driven vision model enumeration
# (the admin /vision/providers surface; no hardcoded fallback).
#
# #457: the parallel VisionProvider classes that wrapped this as
# list_available_models() were collapsed into the AIProvider contract; the
# enumeration policy survives here as the catalog helper the routes call.
# ===========================================================================

class TestCatalogVisionModelIds:
    def test_should_return_catalog_vision_ids_when_present(self):
        rows = [{"model_id": "gpt-4o"}, {"model_id": "o3"}]
        with patch.object(vp, "_catalog_vision_models", return_value=rows):
            assert vp._catalog_vision_model_ids("openai") == ["gpt-4o", "o3"]

    def test_should_return_empty_when_catalog_empty(self):
        with patch.object(vp, "_catalog_vision_models", return_value=[]):
            assert vp._catalog_vision_model_ids("openai") == []

    def test_should_map_anthropic_catalog_rows_to_ids(self):
        rows = [{"model_id": "claude-sonnet-4-20250514"}]
        with patch.object(vp, "_catalog_vision_models", return_value=rows):
            assert vp._catalog_vision_model_ids("anthropic") == ["claude-sonnet-4-20250514"]


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


# ===========================================================================
# resolve_vision_selection — ADR-802 §2 / #378
# explicit → active vision config → vision-capable extraction default → raise
# (no hardcoded 'openai' literal)
# ===========================================================================

class TestResolveVisionSelection:
    @pytest.fixture(autouse=True)
    def _no_env(self, monkeypatch):
        # Default: no VISION_PROVIDER env so the config/default chain is exercised.
        monkeypatch.delenv("VISION_PROVIDER", raising=False)

    def test_explicit_override_is_honored_and_short_circuits(self):
        # Explicit provider wins without consulting config/catalog at all.
        with patch("api.app.lib.ai_vision_config.load_active_vision_config") as lv, \
             patch("api.app.lib.ai_extraction_config.load_active_extraction_config") as le:
            assert vp.resolve_vision_selection(provider="Anthropic", model="m") == ("anthropic", "m")
            lv.assert_not_called()
            le.assert_not_called()

    def test_vision_provider_env_used_when_no_param(self, monkeypatch):
        monkeypatch.setenv("VISION_PROVIDER", "ollama")
        assert vp.resolve_vision_selection() == ("ollama", None)

    def test_active_vision_config_used_when_present(self):
        with patch("api.app.lib.ai_vision_config.load_active_vision_config",
                   return_value={"provider": "openai", "model_name": "gpt-4o"}):
            assert vp.resolve_vision_selection() == ("openai", "gpt-4o")

    def test_explicit_model_overrides_vision_config_model(self):
        with patch("api.app.lib.ai_vision_config.load_active_vision_config",
                   return_value={"provider": "openai", "model_name": "gpt-4o"}):
            assert vp.resolve_vision_selection(model="gpt-4o-mini") == ("openai", "gpt-4o-mini")

    def test_defaults_to_extraction_provider_when_vision_capable(self):
        with patch("api.app.lib.ai_vision_config.load_active_vision_config", return_value=None), \
             patch("api.app.lib.ai_extraction_config.load_active_extraction_config",
                   return_value={"provider": "anthropic"}), \
             patch.object(vp, "_catalog_vision_model_ids", return_value=["claude-x"]):
            assert vp.resolve_vision_selection() == ("anthropic", None)

    def test_does_not_default_to_extraction_provider_without_vision_model(self):
        # Extraction provider has no supports_vision catalog model → fail loud,
        # rather than picking a provider that would error at the first image.
        with patch("api.app.lib.ai_vision_config.load_active_vision_config", return_value=None), \
             patch("api.app.lib.ai_extraction_config.load_active_extraction_config",
                   return_value={"provider": "ollama"}), \
             patch.object(vp, "_catalog_vision_model_ids", return_value=[]):
            with pytest.raises(ValueError, match="No vision provider could be resolved"):
                vp.resolve_vision_selection()

    def test_raises_when_nothing_resolves(self):
        # The headline #378 fix, now the surviving guarantee after #457 collapsed
        # the get_vision_provider() factory into the AIProvider contract: with no
        # explicit provider, no active vision config, and no vision-capable
        # extraction default, resolution RAISES rather than silently defaulting
        # to a hardcoded 'openai'. The ingestion worker then never reaches
        # get_provider()/describe_image with a bogus provider.
        with patch("api.app.lib.ai_vision_config.load_active_vision_config", return_value=None), \
             patch("api.app.lib.ai_extraction_config.load_active_extraction_config", return_value=None):
            with pytest.raises(ValueError, match="No vision provider could be resolved"):
                vp.resolve_vision_selection()
