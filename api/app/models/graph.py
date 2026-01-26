"""
Pydantic models for batch graph operations (ADR-089 Phase 1b).

These models support bulk creation of concepts and edges in a single
transactional operation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List

from .concepts import MatchingMode, CreationMethod
from .edges import RelationshipCategory, EdgeSource


class BatchConceptCreate(BaseModel):
    """
    Concept definition for batch creation.

    Unlike ConceptCreate, ontology is specified at the request level.
    """

    label: str = Field(
        ...,
        description="Human-readable concept label",
        min_length=1,
        max_length=500
    )
    description: Optional[str] = Field(
        None,
        description="Factual 1-2 sentence definition of the concept",
        max_length=2000
    )
    search_terms: Optional[List[str]] = Field(
        default_factory=list,
        description="Alternative terms/phrases for matching"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "label": "Machine Learning",
                "description": "A branch of AI focused on learning from data",
                "search_terms": ["ML", "statistical learning"]
            }
        }


class BatchEdgeCreate(BaseModel):
    """
    Edge definition for batch creation.

    References concepts by label (not ID) to allow referencing
    concepts created in the same batch request.
    """

    from_label: str = Field(
        ...,
        description="Source concept label (must exist or be created in this batch)"
    )
    to_label: str = Field(
        ...,
        description="Target concept label (must exist or be created in this batch)"
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

    class Config:
        json_schema_extra = {
            "example": {
                "from_label": "Machine Learning",
                "to_label": "Artificial Intelligence",
                "relationship_type": "IS_SUBFIELD_OF",
                "category": "structural",
                "confidence": 1.0
            }
        }


class BatchCreateRequest(BaseModel):
    """
    Request to batch create concepts and edges.

    All operations are performed in a single transaction - if any
    operation fails, the entire batch is rolled back.
    """

    ontology: str = Field(
        ...,
        description="Ontology/collection name for all concepts",
        min_length=1,
        max_length=100
    )
    matching_mode: MatchingMode = Field(
        MatchingMode.AUTO,
        description="How to handle potential duplicates"
    )
    creation_method: CreationMethod = Field(
        CreationMethod.IMPORT,
        description="How these entities are being created"
    )
    concepts: List[BatchConceptCreate] = Field(
        default_factory=list,
        description="Concepts to create"
    )
    edges: List[BatchEdgeCreate] = Field(
        default_factory=list,
        description="Edges to create (processed after concepts)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "ontology": "ai-research",
                "matching_mode": "auto",
                "concepts": [
                    {"label": "Machine Learning", "description": "Learning from data"},
                    {"label": "Neural Networks", "description": "Computational models inspired by the brain"}
                ],
                "edges": [
                    {
                        "from_label": "Neural Networks",
                        "to_label": "Machine Learning",
                        "relationship_type": "IS_TECHNIQUE_IN"
                    }
                ]
            }
        }


class BatchItemResult(BaseModel):
    """Result for a single item in the batch."""

    label: str = Field(..., description="Item label")
    status: str = Field(..., description="created, matched, or error")
    id: Optional[str] = Field(None, description="Created/matched entity ID")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchResponse(BaseModel):
    """Response from batch creation."""

    concepts_created: int = Field(0, description="Number of new concepts created")
    concepts_matched: int = Field(0, description="Number of concepts matched to existing")
    edges_created: int = Field(0, description="Number of edges created")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    concept_results: List[BatchItemResult] = Field(
        default_factory=list,
        description="Per-concept results"
    )
    edge_results: List[BatchItemResult] = Field(
        default_factory=list,
        description="Per-edge results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "concepts_created": 2,
                "concepts_matched": 0,
                "edges_created": 1,
                "errors": [],
                "concept_results": [
                    {"label": "Machine Learning", "status": "created", "id": "c_abc123"},
                    {"label": "Neural Networks", "status": "created", "id": "c_def456"}
                ],
                "edge_results": [
                    {"label": "Neural Networks -> Machine Learning", "status": "created", "id": "e_789"}
                ]
            }
        }
