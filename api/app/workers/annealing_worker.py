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
    automation_level = job_data.get("automation_level", "autonomous")
    min_ontology_age_epochs = job_data.get("min_ontology_age_epochs", 3)
    min_ontology_concept_count = job_data.get("min_ontology_concept_count", 5)

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

        manager = AnnealingManager(
            age_client,
            scorer,
            ai_provider=ai_provider,
            automation_level=automation_level,
        )

        job_queue.update_job(job_id, {
            "progress": {"stage": "scoring", "percent": 10}
        })

        # ADR-100: Check for cancellation before expensive scoring
        if job_queue.is_job_cancelled(job_id):
            logger.info(f"Annealing job {job_id} cancelled before scoring")
            return {"status": "cancelled"}

        result = asyncio.run(manager.run_annealing_cycle(
            demotion_threshold=demotion_threshold,
            promotion_min_degree=promotion_min_degree,
            max_proposals=max_proposals,
            dry_run=dry_run,
            derive_edges=derive_edges,
            overlap_threshold=overlap_threshold,
            specializes_threshold=specializes_threshold,
            min_ontology_age_epochs=min_ontology_age_epochs,
            min_ontology_concept_count=min_ontology_concept_count,
        ))

        # Autonomous mode: the manager already stored proposals as 'approved'
        # (no human-raceable pending window) — dispatch their execution jobs.
        # hitl proposals stay 'pending' for human review via the API.
        proposal_ids = result.get("proposal_ids", [])

        if automation_level == "autonomous" and not dry_run and proposal_ids:
            # ADR-100: Check for cancellation before dispatching proposals
            if job_queue.is_job_cancelled(job_id):
                logger.info(f"Annealing job {job_id} cancelled before proposal dispatch")
                return {"status": "cancelled", **result}

            job_queue.update_job(job_id, {
                "progress": {"stage": "executing_proposals", "percent": 90}
            })
            dispatched = _dispatch_approved_proposals(
                proposal_ids, age_client, job_queue
            )
            result["auto_dispatched"] = dispatched
            logger.info(
                f"Autonomous mode: dispatched {dispatched} of "
                f"{len(proposal_ids)} approved proposals for execution"
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


def _dispatch_approved_proposals(
    proposal_ids: List[int],
    age_client: AGEClient,
    job_queue,
) -> int:
    """Dispatch execution jobs for auto-approved annealing proposals.

    In autonomous mode the annealing manager stores proposals already
    'approved' — there is no pending→approved transition to make here. This
    enqueues one proposal_execution job per proposal, the same job the human
    review endpoint dispatches on approval.

    Guarded on status == 'approved' so a re-run cannot double-dispatch a
    proposal that is already executing or executed.

    Returns the number of proposals dispatched.
    """
    dispatched = 0
    conn = age_client.pool.getconn()
    try:
        for proposal_id in proposal_ids:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM kg_api.annealing_proposals WHERE id = %s",
                        (proposal_id,),
                    )
                    row = cur.fetchone()
                conn.commit()  # close the read txn before returning conn to pool

                if not row or row[0] != "approved":
                    logger.warning(
                        f"Proposal {proposal_id} not in 'approved' state "
                        f"({row[0] if row else 'missing'}) — skipping dispatch"
                    )
                    continue

                # Dispatch execution job (same job as the human review endpoint)
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
                # ADR-100: Lane manager will claim the approved job
                dispatched += 1

                logger.info(
                    f"Dispatched execution job {exec_job_id} for "
                    f"approved proposal {proposal_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to dispatch proposal {proposal_id}: {e}",
                    exc_info=True,
                )
    finally:
        age_client.pool.putconn(conn)

    return dispatched
