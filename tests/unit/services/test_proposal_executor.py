"""
Unit tests for ProposalExecutor (ADR-200 Phase 4).

Tests execution logic for promotion and demotion proposals:
- Promotion: validation, ontology creation, ANCHORED_BY, source reassignment
- Demotion: validation, absorption target cascading fallback, dissolve
- Precondition failures (concept gone, ontology already exists, frozen, etc.)
"""

import pytest
from unittest.mock import MagicMock, patch

from api.app.services.proposal_executor import ProposalExecutor


@pytest.fixture
def mock_client():
    """Create a mock AGE client with default behaviors."""
    client = MagicMock()

    # Default pool mock for _get_primordial_pool_name
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("primordial",)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = mock_conn

    return client


@pytest.fixture
def executor(mock_client):
    return ProposalExecutor(mock_client)


def _promotion_proposal(**overrides):
    """Create a test promotion proposal."""
    base = {
        "id": 1,
        "proposal_type": "promotion",
        "ontology_name": "parent-ontology",
        "anchor_concept_id": "c_abc123",
        "target_ontology": None,
        "reasoning": "High degree concept",
        "suggested_name": "New Domain",
        "suggested_description": "A new knowledge domain",
    }
    base.update(overrides)
    return base


def _demotion_proposal(**overrides):
    """Create a test demotion proposal."""
    base = {
        "id": 2,
        "proposal_type": "demotion",
        "ontology_name": "weak-ontology",
        "anchor_concept_id": None,
        "target_ontology": "strong-ontology",
        "reasoning": "Low protection score",
    }
    base.update(overrides)
    return base


@pytest.mark.unit
class TestExecutePromotion:
    """Tests for ProposalExecutor.execute_promotion()."""

    def test_successful_promotion(self, executor, mock_client):
        """Full promotion: create node, anchor edge, reassign sources."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Test Concept",
            "description": "A test concept",
            "embedding": [0.1] * 10,
        }
        mock_client.get_ontology_node.return_value = None  # name not taken
        mock_client.create_ontology_node.return_value = {"name": "New Domain"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = ["s1", "s2", "s3"]
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 3,
            "success": True,
            "error": None,
        }

        result = executor.execute_promotion(_promotion_proposal())

        assert result["success"] is True
        assert result["ontology_created"] == "New Domain"
        assert result["sources_reassigned"] == 3
        assert result["anchored"] is True
        mock_client.create_ontology_node.assert_called_once()
        mock_client.create_anchored_by_edge.assert_called_once_with("New Domain", "c_abc123")

    def test_promotion_missing_anchor_concept(self, executor, mock_client):
        """Promotion fails if anchor concept no longer exists."""
        mock_client.get_concept_node.return_value = None

        result = executor.execute_promotion(_promotion_proposal())

        assert result["success"] is False
        assert "no longer exists" in result["error"]

    def test_promotion_name_already_taken(self, executor, mock_client):
        """Promotion fails if ontology name is already in use."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Existing",
            "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = {"name": "New Domain"}

        result = executor.execute_promotion(_promotion_proposal())

        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_promotion_uses_label_when_no_suggested_name(self, executor, mock_client):
        """Falls back to concept label when suggested_name is None."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Fallback Label",
            "description": "desc",
            "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "Fallback Label"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = []
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 0, "success": True, "error": None,
        }

        result = executor.execute_promotion(
            _promotion_proposal(suggested_name=None)
        )

        assert result["success"] is True
        assert result["ontology_created"] == "Fallback Label"

    def test_promotion_no_sources_still_succeeds(self, executor, mock_client):
        """Promotion with no first-order sources still creates the ontology."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Isolated",
            "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "New Domain"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = []

        result = executor.execute_promotion(_promotion_proposal())

        assert result["success"] is True
        assert result["sources_reassigned"] == 0
        mock_client.reassign_sources.assert_not_called()

    def test_promotion_partial_failure_on_reassign(self, executor, mock_client):
        """Reports partial failure if sources can't be reassigned."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Test",
            "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "New Domain"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = ["s1"]
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 0,
            "success": False,
            "error": "Connection lost",
        }

        result = executor.execute_promotion(_promotion_proposal())

        assert result["success"] is False
        assert result.get("partial") is True
        assert result["ontology_created"] == "New Domain"

    def test_promotion_missing_anchor_id(self, executor):
        """Fails cleanly if proposal has no anchor_concept_id."""
        result = executor.execute_promotion(
            _promotion_proposal(anchor_concept_id=None)
        )
        assert result["success"] is False
        assert "missing" in result["error"].lower()


@pytest.mark.unit
class TestExecuteDemotion:
    """Tests for ProposalExecutor.execute_demotion()."""

    def test_successful_demotion(self, executor, mock_client):
        """Full demotion: validate, dissolve into target."""
        mock_client.get_ontology_node.side_effect = [
            {"name": "weak-ontology", "lifecycle_state": "active"},  # source validation
            {"name": "strong-ontology", "lifecycle_state": "active"},  # _determine target
            {"name": "strong-ontology", "lifecycle_state": "active"},  # target verification
        ]
        mock_client.dissolve_ontology.return_value = {
            "dissolved_ontology": "weak-ontology",
            "sources_reassigned": 5,
            "ontology_node_deleted": True,
            "reassignment_targets": ["strong-ontology"],
            "success": True,
            "error": None,
        }

        result = executor.execute_demotion(_demotion_proposal())

        assert result["success"] is True
        assert result["absorbed_into"] == "strong-ontology"
        assert result["sources_reassigned"] == 5
        mock_client.dissolve_ontology.assert_called_once_with(
            "weak-ontology", "strong-ontology"
        )

    def test_demotion_ontology_gone(self, executor, mock_client):
        """Demotion fails if ontology no longer exists."""
        mock_client.get_ontology_node.return_value = None

        result = executor.execute_demotion(_demotion_proposal())

        assert result["success"] is False
        assert "no longer exists" in result["error"]

    def test_demotion_pinned_ontology(self, executor, mock_client):
        """Demotion fails for pinned ontologies."""
        mock_client.get_ontology_node.return_value = {
            "name": "weak-ontology",
            "lifecycle_state": "pinned",
        }

        result = executor.execute_demotion(_demotion_proposal())

        assert result["success"] is False
        assert "pinned" in result["error"]

    def test_demotion_frozen_ontology(self, executor, mock_client):
        """Demotion fails for frozen ontologies."""
        mock_client.get_ontology_node.return_value = {
            "name": "weak-ontology",
            "lifecycle_state": "frozen",
        }

        result = executor.execute_demotion(_demotion_proposal())

        assert result["success"] is False
        assert "frozen" in result["error"]


@pytest.mark.unit
class TestAbsorptionTargetFallback:
    """Tests for _determine_absorption_target cascading fallback."""

    def test_uses_proposal_target_first(self, executor, mock_client):
        """Priority 1: proposal's target_ontology."""
        mock_client.get_ontology_node.return_value = {
            "name": "proposed-target",
            "lifecycle_state": "active",
        }

        target = executor._determine_absorption_target(
            "weak-ontology", "proposed-target"
        )
        assert target == "proposed-target"

    def test_skips_frozen_proposed_target(self, executor, mock_client):
        """Falls through if proposed target is frozen."""
        mock_client.get_ontology_node.return_value = {
            "name": "proposed-target",
            "lifecycle_state": "frozen",
        }
        mock_client.get_ontology_edges.return_value = []
        mock_client.get_cross_ontology_affinity.return_value = []

        target = executor._determine_absorption_target(
            "weak-ontology", "proposed-target"
        )
        # Falls through to primordial pool
        assert target == "primordial"

    def test_falls_back_to_overlaps_edge(self, executor, mock_client):
        """Priority 2: highest OVERLAPS edge from Phase 5."""
        mock_client.get_ontology_node.return_value = None  # proposed target gone
        mock_client.get_ontology_edges.return_value = [
            {
                "from_ontology": "weak-ontology",
                "to_ontology": "overlapping",
                "edge_type": "OVERLAPS",
                "score": 0.8,
            },
        ]

        target = executor._determine_absorption_target(
            "weak-ontology", "gone-target"
        )
        assert target == "overlapping"

    def test_falls_back_to_affinity(self, executor, mock_client):
        """Priority 3: cross-ontology affinity query."""
        mock_client.get_ontology_node.return_value = None
        mock_client.get_ontology_edges.return_value = []  # no Phase 5 edges
        mock_client.get_cross_ontology_affinity.return_value = [
            {"other_ontology": "affine-target", "affinity_score": 0.6}
        ]

        target = executor._determine_absorption_target(
            "weak-ontology", "gone-target"
        )
        assert target == "affine-target"

    def test_falls_back_to_primordial(self, executor, mock_client):
        """Priority 4: primordial pool as last resort."""
        mock_client.get_ontology_node.return_value = None
        mock_client.get_ontology_edges.return_value = []
        mock_client.get_cross_ontology_affinity.return_value = []

        target = executor._determine_absorption_target(
            "weak-ontology", "gone-target"
        )
        assert target == "primordial"

    def test_no_proposed_target_skips_to_edges(self, executor, mock_client):
        """When proposed_target is None, starts at Phase 5 edges."""
        mock_client.get_ontology_edges.return_value = [
            {
                "from_ontology": "weak-ontology",
                "to_ontology": "via-edges",
                "edge_type": "OVERLAPS",
                "score": 0.5,
            },
        ]

        target = executor._determine_absorption_target(
            "weak-ontology", None
        )
        assert target == "via-edges"
