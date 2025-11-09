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

from ..dependencies.auth import CurrentUser
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
    PathNode,
    CypherQueryRequest,
    CypherQueryResponse,
    CypherNode,
    CypherRelationship
)
from ..services.query_service import QueryService
from ..services.diversity_analyzer import DiversityAnalyzer
from api.api.lib.age_client import AGEClient
from api.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.post("/search", response_model=SearchResponse)
async def search_concepts(
    current_user: CurrentUser,
    request: SearchRequest
):
    """
    Search for concepts using semantic similarity with vector embeddings (ADR-060).

    **Authentication:** Requires valid OAuth token

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

                # Calculate grounding strength if requested (default: true)
                grounding_strength = None
                if request.include_grounding:
                    try:
                        grounding_strength = client.calculate_grounding_strength_semantic(concept_id)
                    except Exception as e:
                        logger.warning(f"Failed to calculate grounding for {concept_id}: {e}")

                # Fetch sample evidence instances if requested (ADR-057: include image metadata, ADR-051: include provenance)
                sample_evidence = None
                if request.include_evidence:
                    evidence_instances_query = client._execute_cypher(
                        f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source) "
                        f"OPTIONAL MATCH (d:DocumentMeta {{ontology: s.document}}) WHERE s.source_id IN d.source_ids "
                        f"RETURN i.quote as quote, s.document as document, s.paragraph as paragraph, s.source_id as source_id, "
                        f"s.content_type as content_type, s.storage_key as storage_key, "
                        f"d.filename as filename, d.source_type as source_type, d.file_path as source_path, d.hostname as source_hostname "
                        f"ORDER BY s.document, s.paragraph "
                        f"LIMIT 3"  # Sample first 3 instances
                    )
                    if evidence_instances_query:
                        sample_evidence = [
                            ConceptInstance(
                                quote=e['quote'],
                                document=e['document'],
                                paragraph=e['paragraph'],
                                source_id=e['source_id'],
                                content_type=e.get('content_type'),
                                has_image=e.get('content_type') == 'image' and e.get('storage_key') is not None,
                                image_uri=f"/api/sources/{e['source_id']}/image" if e.get('content_type') == 'image' and e.get('storage_key') else None,
                                storage_key=e.get('storage_key'),
                                filename=e.get('filename'),
                                source_type=e.get('source_type'),
                                source_path=e.get('source_path'),
                                source_hostname=e.get('source_hostname')
                            )
                            for e in evidence_instances_query
                        ]

                results.append(ConceptSearchResult(
                    concept_id=concept_id,
                    label=match['label'],
                    description=match.get('description'),
                    score=match['similarity'],
                    documents=documents,
                    evidence_count=evidence_count,
                    grounding_strength=grounding_strength,
                    sample_evidence=sample_evidence
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

                    # Calculate grounding for top match if requested
                    top_grounding = None
                    if request.include_grounding:
                        try:
                            top_grounding = client.calculate_grounding_strength_semantic(top_concept_id)
                        except Exception as e:
                            logger.warning(f"Failed to calculate grounding for top match {top_concept_id}: {e}")

                    # Fetch sample evidence for top match if requested (ADR-057: include image metadata, ADR-051: include provenance)
                    top_sample_evidence = None
                    if request.include_evidence:
                        top_evidence_instances_query = client._execute_cypher(
                            f"MATCH (c:Concept {{concept_id: '{top_concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source) "
                            f"OPTIONAL MATCH (d:DocumentMeta {{ontology: s.document}}) WHERE s.source_id IN d.source_ids "
                            f"RETURN i.quote as quote, s.document as document, s.paragraph as paragraph, s.source_id as source_id, "
                            f"s.content_type as content_type, s.storage_key as storage_key, "
                            f"d.filename as filename, d.source_type as source_type, d.file_path as source_path, d.hostname as source_hostname "
                            f"ORDER BY s.document, s.paragraph "
                            f"LIMIT 3"
                        )
                        if top_evidence_instances_query:
                            top_sample_evidence = [
                                ConceptInstance(
                                    quote=e['quote'],
                                    document=e['document'],
                                    paragraph=e['paragraph'],
                                    source_id=e['source_id'],
                                    content_type=e.get('content_type'),
                                    has_image=e.get('content_type') == 'image' and e.get('storage_key') is not None,
                                    image_uri=f"/api/sources/{e['source_id']}/image" if e.get('content_type') == 'image' and e.get('storage_key') else None,
                                    storage_key=e.get('storage_key'),
                                    filename=e.get('filename'),
                                    source_type=e.get('source_type'),
                                    source_path=e.get('source_path'),
                                    source_hostname=e.get('source_hostname')
                                )
                                for e in top_evidence_instances_query
                            ]

                    top_match = ConceptSearchResult(
                        concept_id=top_concept_id,
                        label=top_match_data['label'],
                        description=top_match_data.get('description'),
                        score=top_match_data['similarity'],
                        documents=top_documents,
                        evidence_count=top_evidence_count,
                        grounding_strength=top_grounding,
                        sample_evidence=top_sample_evidence
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
async def get_concept_details(
    concept_id: str,
    current_user: CurrentUser,
    include_grounding: bool = False,
    include_diversity: bool = False,
    diversity_max_hops: int = 2
):
    """
    Get detailed information about a specific concept including all evidence and relationships (ADR-060).

    **Authentication:** Requires valid OAuth token

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

        # Get instances (ADR-057: include image metadata, ADR-051: include provenance from DocumentMeta)
        instances_result = client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)
            MATCH (i)-[:FROM_SOURCE]->(s:Source)
            OPTIONAL MATCH (d:DocumentMeta {{ontology: s.document}})
            WHERE s.source_id IN d.source_ids
            RETURN
                i.quote as quote,
                s.document as document,
                s.paragraph as paragraph,
                s.source_id as source_id,
                s.full_text as full_text,
                s.content_type as content_type,
                s.storage_key as storage_key,
                d.filename as filename,
                d.source_type as source_type,
                d.file_path as source_path,
                d.hostname as source_hostname
            ORDER BY s.document, s.paragraph
        """)

        instances = [
            ConceptInstance(
                quote=record['quote'],
                document=record['document'],
                paragraph=record['paragraph'],
                source_id=record['source_id'],
                full_text=record.get('full_text'),
                # ADR-057: Image metadata
                content_type=record.get('content_type'),
                has_image=record.get('content_type') == 'image' and record.get('storage_key') is not None,
                image_uri=f"/api/sources/{record['source_id']}/image" if record.get('content_type') == 'image' and record.get('storage_key') else None,
                storage_key=record.get('storage_key'),
                # ADR-051: Source provenance from DocumentMeta
                filename=record.get('filename'),
                source_type=record.get('source_type'),
                source_path=record.get('source_path'),
                source_hostname=record.get('source_hostname')
            )
            for record in (instances_result or [])
        ]

        # Get relationships with ADR-051 edge provenance metadata
        relationships_result = client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})-[r]->(related:Concept)
            RETURN
                related.concept_id as to_id,
                related.label as to_label,
                type(r) as rel_type,
                properties(r) as props
        """)

        relationships = []
        for record in (relationships_result or []):
            props = record['props'] if record['props'] else {}

            # ADR-051: Convert created_by from int (user ID) to string
            created_by = props.get('created_by')
            if created_by is not None:
                created_by = str(created_by)

            relationships.append(ConceptRelationship(
                to_id=record['to_id'],
                to_label=record['to_label'],
                rel_type=record['rel_type'],
                confidence=props.get('confidence'),
                # ADR-051: Edge provenance metadata
                created_by=created_by,
                source=props.get('source'),
                job_id=props.get('job_id'),
                document_id=props.get('document_id'),
                created_at=props.get('created_at')
            ))


        # Extract properties from AGE vertex structure: {id, label, properties: {...}}
        props = concept.get('properties', {})

        # Calculate grounding strength if requested (ADR-044)
        grounding_strength = None
        if include_grounding:
            try:
                grounding_strength = client.calculate_grounding_strength_semantic(concept_id)
            except Exception as e:
                logger.warning(f"Failed to calculate grounding for {concept_id}: {e}")

        # Calculate semantic diversity if requested (ADR-063)
        diversity_score = None
        diversity_related_count = None
        authenticated_diversity = None
        if include_diversity:
            try:
                analyzer = DiversityAnalyzer(client)
                diversity_result = analyzer.calculate_diversity(
                    concept_id=concept_id,
                    max_hops=diversity_max_hops,
                    grounding_strength=grounding_strength  # Pass grounding for authenticated diversity
                )
                diversity_score = diversity_result.get('diversity_score')
                diversity_related_count = diversity_result.get('related_concept_count')
                authenticated_diversity = diversity_result.get('authenticated_diversity')
            except Exception as e:
                logger.warning(f"Failed to calculate diversity for {concept_id}: {e}")

        # ADR-051: Query provenance information
        # This finds DocumentMeta nodes linked to the concept via Source nodes
        provenance = None
        try:
            from ..models.queries import ConceptProvenance, ProvenanceDocument

            # Query for source documents via DocumentMeta nodes
            provenance_result = client._execute_cypher(f"""
                MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:APPEARS_IN]->(s:Source)
                MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s)
                RETURN DISTINCT
                    d.document_id as document_id,
                    d.filename as filename,
                    d.source_type as source_type,
                    d.source_path as source_path,
                    d.hostname as hostname,
                    d.ingested_by as ingested_by,
                    d.created_at as ingested_at,
                    d.job_id as job_id,
                    d.source_count as source_count
            """)

            if provenance_result and len(provenance_result) > 0:
                # Build provenance documents list
                prov_docs = []
                for rec in provenance_result:
                    # ADR-051: Convert ingested_by from int (user ID) to string
                    ingested_by = rec.get('ingested_by')
                    if ingested_by is not None:
                        ingested_by = str(ingested_by)

                    prov_docs.append(ProvenanceDocument(
                        document_id=rec['document_id'],
                        filename=rec['filename'],
                        source_type=rec.get('source_type'),
                        source_path=rec.get('source_path'),
                        hostname=rec.get('hostname'),
                        ingested_by=ingested_by,
                        ingested_at=rec.get('ingested_at'),
                        job_id=rec.get('job_id'),
                        source_count=rec.get('source_count')
                    ))

                provenance = ConceptProvenance(documents=prov_docs)
        except Exception as e:
            logger.warning(f"Failed to fetch provenance for {concept_id}: {e}")

        return ConceptDetailsResponse(
            concept_id=props.get('concept_id', ''),
            label=props.get('label', ''),
            description=props.get('description', ''),
            search_terms=props.get('search_terms', []),
            documents=documents,
            instances=instances,
            relationships=relationships,
            grounding_strength=grounding_strength,
            diversity_score=diversity_score,  # ADR-063
            diversity_related_count=diversity_related_count,  # ADR-063
            authenticated_diversity=authenticated_diversity,  # ADR-044 + ADR-063
            provenance=provenance  # ADR-051
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get concept details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get concept details: {str(e)}")
    finally:
        client.close()


@router.post("/related", response_model=RelatedConceptsResponse)
async def find_related_concepts(
    current_user: CurrentUser,
    request: RelatedConceptsRequest
):
    """
    Find concepts related through graph traversal using breadth-first search (ADR-060).

    **Authentication:** Requires valid OAuth token

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
async def find_connection(
    current_user: CurrentUser,
    request: FindConnectionRequest
):
    """
    Find shortest paths between two concepts using exact concept IDs (ADR-060).

    **Authentication:** Requires valid OAuth token

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
            has_metadata_node = False  # Flag to skip paths with Source/Instance nodes

            for node in record['path_nodes']:
                if isinstance(node, dict):
                    props = node.get('properties', {})
                    concept_id = props.get('concept_id', '')
                    label = props.get('label', '')
                    description = props.get('description', '')

                    # Check if this is a metadata node (Source or Instance)
                    # Metadata nodes lack concept_id and label properties
                    if not concept_id or not label:
                        has_metadata_node = True

                    # Calculate grounding strength if requested (default: true)
                    grounding_strength = None
                    if request.include_grounding and concept_id:
                        try:
                            grounding_strength = client.calculate_grounding_strength_semantic(concept_id)
                        except Exception as e:
                            logger.warning(f"Failed to calculate grounding for {concept_id}: {e}")

                    # Fetch sample evidence if requested (ADR-057: include image metadata)
                    sample_evidence = None
                    if request.include_evidence and concept_id:
                        evidence_query = client._execute_cypher(
                            f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source) "
                            f"RETURN i.quote as quote, s.document as document, s.paragraph as paragraph, s.source_id as source_id, "
                            f"s.content_type as content_type, s.storage_key as storage_key "
                            f"ORDER BY s.document, s.paragraph "
                            f"LIMIT 3"
                        )
                        if evidence_query:
                            sample_evidence = [
                                ConceptInstance(
                                    quote=e['quote'],
                                    document=e['document'],
                                    paragraph=e['paragraph'],
                                    source_id=e['source_id'],
                                    content_type=e.get('content_type'),
                                    has_image=e.get('content_type') == 'image' and e.get('storage_key') is not None,
                                    image_uri=f"/api/sources/{e['source_id']}/image" if e.get('content_type') == 'image' and e.get('storage_key') else None,
                                    storage_key=e.get('storage_key')
                                )
                                for e in evidence_query
                            ]

                    nodes.append(PathNode(
                        id=concept_id,
                        label=label,
                        description=description,
                        grounding_strength=grounding_strength,
                        sample_evidence=sample_evidence
                    ))

            # Skip paths that go through Source or Instance nodes
            if has_metadata_node:
                continue

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

        # Limit to 5 paths after filtering
        paths = paths[:5]

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
async def find_connection_by_search(
    current_user: CurrentUser,
    request: FindConnectionBySearchRequest
):
    """
    Find shortest paths between two concepts using semantic phrase matching (ADR-060).

    **Authentication:** Requires valid OAuth token

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
        from_description = from_matches[0].get('description', '')
        from_similarity = from_matches[0]['similarity']
        to_concept_id = to_matches[0]['concept_id']
        to_label = to_matches[0]['label']
        to_description = to_matches[0].get('description', '')
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
            has_metadata_node = False  # Flag to skip paths with Source/Instance nodes

            for node in record['path_nodes']:
                if isinstance(node, dict):
                    props = node.get('properties', {})
                    concept_id = props.get('concept_id', '')
                    label = props.get('label', '')
                    description = props.get('description', '')

                    # Check if this is a metadata node (Source or Instance)
                    # Metadata nodes lack concept_id and label properties
                    if not concept_id or not label:
                        has_metadata_node = True

                    # Calculate grounding strength if requested (default: true)
                    grounding_strength = None
                    if request.include_grounding and concept_id:
                        try:
                            grounding_strength = client.calculate_grounding_strength_semantic(concept_id)
                        except Exception as e:
                            logger.warning(f"Failed to calculate grounding for {concept_id}: {e}")

                    # Fetch sample evidence if requested (ADR-057: include image metadata)
                    sample_evidence = None
                    if request.include_evidence and concept_id:
                        evidence_query = client._execute_cypher(
                            f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source) "
                            f"RETURN i.quote as quote, s.document as document, s.paragraph as paragraph, s.source_id as source_id, "
                            f"s.content_type as content_type, s.storage_key as storage_key "
                            f"ORDER BY s.document, s.paragraph "
                            f"LIMIT 3"
                        )
                        if evidence_query:
                            sample_evidence = [
                                ConceptInstance(
                                    quote=e['quote'],
                                    document=e['document'],
                                    paragraph=e['paragraph'],
                                    source_id=e['source_id'],
                                    content_type=e.get('content_type'),
                                    has_image=e.get('content_type') == 'image' and e.get('storage_key') is not None,
                                    image_uri=f"/api/sources/{e['source_id']}/image" if e.get('content_type') == 'image' and e.get('storage_key') else None,
                                    storage_key=e.get('storage_key')
                                )
                                for e in evidence_query
                            ]

                    nodes.append(PathNode(
                        id=concept_id,
                        label=label,
                        description=description,
                        grounding_strength=grounding_strength,
                        sample_evidence=sample_evidence
                    ))

            # Skip paths that go through Source or Instance nodes
            if has_metadata_node:
                continue

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

        # Limit to 5 paths after filtering
        paths = paths[:5]

        return FindConnectionBySearchResponse(
            from_query=request.from_query,
            to_query=request.to_query,
            from_concept=PathNode(id=from_concept_id, label=from_label, description=from_description),
            to_concept=PathNode(id=to_concept_id, label=to_label, description=to_description),
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


@router.post("/cypher", response_model=CypherQueryResponse)
async def execute_cypher_query(
    current_user: CurrentUser,
    request: CypherQueryRequest
):
    """
    Execute a raw openCypher query against the Apache AGE graph (ADR-060).

    **Authentication:** Requires valid OAuth token

    Allows direct execution of openCypher queries for advanced users who want full control.
    Returns nodes and relationships in a format suitable for graph visualization.

    **Security Note:** This endpoint executes user-provided queries directly.
    In production, consider:
    - Read-only query enforcement
    - Query timeout limits
    - Rate limiting
    - User authentication/authorization

    **Example Query:**
    ```cypher
    MATCH (c:Concept)-[r]->(n:Concept)
    WHERE c.label CONTAINS 'organizational'
    RETURN c, r, n
    LIMIT 50
    ```

    Returns graph data (nodes + relationships) for visualization.
    """
    client = get_age_client()
    import time

    try:
        # Apply default limit if query doesn't have one
        query = request.query.strip()
        if request.limit and 'LIMIT' not in query.upper():
            query = f"{query} LIMIT {request.limit}"

        logger.info(f"Executing openCypher query: {query[:100]}...")

        # Time the query execution
        start_time = time.time()

        # Execute the query
        records = client._execute_cypher(query)

        execution_time = (time.time() - start_time) * 1000  # Convert to ms

        # Parse results into nodes and relationships
        nodes_map = {}
        relationships = []

        for record in records:
            # Extract nodes and relationships from each record
            for key, value in record.items():
                if isinstance(value, dict):
                    # Check if it's a node (has 'id' and typically 'label')
                    if 'id' in value:
                        node_id = str(value['id'])
                        if node_id not in nodes_map:
                            nodes_map[node_id] = CypherNode(
                                id=node_id,
                                label=value.get('label', value.get('properties', {}).get('label', node_id)),
                                properties=value.get('properties', {})
                            )

                elif isinstance(value, (list, tuple)):
                    # Could be a path - extract nodes and relationships
                    for item in value:
                        if isinstance(item, dict):
                            if 'id' in item and 'start' not in item:  # Node
                                node_id = str(item['id'])
                                if node_id not in nodes_map:
                                    nodes_map[node_id] = CypherNode(
                                        id=node_id,
                                        label=item.get('label', item.get('properties', {}).get('label', node_id)),
                                        properties=item.get('properties', {})
                                    )
                            elif 'start' in item and 'end' in item:  # Relationship
                                relationships.append(CypherRelationship(
                                    from_id=str(item['start']),
                                    to_id=str(item['end']),
                                    type=item.get('label', item.get('type', 'RELATED')),
                                    properties=item.get('properties', {})
                                ))

        logger.info(f"Query returned {len(nodes_map)} nodes, {len(relationships)} relationships in {execution_time:.2f}ms")

        return CypherQueryResponse(
            nodes=list(nodes_map.values()),
            relationships=relationships,
            execution_time_ms=execution_time,
            row_count=len(records),
            query=query
        )

    except Exception as e:
        logger.error(f"Failed to execute Cypher query: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")
    finally:
        client.close()
