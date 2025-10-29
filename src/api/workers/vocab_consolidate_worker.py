"""
Vocabulary Consolidation Worker (ADR-050).

Consolidates similar/redundant vocabulary types based on hysteresis thresholds.
This worker is triggered by the VocabConsolidationLauncher when the inactive
vocabulary ratio exceeds 20%.
"""

import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_vocab_consolidate_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute vocabulary consolidation as a background job.

    Uses the existing AITL consolidation logic from VocabularyManager
    (same logic as `kg vocab consolidate` CLI command).

    Args:
        job_data: Job parameters
            - operation: str - "consolidate"
            - auto_mode: bool - True for automatic consolidation (AITL)
            - strategy: str - "hysteresis"
            - upper_threshold: float - 0.20 (20%)
            - lower_threshold: float - 0.10 (10%)
            - target_size: int - Target vocabulary size (default: 90)
            - auto_execute_threshold: float - Auto-execute threshold (default: 0.90)
            - description: str - Job description
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with consolidation stats

    Raises:
        Exception: If consolidation fails
    """
    try:
        from src.api.lib.age_client import AGEClient
        from src.api.lib.vocabulary_manager import get_vocabulary_manager

        logger.info(f"🔄 Vocab consolidation worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Vocabulary consolidation worker started"
        })

        # Extract parameters from launcher (reads from vocab config)
        auto_mode = job_data.get("auto_mode", False)
        target_size = job_data.get("target_size", 90)  # Provided by launcher from vocab_max config
        auto_execute_threshold = job_data.get("auto_execute_threshold", 0.90)
        profile_name = job_data.get("aggressiveness_profile", "aggressive")  # For logging only

        logger.info(
            f"Vocab consolidation params: auto_mode={auto_mode}, "
            f"target_size={target_size}, threshold={auto_execute_threshold}"
        )

        # Initialize manager and client
        manager = get_vocabulary_manager()
        client = AGEClient()

        try:
            # Get initial size
            initial_size = client.get_vocabulary_size()

            # Update progress
            job_queue.update_job(job_id, {
                "progress": f"Analyzing vocabulary (initial size: {initial_size})"
            })

            # Run AITL consolidation (same logic as kg vocab consolidate)
            # Note: manager.aitl_consolidate_vocabulary() is async, so we need asyncio.run()
            results = asyncio.run(manager.aitl_consolidate_vocabulary(
                target_size=target_size,
                batch_size=1,
                auto_execute_threshold=auto_execute_threshold,
                dry_run=not auto_mode  # Only execute if auto_mode=True
            ))

            # Get final size
            final_size = client.get_vocabulary_size()
            size_reduction = initial_size - final_size

            # Update progress
            job_queue.update_job(job_id, {
                "progress": f"Consolidation complete: {size_reduction} types reduced"
            })

            # Build result
            result = {
                "status": "completed",
                "initial_size": initial_size,
                "final_size": final_size,
                "size_reduction": size_reduction,
                "auto_executed_count": len(results["auto_executed"]),
                "needs_review_count": len(results["needs_review"]),
                "rejected_count": len(results["rejected"]),
                "auto_mode": auto_mode,
                "dry_run": not auto_mode
            }

            logger.info(
                f"✅ Vocab consolidation worker completed: {job_id} "
                f"({size_reduction} types reduced, {result['auto_executed_count']} auto-executed)"
            )
            return result

        finally:
            client.close()

    except Exception as e:
        logger.error(f"❌ Vocab consolidation worker failed: {e}", exc_info=True)
        job_queue.update_job(job_id, {
            "status": "failed",
            "error": str(e)
        })
        raise
