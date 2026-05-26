"""
Vocab Embedding Launcher (migration 069).

Background companion to the cold-start path. Pattern-matches
EpistemicRemeasurementLauncher: polls hourly, runs when there's vocab
membership growth that the embedding worker hasn't caught up with yet.

The launcher exists because two earlier paths weren't sufficient on
their own:

- Cold-start at boot covers the case where the API process restarts
  after vocab grew. But long-running processes (the common case in
  production) never re-check.

- The inline `add_edge_type(..., ai_provider=...)` path during LLM
  extraction covers new types added through ingestion. But it skips on
  exceptions (silent), and it doesn't cover types added by other paths
  (migrations, manual SQL).

This launcher is the safety net: if `vocabulary_change_counter` has
moved past `last_processed_vocab_change_counter` for this component,
the worker invokes EmbeddingWorker.regenerate_missing_if_vocab_changed
to fill in any missing embeddings.
"""

import logging
from typing import Dict

from .base import JobLauncher
from api.app.lib.age_client import AGEClient

logger = logging.getLogger(__name__)


class VocabEmbeddingLauncher(JobLauncher):
    """
    Automatically regenerate missing vocab embeddings when vocabulary
    membership grows.

    Schedule: Every 1 hour (cron: "0 * * * *")
    Condition: vocabulary_change_counter > last_processed_vocab_change_counter
               for the 'builtin_vocabulary_embeddings' component (any delta)
    Worker: vocab_embedding_worker
    Pattern: Polling (checks hourly, runs when delta > 0)

    Distinct from EpistemicRemeasurementLauncher: that one also keys on
    vocabulary_change_counter but reads the *global* delta via
    mark_measurement_complete / get_counter_delta. We use the
    *per-component* cursor on system_initialization_status so the two
    consumers track progress independently and don't reset each other.
    """

    def __init__(
        self,
        job_queue,
        max_retries: int = 5,
        component: str = "builtin_vocabulary_embeddings",
    ):
        """
        Args:
            job_queue: JobQueue instance
            max_retries: Maximum retry attempts for failed jobs
            component: which row of system_initialization_status to track
        """
        super().__init__(job_queue, max_retries)
        self.component = component

    def check_conditions(self) -> bool:
        """
        Check whether there's vocab membership the embedding worker hasn't
        caught up with yet.

        Reads the membership counter and the per-component cursor in one
        round-trip each, computes the delta in Python. Threshold is 1
        (any new vocab triggers a run) — embedding generation per type
        is cheap enough that we don't need to batch.
        """
        try:
            client = AGEClient()
            conn = client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT counter FROM graph_metrics "
                        "WHERE metric_name = 'vocabulary_change_counter'"
                    )
                    row = cur.fetchone()
                    current_counter = int(row[0]) if row else 0

                    cur.execute(
                        "SELECT last_processed_vocab_change_counter "
                        "FROM kg_api.system_initialization_status "
                        "WHERE component = %s",
                        (self.component,)
                    )
                    row = cur.fetchone()
                    last_processed = int(row[0]) if row else 0

                if current_counter > last_processed:
                    logger.info(
                        f"✓ VocabEmbeddingLauncher: vocabulary_change_counter "
                        f"({current_counter}) > last_processed ({last_processed}) "
                        f"for component={self.component}"
                    )
                    return True

                logger.debug(
                    f"VocabEmbeddingLauncher: counter ({current_counter}) at or "
                    f"below last_processed ({last_processed}) — no work"
                )
                return False
            finally:
                client.pool.putconn(conn)

        except Exception as e:
            # Let exceptions bubble up so the scheduler can retry.
            logger.error(f"VocabEmbeddingLauncher condition check failed: {e}")
            raise

    def prepare_job_data(self) -> Dict:
        """
        Prepare data for vocab embedding worker.

        The worker reads the membership counter itself (snapshot at start
        of run) — we don't pass it through job_data because there's a
        race window between launcher and worker startup, and the worker's
        snapshot is what gets stored on completion.
        """
        return {
            "operation": "regenerate_missing_vocab_embeddings",
            "component": self.component,
            "description": (
                f"Scheduled vocab embedding regen "
                f"(component={self.component})"
            ),
        }

    def get_job_type(self) -> str:
        """Return job type for worker registry."""
        return "vocab_embedding"
