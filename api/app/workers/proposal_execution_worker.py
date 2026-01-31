"""
Proposal Execution Worker (ADR-200 Phase 4).

Executes approved breathing proposals as background jobs.
Follows the worker pattern: run_<type>_worker(job_data, job_id, job_queue) -> Dict
"""

import json
import logging
from typing import Any, Dict

from api.app.lib.age_client import AGEClient
from api.app.services.proposal_executor import ProposalExecutor

logger = logging.getLogger(__name__)


def run_proposal_execution_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute a single approved proposal.

    Args:
        job_data:
            - proposal_id: int — the proposal to execute
            - triggered_by: str — username or 'breathing_worker'
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with execution outcome
    """
    proposal_id = job_data.get("proposal_id")
    triggered_by = job_data.get("triggered_by", "unknown")

    if not proposal_id:
        return {"status": "failed", "error": "Missing proposal_id in job_data"}

    logger.info(
        f"Proposal execution worker starting (job {job_id}): "
        f"proposal={proposal_id}, triggered_by={triggered_by}"
    )

    job_queue.update_job(job_id, {
        "progress": {"stage": "loading_proposal", "percent": 0}
    })

    age_client = None
    try:
        age_client = AGEClient()

        # 1. Load proposal
        proposal = _load_proposal(age_client, proposal_id)
        if not proposal:
            return {"status": "failed", "error": f"Proposal {proposal_id} not found"}

        # 2. Atomic claim: set status='executing' only if currently 'approved'
        #    Single UPDATE with WHERE guard prevents race between concurrent workers.
        claimed = _claim_proposal(age_client, proposal_id)
        if not claimed:
            return {
                "status": "skipped",
                "reason": f"Proposal not claimable (status='{proposal['status']}')",
            }

        job_queue.update_job(job_id, {
            "progress": {"stage": "executing", "percent": 30}
        })

        # 4. Execute
        executor = ProposalExecutor(age_client)

        if proposal["proposal_type"] == "promotion":
            result = executor.execute_promotion(proposal)
        elif proposal["proposal_type"] == "demotion":
            result = executor.execute_demotion(proposal)
        else:
            result = {
                "success": False,
                "error": f"Unknown proposal type: {proposal['proposal_type']}",
            }

        # 5. Update proposal with result
        if result.get("success"):
            _update_proposal_status(
                age_client, proposal_id, "executed",
                execution_result=result,
            )
            logger.info(
                f"Proposal {proposal_id} ({proposal['proposal_type']}) "
                f"executed successfully"
            )
        else:
            _update_proposal_status(
                age_client, proposal_id, "failed",
                execution_result=result,
            )
            logger.warning(
                f"Proposal {proposal_id} ({proposal['proposal_type']}) "
                f"failed: {result.get('error')}"
            )

        job_queue.update_job(job_id, {
            "progress": {"stage": "complete", "percent": 100}
        })

        return {
            "status": "completed" if result.get("success") else "failed",
            "proposal_id": proposal_id,
            "proposal_type": proposal["proposal_type"],
            **result,
        }

    except Exception as e:
        logger.error(
            f"Proposal execution worker failed (job {job_id}): {e}",
            exc_info=True,
        )
        # Try to mark proposal as failed
        if age_client and proposal_id:
            try:
                _update_proposal_status(
                    age_client, proposal_id, "failed",
                    execution_result={"success": False, "error": str(e)},
                )
            except Exception:
                pass
        return {"status": "failed", "error": str(e)}

    finally:
        if age_client:
            age_client.close()


def _load_proposal(age_client, proposal_id: int) -> Dict[str, Any] | None:
    """Load a proposal from the breathing_proposals table."""
    from psycopg2.extras import RealDictCursor
    conn = age_client.pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, proposal_type, ontology_name, anchor_concept_id,
                       target_ontology, reasoning, mass_score, coherence_score,
                       protection_score, status, suggested_name,
                       suggested_description
                FROM kg_api.breathing_proposals
                WHERE id = %s
                """,
                (proposal_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "proposal_type": row["proposal_type"],
                "ontology_name": row["ontology_name"],
                "anchor_concept_id": row.get("anchor_concept_id"),
                "target_ontology": row.get("target_ontology"),
                "reasoning": row["reasoning"],
                "mass_score": float(row["mass_score"]) if row.get("mass_score") is not None else None,
                "coherence_score": float(row["coherence_score"]) if row.get("coherence_score") is not None else None,
                "protection_score": float(row["protection_score"]) if row.get("protection_score") is not None else None,
                "status": row["status"],
                "suggested_name": row.get("suggested_name"),
                "suggested_description": row.get("suggested_description"),
            }
    finally:
        age_client.pool.putconn(conn)


def _claim_proposal(age_client, proposal_id: int) -> bool:
    """Atomically claim a proposal by setting status='executing' only if 'approved'.

    Returns True if the row was updated (i.e., we won the claim).
    """
    conn = age_client.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE kg_api.breathing_proposals
                SET status = 'executing'
                WHERE id = %s AND status = 'approved'
                RETURNING id
                """,
                (proposal_id,),
            )
            row = cur.fetchone()
            conn.commit()
            return row is not None
    except Exception as e:
        logger.error(f"Failed to claim proposal {proposal_id}: {e}")
        conn.rollback()
        return False
    finally:
        age_client.pool.putconn(conn)


def _update_proposal_status(
    age_client,
    proposal_id: int,
    status: str,
    execution_result: Dict[str, Any] | None = None,
) -> bool:
    """Update a proposal's status and optionally store execution result."""
    conn = age_client.pool.getconn()
    try:
        with conn.cursor() as cur:
            if status in ("executed", "failed"):
                cur.execute(
                    """
                    UPDATE kg_api.breathing_proposals
                    SET status = %s, executed_at = NOW(), execution_result = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        status,
                        json.dumps(execution_result) if execution_result else None,
                        proposal_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE kg_api.breathing_proposals
                    SET status = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (status, proposal_id),
                )
            row = cur.fetchone()
            conn.commit()
            return row is not None
    except Exception as e:
        logger.error(f"Failed to update proposal {proposal_id} to '{status}': {e}")
        conn.rollback()
        return False
    finally:
        age_client.pool.putconn(conn)
