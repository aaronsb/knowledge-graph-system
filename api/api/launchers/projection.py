"""
Embedding Projection Launcher (ADR-078, ADR-079).

Automatically re-compute projections when concept counts change significantly.
Follows the same pattern as EpistemicRemeasurementLauncher from ADR-065.

Storage:
    Projections are stored in Garage (S3-compatible object storage) via
    the projection worker (ADR-079).
"""

from .base import JobLauncher
from api.api.lib.age_client import AGEClient
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        job_queue,
        max_retries: int = 3,
        change_threshold: int = 5,
        ontology: Optional[str] = None
    ):
        """
        Initialize launcher.

        Args:
            job_queue: JobQueue instance
            max_retries: Maximum retry attempts
            change_threshold: Minimum concept count change to trigger recompute
            ontology: Specific ontology to check (None = check all)
        """
        super().__init__(job_queue, max_retries)
        self.change_threshold = change_threshold
        self.ontology = ontology
        self._stale_ontologies: List[str] = []

    def check_conditions(self) -> bool:
        """
        Check if any ontology needs projection update.

        Returns:
            True if at least one ontology has stale projection
        """
        client = AGEClient()
        try:
            conn = client.pool.getconn()
            try:
                # Get current concept counts per ontology
                current_counts = self._get_ontology_concept_counts(conn)

                if not current_counts:
                    logger.debug("No ontologies with concepts found")
                    return False

                # Filter to specific ontology if set
                if self.ontology:
                    if self.ontology not in current_counts:
                        logger.debug(f"Ontology '{self.ontology}' not found")
                        return False
                    current_counts = {self.ontology: current_counts[self.ontology]}

                # Compare with cached projections
                self._stale_ontologies = []

                for ontology, count in current_counts.items():
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
            "description": f"Scheduled projection update for '{ontology}'"
        }

    def get_job_type(self) -> str:
        """Return job type for worker registry."""
        return "projection"

    def _get_ontology_concept_counts(self, conn) -> Dict[str, int]:
        """
        Get concept counts per ontology from the graph.

        Returns:
            Dict mapping ontology name to concept count
        """
        query = """
            SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
                MATCH (c:Concept)-[:APPEARS]->(:Source)
                WHERE c.embedding IS NOT NULL
                WITH c.concept_id as cid
                MATCH (c2:Concept {concept_id: cid})-[:APPEARS]->(s:Source)
                RETURN s.document as ontology, count(DISTINCT c2) as count
            $$) AS (ontology agtype, count agtype)
        """

        counts = {}
        with conn.cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                ontology = str(row[0]).strip('"')
                count = int(str(row[1]))
                counts[ontology] = count

        return counts

    def _get_cached_concept_count(self, ontology: str) -> Optional[int]:
        """
        Get concept count from cached projection in Garage (ADR-079).

        Returns:
            Cached concept count or None if no cache
        """
        try:
            from api.api.workers.projection_worker import get_cached_projection

            # Get cached projection from Garage
            data = get_cached_projection(ontology, "concepts")
            if data is None:
                return None

            return data.get("statistics", {}).get("concept_count")
        except Exception as e:
            logger.warning(f"Failed to get cached projection for {ontology}: {e}")
            return None
