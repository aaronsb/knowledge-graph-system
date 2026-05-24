"""Unit tests for proposal_execution_worker (#402 PR-404 review, finding #2).

The retry_later path is the operational counterpart to the executor's
queue-veto re-check: when execute_demotion returns
{success=False, retry_later=True}, the worker must revert the claim to
'approved' status so the proposal stays alive for the next cycle. Without
this, an approved proposal that hits a transient queue race is
permanently failed — the queue veto becomes a footgun.
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


@pytest.mark.unit
class TestRetryLaterPath:
    """retry_later=True must revert proposal status, not mark it failed."""

    def test_vetoed_demotion_reverts_to_approved(self):
        """When execute_demotion returns retry_later=True, the worker must
        call _update_proposal_status with 'approved' (not 'failed')."""
        with patch(
            "api.app.workers.proposal_execution_worker.AGEClient"
        ) as MockClient, patch(
            "api.app.workers.proposal_execution_worker._load_proposal",
            return_value={
                "id": 42,
                "proposal_type": "demotion",
                "ontology_name": "weak-onto",
                "status": "approved",
            },
        ), patch(
            "api.app.workers.proposal_execution_worker._claim_proposal",
            return_value=True,
        ), patch(
            "api.app.workers.proposal_execution_worker._update_proposal_status"
        ) as mock_update, patch(
            "api.app.workers.proposal_execution_worker.ProposalExecutor"
        ) as MockExecutor:
            MockClient.return_value = MagicMock()
            MockExecutor.return_value.execute_demotion.return_value = {
                "success": False,
                "retry_later": True,
                "error": "Demotion of 'weak-onto' vetoed at execute time: 1 in-flight ingestion job(s) (job_xyz)",
                "vetoed_for_inflight_ingestion": ["job_xyz"],
            }

            result = run_proposal_execution_worker(
                job_data={"proposal_id": 42, "triggered_by": "test"},
                job_id="job_worker_1",
                job_queue=_make_job_queue(),
            )

        # The proposal must be reverted to 'approved' — NOT 'failed'.
        update_calls = mock_update.call_args_list
        assert len(update_calls) == 1, (
            f"expected exactly one status update, got {len(update_calls)}"
        )
        # _update_proposal_status(age_client, proposal_id, status, ...)
        args, kwargs = update_calls[0]
        called_status = args[2] if len(args) >= 3 else kwargs.get("status")
        assert called_status == "approved", (
            f"retry_later must revert to 'approved', got '{called_status}'"
        )

        assert result["status"] == "deferred"
        assert result["retry_later"] is True

    def test_genuine_failure_still_marked_failed(self):
        """retry_later branch must not swallow real failures — a non-veto
        failure (e.g. anchor concept gone) is still marked 'failed'."""
        with patch(
            "api.app.workers.proposal_execution_worker.AGEClient"
        ) as MockClient, patch(
            "api.app.workers.proposal_execution_worker._load_proposal",
            return_value={
                "id": 43,
                "proposal_type": "demotion",
                "ontology_name": "weak-onto",
                "status": "approved",
            },
        ), patch(
            "api.app.workers.proposal_execution_worker._claim_proposal",
            return_value=True,
        ), patch(
            "api.app.workers.proposal_execution_worker._update_proposal_status"
        ) as mock_update, patch(
            "api.app.workers.proposal_execution_worker.ProposalExecutor"
        ) as MockExecutor:
            MockClient.return_value = MagicMock()
            MockExecutor.return_value.execute_demotion.return_value = {
                "success": False,
                "error": "Ontology 'weak-onto' is frozen — cannot demote",
            }

            result = run_proposal_execution_worker(
                job_data={"proposal_id": 43, "triggered_by": "test"},
                job_id="job_worker_2",
                job_queue=_make_job_queue(),
            )

        args, kwargs = mock_update.call_args_list[0]
        called_status = args[2] if len(args) >= 3 else kwargs.get("status")
        assert called_status == "failed"
        assert result["status"] == "failed"
