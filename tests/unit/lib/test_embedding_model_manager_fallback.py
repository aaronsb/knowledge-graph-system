"""
Unit tests for the embedding-model-manager CPU fallback (ADR-101, issue #405).

Locks two related behaviours:

1. When `load_model()` fails on the configured device (CUDA unavailable on
   a host with no NVIDIA driver, ROCm with the wrong torch wheel, MPS on a
   non-Apple host), `init_embedding_model_manager` retries once with
   device='cpu' before giving up.

2. A failed initialisation never leaves the module-global `_model_manager`
   pointing at a half-built manager (the silent-broken state described in
   #405 where downstream code raises "Embedding model not loaded. Call
   load_model() first." for every concept).

The tests mock `EmbeddingModelManager.load_model` so they do not touch
sentence-transformers or torch — they exercise the init wrapper, not the
underlying model load.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from api.app.lib import embedding_model_manager as emm


@pytest.fixture(autouse=True)
def _reset_global_manager():
    """Each test starts and ends with no module-global manager."""
    emm._model_manager = None
    yield
    emm._model_manager = None


def _config(device: str = "cuda") -> dict:
    return {
        "text_provider": "local",
        "text_model_name": "nomic-ai/nomic-embed-text-v1.5",
        "text_loader": "sentence-transformers",
        "text_precision": "float16",
        "device": device,
        "text_dimensions": 768,
    }


def _patch_config_module(device: str = "cuda"):
    # load_active_embedding_config is imported lazily inside the function;
    # patch its source module so the late import resolves to our mock.
    return patch(
        "api.app.lib.embedding_config.load_active_embedding_config",
        return_value=_config(device),
    )


class TestEmbeddingFallback:
    @pytest.mark.asyncio
    async def test_should_use_configured_device_when_load_succeeds(self):
        load_calls = []

        def fake_load(self):
            load_calls.append(self.configured_device)
            self.model = MagicMock()
            self.dimensions = 768

        with _patch_config_module(device="cuda"), \
             patch.object(emm.EmbeddingModelManager, "load_model", fake_load):
            manager = await emm.init_embedding_model_manager()

        assert manager is not None
        assert load_calls == ["cuda"]
        assert emm._model_manager is manager

    @pytest.mark.asyncio
    async def test_should_retry_on_cpu_when_configured_device_fails(self, caplog):
        load_calls = []

        def fake_load(self):
            load_calls.append(self.configured_device)
            if self.configured_device == "cuda":
                raise RuntimeError("Found no NVIDIA driver on your system.")
            self.model = MagicMock()
            self.dimensions = 768

        with _patch_config_module(device="cuda"), \
             patch.object(emm.EmbeddingModelManager, "load_model", fake_load):
            manager = await emm.init_embedding_model_manager()

        assert load_calls == ["cuda", "cpu"]
        assert manager is not None
        assert emm._model_manager is manager
        # User-facing log carries the truth: device fell back to CPU.
        joined = "\n".join(r.message for r in caplog.records)
        assert "Falling back to CPU" in joined

    @pytest.mark.asyncio
    async def test_should_raise_and_clear_global_when_both_devices_fail(self):
        def fake_load(self):
            raise RuntimeError("simulated load failure")

        with _patch_config_module(device="cuda"), \
             patch.object(emm.EmbeddingModelManager, "load_model", fake_load):
            with pytest.raises(RuntimeError):
                await emm.init_embedding_model_manager()

        # The defining bug from #405: a failed init must not leave a half-built
        # manager visible to get_embedding_model_manager().
        assert emm._model_manager is None
        with pytest.raises(RuntimeError, match="not initialized"):
            emm.get_embedding_model_manager()

    @pytest.mark.asyncio
    async def test_should_not_retry_when_configured_device_is_already_cpu(self):
        load_calls = []

        def fake_load(self):
            load_calls.append(self.configured_device)
            raise RuntimeError("simulated CPU failure")

        with _patch_config_module(device="cpu"), \
             patch.object(emm.EmbeddingModelManager, "load_model", fake_load):
            with pytest.raises(RuntimeError):
                await emm.init_embedding_model_manager()

        # Only one attempt — no spurious retry that would double the failure
        # noise in logs.
        assert load_calls == ["cpu"]
        assert emm._model_manager is None
