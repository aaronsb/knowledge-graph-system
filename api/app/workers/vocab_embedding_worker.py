"""
Vocab Embedding Worker (migration 069).

Background worker triggered by VocabEmbeddingLauncher. Invokes the same
EmbeddingWorker.regenerate_missing_if_vocab_changed workhorse the
boot-time cold-start uses — single source of truth for "regenerate
missing vocab embeddings if vocab membership has advanced."

Pattern-matches vocab_refresh_worker and epistemic_remeasurement_worker.
"""

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def run_vocab_embedding_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute vocab embedding regeneration as a background job.

    Same logic as `kg admin embedding regenerate --type vocabulary` but
    gated by the membership-counter delta — does nothing if no new vocab
    has arrived since the last successful run for this component.

    Args:
        job_data: Job parameters from VocabEmbeddingLauncher.prepare_job_data
            - operation: "regenerate_missing_vocab_embeddings"
            - component: system_initialization_status row to track
              (default: "builtin_vocabulary_embeddings")
            - description: human-readable job summary
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict mirroring EmbeddingJobResult.to_dict() — target_count,
        processed_count, failed_count, duration_ms, status.

    Raises:
        Exception: If embedding generation fails catastrophically. Per-type
            failures inside the worker are logged but don't raise (matches
            the chunk-recovery pattern in calculate_grounding_strength_batch).
    """
    try:
        from api.app.services.embedding_worker import get_embedding_worker
        from api.app.lib.age_client import AGEClient
        from api.app.lib.ai_providers import get_provider

        component = job_data.get("component", "builtin_vocabulary_embeddings")

        logger.info(f"🔄 Vocab embedding worker started: {job_id} (component={component})")

        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": "Vocab embedding worker started"
        })

        # ADR-100: check for cancellation before starting work
        if job_queue.is_job_cancelled(job_id):
            logger.info(f"Vocab embedding job {job_id} cancelled before start")
            return {"status": "cancelled"}

        # Build embedding worker. get_embedding_worker is the singleton
        # factory already used by the API startup path; reusing it means
        # the launcher path and cold-start path share the same instance.
        age_client = AGEClient()
        ai_provider = get_provider()
        embedding_worker = get_embedding_worker(age_client, ai_provider)

        if embedding_worker is None:
            raise RuntimeError(
                "EmbeddingWorker not initialized — cannot regen vocab embeddings"
            )

        # Run the shared workhorse. The counter-delta gate inside this
        # method is the second line of defense: even if the launcher's
        # check_conditions returned True but the counter advanced again
        # between then and now (or another worker raced us to the regen),
        # the method exits cleanly.
        result = asyncio.run(
            embedding_worker.regenerate_missing_if_vocab_changed(
                component=component,
                job_type="vocabulary_update",
            )
        )

        job_queue.update_job(job_id, {
            "status": "completed",
            "progress": (
                f"Processed {result.processed_count}/{result.target_count} types "
                f"in {result.duration_ms}ms"
            ),
        })

        logger.info(
            f"✓ Vocab embedding worker complete: {job_id} — "
            f"{result.processed_count}/{result.target_count} types, "
            f"{result.failed_count} failed"
        )

        return {
            "status": "completed",
            "component": component,
            "target_count": result.target_count,
            "processed_count": result.processed_count,
            "failed_count": result.failed_count,
            "duration_ms": result.duration_ms,
        }

    except Exception as e:
        logger.error(f"Vocab embedding worker failed: {job_id} — {e}", exc_info=True)
        job_queue.update_job(job_id, {
            "status": "failed",
            "error": str(e),
        })
        raise
