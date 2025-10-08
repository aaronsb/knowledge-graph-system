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
