"""
Real-torch integration test for the embedding-model-manager CPU fallback.

The companion test file (`test_embedding_model_manager_fallback.py`) mocks
`load_model` to exercise control flow. That covers the wrapper's branching
but does NOT prove the underlying contract the wrapper depends on:

  When PyTorch is asked to load a model on a device it cannot use,
  does it raise a *catchable* Python exception — or does it die in a
  way the `except` clause never sees (segfault, abort, fatal error)?

If the answer is "uncatchable" for any real device, the CPU fallback we
shipped for issue #405 / ADR-101 would silently fail to engage on real
hardware. This test exercises the *real* sentence-transformers /
transformers code path with a tiny model on a host that genuinely lacks
CUDA, and asserts:

  1. The configured device=cuda request raises something we can catch.
  2. The CPU fallback then loads a real model.
  3. The fallback manager produces real embeddings.

A skip-if-CUDA-available guard keeps the test honest — the assertions
only make sense on hosts where the configured device is genuinely missing.
"""

import pytest
from unittest.mock import patch

from api.app.lib import embedding_model_manager as emm


@pytest.fixture(autouse=True)
def _reset_global_manager():
    emm._model_manager = None
    yield
    emm._model_manager = None


def _tiny_model_config(device: str) -> dict:
    # all-MiniLM-L6-v2 is ~80 MB and 384-dim — small enough to download in
    # CI without dominating the test run.
    return {
        "text_provider": "local",
        "text_model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "text_loader": "sentence-transformers",
        "text_precision": "float32",
        "device": device,
        "text_dimensions": 384,
    }


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


@pytest.mark.skipif(
    _cuda_available(),
    reason="real-torch fallback test requires a host without usable CUDA",
)
class TestRealTorchFallback:
    """Hits the real torch + sentence-transformers loader. Slow (~10-30s on
    first run while the model downloads; cached after) but proves the
    catchable-exception contract that the mocked tests can only assume."""

    @pytest.mark.asyncio
    async def test_should_fall_back_to_cpu_with_real_torch_when_cuda_requested(self):
        with patch(
            "api.app.lib.embedding_config.load_active_embedding_config",
            return_value=_tiny_model_config(device="cuda"),
        ):
            try:
                manager = await emm.init_embedding_model_manager()
            except (ImportError, OSError) as e:
                # No network / missing model files / no torch wheels. Skip
                # rather than fail — this is an integration concern, not a
                # contract violation by our code.
                pytest.skip(f"real model load unavailable in this environment: {e}")

        assert manager is not None
        # The model is actually loaded — i.e., the CPU fallback ran the
        # full real-torch code path, not just survived the exception.
        assert manager.model is not None
        assert manager.get_dimensions() == 384

        # And it produces real embeddings of the right shape.
        embedding = manager.generate_embedding("hello world")
        assert isinstance(embedding, list)
        assert len(embedding) == 384
