"""Pydantic models for graph query operations"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# Search Models
class SearchRequest(BaseModel):
    """Request to search for concepts"""
    query: str = Field(..., description="Search query text", min_length=1)
    limit: int = Field(10, description="Maximum number of results", ge=1, le=100)
    min_similarity: float = Field(0.7, description="Minimum similarity score", ge=0.0, le=1.0)


class ConceptSearchResult(BaseModel):
    """Single concept search result"""
    concept_id: str
    label: str
    score: float
    documents: List[str]
    evidence_count: int


class SearchResponse(BaseModel):
    """Search results response"""
    query: str
    count: int
    results: List[ConceptSearchResult]
    below_threshold_count: Optional[int] = Field(None, description="Number of additional concepts below threshold")
    suggested_threshold: Optional[float] = Field(None, description="Suggested threshold to reveal below-threshold results")
    threshold_used: Optional[float] = Field(None, description="Similarity threshold used for filtering")


# Concept Details Models
class ConceptInstance(BaseModel):
    """Evidence instance for a concept"""
    quote: str
    document: str
    paragraph: int
    source_id: str


class ConceptRelationship(BaseModel):
    """Relationship to another concept"""
    to_id: str
    to_label: str
    rel_type: str
    confidence: Optional[float] = None


class ConceptDetailsResponse(BaseModel):
    """Detailed concept information"""
    concept_id: str
    label: str
    search_terms: List[str]
    documents: List[str]
    instances: List[ConceptInstance]
    relationships: List[ConceptRelationship]


# Related Concepts Models
class RelatedConceptsRequest(BaseModel):
    """Request to find related concepts"""
    concept_id: str = Field(..., description="Starting concept ID")
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types")
    max_depth: int = Field(2, description="Maximum traversal depth", ge=1, le=5)


class RelatedConcept(BaseModel):
    """Related concept result"""
    concept_id: str
    label: str
    distance: int
    path_types: List[str]


class RelatedConceptsResponse(BaseModel):
    """Related concepts response"""
    concept_id: str
    max_depth: int
    count: int
    results: List[RelatedConcept]


# Find Connection Models
class FindConnectionRequest(BaseModel):
    """Request to find path between concepts"""
    from_id: str = Field(..., description="Starting concept ID")
    to_id: str = Field(..., description="Target concept ID")
    max_hops: int = Field(5, description="Maximum path length", ge=1, le=10)


class PathNode(BaseModel):
    """Node in a path"""
    id: str
    label: str


class ConnectionPath(BaseModel):
    """Single path between concepts"""
    nodes: List[PathNode]
    relationships: List[str]
    hops: int


class FindConnectionResponse(BaseModel):
    """Connection paths response"""
    from_id: str
    to_id: str
    max_hops: int
    count: int
    paths: List[ConnectionPath]


# Find Connection by Search Models
class FindConnectionBySearchRequest(BaseModel):
    """Request to find path between concepts using natural language queries"""
    from_query: str = Field(..., description="Natural language query for starting concept", min_length=1)
    to_query: str = Field(..., description="Natural language query for target concept", min_length=1)
    max_hops: int = Field(5, description="Maximum path length", ge=1, le=10)


class FindConnectionBySearchResponse(BaseModel):
    """Connection paths response with search queries"""
    from_query: str
    to_query: str
    from_concept: Optional[PathNode] = Field(None, description="Top matching concept for from_query")
    to_concept: Optional[PathNode] = Field(None, description="Top matching concept for to_query")
    from_similarity: Optional[float] = Field(None, description="Similarity score of from match")
    to_similarity: Optional[float] = Field(None, description="Similarity score of to match")
    from_suggested_threshold: Optional[float] = Field(None, description="Suggested threshold if from query had no matches")
    to_suggested_threshold: Optional[float] = Field(None, description="Suggested threshold if to query had no matches")
    from_near_misses: Optional[int] = Field(None, description="Count of near-miss concepts for from query")
    to_near_misses: Optional[int] = Field(None, description="Count of near-miss concepts for to query")
    max_hops: int
    count: int
    paths: List[ConnectionPath]
