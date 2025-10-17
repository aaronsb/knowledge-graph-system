"""Pydantic models for graph query operations"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# Search Models
class SearchRequest(BaseModel):
    """Request to search for concepts using semantic similarity.

    Uses vector embeddings to find concepts matching the query text.
    Returns concepts ranked by cosine similarity score.
    """
    query: str = Field(..., description="Search query text (2-3 word phrases work best)", min_length=1)
    limit: int = Field(10, description="Maximum number of results to return", ge=1, le=100)
    min_similarity: float = Field(0.7, description="Minimum similarity score (0.0-1.0, default 70%)", ge=0.0, le=1.0)
    offset: int = Field(0, description="Number of results to skip for pagination (default: 0)", ge=0)


class ConceptSearchResult(BaseModel):
    """Single concept search result with similarity score and evidence"""
    concept_id: str = Field(..., description="Unique concept identifier")
    label: str = Field(..., description="Human-readable concept label")
    score: float = Field(..., description="Similarity score (0.0-1.0)")
    documents: List[str] = Field(..., description="Documents where concept appears")
    evidence_count: int = Field(..., description="Number of evidence instances")


class SearchResponse(BaseModel):
    """Search results with smart threshold hints.

    If few results found at current threshold, suggests lowering threshold
    to reveal near-miss concepts.
    """
    query: str = Field(..., description="Original search query")
    count: int = Field(..., description="Number of results returned")
    results: List[ConceptSearchResult] = Field(..., description="Ranked search results")
    below_threshold_count: Optional[int] = Field(None, description="Number of additional concepts below threshold")
    suggested_threshold: Optional[float] = Field(None, description="Suggested threshold to reveal below-threshold results")
    top_match: Optional[ConceptSearchResult] = Field(None, description="Best matching concept below threshold for quick preview")
    threshold_used: Optional[float] = Field(None, description="Similarity threshold used for filtering")
    offset: Optional[int] = Field(None, description="Offset used for pagination")


# Concept Details Models
class ConceptInstance(BaseModel):
    """Evidence instance showing where concept appears in source text.

    Each instance is a quoted text snippet from a specific document and paragraph.
    Includes the full chunk text for grounding and context.
    """
    quote: str = Field(..., description="Quoted text from source")
    document: str = Field(..., description="Source document name")
    paragraph: int = Field(..., description="Paragraph number in document")
    source_id: str = Field(..., description="Unique source identifier")
    full_text: Optional[str] = Field(None, description="Full chunk text that was processed (for grounding)")


class ConceptRelationship(BaseModel):
    """Semantic relationship connecting two concepts.

    Relationship types include: IMPLIES, SUPPORTS, CONTRADICTS, RESULTS_FROM, ENABLES, etc.
    """
    to_id: str = Field(..., description="Target concept ID")
    to_label: str = Field(..., description="Target concept label")
    rel_type: str = Field(..., description="Relationship type (e.g., IMPLIES, SUPPORTS)")
    confidence: Optional[float] = Field(None, description="Confidence score (0.0-1.0) if available")


class ConceptDetailsResponse(BaseModel):
    """Complete concept information with evidence and relationships.

    Includes all text instances where concept appears and all semantic relationships
    connecting it to other concepts in the graph.
    """
    concept_id: str = Field(..., description="Unique concept identifier")
    label: str = Field(..., description="Human-readable concept label")
    search_terms: List[str] = Field(..., description="Alternative search terms for this concept")
    documents: List[str] = Field(..., description="Documents where concept appears")
    instances: List[ConceptInstance] = Field(..., description="Evidence instances (quotes from text)")
    relationships: List[ConceptRelationship] = Field(..., description="Outgoing relationships to other concepts")


# Related Concepts Models
class RelatedConceptsRequest(BaseModel):
    """Request to find concepts related through graph traversal.

    Performs breadth-first search from a starting concept to find all connected concepts
    within max_depth hops. Optionally filters by specific relationship types.
    """
    concept_id: str = Field(..., description="Starting concept ID")
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types (e.g., ['IMPLIES', 'SUPPORTS'])")
    max_depth: int = Field(2, description="Maximum traversal depth (1-5 hops)", ge=1, le=5)


class RelatedConcept(BaseModel):
    """Concept found through graph traversal with distance information"""
    concept_id: str = Field(..., description="Related concept ID")
    label: str = Field(..., description="Related concept label")
    distance: int = Field(..., description="Number of hops from starting concept")
    path_types: List[str] = Field(..., description="Relationship types traversed to reach this concept")


class RelatedConceptsResponse(BaseModel):
    """Related concepts grouped by distance from starting concept.

    Results ordered by distance (closer concepts first).
    """
    concept_id: str = Field(..., description="Starting concept ID")
    max_depth: int = Field(..., description="Maximum depth searched")
    count: int = Field(..., description="Number of related concepts found")
    results: List[RelatedConcept] = Field(..., description="Related concepts ordered by distance")


# Find Connection Models
class FindConnectionRequest(BaseModel):
    """Request to find shortest paths between two concepts using exact IDs.

    Uses graph traversal to find up to 5 shortest paths connecting the concepts.
    For phrase-based search, use /query/connect-by-search instead.
    """
    from_id: str = Field(..., description="Starting concept ID (exact match required)")
    to_id: str = Field(..., description="Target concept ID (exact match required)")
    max_hops: int = Field(5, description="Maximum path length to search (1-10 hops)", ge=1, le=10)


class PathNode(BaseModel):
    """Node in a connection path"""
    id: str = Field(..., description="Concept ID")
    label: str = Field(..., description="Concept label")


class ConnectionPath(BaseModel):
    """Single path connecting two concepts through relationships.

    Shows the sequence of nodes and relationship types traversed.
    """
    nodes: List[PathNode] = Field(..., description="Ordered list of concepts in path")
    relationships: List[str] = Field(..., description="Ordered list of relationship types (e.g., IMPLIES, ENABLES)")
    hops: int = Field(..., description="Path length (number of relationships)")


class FindConnectionResponse(BaseModel):
    """Connection paths between two concepts.

    Returns up to 5 shortest paths found within max_hops limit.
    """
    from_id: str = Field(..., description="Starting concept ID")
    to_id: str = Field(..., description="Target concept ID")
    max_hops: int = Field(..., description="Maximum path length searched")
    count: int = Field(..., description="Number of paths found")
    paths: List[ConnectionPath] = Field(..., description="Discovered paths (up to 5)")


# Find Connection by Search Models
class FindConnectionBySearchRequest(BaseModel):
    """Request to find path between concepts using semantic phrase matching.

    Uses vector embeddings to match query phrases to existing concepts, then finds paths.
    Generic single words may not match well - use specific 2-3 word phrases for best results.
    """
    from_query: str = Field(..., description="Semantic phrase for starting concept (e.g., 'licensing issues' not 'licensing')", min_length=1)
    to_query: str = Field(..., description="Semantic phrase for target concept (use specific 2-3 word phrases)", min_length=1)
    max_hops: int = Field(5, description="Maximum path length to search", ge=1, le=10)
    threshold: float = Field(0.5, description="Minimum similarity threshold (default 50% - lower for broader matches)", ge=0.0, le=1.0)


class FindConnectionBySearchResponse(BaseModel):
    """Connection paths response with semantic phrase matching details.

    Shows which concepts matched the search phrases and provides threshold hints
    if matches were weak or missing. Includes similarity scores to help tune queries.
    """
    from_query: str = Field(..., description="Original from query phrase")
    to_query: str = Field(..., description="Original to query phrase")
    from_concept: Optional[PathNode] = Field(None, description="Top matching concept for from_query")
    to_concept: Optional[PathNode] = Field(None, description="Top matching concept for to_query")
    from_similarity: Optional[float] = Field(None, description="Similarity score of from match (0.0-1.0)")
    to_similarity: Optional[float] = Field(None, description="Similarity score of to match (0.0-1.0)")
    from_suggested_threshold: Optional[float] = Field(None, description="Suggested threshold if from query had no matches")
    to_suggested_threshold: Optional[float] = Field(None, description="Suggested threshold if to query had no matches")
    from_near_misses: Optional[int] = Field(None, description="Count of near-miss concepts for from query below threshold")
    to_near_misses: Optional[int] = Field(None, description="Count of near-miss concepts for to query below threshold")
    max_hops: int = Field(..., description="Maximum path length searched")
    count: int = Field(..., description="Number of paths found")
    paths: List[ConnectionPath] = Field(..., description="Discovered paths between matched concepts")
