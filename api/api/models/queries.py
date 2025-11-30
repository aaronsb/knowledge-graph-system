"""Pydantic models for graph query operations"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# Constants
DEFAULT_SOURCE_SEARCH_SIMILARITY = 0.7
"""
Default similarity threshold for source search.

Rationale:
- <0.5: Too many irrelevant results (high recall, low precision)
- 0.5-0.7: Balanced recall/precision for exploratory search
- 0.7-0.85: Good precision for targeted search (recommended default)
- >0.85: Very high precision, may miss relevant results
"""


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
    include_evidence: bool = Field(False, description="Include sample evidence instances (quotes from source text) for each concept")
    include_grounding: bool = Field(True, description="Include grounding strength (ADR-044: probabilistic truth score) for each concept")
    include_diversity: bool = Field(False, description="Include semantic diversity score (ADR-063: authenticity signal) for each concept")
    diversity_max_hops: int = Field(2, description="Maximum traversal depth for diversity calculation (1-3, default: 2)", ge=1, le=3)


class ConceptSearchResult(BaseModel):
    """Single concept search result with similarity score and evidence"""
    concept_id: str = Field(..., description="Unique concept identifier")
    label: str = Field(..., description="Human-readable concept label")
    description: Optional[str] = Field(None, description="Factual 1-2 sentence definition of the concept")
    score: float = Field(..., description="Similarity score (0.0-1.0)")
    documents: List[str] = Field(..., description="Documents where concept appears")
    evidence_count: int = Field(..., description="Number of evidence instances")
    grounding_strength: Optional[float] = Field(None, description="Grounding strength (-1.0 to 1.0) if requested (ADR-044)")
    diversity_score: Optional[float] = Field(None, description="Semantic diversity score (0.0 to 1.0) if requested (ADR-063)")
    diversity_related_count: Optional[int] = Field(None, description="Number of related concepts analyzed for diversity")
    authenticated_diversity: Optional[float] = Field(None, description="Sign-weighted diversity: sign(grounding) × diversity. Positive: diverse support, Negative: diverse contradiction (ADR-044 + ADR-063)")
    sample_evidence: Optional[List['ConceptInstance']] = Field(None, description="Sample evidence instances (quotes from source text) when include_evidence=true")


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

    For image sources (ADR-057), includes image metadata and retrieval URI.
    """
    quote: str = Field(..., description="Quoted text from source (for images, this is the vision AI description)")
    document: str = Field(..., description="Source document name")
    paragraph: int = Field(..., description="Paragraph number in document")
    source_id: str = Field(..., description="Unique source identifier")
    full_text: Optional[str] = Field(None, description="Full chunk text that was processed (for grounding)")
    # ADR-057: Image metadata
    content_type: Optional[str] = Field(None, description="Content type: 'image' for image sources, 'text' or None for text")
    has_image: Optional[bool] = Field(None, description="True if this source has an associated image")
    image_uri: Optional[str] = Field(None, description="URI to retrieve image: /api/sources/{source_id}/image (requires authentication)")
    storage_key: Optional[str] = Field(None, description="MinIO object key for image storage (internal use)")
    # ADR-051: Source provenance metadata (from DocumentMeta)
    filename: Optional[str] = Field(None, description="Original filename or display name")
    source_type: Optional[str] = Field(None, description="Source type: file, stdin, mcp, api")
    source_path: Optional[str] = Field(None, description="Full filesystem path (file ingestion only)")
    source_hostname: Optional[str] = Field(None, description="Hostname where ingestion was initiated")


class ConceptRelationship(BaseModel):
    """Semantic relationship connecting two concepts.

    Relationship types include: IMPLIES, SUPPORTS, CONTRADICTS, RESULTS_FROM, ENABLES, etc.
    """
    to_id: str = Field(..., description="Target concept ID")
    to_label: str = Field(..., description="Target concept label")
    rel_type: str = Field(..., description="Relationship type (e.g., IMPLIES, SUPPORTS)")
    confidence: Optional[float] = Field(None, description="Confidence score (0.0-1.0) if available")
    # ADR-051: Edge provenance metadata
    created_by: Optional[str] = Field(None, description="User ID who created this relationship")
    source: Optional[str] = Field(None, description="Source of relationship: llm_extraction, human_curated, inference")
    job_id: Optional[str] = Field(None, description="Job ID that created this relationship")
    document_id: Optional[str] = Field(None, description="Document hash (content_hash) that created this relationship")
    created_at: Optional[str] = Field(None, description="Timestamp when relationship was created")
    # ADR-065: Vocabulary epistemic status metadata
    category: Optional[str] = Field(None, description="Vocabulary category (causality, identity, temporal, etc.)")
    avg_grounding: Optional[float] = Field(None, description="Average grounding strength for this vocabulary type (-1.0 to 1.0)")
    epistemic_status: Optional[str] = Field(None, description="Epistemic status classification (WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, POORLY_GROUNDED, CONTRADICTED, HISTORICAL, INSUFFICIENT_DATA)")


class ProvenanceDocument(BaseModel):
    """ADR-051: Document provenance information from DocumentMeta nodes"""
    document_id: str = Field(..., description="Document hash (content_hash)")
    filename: str = Field(..., description="Original filename")
    source_type: Optional[str] = Field(None, description="Source type: file, stdin, mcp, api")
    source_path: Optional[str] = Field(None, description="Full filesystem path (file ingestion only)")
    hostname: Optional[str] = Field(None, description="Hostname where ingestion initiated")
    ingested_by: Optional[str] = Field(None, description="User ID who ingested this document")
    ingested_at: Optional[str] = Field(None, description="Timestamp when document was ingested")
    job_id: Optional[str] = Field(None, description="Job ID that ingested this document")
    source_count: Optional[int] = Field(None, description="Number of source nodes created from this document")


class ConceptProvenance(BaseModel):
    """ADR-051: Provenance tracking for concepts and documents.

    For Concept nodes: Lists source documents via DocumentMeta
    For DocumentMeta nodes: Shows full document metadata
    """
    # For DocumentMeta nodes (direct metadata)
    filename: Optional[str] = Field(None, description="Filename (for DocumentMeta nodes)")
    source_type: Optional[str] = Field(None, description="Source type (for DocumentMeta nodes)")
    source_path: Optional[str] = Field(None, description="Full path (for DocumentMeta nodes)")
    hostname: Optional[str] = Field(None, description="Hostname (for DocumentMeta nodes)")
    ingested_by: Optional[str] = Field(None, description="User ID (for DocumentMeta nodes)")
    created_at: Optional[str] = Field(None, description="Ingestion timestamp (for DocumentMeta nodes)")
    job_id: Optional[str] = Field(None, description="Job ID (for DocumentMeta nodes)")
    source_count: Optional[int] = Field(None, description="Source node count (for DocumentMeta nodes)")

    # For Concept nodes (list of source documents)
    documents: Optional[List[ProvenanceDocument]] = Field(None, description="Source documents (for Concept nodes)")


class ConceptDetailsResponse(BaseModel):
    """Complete concept information with evidence and relationships.

    Includes all text instances where concept appears and all semantic relationships
    connecting it to other concepts in the graph.
    """
    concept_id: str = Field(..., description="Unique concept identifier")
    label: str = Field(..., description="Human-readable concept label")
    description: Optional[str] = Field(None, description="Factual 1-2 sentence definition of the concept")
    search_terms: List[str] = Field(..., description="Alternative search terms for this concept")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding for semantic similarity (1536 dimensions)")
    documents: List[str] = Field(..., description="Documents where concept appears")
    instances: List[ConceptInstance] = Field(..., description="Evidence instances (quotes from text)")
    relationships: List[ConceptRelationship] = Field(..., description="Outgoing relationships to other concepts")
    grounding_strength: Optional[float] = Field(None, description="Grounding strength (-1.0 to 1.0) based on incoming relationship semantics (ADR-044)")
    # ADR-063: Semantic diversity
    diversity_score: Optional[float] = Field(None, description="Semantic diversity score (0.0 to 1.0) based on related concept embeddings (ADR-063)")
    diversity_related_count: Optional[int] = Field(None, description="Number of related concepts analyzed for diversity calculation")
    authenticated_diversity: Optional[float] = Field(None, description="Sign-weighted diversity: sign(grounding) × diversity. Positive: diverse support, Negative: diverse contradiction (ADR-044 + ADR-063)")
    # ADR-051: Provenance tracking
    provenance: Optional[ConceptProvenance] = Field(None, description="Provenance information (source documents or document metadata)")


# Related Concepts Models
class RelatedConceptsRequest(BaseModel):
    """Request to find concepts related through graph traversal.

    Performs breadth-first search from a starting concept to find all connected concepts
    within max_depth hops. Optionally filters by specific relationship types.
    """
    concept_id: str = Field(..., description="Starting concept ID")
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types (e.g., ['IMPLIES', 'SUPPORTS'])")
    max_depth: int = Field(2, description="Maximum traversal depth (1-5 hops)", ge=1, le=5)
    # ADR-065: Epistemic status filtering
    include_epistemic_status: Optional[List[str]] = Field(None, description="Filter to only include relationships with these epistemic statuses (e.g., ['AFFIRMATIVE', 'CONTESTED'])")
    exclude_epistemic_status: Optional[List[str]] = Field(None, description="Exclude relationships with these epistemic statuses (e.g., ['HISTORICAL', 'INSUFFICIENT_DATA'])")


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
    include_evidence: bool = Field(False, description="Include sample evidence instances for each concept in paths")
    include_grounding: bool = Field(True, description="Include grounding strength for each concept in paths (ADR-044)")
    # ADR-065: Epistemic status filtering
    include_epistemic_status: Optional[List[str]] = Field(None, description="Filter to only include relationships with these epistemic statuses (e.g., ['AFFIRMATIVE', 'CONTESTED'])")
    exclude_epistemic_status: Optional[List[str]] = Field(None, description="Exclude relationships with these epistemic statuses (e.g., ['HISTORICAL', 'INSUFFICIENT_DATA'])")


class PathNode(BaseModel):
    """Node in a connection path"""
    id: str = Field(..., description="Concept ID")
    label: str = Field(..., description="Concept label")
    description: Optional[str] = Field(None, description="Factual 1-2 sentence definition of the concept")
    grounding_strength: Optional[float] = Field(None, description="Grounding strength (-1.0 to 1.0) if requested (ADR-044)")
    sample_evidence: Optional[List['ConceptInstance']] = Field(None, description="Sample evidence instances when include_evidence=true")


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
    include_evidence: bool = Field(False, description="Include sample evidence instances for each concept in paths")
    include_grounding: bool = Field(True, description="Include grounding strength for each concept in paths (ADR-044)")
    # ADR-065: Epistemic status filtering
    include_epistemic_status: Optional[List[str]] = Field(None, description="Filter to only include relationships with these epistemic statuses (e.g., ['AFFIRMATIVE', 'CONTESTED'])")
    exclude_epistemic_status: Optional[List[str]] = Field(None, description="Exclude relationships with these epistemic statuses (e.g., ['HISTORICAL', 'INSUFFICIENT_DATA'])")


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


# Raw openCypher Query Models
class CypherQueryRequest(BaseModel):
    """Request to execute a raw openCypher query.

    Allows direct execution of openCypher queries against the Apache AGE graph.
    Returns nodes and relationships in a format suitable for visualization.
    """
    query: str = Field(..., description="Raw openCypher query to execute", min_length=1)
    limit: Optional[int] = Field(None, description="Optional result limit (applied if query doesn't have LIMIT)", ge=1, le=1000)


class CypherNode(BaseModel):
    """Node returned from Cypher query"""
    id: str = Field(..., description="Node identifier (concept_id)")
    label: str = Field(..., description="Node label/name")
    properties: Dict[str, Any] = Field(default_factory=dict, description="All node properties")


class CypherRelationship(BaseModel):
    """Relationship/edge returned from Cypher query"""
    from_id: str = Field(..., description="Source node ID")
    to_id: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relationship type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class CypherQueryResponse(BaseModel):
    """Response from executing raw openCypher query"""
    nodes: List[CypherNode] = Field(..., description="Nodes returned by query")
    relationships: List[CypherRelationship] = Field(..., description="Relationships returned by query")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    row_count: int = Field(..., description="Number of rows returned")
    query: str = Field(..., description="The executed query")


# Source Search Models (ADR-068 Phase 3)
class SourceSearchRequest(BaseModel):
    """Request to search source text using semantic similarity (ADR-068).

    Searches source text chunks via embedding similarity, returns matched sources
    with related concepts for evidence/provenance retrieval.
    """
    query: str = Field(..., description="Search query text", min_length=1)
    limit: int = Field(10, description="Maximum number of sources to return", ge=1, le=100)
    min_similarity: float = Field(
        DEFAULT_SOURCE_SEARCH_SIMILARITY,
        description="Minimum similarity score (0.0-1.0, default 0.7=70%)",
        ge=0.0,
        le=1.0
    )
    ontology: Optional[str] = Field(None, description="Filter by ontology/document name")
    include_concepts: bool = Field(True, description="Include concepts extracted from matched sources")
    include_full_text: bool = Field(True, description="Include full source text (not just matched chunk)")


class SourceConcept(BaseModel):
    """Concept extracted from a source."""
    concept_id: str = Field(..., description="Concept identifier")
    label: str = Field(..., description="Concept label")
    description: Optional[str] = Field(None, description="Concept description")
    instance_quote: str = Field(..., description="Quote from source that evidences this concept")


class SourceChunk(BaseModel):
    """Matched text chunk from source embedding."""
    chunk_text: str = Field(..., description="Matched chunk text")
    start_offset: int = Field(..., description="Character offset where chunk starts in source.full_text")
    end_offset: int = Field(..., description="Character offset where chunk ends in source.full_text")
    chunk_index: int = Field(..., description="Chunk number (0-based)")
    similarity: float = Field(..., description="Cosine similarity score for this chunk (0.0-1.0)")


class SourceSearchResult(BaseModel):
    """Single source search result with matched chunk and related concepts."""
    source_id: str = Field(..., description="Source node identifier")
    document: str = Field(..., description="Document/ontology name")
    paragraph: int = Field(..., description="Paragraph/chunk number in document")
    similarity: float = Field(..., description="Best chunk similarity score for this source")
    is_stale: bool = Field(..., description="True if source text changed since embeddings generated")
    matched_chunk: SourceChunk = Field(..., description="Best matching chunk from this source")
    full_text: Optional[str] = Field(None, description="Complete source text (if include_full_text=true)")
    concepts: List[SourceConcept] = Field(default_factory=list, description="Concepts extracted from this source (if include_concepts=true)")


class SourceSearchResponse(BaseModel):
    """Source search results (ADR-068 Phase 3)."""
    query: str = Field(..., description="Original search query")
    count: int = Field(..., description="Number of sources returned")
    results: List[SourceSearchResult] = Field(..., description="Ranked source results by similarity")
    threshold_used: float = Field(..., description="Similarity threshold used")


# Polarity Axis Models (ADR-070)
class PolarityAxisRequest(BaseModel):
    """Request to analyze bidirectional semantic dimension (polarity axis)."""
    positive_pole_id: str = Field(..., description="Concept ID for positive pole (e.g., 'Modern')")
    negative_pole_id: str = Field(..., description="Concept ID for negative pole (e.g., 'Traditional')")
    candidate_ids: Optional[List[str]] = Field(None, description="Specific concept IDs to project onto axis (optional)")
    auto_discover: bool = Field(True, description="Auto-discover related concepts if candidate_ids not provided")
    max_candidates: int = Field(20, description="Maximum candidates for auto-discovery", ge=1, le=100)
    max_hops: int = Field(2, description="Maximum graph hops for auto-discovery (1-3)", ge=1, le=3)


class PolarityAxisPole(BaseModel):
    """Concept pole (endpoint) of polarity axis."""
    concept_id: str = Field(..., description="Concept ID")
    label: str = Field(..., description="Concept label")
    grounding: float = Field(..., description="Grounding strength (-1.0 to 1.0)")
    description: Optional[str] = Field(None, description="Concept description")


class PolarityAxisInfo(BaseModel):
    """Polarity axis metadata (semantic dimension)."""
    positive_pole: PolarityAxisPole = Field(..., description="Positive pole concept")
    negative_pole: PolarityAxisPole = Field(..., description="Negative pole concept")
    magnitude: float = Field(..., description="Semantic distance between poles")
    axis_quality: str = Field(..., description="Axis quality: 'strong' (>0.8) or 'weak' (<0.8)")


class ConceptProjection(BaseModel):
    """Concept projected onto polarity axis."""
    concept_id: str = Field(..., description="Concept ID")
    label: str = Field(..., description="Concept label")
    position: float = Field(..., description="Position on axis (-1.0 to +1.0, 0 = midpoint)")
    axis_distance: float = Field(..., description="Distance from axis (orthogonal component)")
    direction: str = Field(..., description="Direction: 'positive' (>0.3), 'negative' (<-0.3), or 'neutral'")
    grounding: float = Field(..., description="Grounding strength (-1.0 to 1.0)")
    alignment: Dict[str, float] = Field(..., description="Similarity to poles (positive_pole_similarity, negative_pole_similarity)")


class PolarityAxisStatistics(BaseModel):
    """Statistical summary of polarity axis analysis."""
    total_concepts: int = Field(..., description="Number of concepts projected")
    position_range: List[float] = Field(..., description="[min, max] position values")
    mean_position: float = Field(..., description="Mean position on axis")
    std_deviation: float = Field(..., description="Standard deviation of positions")
    mean_axis_distance: float = Field(..., description="Mean distance from axis")
    direction_distribution: Dict[str, int] = Field(..., description="Count by direction (positive, negative, neutral)")


class GroundingCorrelation(BaseModel):
    """Correlation between axis position and grounding strength."""
    pearson_r: float = Field(..., description="Pearson correlation coefficient (-1.0 to 1.0)")
    p_value: float = Field(..., description="Statistical significance (p-value)")
    interpretation: str = Field(..., description="Human-readable interpretation of correlation")
    strength: Optional[str] = Field(None, description="Correlation strength: 'strong', 'moderate', 'weak'")
    direction: Optional[str] = Field(None, description="Correlation direction: 'positive', 'negative', 'none'")


class PolarityAxisResponse(BaseModel):
    """Polarity axis analysis results."""
    success: bool = Field(..., description="Analysis success status")
    axis: PolarityAxisInfo = Field(..., description="Polarity axis metadata")
    projections: List[ConceptProjection] = Field(..., description="Concepts projected onto axis")
    statistics: PolarityAxisStatistics = Field(..., description="Statistical summary")
    grounding_correlation: GroundingCorrelation = Field(..., description="Correlation between position and grounding")
