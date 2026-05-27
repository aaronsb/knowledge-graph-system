"""
ProjectionWorker defensive floor check.

The launcher threads `min_ontology_concept_count` through job_data so the
worker can defensively re-check the actual concept count returned by
generate_projection_dataset. Without this, any out-of-band enqueue path
(manual queue insert, future retry path) would bypass the launcher's
gate and re-trigger the original loop on a tiny ontology.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.app.workers.projection_worker import run_projection_worker


def _make_queue():
    queue = MagicMock()
    queue.is_job_cancelled.return_value = False
    return queue


def _patched_run(job_data, dataset):
    """Run the worker with the AGE client + service mocked.

    `dataset` is what service.generate_projection_dataset returns.
    """
    with patch("api.app.lib.age_client.AGEClient") as mock_client_cls, patch(
        "api.app.services.embedding_projection_service.EmbeddingProjectionService"
    ) as mock_service_cls:
        mock_client_cls.return_value = MagicMock()
        mock_service = MagicMock()
        mock_service.get_available_algorithms.return_value = ["tsne", "umap"]
        mock_service.generate_projection_dataset.return_value = dataset
        mock_service_cls.return_value = mock_service
        return run_projection_worker(job_data, "job_test", _make_queue())


def test_worker_refuses_when_actual_count_below_threaded_floor():
    """job_data carries the floor; worker must enforce it even when the
    dataset slipped past — defense in depth against out-of-band callers."""
    dataset = {
        "ontology": "tiny",
        "coordinates": [],
        "statistics": {"concept_count": 4},
    }
    job_data = {
        "operation": "compute_projection",
        "ontology": "tiny",
        "algorithm": "tsne",
        "min_ontology_concept_count": 5,
    }

    # Worker's outer try/except re-raises as Exception with the original
    # message; the inner ValueError is the cause. Both layers should reach
    # the message that names the floor.
    with pytest.raises(Exception, match="refusing to project"):
        _patched_run(job_data, dataset)


def test_worker_proceeds_when_actual_count_meets_floor():
    """At the floor, the defensive check passes through to the storage path."""
    dataset = {
        "ontology": "ok",
        "coordinates": [{"id": str(i)} for i in range(5)],
        "statistics": {"concept_count": 5},
        "metadata": {"algorithm": "tsne"},
    }
    job_data = {
        "operation": "compute_projection",
        "ontology": "ok",
        "algorithm": "tsne",
        "min_ontology_concept_count": 5,
    }

    # _store_projection writes to Garage; stub it so the test doesn't hit S3.
    with patch(
        "api.app.workers.projection_worker._store_projection",
        return_value="projections/ok/concepts/latest.json",
    ):
        result = _patched_run(job_data, dataset)

    assert result["success"] is True
    assert result["concept_count"] == 5


def test_worker_skips_check_when_floor_not_threaded():
    """If job_data omits the floor (out-of-band path), the worker doesn't
    invent one — the service's hard floor and the route's 422 are the
    other layers of defense."""
    dataset = {
        "ontology": "no-gate",
        "coordinates": [{"id": str(i)} for i in range(3)],
        "statistics": {"concept_count": 3},
        "metadata": {"algorithm": "tsne"},
    }
    job_data = {
        "operation": "compute_projection",
        "ontology": "no-gate",
        "algorithm": "tsne",
        # min_ontology_concept_count intentionally absent
    }

    with patch(
        "api.app.workers.projection_worker._store_projection",
        return_value="projections/no-gate/concepts/latest.json",
    ):
        result = _patched_run(job_data, dataset)

    assert result["success"] is True
