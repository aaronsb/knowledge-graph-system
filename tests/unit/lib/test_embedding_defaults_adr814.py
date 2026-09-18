"""
Unit tests for the ADR-814 default-profile loader behaviours.

Locks three decisions from ADR-814 without touching torch or transformers:

1. The image loader resolves a two-tower checkpoint (SigLIP, CLIP) to its
   vision-tower class, and falls back to AutoModel for single-tower encoders.
2. Image pooling uses ``pooler_output`` when the model defines one and falls
   back to the CLS token otherwise (Nomic Vision has no pooler).
3. Text task prefixes are passed to sentence-transformers as a raw ``prompt``
   string, never by ``prompt_name`` (modernbert-embed-base registers the
   'query'/'document' names as empty strings, which would drop the prefix).
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from api.app.lib import embedding_model_manager as emm
from api.app.lib import visual_embeddings as ve


class _Tensor:
    """Minimal stand-in for a torch tensor slice: records what was taken."""

    def __init__(self, tag):
        self.tag = tag

    def __getitem__(self, key):
        return _Tensor(f"{self.tag}{key}")


class TestVisionPooling:
    def test_should_prefer_pooler_output_when_present(self):
        out = SimpleNamespace(pooler_output=_Tensor("pooled"), last_hidden_state=_Tensor("hidden"))
        assert ve.VisualEmbeddingGenerator._pool(out).tag == "pooled"

    def test_should_fall_back_to_cls_token_without_pooler(self):
        out = SimpleNamespace(pooler_output=None, last_hidden_state=_Tensor("hidden"))
        pooled = ve.VisualEmbeddingGenerator._pool(out)
        assert pooled.tag.startswith("hidden(slice(None, None, None), 0")

    def test_should_fall_back_when_output_has_no_pooler_attribute(self):
        out = SimpleNamespace(last_hidden_state=_Tensor("hidden"))
        assert ve.VisualEmbeddingGenerator._pool(out).tag.startswith("hidden")


def _generator_without_load(model_name: str) -> ve.VisualEmbeddingGenerator:
    with patch.object(ve.VisualEmbeddingGenerator, "_load_model"), \
         patch("api.app.lib.device_selector.get_best_device", return_value="cpu"), \
         patch("api.app.lib.device_selector.log_device_selection"):
        return ve.VisualEmbeddingGenerator(model_name=model_name, device="cpu")


def _fake_transformers(model_type: str, **classes):
    """A stub `transformers` module exposing AutoConfig/AutoModel plus any tower classes."""
    mod = types.ModuleType("transformers")
    mod.AutoConfig = SimpleNamespace(from_pretrained=MagicMock(return_value=SimpleNamespace(model_type=model_type)))
    mod.AutoModel = object()
    for name, cls in classes.items():
        setattr(mod, name, cls)
    return mod


class TestVisionTowerResolution:
    @pytest.mark.parametrize("model_type,cls_name", [
        ("siglip", "SiglipVisionModel"),
        ("siglip2", "Siglip2VisionModel"),
        ("clip", "CLIPVisionModel"),
    ])
    def test_should_load_vision_tower_for_two_tower_models(self, model_type, cls_name):
        tower = object()
        gen = _generator_without_load("google/siglip2-base-patch16-256")
        with patch.dict(sys.modules, {"transformers": _fake_transformers(model_type, **{cls_name: tower})}):
            assert gen._resolve_vision_model_class() is tower

    def test_should_fall_back_to_automodel_for_single_tower_encoders(self):
        gen = _generator_without_load("nomic-ai/nomic-embed-vision-v1.5")
        fake = _fake_transformers("nomic_bert")
        with patch.dict(sys.modules, {"transformers": fake}):
            assert gen._resolve_vision_model_class() is fake.AutoModel

    def test_should_default_to_siglip2_without_remote_code(self):
        gen = _generator_without_load(ve.VisualEmbeddingGenerator.__init__.__defaults__[0])
        assert gen.model_name == "google/siglip2-base-patch16-256"
        assert gen.trust_remote_code is False


class TestRawTaskPrefix:
    def _manager(self, query_prefix, document_prefix):
        m = emm.EmbeddingModelManager(
            model_name="nomic-ai/modernbert-embed-base",
            loader="sentence-transformers",
            precision="float32",
            query_prefix=query_prefix,
            document_prefix=document_prefix,
        )
        m.model = MagicMock()
        m.model.encode.return_value = np.ones(4, dtype=np.float32)
        return m

    def test_should_pass_query_prefix_as_raw_prompt(self):
        m = self._manager("search_query: ", "search_document: ")
        m.generate_embedding("hello", purpose="query")
        kwargs = m.model.encode.call_args.kwargs
        assert kwargs["prompt"] == "search_query: "
        assert "prompt_name" not in kwargs

    def test_should_pass_document_prefix_as_raw_prompt(self):
        m = self._manager("search_query: ", "search_document: ")
        m.generate_embedding("hello", purpose="document")
        assert m.model.encode.call_args.kwargs["prompt"] == "search_document: "

    def test_should_send_no_prompt_when_profile_has_no_prefix(self):
        m = self._manager(None, None)
        m.generate_embedding("hello", purpose="query")
        kwargs = m.model.encode.call_args.kwargs
        assert "prompt" not in kwargs and "prompt_name" not in kwargs
