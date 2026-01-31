"""
Annealing cycle worker (ADR-200 Phase 3b).

Runs ontology annealing cycle as a background job:
score all → recompute centroids → identify candidates → LLM judgment → store proposals.

Phase 3b is proposal-only (HITL). Phase 4 adds execution.
"""

import asyncio
import logging
from typing import Dict, Any

from api.app.lib.age_client import AGEClient
from api.app.lib.ontology_scorer import OntologyScorer
from api.app.lib.ai_providers import get_provider
from api.app.services.annealing_manager import AnnealingManager

logger = logging.getLogger(__name__)


def run_annealing_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute a annealing cycle as a background job.

    Args:
        job_data: Job parameters
            - demotion_threshold: float (default 0.15)
            - promotion_min_degree: int (default 10)
            - max_proposals: int (default 5)
            - dry_run: bool (default False)
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with cycle summary
    """
    demotion_threshold = job_data.get("demotion_threshold", 0.15)
    promotion_min_degree = job_data.get("promotion_min_degree", 10)
    max_proposals = job_data.get("max_proposals", 5)
    dry_run = job_data.get("dry_run", False)
    derive_edges = job_data.get("derive_edges", True)
    overlap_threshold = job_data.get("overlap_threshold", 0.1)
    specializes_threshold = job_data.get("specializes_threshold", 0.3)

    logger.info(
        f"Annealing worker starting (job {job_id}): "
        f"threshold={demotion_threshold}, min_degree={promotion_min_degree}, "
        f"max_proposals={max_proposals}, dry_run={dry_run}"
    )

    job_queue.update_job(job_id, {
        "progress": {"stage": "initializing", "percent": 0}
    })

    age_client = None
    try:
        age_client = AGEClient()
        scorer = OntologyScorer(age_client)

        # Get AI provider for LLM evaluation (optional — falls back to score-based)
        try:
            ai_provider = get_provider()
        except Exception:
            ai_provider = None
            logger.info("No AI provider available — using score-based decisions")

        manager = AnnealingManager(age_client, scorer, ai_provider=ai_provider)

        job_queue.update_job(job_id, {
            "progress": {"stage": "scoring", "percent": 10}
        })

        result = asyncio.run(manager.run_annealing_cycle(
            demotion_threshold=demotion_threshold,
            promotion_min_degree=promotion_min_degree,
            max_proposals=max_proposals,
            dry_run=dry_run,
            derive_edges=derive_edges,
            overlap_threshold=overlap_threshold,
            specializes_threshold=specializes_threshold,
        ))

        job_queue.update_job(job_id, {
            "progress": {"stage": "complete", "percent": 100}
        })

        logger.info(
            f"Annealing worker complete (job {job_id}): "
            f"{result.get('proposals_generated', 0)} proposals, "
            f"{result.get('scores_updated', 0)} scored, "
            f"{result.get('centroids_updated', 0)} centroids"
        )

        return {
            "status": "completed",
            **result,
        }

    finally:
        if age_client:
            age_client.close()
