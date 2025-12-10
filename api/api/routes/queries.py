"""
Graph query endpoints for concept search and exploration.

Provides REST API access to:
- Semantic concept search using vector embeddings
- Concept details with evidence and relationships
- Related concept traversal
- Path finding between concepts
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
import logging
import numpy as np
import os
import psycopg2

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
    CypherRelationship,
    # ADR-068 Phase 3: Source search models
    SourceSearchRequest,
    SourceSearchResponse,
    SourceSearchResult,
    SourceConcept,
    SourceChunk,
    # ADR-070: Polarity axis models
    PolarityAxisRequest,
    PolarityAxisResponse
)
from ..services.query_service import QueryService
from ..services.diversity_analyzer import DiversityAnalyzer
from ..lib.pathfinding_facade import PathfindingFacade
from api.api.lib.age_client import AGEClient
from api.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["queries"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


def resolve_epistemic_filters_to_rel_types(
    age_client: AGEClient,
    include_epistemic_status: Optional[List[str]] = None,
    exclude_epistemic_status: Optional[List[str]] = None
) -> Optional[List[str]]:
    """
    Resolve epistemic status filters to list of allowed relationship types (ADR-065).

    Queries VocabType nodes to find relationship types matching the epistemic status criteria.
    Returns None if no filtering requested, or a list of relationship types if filtering active.

    Args:
        age_client: AGE client for querying VocabType nodes
        include_epistemic_status: Only include relationships with these epistemic statuses
        exclude_epistemic_status: Exclude relationships with these epistemic statuses

    Returns:
        List of allowed relationship types, or None if no filtering
    """
    if not include_epistemic_status and not exclude_epistemic_status:
        return None

    # Build filter conditions for VocabType query
    status_filters = []

    if include_epistemic_status:
        status_list = ", ".join([f"'{s}'" for s in include_epistemic_status])
        status_filters.append(f"v.epistemic_status IN [{status_list}]")

    if exclude_epistemic_status:
        status_list = ", ".join([f"'{s}'" for s in exclude_epistemic_status])
        status_filters.append(f"NOT v.epistemic_status IN [{status_list}]")

    # Query VocabType nodes matching the filters
    vocab_query = f"""
        MATCH (v:VocabType)
        WHERE {' AND '.join(status_filters)}
        RETURN v.name as type_name
    """

    logger.debug(f"[EpistemicFilter] Querying VocabType nodes: {vocab_query}")
    vocab_results = age_client._execute_cypher(vocab_query, params={})
    allowed_types = [row['type_name'] for row in vocab_results]

    logger.info(f"[EpistemicFilter] Resolved to {len(allowed_types)} relationship types: {allowed_types}")
    return allowed_types if allowed_types else None


def _generate_source_search_embedding(query: str) -> np.ndarray:
    """
    Generate embedding for source search query.

    Args:
        query: Search query text

    Returns:
        Embedding vector as numpy array

    Raises:
        HTTPException(500): If embedding generation fails or returns empty
    """
    provider = get_provider()
    embedding_result = provider.generate_embedding(query)

    # Extract embedding vector
    if isinstance(embedding_result, dict):
        embedding = embedding_result['embedding']
    else:
        embedding = embedding_result

    # Validate embedding is non-empty
    if not embedding or len(embedding) == 0:
        logger.error("Generated embedding is empty")
        raise HTTPException(
            status_code=500,
            detail="Generated embedding is empty. Check embedding provider configuration."
        )

    return np.array(embedding, dtype=np.float32)


def _search_source_embeddings_by_similarity(
    query_embedding: np.ndarray,
    min_similarity: float,
    limit: int
) -> Dict[str, Dict]:
    """
    Search source_embeddings table for similar chunks.

    Args:
        query_embedding: Query vector
        min_similarity: Minimum similarity threshold (0.0-1.0)
        limit: Maximum sources to return

    Returns:
        Dict mapping source_id to best matching chunk data:
        {
            "source_id": {
                "chunk_text": str,
                "start_offset": int,
                "end_offset": int,
                "chunk_index": int,
                "similarity": float,
                "source_hash": str
            }
        }
    """
    from api.api.lib.similarity_calculator import cosine_similarity

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "knowledge_graph"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    try:
        with conn.cursor() as cursor:
            # Fetch all source embeddings
            cursor.execute("""
                SELECT
                    se.source_id,
                    se.chunk_index,
                    se.chunk_text,
                    se.start_offset,
                    se.end_offset,
                    se.source_hash,
                    se.embedding
                FROM kg_api.source_embeddings se
                WHERE se.chunk_strategy = 'sentence'
                ORDER BY se.source_id, se.chunk_index
            """)

            # Calculate similarities using utility
            chunk_matches = []
            for row in cursor.fetchall():
                source_id, chunk_index, chunk_text, start_offset, end_offset, source_hash, embedding_bytes = row

                # Convert BYTEA to numpy array
                chunk_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)

                # Use centralized similarity calculator
                similarity = cosine_similarity(query_embedding, chunk_embedding)

                # Filter by threshold
                if similarity >= min_similarity:
                    chunk_matches.append({
                        'source_id': source_id,
                        'chunk_index': chunk_index,
                        'chunk_text': chunk_text,
                        'start_offset': start_offset,
                        'end_offset': end_offset,
                        'source_hash': source_hash,
                        'similarity': similarity
                    })

            # Sort by similarity
            chunk_matches.sort(key=lambda x: x['similarity'], reverse=True)

            # Group by source_id, keep best match per source
            source_best_matches = {}
            for match in chunk_matches:
                source_id = match['source_id']
                if source_id not in source_best_matches:
                    source_best_matches[source_id] = match
                elif match['similarity'] > source_best_matches[source_id]['similarity']:
                    source_best_matches[source_id] = match

            return source_best_matches

    finally:
        conn.close()


def _build_source_search_result(
    source_id: str,
    best_match: Dict,
    source_props: Dict,
    concepts_list: List[Dict],
    request: SourceSearchRequest
) -> Optional[SourceSearchResult]:
    """
    Build a single SourceSearchResult from fetched data.

    Args:
        source_id: Source identifier
        best_match: Best matching chunk data
        source_props: Source node properties from AGE
        concepts_list: List of concept dicts from batch query
        request: Original request (for filters, flags)

    Returns:
        SourceSearchResult or None if filtered out
    """
    # Apply ontology filter
    if request.ontology and source_props.get('document') != request.ontology:
        return None

    # Detect stale embeddings
    current_hash = source_props.get('content_hash')
    is_stale = (current_hash is not None and current_hash != best_match['source_hash'])

    # Build matched chunk
    matched_chunk = SourceChunk(
        chunk_text=best_match['chunk_text'],
        start_offset=best_match['start_offset'],
        end_offset=best_match['end_offset'],
        chunk_index=best_match['chunk_index'],
        similarity=best_match['similarity']
    )

    # Build full_text (optional)
    full_text = None
    if request.include_full_text:
        full_text = source_props.get('full_text')

    # Build concepts (optional)
    concepts = []
    if request.include_concepts:
        for concept_data in concepts_list:
            concepts.append(SourceConcept(
                concept_id=concept_data['concept_id'],
                label=concept_data['label'],
                description=concept_data.get('description'),
                instance_quote=concept_data['instance_quote']
            ))

    # Build result with NULL-safe field access
    return SourceSearchResult(
        source_id=source_id,
        document=source_props.get('document', 'Unknown'),
        paragraph=source_props.get('paragraph', 0),
        similarity=best_match['similarity'],
        is_stale=is_stale,
        matched_chunk=matched_chunk,
        full_text=full_text,
        concepts=concepts
    )


@router.post("/search", response_model=SearchResponse)
async def search_concepts(
    current_user: CurrentUser,
    request: SearchRequest
):
    """
    Search for concepts using semantic similarity with vector embeddings (ADR-060).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

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
                    f"MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:APPEARS]->(s:Source) RETURN DISTINCT s.document as doc"
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

                # Calculate semantic diversity if requested (ADR-063)
                diversity_score = None
                diversity_related_count = None
                authenticated_diversity = None
                if request.include_diversity:
                    try:
                        analyzer = DiversityAnalyzer(client)
                        diversity_result = analyzer.calculate_diversity(
                            concept_id=concept_id,
                            max_hops=request.diversity_max_hops,
                            grounding_strength=grounding_strength
                        )
                        diversity_score = diversity_result.get('diversity_score')
                        diversity_related_count = diversity_result.get('related_concept_count')
                        authenticated_diversity = diversity_result.get('authenticated_diversity')
                    except Exception as e:
                        logger.warning(f"Failed to calculate diversity for {concept_id}: {e}")

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
                    diversity_score=diversity_score,
                    diversity_related_count=diversity_related_count,
                    authenticated_diversity=authenticated_diversity,
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
                        f"MATCH (c:Concept {{concept_id: '{top_concept_id}'}})-[:APPEARS]->(s:Source) RETURN DISTINCT s.document as doc"
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

                    # Calculate diversity for top match if requested (ADR-063)
                    top_diversity_score = None
                    top_diversity_related_count = None
                    top_authenticated_diversity = None
                    if request.include_diversity:
                        try:
                            analyzer = DiversityAnalyzer(client)
                            top_diversity_result = analyzer.calculate_diversity(
                                concept_id=top_concept_id,
                                max_hops=request.diversity_max_hops,
                                grounding_strength=top_grounding
                            )
                            top_diversity_score = top_diversity_result.get('diversity_score')
                            top_diversity_related_count = top_diversity_result.get('related_concept_count')
                            top_authenticated_diversity = top_diversity_result.get('authenticated_diversity')
                        except Exception as e:
                            logger.warning(f"Failed to calculate diversity for top match {top_concept_id}: {e}")

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
                        diversity_score=top_diversity_score,
                        diversity_related_count=top_diversity_related_count,
                        authenticated_diversity=top_authenticated_diversity,
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


@router.post("/sources/search", response_model=SourceSearchResponse)
async def search_sources(
    current_user: CurrentUser,
    request: SourceSearchRequest
):
    """
    Search source text using semantic similarity on embeddings (ADR-068 Phase 3).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

    Searches source text chunks via embedding similarity, returns matched sources
    with related concepts for evidence/provenance retrieval.

    **How It Works:**
    - Query text → vector embedding (same dimensions as concept embeddings)
    - Cosine similarity search on source_embeddings table
    - Returns top matching source chunks with full source text
    - Optionally includes concepts extracted from those sources

    **Use Cases:**
    - Find source documents containing specific information
    - Retrieve evidence/citations for concepts
    - Locate original text passages for fact-checking
    - Navigate from text evidence to extracted concepts

    **Best Practices:**
    - Use 2-3 word descriptive phrases for best results
    - Default threshold of 70% (0.7) works well for most searches
    - Lower threshold to 50-60% (0.5-0.6) to find broader matches
    - Set include_concepts=true to see which concepts were extracted from matched sources

    Args:
        request: Source search parameters (query, limit, min_similarity, ontology, include_concepts, include_full_text)

    Returns:
        SourceSearchResponse with matching sources sorted by similarity score,
        including matched chunks, full text (optional), and related concepts (optional)

    Example:
        POST /query/sources/search
        {
          "query": "recursive awareness loop",
          "limit": 10,
          "min_similarity": 0.7,
          "include_concepts": true,
          "include_full_text": true
        }
    """
    try:
        # 1. Generate embedding for query
        query_embedding = _generate_source_search_embedding(request.query)

        # 2. Search source embeddings for similar chunks
        source_best_matches = _search_source_embeddings_by_similarity(
            query_embedding=query_embedding,
            min_similarity=request.min_similarity,
            limit=request.limit
        )

        # 3. Get top source IDs sorted by similarity
        top_source_ids = sorted(
            source_best_matches.keys(),
            key=lambda sid: source_best_matches[sid]['similarity'],
            reverse=True
        )[:request.limit]

        # 4. Batch-fetch Source nodes and concepts from AGE
        client = get_age_client()
        try:
            # Batch-fetch all Source nodes at once (query safety via facade)
            sources_data = client.facade.match_sources(
                where="s.source_id IN $source_ids",
                params={"source_ids": top_source_ids}
            )

            # Build lookup map for sources by source_id
            sources_by_id = {}
            for source_row in sources_data:
                # AGE facade returns {'s': {"id": ..., "label": ..., "properties": {...}}}
                source_vertex = source_row.get('s', {})
                source_props = source_vertex.get('properties', {})
                source_id_key = source_props.get('source_id')
                if source_id_key:
                    sources_by_id[source_id_key] = source_props

            # Batch-fetch all concepts for all sources at once (fixes N+1 query problem)
            concepts_by_source = {}
            if request.include_concepts:
                concepts_by_source = client.facade.match_concepts_for_sources_batch(top_source_ids)

            # 5. Assemble results using helper function
            results = []
            for source_id in top_source_ids:
                best_match = source_best_matches[source_id]
                source_props = sources_by_id.get(source_id)

                if not source_props:
                    logger.warning(f"Source node not found for source_id: {source_id}")
                    continue

                # Build result using helper (handles filtering, staleness detection, assembly)
                result = _build_source_search_result(
                    source_id=source_id,
                    best_match=best_match,
                    source_props=source_props,
                    concepts_list=concepts_by_source.get(source_id, []),
                    request=request
                )

                if result:
                    results.append(result)

            # 6. Return response
            return SourceSearchResponse(
                query=request.query,
                count=len(results),
                results=results,
                threshold_used=request.min_similarity
            )

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Source search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Source search failed: {str(e)}")


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
    **Authorization:** Requires `graph:read` permission

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
            OPTIONAL MATCH (c)-[:APPEARS]->(s:Source)
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

        # Get relationships with ADR-051 edge provenance metadata and ADR-065 vocabulary epistemic status
        # ADR-048: Read category via :IN_CATEGORY relationship (not property)
        relationships_result = client._execute_cypher(f"""
            MATCH (c:Concept {{concept_id: '{concept_id}'}})-[r]->(related:Concept)
            OPTIONAL MATCH (v:VocabType {{name: type(r)}})-[:IN_CATEGORY]->(cat:VocabCategory)
            RETURN
                related.concept_id as to_id,
                related.label as to_label,
                type(r) as rel_type,
                properties(r) as props,
                cat.name as vocab_category,
                v.epistemic_status as vocab_epistemic_status,
                v.epistemic_stats as vocab_epistemic_stats
        """)

        relationships = []
        for record in (relationships_result or []):
            props = record['props'] if record['props'] else {}

            # ADR-051: Convert created_by from int (user ID) to string
            created_by = props.get('created_by')
            if created_by is not None:
                created_by = str(created_by)

            # ADR-065: Extract avg_grounding from epistemic_stats JSON
            avg_grounding = None
            vocab_epistemic_stats = record.get('vocab_epistemic_stats')
            if vocab_epistemic_stats and isinstance(vocab_epistemic_stats, dict):
                avg_grounding = vocab_epistemic_stats.get('avg_grounding')

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
                created_at=props.get('created_at'),
                # ADR-065: Vocabulary epistemic status metadata
                category=record.get('vocab_category'),
                avg_grounding=avg_grounding,
                epistemic_status=record.get('vocab_epistemic_status')
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
                MATCH (c:Concept {{concept_id: '{concept_id}'}})-[:APPEARS]->(s:Source)
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
    **Authorization:** Requires `graph:read` permission

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
        # ADR-065: Resolve epistemic status filters to relationship types
        status_filtered_types = resolve_epistemic_filters_to_rel_types(
            client,
            request.include_epistemic_status,
            request.exclude_epistemic_status
        )

        # Combine explicit relationship_types filter with epistemic status filtering
        if request.relationship_types and status_filtered_types:
            # Intersection: only types that match both filters
            final_rel_types = [t for t in request.relationship_types if t in status_filtered_types]
        elif status_filtered_types:
            # Use epistemic status filtered types
            final_rel_types = status_filtered_types
        else:
            # Use explicit types or None (all types)
            final_rel_types = request.relationship_types

        # Build and execute related concepts query
        query = QueryService.build_related_concepts_query(
            request.max_depth,
            final_rel_types
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
    **Authorization:** Requires `graph:read` permission

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
        # ADR-065: Resolve epistemic status filters to relationship types
        allowed_rel_types = resolve_epistemic_filters_to_rel_types(
            client,
            request.include_epistemic_status,
            request.exclude_epistemic_status
        )

        # ADR-076: Use Bidirectional BFS instead of exhaustive Cypher patterns
        pathfinder = PathfindingFacade(client)
        raw_paths = pathfinder.find_paths(
            from_id=request.from_id,
            to_id=request.to_id,
            max_hops=request.max_hops,
            max_paths=5,
            allowed_rel_types=allowed_rel_types
        )

        # Convert facade output to API response format
        paths = []
        for raw_path in raw_paths:
            nodes = []
            for node_data in raw_path.get('path_nodes', []):
                concept_id = node_data.get('concept_id', '')
                label = node_data.get('label', '')
                description = node_data.get('description', '')

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

            # Extract relationship types from facade output
            rel_types = [rel.get('label', '') for rel in raw_path.get('path_rels', [])]

            paths.append(ConnectionPath(
                nodes=nodes,
                relationships=rel_types,
                hops=raw_path.get('hops', len(rel_types))
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
async def find_connection_by_search(
    current_user: CurrentUser,
    request: FindConnectionBySearchRequest
):
    """
    Find shortest paths between two concepts using semantic phrase matching (ADR-060).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

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

        # ADR-065: Resolve epistemic status filters to relationship types
        allowed_rel_types = resolve_epistemic_filters_to_rel_types(
            client,
            request.include_epistemic_status,
            request.exclude_epistemic_status
        )

        # ADR-076: Use Bidirectional BFS instead of exhaustive Cypher patterns
        pathfinder = PathfindingFacade(client)
        raw_paths = pathfinder.find_paths(
            from_id=from_concept_id,
            to_id=to_concept_id,
            max_hops=request.max_hops,
            max_paths=5,
            allowed_rel_types=allowed_rel_types
        )

        # Convert facade output to API response format
        paths = []
        for raw_path in raw_paths:
            nodes = []
            for node_data in raw_path.get('path_nodes', []):
                concept_id = node_data.get('concept_id', '')
                label = node_data.get('label', '')
                description = node_data.get('description', '')

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

            # Extract relationship types from facade output
            rel_types = [rel.get('label', '') for rel in raw_path.get('path_rels', [])]

            paths.append(ConnectionPath(
                nodes=nodes,
                relationships=rel_types,
                hops=raw_path.get('hops', len(rel_types))
            ))

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
    **Authorization:** Requires `graph:execute` permission

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
                            # Prefer properties.label (actual name) over AGE label (node type like "Concept")
                            props = value.get('properties', {})
                            node_label = props.get('label') or value.get('label', node_id)
                            nodes_map[node_id] = CypherNode(
                                id=node_id,
                                label=node_label,
                                properties=props
                            )

                elif isinstance(value, (list, tuple)):
                    # Could be a path - extract nodes and relationships
                    for item in value:
                        if isinstance(item, dict):
                            # Check for relationship first (AGE uses start_id/end_id)
                            start_id = item.get('start_id') or item.get('start')
                            end_id = item.get('end_id') or item.get('end')

                            if start_id and end_id:  # Relationship
                                relationships.append(CypherRelationship(
                                    from_id=str(start_id),
                                    to_id=str(end_id),
                                    type=item.get('label', item.get('type', 'RELATED')),
                                    properties=item.get('properties', {})
                                ))
                            elif 'id' in item:  # Node
                                node_id = str(item['id'])
                                if node_id not in nodes_map:
                                    # Prefer properties.label (actual name) over AGE label (node type)
                                    props = item.get('properties', {})
                                    node_label = props.get('label') or item.get('label', node_id)
                                    nodes_map[node_id] = CypherNode(
                                        id=node_id,
                                        label=node_label,
                                        properties=props
                                    )

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


@router.post("/polarity-axis", response_model=PolarityAxisResponse)
async def analyze_polarity_axis_endpoint(
    current_user: CurrentUser,
    request: PolarityAxisRequest
):
    """
    Analyze bidirectional semantic dimension (polarity axis) between two concept poles (ADR-070).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

    Projects concepts onto a semantic axis formed by two opposing poles (e.g., Modern ↔ Traditional).
    Returns concept positions, directions, and grounding correlation analysis.

    **Use Cases:**
    - Explore conceptual spectrums (Centralized ↔ Decentralized)
    - Find middle-ground concepts between opposites
    - Analyze value-laden vs descriptive dimensions (grounding correlation)
    - Discover implicit semantic dimensions

    **Parameters:**
    - **positive_pole_id**: Concept ID for "positive" direction (e.g., "Modern")
    - **negative_pole_id**: Concept ID for "negative" direction (e.g., "Traditional")
    - **candidate_ids**: Optional list of concept IDs to project (default: auto-discover)
    - **auto_discover**: Auto-find related concepts via graph traversal (default: true)
    - **max_candidates**: Max concepts for auto-discovery (default: 20)
    - **max_hops**: Max graph hops for auto-discovery (default: 2)

    **Returns:**
    - **axis**: Axis metadata (poles, magnitude, quality)
    - **projections**: Concepts projected with positions (-1 to +1)
    - **statistics**: Distribution summary (mean, range, direction counts)
    - **grounding_correlation**: Correlation between position and grounding strength

    **Position Interpretation:**
    - **+1.0**: Aligned with positive pole
    - **0.0**: Midpoint between poles
    - **-1.0**: Aligned with negative pole

    **Direction Classification:**
    - **positive**: position > 0.3
    - **neutral**: -0.3 ≤ position ≤ 0.3
    - **negative**: position < -0.3

    **Grounding Correlation:**
    - **Strong positive (r > 0.7)**: Positive pole concepts better grounded
    - **Weak (|r| < 0.3)**: Descriptive axis (no value judgment)
    - **Strong negative (r < -0.7)**: Negative pole concepts better grounded

    **Processing Time:** ~2-3 seconds (direct query, not queued)

    **Example:**
    ```json
    {
        "positive_pole_id": "sha256:abc123...",
        "negative_pole_id": "sha256:def456...",
        "auto_discover": true,
        "max_candidates": 20,
        "max_hops": 2
    }
    ```
    """
    client = get_age_client()

    try:
        logger.info(f"Polarity axis analysis: {request.positive_pole_id} ↔ {request.negative_pole_id}")

        # Import analysis function
        from api.api.lib.polarity_axis import analyze_polarity_axis

        # Run analysis (direct query - no job queue)
        result = analyze_polarity_axis(
            positive_pole_id=request.positive_pole_id,
            negative_pole_id=request.negative_pole_id,
            age_client=client,
            candidate_ids=request.candidate_ids,
            auto_discover=request.auto_discover,
            max_candidates=request.max_candidates,
            max_hops=request.max_hops,
            use_parallel=request.use_parallel,
            discovery_slot_pct=request.discovery_slot_pct,
            max_workers=request.max_workers,
            chunk_size=request.chunk_size,
            timeout_seconds=request.timeout_seconds
        )

        return PolarityAxisResponse(**result)

    except ValueError as e:
        logger.error(f"Invalid polarity axis request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Polarity axis analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        client.close()
