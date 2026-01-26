"""
Pydantic models for deterministic concept CRUD (ADR-089).

These models support direct concept creation/editing without LLM ingestion,
enabling manual curation, agent-driven knowledge building, and foreign graph import.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class MatchingMode(str, Enum):
    """
    How to handle potential duplicates when creating concepts.

    - auto: Match existing concepts by embedding similarity, create if no match
    - force_create: Always create new concept, skip matching
    - match_only: Only link to existing concept, fail if no match found
    """
    AUTO = "auto"
    FORCE_CREATE = "force_create"
    MATCH_ONLY = "match_only"


class CreationMethod(str, Enum):
    """
    How this concept was created (provenance tracking).

    - api: Created via deterministic API
    - cli: Created via CLI tool
    - mcp: Created via MCP server
    - workstation: Created via web workstation
    - import: Imported from foreign graph
    - llm_extraction: Extracted by LLM during ingestion (default for ingest pipeline)
    """
    API = "api"
    CLI = "cli"
    MCP = "mcp"
    WORKSTATION = "workstation"
    IMPORT = "import"
    LLM_EXTRACTION = "llm_extraction"


class ConceptCreate(BaseModel):
    """Request to create a new concept."""

    label: str = Field(
        ...,
        description="Human-readable concept label",
        min_length=1,
        max_length=500
    )
    ontology: str = Field(
        ...,
        description="Ontology/collection name",
        min_length=1,
        max_length=100
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
    matching_mode: MatchingMode = Field(
        MatchingMode.AUTO,
        description="How to handle potential duplicates"
    )
    creation_method: CreationMethod = Field(
        CreationMethod.API,
        description="How this concept is being created"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "label": "Machine Learning",
                "ontology": "ai-concepts",
                "description": "A subset of artificial intelligence that enables systems to learn from data.",
                "search_terms": ["ML", "statistical learning"],
                "matching_mode": "auto",
                "creation_method": "api"
            }
        }


class ConceptUpdate(BaseModel):
    """Request to update an existing concept (partial update)."""

    label: Optional[str] = Field(
        None,
        description="New label for the concept",
        min_length=1,
        max_length=500
    )
    description: Optional[str] = Field(
        None,
        description="New description",
        max_length=2000
    )
    search_terms: Optional[List[str]] = Field(
        None,
        description="Replace search terms (not merge)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "description": "Updated definition of the concept."
            }
        }


class ConceptResponse(BaseModel):
    """Response containing concept details."""

    concept_id: str = Field(..., description="Unique concept identifier")
    label: str = Field(..., description="Human-readable label")
    description: Optional[str] = Field(None, description="Concept definition")
    search_terms: List[str] = Field(default_factory=list, description="Alternative terms")
    ontology: Optional[str] = Field(None, description="Ontology this concept belongs to")
    creation_method: Optional[str] = Field(None, description="How this concept was created")
    has_embedding: bool = Field(True, description="Whether embedding has been generated")
    matched_existing: bool = Field(
        False,
        description="True if this was matched to an existing concept rather than created"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "concept_id": "c_abc123",
                "label": "Machine Learning",
                "description": "A subset of AI that enables systems to learn from data.",
                "search_terms": ["ML", "statistical learning"],
                "ontology": "ai-concepts",
                "creation_method": "api",
                "has_embedding": True,
                "matched_existing": False
            }
        }


class ConceptListResponse(BaseModel):
    """Response containing a list of concepts."""

    concepts: List[ConceptResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of matching concepts")
    offset: int = Field(0, description="Offset used for pagination")
    limit: int = Field(50, description="Limit used for pagination")


class ConceptListParams(BaseModel):
    """Query parameters for listing concepts."""

    ontology: Optional[str] = Field(None, description="Filter by ontology")
    label_contains: Optional[str] = Field(None, description="Filter by label substring")
    creation_method: Optional[CreationMethod] = Field(None, description="Filter by creation method")
    offset: int = Field(0, ge=0, description="Pagination offset")
    limit: int = Field(50, ge=1, le=500, description="Pagination limit")
