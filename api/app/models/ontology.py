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
    source_ids: List[str] = []


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


# =========================================================================
# ADR-200 Phase 3a: Scoring & Breathing Control Surface
# =========================================================================

class OntologyStats(BaseModel):
    """Raw counts for mass scoring (ADR-200 Phase 3a)"""
    ontology: str
    concept_count: int = 0
    source_count: int = 0
    file_count: int = 0
    evidence_count: int = 0
    internal_relationship_count: int = 0
    cross_ontology_relationship_count: int = 0


class OntologyScores(BaseModel):
    """Computed scores for an ontology (ADR-200 Phase 3a)"""
    ontology: str
    mass_score: float = 0.0
    coherence_score: float = 0.0
    raw_exposure: float = 0.0
    weighted_exposure: float = 0.0
    protection_score: float = 0.0
    last_evaluated_epoch: int = 0


class OntologyScoresResponse(BaseModel):
    """List of all ontology scores"""
    count: int
    global_epoch: int
    scores: List[OntologyScores]


class ConceptDegreeRanking(BaseModel):
    """Concept ranked by degree within an ontology"""
    concept_id: str
    label: str
    degree: int = 0
    in_degree: int = 0
    out_degree: int = 0


class ConceptDegreeResponse(BaseModel):
    """Top concepts by degree in an ontology"""
    ontology: str
    count: int
    concepts: List[ConceptDegreeRanking]


class AffinityResult(BaseModel):
    """Cross-ontology affinity measurement"""
    other_ontology: str
    shared_concept_count: int = 0
    total_concepts: int = 0
    affinity_score: float = 0.0


class AffinityResponse(BaseModel):
    """Cross-ontology affinity for an ontology"""
    ontology: str
    count: int
    affinities: List[AffinityResult]


class ReassignRequest(BaseModel):
    """Request to reassign sources between ontologies"""
    target_ontology: str = Field(..., description="Destination ontology name")
    source_ids: List[str] = Field(..., description="Source IDs to move", min_length=1)


class ReassignResponse(BaseModel):
    """Response from source reassignment"""
    from_ontology: str
    to_ontology: str
    sources_reassigned: int
    success: bool
    error: Optional[str] = None


class DissolveRequest(BaseModel):
    """Request to dissolve an ontology (non-destructive demotion)"""
    target_ontology: str = Field(..., description="Default ontology to receive orphaned sources")


class DissolveResponse(BaseModel):
    """Response from ontology dissolution"""
    dissolved_ontology: str
    sources_reassigned: int
    ontology_node_deleted: bool
    reassignment_targets: List[str] = []
    success: bool
    error: Optional[str] = None
