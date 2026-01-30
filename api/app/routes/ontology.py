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

from ..dependencies.auth import CurrentUser, require_role, require_permission
from ..models.ontology import (
    OntologyListResponse,
    OntologyItem,
    OntologyInfoResponse,
    OntologyFilesResponse,
    OntologyFileInfo,
    OntologyDeleteRequest,
    OntologyDeleteResponse,
    OntologyRenameRequest,
    OntologyRenameResponse,
    OntologyNodeResponse,
    OntologyCreateRequest,
)
from api.app.lib.age_client import AGEClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ontology", tags=["ontology"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.post("/", response_model=OntologyNodeResponse, status_code=201)
async def create_ontology(
    request: OntologyCreateRequest,
    current_user: CurrentUser,
    _: None = Depends(require_permission("ontologies", "create"))
):
    """
    Create an ontology explicitly (ADR-200: directed growth).

    Creates an Ontology graph node before any documents are ingested.
    Generates an embedding from the name (and description if provided)
    so the ontology is immediately discoverable in the vector space.

    **Authorization:** Requires `ontologies:create` permission

    Args:
        request: OntologyCreateRequest with name and optional description

    Returns:
        OntologyNodeResponse with the created node's properties

    Raises:
        409: If an ontology with that name already exists

    Example:
        POST /ontology/
        {"name": "Distributed Systems", "description": "CAP theorem, consensus, replication"}
    """
    import uuid

    client = get_age_client()
    try:
        # Check if already exists
        existing = client.get_ontology_node(request.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Ontology '{request.name}' already exists"
            )

        # Also check if sources exist with this name (legacy ontology)
        source_check = client._execute_cypher(
            f"MATCH (s:Source {{document: '{request.name}'}}) RETURN count(s) as c",
            fetch_one=True
        )
        if source_check and source_check.get('c', 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Ontology '{request.name}' already exists (has source data)"
            )

        # Get creation epoch
        creation_epoch = 0
        try:
            conn = client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT counter FROM graph_metrics WHERE metric_name = 'document_ingestion_counter'")
                    row = cur.fetchone()
                    if row:
                        creation_epoch = row[0] or 0
            finally:
                client.pool.putconn(conn)
        except Exception:
            pass

        ontology_id = f"ont_{uuid.uuid4()}"
        node = client.create_ontology_node(
            ontology_id=ontology_id,
            name=request.name,
            description=request.description,
            lifecycle_state="active",
            creation_epoch=creation_epoch,
        )

        # Generate embedding
        has_embedding = False
        try:
            from ..lib.ai_providers import get_provider
            provider = get_provider()
            if provider:
                embed_text = request.name
                if request.description:
                    embed_text = f"{request.name}: {request.description}"
                emb_result = provider.generate_embedding(embed_text)
                emb_vector = emb_result if isinstance(emb_result, list) else emb_result.get("embedding", [])
                if emb_vector:
                    client.update_ontology_embedding(request.name, emb_vector)
                    has_embedding = True
        except Exception as e:
            logger.warning(f"Failed to generate embedding for new ontology '{request.name}': {e}")

        return OntologyNodeResponse(
            ontology_id=node.get('ontology_id', ontology_id),
            name=request.name,
            description=request.description,
            lifecycle_state=node.get('lifecycle_state', 'active'),
            creation_epoch=node.get('creation_epoch', creation_epoch),
            has_embedding=has_embedding,
            search_terms=node.get('search_terms', []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ontology: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create ontology: {str(e)}")
    finally:
        client.close()


@router.get("/", response_model=OntologyListResponse)
async def list_ontologies(
    current_user: CurrentUser
):
    """
    List all ontologies in the knowledge graph (ADR-060).

    Returns summary statistics for each ontology including
    file count, chunk count, and concept count.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `ontologies:read` permission

    Returns:
        OntologyListResponse with all ontologies

    Example:
        GET /ontology/
    """
    client = get_age_client()
    try:
        # ADR-200: Source stats by ontology name
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

        stats_map = {}
        for record in (result or []):
            stats_map[record['ontology']] = record

        # ADR-200: Ontology graph nodes are the source of truth.
        # This includes empty ontologies created via directed growth.
        node_map = {}
        try:
            nodes = client.list_ontology_nodes()
            for n in nodes:
                node_map[n['name']] = n
        except Exception as e:
            logger.warning(f"Failed to fetch Ontology nodes: {e}")

        # Merge: all graph nodes + any source-only ontologies without nodes
        seen = set()
        ontologies = []

        # Graph nodes first (source of truth)
        for name, node in sorted(node_map.items()):
            seen.add(name)
            stats = stats_map.get(name)
            ontologies.append(OntologyItem(
                ontology=name,
                source_count=stats['source_count'] if stats else 0,
                file_count=stats['file_count'] if stats else 0,
                concept_count=stats['concept_count'] if stats else 0,
                ontology_id=node.get('ontology_id'),
                lifecycle_state=node.get('lifecycle_state'),
                creation_epoch=node.get('creation_epoch'),
                has_embedding=node.get('embedding') is not None,
            ))

        # Source-only ontologies (legacy — no graph node yet)
        for name, stats in sorted(stats_map.items()):
            if name not in seen:
                ontologies.append(OntologyItem(
                    ontology=name,
                    source_count=stats['source_count'],
                    file_count=stats['file_count'],
                    concept_count=stats['concept_count'],
                ))

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
    **Authorization:** Requires `ontologies:read` permission

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

        # ADR-200: Fetch graph node properties
        node_response = None
        try:
            node = client.get_ontology_node(ontology_name)
            if node:
                node_response = OntologyNodeResponse(
                    ontology_id=node.get('ontology_id', ''),
                    name=node.get('name', ontology_name),
                    description=node.get('description', ''),
                    lifecycle_state=node.get('lifecycle_state', 'active'),
                    creation_epoch=node.get('creation_epoch', 0),
                    has_embedding=node.get('embedding') is not None,
                    search_terms=node.get('search_terms', []),
                )
        except Exception as e:
            logger.warning(f"Failed to fetch Ontology node for '{ontology_name}': {e}")

        return OntologyInfoResponse(
            ontology=ontology_name,
            statistics=statistics,
            files=files,
            node=node_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ontology info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ontology info: {str(e)}")
    finally:
        client.close()


@router.get("/{ontology_name}/node", response_model=OntologyNodeResponse)
async def get_ontology_node(
    ontology_name: str,
    current_user: CurrentUser
):
    """
    Get Ontology graph node properties (ADR-200).

    Returns the graph node's properties including lifecycle state,
    creation epoch, embedding status, and search terms.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `ontologies:read` permission

    Args:
        ontology_name: Name of the ontology

    Returns:
        OntologyNodeResponse with all node properties

    Raises:
        404: If ontology node not found

    Example:
        GET /ontology/Research%20Papers/node
    """
    client = get_age_client()
    try:
        node = client.get_ontology_node(ontology_name)
        if not node:
            raise HTTPException(
                status_code=404,
                detail=f"Ontology node '{ontology_name}' not found"
            )

        return OntologyNodeResponse(
            ontology_id=node.get('ontology_id', ''),
            name=node.get('name', ontology_name),
            description=node.get('description', ''),
            lifecycle_state=node.get('lifecycle_state', 'active'),
            creation_epoch=node.get('creation_epoch', 0),
            has_embedding=node.get('embedding') is not None,
            search_terms=node.get('search_terms', []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ontology node: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ontology node: {str(e)}")
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
    **Authorization:** Requires `ontologies:read` permission

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
    _: None = Depends(require_permission("ontologies", "delete")),
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

    **Authorization:** Requires `ontologies:delete` permission

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

        # ADR-057/ADR-081: Clean up ALL Garage objects before deleting sources
        # This includes: images, source documents, and projections
        try:
            from ..lib.garage_client import get_garage_client
            garage_client = get_garage_client()

            # 1. Delete images (via storage_key on Source nodes)
            storage_objects_result = client._execute_cypher(f"""
                MATCH (s:Source {{document: '{ontology_name}'}})
                WHERE s.storage_key IS NOT NULL
                RETURN s.storage_key as storage_key
            """)

            if storage_objects_result:
                image_deleted_count = 0
                for row in storage_objects_result:
                    if row.get('storage_key'):
                        try:
                            garage_client.delete_image(row['storage_key'])
                            image_deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete Garage image {row['storage_key']}: {e}")
                if image_deleted_count > 0:
                    logger.info(f"Deleted {image_deleted_count} images from Garage for ontology '{ontology_name}'")

            # 2. Delete source documents (ADR-081)
            try:
                from ..lib.garage import get_source_storage
                source_storage = get_source_storage()
                source_docs_deleted = source_storage.delete_by_ontology(ontology_name)
                if source_docs_deleted:
                    logger.info(f"Deleted {len(source_docs_deleted)} source documents from Garage for ontology '{ontology_name}'")
            except Exception as e:
                logger.warning(f"Failed to delete source documents from Garage: {e}")

            # 3. Delete projections (ADR-079)
            try:
                projections_deleted = garage_client.delete_all_projections(ontology_name)
                if projections_deleted > 0:
                    logger.info(f"Deleted {projections_deleted} projections from Garage for ontology '{ontology_name}'")
            except Exception as e:
                logger.warning(f"Failed to delete projections from Garage: {e}")

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
            conn = None
            try:
                conn = client.pool.getconn()
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
            finally:
                if conn:
                    client.pool.putconn(conn)

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

        # ADR-200: Delete Ontology node and its edges (SCOPED_BY, etc)
        try:
            if client.delete_ontology_node(ontology_name):
                logger.info(f"Deleted Ontology node for '{ontology_name}'")
        except Exception as e:
            logger.warning(f"Failed to delete Ontology node for '{ontology_name}': {e}")

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
    _: None = Depends(require_permission("ontologies", "create"))
):
    """
    Rename an ontology (Admin only - ADR-060).

    Updates all Source nodes' document property from old_name to new_name.
    This operation is fast and safe - only affects Source nodes in the specified ontology.

    **Authorization:** Requires `ontologies:create` permission

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

            # ADR-200: Also rename the Ontology graph node
            try:
                client.rename_ontology_node(ontology_name, request.new_name)
            except Exception as e:
                logger.warning(f"Failed to rename Ontology node: {e}")
                # Non-fatal: Source nodes are already renamed

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
