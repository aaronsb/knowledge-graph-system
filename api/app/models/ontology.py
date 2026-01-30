"""Pydantic models for ontology operations"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional


class LifecycleState(str, Enum):
    """Ontology lifecycle states (ADR-200 Phase 2)"""
    active = "active"
    pinned = "pinned"
    frozen = "frozen"


class OntologyItem(BaseModel):
    """Single ontology in the list"""
    ontology: str
    source_count: int
    file_count: int
    concept_count: int
    # ADR-200: Graph node properties (always present — no source-only fallback)
    ontology_id: str
    lifecycle_state: str
    creation_epoch: int
    has_embedding: bool
    created_by: Optional[str] = None


class OntologyListResponse(BaseModel):
    """List of all ontologies"""
    count: int
    ontologies: List[OntologyItem]


class OntologyNodeResponse(BaseModel):
    """Ontology graph node properties (ADR-200)"""
    ontology_id: str
    name: str
    description: str = ""
    lifecycle_state: str = "active"
    creation_epoch: int = 0
    has_embedding: bool = False
    search_terms: List[str] = []
    created_by: Optional[str] = None


class OntologyLifecycleRequest(BaseModel):
    """Request to change ontology lifecycle state (ADR-200 Phase 2)"""
    state: LifecycleState = Field(..., description="Target lifecycle state")


class OntologyLifecycleResponse(BaseModel):
    """Response from lifecycle state change"""
    ontology: str
    previous_state: str
    new_state: str
    success: bool


class OntologyCreateRequest(BaseModel):
    """Request to create an ontology (ADR-200: directed growth)"""
    name: str = Field(..., description="Ontology name", min_length=1)
    description: str = Field("", description="What this knowledge domain covers")


class OntologyInfoResponse(BaseModel):
    """Detailed ontology information"""
    ontology: str
    statistics: dict  # Contains source_count, file_count, concept_count, instance_count, relationship_count
    files: List[str]
    # ADR-200: Graph node properties
    node: Optional[OntologyNodeResponse] = None


class OntologyFileInfo(BaseModel):
    """File within an ontology"""
    file_path: str
    chunk_count: int
    concept_count: int


class OntologyFilesResponse(BaseModel):
    """Files in an ontology"""
    ontology: str
    count: int
    files: List[OntologyFileInfo]


class OntologyDeleteRequest(BaseModel):
    """Request to delete an ontology"""
    force: bool = Field(False, description="Skip confirmation (auto-confirm deletion)")


class OntologyDeleteResponse(BaseModel):
    """Delete ontology response"""
    ontology: str
    deleted: bool
    sources_deleted: int
    orphaned_concepts_deleted: int
    error: Optional[str] = None


class OntologyRenameRequest(BaseModel):
    """Request to rename an ontology"""
    new_name: str = Field(..., description="New ontology name", min_length=1)


class OntologyRenameResponse(BaseModel):
    """Rename ontology response"""
    old_name: str
    new_name: str
    sources_updated: int
    success: bool
    error: Optional[str] = None
