"""
Annealing cycle worker (ADR-200).

Runs ontology annealing cycle as a background job:
score all → recompute centroids → identify candidates → LLM judgment → store proposals.

In autonomous mode (default), proposals are auto-approved and dispatched
for execution within the same job. In hitl mode, proposals wait for
human review via the API.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

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

        # Auto-approve and dispatch proposals in autonomous mode
        automation_level = job_data.get("automation_level", "autonomous")
        proposal_ids = result.get("proposal_ids", [])

        if automation_level == "autonomous" and not dry_run and proposal_ids:
            job_queue.update_job(job_id, {
                "progress": {"stage": "executing_proposals", "percent": 90}
            })
            dispatched = _auto_approve_and_dispatch(
                proposal_ids, age_client, job_queue
            )
            result["auto_dispatched"] = dispatched
            logger.info(
                f"Autonomous mode: dispatched {dispatched} of "
                f"{len(proposal_ids)} proposals for execution"
            )
        elif proposal_ids:
            logger.info(
                f"HITL mode: {len(proposal_ids)} proposals awaiting "
                f"human review (automation_level={automation_level})"
            )

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


def _auto_approve_and_dispatch(
    proposal_ids: List[int],
    age_client: AGEClient,
    job_queue,
) -> int:
    """Auto-approve pending proposals and dispatch execution jobs.

    Follows the same execution path as the human review endpoint:
    mark approved → enqueue proposal_execution job → dispatch async.

    Returns the number of proposals dispatched.
    """
    dispatched = 0
    conn = age_client.pool.getconn()
    try:
        for proposal_id in proposal_ids:
            try:
                # Atomic approve — only if still pending (prevents double-dispatch)
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE kg_api.annealing_proposals
                        SET status = 'approved',
                            reviewed_by = 'annealing_worker',
                            reviewed_at = %s,
                            reviewer_notes = 'auto-approved (autonomous mode)'
                        WHERE id = %s AND status = 'pending'
                        RETURNING id
                    """, (datetime.now(timezone.utc), proposal_id))
                    row = cur.fetchone()
                conn.commit()

                if not row:
                    logger.warning(
                        f"Proposal {proposal_id} not pending — skipping auto-approve"
                    )
                    continue

                # Dispatch execution job
                exec_job_id = job_queue.enqueue(
                    job_type="proposal_execution",
                    job_data={
                        "proposal_id": proposal_id,
                        "triggered_by": "annealing_worker",
                    },
                )
                job_queue.update_job(exec_job_id, {
                    "status": "approved",
                    "approved_by": "annealing_worker",
                })
                job_queue.execute_job_async(exec_job_id)
                dispatched += 1

                logger.info(
                    f"Auto-approved proposal {proposal_id}, "
                    f"dispatched execution job {exec_job_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to auto-approve/dispatch proposal {proposal_id}: {e}",
                    exc_info=True,
                )
    finally:
        age_client.pool.putconn(conn)

    return dispatched
