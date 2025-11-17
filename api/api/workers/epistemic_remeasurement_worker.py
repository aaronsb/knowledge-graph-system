"""
Epistemic Re-measurement Worker (ADR-065 Phase 2).

Executes epistemic status measurement for all vocabulary types and resets
the vocabulary_change_counter delta. Triggered by EpistemicRemeasurementLauncher
when vocabulary changes exceed threshold.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_epistemic_remeasurement_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute epistemic status re-measurement as a background job.

    Uses the EpistemicStatusService to measure grounding statistics for all
    vocabulary types (same logic as `kg vocab epistemic-status measure` command).

    Args:
        job_data: Job parameters
            - operation: str - "remeasure_epistemic_status"
            - sample_size: int - Number of edges to sample per type (default: 100)
            - store: bool - Whether to store results to VocabType nodes (default: True)
            - description: str - Job description
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with measurement stats

    Raises:
        Exception: If measurement fails
    """
    try:
        from api.api.lib.age_client import AGEClient
        from api.api.services.epistemic_status_service import EpistemicStatusService

        logger.info(f"🔄 Epistemic re-measurement worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Epistemic re-measurement worker started"
        })

        # Extract parameters
        sample_size = job_data.get("sample_size", 100)
        store = job_data.get("store", True)

        logger.info(
            f"Epistemic re-measurement params: sample_size={sample_size}, store={store}"
        )

        # Initialize service
        client = AGEClient()
        service = EpistemicStatusService(client)

        try:
            # Update progress
            job_queue.update_job(job_id, {
                "progress": "Measuring epistemic status for all vocabulary types"
            })

            # Measure all vocabulary types
            # This also resets the vocabulary_change_counter delta to 0 (see ADR-065)
            results = service.measure_all_vocabulary(
                sample_size=sample_size,
                store=store
            )

            # Count classifications
            classifications = {}
            for vocab_type, data in results.items():
                status = data['status']
                classifications[status] = classifications.get(status, 0) + 1

            total_types = len(results)

            # Update progress
            job_queue.update_job(job_id, {
                "progress": f"Measured {total_types} vocabulary types"
            })

            # Prepare result
            result = {
                "success": True,
                "total_types": total_types,
                "stored": store,
                "classifications": classifications,
                "sample_size": sample_size
            }

            logger.info(
                f"✅ Epistemic re-measurement worker completed: {job_id} "
                f"({total_types} types measured, {len(classifications)} statuses)"
            )
            return result

        except Exception as e:
            error_msg = f"Epistemic re-measurement failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            job_queue.update_job(job_id, {
                "status": "failed",
                "error": error_msg,
                "progress": "Epistemic re-measurement failed"
            })

            raise Exception(error_msg) from e

    except Exception as e:
        logger.error(f"❌ Epistemic re-measurement worker failed: {job_id} - {e}")
        raise
