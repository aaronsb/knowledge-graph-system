"""
Vocabulary Refresh Worker (ADR-050).

Re-integrates LLM-generated vocabulary categories into the base vocabulary.
This worker is triggered by the CategoryRefreshLauncher when llm_generated
categories are detected.
"""

import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)


def run_vocab_refresh_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute vocabulary category refresh as a background job.

    Uses the existing category refresh logic from VocabularyCategorizer
    (same logic as `kg vocab refresh-categories` CLI command).

    Args:
        job_data: Job parameters
            - operation: str - "refresh_categories"
            - auto_mode: bool - True for automatic refresh
            - filter: str - "llm_generated" to filter categories
            - only_computed: bool - Only refresh computed categories (default: True)
            - description: str - Job description
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with refresh stats

    Raises:
        Exception: If refresh fails
    """
    try:
        from api.api.lib.age_client import AGEClient
        from api.api.lib.vocabulary_categorizer import VocabularyCategorizer

        logger.info(f"🔄 Vocab refresh worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Vocabulary refresh worker started"
        })

        # Extract parameters
        only_computed = job_data.get("only_computed", True)

        logger.info(
            f"Vocab refresh params: only_computed={only_computed}"
        )

        # Initialize categorizer and client
        db_client = AGEClient()
        categorizer = VocabularyCategorizer(db_client)

        try:
            # Update progress
            job_queue.update_job(job_id, {
                "progress": "Refreshing category assignments"
            })

            # Refresh categories (same logic as kg vocab refresh-categories)
            # Note: categorizer.refresh_all_categories() is async, so we need asyncio.run()
            assignments = asyncio.run(categorizer.refresh_all_categories(
                only_computed=only_computed
            ))

            refreshed_count = len(assignments)

            # Count ambiguous assignments
            ambiguous_count = sum(1 for a in assignments if a.ambiguous)

            # Update progress
            job_queue.update_job(job_id, {
                "progress": f"Refresh complete: {refreshed_count} assignments updated"
            })

            # Build result
            result = {
                "status": "completed",
                "refreshed_count": refreshed_count,
                "ambiguous_count": ambiguous_count,
                "only_computed": only_computed,
                "assignments": [
                    {
                        "relationship_type": a.relationship_type,
                        "category": a.category,
                        "confidence": a.confidence,
                        "ambiguous": a.ambiguous
                    }
                    for a in assignments[:10]  # Include first 10 for logging
                ]
            }

            logger.info(
                f"✅ Vocab refresh worker completed: {job_id} "
                f"({refreshed_count} assignments updated, {ambiguous_count} ambiguous)"
            )
            return result

        finally:
            db_client.close()

    except Exception as e:
        logger.error(f"❌ Vocab refresh worker failed: {e}", exc_info=True)
        job_queue.update_job(job_id, {
            "status": "failed",
            "error": str(e)
        })
        raise
