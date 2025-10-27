"""Pydantic models for vocabulary management operations (ADR-032)"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class ActionTypeEnum(str, Enum):
    """Type of vocabulary action"""
    merge = "merge"
    prune = "prune"
    deprecate = "deprecate"
    skip = "skip"


class ReviewLevelEnum(str, Enum):
    """Required review level for action"""
    none = "none"
    ai = "ai"
    human = "human"


class PruningModeEnum(str, Enum):
    """Pruning decision mode"""
    naive = "naive"
    hitl = "hitl"
    aitl = "aitl"


class ZoneEnum(str, Enum):
    """Aggressiveness zone"""
    comfort = "comfort"
    watch = "watch"
    merge = "merge"
    mixed = "mixed"
    emergency = "emergency"
    block = "block"


# =============================================================================
# Edge Type Models
# =============================================================================

class EdgeTypeInfo(BaseModel):
    """Information about an edge type"""
    relationship_type: str
    category: str
    description: Optional[str] = None
    is_builtin: bool
    is_active: bool
    added_by: Optional[str] = None
    added_at: Optional[datetime] = None
    usage_count: Optional[int] = None
    edge_count: Optional[int] = None
    avg_traversal: Optional[float] = None
    last_used: Optional[datetime] = None
    value_score: Optional[float] = None
    # ADR-047: Probabilistic category assignment
    category_source: Optional[str] = None  # 'builtin' or 'computed'
    category_confidence: Optional[float] = None  # 0.0-1.0
    category_scores: Optional[Dict[str, float]] = None  # Full category breakdown
    category_ambiguous: Optional[bool] = None  # True if runner-up > 0.70
    # ADR-049: LLM-determined direction semantics
    direction_semantics: Optional[str] = None  # 'outward', 'inward', 'bidirectional', or None


class AddEdgeTypeRequest(BaseModel):
    """Request to manually add edge type"""
    relationship_type: str = Field(..., min_length=3, max_length=50)
    category: str
    description: Optional[str] = None
    is_builtin: bool = False


class EdgeTypeListResponse(BaseModel):
    """List of edge types with statistics"""
    total: int
    active: int
    builtin: int
    custom: int
    types: List[EdgeTypeInfo]


# =============================================================================
# Vocabulary Status Models
# =============================================================================

class VocabularyStatusResponse(BaseModel):
    """Current vocabulary status"""
    vocab_size: int
    vocab_min: int
    vocab_max: int
    vocab_emergency: int
    aggressiveness: float
    zone: ZoneEnum
    builtin_types: int
    custom_types: int
    categories: int
    profile: str


# =============================================================================
# Recommendation Models
# =============================================================================

class ActionRecommendationResponse(BaseModel):
    """Vocabulary action recommendation"""
    id: Optional[str] = None  # For DB persistence
    action_type: ActionTypeEnum
    edge_type: str
    target_type: Optional[str] = None
    review_level: ReviewLevelEnum
    should_execute: bool
    needs_review: bool
    reasoning: str
    metadata: Optional[Dict[str, Any]] = None


class RecommendationsResponse(BaseModel):
    """Generated recommendations"""
    vocab_size: int
    zone: ZoneEnum
    aggressiveness: float
    auto_execute: List[ActionRecommendationResponse]
    needs_review: List[ActionRecommendationResponse]
    generated_at: datetime = Field(default_factory=datetime.now)


class ApproveRecommendationRequest(BaseModel):
    """Approve or reject recommendation"""
    approved: bool
    reviewer: str
    notes: Optional[str] = None


class ExecutionResultResponse(BaseModel):
    """Result of executing an action"""
    success: bool
    message: str
    affected_edges: int = 0
    error: Optional[str] = None


# =============================================================================
# Analysis Models
# =============================================================================

class EdgeTypeScoreResponse(BaseModel):
    """Value score for an edge type"""
    relationship_type: str
    edge_count: int
    avg_traversal: float
    bridge_count: int
    trend: float
    value_score: float
    is_builtin: bool
    last_used: Optional[datetime] = None


class SynonymCandidateResponse(BaseModel):
    """Synonym candidate pair"""
    type1: str
    type2: str
    similarity: float
    strength: str  # "strong", "moderate", "weak"
    is_strong_match: bool
    needs_review: bool
    reasoning: str


class VocabularyAnalysisResponse(BaseModel):
    """Detailed vocabulary analysis"""
    vocab_size: int
    vocab_min: int
    vocab_max: int
    vocab_emergency: int
    aggressiveness: float
    zone: ZoneEnum
    edge_type_scores: List[EdgeTypeScoreResponse]
    synonym_candidates: List[SynonymCandidateResponse]
    low_value_types: List[EdgeTypeScoreResponse]
    category_distribution: Dict[str, int]


# =============================================================================
# Configuration Models
# =============================================================================

class VocabularyConfigResponse(BaseModel):
    """Vocabulary configuration"""
    vocab_min: int
    vocab_max: int
    vocab_emergency: int
    pruning_mode: PruningModeEnum
    aggressiveness_profile: str
    category_min: int = 8
    category_max: int = 15
    auto_expand_enabled: bool = False
    synonym_threshold_strong: float = 0.90
    synonym_threshold_moderate: float = 0.70
    low_value_threshold: float = 1.0
    embedding_model: str = "text-embedding-ada-002"


class UpdateConfigRequest(BaseModel):
    """Update vocabulary configuration"""
    vocab_min: Optional[int] = None
    vocab_max: Optional[int] = None
    vocab_emergency: Optional[int] = None
    pruning_mode: Optional[PruningModeEnum] = None
    aggressiveness_profile: Optional[str] = None
    auto_expand_enabled: Optional[bool] = None
    synonym_threshold_strong: Optional[float] = None
    synonym_threshold_moderate: Optional[float] = None
    low_value_threshold: Optional[float] = None


# =============================================================================
# History Models
# =============================================================================

class VocabularyHistoryEntry(BaseModel):
    """Vocabulary change history entry"""
    id: int
    relationship_type: str
    action: str  # 'added', 'merged', 'pruned', 'deprecated', 'reactivated'
    performed_by: str
    performed_at: datetime
    target_type: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    aggressiveness: Optional[float] = None
    zone: Optional[str] = None
    vocab_size_before: Optional[int] = None
    vocab_size_after: Optional[int] = None


class VocabularyHistoryResponse(BaseModel):
    """History of vocabulary changes"""
    total: int
    entries: List[VocabularyHistoryEntry]


# =============================================================================
# Merge/Restore Models
# =============================================================================

class MergeEdgeTypesRequest(BaseModel):
    """Request to merge edge types"""
    deprecated_type: str
    target_type: str
    performed_by: str
    reason: Optional[str] = None


class MergeEdgeTypesResponse(BaseModel):
    """Result of merging edge types"""
    success: bool
    deprecated_type: str
    target_type: str
    edges_updated: int
    vocab_updated: int
    message: str


class RestoreEdgeTypeRequest(BaseModel):
    """Request to restore pruned edge type"""
    relationship_type: str
    restored_by: str
    reason: Optional[str] = None


class RestoreEdgeTypeResponse(BaseModel):
    """Result of restoring edge type"""
    success: bool
    relationship_type: str
    message: str


# =============================================================================
# Embedding Models
# =============================================================================

class GenerateEmbeddingsRequest(BaseModel):
    """Request to generate vocabulary embeddings"""
    force_regenerate: bool = False
    only_missing: bool = True


class GenerateEmbeddingsResponse(BaseModel):
    """Result of generating vocabulary embeddings"""
    success: bool
    generated: int
    skipped: int
    failed: int
    message: str


# =============================================================================
# AITL Consolidation Models
# =============================================================================

class ConsolidateVocabularyRequest(BaseModel):
    """Request to run AITL vocabulary consolidation"""
    target_size: int = Field(90, ge=30, le=200, description="Target vocabulary size")
    batch_size: int = Field(1, ge=1, le=20, description="Number of candidates per iteration (usually 1)")
    auto_execute_threshold: float = Field(0.90, ge=0.0, le=1.0, description="Auto-execute merges above this similarity")
    dry_run: bool = Field(False, description="Evaluate candidates without executing merges")


class MergeResultInfo(BaseModel):
    """Information about a single merge result"""
    deprecated: str
    target: str
    similarity: float
    reasoning: str
    blended_description: Optional[str] = None
    edges_affected: Optional[int] = None
    edges_updated: Optional[int] = None
    error: Optional[str] = None


class ReviewInfo(BaseModel):
    """Information about a merge needing human review"""
    type1: str
    type2: str
    suggested_term: Optional[str] = None
    suggested_description: Optional[str] = None
    similarity: float
    reasoning: str
    edge_count1: Optional[int] = None
    edge_count2: Optional[int] = None


class RejectionInfo(BaseModel):
    """Information about a rejected merge"""
    type1: str
    type2: str
    reasoning: str


class ConsolidateVocabularyResponse(BaseModel):
    """Result of AITL vocabulary consolidation"""
    success: bool
    initial_size: int
    final_size: int
    size_reduction: int
    auto_executed: List[MergeResultInfo]
    needs_review: List[ReviewInfo]
    rejected: List[RejectionInfo]
    message: str


# =============================================================================
# Category Scoring (ADR-047)
# =============================================================================

class CategoryScoresResponse(BaseModel):
    """Category similarity scores for a relationship type"""
    relationship_type: str
    category: str
    confidence: float
    scores: Dict[str, float]  # category -> similarity score
    ambiguous: bool
    runner_up_category: Optional[str] = None
    runner_up_score: Optional[float] = None


class RefreshCategoriesRequest(BaseModel):
    """Request to refresh category assignments"""
    only_computed: bool = Field(
        default=True,
        description="Only refresh types with category_source='computed'"
    )


class RefreshCategoriesResponse(BaseModel):
    """Result of category refresh operation"""
    success: bool
    refreshed_count: int
    skipped_count: int
    failed_count: int
    assignments: List[CategoryScoresResponse]
    message: str
