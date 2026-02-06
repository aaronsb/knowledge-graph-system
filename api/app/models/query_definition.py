"""
Query Definition Models (ADR-083)

Pydantic models for query definitions - saved query recipes that can be re-executed.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field


# Valid definition types (from migration 035, extended by 050 and 052)
DEFINITION_TYPES = [
    'block_diagram',
    'cypher',
    'search',
    'polarity',
    'connection',
    'exploration',
    'program',
]

DefinitionType = Literal['block_diagram', 'cypher', 'search', 'polarity', 'connection', 'exploration', 'program']


class QueryDefinitionCreate(BaseModel):
    """Request model for creating a query definition."""
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    definition_type: DefinitionType = Field(..., description="Type of query definition")
    definition: Dict[str, Any] = Field(..., description="Query parameters/structure as JSON")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata (nodeCount, edgeCount, description)")

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
                },
                "metadata": {
                    "description": "Analyzing modern vs traditional approaches",
                    "nodeCount": 3,
                    "edgeCount": 2
                }
            }
        }


class QueryDefinitionUpdate(BaseModel):
    """Request model for updating a query definition."""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Human-readable name")
    definition: Optional[Dict[str, Any]] = Field(None, description="Query parameters/structure")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata (nodeCount, edgeCount, description)")


class QueryDefinitionRead(BaseModel):
    """Response model for query definition data."""
    id: int
    name: str
    definition_type: DefinitionType
    definition: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
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
    updated_at: datetime
