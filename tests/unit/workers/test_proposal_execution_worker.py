"""Unit tests for proposal_execution_worker.

Covers:
- The retry_later path (#402 PR-404 review, finding #2): the operational
  counterpart to the executor's queue-veto re-check — when
  execute_dissolve returns {success=False, retry_later=True}, the worker
  must revert the claim to 'approved' status so the proposal stays alive
  for the next cycle. Without this, an approved proposal that hits a
  transient queue race is permanently failed.
- ADR-206 dispatch: the worker reads proposal_type, normalizes legacy
  aliases (promotion → CLEAVE, demotion → DISSOLVE) and routes to the
  correct executor method.
"""

import pytest
from unittest.mock import MagicMock, patch

from api.app.workers.proposal_execution_worker import (
    run_proposal_execution_worker,
)


def _make_job_queue():
    queue = MagicMock()
    queue.is_job_cancelled.return_value = False
    queue.update_job = MagicMock()
    return queue


def _run_worker_with_proposal(proposal, executor_responses):
    """Execute the worker against a fixed proposal + executor mock setup.

    executor_responses is a dict mapping method names ('execute_cleave',
    'execute_dissolve', ...) to the result dict each should return. The
    test asserts on which method was actually invoked by checking the
    mocks afterwards.
    """
    with patch(
        "api.app.workers.proposal_execution_worker.AGEClient"
    ) as MockClient, patch(
        "api.app.workers.proposal_execution_worker._load_proposal",
        return_value=proposal,
    ), patch(
        "api.app.workers.proposal_execution_worker._claim_proposal",
        return_value=True,
    ), patch(
        "api.app.workers.proposal_execution_worker._update_proposal_status"
    ) as mock_update, patch(
        "api.app.workers.proposal_execution_worker.ProposalExecutor"
    ) as MockExecutor:
        MockClient.return_value = MagicMock()
        executor_instance = MockExecutor.return_value
        for method_name, response in executor_responses.items():
            getattr(executor_instance, method_name).return_value = response

        result = run_proposal_execution_worker(
            job_data={"proposal_id": proposal["id"], "triggered_by": "test"},
            job_id="job_test",
            job_queue=_make_job_queue(),
        )
        return result, executor_instance, mock_update


# ---------------------------------------------------------------------------
# Retry-later path (preserved from #402 PR-404 review)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRetryLaterPath:
    """retry_later=True must revert proposal status, not mark it failed."""

    def test_vetoed_dissolve_reverts_to_approved(self):
        """When execute_dissolve returns retry_later=True, revert claim to 'approved'."""
        proposal = {
            "id": 42,
            "proposal_type": "DISSOLVE",
            "proposal_kind": "ontology",
            "params": {"source_ontology": "weak-onto"},
            "ontology_name": "weak-onto",
            "status": "approved",
        }
        result, executor_instance, mock_update = _run_worker_with_proposal(
            proposal,
            {
                "execute_dissolve": {
                    "success": False,
                    "retry_later": True,
                    "error": "Demotion of 'weak-onto' vetoed at execute time: 1 in-flight ingestion job(s) (job_xyz)",
                    "vetoed_for_inflight_ingestion": ["job_xyz"],
                }
            },
        )

        # The proposal must be reverted to 'approved' — NOT 'failed'.
        update_calls = mock_update.call_args_list
        assert len(update_calls) == 1
        args, kwargs = update_calls[0]
        called_status = args[2] if len(args) >= 3 else kwargs.get("status")
        assert called_status == "approved"
        assert result["status"] == "deferred"
        assert result["retry_later"] is True

    def test_genuine_failure_still_marked_failed(self):
        """A non-veto failure (e.g. frozen ontology) is still marked 'failed'."""
        proposal = {
            "id": 43,
            "proposal_type": "DISSOLVE",
            "proposal_kind": "ontology",
            "params": {"source_ontology": "weak-onto"},
            "ontology_name": "weak-onto",
            "status": "approved",
        }
        result, _, mock_update = _run_worker_with_proposal(
            proposal,
            {
                "execute_dissolve": {
                    "success": False,
                    "error": "Ontology 'weak-onto' is frozen — cannot demote",
                }
            },
        )

        args, kwargs = mock_update.call_args_list[0]
        called_status = args[2] if len(args) >= 3 else kwargs.get("status")
        assert called_status == "failed"
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# ADR-206 dispatch
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDispatchOnCanonicalVerb:
    """The worker normalizes legacy verbs and dispatches to the right method."""

    def test_cleave_routes_to_execute_cleave(self):
        proposal = {
            "id": 100,
            "proposal_type": "CLEAVE",
            "proposal_kind": "ontology",
            "params": {"anchor_concept_id": "c1", "source_ontology": "primordial"},
            "ontology_name": "primordial",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_cleave": {"success": True, "action": "cleave"}},
        )
        executor_instance.execute_cleave.assert_called_once()
        executor_instance.execute_dissolve.assert_not_called()
        assert result["status"] == "completed"

    def test_dissolve_routes_to_execute_dissolve(self):
        proposal = {
            "id": 101,
            "proposal_type": "DISSOLVE",
            "proposal_kind": "ontology",
            "params": {"source_ontology": "weak"},
            "ontology_name": "weak",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_dissolve": {"success": True, "action": "dissolve"}},
        )
        executor_instance.execute_dissolve.assert_called_once()
        assert result["status"] == "completed"

    def test_merge_routes_to_execute_merge(self):
        proposal = {
            "id": 102,
            "proposal_type": "MERGE",
            "proposal_kind": "ontology",
            "params": {
                "donor_ontologies": ["a", "b"],
                "target": {"kind": "new", "new_name": "merged"},
            },
            "ontology_name": "a",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_merge": {"success": True, "action": "merge"}},
        )
        executor_instance.execute_merge.assert_called_once()
        executor_instance.execute_cleave.assert_not_called()
        executor_instance.execute_dissolve.assert_not_called()
        assert result["status"] == "completed"

    def test_rename_routes_to_execute_rename(self):
        proposal = {
            "id": 103,
            "proposal_type": "RENAME",
            "proposal_kind": "ontology",
            "params": {"ontology": "old", "new_name": "new"},
            "ontology_name": "old",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_rename": {"success": True, "action": "rename"}},
        )
        executor_instance.execute_rename.assert_called_once()
        assert result["status"] == "completed"

    def test_no_action_routes_to_execute_no_action(self):
        proposal = {
            "id": 104,
            "proposal_type": "NO_ACTION",
            "proposal_kind": "ontology",
            "params": {"reasoning": "all good"},
            "ontology_name": "n/a",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_no_action": {"success": True, "action": "no_action"}},
        )
        executor_instance.execute_no_action.assert_called_once()
        assert result["status"] == "completed"

    def test_escalate_routes_to_execute_escalate(self):
        proposal = {
            "id": 105,
            "proposal_type": "ESCALATE",
            "proposal_kind": "ontology",
            "params": {"recommended_action": "CLEAVE", "confidence": 0.5},
            "ontology_name": "ambiguous",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_escalate": {"success": True, "action": "escalate"}},
        )
        executor_instance.execute_escalate.assert_called_once()
        assert result["status"] == "completed"


@pytest.mark.unit
class TestLegacyAliasNormalization:
    """Pre-ADR-206 rows ('promotion'/'demotion') normalize to CLEAVE/DISSOLVE."""

    def test_legacy_promotion_routed_to_execute_cleave(self):
        """Stored proposal_type='promotion' → execute_cleave with merged params."""
        proposal = {
            "id": 200,
            "proposal_type": "promotion",   # raw legacy value
            "proposal_kind": "ontology",
            "params": {},
            "ontology_name": "parent",
            "anchor_concept_id": "c_anchor",
            "suggested_name": "spawn",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_cleave": {"success": True, "action": "cleave"}},
        )
        executor_instance.execute_cleave.assert_called_once()
        # The proposal handed to execute_cleave carries the canonical verb
        # and the merged params (source_ontology=primordial from alias delta).
        call_proposal = executor_instance.execute_cleave.call_args[0][0]
        assert call_proposal["proposal_type"] == "CLEAVE"
        assert call_proposal["params"].get("source_ontology") == "primordial"
        assert result["status"] == "completed"

    def test_legacy_demotion_routed_to_execute_dissolve(self):
        """Stored proposal_type='demotion' → execute_dissolve."""
        proposal = {
            "id": 201,
            "proposal_type": "demotion",   # raw legacy value
            "proposal_kind": "ontology",
            "params": {},
            "ontology_name": "weak",
            "status": "approved",
        }
        result, executor_instance, _ = _run_worker_with_proposal(
            proposal,
            {"execute_dissolve": {"success": True, "action": "dissolve"}},
        )
        executor_instance.execute_dissolve.assert_called_once()
        call_proposal = executor_instance.execute_dissolve.call_args[0][0]
        assert call_proposal["proposal_type"] == "DISSOLVE"
        assert result["status"] == "completed"
