"""Shared test helpers for the Knowledge Graph test suite."""

import numpy as np


def patch_synonym_detector_embedding(detector):
    """Patch SynonymDetector._get_edge_type_embedding to bypass AGEClient.

    The production _get_edge_type_embedding imports AGEClient for database
    lookups, which isn't available in tests. This replaces it with a version
    that goes directly to the mock AI provider.

    Args:
        detector: SynonymDetector instance with a mock ai_provider
    """
    async def _patched(edge_type: str) -> np.ndarray:
        if edge_type in detector._embedding_cache:
            return detector._embedding_cache[edge_type]

        descriptive_text = detector._edge_type_to_text(edge_type)
        result = await detector.ai_provider.generate_embedding(descriptive_text)
        embedding = np.array(result["embedding"])
        detector._embedding_cache[edge_type] = embedding
        return embedding

    detector._get_edge_type_embedding = _patched
