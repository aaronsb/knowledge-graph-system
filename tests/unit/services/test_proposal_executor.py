"""
Unit tests for ProposalExecutor (ADR-200 Phase 4 / ADR-206).

Tests execution logic for the closed 6-verb annealing vocabulary:
- CLEAVE       : split parent ontology around an anchor concept
- DISSOLVE     : per-source affinity routing + force_primordial (#252)
- MERGE        : fold ≥2 donors into a target
- RENAME       : rename an ontology
- NO_ACTION    : record a deliberate no-op
- ESCALATE     : record an escalation (no graph mutation)

Plus legacy-shim coverage: execute_promotion/execute_demotion still
delegate to execute_cleave/execute_dissolve.
"""

import pytest
from unittest.mock import MagicMock, patch

from api.app.services.proposal_executor import ProposalExecutor


@pytest.fixture
def mock_client():
    """Create a mock AGE client with default behaviors."""
    client = MagicMock()

    # Default pool mock for _get_primordial_pool_name and
    # _inflight_ingestion_jobs (PR-404 review, finding #2).
    # fetchone() → ("primordial",) for the pool-name query.
    # fetchall() → [] for the in-flight job query (no jobs by default).
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("primordial",)
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = mock_conn

    return client


@pytest.fixture
def executor(mock_client):
    return ProposalExecutor(mock_client)


# ---------------------------------------------------------------------------
# Proposal factories
# ---------------------------------------------------------------------------

def _legacy_promotion(**overrides):
    """v1 promotion proposal (no params JSONB) — exercises the fallback path."""
    base = {
        "id": 1,
        "proposal_type": "CLEAVE",  # post-normalization
        "ontology_name": "parent-ontology",
        "anchor_concept_id": "c_abc123",
        "target_ontology": None,
        "reasoning": "High degree concept",
        "suggested_name": "New Domain",
        "suggested_description": "A new knowledge domain",
        "params": {},
    }
    base.update(overrides)
    return base


def _legacy_demotion(**overrides):
    """v1 demotion proposal (no params JSONB) — exercises the fallback path."""
    base = {
        "id": 2,
        "proposal_type": "DISSOLVE",  # post-normalization
        "ontology_name": "weak-ontology",
        "anchor_concept_id": None,
        "target_ontology": "strong-ontology",
        "reasoning": "Low protection score",
        "params": {},
    }
    base.update(overrides)
    return base


def _cleave_new(**overrides):
    """v2 CLEAVE proposal with target.kind='new'."""
    base = {
        "id": 10,
        "proposal_type": "CLEAVE",
        "ontology_name": "primordial",
        "reasoning": "Found a dense subcluster",
        "params": {
            "source_ontology": "primordial",
            "anchor_concept_id": "c_anchor",
            "cluster_selection": "first_order",
            "cluster_params": {},
            "target": {
                "kind": "new",
                "new_name": "domain-x",
                "new_description": "A new domain split off the pool",
            },
        },
    }
    base.update(overrides)
    return base


def _cleave_existing(**overrides):
    """v2 CLEAVE proposal with target.kind='existing'."""
    base = {
        "id": 11,
        "proposal_type": "CLEAVE",
        "ontology_name": "primordial",
        "reasoning": "Subcluster belongs in an existing domain",
        "params": {
            "source_ontology": "primordial",
            "anchor_concept_id": "c_anchor",
            "cluster_selection": "first_order",
            "cluster_params": {},
            "target": {
                "kind": "existing",
                "existing_ontology": "domain-y",
            },
        },
    }
    base.update(overrides)
    return base


def _dissolve(**overrides):
    """v2 DISSOLVE proposal with per-source routing."""
    base = {
        "id": 20,
        "proposal_type": "DISSOLVE",
        "ontology_name": "weak-ontology",
        "reasoning": "Low mass, sources should re-home",
        "params": {
            "source_ontology": "weak-ontology",
            "force_primordial": False,
            "rationale": "low affinity",
        },
    }
    base.update(overrides)
    return base


def _merge(**overrides):
    """v2 MERGE proposal."""
    base = {
        "id": 30,
        "proposal_type": "MERGE",
        "ontology_name": "donor-a",
        "reasoning": "Donors share most concepts",
        "params": {
            "donor_ontologies": ["donor-a", "donor-b"],
            "target": {
                "kind": "new",
                "new_name": "merged-domain",
                "new_description": "Merged from donor-a + donor-b",
            },
        },
    }
    base.update(overrides)
    return base


def _rename(**overrides):
    """v2 RENAME proposal."""
    base = {
        "id": 40,
        "proposal_type": "RENAME",
        "ontology_name": "old-name",
        "reasoning": "Better name",
        "params": {
            "ontology": "old-name",
            "new_name": "new-name",
            "new_description": "Clearer description",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# CLEAVE
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteCleaveTargetNew:
    """CLEAVE with target.kind='new' (the v1 promotion path)."""

    def test_successful_cleave_new(self, executor, mock_client):
        """Creates ontology, anchors it, reassigns first-order sources."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor",
            "label": "Anchor",
            "description": "An anchor",
            "embedding": [0.1] * 10,
        }
        mock_client.get_ontology_node.return_value = None  # name not taken
        mock_client.create_ontology_node.return_value = {"name": "domain-x"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = ["s1", "s2", "s3"]
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 3, "success": True, "error": None,
        }

        result = executor.execute_cleave(_cleave_new())

        assert result["success"] is True
        assert result["target_kind"] == "new"
        assert result["ontology_created"] == "domain-x"
        assert result["target_ontology"] == "domain-x"
        assert result["sources_reassigned"] == 3
        assert result["anchored"] is True
        mock_client.create_ontology_node.assert_called_once()
        mock_client.create_anchored_by_edge.assert_called_once_with(
            "domain-x", "c_anchor"
        )

    def test_cleave_new_rejects_existing_name(self, executor, mock_client):
        """target.kind='new' fails fast when the name is taken."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "Anchor", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = {"name": "domain-x"}

        result = executor.execute_cleave(_cleave_new())

        assert result["success"] is False
        assert "already exists" in result["error"]
        mock_client.create_ontology_node.assert_not_called()

    def test_cleave_missing_anchor_id(self, executor):
        """Fails cleanly if proposal has no anchor_concept_id."""
        proposal = _cleave_new()
        proposal["params"]["anchor_concept_id"] = None
        result = executor.execute_cleave(proposal)
        assert result["success"] is False
        assert "anchor_concept_id" in result["error"]

    def test_cleave_missing_anchor_concept(self, executor, mock_client):
        """Fails if the anchor concept no longer exists in the graph."""
        mock_client.get_concept_node.return_value = None
        result = executor.execute_cleave(_cleave_new())
        assert result["success"] is False
        assert "no longer exists" in result["error"]

    def test_cleave_no_sources_still_succeeds(self, executor, mock_client):
        """Empty cluster — ontology is still created and anchored."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "Solo", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "domain-x"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = []

        result = executor.execute_cleave(_cleave_new())

        assert result["success"] is True
        assert result["sources_reassigned"] == 0
        mock_client.reassign_sources.assert_not_called()


@pytest.mark.unit
class TestExecuteCleaveTargetExisting:
    """CLEAVE with target.kind='existing' — schema slot newly reachable."""

    def test_successful_cleave_into_existing(self, executor, mock_client):
        """Reassigns sources from source_ontology → existing target. No node creation."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "A", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = {
            "name": "domain-y", "lifecycle_state": "active",
        }
        mock_client.get_first_order_source_ids.return_value = ["s1", "s2"]
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 2, "success": True, "error": None,
        }

        result = executor.execute_cleave(_cleave_existing())

        assert result["success"] is True
        assert result["target_kind"] == "existing"
        assert result["target_ontology"] == "domain-y"
        assert result["ontology_created"] is None
        assert result["sources_reassigned"] == 2
        # Crucially: no ontology node creation for existing targets.
        mock_client.create_ontology_node.assert_not_called()

    def test_cleave_existing_rejects_missing_target(self, executor, mock_client):
        """target.kind='existing' fails if the target ontology doesn't exist."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "A", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None

        result = executor.execute_cleave(_cleave_existing())

        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_cleave_existing_rejects_same_as_source(self, executor, mock_client):
        """target=existing must differ from source_ontology."""
        proposal = _cleave_existing()
        proposal["params"]["target"]["existing_ontology"] = "primordial"
        result = executor.execute_cleave(proposal)
        assert result["success"] is False
        assert "equals source" in result["error"]


@pytest.mark.unit
class TestExecuteCleaveClusterStrategies:
    """CLEAVE supports first_order today; documents the unimplemented strategies."""

    def test_embedding_radius_not_yet_implemented(self, executor, mock_client):
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "A", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        proposal = _cleave_new()
        proposal["params"]["cluster_selection"] = "embedding_radius"
        result = executor.execute_cleave(proposal)
        assert result["success"] is False
        assert "embedding_radius" in result["error"]
        assert "not yet implemented" in result["error"]

    def test_named_concepts_not_yet_implemented(self, executor, mock_client):
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_anchor", "label": "A", "embedding": [0.1],
        }
        mock_client.get_ontology_node.return_value = None
        proposal = _cleave_new()
        proposal["params"]["cluster_selection"] = "named_concepts"
        result = executor.execute_cleave(proposal)
        assert result["success"] is False
        assert "named_concepts" in result["error"]


@pytest.mark.unit
class TestLegacyPromotionShim:
    """v1 promotion rows (no params) still work via execute_promotion / execute_cleave."""

    def test_execute_promotion_delegates_to_cleave(self, executor, mock_client):
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123",
            "label": "Test",
            "embedding": [0.1] * 10,
            "description": "A test concept",
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "New Domain"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = ["s1"]
        mock_client.reassign_sources.return_value = {
            "sources_reassigned": 1, "success": True, "error": None,
        }

        result = executor.execute_promotion(_legacy_promotion())

        assert result["success"] is True
        assert result["ontology_created"] == "New Domain"
        assert result["target_kind"] == "new"

    def test_legacy_promotion_uses_label_when_no_suggested_name(
        self, executor, mock_client
    ):
        """v1 fallback: suggested_name=None → concept label."""
        mock_client.get_concept_node.return_value = {
            "concept_id": "c_abc123", "label": "Fallback Label",
            "embedding": [0.1], "description": "desc",
        }
        mock_client.get_ontology_node.return_value = None
        mock_client.create_ontology_node.return_value = {"name": "Fallback Label"}
        mock_client.create_anchored_by_edge.return_value = True
        mock_client.get_first_order_source_ids.return_value = []

        proposal = _legacy_promotion(suggested_name=None)
        result = executor.execute_promotion(proposal)

        assert result["success"] is True
        assert result["ontology_created"] == "Fallback Label"


# ---------------------------------------------------------------------------
# DISSOLVE — closes #252
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteDissolvePerSourceRouting:
    """DISSOLVE builds a per-source routing_map and passes it to the client."""

    def test_dissolve_with_affinity(self, executor, mock_client):
        """Affinity-driven routing: best target picked from affinity ranking."""
        # Validation: ontology exists + active.
        # Then _ensure_primordial_pool: primordial exists.
        # Then _build_affinity_routing: ranked target nodes are queried.
        mock_client.get_ontology_node.side_effect = [
            {"name": "weak-ontology", "lifecycle_state": "active"},  # validation
            {"name": "primordial", "lifecycle_state": "active"},      # primordial exists
            {"name": "strong", "lifecycle_state": "active"},          # affinity target exists
        ]
        # Source enumeration via _list_source_ids → _execute_cypher.
        mock_client._execute_cypher.return_value = [
            {"source_id": "s1"}, {"source_id": "s2"}
        ]
        mock_client.get_cross_ontology_affinity.return_value = [
            {"other_ontology": "strong", "affinity_score": 0.6}
        ]
        mock_client.dissolve_ontology.return_value = {
            "dissolved_ontology": "weak-ontology",
            "sources_reassigned": 2,
            "ontology_node_deleted": True,
            "routing_targets": ["strong"],
            "success": True,
            "error": None,
        }

        result = executor.execute_dissolve(_dissolve())

        assert result["success"] is True
        assert result["sources_reassigned"] == 2
        # dissolve_ontology was called with a routing_map keyed by source_id.
        call = mock_client.dissolve_ontology.call_args
        kwargs = call.kwargs
        routing = kwargs["routing_map"]
        assert routing == {"s1": "strong", "s2": "strong"}
        assert kwargs["force_primordial"] is False

    def test_dissolve_force_primordial_routes_everything_to_pool(
        self, executor, mock_client
    ):
        """force_primordial=True bypasses affinity; every source → primordial."""
        mock_client.get_ontology_node.side_effect = [
            {"name": "weak-ontology", "lifecycle_state": "active"},  # validation
            {"name": "primordial", "lifecycle_state": "active"},      # primordial exists
        ]
        mock_client._execute_cypher.return_value = [
            {"source_id": "s1"}, {"source_id": "s2"}, {"source_id": "s3"}
        ]
        mock_client.dissolve_ontology.return_value = {
            "dissolved_ontology": "weak-ontology",
            "sources_reassigned": 3,
            "ontology_node_deleted": True,
            "routing_targets": ["primordial"],
            "success": True,
            "error": None,
        }

        proposal = _dissolve()
        proposal["params"]["force_primordial"] = True
        result = executor.execute_dissolve(proposal)

        assert result["success"] is True
        assert result["force_primordial"] is True
        # No affinity lookup at all.
        mock_client.get_cross_ontology_affinity.assert_not_called()
        call = mock_client.dissolve_ontology.call_args
        routing = call.kwargs["routing_map"]
        assert routing == {
            "s1": "primordial", "s2": "primordial", "s3": "primordial"
        }
        assert call.kwargs["force_primordial"] is True

    def test_dissolve_no_affinity_falls_back_to_primordial(
        self, executor, mock_client
    ):
        """When affinity returns nothing, sources route to primordial."""
        mock_client.get_ontology_node.side_effect = [
            {"name": "weak-ontology", "lifecycle_state": "active"},  # validation
            {"name": "primordial", "lifecycle_state": "active"},      # primordial exists
        ]
        mock_client._execute_cypher.return_value = [{"source_id": "s1"}]
        mock_client.get_cross_ontology_affinity.return_value = []
        mock_client.dissolve_ontology.return_value = {
            "dissolved_ontology": "weak-ontology",
            "sources_reassigned": 1,
            "ontology_node_deleted": True,
            "routing_targets": ["primordial"],
            "success": True,
            "error": None,
        }

        result = executor.execute_dissolve(_dissolve())

        assert result["success"] is True
        call = mock_client.dissolve_ontology.call_args
        assert call.kwargs["routing_map"] == {"s1": "primordial"}


@pytest.mark.unit
class TestExecuteDissolveValidation:
    """Pre-flight validation behaviour (preserved from v1)."""

    def test_dissolve_ontology_gone(self, executor, mock_client):
        mock_client.get_ontology_node.return_value = None
        result = executor.execute_dissolve(_dissolve())
        assert result["success"] is False
        assert "no longer exists" in result["error"]

    def test_dissolve_pinned_ontology(self, executor, mock_client):
        mock_client.get_ontology_node.return_value = {
            "name": "weak", "lifecycle_state": "pinned",
        }
        result = executor.execute_dissolve(_dissolve())
        assert result["success"] is False
        assert "pinned" in result["error"]

    def test_dissolve_frozen_ontology(self, executor, mock_client):
        mock_client.get_ontology_node.return_value = {
            "name": "weak", "lifecycle_state": "frozen",
        }
        result = executor.execute_dissolve(_dissolve())
        assert result["success"] is False
        assert "frozen" in result["error"]

    def test_dissolve_vetoed_by_inflight_ingestion(self, executor, mock_client):
        """#402 PR-404 finding #2 — queue veto preserved under DISSOLVE."""
        mock_client.get_ontology_node.return_value = {
            "name": "weak-ontology", "lifecycle_state": "active",
        }
        mock_cursor = (
            mock_client.pool.getconn.return_value.cursor.return_value.__enter__.return_value
        )
        mock_cursor.fetchall.return_value = [("job_late_1",), ("job_late_2",)]

        result = executor.execute_dissolve(_dissolve())

        assert result["success"] is False
        assert result["retry_later"] is True
        assert "vetoed at execute time" in result["error"]
        assert result["vetoed_for_inflight_ingestion"] == [
            "job_late_1", "job_late_2"
        ]
        mock_client.dissolve_ontology.assert_not_called()


@pytest.mark.unit
class TestLegacyDemotionShim:
    """v1 demotion via execute_demotion → execute_dissolve."""

    def test_execute_demotion_delegates_to_dissolve(self, executor, mock_client):
        mock_client.get_ontology_node.side_effect = [
            {"name": "weak-ontology", "lifecycle_state": "active"},  # validation
            {"name": "primordial", "lifecycle_state": "active"},      # primordial exists
            {"name": "strong-ontology", "lifecycle_state": "active"}, # affinity target
        ]
        mock_client._execute_cypher.return_value = [{"source_id": "s1"}]
        mock_client.get_cross_ontology_affinity.return_value = [
            {"other_ontology": "strong-ontology", "affinity_score": 0.8}
        ]
        mock_client.dissolve_ontology.return_value = {
            "dissolved_ontology": "weak-ontology",
            "sources_reassigned": 1,
            "ontology_node_deleted": True,
            "routing_targets": ["strong-ontology"],
            "success": True,
            "error": None,
        }

        result = executor.execute_demotion(_legacy_demotion())

        assert result["success"] is True
        assert result["action"] == "dissolve"


# ---------------------------------------------------------------------------
# MERGE
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteMerge:
    """MERGE folds donors into a target (new or existing)."""

    def test_merge_into_new_target(self, executor, mock_client):
        """All donor sources route to the freshly-created target."""
        # get_ontology_node calls (in order):
        #   donor-a validation, donor-b validation, target collision check,
        #   then _list_source_ids uses _execute_cypher (not get_ontology_node).
        mock_client.get_ontology_node.side_effect = [
            {"name": "donor-a", "lifecycle_state": "active"},  # donor-a validation
            {"name": "donor-b", "lifecycle_state": "active"},  # donor-b validation
            None,  # target name not yet taken
        ]
        mock_client.create_ontology_node.return_value = {"name": "merged-domain"}
        # _list_source_ids cypher results for donor-a, donor-b
        mock_client._execute_cypher.side_effect = [
            [{"source_id": "s1"}, {"source_id": "s2"}],  # donor-a sources
            [{"source_id": "s3"}],                        # donor-b sources
        ]
        mock_client.dissolve_ontology.side_effect = [
            {
                "dissolved_ontology": "donor-a",
                "sources_reassigned": 2,
                "ontology_node_deleted": True,
                "routing_targets": ["merged-domain"],
                "success": True, "error": None,
            },
            {
                "dissolved_ontology": "donor-b",
                "sources_reassigned": 1,
                "ontology_node_deleted": True,
                "routing_targets": ["merged-domain"],
                "success": True, "error": None,
            },
        ]

        result = executor.execute_merge(_merge())

        assert result["success"] is True
        assert result["action"] == "merge"
        assert result["target_kind"] == "new"
        assert result["target_ontology"] == "merged-domain"
        assert result["donors_dissolved"] == ["donor-a", "donor-b"]
        assert result["sources_reassigned"] == 3
        # The new target node was created.
        mock_client.create_ontology_node.assert_called_once()

    def test_merge_into_existing_target(self, executor, mock_client):
        """Existing target: no node creation, just dissolve donors into it."""
        mock_client.get_ontology_node.side_effect = [
            {"name": "donor-a", "lifecycle_state": "active"},
            {"name": "donor-b", "lifecycle_state": "active"},
            {"name": "target-onto", "lifecycle_state": "active"},
        ]
        mock_client._execute_cypher.side_effect = [
            [{"source_id": "s1"}], [{"source_id": "s2"}],
        ]
        mock_client.dissolve_ontology.side_effect = [
            {"sources_reassigned": 1, "routing_targets": ["target-onto"], "success": True, "error": None},
            {"sources_reassigned": 1, "routing_targets": ["target-onto"], "success": True, "error": None},
        ]

        proposal = _merge()
        proposal["params"]["target"] = {
            "kind": "existing", "existing_ontology": "target-onto"
        }
        result = executor.execute_merge(proposal)

        assert result["success"] is True
        assert result["target_ontology"] == "target-onto"
        assert result["target_kind"] == "existing"
        mock_client.create_ontology_node.assert_not_called()

    def test_merge_requires_at_least_two_donors(self, executor):
        proposal = _merge()
        proposal["params"]["donor_ontologies"] = ["only-one"]
        result = executor.execute_merge(proposal)
        assert result["success"] is False
        assert "at least 2" in result["error"]

    def test_merge_rejects_frozen_donor(self, executor, mock_client):
        mock_client.get_ontology_node.side_effect = [
            {"name": "donor-a", "lifecycle_state": "active"},
            {"name": "donor-b", "lifecycle_state": "frozen"},
        ]
        result = executor.execute_merge(_merge())
        assert result["success"] is False
        assert "frozen" in result["error"]

    def test_merge_rejects_target_colliding_with_donor(self, executor, mock_client):
        """Target name == donor → reject."""
        mock_client.get_ontology_node.side_effect = [
            {"name": "donor-a", "lifecycle_state": "active"},
            {"name": "donor-b", "lifecycle_state": "active"},
        ]
        proposal = _merge()
        proposal["params"]["target"]["new_name"] = "donor-a"
        result = executor.execute_merge(proposal)
        assert result["success"] is False
        assert "collides with a donor" in result["error"]


# ---------------------------------------------------------------------------
# RENAME
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteRename:
    """RENAME updates Ontology node name + Source.document property."""

    def test_rename_success(self, executor, mock_client):
        mock_client.get_ontology_node.side_effect = [
            {"name": "old-name", "lifecycle_state": "active"},  # current
            None,  # new name not taken
        ]
        mock_client.rename_ontology_node.return_value = True
        mock_client.rename_ontology.return_value = {"sources_updated": 7}
        # Description update.
        mock_client._execute_cypher.return_value = {"ontology_id": "ont_x"}

        result = executor.execute_rename(_rename())

        assert result["success"] is True
        assert result["action"] == "rename"
        assert result["old_name"] == "old-name"
        assert result["new_name"] == "new-name"
        assert result["sources_updated"] == 7
        assert result["description_updated"] is True
        mock_client.rename_ontology_node.assert_called_once_with(
            "old-name", "new-name"
        )

    def test_rename_rejects_primordial(self, executor, mock_client):
        proposal = _rename()
        proposal["params"]["ontology"] = "primordial"
        result = executor.execute_rename(proposal)
        assert result["success"] is False
        assert "primordial" in result["error"]

    def test_rename_rejects_same_name(self, executor):
        proposal = _rename()
        proposal["params"]["new_name"] = "old-name"
        result = executor.execute_rename(proposal)
        assert result["success"] is False
        assert "equals current name" in result["error"]

    def test_rename_rejects_existing_new_name(self, executor, mock_client):
        mock_client.get_ontology_node.side_effect = [
            {"name": "old-name", "lifecycle_state": "active"},
            {"name": "new-name", "lifecycle_state": "active"},  # already taken
        ]
        result = executor.execute_rename(_rename())
        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_rename_rejects_pinned(self, executor, mock_client):
        mock_client.get_ontology_node.return_value = {
            "name": "old-name", "lifecycle_state": "pinned",
        }
        result = executor.execute_rename(_rename())
        assert result["success"] is False
        assert "pinned" in result["error"]


# ---------------------------------------------------------------------------
# NO_ACTION
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteNoAction:
    """NO_ACTION records the deliberate no-op."""

    def test_no_action_returns_success_without_mutation(self, executor, mock_client):
        proposal = {
            "id": 50,
            "proposal_type": "NO_ACTION",
            "ontology_name": "any",
            "reasoning": "ecosystem is healthy",
            "params": {"reasoning": "ecosystem is healthy"},
        }
        result = executor.execute_no_action(proposal)
        assert result["success"] is True
        assert result["action"] == "no_action"
        assert result["reasoning"] == "ecosystem is healthy"
        # No graph mutation primitives invoked.
        mock_client.create_ontology_node.assert_not_called()
        mock_client.dissolve_ontology.assert_not_called()
        mock_client.reassign_sources.assert_not_called()

    def test_no_action_falls_back_to_top_level_reasoning(self, executor):
        proposal = {
            "id": 51,
            "proposal_type": "NO_ACTION",
            "ontology_name": "x",
            "reasoning": "top-level reasoning",
            "params": {},
        }
        result = executor.execute_no_action(proposal)
        assert result["reasoning"] == "top-level reasoning"


# ---------------------------------------------------------------------------
# ESCALATE
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecuteEscalate:
    """ESCALATE records uncertainty; no graph mutation."""

    def test_escalate_surfaces_audit_fields(self, executor, mock_client):
        proposal = {
            "id": 60,
            "proposal_type": "ESCALATE",
            "ontology_name": "ambiguous",
            "reasoning": "I'm not sure",
            "params": {
                "candidate_actions": ["CLEAVE", "DISSOLVE"],
                "recommended_action": "CLEAVE",
                "confidence": 0.45,
                "what_i_know": "donor has mixed concepts",
                "what_i_dont_know": "operator intent",
            },
        }
        result = executor.execute_escalate(proposal)
        assert result["success"] is True
        assert result["action"] == "escalate"
        assert result["candidate_actions"] == ["CLEAVE", "DISSOLVE"]
        assert result["recommended_action"] == "CLEAVE"
        assert result["confidence"] == 0.45
        assert result["escalation_recorded"] is True
        mock_client.dissolve_ontology.assert_not_called()
