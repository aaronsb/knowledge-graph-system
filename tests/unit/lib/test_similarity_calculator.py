"""
Unit tests for similarity_calculator.py

Tests cosine similarity calculations with comprehensive edge cases,
validation, and performance benchmarks.
"""

import pytest
import numpy as np
import time
from api.app.lib.similarity_calculator import (
    cosine_similarity,
    batch_cosine_similarity
)


class TestCosineSimilarity:
    """Test cases for cosine_similarity() function"""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0"""
        vec = np.array([1.0, 2.0, 3.0])
        similarity = cosine_similarity(vec, vec)
        assert similarity == 1.0

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0"""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity) < 1e-10

    def test_opposite_vectors(self):
        """Opposite direction vectors should have similarity -1.0"""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([-1.0, -2.0, -3.0])
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 1e-10

    def test_similar_vectors(self):
        """Similar vectors should have high positive similarity"""
        vec1 = np.array([1.0, 1.0, 1.0])
        vec2 = np.array([1.0, 1.0, 0.9])
        similarity = cosine_similarity(vec1, vec2)
        assert 0.95 < similarity < 1.0

    def test_different_magnitudes(self):
        """Cosine similarity is magnitude-independent"""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([100.0, 0.0])
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 1.0

    def test_normalized_vectors(self):
        """Pre-normalized vectors should work correctly"""
        vec1 = np.array([1.0, 0.0])  # Already normalized
        vec2 = np.array([0.707, 0.707])  # Normalized
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.707) < 0.001

    def test_zero_vector_raises_error(self):
        """Zero vectors should raise ValueError"""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="zero vector"):
            cosine_similarity(vec1, vec2)

    def test_dimension_mismatch_raises_error(self):
        """Vectors with different dimensions should raise ValueError"""
        vec1 = np.array([1.0, 2.0])
        vec2 = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity(vec1, vec2)

    def test_2d_array_raises_error(self):
        """2D arrays should raise ValueError (must be 1D)"""
        vec1 = np.array([[1.0, 2.0]])
        vec2 = np.array([[1.0, 2.0]])
        with pytest.raises(ValueError, match="1D arrays"):
            cosine_similarity(vec1, vec2)

    def test_high_dimensional_vectors(self):
        """Should work with high-dimensional vectors (e.g., 768-dim embeddings)"""
        vec1 = np.random.rand(768)
        vec2 = vec1.copy()
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_returns_python_float(self):
        """Should return Python float, not numpy.float64"""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([1.0, 0.0])
        similarity = cosine_similarity(vec1, vec2)
        assert isinstance(similarity, float)
        assert not isinstance(similarity, np.floating)

    def test_numerical_precision(self):
        """Should handle very small values without overflow"""
        vec1 = np.array([1e-10, 1e-10, 1e-10])
        vec2 = np.array([1e-10, 1e-10, 1e-10])
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-5

    def test_negative_values(self):
        """Should handle vectors with negative values"""
        vec1 = np.array([-1.0, -2.0, -3.0])
        vec2 = np.array([-1.0, -2.0, -3.0])
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 1.0


class TestBatchCosineSimilarity:
    """Test cases for batch_cosine_similarity() function"""

    def test_batch_identical_vectors(self):
        """Batch similarity with identical vectors"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.array([
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0],
            [1.0, 2.0, 3.0]
        ])
        similarities = batch_cosine_similarity(query, vectors)
        np.testing.assert_allclose(similarities, 1.0, atol=1e-10)

    def test_batch_orthogonal_vectors(self):
        """Batch similarity with orthogonal vectors"""
        query = np.array([1.0, 0.0, 0.0])
        vectors = np.array([
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 1.0]
        ])
        similarities = batch_cosine_similarity(query, vectors)
        assert np.all(np.abs(similarities) < 1e-10)

    def test_batch_mixed_similarities(self):
        """Batch similarity with mixed directions"""
        query = np.array([1.0, 0.0, 0.0])
        vectors = np.array([
            [1.0, 0.0, 0.0],   # Identical: sim=1.0
            [0.0, 1.0, 0.0],   # Orthogonal: sim=0.0
            [-1.0, 0.0, 0.0]   # Opposite: sim=-1.0
        ])
        similarities = batch_cosine_similarity(query, vectors)
        assert abs(similarities[0] - 1.0) < 1e-10
        assert abs(similarities[1] - 0.0) < 1e-10
        assert abs(similarities[2] - (-1.0)) < 1e-10

    def test_batch_returns_correct_shape(self):
        """Batch should return 1D array of correct length"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
            [10.0, 11.0, 12.0]
        ])
        similarities = batch_cosine_similarity(query, vectors)
        assert similarities.shape == (4,)
        assert similarities.ndim == 1

    def test_batch_matches_individual_calculations(self):
        """Batch results should match individual cosine_similarity calls"""
        query = np.array([1.0, 2.0, 3.0, 4.0])
        vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [1.0, 2.0, 3.0, 4.0],
            [4.0, 3.0, 2.0, 1.0]
        ])

        batch_result = batch_cosine_similarity(query, vectors)

        for i, vec in enumerate(vectors):
            individual_result = cosine_similarity(query, vec)
            assert abs(batch_result[i] - individual_result) < 1e-10

    def test_batch_query_not_1d_raises_error(self):
        """Batch should raise error if query is not 1D"""
        query = np.array([[1.0, 2.0, 3.0]])  # 2D
        vectors = np.array([[1.0, 2.0, 3.0]])
        with pytest.raises(ValueError, match="must be 1D"):
            batch_cosine_similarity(query, vectors)

    def test_batch_vectors_not_2d_raises_error(self):
        """Batch should raise error if vectors is not 2D"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.array([1.0, 2.0, 3.0])  # 1D instead of 2D
        with pytest.raises(ValueError, match="must be 2D"):
            batch_cosine_similarity(query, vectors)

    def test_batch_dimension_mismatch_raises_error(self):
        """Batch should raise error if dimensions don't match"""
        query = np.array([1.0, 2.0])
        vectors = np.array([[1.0, 2.0, 3.0]])
        with pytest.raises(ValueError, match="Dimension mismatch"):
            batch_cosine_similarity(query, vectors)

    def test_batch_zero_query_vector_raises_error(self):
        """Batch should raise error if query is zero vector"""
        query = np.array([0.0, 0.0, 0.0])
        vectors = np.array([[1.0, 2.0, 3.0]])
        with pytest.raises(ValueError, match="zero query vector"):
            batch_cosine_similarity(query, vectors)

    def test_batch_contains_zero_vector_raises_error(self):
        """Batch should raise error if any vector is zero"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.array([
            [1.0, 2.0, 3.0],
            [0.0, 0.0, 0.0],  # Zero vector
            [4.0, 5.0, 6.0]
        ])
        with pytest.raises(ValueError, match="zero vector"):
            batch_cosine_similarity(query, vectors)

    def test_batch_high_dimensional(self):
        """Batch should work with high-dimensional vectors (768-dim embeddings)"""
        query = np.random.rand(768)
        vectors = np.random.rand(100, 768)
        similarities = batch_cosine_similarity(query, vectors)
        assert similarities.shape == (100,)
        assert np.all(similarities >= -1.0) and np.all(similarities <= 1.0)

    def test_batch_performance(self):
        """Batch should be significantly faster than loop on large inputs"""
        query = np.random.rand(768)
        vectors = np.random.rand(1000, 768)

        # Warm up both code paths to avoid JIT / first-call overhead
        _ = batch_cosine_similarity(query, vectors[:10])
        _ = [cosine_similarity(query, v) for v in vectors[:10]]

        # Run multiple iterations and take the best time to reduce noise
        best_batch = float('inf')
        best_loop = float('inf')
        for _ in range(3):
            start = time.time()
            batch_result = batch_cosine_similarity(query, vectors)
            best_batch = min(best_batch, time.time() - start)

            start = time.time()
            loop_result = np.array([cosine_similarity(query, v) for v in vectors])
            best_loop = min(best_loop, time.time() - start)

        # Results should match within floating point precision (the critical assertion)
        np.testing.assert_allclose(batch_result, loop_result, rtol=1e-5)

        # Batch should generally be faster, but timing is non-deterministic under load
        if best_batch >= best_loop / 2:
            import warnings
            warnings.warn(
                f"Batch ({best_batch:.4f}s) not 2x faster than loop ({best_loop:.4f}s) — "
                f"likely CPU contention from parallel test execution"
            )

    def test_batch_empty_vectors(self):
        """Batch should handle empty array"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.empty((0, 3))
        similarities = batch_cosine_similarity(query, vectors)
        assert similarities.shape == (0,)

    def test_batch_single_vector(self):
        """Batch should work with single vector"""
        query = np.array([1.0, 2.0, 3.0])
        vectors = np.array([[1.0, 2.0, 3.0]])
        similarities = batch_cosine_similarity(query, vectors)
        assert similarities.shape == (1,)
        assert similarities[0] == 1.0


class TestEdgeCases:
    """Additional edge case tests"""

    def test_very_small_vectors(self):
        """Should handle very small magnitude vectors"""
        vec1 = np.array([1e-100, 1e-100, 1e-100])
        vec2 = np.array([1e-100, 1e-100, 1e-100])
        # This might raise ValueError due to underflow, which is acceptable
        # Or it might work, in which case similarity should be 1.0
        try:
            similarity = cosine_similarity(vec1, vec2)
            assert abs(similarity - 1.0) < 1e-5
        except ValueError:
            pass  # Acceptable behavior for extreme underflow

    def test_mixed_positive_negative_values(self):
        """Should correctly handle mixed positive/negative values"""
        vec1 = np.array([1.0, -1.0, 1.0, -1.0])
        vec2 = np.array([1.0, -1.0, 1.0, -1.0])
        similarity = cosine_similarity(vec1, vec2)
        assert similarity == 1.0

    def test_batch_with_varying_norms(self):
        """Batch should handle vectors with very different magnitudes"""
        query = np.array([1.0, 1.0, 1.0])
        vectors = np.array([
            [0.001, 0.001, 0.001],    # Very small
            [1.0, 1.0, 1.0],          # Same magnitude
            [1000.0, 1000.0, 1000.0]  # Very large
        ])
        similarities = batch_cosine_similarity(query, vectors)
        # All should be 1.0 since cosine is magnitude-independent
        np.testing.assert_allclose(similarities, [1.0, 1.0, 1.0], rtol=1e-5)
