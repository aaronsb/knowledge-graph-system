"""
Artifact Routes (ADR-083)

API endpoints for artifact persistence - storing and retrieving computed results.
"""

from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional, List
import logging
import psycopg2.extras

from ..models.artifact import (
    ArtifactCreate,
    ArtifactMetadata,
    ArtifactWithPayload,
    ArtifactList,
    ArtifactCreateResponse,
    ARTIFACT_TYPES,
    REPRESENTATIONS
)
from ..models.auth import UserInDB
from ..dependencies.auth import get_current_user, get_db_connection
from ..lib.garage import get_artifact_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _get_current_epoch(conn) -> int:
    """Get current graph epoch for freshness tracking."""
    with conn.cursor() as cur:
        cur.execute("SELECT kg_api.get_graph_epoch()")
        return cur.fetchone()[0] or 0


@router.get(
    "",
    response_model=ArtifactList,
    summary="List artifacts"
)
async def list_artifacts(
    artifact_type: Optional[str] = Query(None, description="Filter by artifact type"),
    representation: Optional[str] = Query(None, description="Filter by representation/source"),
    ontology: Optional[str] = Query(None, description="Filter by ontology"),
    owner_id: Optional[int] = Query(None, description="Filter by owner (admin only)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum artifacts to return"),
    offset: int = Query(0, ge=0, description="Number to skip for pagination"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    List artifacts with optional filtering.

    Returns metadata only (not payloads) for efficiency.
    Use GET /artifacts/{id}/payload to retrieve full payload.

    **Filters:**
    - `artifact_type`: polarity_analysis, projection, query_result, etc.
    - `representation`: cli, polarity_explorer, mcp_server, etc.
    - `ontology`: Filter by associated ontology
    - `owner_id`: Admin can view other users' artifacts

    **Ownership:**
    - Regular users see only their own artifacts
    - Admins can see all artifacts or filter by owner_id
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get current epoch for freshness check
            current_epoch = _get_current_epoch(conn)

            # Build query
            query = """
                SELECT id, artifact_type, representation, name, owner_id,
                       graph_epoch, created_at, expires_at, parameters, metadata,
                       ontology, concept_ids, query_definition_id,
                       inline_result IS NOT NULL as has_inline, garage_key
                FROM kg_api.artifacts
                WHERE 1=1
            """
            params = []

            # Filter by owner (unless admin viewing all)
            user_id = current_user.id
            user_role = current_user.role

            if owner_id is not None and user_role in ("admin", "platform_admin"):
                query += " AND owner_id = %s"
                params.append(owner_id)
            elif user_role not in ("admin", "platform_admin"):
                # Non-admins see only their own artifacts
                query += " AND (owner_id = %s OR owner_id IS NULL)"
                params.append(user_id)

            if artifact_type:
                query += " AND artifact_type = %s"
                params.append(artifact_type)

            if representation:
                query += " AND representation = %s"
                params.append(representation)

            if ontology:
                query += " AND ontology = %s"
                params.append(ontology)

            # Get total count
            count_query = f"SELECT COUNT(*) FROM ({query}) sub"
            cur.execute(count_query, params)
            total = cur.fetchone()[0]

            # Add ordering and pagination
            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = cur.fetchall()

            artifacts = []
            for row in rows:
                artifacts.append(ArtifactMetadata(
                    id=row[0],
                    artifact_type=row[1],
                    representation=row[2],
                    name=row[3],
                    owner_id=row[4],
                    graph_epoch=row[5],
                    is_fresh=(row[5] == current_epoch),
                    created_at=row[6],
                    expires_at=row[7],
                    parameters=row[8] or {},
                    metadata=row[9],
                    ontology=row[10],
                    concept_ids=row[11],
                    query_definition_id=row[12],
                    has_inline_result=row[13],
                    garage_key=row[14]
                ))

            return ArtifactList(
                artifacts=artifacts,
                total=total,
                limit=limit,
                offset=offset
            )
    finally:
        conn.close()


@router.get(
    "/{artifact_id}",
    response_model=ArtifactMetadata,
    summary="Get artifact metadata"
)
async def get_artifact(
    artifact_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get artifact metadata by ID.

    Returns metadata without payload. Use GET /artifacts/{id}/payload for full data.

    **Freshness:**
    The `is_fresh` field indicates whether the graph has changed since this
    artifact was created. Stale artifacts may need regeneration.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            current_epoch = _get_current_epoch(conn)

            cur.execute("""
                SELECT id, artifact_type, representation, name, owner_id,
                       graph_epoch, created_at, expires_at, parameters, metadata,
                       ontology, concept_ids, query_definition_id,
                       inline_result IS NOT NULL as has_inline, garage_key
                FROM kg_api.artifacts
                WHERE id = %s
            """, (artifact_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artifact not found: {artifact_id}"
                )

            # Check ownership
            user_id = current_user.id
            user_role = current_user.role
            owner_id = row[4]

            if owner_id is not None and owner_id != user_id:
                if user_role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this artifact"
                    )

            return ArtifactMetadata(
                id=row[0],
                artifact_type=row[1],
                representation=row[2],
                name=row[3],
                owner_id=row[4],
                graph_epoch=row[5],
                is_fresh=(row[5] == current_epoch),
                created_at=row[6],
                expires_at=row[7],
                parameters=row[8] or {},
                metadata=row[9],
                ontology=row[10],
                concept_ids=row[11],
                query_definition_id=row[12],
                has_inline_result=row[13],
                garage_key=row[14]
            )
    finally:
        conn.close()


@router.get(
    "/{artifact_id}/payload",
    response_model=ArtifactWithPayload,
    summary="Get artifact with payload"
)
async def get_artifact_payload(
    artifact_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get artifact with full payload.

    Retrieves the computed result, either from inline storage or Garage.

    **Storage tiers:**
    - Small artifacts (<10KB): Stored inline in database
    - Large artifacts (>=10KB): Stored in Garage, retrieved on demand

    **Performance:**
    For large artifacts, this endpoint fetches from Garage which adds latency.
    Consider caching payloads client-side using the `graph_epoch` for invalidation.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            current_epoch = _get_current_epoch(conn)

            cur.execute("""
                SELECT id, artifact_type, representation, name, owner_id,
                       graph_epoch, created_at, expires_at, parameters, metadata,
                       ontology, concept_ids, query_definition_id,
                       inline_result, garage_key
                FROM kg_api.artifacts
                WHERE id = %s
            """, (artifact_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artifact not found: {artifact_id}"
                )

            # Check ownership
            user_id = current_user.id
            user_role = current_user.role
            owner_id = row[4]

            if owner_id is not None and owner_id != user_id:
                if user_role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this artifact"
                    )

            # Get payload from inline or Garage
            inline_result = row[13]
            garage_key = row[14]

            if inline_result is not None:
                payload = inline_result
            elif garage_key:
                storage = get_artifact_storage()
                payload = storage.get(garage_key)
                if payload is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Artifact payload not found in storage: {garage_key}"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Artifact has no payload (neither inline nor garage)"
                )

            return ArtifactWithPayload(
                id=row[0],
                artifact_type=row[1],
                representation=row[2],
                name=row[3],
                owner_id=row[4],
                graph_epoch=row[5],
                is_fresh=(row[5] == current_epoch),
                created_at=row[6],
                expires_at=row[7],
                parameters=row[8] or {},
                metadata=row[9],
                ontology=row[10],
                concept_ids=row[11],
                query_definition_id=row[12],
                has_inline_result=(inline_result is not None),
                garage_key=garage_key,
                payload=payload
            )
    finally:
        conn.close()


@router.post(
    "",
    response_model=ArtifactCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create artifact"
)
async def create_artifact(
    artifact: ArtifactCreate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Create a new artifact.

    Stores a computed result with automatic tier routing:
    - Small payloads (<10KB): Stored inline in PostgreSQL
    - Large payloads (>=10KB): Stored in Garage S3

    **Required fields:**
    - `artifact_type`: Type of computation (polarity_analysis, projection, etc.)
    - `representation`: Source UI/tool (cli, polarity_explorer, etc.)
    - `parameters`: Parameters used to generate this artifact
    - `payload`: The computed result data

    **Freshness:**
    The current `graph_epoch` is automatically recorded for staleness detection.
    """
    # Validate artifact_type
    if artifact.artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid artifact_type. Must be one of: {ARTIFACT_TYPES}"
        )

    # Validate representation
    if artifact.representation not in REPRESENTATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid representation. Must be one of: {REPRESENTATIONS}"
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get current graph epoch
            current_epoch = _get_current_epoch(conn)
            user_id = current_user.id

            # Get next artifact ID for storage key generation
            cur.execute("SELECT nextval('kg_api.artifacts_id_seq')")
            artifact_id = cur.fetchone()[0]

            # Route payload to inline or Garage (need ID for garage key)
            storage = get_artifact_storage()
            inline_result, garage_key = storage.prepare_for_storage(
                artifact.artifact_type,
                artifact_id,
                artifact.payload
            )

            # Insert artifact with storage location in single statement
            # (has_content constraint requires inline_result OR garage_key)
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
                artifact.artifact_type,
                artifact.representation,
                artifact.name,
                user_id,
                current_epoch,
                artifact.expires_at,
                psycopg2.extras.Json(artifact.parameters),
                psycopg2.extras.Json(artifact.metadata) if artifact.metadata else None,
                artifact.ontology,
                artifact.concept_ids,
                artifact.query_definition_id,
                psycopg2.extras.Json(inline_result) if inline_result else None,
                garage_key
            ))

            created_at = cur.fetchone()[0]

            conn.commit()

            storage_location = "inline" if inline_result is not None else "garage"
            logger.info(
                f"Created artifact {artifact_id} ({artifact.artifact_type}) "
                f"for user {user_id}, stored {storage_location}"
            )

            return ArtifactCreateResponse(
                id=artifact_id,
                artifact_type=artifact.artifact_type,
                representation=artifact.representation,
                name=artifact.name,
                graph_epoch=current_epoch,
                storage_location=storage_location,
                garage_key=garage_key,
                created_at=created_at
            )

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create artifact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create artifact: {str(e)}"
        )
    finally:
        conn.close()


@router.delete(
    "/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete artifact"
)
async def delete_artifact(
    artifact_id: int,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Delete an artifact.

    Removes both the database record and any Garage-stored payload.

    **Authorization:**
    - Users can delete their own artifacts
    - Admins can delete any artifact
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get artifact to check ownership and garage_key
            cur.execute("""
                SELECT owner_id, garage_key FROM kg_api.artifacts WHERE id = %s
            """, (artifact_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artifact not found: {artifact_id}"
                )

            owner_id, garage_key = row

            # Check ownership
            user_id = current_user.id
            user_role = current_user.role

            if owner_id is not None and owner_id != user_id:
                if user_role not in ("admin", "platform_admin"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to delete this artifact"
                    )

            # Delete from Garage if stored there
            if garage_key:
                try:
                    storage = get_artifact_storage()
                    storage.delete(garage_key)
                except Exception as garage_err:
                    # Log but continue - DB record deletion is primary concern
                    # Orphaned Garage objects will be cleaned up by maintenance job
                    logger.warning(
                        f"Failed to delete Garage object {garage_key} for artifact {artifact_id}: {garage_err}. "
                        "Orphaned object will be cleaned up by maintenance job."
                    )

            # Delete database record
            cur.execute("DELETE FROM kg_api.artifacts WHERE id = %s", (artifact_id,))
            conn.commit()

            logger.info(f"Deleted artifact {artifact_id} by user {user_id}")

    finally:
        conn.close()
