"""Unit tests for DBSCAN clustering and cluster naming in EmbeddingProjectionService.

Tests _compute_clusters() and _name_clusters() which are pure-function-like methods
that operate on numpy arrays without needing a database connection.
"""

import numpy as np
import pytest

from api.app.services.embedding_projection_service import EmbeddingProjectionService


@pytest.fixture
def service():
    """Create service with no db client (only clustering methods need no db)."""
    return EmbeddingProjectionService(age_client=None)  # type: ignore[arg-type]


class TestComputeClusters:
    """Tests for _compute_clusters()."""

    def test_too_few_points_returns_all_noise(self, service):
        """With fewer points than min_samples, everything is noise."""
        projection = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32)
        result = service._compute_clusters(projection, min_samples=5)

        assert result["cluster_count"] == 0
        assert result["noise_count"] == 2
        assert len(result["cluster_labels"]) == 2
        assert all(label == -1 for label in result["cluster_labels"])

    def test_tight_cluster_detected(self, service):
        """Points packed tightly should form at least one cluster."""
        rng = np.random.RandomState(42)
        # 50 points in a tight ball + 50 in another
        cluster_a = rng.normal(0, 0.1, (50, 3))
        cluster_b = rng.normal(10, 0.1, (50, 3))
        projection = np.vstack([cluster_a, cluster_b]).astype(np.float32)

        result = service._compute_clusters(projection, min_samples=5)

        assert result["cluster_count"] >= 2
        assert result["eps_used"] > 0
        # Cluster sizes should be str keys
        for key in result["cluster_sizes"]:
            assert isinstance(key, str)

    def test_all_same_point_single_cluster(self, service):
        """Identical points should form one cluster."""
        projection = np.zeros((20, 3), dtype=np.float32)
        result = service._compute_clusters(projection, min_samples=5)

        assert result["cluster_count"] == 1
        assert result["noise_count"] == 0

    def test_noise_count_consistency(self, service):
        """noise_count + sum(cluster_sizes) should equal total points."""
        rng = np.random.RandomState(123)
        projection = rng.randn(100, 3).astype(np.float32)
        result = service._compute_clusters(projection, min_samples=5)

        total_clustered = sum(result["cluster_sizes"].values())
        assert total_clustered + result["noise_count"] == 100

    def test_returns_expected_keys(self, service):
        """Result dict should have all expected keys."""
        projection = np.zeros((20, 3), dtype=np.float32)
        result = service._compute_clusters(projection, min_samples=5)

        expected_keys = {"cluster_labels", "cluster_count", "cluster_sizes", "eps_used", "noise_count"}
        assert set(result.keys()) == expected_keys


class TestNameClusters:
    """Tests for _name_clusters()."""

    def test_empty_labels_returns_empty(self, service):
        """All noise (-1) should return empty dict."""
        labels = np.array([-1, -1, -1])
        items = [{"label": "foo"}, {"label": "bar"}, {"label": "baz"}]
        result = service._name_clusters(labels, items)
        assert result == {}

    def test_single_cluster_names_by_frequency(self, service):
        """Single cluster uses frequency ranking (no IDF)."""
        labels = np.array([0, 0, 0, 0])
        items = [
            {"label": "machine learning algorithms"},
            {"label": "machine learning models"},
            {"label": "deep learning algorithms"},
            {"label": "machine learning training"},
        ]
        result = service._name_clusters(labels, items)
        assert "0" in result
        name = result["0"].lower()
        # "machine" appears 3 times, "learning" appears 4 times — both should appear
        assert "learning" in name or "machine" in name

    def test_two_clusters_idf_distinguishes(self, service):
        """IDF scoring should pick terms unique to each cluster."""
        labels = np.array([0, 0, 0, 1, 1, 1])
        items = [
            {"label": "quantum physics experiment"},
            {"label": "quantum mechanics theory"},
            {"label": "quantum entanglement research"},
            {"label": "economic market analysis"},
            {"label": "economic trade policy"},
            {"label": "economic growth forecast"},
        ]
        result = service._name_clusters(labels, items)
        assert "0" in result
        assert "1" in result
        # Cluster 0 should mention quantum-related terms
        assert "quantum" in result["0"].lower()
        # Cluster 1 should mention economic-related terms
        assert "economic" in result["1"].lower()

    def test_stop_words_filtered(self, service):
        """Stop words should not appear in cluster names."""
        labels = np.array([0, 0, 0])
        items = [
            {"label": "the big analysis of data"},
            {"label": "the big study of data"},
            {"label": "the big review of data"},
        ]
        result = service._name_clusters(labels, items)
        name_words = result["0"].lower().split()
        # "the", "of" are stop words, should not appear
        assert "the" not in name_words
        assert "of" not in name_words

    def test_str_keys_in_result(self, service):
        """Result dict should use str keys to match Pydantic model."""
        labels = np.array([0, 0, 0, 1, 1, 1])
        items = [{"label": f"concept {i}"} for i in range(6)]
        result = service._name_clusters(labels, items)
        for key in result:
            assert isinstance(key, str)

    def test_missing_labels_fallback(self, service):
        """Items with empty labels should still get a name."""
        labels = np.array([0, 0, 0, 0, 0])
        items = [{"label": ""} for _ in range(5)]
        result = service._name_clusters(labels, items)
        assert "0" in result
        assert "Cluster 0" in result["0"]
