"""
Pydantic models for deterministic edge CRUD (ADR-089).

These models support direct relationship creation/editing between concepts
without going through LLM ingestion.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class EdgeSource(str, Enum):
    """
    How this edge was created (provenance tracking).

    - api_creation: Created via deterministic API
    - human_curation: Created/edited by human
    - llm_extraction: Extracted by LLM during ingestion
    - import: Imported from foreign graph
    """
    API_CREATION = "api_creation"
    HUMAN_CURATION = "human_curation"
    LLM_EXTRACTION = "llm_extraction"
    IMPORT = "import"


class RelationshipCategory(str, Enum):
    """
    Semantic category of the relationship (ADR-022).

    Categories help with query filtering and visualization.
    """
    LOGICAL_TRUTH = "logical_truth"
    CAUSAL = "causal"
    STRUCTURAL = "structural"
    TEMPORAL = "temporal"
    COMPARATIVE = "comparative"
    FUNCTIONAL = "functional"
    DEFINITIONAL = "definitional"


class EdgeCreate(BaseModel):
    """Request to create a new edge between concepts."""

    from_concept_id: str = Field(
        ...,
        description="Source concept ID"
    )
    to_concept_id: str = Field(
        ...,
        description="Target concept ID"
    )
    relationship_type: str = Field(
        ...,
        description="Relationship type (e.g., IMPLIES, SUPPORTS, CONTRADICTS)",
        min_length=1,
        max_length=100
    )
    category: RelationshipCategory = Field(
        RelationshipCategory.STRUCTURAL,
        description="Semantic category of the relationship"
    )
    confidence: float = Field(
        1.0,
        description="Confidence score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    source: EdgeSource = Field(
        EdgeSource.API_CREATION,
        description="How this edge is being created"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "from_concept_id": "c_abc123",
                "to_concept_id": "c_def456",
                "relationship_type": "IMPLIES",
                "category": "logical_truth",
                "confidence": 0.95,
                "source": "api_creation"
            }
        }


class EdgeUpdate(BaseModel):
    """Request to update an existing edge (partial update)."""

    relationship_type: Optional[str] = Field(
        None,
        description="New relationship type",
        min_length=1,
        max_length=100
    )
    category: Optional[RelationshipCategory] = Field(
        None,
        description="New category"
    )
    confidence: Optional[float] = Field(
        None,
        description="New confidence score",
        ge=0.0,
        le=1.0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "confidence": 0.8
            }
        }


class EdgeResponse(BaseModel):
    """Response containing edge details."""

    edge_id: str = Field(..., description="Unique edge identifier")
    from_concept_id: str = Field(..., description="Source concept ID")
    to_concept_id: str = Field(..., description="Target concept ID")
    relationship_type: str = Field(..., description="Relationship type")
    category: str = Field(..., description="Semantic category")
    confidence: float = Field(..., description="Confidence score")
    source: str = Field(..., description="How edge was created")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="User who created")

    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "e_abc123",
                "from_concept_id": "c_abc123",
                "to_concept_id": "c_def456",
                "relationship_type": "IMPLIES",
                "category": "logical_truth",
                "confidence": 0.95,
                "source": "api_creation",
                "created_at": "2026-01-25T20:00:00Z",
                "created_by": "user_123"
            }
        }


class EdgeListResponse(BaseModel):
    """Response containing a list of edges."""

    edges: List[EdgeResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching edges")
    offset: int = Field(0, description="Offset used for pagination")
    limit: int = Field(50, description="Limit used for pagination")


class EdgeListParams(BaseModel):
    """Query parameters for listing edges."""

    from_concept_id: Optional[str] = Field(None, description="Filter by source concept")
    to_concept_id: Optional[str] = Field(None, description="Filter by target concept")
    relationship_type: Optional[str] = Field(None, description="Filter by relationship type")
    category: Optional[RelationshipCategory] = Field(None, description="Filter by category")
    source: Optional[EdgeSource] = Field(None, description="Filter by creation source")
    offset: int = Field(0, ge=0, description="Pagination offset")
    limit: int = Field(50, ge=1, le=500, description="Pagination limit")
