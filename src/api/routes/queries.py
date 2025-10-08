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
from src.api.lib.age_client import AGEClient
from src.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


def get_neo4j_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


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

        # Vector similarity search using AGE client
        client = get_neo4j_client()
        try:
            # Use AGEClient's vector_search method
            matches = client.vector_search(embedding, top_k=request.limit)

            # Filter by minimum similarity and gather document/evidence info
            results = []
            for match in matches:
                if match['score'] < request.min_similarity:
                    continue

                # Get documents and evidence count
                concept_id = match['concept_id']
                docs_query = client._execute_cypher(
                    f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:APPEARS_IN]->(s:Source) RETURN DISTINCT s.document as doc"
                )
                documents = [r['doc'] for r in (docs_query or [])]

                evidence_query = client._execute_cypher(
                    f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance) RETURN count(i) as count",
                    fetch_one=True
                )
                evidence_count = evidence_query['count'] if evidence_query else 0

                results.append(ConceptSearchResult(
                    concept_id=concept_id,
                    label=match['label'],
                    score=match['score'],
                    documents=documents,
                    evidence_count=evidence_count
                ))

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
        # Get concept and documents
        concept_result = client._execute_cypher(
            f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})
            OPTIONAL MATCH (c)-[:APPEARS_IN]->(s:Source)
            WITH c, collect(DISTINCT s.document) as documents
            RETURN c, documents
            """,
            fetch_one=True
        )

        if not concept_result:
            raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

        concept = concept_result['c']
        documents = concept_result['documents']

        # Get instances
        instances_result = client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)
            MATCH (i)-[:FROM_SOURCE]->(s:Source)
            RETURN
                i.quote as quote,
                s.document as document,
                s.paragraph as paragraph,
                s.source_id as source_id
            ORDER BY s.document, s.paragraph
        """)

        instances = [
            ConceptInstance(
                quote=record['quote'],
                document=record['document'],
                paragraph=record['paragraph'],
                source_id=record['source_id']
            )
            for record in (instances_result or [])
        ]

        # Get relationships
        relationships_result = client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})-[r]->(related:Concept)
            RETURN
                related.concept_id as to_id,
                related.label as to_label,
                type(r) as rel_type,
                properties(r) as props
        """)

        relationships = [
            ConceptRelationship(
                to_id=record['to_id'],
                to_label=record['to_label'],
                rel_type=record['rel_type'],
                confidence=record['props'].get('confidence') if record['props'] else None
            )
            for record in (relationships_result or [])
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
        # Build and execute related concepts query
        query = QueryService.build_related_concepts_query(
            request.max_depth,
            request.relationship_types
        )

        records = client._execute_cypher(
            query.replace("$concept_id", f"'{request.concept_id}'")
        )

        results = [
            RelatedConcept(
                concept_id=record['concept_id'],
                label=record['label'],
                distance=record['distance'],
                path_types=record['path_types']
            )
            for record in (records or [])
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
        # Build and execute shortest path query
        query = QueryService.build_shortest_path_query(request.max_hops)

        records = client._execute_cypher(
            query.replace("$from_id", f"'{request.from_id}'")
                 .replace("$to_id", f"'{request.to_id}'")
        )

        paths = [
            ConnectionPath(
                nodes=[PathNode(id=n['id'], label=n['label']) for n in record['path_nodes']],
                relationships=record['rel_types'],
                hops=record['hops']
            )
            for record in (records or [])
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
