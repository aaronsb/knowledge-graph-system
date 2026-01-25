"""
Artifact Models (ADR-083)

Pydantic models for artifact persistence API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


# Valid artifact types (from migration 035)
ARTIFACT_TYPES = [
    'polarity_analysis',
    'projection',
    'query_result',
    'graph_subgraph',
    'vocabulary_analysis',
    'epistemic_measurement',
    'consolidation_result',
    'search_result',
    'connection_path',
    'report',
    'stats_snapshot'
]

# Valid representation sources (from migration 035)
REPRESENTATIONS = [
    'polarity_explorer',
    'embedding_landscape',
    'block_builder',
    'edge_explorer',
    'vocabulary_chord',
    'force_graph_2d',
    'force_graph_3d',
    'report_workspace',
    'cli',
    'mcp_server',
    'api_direct'
]


class ArtifactCreate(BaseModel):
    """Request model for creating an artifact."""
    artifact_type: str = Field(..., description="Type of artifact (e.g., polarity_analysis, projection)")
    representation: str = Field(..., description="Source UI/tool (e.g., cli, polarity_explorer)")
    name: Optional[str] = Field(None, description="Optional human-readable name")
    parameters: Dict[str, Any] = Field(..., description="Parameters used to generate this artifact")
    payload: Dict[str, Any] = Field(..., description="The computed result payload")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    ontology: Optional[str] = Field(None, description="Associated ontology name")
    concept_ids: Optional[List[str]] = Field(None, description="Concept IDs involved in this artifact")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp")
    query_definition_id: Optional[int] = Field(None, description="Optional link to query definition")

    class Config:
        json_schema_extra = {
            "example": {
                "artifact_type": "polarity_analysis",
                "representation": "cli",
                "name": "Modern vs Traditional Analysis",
                "parameters": {
                    "positive_pole_id": "abc123",
                    "negative_pole_id": "def456",
                    "max_candidates": 20
                },
                "payload": {
                    "axis_quality": 0.85,
                    "projections": []
                },
                "ontology": "philosophy-texts"
            }
        }


class ArtifactMetadata(BaseModel):
    """Response model for artifact metadata (without payload)."""
    id: int
    artifact_type: str
    representation: str
    name: Optional[str]
    owner_id: Optional[int]
    graph_epoch: int
    is_fresh: bool = Field(..., description="True if graph_epoch matches current epoch")
    created_at: datetime
    expires_at: Optional[datetime]
    parameters: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]
    ontology: Optional[str]
    concept_ids: Optional[List[str]]
    query_definition_id: Optional[int]
    has_inline_result: bool = Field(..., description="True if payload stored inline")
    garage_key: Optional[str] = Field(None, description="Garage key if stored externally")


class ArtifactWithPayload(ArtifactMetadata):
    """Response model for artifact with full payload."""
    payload: Dict[str, Any]


class ArtifactList(BaseModel):
    """Response model for listing artifacts."""
    artifacts: List[ArtifactMetadata]
    total: int
    limit: int
    offset: int


class ArtifactCreateResponse(BaseModel):
    """Response model for artifact creation."""
    id: int
    artifact_type: str
    representation: str
    name: Optional[str]
    graph_epoch: int
    storage_location: str = Field(..., description="'inline' or 'garage'")
    garage_key: Optional[str]
    created_at: datetime
