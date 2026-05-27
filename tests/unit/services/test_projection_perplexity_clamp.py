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


def test_min_samples_constant_is_three(service):
    """Pin the class constant so the launcher/route stays in sync."""
    assert service.MIN_SAMPLES_FOR_PROJECTION == 3


def test_error_message_is_algorithm_agnostic(service):
    """The guard fires for both t-SNE and UMAP — message shouldn't blame one."""
    for algo in ("tsne", "umap"):
        try:
            service.compute_projection(
                _rand(2), algorithm=algo, n_components=2, perplexity=30
            )
        except ValueError as exc:
            assert "t-SNE" not in str(exc), (
                f"Algorithm-specific text leaked into the message for {algo}: {exc}"
            )
        except Exception:
            # UMAP may not be installed; skip but don't fail
            pass


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


def test_dataset_returns_error_dict_at_two_items_not_raise():
    """Boundary fix (#1): generate_projection_dataset's pre-check must stay
    aligned with compute_projection's hard floor. For exactly 2 items, the
    method must return the friendly error dict — not let the call fall
    through to compute_projection and raise. Worker code branches on
    `if "error" in dataset`; without this alignment, 2-item ontologies
    crash with a raw ValueError instead of completing with a structured
    error."""
    service = EmbeddingProjectionService(age_client=MagicMock())
    # Stub the fetcher to return exactly 2 items with embeddings
    service.get_ontology_embeddings = MagicMock(
        return_value=[
            {"concept_id": "c1", "label": "A", "embedding": [0.1] * 8},
            {"concept_id": "c2", "label": "B", "embedding": [0.2] * 8},
        ]
    )

    result = service.generate_projection_dataset(
        ontology="two-items",
        embedding_source="concepts",
    )

    assert isinstance(result, dict)
    assert "error" in result
    assert result["concept_count"] == 2
    assert "at least 3" in result["error"]
