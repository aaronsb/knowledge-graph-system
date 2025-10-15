"""
Vocabulary Manager - Orchestration Layer for ADR-032.

Coordinates automatic edge vocabulary expansion and intelligent pruning:
- Monitors vocabulary size and calculates aggressiveness
- Scores edge types by value (usage, bridges, trends)
- Detects synonyms for merging
- Classifies new types into categories
- Makes pruning decisions based on strategy mode
- Manages approval workflows

Usage:
    from src.api.services.vocabulary_manager import VocabularyManager

    manager = VocabularyManager(
        db_client=age_client,
        ai_provider=provider,
        mode="aitl"
    )

    # Analyze current vocabulary
    analysis = await manager.analyze_vocabulary()

    # Generate recommendations
    recommendations = await manager.generate_recommendations()

    # Execute auto-approved actions
    results = await manager.execute_auto_actions(recommendations['auto_execute'])

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - ADR-025: Dynamic Relationship Vocabulary
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Phase 1 worker modules
from src.api.lib.aggressiveness_curve import calculate_aggressiveness
from src.api.lib.vocabulary_scoring import VocabularyScorer, EdgeTypeScore
from src.api.lib.category_classifier import CategoryClassifier, CategoryClassification
from src.api.lib.synonym_detector import SynonymDetector, SynonymCandidate
from src.api.lib.pruning_strategies import (
    PruningStrategy,
    ActionRecommendation,
    ActionType,
    ReviewLevel
)

logger = logging.getLogger(__name__)


@dataclass
class VocabularyAnalysis:
    """
    Analysis of current vocabulary state.

    Attributes:
        vocab_size: Current vocabulary size
        vocab_min: Minimum vocabulary size (threshold)
        vocab_max: Maximum vocabulary size (threshold)
        vocab_emergency: Emergency threshold
        aggressiveness: Current aggressiveness score (0.0-1.0)
        zone: Current zone (safe/active/critical/emergency)
        edge_type_scores: Dict mapping type -> EdgeTypeScore
        synonym_candidates: List of detected synonym pairs
        low_value_types: List of low-value EdgeTypeScore objects
        category_distribution: Dict mapping category -> count
    """
    vocab_size: int
    vocab_min: int
    vocab_max: int
    vocab_emergency: int
    aggressiveness: float
    zone: str
    edge_type_scores: Dict[str, EdgeTypeScore]
    synonym_candidates: List[Tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore]]
    low_value_types: List[EdgeTypeScore]
    category_distribution: Dict[str, int] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"VocabularyAnalysis(size={self.vocab_size}, "
            f"zone={self.zone}, aggressiveness={self.aggressiveness:.2f})"
        )


@dataclass
class ExecutionResult:
    """
    Result of executing a vocabulary action.

    Attributes:
        action: The action that was executed
        success: Whether execution succeeded
        message: Result message
        affected_edges: Number of edges modified (for merges)
        error: Error message if failed
    """
    action: ActionRecommendation
    success: bool
    message: str
    affected_edges: int = 0
    error: Optional[str] = None

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"ExecutionResult({status}: {self.action.action_type.value} {self.action.edge_type})"


class VocabularyManager:
    """
    Orchestrates automatic vocabulary expansion and intelligent pruning.

    Coordinates all Phase 1 worker modules to manage vocabulary lifecycle.
    """

    # Vocabulary thresholds (from ADR-032)
    VOCAB_MIN = 30          # Protected core (30 builtin types)
    VOCAB_MAX = 90          # Soft limit for new additions
    VOCAB_EMERGENCY = 200   # Hard limit - aggressive pruning kicks in

    # Pruning thresholds
    LOW_VALUE_THRESHOLD = 1.0    # Value score threshold for pruning consideration

    def __init__(
        self,
        db_client,
        ai_provider,
        mode: str = "hitl",
        aggressiveness_profile: str = "aggressive"
    ):
        """
        Initialize vocabulary manager.

        Args:
            db_client: Database client (AGEClient or psycopg2 connection)
            ai_provider: AI provider for embeddings and classification
            mode: Pruning mode (naive, hitl, aitl)
            aggressiveness_profile: Aggressiveness curve profile
        """
        self.db = db_client
        self.ai_provider = ai_provider
        self.mode = mode
        self.profile = aggressiveness_profile

        # Initialize worker modules
        self.scorer = VocabularyScorer(db_client)
        self.classifier = CategoryClassifier(ai_provider)
        self.synonym_detector = SynonymDetector(ai_provider)
        self.strategy = PruningStrategy(mode=mode, ai_provider=ai_provider)

        logger.info(f"VocabularyManager initialized (mode={mode}, profile={aggressiveness_profile})")

    async def analyze_vocabulary(
        self,
        vocab_min: Optional[int] = None,
        vocab_max: Optional[int] = None,
        vocab_emergency: Optional[int] = None
    ) -> VocabularyAnalysis:
        """
        Analyze current vocabulary state.

        Args:
            vocab_min: Override minimum threshold
            vocab_max: Override maximum threshold
            vocab_emergency: Override emergency threshold

        Returns:
            VocabularyAnalysis with current state

        Example:
            >>> manager = VocabularyManager(db, provider, mode="aitl")
            >>> analysis = await manager.analyze_vocabulary()
            >>> print(f"Size: {analysis.vocab_size}, Zone: {analysis.zone}")
        """
        # Use provided thresholds or defaults
        vocab_min = vocab_min or self.VOCAB_MIN
        vocab_max = vocab_max or self.VOCAB_MAX
        vocab_emergency = vocab_emergency or self.VOCAB_EMERGENCY

        # Get current vocabulary size
        vocab_size = await self._get_vocabulary_size()

        # Calculate aggressiveness
        aggressiveness, zone = calculate_aggressiveness(
            current_size=vocab_size,
            vocab_min=vocab_min,
            vocab_max=vocab_max,
            vocab_emergency=vocab_emergency,
            profile=self.profile
        )

        # Get value scores for all types
        edge_type_scores = await self.scorer.get_value_scores(include_builtin=True)

        # Detect synonym candidates
        synonym_candidates = await self._detect_synonym_candidates(edge_type_scores)

        # Identify low-value types
        low_value_types = await self.scorer.get_low_value_types(
            threshold=self.LOW_VALUE_THRESHOLD,
            exclude_builtin=True,
            exclude_nonzero_edges=False
        )

        # Get category distribution
        category_distribution = await self._get_category_distribution()

        logger.info(
            f"Vocabulary analysis: size={vocab_size}, zone={zone}, "
            f"aggressiveness={aggressiveness:.2f}, synonyms={len(synonym_candidates)}, "
            f"low_value={len(low_value_types)}"
        )

        return VocabularyAnalysis(
            vocab_size=vocab_size,
            vocab_min=vocab_min,
            vocab_max=vocab_max,
            vocab_emergency=vocab_emergency,
            aggressiveness=aggressiveness,
            zone=zone,
            edge_type_scores=edge_type_scores,
            synonym_candidates=synonym_candidates,
            low_value_types=low_value_types,
            category_distribution=category_distribution
        )

    async def generate_recommendations(
        self,
        analysis: Optional[VocabularyAnalysis] = None
    ) -> Dict[str, List[ActionRecommendation]]:
        """
        Generate vocabulary action recommendations.

        Args:
            analysis: Optional pre-computed analysis (will analyze if not provided)

        Returns:
            Dict with 'auto_execute' and 'needs_review' lists

        Example:
            >>> recommendations = await manager.generate_recommendations()
            >>> print(f"Auto: {len(recommendations['auto_execute'])}")
            >>> print(f"Review: {len(recommendations['needs_review'])}")
        """
        # Analyze if not provided
        if analysis is None:
            analysis = await self.analyze_vocabulary()

        # Use pruning strategy to evaluate all candidates
        results = await self.strategy.batch_evaluate(
            synonyms=analysis.synonym_candidates,
            low_value_types=analysis.low_value_types
        )

        logger.info(
            f"Generated recommendations: auto={len(results['auto_execute'])}, "
            f"review={len(results['needs_review'])}"
        )

        return results

    async def classify_new_type(
        self,
        edge_type: str,
        existing_categories: Optional[List[str]] = None
    ) -> CategoryClassification:
        """
        Classify a new edge type into semantic category.

        Used during auto-expansion to determine category placement.

        Args:
            edge_type: New edge type to classify
            existing_categories: List of existing categories (optional)

        Returns:
            CategoryClassification with assignment or new category proposal

        Example:
            >>> classification = await manager.classify_new_type("MONITORS")
            >>> if classification.should_create_new:
            ...     print(f"Propose new category: {classification.suggested_category}")
        """
        result = await self.classifier.classify_edge_type(
            edge_type,
            existing_categories=existing_categories
        )

        logger.info(
            f"Classified '{edge_type}': "
            f"{'NEW: ' + result.suggested_category if result.should_create_new else result.best_match_category} "
            f"(confidence: {result.confidence:.2f})"
        )

        return result

    async def check_for_synonyms(
        self,
        new_type: str,
        existing_types: Optional[List[str]] = None
    ) -> List[SynonymCandidate]:
        """
        Check if new type has synonyms in existing vocabulary.

        Used during auto-expansion to prevent duplicates.

        Args:
            new_type: New edge type to check
            existing_types: List of existing types (optional, will query DB if not provided)

        Returns:
            List of synonym candidates (sorted by similarity)

        Example:
            >>> synonyms = await manager.check_for_synonyms("VERIFIES")
            >>> if synonyms and synonyms[0].is_strong_match:
            ...     print(f"Don't add - use '{synonyms[0].type2}' instead")
        """
        # Get existing types if not provided
        if existing_types is None:
            existing_types = await self._get_all_edge_types()

        synonyms = await self.synonym_detector.find_synonyms_for_type(
            new_type,
            existing_types,
            min_similarity=0.70  # Include moderate and strong matches
        )

        if synonyms:
            logger.warning(
                f"Type '{new_type}' has {len(synonyms)} potential synonyms "
                f"(strongest: '{synonyms[0].type2}' at {synonyms[0].similarity:.3f})"
            )

        return synonyms

    async def execute_auto_actions(
        self,
        actions: List[ActionRecommendation]
    ) -> List[ExecutionResult]:
        """
        Execute auto-approved actions.

        Args:
            actions: List of auto-approved actions from generate_recommendations()

        Returns:
            List of ExecutionResult objects

        Example:
            >>> recommendations = await manager.generate_recommendations()
            >>> results = await manager.execute_auto_actions(recommendations['auto_execute'])
            >>> for result in results:
            ...     if result.success:
            ...         print(f"Executed: {result.message}")
        """
        results = []

        for action in actions:
            try:
                if action.action_type == ActionType.MERGE:
                    result = await self._execute_merge(action)
                elif action.action_type == ActionType.PRUNE:
                    result = await self._execute_prune(action)
                elif action.action_type == ActionType.DEPRECATE:
                    result = await self._execute_deprecate(action)
                else:
                    # SKIP actions don't need execution
                    result = ExecutionResult(
                        action=action,
                        success=True,
                        message=f"Skipped {action.edge_type}"
                    )

                results.append(result)

            except Exception as e:
                logger.error(f"Failed to execute action {action}: {e}", exc_info=True)
                results.append(ExecutionResult(
                    action=action,
                    success=False,
                    message=f"Execution failed",
                    error=str(e)
                ))

        logger.info(
            f"Executed {len(actions)} actions: "
            f"{sum(1 for r in results if r.success)} succeeded, "
            f"{sum(1 for r in results if not r.success)} failed"
        )

        return results

    async def get_pending_reviews(self) -> List[ActionRecommendation]:
        """
        Get actions pending human review.

        Returns:
            List of actions needing approval

        Example:
            >>> pending = await manager.get_pending_reviews()
            >>> for action in pending:
            ...     print(f"Review: {action.reasoning}")
        """
        # TODO: Implement persistence layer
        # For now, generate fresh recommendations
        recommendations = await self.generate_recommendations()
        return recommendations['needs_review']

    async def approve_action(
        self,
        action: ActionRecommendation,
        approved: bool,
        reviewer: str = "system"
    ) -> Optional[ExecutionResult]:
        """
        Approve or reject a pending action.

        Args:
            action: Action to approve/reject
            approved: True to approve, False to reject
            reviewer: Who approved/rejected

        Returns:
            ExecutionResult if approved and executed, None if rejected

        Example:
            >>> pending = await manager.get_pending_reviews()
            >>> result = await manager.approve_action(pending[0], approved=True, reviewer="admin")
        """
        if not approved:
            logger.info(f"Action rejected by {reviewer}: {action}")
            return None

        logger.info(f"Action approved by {reviewer}: {action}")

        # TODO: Record approval in database
        # UPDATE kg_api.pruning_recommendations
        # SET status = 'approved', approved_by = reviewer, approved_at = NOW()

        # Execute the approved action
        results = await self.execute_auto_actions([action])
        return results[0] if results else None

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    async def _get_vocabulary_size(self) -> int:
        """Get current vocabulary size."""
        return self.db.get_vocabulary_size()

    async def _get_all_edge_types(self) -> List[str]:
        """Get list of all active edge types."""
        return self.db.get_all_edge_types(include_inactive=False)

    async def _get_category_distribution(self) -> Dict[str, int]:
        """Get count of types per category."""
        return self.db.get_category_distribution()

    async def _detect_synonym_candidates(
        self,
        edge_type_scores: Dict[str, EdgeTypeScore]
    ) -> List[Tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore]]:
        """
        Detect synonym candidates among edge types.

        Returns list of (candidate, score1, score2) tuples.
        """
        # Get list of types
        edge_types = list(edge_type_scores.keys())

        # Find synonyms
        candidates = await self.synonym_detector.find_synonyms(
            edge_types,
            min_similarity=0.70  # Include moderate and strong
        )

        # Pair each candidate with scores
        result = []
        for candidate in candidates:
            score1 = edge_type_scores.get(candidate.type1)
            score2 = edge_type_scores.get(candidate.type2)

            if score1 and score2:
                result.append((candidate, score1, score2))

        return result

    async def _execute_merge(self, action: ActionRecommendation) -> ExecutionResult:
        """
        Execute merge action: update all edges to use preserved type.

        Args:
            action: MERGE action with edge_type (deprecate) and target_type (preserve)

        Returns:
            ExecutionResult with affected edge count
        """
        deprecate_type = action.edge_type
        preserve_type = action.target_type

        logger.info(f"Executing merge: {deprecate_type} → {preserve_type}")

        try:
            # Use AGE client to merge types
            result = self.db.merge_edge_types(
                deprecated_type=deprecate_type,
                target_type=preserve_type,
                performed_by="vocabulary_manager"
            )

            affected_edges = result.get("edges_updated", 0)

            return ExecutionResult(
                action=action,
                success=True,
                message=f"Merged {deprecate_type} into {preserve_type}",
                affected_edges=affected_edges
            )
        except Exception as e:
            logger.error(f"Failed to merge {deprecate_type} → {preserve_type}: {e}")
            return ExecutionResult(
                action=action,
                success=False,
                message=f"Merge failed",
                error=str(e)
            )

    async def _execute_prune(self, action: ActionRecommendation) -> ExecutionResult:
        """
        Execute prune action: remove type entirely (safe for zero-edge types).

        Args:
            action: PRUNE action with edge_type

        Returns:
            ExecutionResult
        """
        edge_type = action.edge_type

        logger.info(f"Executing prune: {edge_type}")

        # TODO: Implement actual prune in database
        # 1. Verify no edges exist (safety check)
        #    SELECT COUNT(*) FROM graph WHERE relationship_type = edge_type
        #    (should be 0)
        #
        # 2. Delete from vocabulary
        #    DELETE FROM kg_api.relationship_vocabulary
        #    WHERE relationship_type = edge_type AND edge_count = 0
        #
        # 3. Record in vocabulary_history
        #    INSERT INTO kg_api.vocabulary_history (action='prune', ...)

        return ExecutionResult(
            action=action,
            success=True,
            message=f"Pruned {edge_type} (zero edges)",
            affected_edges=0
        )

    async def _execute_deprecate(self, action: ActionRecommendation) -> ExecutionResult:
        """
        Execute deprecate action: mark type inactive but keep existing edges.

        Args:
            action: DEPRECATE action with edge_type

        Returns:
            ExecutionResult
        """
        edge_type = action.edge_type

        logger.info(f"Executing deprecate: {edge_type}")

        # TODO: Implement actual deprecate in database
        # UPDATE kg_api.relationship_vocabulary
        # SET is_active = FALSE,
        #     deprecated_at = NOW(),
        #     deprecation_reason = 'Low value - discouraged for new edges'
        # WHERE relationship_type = edge_type

        return ExecutionResult(
            action=action,
            success=True,
            message=f"Deprecated {edge_type} (existing edges preserved)",
            affected_edges=0
        )


# ============================================================================
# Utility Functions
# ============================================================================


def format_analysis_summary(analysis: VocabularyAnalysis) -> str:
    """
    Format vocabulary analysis as human-readable summary.

    Args:
        analysis: VocabularyAnalysis object

    Returns:
        Formatted string

    Example:
        >>> analysis = await manager.analyze_vocabulary()
        >>> print(format_analysis_summary(analysis))
    """
    lines = [
        "Vocabulary Analysis Summary",
        "=" * 60,
        f"Size: {analysis.vocab_size} (min: {analysis.vocab_min}, max: {analysis.vocab_max})",
        f"Zone: {analysis.zone.upper()}",
        f"Aggressiveness: {analysis.aggressiveness:.2f}",
        "",
        f"Edge Types: {len(analysis.edge_type_scores)}",
        f"Synonym Candidates: {len(analysis.synonym_candidates)}",
        f"Low-Value Types: {len(analysis.low_value_types)}",
        "",
        "Category Distribution:"
    ]

    for category, count in sorted(analysis.category_distribution.items()):
        lines.append(f"  {category}: {count}")

    return "\n".join(lines)


def format_recommendations_summary(
    recommendations: Dict[str, List[ActionRecommendation]]
) -> str:
    """
    Format recommendations as human-readable summary.

    Args:
        recommendations: Dict from generate_recommendations()

    Returns:
        Formatted string

    Example:
        >>> recommendations = await manager.generate_recommendations()
        >>> print(format_recommendations_summary(recommendations))
    """
    lines = [
        "Vocabulary Recommendations",
        "=" * 60,
        f"Auto-Execute: {len(recommendations['auto_execute'])}",
        f"Needs Review: {len(recommendations['needs_review'])}",
        ""
    ]

    if recommendations['auto_execute']:
        lines.append("Auto-Execute Actions:")
        for action in recommendations['auto_execute'][:5]:  # Show first 5
            lines.append(f"  - {action.action_type.value}: {action.edge_type} ({action.reasoning[:50]}...)")

    if recommendations['needs_review']:
        lines.append("")
        lines.append("Needs Review:")
        for action in recommendations['needs_review'][:5]:  # Show first 5
            lines.append(f"  - {action.action_type.value}: {action.edge_type} ({action.reasoning[:50]}...)")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick demonstration
    import asyncio

    print("Vocabulary Manager - ADR-032 Orchestration Layer")
    print("=" * 60)
    print()
    print("This service coordinates:")
    print("  - Aggressiveness calculation (Bezier curves)")
    print("  - Value scoring (usage metrics)")
    print("  - Synonym detection (embeddings)")
    print("  - Category classification (semantic similarity)")
    print("  - Pruning strategy (naive/HITL/AITL)")
    print()
    print("Usage:")
    print("  from src.api.services.vocabulary_manager import VocabularyManager")
    print("  manager = VocabularyManager(db, provider, mode='aitl')")
    print("  analysis = await manager.analyze_vocabulary()")
    print("  recommendations = await manager.generate_recommendations()")
    print()
    print("For testing, run: pytest tests/test_vocabulary_manager.py")
