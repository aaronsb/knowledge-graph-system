"""
Unit tests for BreathingManager (ADR-200 Phase 3b).

Tests the breathing cycle orchestration:
- Candidate identification (demotion, promotion)
- Threshold filtering and lifecycle exclusion
- Dry-run vs full cycle behavior
- Proposal storage
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from api.app.services.breathing_manager import BreathingManager
from api.app.lib.breathing_evaluator import PromotionDecision, DemotionDecision


@pytest.fixture
def mock_client():
    """Create a mock AGE client."""
    client = MagicMock()
    client.get_current_epoch.return_value = 20

    # Default: connection pool mock for _store_proposal
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = mock_conn

    return client


@pytest.fixture
def mock_scorer():
    """Create a mock OntologyScorer."""
    scorer = MagicMock()
    scorer.score_all_ontologies.return_value = []
    scorer.recompute_all_centroids.return_value = 0
    return scorer


@pytest.fixture
def manager(mock_client, mock_scorer):
    """Create a BreathingManager with mocked dependencies."""
    return BreathingManager(mock_client, mock_scorer, ai_provider=None)


@pytest.mark.unit
class TestFindDemotionCandidates:
    """Tests for _find_demotion_candidates."""

    def test_no_candidates_above_threshold(self, manager, mock_client):
        """No demotion candidates when all scores are above threshold."""
        scores = [
            {"ontology": "healthy", "protection_score": 0.5},
            {"ontology": "also-healthy", "protection_score": 0.3},
        ]
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 0

    def test_low_protection_becomes_candidate(self, manager, mock_client):
        """Ontology with protection below threshold becomes a candidate."""
        scores = [
            {"ontology": "struggling", "protection_score": 0.05},
            {"ontology": "healthy", "protection_score": 0.5},
        ]
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 1
        assert result[0]["ontology"] == "struggling"

    def test_pinned_excluded(self, manager, mock_client):
        """Pinned ontologies are excluded from demotion."""
        scores = [{"ontology": "pinned-one", "protection_score": 0.01}]
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "pinned"}

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 0

    def test_frozen_excluded(self, manager, mock_client):
        """Frozen ontologies are excluded from demotion."""
        scores = [{"ontology": "frozen-one", "protection_score": 0.01}]
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "frozen"}

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 0

    def test_sorted_by_protection_ascending(self, manager, mock_client):
        """Candidates sorted by protection (worst first)."""
        scores = [
            {"ontology": "bad", "protection_score": 0.10},
            {"ontology": "worse", "protection_score": 0.02},
            {"ontology": "worst", "protection_score": -0.05},
        ]
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 3
        assert result[0]["ontology"] == "worst"
        assert result[1]["ontology"] == "worse"
        assert result[2]["ontology"] == "bad"

    def test_missing_node_skipped(self, manager, mock_client):
        """Ontology with no graph node is skipped."""
        scores = [{"ontology": "ghost", "protection_score": 0.01}]
        mock_client.get_ontology_node.return_value = None

        result = manager._find_demotion_candidates(scores, threshold=0.15)
        assert len(result) == 0


@pytest.mark.unit
class TestFindPromotionCandidates:
    """Tests for _find_promotion_candidates."""

    def test_no_candidates_below_threshold(self, manager, mock_client):
        """No promotion candidates when all concepts are below degree threshold."""
        scores = [{"ontology": "small"}]
        mock_client.get_concept_degree_ranking.return_value = [
            {"concept_id": "c1", "label": "Concept A", "degree": 3, "description": ""},
        ]

        result = manager._find_promotion_candidates(scores, min_degree=10)
        assert len(result) == 0

    def test_high_degree_becomes_candidate(self, manager, mock_client):
        """High-degree concept becomes a promotion candidate."""
        scores = [{"ontology": "big-domain"}]
        mock_client.get_concept_degree_ranking.return_value = [
            {"concept_id": "c1", "label": "PostgreSQL", "degree": 25, "description": "RDBMS"},
        ]

        result = manager._find_promotion_candidates(scores, min_degree=10)
        assert len(result) == 1
        assert result[0]["label"] == "PostgreSQL"
        assert result[0]["degree"] == 25

    def test_existing_ontology_name_excluded(self, manager, mock_client):
        """Concept matching an existing ontology name (case-insensitive) is excluded."""
        scores = [
            {"ontology": "database-architecture"},
            {"ontology": "distributed-systems"},
        ]
        # Label must match ontology name exactly (lowercased) to be excluded
        mock_client.get_concept_degree_ranking.return_value = [
            {"concept_id": "c1", "label": "database-architecture", "degree": 30, "description": ""},
        ]

        result = manager._find_promotion_candidates(scores, min_degree=10)
        assert len(result) == 0

    def test_sorted_by_degree_descending(self, manager, mock_client):
        """Candidates sorted by degree (highest first)."""
        scores = [{"ontology": "domain"}]
        mock_client.get_concept_degree_ranking.return_value = [
            {"concept_id": "c1", "label": "A", "degree": 15, "description": ""},
            {"concept_id": "c2", "label": "B", "degree": 30, "description": ""},
            {"concept_id": "c3", "label": "C", "degree": 20, "description": ""},
        ]

        result = manager._find_promotion_candidates(scores, min_degree=10)
        assert len(result) == 3
        assert result[0]["label"] == "B"
        assert result[1]["label"] == "C"
        assert result[2]["label"] == "A"


@pytest.mark.unit
class TestBreathingCycleDryRun:
    """Tests for run_breathing_cycle in dry-run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_candidates_without_proposals(self, manager, mock_scorer, mock_client):
        """Dry run returns candidate counts but generates no proposals."""
        mock_scorer.score_all_ontologies.return_value = [
            {"ontology": "weak", "protection_score": 0.05},
            {"ontology": "strong", "protection_score": 0.8},
        ]
        mock_scorer.recompute_all_centroids.return_value = 2
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}
        mock_client.get_concept_degree_ranking.return_value = []

        result = await manager.run_breathing_cycle(dry_run=True)

        assert result["dry_run"] is True
        assert result["proposals_generated"] == 0
        assert result["scores_updated"] == 2
        assert result["centroids_updated"] == 2
        assert result["demotion_candidates"] == 1

    @pytest.mark.asyncio
    async def test_dry_run_includes_candidate_details(self, manager, mock_scorer, mock_client):
        """Dry run includes detailed candidate information."""
        mock_scorer.score_all_ontologies.return_value = [
            {"ontology": "weak", "protection_score": 0.05},
        ]
        mock_scorer.recompute_all_centroids.return_value = 0
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}
        mock_client.get_concept_degree_ranking.return_value = []

        result = await manager.run_breathing_cycle(dry_run=True)

        assert "candidates" in result
        assert len(result["candidates"]["demotions"]) == 1
        assert result["candidates"]["demotions"][0]["ontology"] == "weak"


@pytest.mark.unit
class TestBreathingCycleFull:
    """Tests for run_breathing_cycle in full (non-dry-run) mode."""

    @pytest.mark.asyncio
    async def test_full_cycle_with_no_candidates(self, manager, mock_scorer, mock_client):
        """Full cycle with no candidates generates no proposals."""
        mock_scorer.score_all_ontologies.return_value = [
            {"ontology": "healthy", "protection_score": 0.8},
        ]
        mock_scorer.recompute_all_centroids.return_value = 1
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}
        mock_client.get_concept_degree_ranking.return_value = []

        result = await manager.run_breathing_cycle()

        assert result["dry_run"] is False
        assert result["proposals_generated"] == 0
        assert result["demotion_candidates"] == 0
        assert result["promotion_candidates"] == 0

    @pytest.mark.asyncio
    async def test_max_proposals_cap(self, manager, mock_scorer, mock_client):
        """Proposals are capped at max_proposals."""
        # 5 demotion candidates but max_proposals=2
        mock_scorer.score_all_ontologies.return_value = [
            {"ontology": f"weak-{i}", "protection_score": 0.01 * i}
            for i in range(5)
        ]
        mock_scorer.recompute_all_centroids.return_value = 0
        mock_client.get_ontology_node.return_value = {"lifecycle_state": "active"}
        mock_client.get_concept_degree_ranking.return_value = []
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.get_ontology_stats.return_value = {"concept_count": 5}

        result = await manager.run_breathing_cycle(
            demotion_threshold=0.15,
            max_proposals=2,
        )

        assert result["proposals_generated"] <= 2


@pytest.mark.unit
class TestStoreProposal:
    """Tests for _store_proposal."""

    def test_stores_demotion_proposal(self, manager, mock_client):
        """Demotion proposal is stored with correct fields."""
        proposal_id = manager._store_proposal(
            proposal_type="demotion",
            ontology_name="weak-domain",
            reasoning="Too small to justify existence",
            epoch=20,
            target_ontology="parent-domain",
            mass_score=0.05,
            coherence_score=0.3,
            protection_score=-0.1,
        )

        assert proposal_id == 1  # From mock_cursor.fetchone = (1,)

    def test_stores_promotion_proposal(self, manager, mock_client):
        """Promotion proposal is stored with correct fields."""
        proposal_id = manager._store_proposal(
            proposal_type="promotion",
            ontology_name="big-domain",
            reasoning="PostgreSQL is a natural nucleus",
            epoch=20,
            anchor_concept_id="c_abc123",
        )

        assert proposal_id == 1

    def test_db_error_returns_none(self, manager, mock_client):
        """Database error returns None instead of raising."""
        mock_client.pool.getconn.side_effect = Exception("Connection failed")

        proposal_id = manager._store_proposal(
            proposal_type="demotion",
            ontology_name="test",
            reasoning="test",
            epoch=20,
        )

        assert proposal_id is None
