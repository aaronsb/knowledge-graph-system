"""
Graph query endpoints for concept search and exploration.

Provides REST API access to:
- Semantic concept search using vector embeddings
- Concept details with evidence and relationships
- Related concept traversal
- Path finding between concepts
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

from ..models.queries import (
    SearchRequest,
    SearchResponse,
    ConceptSearchResult,
    ConceptDetailsResponse,
    ConceptInstance,
    ConceptRelationship,
    RelatedConceptsRequest,
    RelatedConceptsResponse,
    RelatedConcept,
    FindConnectionRequest,
    FindConnectionResponse,
    ConnectionPath,
    PathNode
)
from ..services.query_service import QueryService
from src.ingest.neo4j_client import Neo4jClient
from src.ingest.ai_providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j client instance"""
    return Neo4jClient()


@router.post("/search", response_model=SearchResponse)
async def search_concepts(request: SearchRequest):
    """
    Search for concepts using semantic similarity.

    Generates an embedding for the query text and performs vector similarity
    search against the concept-embeddings index.

    Args:
        request: Search parameters (query, limit, min_similarity)

    Returns:
        SearchResponse with matching concepts sorted by similarity

    Example:
        POST /query/search
        {
          "query": "linear thinking patterns",
          "limit": 10,
          "min_similarity": 0.7
        }
    """
    try:
        # Generate embedding for query
        provider = get_provider()
        embedding_result = provider.generate_embedding(request.query)

        # Extract embedding vector
        if isinstance(embedding_result, dict):
            embedding = embedding_result['embedding']
        else:
            embedding = embedding_result

        # Vector similarity search
        client = get_neo4j_client()
        try:
            with client.driver.session() as session:
                records = QueryService.execute_search(
                    session,
                    embedding,
                    request.limit,
                    request.min_similarity
                )

                results = [
                    ConceptSearchResult(
                        concept_id=record['concept_id'],
                        label=record['label'],
                        score=record['score'],
                        documents=record['documents'],
                        evidence_count=record['evidence_count']
                    )
                    for record in records
                ]

                return SearchResponse(
                    query=request.query,
                    count=len(results),
                    results=results
                )
        finally:
            client.close()

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/concept/{concept_id}", response_model=ConceptDetailsResponse)
async def get_concept_details(concept_id: str):
    """
    Get detailed information about a specific concept.

    Includes:
    - Concept metadata (label, search terms, documents)
    - Evidence instances (quotes with source references)
    - Outgoing relationships to other concepts

    Args:
        concept_id: The concept ID to retrieve

    Returns:
        ConceptDetailsResponse with full concept information

    Raises:
        404: If concept not found

    Example:
        GET /query/concept/linear-scanning-system
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            data = QueryService.execute_concept_details(session, concept_id)

            if not data:
                raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

            concept = data['concept']
            documents = data['documents']

            instances = [
                ConceptInstance(
                    quote=record['quote'],
                    document=record['document'],
                    paragraph=record['paragraph'],
                    source_id=record['source_id']
                )
                for record in data['instances']
            ]

            relationships = [
                ConceptRelationship(
                    to_id=record['to_id'],
                    to_label=record['to_label'],
                    rel_type=record['rel_type'],
                    confidence=record['props'].get('confidence')
                )
                for record in data['relationships']
            ]

            return ConceptDetailsResponse(
                concept_id=concept['concept_id'],
                label=concept['label'],
                search_terms=concept.get('search_terms', []),
                documents=documents,
                instances=instances,
                relationships=relationships
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get concept details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get concept details: {str(e)}")
    finally:
        client.close()


@router.post("/related", response_model=RelatedConceptsResponse)
async def find_related_concepts(request: RelatedConceptsRequest):
    """
    Find concepts related through graph traversal.

    Performs breadth-first traversal from a starting concept to find
    connected concepts within a maximum depth.

    Args:
        request: Related concepts parameters (concept_id, max_depth, relationship_types)

    Returns:
        RelatedConceptsResponse with related concepts grouped by distance

    Example:
        POST /query/related
        {
          "concept_id": "linear-scanning-system",
          "max_depth": 2,
          "relationship_types": ["SUPPORTS", "IMPLIES"]
        }
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            records = QueryService.execute_related_concepts(
                session,
                request.concept_id,
                request.max_depth,
                request.relationship_types
            )

            results = [
                RelatedConcept(
                    concept_id=record['concept_id'],
                    label=record['label'],
                    distance=record['distance'],
                    path_types=record['path_types']
                )
                for record in records
            ]

            return RelatedConceptsResponse(
                concept_id=request.concept_id,
                max_depth=request.max_depth,
                count=len(results),
                results=results
            )

    except Exception as e:
        logger.error(f"Failed to find related concepts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find related concepts: {str(e)}")
    finally:
        client.close()


@router.post("/connect", response_model=FindConnectionResponse)
async def find_connection(request: FindConnectionRequest):
    """
    Find shortest paths between two concepts.

    Uses Neo4j's shortestPath algorithm to find up to 5 shortest paths
    connecting two concepts in the graph.

    Args:
        request: Connection parameters (from_id, to_id, max_hops)

    Returns:
        FindConnectionResponse with discovered paths

    Example:
        POST /query/connect
        {
          "from_id": "linear-scanning-system",
          "to_id": "genetic-intervention",
          "max_hops": 5
        }
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            records = QueryService.execute_shortest_path(
                session,
                request.from_id,
                request.to_id,
                request.max_hops
            )

            paths = [
                ConnectionPath(
                    nodes=[PathNode(id=n['id'], label=n['label']) for n in record['path_nodes']],
                    relationships=record['rel_types'],
                    hops=record['hops']
                )
                for record in records
            ]

            return FindConnectionResponse(
                from_id=request.from_id,
                to_id=request.to_id,
                max_hops=request.max_hops,
                count=len(paths),
                paths=paths
            )

    except Exception as e:
        logger.error(f"Failed to find connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find connection: {str(e)}")
    finally:
        client.close()
