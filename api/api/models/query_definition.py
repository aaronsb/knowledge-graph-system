"""
Query Definition Models (ADR-083)

Pydantic models for query definitions - saved query recipes that can be re-executed.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field


# Valid definition types (from migration 035)
DEFINITION_TYPES = [
    'block_diagram',
    'cypher',
    'search',
    'polarity',
    'connection'
]

DefinitionType = Literal['block_diagram', 'cypher', 'search', 'polarity', 'connection']


class QueryDefinitionCreate(BaseModel):
    """Request model for creating a query definition."""
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    definition_type: DefinitionType = Field(..., description="Type of query definition")
    definition: Dict[str, Any] = Field(..., description="Query parameters/structure as JSON")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Modern vs Traditional Analysis",
                "definition_type": "polarity",
                "definition": {
                    "positive_pole_query": "modern approaches",
                    "negative_pole_query": "traditional methods",
                    "max_candidates": 20,
                    "ontology": "philosophy-texts"
                }
            }
        }


class QueryDefinitionUpdate(BaseModel):
    """Request model for updating a query definition."""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Human-readable name")
    definition: Optional[Dict[str, Any]] = Field(None, description="Query parameters/structure")


class QueryDefinitionRead(BaseModel):
    """Response model for query definition data."""
    id: int
    name: str
    definition_type: DefinitionType
    definition: Dict[str, Any]
    owner_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class QueryDefinitionList(BaseModel):
    """Response model for listing query definitions."""
    definitions: List[QueryDefinitionRead]
    total: int
    limit: int
    offset: int


class QueryDefinitionCreateResponse(BaseModel):
    """Response model for query definition creation."""
    id: int
    name: str
    definition_type: DefinitionType
    created_at: datetime
