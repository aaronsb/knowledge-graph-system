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
    FindConnectionBySearchRequest,
    FindConnectionBySearchResponse,
    ConnectionPath,
    PathNode
)
from ..services.query_service import QueryService
from src.api.lib.age_client import AGEClient
from src.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.post("/search", response_model=SearchResponse)
async def search_concepts(request: SearchRequest):
    """
    Search for concepts using semantic similarity with vector embeddings.

    Generates a vector embedding for the query text using the configured AI provider
    and performs cosine similarity search against all concept embeddings in the graph.
    Results include smart threshold hints when few matches are found.

    **How It Works:**
    - Query text → vector embedding (1536 dimensions via OpenAI/Anthropic)
    - Cosine similarity comparison against all concept embeddings
    - Results ranked by similarity score (0.0-1.0, higher is better)
    - Includes evidence counts and source document references

    **Best Practices:**
    - Use 2-3 word descriptive phrases for best results (e.g., "linear thinking patterns")
    - Default threshold of 70% (0.7) works well for most searches
    - Lower threshold to 50-60% (0.5-0.6) to find broader or weaker matches
    - Response includes threshold hints when additional concepts exist below threshold

    Args:
        request: Search parameters (query, limit, min_similarity)

    Returns:
        SearchResponse with matching concepts sorted by similarity score, plus
        smart hints about additional concepts available at lower thresholds

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
        client = get_age_client()
        try:
            # Use AGEClient's vector_search method with threshold from request
            # Fetch limit + offset to handle pagination
            fetch_count = request.limit + request.offset
            matches = client.vector_search(
                embedding,
                threshold=request.min_similarity,
                top_k=fetch_count
            )

            # Apply offset (skip first N results) and limit
            paginated_matches = matches[request.offset:request.offset + request.limit]

            # Filter by minimum similarity and gather document/evidence info
            results = []
            for match in paginated_matches:
                if match['similarity'] < request.min_similarity:
                    continue

                # Get documents and evidence count
                concept_id = match['concept_id']
                docs_query = client._execute_cypher(
                    f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:APPEARS_IN]->(s:Source) RETURN DISTINCT s.document as doc"
                )
                documents = [r['doc'] for r in (docs_query or [])]

                evidence_query = client._execute_cypher(
                    f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance) RETURN count(i) as evidence_count",
                    fetch_one=True
                )
                evidence_count = evidence_query['evidence_count'] if evidence_query else 0

                results.append(ConceptSearchResult(
                    concept_id=concept_id,
                    label=match['label'],
                    score=match['similarity'],
                    documents=documents,
                    evidence_count=evidence_count
                ))

            # If few results found, check for additional concepts below threshold
            below_threshold_count = None
            suggested_threshold = None
            top_match = None
            if len(results) < 3 and request.min_similarity > 0.3:
                # Search with fixed lower threshold to find near-misses
                # Use 0.3 (30%) to catch most reasonable matches
                lower_threshold = 0.3
                lower_matches = client.vector_search(
                    embedding,
                    threshold=lower_threshold,
                    top_k=request.limit * 2  # Check more results
                )
                # Find matches between lower_threshold and request.min_similarity
                below_threshold_matches = [
                    m for m in lower_matches
                    if lower_threshold <= m['similarity'] < request.min_similarity
                ]

                if below_threshold_matches:
                    below_threshold_count = len(below_threshold_matches)
                    # Calculate exact threshold needed: round down the lowest score to nearest 0.05
                    min_score = min(m['similarity'] for m in below_threshold_matches)
                    suggested_threshold = round(min_score - 0.02, 2)  # Slightly below lowest to include it

                    # Get top match (highest similarity) for preview
                    top_match_data = max(below_threshold_matches, key=lambda m: m['similarity'])

                    # Get documents and evidence for top match
                    top_concept_id = top_match_data['concept_id']
                    top_docs_query = client._execute_cypher(
                        f"MATCH (c:Concept {{concept_id: '{top_concept_id}'}})-[:APPEARS_IN]->(s:Source) RETURN DISTINCT s.document as doc"
                    )
                    top_documents = [r['doc'] for r in (top_docs_query or [])]

                    top_evidence_query = client._execute_cypher(
                        f"MATCH (c:Concept {{concept_id: '{top_concept_id}'}})-[:EVIDENCED_BY]->(i:Instance) RETURN count(i) as evidence_count",
                        fetch_one=True
                    )
                    top_evidence_count = top_evidence_query['evidence_count'] if top_evidence_query else 0

                    top_match = ConceptSearchResult(
                        concept_id=top_concept_id,
                        label=top_match_data['label'],
                        score=top_match_data['similarity'],
                        documents=top_documents,
                        evidence_count=top_evidence_count
                    )

            return SearchResponse(
                query=request.query,
                count=len(results),
                results=results,
                below_threshold_count=below_threshold_count if below_threshold_count else None,
                suggested_threshold=suggested_threshold,
                top_match=top_match,
                threshold_used=request.min_similarity,
                offset=request.offset
            )
        finally:
            client.close()

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/concept/{concept_id}", response_model=ConceptDetailsResponse)
async def get_concept_details(concept_id: str):
    """
    Get detailed information about a specific concept including all evidence and relationships.

    Retrieves complete concept data from the graph including:
    - Concept metadata (unique ID, human-readable label, alternative search terms)
    - Evidence instances (quoted text snippets from source documents)
    - Source document references with paragraph numbers
    - Outgoing relationships to other concepts (with relationship types and optional confidence scores)

    **Use Cases:**
    - Inspect evidence supporting a concept extracted from documents
    - Explore semantic relationships connecting this concept to others
    - Verify extraction quality by reviewing source quotes
    - Navigate the knowledge graph by following relationships

    **Response Details:**
    - `instances`: Ordered by document and paragraph number for context
    - `relationships`: All outgoing edges from this concept
    - `search_terms`: Alternative phrases that can match this concept in searches

    Args:
        concept_id: The unique concept identifier (from search results or graph traversal)

    Returns:
        ConceptDetailsResponse with complete concept information including evidence,
        source documents, and semantic relationships

    Raises:
        404: If concept_id does not exist in the graph

    Example:
        GET /query/concept/linear-scanning-system
    """
    client = get_age_client()
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
                s.source_id as source_id,
                s.full_text as full_text
            ORDER BY s.document, s.paragraph
        """)

        instances = [
            ConceptInstance(
                quote=record['quote'],
                document=record['document'],
                paragraph=record['paragraph'],
                source_id=record['source_id'],
                full_text=record.get('full_text')
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

        # Extract properties from AGE vertex structure: {id, label, properties: {...}}
        props = concept.get('properties', {})

        return ConceptDetailsResponse(
            concept_id=props.get('concept_id', ''),
            label=props.get('label', ''),
            search_terms=props.get('search_terms', []),
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
    Find concepts related through graph traversal using breadth-first search.

    Performs breadth-first graph traversal from a starting concept to discover
    all connected concepts within a specified maximum distance (hops). Optionally
    filters by specific relationship types.

    **How It Works:**
    - Starts from the specified concept_id
    - Explores outgoing relationships level by level (breadth-first)
    - Returns all reachable concepts within max_depth hops
    - Groups results by distance from starting concept

    **Relationship Types:**
    - IMPLIES, SUPPORTS, CONTRADICTS, RESULTS_FROM, ENABLES, etc.
    - Filter to specific types or omit to traverse all relationship types
    - Path includes the sequence of relationship types traversed

    **Performance Note:**
    - Depth 1-2: Fast, typically <100 concepts
    - Depth 3-4: Moderate, can return 100s of concepts
    - Depth 5: Slow, may return 1000s of concepts depending on graph density

    Args:
        request: Related concepts parameters (concept_id, max_depth, relationship_types)

    Returns:
        RelatedConceptsResponse with related concepts grouped by distance,
        ordered from closest (distance 1) to farthest (distance max_depth)

    Example:
        POST /query/related
        {
          "concept_id": "linear-scanning-system",
          "max_depth": 2,
          "relationship_types": ["SUPPORTS", "IMPLIES"]
        }
    """
    client = get_age_client()
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
    Find shortest paths between two concepts using exact concept IDs.

    Uses Apache AGE graph traversal to find up to 5 shortest paths connecting
    two concepts. Requires exact concept IDs (not semantic phrase matching).

    **When to Use:**
    - You already have exact concept IDs from search results or details views
    - You want guaranteed exact matches without similarity thresholds
    - You're connecting concepts programmatically with known IDs

    **For Semantic Phrase Matching:**
    - Use `/query/connect-by-search` instead to match phrases like "licensing issues"
    - That endpoint handles phrase-to-ID matching automatically

    Args:
        request: Connection parameters (from_id, to_id, max_hops)

    Returns:
        FindConnectionResponse with discovered paths between the exact concepts

    Raises:
        404: If either concept ID does not exist in the graph

    Example:
        POST /query/connect
        {
          "from_id": "linear-scanning-system",
          "to_id": "genetic-intervention",
          "max_hops": 5
        }
    """
    client = get_age_client()
    try:
        # Build and execute shortest path query
        query = QueryService.build_shortest_path_query(request.max_hops)

        records = client._execute_cypher(
            query.replace("$from_id", f"'{request.from_id}'")
                 .replace("$to_id", f"'{request.to_id}'")
        )

        # Extract properties from AGE vertex and edge objects
        paths = []
        for record in (records or []):
            # path_nodes is a list of AGE vertex dicts: {id, label, properties: {...}}
            # path_rels is a list of AGE edge dicts: {id, label, properties: {...}}

            nodes = []
            for node in record['path_nodes']:
                if isinstance(node, dict):
                    props = node.get('properties', {})
                    nodes.append(PathNode(
                        id=props.get('concept_id', ''),
                        label=props.get('label', '')
                    ))

            # Relationship type is in the 'label' field of AGE edge object
            rel_types = []
            for rel in record['path_rels']:
                if isinstance(rel, dict):
                    rel_types.append(rel.get('label', ''))

            paths.append(ConnectionPath(
                nodes=nodes,
                relationships=rel_types,
                hops=record['hops']
            ))


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


@router.post("/connect-by-search", response_model=FindConnectionBySearchResponse)
async def find_connection_by_search(request: FindConnectionBySearchRequest):
    """
    Find shortest paths between two concepts using semantic phrase matching.

    Uses vector embeddings to match query phrases to existing concepts based on
    semantic similarity, then finds shortest paths connecting them.

    **Best Practices:**
    - Use specific 2-3 word phrases (e.g., "licensing issues" not "licensing")
    - Generic single words may not match well due to lack of semantic context
    - Lower threshold (0.3-0.4) to find concepts with weaker similarity
    - Error messages include threshold hints when near-miss concepts exist

    Args:
        request: Connection parameters (from_query, to_query, max_hops, threshold)

    Returns:
        FindConnectionBySearchResponse with discovered paths, match quality scores,
        and helpful threshold hints if matches were weak or missing

    Example:
        POST /query/connect-by-search
        {
          "from_query": "licensing issues",
          "to_query": "AGE benefits",
          "max_hops": 5,
          "threshold": 0.5
        }
    """
    client = get_age_client()
    provider = get_provider()

    try:
        # Search for concepts matching both queries
        from_embedding_result = provider.generate_embedding(request.from_query)
        from_embedding = from_embedding_result['embedding'] if isinstance(from_embedding_result, dict) else from_embedding_result

        to_embedding_result = provider.generate_embedding(request.to_query)
        to_embedding = to_embedding_result['embedding'] if isinstance(to_embedding_result, dict) else to_embedding_result

        # Find top matching concepts for each query using request threshold
        threshold = request.threshold
        from_matches = client.vector_search(from_embedding, top_k=1, threshold=threshold)
        to_matches = client.vector_search(to_embedding, top_k=1, threshold=threshold)

        # Helper function to find near-misses and suggest threshold
        def check_near_misses(embedding, query_name):
            """Check for near-miss concepts and suggest threshold"""
            # Search with lower threshold to find near-misses
            lower_threshold = 0.3
            lower_matches = client.vector_search(embedding, top_k=5, threshold=lower_threshold)

            # Find matches between lower_threshold and threshold
            near_misses = [m for m in lower_matches if lower_threshold <= m['similarity'] < threshold]

            if near_misses:
                # Calculate suggested threshold (slightly below best match)
                best_similarity = max(m['similarity'] for m in near_misses)
                suggested = round(best_similarity - 0.02, 2)
                return len(near_misses), suggested
            return None, None

        # Initialize hint fields
        from_suggested_threshold = None
        to_suggested_threshold = None
        from_near_misses = None
        to_near_misses = None

        # Check for no matches and provide hints
        if not from_matches:
            from_near_misses, from_suggested_threshold = check_near_misses(from_embedding, "from_query")
            if from_suggested_threshold:
                raise HTTPException(
                    status_code=404,
                    detail=f"No concepts found matching '{request.from_query}' at {int(threshold*100)}% similarity. "
                           f"Try: --min-similarity {from_suggested_threshold} ({from_near_misses} near-miss concept{'s' if from_near_misses > 1 else ''} available)"
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No concepts found matching '{request.from_query}'"
                )

        if not to_matches:
            to_near_misses, to_suggested_threshold = check_near_misses(to_embedding, "to_query")
            if to_suggested_threshold:
                raise HTTPException(
                    status_code=404,
                    detail=f"No concepts found matching '{request.to_query}' at {int(threshold*100)}% similarity. "
                           f"Try: --min-similarity {to_suggested_threshold} ({to_near_misses} near-miss concept{'s' if to_near_misses > 1 else ''} available)"
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"No concepts found matching '{request.to_query}'"
                )

        # Use the top match for each
        from_concept_id = from_matches[0]['concept_id']
        from_label = from_matches[0]['label']
        from_similarity = from_matches[0]['similarity']
        to_concept_id = to_matches[0]['concept_id']
        to_label = to_matches[0]['label']
        to_similarity = to_matches[0]['similarity']

        logger.info(f"Found concept matches: '{from_label}' ({from_concept_id}, {from_similarity:.1%}) -> '{to_label}' ({to_concept_id}, {to_similarity:.1%})")

        # Build and execute shortest path query
        query = QueryService.build_shortest_path_query(request.max_hops)

        records = client._execute_cypher(
            query.replace("$from_id", f"'{from_concept_id}'")
                 .replace("$to_id", f"'{to_concept_id}'")
        )

        # Extract properties from AGE vertex and edge objects
        paths = []
        for record in (records or []):
            # path_nodes is a list of AGE vertex dicts: {id, label, properties: {...}}
            # path_rels is a list of AGE edge dicts: {id, label, properties: {...}}

            nodes = []
            for node in record['path_nodes']:
                if isinstance(node, dict):
                    props = node.get('properties', {})
                    nodes.append(PathNode(
                        id=props.get('concept_id', ''),
                        label=props.get('label', '')
                    ))

            # Relationship type is in the 'label' field of AGE edge object
            rel_types = []
            for rel in record['path_rels']:
                if isinstance(rel, dict):
                    rel_types.append(rel.get('label', ''))

            paths.append(ConnectionPath(
                nodes=nodes,
                relationships=rel_types,
                hops=record['hops']
            ))


        return FindConnectionBySearchResponse(
            from_query=request.from_query,
            to_query=request.to_query,
            from_concept=PathNode(id=from_concept_id, label=from_label),
            to_concept=PathNode(id=to_concept_id, label=to_label),
            from_similarity=from_similarity,
            to_similarity=to_similarity,
            from_suggested_threshold=from_suggested_threshold,
            to_suggested_threshold=to_suggested_threshold,
            from_near_misses=from_near_misses,
            to_near_misses=to_near_misses,
            max_hops=request.max_hops,
            count=len(paths),
            paths=paths
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find connection by search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find connection by search: {str(e)}")
    finally:
        client.close()
