"""
Unit tests for OntologyScorer (ADR-200 Phase 3a).

Tests the scoring algorithms:
- calculate_mass (Michaelis-Menten saturation)
- calculate_coherence (pairwise cosine similarity)
- calculate_exposure (epoch delta with adjacency weighting)
- calculate_protection (composite: mass × coherence - exposure)
- score_ontology / score_all_ontologies (pipeline)
"""

import pytest
import numpy as np
from unittest.mock import MagicMock


@pytest.fixture
def mock_client():
    """Create a mock AGE client for scorer tests."""
    return MagicMock()


@pytest.fixture
def scorer(mock_client):
    """Create an OntologyScorer with mock client."""
    from api.app.lib.ontology_scorer import OntologyScorer
    return OntologyScorer(mock_client)


@pytest.mark.unit
class TestCalculateMass:
    """Tests for mass scoring (Michaelis-Menten saturation)."""

    def test_empty_ontology_returns_zero(self, scorer):
        """Empty ontology has zero mass."""
        stats = {"concept_count": 0, "source_count": 0, "internal_relationship_count": 0}
        assert scorer.calculate_mass(stats) == 0.0

    def test_small_ontology_low_mass(self, scorer):
        """Small ontology has low mass (well under saturation)."""
        stats = {"concept_count": 5, "source_count": 2, "internal_relationship_count": 3}
        mass = scorer.calculate_mass(stats)
        assert 0.0 < mass < 0.3

    def test_medium_ontology_moderate_mass(self, scorer):
        """Medium ontology has moderate mass (~0.5)."""
        stats = {"concept_count": 50, "source_count": 20, "internal_relationship_count": 50}
        mass = scorer.calculate_mass(stats)
        # composite = 50/50 + 20/20 + 50/50 = 3.0, mass = 3/(3+2) = 0.6
        assert 0.5 < mass < 0.7

    def test_large_ontology_high_mass(self, scorer):
        """Large ontology approaches saturation (diminishing returns)."""
        stats = {"concept_count": 500, "source_count": 200, "internal_relationship_count": 500}
        mass = scorer.calculate_mass(stats)
        # composite = 10 + 10 + 10 = 30, mass = 30/32 ≈ 0.94
        assert mass > 0.9

    def test_mass_never_exceeds_one(self, scorer):
        """Mass asymptotically approaches but never exceeds 1.0."""
        stats = {"concept_count": 10000, "source_count": 10000, "internal_relationship_count": 10000}
        mass = scorer.calculate_mass(stats)
        assert mass < 1.0

    def test_mass_missing_fields_default_zero(self, scorer):
        """Missing stats fields default to 0."""
        stats = {}
        assert scorer.calculate_mass(stats) == 0.0


@pytest.mark.unit
class TestCalculateCoherence:
    """Tests for coherence scoring (pairwise cosine similarity)."""

    def test_too_few_concepts_returns_zero(self, scorer, mock_client):
        """Less than 2 concepts returns zero coherence."""
        mock_client.get_ontology_concept_embeddings.return_value = [
            {"concept_id": "c1", "label": "Solo", "embedding": [1.0, 0.0]}
        ]

        assert scorer.calculate_coherence("test") == 0.0

    def test_identical_embeddings_high_coherence(self, scorer, mock_client):
        """Identical embeddings produce coherence close to 1.0."""
        emb = [1.0, 0.0, 0.0]
        mock_client.get_ontology_concept_embeddings.return_value = [
            {"concept_id": "c1", "label": "A", "embedding": emb},
            {"concept_id": "c2", "label": "B", "embedding": emb},
            {"concept_id": "c3", "label": "C", "embedding": emb},
        ]

        coherence = scorer.calculate_coherence("test")
        assert coherence > 0.99

    def test_orthogonal_embeddings_low_coherence(self, scorer, mock_client):
        """Orthogonal embeddings produce zero coherence."""
        mock_client.get_ontology_concept_embeddings.return_value = [
            {"concept_id": "c1", "label": "A", "embedding": [1.0, 0.0, 0.0]},
            {"concept_id": "c2", "label": "B", "embedding": [0.0, 1.0, 0.0]},
            {"concept_id": "c3", "label": "C", "embedding": [0.0, 0.0, 1.0]},
        ]

        coherence = scorer.calculate_coherence("test")
        assert coherence == 0.0

    def test_no_embeddings_returns_zero(self, scorer, mock_client):
        """No concept embeddings returns zero."""
        mock_client.get_ontology_concept_embeddings.return_value = []

        assert scorer.calculate_coherence("test") == 0.0


@pytest.mark.unit
class TestCalculateExposure:
    """Tests for exposure scoring (epoch delta with adjacency)."""

    def test_new_ontology_zero_exposure(self, scorer, mock_client):
        """Just-created ontology has zero exposure."""
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 100, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 100
        mock_client.get_cross_ontology_affinity.return_value = []

        result = scorer.calculate_exposure("new-onto")

        assert result["raw_exposure"] == 0.0
        assert result["weighted_exposure"] == 0.0

    def test_old_ontology_high_exposure(self, scorer, mock_client):
        """Old ontology with large epoch delta has high exposure."""
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 0, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 200
        mock_client.get_cross_ontology_affinity.return_value = []

        result = scorer.calculate_exposure("old-onto")

        # raw_exposure = 200 / (200 + 50) = 0.8
        assert result["raw_exposure"] > 0.7

    def test_nonexistent_ontology_zero(self, scorer, mock_client):
        """Nonexistent ontology returns zeros."""
        mock_client.get_ontology_node.return_value = None

        result = scorer.calculate_exposure("ghost")

        assert result["raw_exposure"] == 0.0


@pytest.mark.unit
class TestCalculateProtection:
    """Tests for protection scoring (composite)."""

    def test_high_mass_high_coherence_positive(self, scorer):
        """High mass + high coherence = positive protection."""
        protection = scorer.calculate_protection(0.9, 0.9, 0.0)
        assert protection > 0.5

    def test_zero_mass_low_protection(self, scorer):
        """Zero mass produces low protection."""
        protection = scorer.calculate_protection(0.0, 0.5, 0.0)
        # sigmoid(0) = 0.5, with rescaling sigmoid(0*4-2) = sigmoid(-2) ≈ 0.12
        assert protection < 0.2

    def test_high_exposure_reduces_protection(self, scorer):
        """High exposure erodes protection."""
        high_protection = scorer.calculate_protection(0.8, 0.8, 0.0)
        low_protection = scorer.calculate_protection(0.8, 0.8, 0.9)
        assert low_protection < high_protection

    def test_protection_can_go_negative(self, scorer):
        """Severely failing ontology can have negative protection."""
        protection = scorer.calculate_protection(0.0, 0.0, 1.0)
        assert protection < 0


@pytest.mark.unit
class TestScoreOntology:
    """Tests for score_ontology() pipeline."""

    def test_score_returns_all_fields(self, scorer, mock_client):
        """Scoring returns all expected fields."""
        mock_client.get_ontology_stats.return_value = {
            "ontology": "test",
            "concept_count": 10,
            "source_count": 5,
            "internal_relationship_count": 8,
        }
        mock_client.get_ontology_concept_embeddings.return_value = []
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 0, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 10
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.update_ontology_scores.return_value = True

        scores = scorer.score_ontology("test")

        assert scores is not None
        assert "mass_score" in scores
        assert "coherence_score" in scores
        assert "raw_exposure" in scores
        assert "weighted_exposure" in scores
        assert "protection_score" in scores
        assert "last_evaluated_epoch" in scores
        assert scores["ontology"] == "test"

    def test_score_nonexistent_returns_none(self, scorer, mock_client):
        """Scoring nonexistent ontology returns None."""
        mock_client.get_ontology_stats.return_value = None

        assert scorer.score_ontology("ghost") is None

    def test_score_caches_results(self, scorer, mock_client):
        """Scoring calls update_ontology_scores to cache."""
        mock_client.get_ontology_stats.return_value = {
            "ontology": "test",
            "concept_count": 0,
            "source_count": 0,
            "internal_relationship_count": 0,
        }
        mock_client.get_ontology_concept_embeddings.return_value = []
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 0, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 0
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.update_ontology_scores.return_value = True

        scorer.score_ontology("test")

        mock_client.update_ontology_scores.assert_called_once()


@pytest.mark.unit
class TestScoreAllOntologies:
    """Tests for score_all_ontologies()."""

    def test_scores_all_nodes(self, scorer, mock_client):
        """Iterates through all ontology nodes."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "onto-1"},
            {"name": "onto-2"},
        ]
        mock_client.get_ontology_stats.return_value = {
            "ontology": "x",
            "concept_count": 0,
            "source_count": 0,
            "internal_relationship_count": 0,
        }
        mock_client.get_ontology_concept_embeddings.return_value = []
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 0, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 0
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.update_ontology_scores.return_value = True

        results = scorer.score_all_ontologies()

        assert len(results) == 2

    def test_continues_on_individual_failure(self, scorer, mock_client):
        """Failures for one ontology don't stop scoring others."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "good"},
            {"name": "bad"},
        ]
        # First call succeeds, second fails
        mock_client.get_ontology_stats.side_effect = [
            {"ontology": "good", "concept_count": 0, "source_count": 0, "internal_relationship_count": 0},
            None,  # "bad" doesn't exist
        ]
        mock_client.get_ontology_concept_embeddings.return_value = []
        mock_client.get_ontology_node.return_value = {
            "creation_epoch": 0, "lifecycle_state": "active"
        }
        mock_client.get_current_epoch.return_value = 0
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.update_ontology_scores.return_value = True

        results = scorer.score_all_ontologies()

        # Only "good" scored successfully
        assert len(results) == 1


@pytest.mark.unit
class TestCosineSimilarity:
    """Tests for the _cosine_similarity helper."""

    def test_identical_vectors(self, scorer):
        """Identical vectors have similarity 1.0."""
        v = np.array([1.0, 2.0, 3.0])
        assert scorer._cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self, scorer):
        """Orthogonal vectors have similarity 0.0."""
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        assert scorer._cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_zero_vector(self, scorer):
        """Zero vector returns 0.0 (no division by zero)."""
        v1 = np.array([0.0, 0.0])
        v2 = np.array([1.0, 0.0])
        assert scorer._cosine_similarity(v1, v2) == 0.0

    def test_negative_similarity_clamped(self, scorer):
        """Negative cosine similarity clamped to 0.0."""
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-1.0, 0.0])
        assert scorer._cosine_similarity(v1, v2) == 0.0


# ==========================================================================
# ADR-200 Phase 5: Edge Derivation Tests
# ==========================================================================


@pytest.mark.unit
class TestDeriveOntologyEdges:
    """Tests for derive_ontology_edges()."""

    def test_derives_overlaps_for_symmetric_affinity(self, scorer, mock_client):
        """Symmetric high affinity between ontologies produces OVERLAPS edges."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "alpha", "lifecycle_state": "active"},
            {"name": "beta", "lifecycle_state": "active"},
        ]
        # Both directions: alpha→beta and beta→alpha are high and symmetric
        mock_client.get_cross_ontology_affinity.side_effect = lambda name, **kw: [
            {"other_ontology": "beta" if name == "alpha" else "alpha",
             "affinity_score": 0.5, "shared_concept_count": 20, "total_concepts": 40}
        ]
        mock_client.delete_all_derived_ontology_edges.return_value = 0
        mock_client.upsert_ontology_edge.return_value = True
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges(
            overlap_threshold=0.1, specializes_threshold=0.3
        )

        assert result["edges_created"] > 0
        # Should have called upsert for OVERLAPS
        calls = mock_client.upsert_ontology_edge.call_args_list
        edge_types = [c.kwargs.get("edge_type") or c[1].get("edge_type", "") for c in calls]
        assert "OVERLAPS" in edge_types

    def test_derives_specializes_for_asymmetric_affinity(self, scorer, mock_client):
        """When A→B affinity is high but B→A is low, A SPECIALIZES B."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "subset", "lifecycle_state": "active"},
            {"name": "superset", "lifecycle_state": "active"},
        ]
        # subset→superset: high affinity (subset is part of superset)
        # superset→subset: low affinity (superset is much bigger)
        def mock_affinity(name, **kw):
            if name == "subset":
                return [{"other_ontology": "superset", "affinity_score": 0.8,
                         "shared_concept_count": 20, "total_concepts": 25}]
            else:
                return [{"other_ontology": "subset", "affinity_score": 0.1,
                         "shared_concept_count": 20, "total_concepts": 200}]

        mock_client.get_cross_ontology_affinity.side_effect = mock_affinity
        mock_client.delete_all_derived_ontology_edges.return_value = 0
        mock_client.upsert_ontology_edge.return_value = True
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges(
            overlap_threshold=0.1, specializes_threshold=0.3
        )

        assert result["edges_created"] > 0
        calls = mock_client.upsert_ontology_edge.call_args_list
        edge_types = [c.kwargs.get("edge_type") or c[1].get("edge_type", "") for c in calls]
        assert "SPECIALIZES" in edge_types or "GENERALIZES" in edge_types

    def test_skips_frozen_ontologies(self, scorer, mock_client):
        """Frozen ontologies are excluded from edge derivation."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "active-one", "lifecycle_state": "active"},
            {"name": "frozen-one", "lifecycle_state": "frozen"},
        ]
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.delete_all_derived_ontology_edges.return_value = 0
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges()

        # Only active ontologies should be queried for affinity
        affinity_calls = mock_client.get_cross_ontology_affinity.call_args_list
        queried_names = [c.args[0] if c.args else c.kwargs.get("ontology_name") for c in affinity_calls]
        assert "frozen-one" not in queried_names

    def test_below_threshold_creates_no_edges(self, scorer, mock_client):
        """Affinity below overlap_threshold creates no edges."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "a", "lifecycle_state": "active"},
            {"name": "b", "lifecycle_state": "active"},
        ]
        mock_client.get_cross_ontology_affinity.return_value = [
            {"other_ontology": "b", "affinity_score": 0.01,
             "shared_concept_count": 1, "total_concepts": 100}
        ]
        mock_client.delete_all_derived_ontology_edges.return_value = 0
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges(overlap_threshold=0.1)

        assert result["edges_created"] == 0
        mock_client.upsert_ontology_edge.assert_not_called()

    def test_deletes_stale_edges_before_creating(self, scorer, mock_client):
        """All derived edges are deleted before new ones are created."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "a", "lifecycle_state": "active"},
            {"name": "b", "lifecycle_state": "active"},
        ]
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.delete_all_derived_ontology_edges.return_value = 5
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges()

        assert result["edges_deleted"] == 5
        mock_client.delete_all_derived_ontology_edges.assert_called_once()

    def test_single_ontology_creates_no_edges(self, scorer, mock_client):
        """A single ontology has no pairs to compare."""
        mock_client.list_ontology_nodes.return_value = [
            {"name": "solo", "lifecycle_state": "active"},
        ]
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.delete_all_derived_ontology_edges.return_value = 0
        mock_client.get_current_epoch.return_value = 10

        result = scorer.derive_ontology_edges()

        assert result["edges_created"] == 0
