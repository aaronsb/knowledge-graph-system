"""
Polarity Axis Analysis Worker (ADR-070, ADR-083).

Computes polarity axis analysis as an async job with artifact persistence.
Projects concepts onto an axis formed by two opposing semantic poles.

Job Parameters:
    - positive_pole_id: Concept ID for positive pole
    - negative_pole_id: Concept ID for negative pole
    - candidate_ids: Optional list of concept IDs to project
    - auto_discover: Whether to auto-discover related concepts
    - max_candidates: Maximum candidates for auto-discovery
    - max_hops: Maximum graph hops for discovery
    - create_artifact: Whether to persist result as artifact (ADR-083)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_polarity_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute polarity axis analysis as a background job.

    Args:
        job_data: Job parameters
            - positive_pole_id: str - Positive pole concept ID
            - negative_pole_id: str - Negative pole concept ID
            - candidate_ids: Optional[List[str]] - Specific concepts to project
            - auto_discover: bool - Auto-discover related concepts (default: True)
            - max_candidates: int - Max auto-discovery candidates (default: 20)
            - max_hops: int - Max graph hops (default: 1)
            - discovery_slot_pct: float - Random discovery percentage (default: 0.2)
            - max_workers: int - Parallel workers (default: 8)
            - chunk_size: int - Concepts per worker (default: 20)
            - timeout_seconds: float - Analysis timeout (default: 120)
            - create_artifact: bool - Save result as artifact (default: True)
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with analysis data and optional artifact_id

    Raises:
        Exception: If analysis fails
    """
    try:
        from api.api.lib.age_client import AGEClient
        from api.api.lib.polarity_axis import analyze_polarity_axis

        logger.info(f"📊 Polarity worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Polarity analysis started"
        })

        # Extract parameters
        positive_pole_id = job_data.get("positive_pole_id")
        negative_pole_id = job_data.get("negative_pole_id")

        if not positive_pole_id or not negative_pole_id:
            raise ValueError("Missing required parameters: positive_pole_id and negative_pole_id")

        candidate_ids = job_data.get("candidate_ids")
        auto_discover = job_data.get("auto_discover", True)
        max_candidates = job_data.get("max_candidates", 20)
        max_hops = job_data.get("max_hops", 1)
        discovery_slot_pct = job_data.get("discovery_slot_pct", 0.2)
        max_workers = job_data.get("max_workers", 8)
        chunk_size = job_data.get("chunk_size", 20)
        timeout_seconds = job_data.get("timeout_seconds", 120.0)
        create_artifact = job_data.get("create_artifact", True)

        logger.info(
            f"Polarity params: positive={positive_pole_id}, negative={negative_pole_id}, "
            f"auto_discover={auto_discover}, max_candidates={max_candidates}"
        )

        # Initialize client
        client = AGEClient()

        # Update progress
        job_queue.update_job(job_id, {
            "progress": f"Analyzing axis: {positive_pole_id} ↔ {negative_pole_id}"
        })

        # Run analysis
        result = analyze_polarity_axis(
            positive_pole_id=positive_pole_id,
            negative_pole_id=negative_pole_id,
            age_client=client,
            candidate_ids=candidate_ids,
            auto_discover=auto_discover,
            max_candidates=max_candidates,
            max_hops=max_hops,
            discovery_slot_pct=discovery_slot_pct,
            max_workers=max_workers,
            chunk_size=chunk_size,
            timeout_seconds=timeout_seconds
        )

        client.close()

        # Update progress
        concept_count = result.get("statistics", {}).get("total_concepts", 0)
        job_queue.update_job(job_id, {
            "progress": f"Analyzed {concept_count} concepts"
        })

        # ADR-083: Create artifact if requested
        artifact_id = None
        if create_artifact:
            from api.api.workers.artifact_helper import create_job_artifact, get_job_user_id

            user_id = get_job_user_id(job_id)
            if user_id:
                # Build descriptive name from pole labels
                pos_label = result.get("axis", {}).get("positive_pole", {}).get("label", positive_pole_id)
                neg_label = result.get("axis", {}).get("negative_pole", {}).get("label", negative_pole_id)

                artifact_id = create_job_artifact(
                    job_id=job_id,
                    job_queue=job_queue,
                    user_id=user_id,
                    artifact_type="polarity_analysis",
                    representation="polarity_explorer",
                    name=f"Polarity: {pos_label} ↔ {neg_label}",
                    parameters={
                        "positive_pole_id": positive_pole_id,
                        "negative_pole_id": negative_pole_id,
                        "candidate_ids": candidate_ids,
                        "auto_discover": auto_discover,
                        "max_candidates": max_candidates,
                        "max_hops": max_hops,
                        "discovery_slot_pct": discovery_slot_pct
                    },
                    payload=result,
                    concept_ids=[positive_pole_id, negative_pole_id] + (candidate_ids or [])
                )
            else:
                logger.warning(f"Could not create artifact - no user_id for job {job_id}")

        # Prepare result
        job_result = {
            "success": True,
            "positive_pole_id": positive_pole_id,
            "negative_pole_id": negative_pole_id,
            "concept_count": concept_count,
            "axis_quality": result.get("axis", {}).get("axis_quality"),
            "artifact_id": artifact_id
        }

        logger.info(
            f"✅ Polarity worker completed: {job_id} "
            f"({concept_count} concepts)"
            f"{f', artifact={artifact_id}' if artifact_id else ''}"
        )

        return job_result

    except Exception as e:
        error_msg = f"Polarity analysis failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        job_queue.update_job(job_id, {
            "status": "failed",
            "error": error_msg,
            "progress": "Polarity analysis failed"
        })

        raise Exception(error_msg) from e
