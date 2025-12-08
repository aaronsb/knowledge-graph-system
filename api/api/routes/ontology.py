"""
Ontology management endpoints for organizing knowledge domains.

Provides REST API access to:
- List all ontologies
- Get ontology details and statistics
- List files within an ontology
- Delete ontologies with orphan cleanup
"""

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
import logging

from ..dependencies.auth import CurrentUser, require_role
from ..models.ontology import (
    OntologyListResponse,
    OntologyItem,
    OntologyInfoResponse,
    OntologyFilesResponse,
    OntologyFileInfo,
    OntologyDeleteRequest,
    OntologyDeleteResponse,
    OntologyRenameRequest,
    OntologyRenameResponse
)
from api.api.lib.age_client import AGEClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ontology", tags=["ontology"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.get("/", response_model=OntologyListResponse)
async def list_ontologies(
    current_user: CurrentUser
):
    """
    List all ontologies in the knowledge graph (ADR-060).

    Returns summary statistics for each ontology including
    file count, chunk count, and concept count.

    **Authentication:** Requires valid OAuth token

    Returns:
        OntologyListResponse with all ontologies

    Example:
        GET /ontology/
    """
    client = get_age_client()
    try:
        result = client._execute_cypher("""
            MATCH (s:Source)
            WITH DISTINCT s.document as ontology
            MATCH (src:Source {document: ontology})
            WITH ontology,
                 count(DISTINCT src) as source_count,
                 count(DISTINCT src.file_path) as file_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS]->(s:Source {document: ontology})
            WITH ontology, source_count, file_count, count(DISTINCT c) as concept_count
            RETURN ontology, source_count, file_count, concept_count
            ORDER BY ontology
        """)

        ontologies = [
            OntologyItem(
                ontology=record['ontology'],
                source_count=record['source_count'],
                file_count=record['file_count'],
                concept_count=record['concept_count']
            )
            for record in (result or [])
        ]

        return OntologyListResponse(
            count=len(ontologies),
            ontologies=ontologies
        )

    except Exception as e:
        logger.error(f"Failed to list ontologies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list ontologies: {str(e)}")
    finally:
        client.close()


@router.get("/{ontology_name}", response_model=OntologyInfoResponse)
async def get_ontology_info(
    ontology_name: str,
    current_user: CurrentUser
):
    """
    Get detailed information about a specific ontology (ADR-060).

    Includes:
    - File count and list of files
    - Chunk (source) count
    - Concept count
    - Evidence instance count
    - Relationship count

    **Authentication:** Requires valid OAuth token

    Args:
        ontology_name: Name of the ontology

    Returns:
        OntologyInfoResponse with detailed statistics

    Raises:
        404: If ontology not found

    Example:
        GET /ontology/Research%20Papers
    """
    client = get_age_client()
    try:
        # Check if ontology exists
        exists_check = client._execute_cypher(
            f"MATCH (s:Source {{document: '{ontology_name}'}}) RETURN count(s) > 0 as ontology_exists",
            fetch_one=True
        )

        if not exists_check or not exists_check['ontology_exists']:
            raise HTTPException(status_code=404, detail=f"Ontology '{ontology_name}' not found")

        # Get statistics
        stats = client._execute_cypher(f"""
            MATCH (s:Source {{document: '{ontology_name}'}})
            WITH count(DISTINCT s) as source_count,
                 count(DISTINCT s.file_path) as file_count,
                 collect(DISTINCT s.file_path) as files
            OPTIONAL MATCH (c:Concept)-[:APPEARS]->(src:Source {{document: '{ontology_name}'}})
            WITH source_count, file_count, files, count(DISTINCT c) as concept_count
            OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(src:Source {{document: '{ontology_name}'}})
            WITH source_count, file_count, files, concept_count, count(DISTINCT i) as instance_count
            OPTIONAL MATCH (ontology_concept:Concept)-[:APPEARS]->(:Source {{document: '{ontology_name}'}})
            OPTIONAL MATCH (ontology_concept)-[r]->(other:Concept)
            RETURN source_count, file_count, files, concept_count, instance_count, count(r) as relationship_count
        """, fetch_one=True)

        statistics = {
            "source_count": stats['source_count'],
            "file_count": stats['file_count'],
            "concept_count": stats['concept_count'],
            "instance_count": stats['instance_count'],
            "relationship_count": stats['relationship_count']
        }

        # Filter out None values from files list
        files = [f for f in stats['files'] if f is not None]

        return OntologyInfoResponse(
            ontology=ontology_name,
            statistics=statistics,
            files=files
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ontology info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ontology info: {str(e)}")
    finally:
        client.close()


@router.get("/{ontology_name}/files", response_model=OntologyFilesResponse)
async def get_ontology_files(
    ontology_name: str,
    current_user: CurrentUser
):
    """
    List all files in a specific ontology with their statistics (ADR-060).

    **Authentication:** Requires valid OAuth token

    Args:
        ontology_name: Name of the ontology

    Returns:
        OntologyFilesResponse with file details

    Raises:
        404: If ontology not found or has no files

    Example:
        GET /ontology/Research%20Papers/files
    """
    client = get_age_client()
    try:
        result = client._execute_cypher(f"""
            MATCH (s:Source {{document: '{ontology_name}'}})
            WITH DISTINCT s.file_path as file_path
            WHERE file_path IS NOT NULL
            MATCH (src:Source {{document: '{ontology_name}', file_path: file_path}})
            WITH file_path, count(src) as chunk_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS]->(s:Source {{document: '{ontology_name}', file_path: file_path}})
            WITH file_path, chunk_count, count(DISTINCT c) as concept_count
            RETURN file_path, chunk_count, concept_count
            ORDER BY file_path
        """)

        files = [
            OntologyFileInfo(
                file_path=record['file_path'],
                chunk_count=record['chunk_count'],
                concept_count=record['concept_count']
            )
            for record in (result or [])
        ]

        if not files:
            raise HTTPException(
                status_code=404,
                detail=f"No files found in ontology '{ontology_name}'"
            )

        return OntologyFilesResponse(
            ontology=ontology_name,
            count=len(files),
            files=files
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ontology files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ontology files: {str(e)}")
    finally:
        client.close()


@router.delete("/{ontology_name}", response_model=OntologyDeleteResponse)
async def delete_ontology(
    ontology_name: str,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin")),
    force: bool = QueryParam(False, description="Skip confirmation and force deletion")
):
    """
    Delete an ontology and all its data (Admin only - ADR-060).

    **WARNING: This action cannot be undone!**

    Deletes:
    - All Source nodes belonging to the ontology
    - All Instance nodes linked to those sources
    - All DocumentMeta nodes for this ontology (ADR-051: provenance metadata)
    - Orphaned Concept nodes (concepts with no remaining sources)
    - All source embeddings for deleted sources (kg_api.source_embeddings)
    - All job records for this ontology (enables clean re-ingestion)
    - All Garage storage objects (images) for this ontology

    **Authentication:** Requires admin role

    Args:
        ontology_name: Name of the ontology to delete
        force: If True, skip existence check and proceed with deletion

    Returns:
        OntologyDeleteResponse with deletion statistics

    Raises:
        404: If ontology not found (when force=False)

    Example:
        DELETE /ontology/Test%20Ontology?force=true
    """
    from ..services.job_queue import get_job_queue

    client = get_age_client()
    queue = get_job_queue()
    try:
        # Check if ontology exists
        if not force:
            check = client._execute_cypher(f"""
                MATCH (s:Source {{document: '{ontology_name}'}})
                WITH count(s) as source_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS]->(s:Source {{document: '{ontology_name}'}})
                RETURN source_count, count(DISTINCT c) as concept_count
            """, fetch_one=True)

            if not check or check['source_count'] == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Ontology '{ontology_name}' not found"
                )

        # ADR-057: Clean up Garage objects before deleting sources
        # Query for all Garage object keys in this ontology
        storage_objects_result = client._execute_cypher(f"""
            MATCH (s:Source {{document: '{ontology_name}'}})
            WHERE s.storage_key IS NOT NULL
            RETURN s.storage_key as storage_key
        """)

        storage_keys_to_delete = []
        if storage_objects_result:
            for row in storage_objects_result:
                if row.get('storage_key'):
                    storage_keys_to_delete.append(row['storage_key'])

        # Delete Garage objects
        if storage_keys_to_delete:
            try:
                from ..lib.garage_client import get_garage_client
                garage_client = get_garage_client()

                deleted_count = 0
                for object_key in storage_keys_to_delete:
                    try:
                        garage_client.delete_image(object_key)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete Garage object {object_key}: {e}")

                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} images from Garage for ontology '{ontology_name}'")
            except Exception as e:
                logger.warning(f"Failed to initialize Garage client for cleanup: {e}")

        # Delete instances linked to sources in this ontology
        client._execute_cypher(f"""
            MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {{document: '{ontology_name}'}})
            DETACH DELETE i
        """)

        # IMPORTANT: Capture source_ids BEFORE cascade deleting from graph.
        # After graph nodes are deleted, we lose the ability to know which source_ids
        # belonged to this ontology - they're just opaque hashes in the relational table.
        # This pattern: capture references → cascade delete → cleanup related tables.
        source_ids_result = client._execute_cypher(f"""
            MATCH (s:Source {{document: '{ontology_name}'}})
            RETURN s.source_id as source_id
        """)
        source_ids = [row['source_id'] for row in (source_ids_result or []) if row.get('source_id')]

        # Delete sources from graph
        result = client._execute_cypher(f"""
            MATCH (s:Source {{document: '{ontology_name}'}})
            DETACH DELETE s
            RETURN count(s) as deleted_count
        """, fetch_one=True)

        sources_deleted = result['deleted_count'] if result else 0

        # Delete source_embeddings for the deleted sources
        if source_ids:
            try:
                conn = client.conn
                with conn.cursor() as cur:
                    # Use ANY to match source_ids in the list
                    cur.execute("""
                        DELETE FROM kg_api.source_embeddings
                        WHERE source_id = ANY(%s)
                    """, (source_ids,))
                    embeddings_deleted = cur.rowcount
                    conn.commit()
                    if embeddings_deleted > 0:
                        logger.info(f"Deleted {embeddings_deleted} source embeddings for ontology '{ontology_name}'")
            except Exception as e:
                logger.warning(f"Failed to delete source embeddings: {e}")

        # ADR-051: Delete DocumentMeta nodes for this ontology
        # This ensures cascade deletion of provenance metadata
        doc_meta_result = client._execute_cypher(f"""
            MATCH (d:DocumentMeta {{ontology: '{ontology_name}'}})
            DETACH DELETE d
            RETURN count(d) as deleted_count
        """, fetch_one=True)

        doc_meta_deleted = doc_meta_result['deleted_count'] if doc_meta_result else 0
        if doc_meta_deleted > 0:
            logger.info(f"Deleted {doc_meta_deleted} DocumentMeta nodes for ontology '{ontology_name}'")

        # Clean up orphaned concepts (concepts with no sources)
        # AGE doesn't support WHERE NOT with patterns, use OPTIONAL MATCH instead
        orphaned_result = client._execute_cypher("""
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[:APPEARS]->(s:Source)
            WITH c, s
            WHERE s IS NULL
            DETACH DELETE c
            RETURN count(c) as orphaned_count
        """, fetch_one=True)

        orphaned_count = orphaned_result['orphaned_count'] if orphaned_result else 0

        # Delete job records for this ontology to allow clean re-ingestion
        jobs_deleted = queue.delete_jobs_by_ontology(ontology_name)
        if jobs_deleted > 0:
            logger.info(f"Deleted {jobs_deleted} job records for ontology '{ontology_name}'")

        return OntologyDeleteResponse(
            ontology=ontology_name,
            deleted=True,
            sources_deleted=sources_deleted,
            orphaned_concepts_deleted=orphaned_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete ontology: {str(e)}")
    finally:
        client.close()


@router.post("/{ontology_name}/rename", response_model=OntologyRenameResponse)
async def rename_ontology(
    ontology_name: str,
    request: OntologyRenameRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Rename an ontology (Admin only - ADR-060).

    Updates all Source nodes' document property from old_name to new_name.
    This operation is fast and safe - only affects Source nodes in the specified ontology.

    **Authentication:** Requires admin role

    Args:
        ontology_name: Current ontology name
        request: Rename request with new_name

    Returns:
        OntologyRenameResponse with operation statistics

    Raises:
        404: If old ontology not found
        409: If new ontology name already exists

    Example:
        POST /ontology/Old%20Name/rename
        {
          "new_name": "New Name"
        }
    """
    client = get_age_client()
    try:
        # Perform rename via AGE client
        try:
            result = client.rename_ontology(ontology_name, request.new_name)

            return OntologyRenameResponse(
                old_name=ontology_name,
                new_name=request.new_name,
                sources_updated=result["sources_updated"],
                success=True
            )

        except ValueError as ve:
            # ValueError is raised for existence checks
            error_msg = str(ve)
            if "does not exist" in error_msg:
                raise HTTPException(status_code=404, detail=error_msg)
            elif "already exists" in error_msg:
                raise HTTPException(status_code=409, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rename ontology: {str(e)}")
    finally:
        client.close()
