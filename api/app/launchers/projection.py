"""
Embedding Projection Launcher (ADR-078, ADR-079).

Automatically re-compute projections when concept counts change significantly.
Follows the same pattern as EpistemicRemeasurementLauncher from ADR-065.

Storage:
    Projections are stored in Garage (S3-compatible object storage) via
    the projection worker (ADR-079).

Configuration:
    The per-ontology floor `min_ontology_concept_count` is shared with the
    annealing pipeline and read from kg_api.annealing_options (migration
    065). Below the floor, an ontology is too small for the heuristics
    above this layer (t-SNE perplexity, annealing scores) to produce
    meaningful results — both subsystems gate on the same row.
"""

from .base import JobLauncher
from api.app.lib.age_client import AGEClient
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Code default — overridden by the same `min_ontology_concept_count` row in
# kg_api.annealing_options that AnnealingLauncher reads. Keep this number in
# sync with annealing.DEFAULTS so a fresh DB (no annealing_options row yet)
# gates both subsystems identically.
DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT = 5


def _read_min_ontology_concept_count(conn) -> int:
    """Read the floor from kg_api.annealing_options, falling back to the code default."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM kg_api.annealing_options "
                "WHERE key = 'min_ontology_concept_count'"
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
    except Exception as e:
        logger.warning(
            f"ProjectionLauncher: could not read min_ontology_concept_count, "
            f"using default {DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT}: {e}"
        )
    return DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT


class ProjectionLauncher(JobLauncher):
    """
    Automatically re-compute projections when ontology changes significantly.

    Schedule: Every 1 hour (or triggered manually)
    Condition: Concept count changed by threshold since last projection
    Worker: projection_worker
    Pattern: Polling with per-ontology tracking

    Example flow:
    1. Scheduler fires hourly (or manual trigger)
    2. check_conditions() compares current concept counts with cached projections
    3. If any ontology changed significantly: enqueue projection job
    4. Worker computes projection and updates cache

    Tiny ontologies (below `min_ontology_concept_count`, read from
    annealing_options) are skipped. If they previously had a cached
    projection — e.g. they shrank below the floor after mass deletion —
    that stale cache is invalidated so consumers don't read an obsolete
    landscape. When the launcher is constructed with an explicit
    `ontology` arg and that ontology is below the floor, the launcher
    raises ValueError instead of skipping silently — manual triggers
    deserve a hard signal.
    """

    def __init__(
        self,
        job_queue,
        max_retries: int = 3,
        change_threshold: int = 5,
        min_ontology_concept_count: Optional[int] = None,
        ontology: Optional[str] = None
    ):
        """
        Initialize launcher.

        Args:
            job_queue: JobQueue instance
            max_retries: Maximum retry attempts
            change_threshold: Minimum concept count change to trigger recompute
            min_ontology_concept_count: Override for the per-ontology floor.
                When None (default), the floor is read from
                kg_api.annealing_options at check_conditions() time, sharing
                a single row with the annealing pipeline.
            ontology: Specific ontology to check (None = check all)
        """
        super().__init__(job_queue, max_retries)
        self.change_threshold = change_threshold
        self._configured_min_concepts = min_ontology_concept_count
        self.ontology = ontology
        self._stale_ontologies: List[str] = []
        self._active_min_concepts: int = (
            min_ontology_concept_count
            if min_ontology_concept_count is not None
            else DEFAULT_MIN_ONTOLOGY_CONCEPT_COUNT
        )

    def check_conditions(self) -> bool:
        """
        Check if any ontology needs projection update.

        Returns:
            True if at least one ontology has stale projection

        Raises:
            ValueError: When self.ontology is set explicitly and that
                ontology is below the floor — manual triggers shouldn't
                silently disappear.
        """
        client = AGEClient()
        try:
            conn = client.pool.getconn()
            try:
                # Resolve the floor: explicit constructor override wins,
                # otherwise read the shared annealing_options row.
                if self._configured_min_concepts is not None:
                    min_concepts = self._configured_min_concepts
                else:
                    min_concepts = _read_min_ontology_concept_count(conn)
                self._active_min_concepts = min_concepts

                # Get current concept counts per ontology via the canonical
                # mixin (ADR-048: prefer facade over raw Cypher in launchers).
                current_counts = client.list_ontology_concept_counts()

                if not current_counts:
                    logger.debug("No ontologies with concepts found")
                    return False

                # Filter to specific ontology if set
                if self.ontology:
                    if self.ontology not in current_counts:
                        logger.debug(f"Ontology '{self.ontology}' not found")
                        return False
                    count = current_counts[self.ontology]
                    if count < min_concepts:
                        # Manual mode: raise instead of silent skip so the
                        # operator sees the floor that blocked them.
                        raise ValueError(
                            f"Ontology '{self.ontology}' has {count} concepts "
                            f"(< min_ontology_concept_count={min_concepts}); "
                            f"refusing to project. Lower the floor in "
                            f"annealing_options or add more concepts."
                        )
                    current_counts = {self.ontology: count}

                # Compare with cached projections
                self._stale_ontologies = []

                for ontology, count in current_counts.items():
                    if count < min_concepts:
                        cached = self._get_cached_concept_count(ontology)
                        if cached is not None:
                            # Ontology shrank below the floor; the cached
                            # projection no longer matches reality. Drop it
                            # so read paths can't serve a stale landscape.
                            logger.info(
                                f"Ontology '{ontology}' shrank to {count} concepts "
                                f"(< min={min_concepts}); invalidating stale cache"
                            )
                            self._invalidate_projection_cache(ontology)
                        else:
                            logger.info(
                                f"Ontology '{ontology}' has {count} concepts "
                                f"(< min={min_concepts}); skipping projection"
                            )
                        continue

                    cached = self._get_cached_concept_count(ontology)

                    if cached is None:
                        # No cache exists - needs projection
                        logger.info(f"Ontology '{ontology}' has no projection cache")
                        self._stale_ontologies.append(ontology)
                    elif abs(count - cached) >= self.change_threshold:
                        # Significant change
                        logger.info(
                            f"Ontology '{ontology}' changed: {cached} → {count} concepts "
                            f"(delta: {abs(count - cached)})"
                        )
                        self._stale_ontologies.append(ontology)
                    else:
                        logger.debug(
                            f"Ontology '{ontology}' unchanged: {count} concepts"
                        )

                if self._stale_ontologies:
                    logger.info(
                        f"✓ ProjectionLauncher: {len(self._stale_ontologies)} ontologies need update"
                    )
                    return True

                return False

            finally:
                client.pool.putconn(conn)

        except Exception as e:
            logger.error(f"ProjectionLauncher condition check failed: {e}")
            raise
        finally:
            client.close()

    def prepare_job_data(self) -> Dict:
        """
        Prepare data for projection worker.

        Note: We enqueue one job at a time for the first stale ontology.
        The scheduler will call us again for remaining ontologies.

        The floor is threaded into job_data so the worker can defensively
        re-check (mirroring annealing_worker's pattern). Without this,
        any out-of-band enqueue path bypasses the launcher's gate.
        """
        if not self._stale_ontologies:
            # Should not happen if check_conditions returned True
            return {
                "operation": "compute_projection",
                "error": "No stale ontologies found"
            }

        # Process first stale ontology
        ontology = self._stale_ontologies[0]

        return {
            "operation": "compute_projection",
            "ontology": ontology,
            "algorithm": "tsne",  # Default algorithm
            "n_components": 3,
            "perplexity": 30,
            "include_grounding": True,
            "include_diversity": False,  # Off by default for performance
            "min_ontology_concept_count": self._active_min_concepts,
            "description": f"Scheduled projection update for '{ontology}'"
        }

    def get_job_type(self) -> str:
        """Return job type for worker registry."""
        return "projection"

    def _get_cached_concept_count(self, ontology: str) -> Optional[int]:
        """
        Get concept count from cached projection in Garage (ADR-079).

        Returns:
            Cached concept count or None if no cache
        """
        try:
            from api.app.workers.projection_worker import get_cached_projection

            # Get cached projection from Garage
            data = get_cached_projection(ontology, "concepts")
            if data is None:
                return None

            return data.get("statistics", {}).get("concept_count")
        except Exception as e:
            logger.warning(f"Failed to get cached projection for {ontology}: {e}")
            return None

    def _invalidate_projection_cache(self, ontology: str) -> None:
        """Drop the cached projection for an ontology that no longer qualifies."""
        try:
            from api.app.workers.projection_worker import invalidate_cached_projection

            invalidate_cached_projection(ontology, "concepts")
        except Exception as e:
            logger.warning(
                f"Failed to invalidate stale projection cache for '{ontology}': {e}"
            )
