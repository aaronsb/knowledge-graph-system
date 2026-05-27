"""
Perplexity clamp in EmbeddingProjectionService.compute_projection.

Sklearn's TSNE requires `perplexity < n_samples`. The launcher (above) now
refuses to enqueue projection jobs below min_concepts, but the worker still
needs to refuse impossibly small inputs and clamp perplexity defensively so
no future change to the heuristic can produce an invalid value.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from api.app.services.embedding_projection_service import EmbeddingProjectionService


@pytest.fixture
def service():
    """Bare service — compute_projection doesn't touch the DB."""
    return EmbeddingProjectionService(age_client=MagicMock())


def _rand(n, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, dim)).astype(np.float32)


def test_raises_when_n_samples_below_three(service):
    """n_samples in {0, 1, 2} cannot be projected meaningfully — refuse."""
    for n in (0, 1, 2):
        with pytest.raises(ValueError, match="at least 3 samples"):
            service.compute_projection(
                _rand(n),
                algorithm="tsne",
                n_components=2,
                perplexity=30,
            )


def test_tsne_succeeds_on_minimal_input(service):
    """n_samples=3 with high requested perplexity must clamp, not raise."""
    coords = service.compute_projection(
        _rand(3),
        algorithm="tsne",
        n_components=2,
        perplexity=30,  # would violate perplexity < n_samples without clamp
    )
    assert coords.shape == (3, 2)


def test_tsne_succeeds_just_above_the_floor(service):
    """A 5-concept ontology (launcher floor) must project cleanly."""
    coords = service.compute_projection(
        _rand(5),
        algorithm="tsne",
        n_components=2,
        perplexity=30,
    )
    assert coords.shape == (5, 2)
