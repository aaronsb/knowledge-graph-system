"""
Ontology management endpoints for organizing knowledge domains.

Provides REST API access to:
- List all ontologies
- Get ontology details and statistics
- List files within an ontology
- Delete ontologies with orphan cleanup
"""

from fastapi import APIRouter, HTTPException, Query as QueryParam
import logging

from ..models.ontology import (
    OntologyListResponse,
    OntologyItem,
    OntologyInfoResponse,
    OntologyFilesResponse,
    OntologyFileInfo,
    OntologyDeleteRequest,
    OntologyDeleteResponse
)
from src.api.lib.age_client import AGEClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ontology", tags=["ontology"])


def get_neo4j_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.get("/", response_model=OntologyListResponse)
async def list_ontologies():
    """
    List all ontologies in the knowledge graph.

    Returns summary statistics for each ontology including
    file count, chunk count, and concept count.

    Returns:
        OntologyListResponse with all ontologies

    Example:
        GET /ontology/
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            result = session.run("""
                MATCH (s:Source)
                WITH DISTINCT s.document as ontology
                MATCH (src:Source {document: ontology})
                WITH ontology,
                     count(DISTINCT src) as source_count,
                     count(DISTINCT src.file_path) as file_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: ontology})
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
                for record in result
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
async def get_ontology_info(ontology_name: str):
    """
    Get detailed information about a specific ontology.

    Includes:
    - File count and list of files
    - Chunk (source) count
    - Concept count
    - Evidence instance count
    - Relationship count

    Args:
        ontology_name: Name of the ontology

    Returns:
        OntologyInfoResponse with detailed statistics

    Raises:
        404: If ontology not found

    Example:
        GET /ontology/Research%20Papers
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            # Check if ontology exists
            exists = session.run("""
                MATCH (s:Source {document: $ontology})
                RETURN count(s) > 0 as exists
            """, ontology=ontology_name)

            if not exists.single()['exists']:
                raise HTTPException(status_code=404, detail=f"Ontology '{ontology_name}' not found")

            # Get statistics
            stats = session.run("""
                MATCH (s:Source {document: $ontology})
                WITH count(DISTINCT s) as source_count,
                     count(DISTINCT s.file_path) as file_count,
                     collect(DISTINCT s.file_path) as files
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(src:Source {document: $ontology})
                WITH source_count, file_count, files, count(DISTINCT c) as concept_count
                OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(src:Source {document: $ontology})
                WITH source_count, file_count, files, concept_count, count(DISTINCT i) as instance_count
                OPTIONAL MATCH (c1:Concept)-[r]->(c2:Concept)
                WHERE (c1)-[:APPEARS_IN]->(:Source {document: $ontology})
                   OR (c2)-[:APPEARS_IN]->(:Source {document: $ontology})
                RETURN source_count, file_count, files, concept_count, instance_count, count(r) as relationship_count
            """, ontology=ontology_name).single()

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
async def get_ontology_files(ontology_name: str):
    """
    List all files in a specific ontology with their statistics.

    Args:
        ontology_name: Name of the ontology

    Returns:
        OntologyFilesResponse with file details

    Raises:
        404: If ontology not found or has no files

    Example:
        GET /ontology/Research%20Papers/files
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            result = session.run("""
                MATCH (s:Source {document: $ontology})
                WITH DISTINCT s.file_path as file_path
                WHERE file_path IS NOT NULL
                MATCH (src:Source {document: $ontology, file_path: file_path})
                WITH file_path, count(src) as chunk_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology, file_path: file_path})
                WITH file_path, chunk_count, count(DISTINCT c) as concept_count
                RETURN file_path, chunk_count, concept_count
                ORDER BY file_path
            """, ontology=ontology_name)

            files = [
                OntologyFileInfo(
                    file_path=record['file_path'],
                    chunk_count=record['chunk_count'],
                    concept_count=record['concept_count']
                )
                for record in result
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
    force: bool = QueryParam(False, description="Skip confirmation and force deletion")
):
    """
    Delete an ontology and all its data.

    **WARNING: This action cannot be undone!**

    Deletes:
    - All Source nodes belonging to the ontology
    - All Instance nodes linked to those sources
    - Orphaned Concept nodes (concepts with no remaining sources)

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
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            # Check if ontology exists
            if not force:
                check = session.run("""
                    MATCH (s:Source {document: $ontology})
                    WITH count(s) as source_count
                    OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology})
                    RETURN source_count, count(DISTINCT c) as concept_count
                """, ontology=ontology_name).single()

                if check['source_count'] == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Ontology '{ontology_name}' not found"
                    )

            # Delete instances linked to sources in this ontology
            session.run("""
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                DETACH DELETE i
            """, ontology=ontology_name)

            # Delete sources
            result = session.run("""
                MATCH (s:Source {document: $ontology})
                DETACH DELETE s
                RETURN count(s) as deleted_count
            """, ontology=ontology_name)

            sources_deleted = result.single()['deleted_count']

            # Clean up orphaned concepts (concepts with no sources)
            orphaned_result = session.run("""
                MATCH (c:Concept)
                WHERE NOT (c)-[:APPEARS_IN]->(:Source)
                DETACH DELETE c
                RETURN count(c) as orphaned_count
            """)

            orphaned_count = orphaned_result.single()['orphaned_count']

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
