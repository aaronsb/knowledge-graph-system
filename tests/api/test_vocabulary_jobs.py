"""
Vocabulary job-dispatch route tests (ADR-701 §1a).

Tests POST /vocabulary/jobs — the unified dispatch endpoint that enqueues the
four vocabulary worker operations onto the ADR-100 job queue, mirroring
/ontology/annealing-cycle. The job queue is mocked; auth/permission gating is
covered by the shared endpoint-security tests.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation):
    """Auto-use mock OAuth validation for all tests in this module."""
    pass


@pytest.fixture(autouse=True)
def bypass_permission_check(monkeypatch):
    """Bypass require_permission for route tests — auth is tested separately."""
    monkeypatch.setattr(
        "api.app.dependencies.auth.check_permission",
        lambda *args, **kwargs: True,
    )


def _mock_queue(job_id="job_test123"):
    """A job queue whose enqueue returns a fixed id and update_job is a no-op."""
    queue = MagicMock()
    queue.enqueue = MagicMock(return_value=job_id)
    queue.update_job = MagicMock(return_value=True)
    return queue


@pytest.mark.unit
class TestDispatchVocabularyJob:
    """Tests for POST /vocabulary/jobs."""

    @pytest.mark.parametrize(
        "kind,expected_type",
        [
            ("consolidate", "vocab_consolidate"),
            ("refresh", "vocab_refresh"),
            ("remeasure", "epistemic_remeasurement"),
            ("embed", "vocab_embedding"),
        ],
    )
    def test_dispatch_enqueues_correct_worker(
        self, api_client, auth_headers_admin, kind, expected_type
    ):
        """Each kind enqueues its mapped worker job_type and auto-approves."""
        queue = _mock_queue()
        with patch("api.app.services.job_queue.get_job_queue", return_value=queue):
            response = api_client.post(
                "/vocabulary/jobs", json={"kind": kind}, headers=auth_headers_admin
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["kind"] == kind
        assert data["job_type"] == expected_type
        assert data["job_id"] == "job_test123"
        assert data["status"] == "approved"

        # Enqueued with the right worker job_type...
        queue.enqueue.assert_called_once()
        assert queue.enqueue.call_args.kwargs["job_type"] == expected_type
        # ...then auto-approved (by job_id) so the lane manager claims it (ADR-100).
        queue.update_job.assert_called_once()
        assert queue.update_job.call_args.args[0] == "job_test123"
        approve_updates = queue.update_job.call_args.args[1]
        assert approve_updates["status"] == "approved"

    def test_params_passed_through_to_job_data(self, api_client, auth_headers_admin):
        """Optional params flow into job_data alongside triggered_by."""
        queue = _mock_queue()
        with patch("api.app.services.job_queue.get_job_queue", return_value=queue):
            response = api_client.post(
                "/vocabulary/jobs",
                json={"kind": "consolidate", "params": {"target_size": 80, "dry_run": True}},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200, response.text
        job_data = queue.enqueue.call_args.kwargs["job_data"]
        assert job_data["target_size"] == 80
        assert job_data["dry_run"] is True
        assert "triggered_by" in job_data

    def test_invalid_kind_rejected(self, api_client, auth_headers_admin):
        """An unknown kind is rejected by Pydantic validation before enqueue."""
        queue = _mock_queue()
        with patch("api.app.services.job_queue.get_job_queue", return_value=queue):
            response = api_client.post(
                "/vocabulary/jobs", json={"kind": "bogus"}, headers=auth_headers_admin
            )

        assert response.status_code == 422
        queue.enqueue.assert_not_called()

    def test_missing_kind_rejected(self, api_client, auth_headers_admin):
        """kind is required."""
        queue = _mock_queue()
        with patch("api.app.services.job_queue.get_job_queue", return_value=queue):
            response = api_client.post(
                "/vocabulary/jobs", json={}, headers=auth_headers_admin
            )

        assert response.status_code == 422
        queue.enqueue.assert_not_called()
