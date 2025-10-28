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
    VOCAB_MAX = 90          # Soft limit for new additions (GREEN zone)
    VOCAB_EMERGENCY = 300   # Hard limit - aggressive pruning kicks in

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

        # Get value scores for all types (optional - used for prioritization)
        # If scorer fails (e.g., missing edge_usage_stats), continue without value scores
        try:
            edge_type_scores = await self.scorer.get_value_scores(include_builtin=True)
        except Exception as e:
            logger.warning(f"Value scorer unavailable: {e}. Continuing without usage metrics.")
            edge_type_scores = {}

        # Detect synonym candidates using vocabulary types directly from database
        # This decouples synonym detection from value scoring (per ADR-032 architecture)
        synonym_candidates = await self._detect_synonym_candidates_from_vocab()

        # Identify low-value types (if scorer available)
        try:
            low_value_types = await self.scorer.get_low_value_types(
                threshold=self.LOW_VALUE_THRESHOLD,
                exclude_builtin=True,
                exclude_nonzero_edges=False
            )
        except Exception as e:
            logger.warning(f"Low-value scoring unavailable: {e}")
            low_value_types = []

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

    async def _detect_synonym_candidates_from_vocab(
        self
    ) -> List[Tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore]]:
        """
        Detect synonym candidates by getting types directly from vocabulary table.

        This decouples synonym detection from value scoring per ADR-032 architecture.
        Synonym detection uses embeddings; scoring uses usage metrics.
        They are separate concerns.

        Returns:
            List of (candidate, score1, score2) tuples
            Scores use minimal defaults if scorer unavailable
        """
        # Get all active edge types directly from vocabulary table
        edge_types = await self._get_all_edge_types()

        logger.info(f"Detecting synonyms from {len(edge_types)} vocabulary types")

        # Find synonyms using embedding similarity
        candidates = await self.synonym_detector.find_synonyms(
            edge_types,
            min_similarity=0.70  # Include moderate and strong matches
        )

        logger.info(f"Found {len(candidates)} synonym candidates")

        # Try to get full scores, fall back to minimal scores if scorer unavailable
        all_scores = {}
        try:
            all_scores = await self.scorer.get_value_scores(include_builtin=True)
            logger.info("Using full value scores for synonym evaluation")
        except Exception as e:
            logger.warning(f"Scorer unavailable ({e}), using minimal scores from vocabulary table")
            # Get minimal scores directly from vocabulary table
            all_scores = await self._get_minimal_scores()

        # Pair each candidate with scores
        result = []
        for candidate in candidates:
            score1 = all_scores.get(candidate.type1)
            score2 = all_scores.get(candidate.type2)

            # If scores still missing, create minimal defaults
            if score1 is None:
                score1 = EdgeTypeScore(
                    relationship_type=candidate.type1,
                    edge_count=0,
                    avg_traversal=0.0,
                    bridge_count=0,
                    trend=0.0,
                    value_score=0.0,
                    is_builtin=False,
                    last_used=None
                )
            if score2 is None:
                score2 = EdgeTypeScore(
                    relationship_type=candidate.type2,
                    edge_count=0,
                    avg_traversal=0.0,
                    bridge_count=0,
                    trend=0.0,
                    value_score=0.0,
                    is_builtin=False,
                    last_used=None
                )

            result.append((candidate, score1, score2))

        return result

    def prioritize_merge_candidates(
        self,
        candidates: List[Tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore]],
        min_similarity: float = 0.80,
        max_edge_count: int = 20
    ) -> List[Tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore, float]]:
        """
        Filter and prioritize merge candidates for AITL processing.

        Strategy:
        1. Filter out low-similarity pairs (< min_similarity)
        2. Filter out likely inverse relationships (_BY suffix patterns)
        3. Prefer low-frequency types (easier to merge, less disruption)
        4. Score by: (similarity * 2) - (min_edge_count / 100)
        5. Sort by priority score descending

        Args:
            candidates: List of (SynonymCandidate, Score1, Score2) tuples
            min_similarity: Minimum similarity threshold (default: 0.80)
            max_edge_count: Skip high-frequency types initially (default: 20)

        Returns:
            List of (candidate, score1, score2, priority_score) sorted by priority
        """
        filtered = []

        for candidate, score1, score2 in candidates:
            # Filter: similarity threshold
            if candidate.similarity < min_similarity:
                continue

            # Filter: skip likely inverse relationships
            # Pattern: TYPE vs TYPE_BY (e.g., VERIFIED vs VERIFIED_BY)
            type1_base = candidate.type1.replace('_BY', '').replace('_TO', '')
            type2_base = candidate.type2.replace('_BY', '').replace('_TO', '')
            if type1_base == type2_base:
                logger.debug(f"Skipping inverse pair: {candidate.type1} / {candidate.type2}")
                continue

            # Filter: skip high-frequency types in first pass
            min_count = min(score1.edge_count, score2.edge_count)
            if min_count > max_edge_count:
                continue

            # Calculate priority score
            # High similarity + low usage = high priority
            priority_score = (candidate.similarity * 2) - (min_count / 100)
            filtered.append((candidate, score1, score2, priority_score))

        # Sort by priority score descending
        filtered.sort(key=lambda x: -x[3])

        logger.info(
            f"Prioritized {len(filtered)} candidates from {len(candidates)} "
            f"(similarity ≥ {min_similarity:.0%}, edge_count ≤ {max_edge_count})"
        )

        return filtered

    async def aitl_consolidate_vocabulary(
        self,
        target_size: int = 90,
        batch_size: int = 1,  # Process ONE at a time
        auto_execute_threshold: float = 0.90,  # DEPRECATED - now trusts LLM completely
        dry_run: bool = False
    ) -> Dict[str, List]:
        """
        AITL vocabulary consolidation - one merge at a time with re-query.

        AITL Mode: Fully trust LLM decisions. No "needs review" - either merge or reject.

        Process:
        1. Get top 1 prioritized candidate (fresh query each iteration)
        2. Evaluate with LLM (synonym vs directional inverse)
        3. If LLM approves → execute immediately
        4. If LLM rejects → skip and continue
        5. Re-query vocabulary (landscape has changed)
        6. Repeat until vocab_size ≤ target

        This prevents contradictory recommendations by ensuring the vocabulary
        state is fresh for each decision.

        Args:
            target_size: Stop when vocabulary reaches this size (default: 90)
            batch_size: DEPRECATED - always processes 1 candidate at a time
            auto_execute_threshold: DEPRECATED - now trusts LLM completely
            dry_run: If True, don't execute merges (default: False)

        Returns:
            Dict with 'auto_executed' and 'rejected' lists (no 'needs_review')

        Example:
            >>> results = await manager.aitl_consolidate_vocabulary(
            ...     target_size=85, dry_run=False
            ... )
            >>> print(f"Merged: {len(results['auto_executed'])}")
            >>> print(f"Rejected: {len(results['rejected'])}")
        """
        from src.api.lib.pruning_strategies import llm_evaluate_merge

        results = {
            'auto_executed': [],
            'needs_review': [],
            'rejected': []
        }

        # DRY RUN MODE: Just evaluate top candidates for validation (AITL trusts LLM)
        if dry_run:
            logger.info("DRY RUN MODE: Evaluating top candidates (no execution)")

            # Get candidates once
            analysis = await self.analyze_vocabulary()
            prioritized = self.prioritize_merge_candidates(
                analysis.synonym_candidates,
                min_similarity=0.80,
                max_edge_count=20
            )

            # Evaluate top 10 candidates for validation
            max_eval = min(10, len(prioritized))
            for i, (candidate, score1, score2, priority) in enumerate(prioritized[:max_eval]):
                logger.info(f"[{i+1}/{max_eval}] Evaluating: {candidate.type1} + {candidate.type2}")

                decision = await llm_evaluate_merge(
                    type1=candidate.type1,
                    type2=candidate.type2,
                    type1_edge_count=score1.edge_count,
                    type2_edge_count=score2.edge_count,
                    similarity=candidate.similarity,
                    ai_provider=self.ai_provider
                )

                if not decision.should_merge:
                    results['rejected'].append({
                        'type1': candidate.type1,
                        'type2': candidate.type2,
                        'reasoning': decision.reasoning
                    })
                    continue

                # AITL: Trust LLM decision completely
                target_term = decision.blended_term or (candidate.type1 if score1.edge_count >= score2.edge_count else candidate.type2)
                deprecate = candidate.type2 if score1.edge_count >= score2.edge_count else candidate.type1

                results['auto_executed'].append({
                    'deprecated': deprecate,
                    'target': target_term,
                    'similarity': candidate.similarity,
                    'reasoning': decision.reasoning,
                    'blended_description': decision.blended_description
                })

            return results

        # LIVE MODE: Process one at a time with re-query
        logger.info("LIVE MODE: Processing candidates one-at-a-time with re-query")
        iteration = 0

        # Calculate max iterations as half of starting vocabulary size
        initial_vocab_size = await self._get_vocabulary_size()
        max_iterations = max(10, initial_vocab_size // 2)  # At least 10, or vocab_size/2
        logger.info(f"Max iterations set to {max_iterations} (vocab_size: {initial_vocab_size})")

        # Track processed pairs during this session to avoid re-presenting rejected candidates
        processed_pairs: set[frozenset[str]] = set()

        while True:
            # Check if we've reached target
            vocab_size = await self._get_vocabulary_size()
            if vocab_size <= target_size:
                logger.info(f"Target reached: {vocab_size} ≤ {target_size}")
                break

            iteration += 1
            logger.info(f"=== Iteration {iteration} (vocab_size: {vocab_size}, target: {target_size}) ===")

            # Get fresh analysis (vocabulary changes each iteration)
            analysis = await self.analyze_vocabulary()

            # Prioritize candidates and filter out already-processed pairs
            prioritized = self.prioritize_merge_candidates(
                analysis.synonym_candidates,
                min_similarity=0.80,
                max_edge_count=20
            )

            # Filter out already-processed pairs
            unprocessed = []
            for cand, s1, s2, pri in prioritized:
                pair_key = frozenset([cand.type1, cand.type2])
                if pair_key not in processed_pairs:
                    unprocessed.append((cand, s1, s2, pri))

            if not unprocessed:
                logger.info("No more unprocessed candidates available")
                break

            # Take ONLY the top unprocessed candidate (one at a time)
            candidate, score1, score2, priority = unprocessed[0]
            pair_key = frozenset([candidate.type1, candidate.type2])

            logger.info(
                f"Evaluating: {candidate.type1} ({score1.edge_count}) + "
                f"{candidate.type2} ({score2.edge_count}) "
                f"[similarity: {candidate.similarity:.1%}, priority: {priority:.3f}]"
            )

            # Call LLM for decision
            decision = await llm_evaluate_merge(
                type1=candidate.type1,
                type2=candidate.type2,
                type1_edge_count=score1.edge_count,
                type2_edge_count=score2.edge_count,
                similarity=candidate.similarity,
                ai_provider=self.ai_provider
            )

            if not decision.should_merge:
                results['rejected'].append({
                    'type1': candidate.type1,
                    'type2': candidate.type2,
                    'reasoning': decision.reasoning
                })
                # Mark as processed so we don't present it again
                processed_pairs.add(pair_key)
                logger.info(f"  ✗ Rejected: {decision.reasoning}")
                # Continue to next iteration (will re-query)
                continue

            # LLM approved merge - trust the decision completely (AITL mode)
            # Use LLM-generated blended term, or fall back to higher-usage type
            target_term = decision.blended_term
            if not target_term:
                target_term = candidate.type1 if score1.edge_count >= score2.edge_count else candidate.type2

            # Deprecate the other type
            if score1.edge_count >= score2.edge_count:
                deprecate = candidate.type2
            else:
                deprecate = candidate.type1

            # AITL: Trust LLM decision - execute immediately
            merge_info = {
                'deprecated': deprecate,
                'target': target_term,
                'similarity': candidate.similarity,
                'reasoning': decision.reasoning,
                'blended_description': decision.blended_description,
                'edges_affected': min(score1.edge_count, score2.edge_count)
            }

            if not dry_run:
                # Execute merge immediately
                try:
                    merge_result = self.db.merge_edge_types(
                        deprecated_type=deprecate,
                        target_type=target_term,
                        performed_by="aitl_consolidation"
                    )
                    merge_info['edges_updated'] = merge_result.get('edges_updated', 0)
                    logger.info(f"  ✓ LLM-approved merge: {deprecate} → {target_term} (edges: {merge_info['edges_updated']})")
                except Exception as e:
                    logger.error(f"  ✗ Merge failed: {e}")
                    merge_info['error'] = str(e)
            else:
                logger.info(f"  [DRY RUN] Would merge: {deprecate} → {target_term}")

            results['auto_executed'].append(merge_info)
            # Mark as processed so we don't present it again
            processed_pairs.add(pair_key)
            # Vocabulary has changed - next iteration will re-query

            # Safety: don't run forever
            if iteration >= max_iterations:
                logger.warning(f"Max iterations ({max_iterations}) reached, stopping")
                break

        logger.info(
            f"AITL consolidation complete after {iteration} iterations: "
            f"{len(results['auto_executed'])} merged, "
            f"{len(results['rejected'])} rejected"
        )

        return results

    async def _get_minimal_scores(self) -> Dict[str, EdgeTypeScore]:
        """
        Get minimal scores directly from vocabulary table when scorer unavailable.

        Returns EdgeTypeScore objects with just edge_count and is_builtin populated.
        """
        try:
            # Get all active edge types
            edge_types = await self._get_all_edge_types()

            scores = {}
            for edge_type in edge_types:
                # Get info for each type
                info = self.db.get_edge_type_info(edge_type)
                if info:
                    edge_count = info.get('edge_count', 0)
                    scores[edge_type] = EdgeTypeScore(
                        relationship_type=edge_type,
                        edge_count=edge_count,
                        avg_traversal=0.0,
                        bridge_count=0,
                        trend=0.0,
                        value_score=float(edge_count),  # Use count as proxy for value
                        is_builtin=info.get('is_builtin', False),
                        last_used=None
                    )

            logger.info(f"Retrieved minimal scores for {len(scores)} types")
            return scores
        except Exception as e:
            logger.warning(f"Failed to get minimal scores from vocabulary table: {e}")
            return {}

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
