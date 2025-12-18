"""
Artifact Helper for Workers (ADR-083 Phase 4).

Provides utilities for workers to create artifacts from job results and
link them to their originating jobs. Encapsulates the common pattern of:
1. Create artifact with computed result
2. Link artifact to job via artifact_id
3. Update job status with artifact reference

Usage in workers:
    from api.api.workers.artifact_helper import create_job_artifact

    # At job completion:
    artifact_id = create_job_artifact(
        job_id=job_id,
        job_queue=job_queue,
        user_id=user_id,
        artifact_type="projection",
        representation="embedding_landscape",
        name=f"Projection: {ontology}",
        parameters=job_params,
        payload=projection_data,
        ontology=ontology
    )
"""

import logging
from typing import Dict, Any, Optional, List
import psycopg2.extras

logger = logging.getLogger(__name__)


def create_job_artifact(
    job_id: str,
    job_queue,
    user_id: int,
    artifact_type: str,
    representation: str,
    name: str,
    parameters: Dict[str, Any],
    payload: Dict[str, Any],
    ontology: Optional[str] = None,
    concept_ids: Optional[List[str]] = None,
    query_definition_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    expires_at: Optional[str] = None
) -> Optional[int]:
    """
    Create an artifact from job results and link to the job.

    This is the main entry point for workers to persist their results
    as artifacts. Handles:
    - Getting current graph epoch
    - Routing to inline or Garage storage
    - Creating artifact record
    - Linking artifact to job

    Args:
        job_id: Job ID to link the artifact to
        job_queue: JobQueue instance for job updates
        user_id: Owner of the artifact (from job's user_id)
        artifact_type: Type of artifact (projection, polarity_analysis, etc.)
        representation: Source representation (embedding_landscape, polarity_explorer, etc.)
        name: Human-readable artifact name
        parameters: Parameters used to generate this artifact
        payload: The computed result data
        ontology: Optional ontology name
        concept_ids: Optional list of concept IDs involved
        query_definition_id: Optional link to query definition
        metadata: Optional additional metadata
        expires_at: Optional expiration timestamp (ISO format)

    Returns:
        Artifact ID if created successfully, None if failed

    Note:
        On failure, logs error but does not raise. The job can still
        complete successfully without artifact persistence.
    """
    try:
        from api.api.lib.garage import get_artifact_storage
        from api.api.dependencies.auth import get_db_connection

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get current graph epoch
                cur.execute("""
                    SELECT counter FROM public.graph_metrics
                    WHERE metric_name = 'graph_change_counter'
                """)
                row = cur.fetchone()
                current_epoch = row[0] if row else 0

                # Get next artifact ID for storage key generation
                cur.execute("SELECT nextval('kg_api.artifacts_id_seq')")
                artifact_id = cur.fetchone()[0]

                # Route payload to inline or Garage
                storage = get_artifact_storage()
                inline_result, garage_key = storage.prepare_for_storage(
                    artifact_type,
                    artifact_id,
                    payload
                )

                # Insert artifact
                cur.execute("""
                    INSERT INTO kg_api.artifacts (
                        id, artifact_type, representation, name, owner_id,
                        graph_epoch, expires_at, parameters, metadata,
                        ontology, concept_ids, query_definition_id,
                        inline_result, garage_key
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING created_at
                """, (
                    artifact_id,
                    artifact_type,
                    representation,
                    name,
                    user_id,
                    current_epoch,
                    expires_at,
                    psycopg2.extras.Json(parameters),
                    psycopg2.extras.Json(metadata) if metadata else None,
                    ontology,
                    concept_ids,
                    query_definition_id,
                    psycopg2.extras.Json(inline_result) if inline_result else None,
                    garage_key
                ))

                created_at = cur.fetchone()[0]
                conn.commit()

                logger.info(
                    f"Created artifact {artifact_id} ({artifact_type}) for job {job_id}"
                )

                # Link artifact to job
                job_queue.update_job(job_id, {"artifact_id": artifact_id})

                return artifact_id

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to create artifact for job {job_id}: {e}")
        return None


def create_artifact(
    user_id: int,
    artifact_type: str,
    representation: str,
    name: str,
    parameters: Dict[str, Any],
    payload: Dict[str, Any],
    ontology: Optional[str] = None,
    concept_ids: Optional[List[str]] = None,
    query_definition_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    expires_at: Optional[str] = None
) -> Optional[int]:
    """
    Create an artifact directly (without job linkage).

    Used for synchronous operations that create artifacts without using
    the job queue (e.g., fast projection computations).

    Args:
        user_id: Owner of the artifact
        artifact_type: Type of artifact (projection, polarity_analysis, etc.)
        representation: Source representation (embedding_landscape, cli, etc.)
        name: Human-readable artifact name
        parameters: Parameters used to generate this artifact
        payload: The computed result data
        ontology: Optional ontology name
        concept_ids: Optional list of concept IDs involved
        query_definition_id: Optional link to query definition
        metadata: Optional additional metadata
        expires_at: Optional expiration timestamp (ISO format)

    Returns:
        Artifact ID if created successfully, None if failed
    """
    try:
        from api.api.lib.garage import get_artifact_storage
        from api.api.dependencies.auth import get_db_connection

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get current graph epoch
                cur.execute("""
                    SELECT counter FROM public.graph_metrics
                    WHERE metric_name = 'graph_change_counter'
                """)
                row = cur.fetchone()
                current_epoch = row[0] if row else 0

                # Get next artifact ID for storage key generation
                cur.execute("SELECT nextval('kg_api.artifacts_id_seq')")
                artifact_id = cur.fetchone()[0]

                # Route payload to inline or Garage
                storage = get_artifact_storage()
                inline_result, garage_key = storage.prepare_for_storage(
                    artifact_type,
                    artifact_id,
                    payload
                )

                # Insert artifact
                cur.execute("""
                    INSERT INTO kg_api.artifacts (
                        id, artifact_type, representation, name, owner_id,
                        graph_epoch, expires_at, parameters, metadata,
                        ontology, concept_ids, query_definition_id,
                        inline_result, garage_key
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING created_at
                """, (
                    artifact_id,
                    artifact_type,
                    representation,
                    name,
                    user_id,
                    current_epoch,
                    expires_at,
                    psycopg2.extras.Json(parameters),
                    psycopg2.extras.Json(metadata) if metadata else None,
                    ontology,
                    concept_ids,
                    query_definition_id,
                    psycopg2.extras.Json(inline_result) if inline_result else None,
                    garage_key
                ))

                conn.commit()

                logger.info(
                    f"Created artifact {artifact_id} ({artifact_type}) for user {user_id}"
                )

                return artifact_id

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to create artifact: {e}")
        return None


def get_job_user_id(job_id: str) -> Optional[int]:
    """
    Get the user_id for a job.

    Args:
        job_id: Job ID

    Returns:
        User ID or None if job not found
    """
    try:
        from api.api.dependencies.auth import get_db_connection

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM kg_api.jobs WHERE job_id = %s",
                    (job_id,)
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to get user_id for job {job_id}: {e}")
        return None
