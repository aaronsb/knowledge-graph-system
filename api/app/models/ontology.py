"""Pydantic models for ontology operations"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Tuple


class LifecycleState(str, Enum):
    """Ontology lifecycle states (ADR-200 Phase 2)"""
    active = "active"
    pinned = "pinned"
    frozen = "frozen"


class ProposalType(str, Enum):
    """
    Closed annealing-action vocabulary (ADR-206).

    The six ontology actions are the Sonnet-tier closed vocabulary; only one
    of these may be emitted per proposal. ADJUST_CONTROL is the Opus-tier
    meta-action that tunes Phase 3 control-surface entries (`proposal_kind
    = 'control'` rather than 'ontology'). Deprecated values are retained
    so historical rows still parse — `normalize_proposal_type` maps them
    to current names per the ADR-206 alias table.
    """
    # Sonnet-tier ontology actions (proposal_kind = 'ontology')
    CLEAVE = "CLEAVE"
    DISSOLVE = "DISSOLVE"
    MERGE = "MERGE"
    RENAME = "RENAME"
    NO_ACTION = "NO_ACTION"
    ESCALATE = "ESCALATE"
    # Opus-tier meta-action (proposal_kind = 'control')
    ADJUST_CONTROL = "ADJUST_CONTROL"
    # Deprecated — normalized on read via _DEPRECATED_ALIASES
    PROMOTION_LEGACY = "promotion"
    DEMOTION_LEGACY = "demotion"


class ProposalKind(str, Enum):
    """Discriminator on annealing_proposals.proposal_kind (ADR-206)."""
    ONTOLOGY = "ontology"
    CONTROL = "control"


# ADR-206 §Aliases — historical names → 6-verb vocabulary.
#
# Each entry yields the canonical ProposalType plus a params delta that
# materializes the implicit context the old name carried. Callers merge
# the delta into the row's params JSONB before treating the row as a
# v2 proposal.
_DEPRECATED_ALIASES: Dict[str, Tuple[ProposalType, Dict[str, Any]]] = {
    # promotion: CLEAVE applied to the primordial pool.
    "promotion": (ProposalType.CLEAVE, {"source_ontology": "primordial"}),
    # demotion: DISSOLVE of a named ontology.
    "demotion": (ProposalType.DISSOLVE, {}),
}


def normalize_proposal_type(
    proposal_type: str,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[ProposalType, Dict[str, Any]]:
    """
    Map a stored proposal_type string to (canonical ProposalType, params).

    Historical rows carry `promotion` / `demotion` strings (pre-ADR-206).
    This collapses them onto the 6-verb vocabulary and merges the implicit
    parameters the old name carried (`source_ontology=primordial` for
    promotions; nothing extra for demotions, since DISSOLVE's per-source
    routing is read from the graph at execution time, not stored).

    Current 6-verb names pass through unchanged. Unknown names raise
    ValueError so corrupted rows surface loudly instead of silently
    falling through.
    """
    out_params: Dict[str, Any] = dict(params) if params else {}

    if proposal_type in _DEPRECATED_ALIASES:
        canonical, delta = _DEPRECATED_ALIASES[proposal_type]
        # Caller-supplied params win — never overwrite a v2 row that already
        # carries a contradicting field.
        for key, value in delta.items():
            out_params.setdefault(key, value)
        return canonical, out_params

    try:
        return ProposalType(proposal_type), out_params
    except ValueError as exc:
        raise ValueError(
            f"Unknown proposal_type {proposal_type!r}; not in ADR-206 vocabulary "
            f"and no deprecated alias matches"
        ) from exc


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
# ADR-200 Phase 3a: Scoring & Annealing Control Surface
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


# =========================================================================
# ADR-200 Phase 3b: Annealing Worker Models
# =========================================================================

class AnnealingProposal(BaseModel):
    """
    An annealing-worker proposal (ADR-200 Phase 3b, ADR-206 vocabulary).

    `proposal_type` carries the canonical ADR-206 verb after normalization;
    historical `promotion`/`demotion` rows are mapped on read via
    `normalize_proposal_type`. `params` is the verb-specific parameter
    shape (ADR-206 §1); `proposal_kind` discriminates ontology actions
    from the Opus-tier ADJUST_CONTROL meta-action.
    """
    id: int
    proposal_type: str
    proposal_kind: str = "ontology"
    ontology_name: str
    anchor_concept_id: Optional[str] = None
    target_ontology: Optional[str] = None
    reasoning: str
    params: Optional[Dict[str, Any]] = None
    mass_score: Optional[float] = None
    coherence_score: Optional[float] = None
    protection_score: Optional[float] = None
    status: str = "pending"
    created_at: datetime
    created_at_epoch: int = 0
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewer_notes: Optional[str] = None
    # Phase 4: execution tracking
    executed_at: Optional[datetime] = None
    execution_result: Optional[dict] = None
    execution_job_id: Optional[str] = None
    suggested_name: Optional[str] = None
    suggested_description: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "AnnealingProposal":
        """
        Build an AnnealingProposal from a DB row, normalizing legacy verbs.

        Historical rows carrying `promotion`/`demotion` are mapped to the
        canonical ADR-206 vocabulary, and the alias's implicit parameters
        are merged into `params` (e.g. promotion → CLEAVE with
        source_ontology=primordial).
        """
        proposal_type_raw = row.get("proposal_type", "")
        params_raw = row.get("params")
        canonical, merged_params = normalize_proposal_type(
            proposal_type_raw, params_raw
        )
        payload = dict(row)
        payload["proposal_type"] = canonical.value
        payload["params"] = merged_params or None
        return cls(**payload)


class AnnealingProposalListResponse(BaseModel):
    """List of annealing proposals"""
    proposals: List[AnnealingProposal]
    count: int


class AnnealingProposalReviewRequest(BaseModel):
    """Request to approve or reject a proposal"""
    status: str = Field(..., pattern="^(approved|rejected)$")
    notes: Optional[str] = None


class AnnealingCycleResult(BaseModel):
    """Result summary from a annealing cycle"""
    proposals_generated: int = 0
    demotion_candidates: int = 0
    promotion_candidates: int = 0
    scores_updated: int = 0
    centroids_updated: int = 0
    edges_created: int = 0
    edges_deleted: int = 0
    cycle_epoch: int = 0
    dry_run: bool = False


class AnnealingStatus(BaseModel):
    """Health, configuration, and schedule of the annealing loop (ADR-703).

    Read-only insight surface for the ontology lifecycle admin panel. The
    annealing loop runs autonomously by default — this exposes enough state
    for an operator to understand what it is doing without dropping to the CLI.
    """
    enabled: bool
    automation_level: str
    options: Dict[str, str]
    schedule_cron: Optional[str] = None
    schedule_enabled: bool = False
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    next_run: Optional[datetime] = None
    current_epoch: int = 0
    last_annealing_epoch: int = 0
    epoch_interval: int = 5
    ontology_count: int = 0
    proposals_by_status: Dict[str, int] = {}


class PressureControlRecommendation(BaseModel):
    """Per-control delta from current → Bezier-recommended (ADR-206 §Phase 3)."""
    current: int
    recommended: int
    delta: int


class EcologicalPressureSnapshot(BaseModel):
    """
    One ecological-pressure read-out (#249, ADR-206 §Phase 3).

    Mirrors the dict returned by `AnnealingManager._get_ecological_snapshot`
    plus a `recorded_at` / `epoch` pair when loaded from history. The web
    admin tab reads `/annealing/pressure` (latest row) for the current-
    state Bezier panel and `/annealing/pressure/history` for the trend
    chart.
    """
    epoch: int
    total_ontologies: int
    total_concepts: int
    avg_concepts_per_ontology: float
    pressure_score: float
    pressure_zone: str
    pressure_recommendation: Dict[str, PressureControlRecommendation] = {}
    recorded_at: Optional[datetime] = None


class EcologicalPressureCurve(BaseModel):
    """
    Static metadata describing the Bezier curve the system uses for
    pressure mapping. Lets the UI draw the curve without hardcoding the
    control points (so a future operator can tune them server-side and
    the UI follows).
    """
    profile: str
    comfort_min: float
    comfort_max: float
    emergency_threshold: float
    bezier_p1: List[float]
    bezier_p2: List[float]


class EcologicalPressureResponse(BaseModel):
    """Payload for GET /ontology/annealing/pressure."""
    current: EcologicalPressureSnapshot
    curve: EcologicalPressureCurve


class EcologicalPressureHistoryResponse(BaseModel):
    """Payload for GET /ontology/annealing/pressure/history."""
    snapshots: List[EcologicalPressureSnapshot]
    count: int
    curve: EcologicalPressureCurve


# =========================================================================
# ADR-200 Phase 5: Ontology-to-Ontology Edges
# =========================================================================

class OntologyEdge(BaseModel):
    """An edge between two ontology nodes (OVERLAPS, SPECIALIZES, GENERALIZES)"""
    from_ontology: str
    to_ontology: str
    edge_type: str
    score: float = 0.0
    shared_concept_count: int = 0
    computed_at_epoch: int = 0
    source: str = ""
    direction: str = ""


class OntologyEdgesResponse(BaseModel):
    """Ontology-to-ontology edges for an ontology"""
    ontology: str
    count: int
    edges: List[OntologyEdge]


class OntologyEdgeCreateRequest(BaseModel):
    """Request to create a manual ontology-to-ontology edge"""
    to_ontology: str = Field(..., description="Target ontology name")
    edge_type: str = Field(..., pattern="^(OVERLAPS|SPECIALIZES|GENERALIZES)$",
                           description="Edge type: OVERLAPS, SPECIALIZES, or GENERALIZES")
    score: float = Field(1.0, ge=0.0, le=1.0, description="Edge weight (0-1)")
    shared_concept_count: int = Field(0, ge=0, description="Number of shared concepts")
