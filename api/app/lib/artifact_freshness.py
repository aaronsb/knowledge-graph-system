"""
Artifact freshness as an ADR-207 InstanceDerivation.

Saved artifacts (polarity analyses, projections, query results) are the platform's
one *instance-level* materialized derivation: unlike the catalog index or the
grounding cache — which have a single stamp for the whole derivation — each
artifact row carries its own `graph_epoch` stamp and reconciles (regenerates)
independently from its stored parameters. That is exactly the ADR-207 D3
`InstanceDerivation` shape.

The freshness stamp is the committed-epoch tick (the universal clock, ADR-207
D1): an artifact is fresh while the tick it was computed at still equals the
current tick. `reconcile(id)` regenerates the artifact — an async job, the same
one `POST /artifacts/{id}/regenerate` dispatches.
"""

import logging
from typing import Optional

from .freshness import Budget, InstanceDerivation, register_derivation

logger = logging.getLogger(__name__)

# Artifact types that can be regenerated, mapped to their job type. Mirrors the
# map in routes/artifacts.py:regenerate_artifact — keep them in sync.
_REGENERATABLE = {
    "polarity_analysis": "polarity",
    "projection": "projection",
}


@register_derivation
class ArtifactDerivation(InstanceDerivation):
    """Saved artifacts under the ADR-207 freshness contract (per-row).

    Reads/writes go through psycopg2 connections from the auth dependency's
    pool (the same source the artifact routes use); imports are deferred to call
    time to avoid an import cycle with the routes/dependencies layer.
    """

    name = "artifacts"
    budget = Budget.strict()

    def version_stamp(self, item_id) -> Optional[int]:
        """The committed-epoch tick artifact `item_id` was computed at (None if
        the artifact does not exist)."""
        from api.app.dependencies.auth import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT graph_epoch FROM kg_api.artifacts WHERE id = %s",
                    (item_id,),
                )
                row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()

    def current_version(self) -> int:
        """The canonical clock now: the committed-epoch tick."""
        from api.app.dependencies.auth import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT kg_api.get_committed_epoch()")
                return int(cur.fetchone()[0] or 0)
        finally:
            conn.close()

    def reconcile(self, item_id) -> None:
        """Regenerate one artifact from its stored parameters (async job).

        System-triggered (no requesting user) — mirrors the enqueue in
        `routes/artifacts.py:regenerate_artifact`, which is the user-facing,
        auth-checked entry point. Raises ValueError if the artifact is missing
        or its type does not support regeneration.
        """
        from api.app.dependencies.auth import get_db_connection
        from api.app.services.job_queue import get_job_queue

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT artifact_type, parameters, ontology "
                    "FROM kg_api.artifacts WHERE id = %s",
                    (item_id,),
                )
                row = cur.fetchone()
            if not row:
                raise ValueError(f"artifact not found: {item_id}")
            artifact_type, parameters, ontology = row
            job_type = _REGENERATABLE.get(artifact_type)
            if not job_type:
                raise ValueError(
                    f"artifact type '{artifact_type}' does not support regeneration"
                )

            job_data = dict(parameters) if parameters else {}
            job_data["create_artifact"] = True
            if ontology:
                job_data["ontology"] = ontology
            job_data["description"] = (
                f"Reconcile (regenerate) stale artifact {item_id} ({artifact_type})"
            )

            queue = get_job_queue()
            job_id = queue.enqueue(job_type=job_type, job_data=job_data)
            queue.update_job(job_id, {"status": "approved", "approved_by": "freshness_reconcile"})
            logger.info(f"Artifact {item_id} reconcile → regeneration job {job_id}")
        finally:
            conn.close()
