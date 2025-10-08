"""Pydantic models for ontology operations"""

from pydantic import BaseModel, Field
from typing import List, Optional


class OntologyItem(BaseModel):
    """Single ontology in the list"""
    ontology: str
    source_count: int
    file_count: int
    concept_count: int


class OntologyListResponse(BaseModel):
    """List of all ontologies"""
    count: int
    ontologies: List[OntologyItem]


class OntologyInfoResponse(BaseModel):
    """Detailed ontology information"""
    ontology: str
    statistics: dict  # Contains source_count, file_count, concept_count, instance_count, relationship_count
    files: List[str]


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
