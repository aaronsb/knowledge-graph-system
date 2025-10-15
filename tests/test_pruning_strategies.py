"""
Tests for pruning_strategies.py

Validates three-tier decision model (naive/HITL/AITL) for vocabulary management (ADR-032).
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.api.lib.pruning_strategies import (
    PruningStrategy,
    PruningMode,
    ActionType,
    ReviewLevel,
    ActionRecommendation,
    filter_by_review_level,
    group_by_action_type
)
from src.api.lib.synonym_detector import SynonymCandidate, SynonymStrength
from src.api.lib.vocabulary_scoring import EdgeTypeScore


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ai_provider():
    """Mock AI provider for AITL mode."""
    return MagicMock()


@pytest.fixture
def strong_synonym_candidate():
    """Strong synonym match (>= 0.90)."""
    return SynonymCandidate(
        type1="VALIDATES",
        type2="VERIFIES",
        similarity=0.95,
        strength=SynonymStrength.STRONG,
        is_strong_match=True,
        needs_review=False,
        reasoning="Very high similarity"
    )


@pytest.fixture
def moderate_synonym_candidate():
    """Moderate synonym match (0.70-0.89)."""
    return SynonymCandidate(
        type1="CHECKS",
        type2="TESTS",
        similarity=0.75,
        strength=SynonymStrength.MODERATE,
        is_strong_match=False,
        needs_review=True,
        reasoning="Moderate similarity"
    )


@pytest.fixture
def weak_synonym_candidate():
    """Weak synonym match (< 0.70)."""
    return SynonymCandidate(
        type1="VALIDATES",
        type2="IMPLIES",
        similarity=0.50,
        strength=SynonymStrength.WEAK,
        is_strong_match=False,
        needs_review=False,
        reasoning="Low similarity"
    )


@pytest.fixture
def high_value_score():
    """High-value edge type."""
    return EdgeTypeScore(
        relationship_type="IMPLIES",
        edge_count=500,
        avg_traversal=50.0,
        bridge_count=10,
        trend=5.0,
        value_score=120.5,
        is_builtin=True,
        last_used=datetime.now()
    )


@pytest.fixture
def low_value_score():
    """Low-value edge type with edges."""
    return EdgeTypeScore(
        relationship_type="CUSTOM_TYPE",
        edge_count=5,
        avg_traversal=0.5,
        bridge_count=0,
        trend=0.0,
        value_score=0.3,
        is_builtin=False,
        last_used=datetime.now()
    )


@pytest.fixture
def zero_edge_score():
    """Zero-edge type (safe to prune)."""
    return EdgeTypeScore(
        relationship_type="UNUSED_TYPE",
        edge_count=0,
        avg_traversal=0.0,
        bridge_count=0,
        trend=0.0,
        value_score=0.0,
        is_builtin=False,
        last_used=None
    )


# ============================================================================
# Initialization Tests
# ============================================================================


def test_init_naive_mode():
    """Test initialization in naive mode."""
    strategy = PruningStrategy(mode="naive")
    assert strategy.mode == PruningMode.NAIVE


def test_init_hitl_mode():
    """Test initialization in HITL mode."""
    strategy = PruningStrategy(mode="hitl")
    assert strategy.mode == PruningMode.HITL


def test_init_aitl_mode(mock_ai_provider):
    """Test initialization in AITL mode with AI provider."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)
    assert strategy.mode == PruningMode.AITL
    assert strategy.ai_provider is not None


def test_init_aitl_without_provider():
    """Test that AITL mode requires AI provider."""
    with pytest.raises(ValueError, match="AITL mode requires ai_provider"):
        PruningStrategy(mode="aitl")


def test_init_invalid_mode():
    """Test initialization with invalid mode."""
    with pytest.raises(ValueError, match="Invalid mode"):
        PruningStrategy(mode="invalid")


# ============================================================================
# Naive Mode Tests
# ============================================================================


@pytest.mark.asyncio
async def test_naive_strong_synonym_auto_merge(strong_synonym_candidate, high_value_score, low_value_score):
    """Test naive mode auto-merges strong synonyms."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_synonym(
        strong_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.MERGE
    assert action.review_level == ReviewLevel.NONE
    assert action.should_execute is True
    assert action.needs_review is False
    assert "auto-merge" in action.reasoning.lower()


@pytest.mark.asyncio
async def test_naive_moderate_synonym_skip(moderate_synonym_candidate, high_value_score, low_value_score):
    """Test naive mode skips moderate synonyms."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_synonym(
        moderate_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.SKIP
    assert action.should_execute is False
    assert action.needs_review is False
    assert "skip" in action.reasoning.lower()


@pytest.mark.asyncio
async def test_naive_weak_synonym_skip(weak_synonym_candidate, high_value_score, low_value_score):
    """Test naive mode skips weak synonyms."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_synonym(
        weak_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.SKIP
    assert action.should_execute is False


@pytest.mark.asyncio
async def test_naive_zero_edge_auto_prune(zero_edge_score):
    """Test naive mode auto-prunes zero-edge types."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_low_value_type(zero_edge_score)

    assert action.action_type == ActionType.PRUNE
    assert action.review_level == ReviewLevel.NONE
    assert action.should_execute is True
    assert action.needs_review is False


@pytest.mark.asyncio
async def test_naive_low_value_skip(low_value_score):
    """Test naive mode skips low-value types with edges (too risky)."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_low_value_type(low_value_score)

    assert action.action_type == ActionType.SKIP
    assert action.should_execute is False
    assert "too risky" in action.reasoning.lower()


@pytest.mark.asyncio
async def test_naive_builtin_protected(high_value_score):
    """Test naive mode protects builtin types."""
    strategy = PruningStrategy(mode="naive")

    action = await strategy.evaluate_low_value_type(high_value_score)

    assert action.action_type == ActionType.SKIP
    assert "builtin" in action.reasoning.lower()


# ============================================================================
# HITL Mode Tests
# ============================================================================


@pytest.mark.asyncio
async def test_hitl_strong_synonym_needs_approval(strong_synonym_candidate, high_value_score, low_value_score):
    """Test HITL mode requires human approval for strong synonyms."""
    strategy = PruningStrategy(mode="hitl")

    action = await strategy.evaluate_synonym(
        strong_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.MERGE
    assert action.review_level == ReviewLevel.HUMAN
    assert action.should_execute is False
    assert action.needs_review is True


@pytest.mark.asyncio
async def test_hitl_moderate_synonym_needs_approval(moderate_synonym_candidate, high_value_score, low_value_score):
    """Test HITL mode requires human approval for moderate synonyms."""
    strategy = PruningStrategy(mode="hitl")

    action = await strategy.evaluate_synonym(
        moderate_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.MERGE
    assert action.review_level == ReviewLevel.HUMAN
    assert action.needs_review is True


@pytest.mark.asyncio
async def test_hitl_weak_synonym_skip(weak_synonym_candidate, high_value_score, low_value_score):
    """Test HITL mode skips weak synonyms (always skip)."""
    strategy = PruningStrategy(mode="hitl")

    action = await strategy.evaluate_synonym(
        weak_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.SKIP
    assert action.should_execute is False


@pytest.mark.asyncio
async def test_hitl_zero_edge_needs_approval(zero_edge_score):
    """Test HITL mode requires human approval even for zero-edge types."""
    strategy = PruningStrategy(mode="hitl")

    action = await strategy.evaluate_low_value_type(zero_edge_score)

    assert action.action_type == ActionType.PRUNE
    assert action.review_level == ReviewLevel.HUMAN
    assert action.needs_review is True


@pytest.mark.asyncio
async def test_hitl_low_value_needs_approval(low_value_score):
    """Test HITL mode requires human approval for low-value types."""
    strategy = PruningStrategy(mode="hitl")

    action = await strategy.evaluate_low_value_type(low_value_score)

    assert action.action_type == ActionType.DEPRECATE
    assert action.review_level == ReviewLevel.HUMAN
    assert action.needs_review is True


# ============================================================================
# AITL Mode Tests
# ============================================================================


@pytest.mark.asyncio
async def test_aitl_strong_synonym_auto_merge(mock_ai_provider, strong_synonym_candidate, high_value_score, low_value_score):
    """Test AITL mode auto-merges strong synonyms."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    action = await strategy.evaluate_synonym(
        strong_synonym_candidate,
        high_value_score,
        low_value_score
    )

    assert action.action_type == ActionType.MERGE
    assert action.review_level == ReviewLevel.NONE
    assert action.should_execute is True
    assert action.needs_review is False


@pytest.mark.asyncio
async def test_aitl_moderate_synonym_ai_review(mock_ai_provider, moderate_synonym_candidate, high_value_score, low_value_score):
    """Test AITL mode uses AI review for moderate synonyms."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    action = await strategy.evaluate_synonym(
        moderate_synonym_candidate,
        high_value_score,
        low_value_score
    )

    # AI review should make a decision
    assert action.review_level == ReviewLevel.AI
    # Based on heuristic in code: similarity < 0.80 -> SKIP
    assert action.action_type == ActionType.SKIP or action.action_type == ActionType.MERGE


@pytest.mark.asyncio
async def test_aitl_high_moderate_synonym_ai_approves(mock_ai_provider, high_value_score, low_value_score):
    """Test AITL AI approves high moderate synonyms (>= 0.80)."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    # Create high moderate candidate (0.85)
    candidate = SynonymCandidate(
        type1="VALIDATES",
        type2="VERIFIES",
        similarity=0.85,
        strength=SynonymStrength.MODERATE,
        is_strong_match=False,
        needs_review=True,
        reasoning="High moderate similarity"
    )

    action = await strategy.evaluate_synonym(candidate, high_value_score, low_value_score)

    assert action.action_type == ActionType.MERGE
    assert action.review_level == ReviewLevel.AI
    assert action.should_execute is True
    assert "ai approved" in action.reasoning.lower()


@pytest.mark.asyncio
async def test_aitl_zero_edge_auto_prune(mock_ai_provider, zero_edge_score):
    """Test AITL mode auto-prunes zero-edge types."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    action = await strategy.evaluate_low_value_type(zero_edge_score)

    assert action.action_type == ActionType.PRUNE
    assert action.review_level == ReviewLevel.NONE
    assert action.should_execute is True


@pytest.mark.asyncio
async def test_aitl_low_value_ai_review(mock_ai_provider, low_value_score):
    """Test AITL mode uses AI review for low-value types with edges."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    action = await strategy.evaluate_low_value_type(low_value_score)

    # AI review should make a decision
    assert action.review_level == ReviewLevel.AI
    # Based on heuristic: value < 0.5 and no bridges -> DEPRECATE
    assert action.action_type == ActionType.DEPRECATE
    assert action.should_execute is True


@pytest.mark.asyncio
async def test_aitl_low_value_with_bridges_protected(mock_ai_provider):
    """Test AITL AI protects low-value types with bridges."""
    strategy = PruningStrategy(mode="aitl", ai_provider=mock_ai_provider)

    # Low value but has bridges
    score = EdgeTypeScore(
        relationship_type="CONNECTS",
        edge_count=10,
        avg_traversal=1.0,
        bridge_count=5,  # Has bridges!
        trend=0.0,
        value_score=0.3,
        is_builtin=False,
        last_used=datetime.now()
    )

    action = await strategy.evaluate_low_value_type(score)

    assert action.action_type == ActionType.SKIP
    assert "structurally important" in action.reasoning.lower()


# ============================================================================
# Merge Target Selection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_merge_preserves_higher_value(strong_synonym_candidate):
    """Test merge preserves type with higher value score."""
    strategy = PruningStrategy(mode="naive")

    high_score = EdgeTypeScore("VALIDATES", 100, 10.0, 5, 2.0, 50.0, False, datetime.now())
    low_score = EdgeTypeScore("VERIFIES", 50, 5.0, 2, 1.0, 20.0, False, datetime.now())

    action = await strategy.evaluate_synonym(strong_synonym_candidate, high_score, low_score)

    assert action.target_type == "VALIDATES"  # Higher value preserved
    assert action.edge_type == "VERIFIES"     # Lower value deprecated


@pytest.mark.asyncio
async def test_merge_preserves_lower_value_if_higher(strong_synonym_candidate):
    """Test merge preserves type2 if it has higher value."""
    strategy = PruningStrategy(mode="naive")

    low_score = EdgeTypeScore("VALIDATES", 50, 5.0, 2, 1.0, 20.0, False, datetime.now())
    high_score = EdgeTypeScore("VERIFIES", 100, 10.0, 5, 2.0, 50.0, False, datetime.now())

    action = await strategy.evaluate_synonym(strong_synonym_candidate, low_score, high_score)

    assert action.target_type == "VERIFIES"   # Higher value preserved
    assert action.edge_type == "VALIDATES"    # Lower value deprecated


# ============================================================================
# Batch Evaluation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batch_evaluate_naive(strong_synonym_candidate, moderate_synonym_candidate, zero_edge_score, low_value_score, high_value_score):
    """Test batch evaluation in naive mode."""
    strategy = PruningStrategy(mode="naive")

    synonyms = [
        (strong_synonym_candidate, high_value_score, low_value_score),
        (moderate_synonym_candidate, high_value_score, low_value_score)
    ]

    low_value_types = [zero_edge_score, low_value_score]

    results = await strategy.batch_evaluate(synonyms, low_value_types)

    assert "auto_execute" in results
    assert "needs_review" in results

    # Naive should auto-execute: strong synonym merge + zero-edge prune
    assert len(results["auto_execute"]) >= 2

    # Naive should not need review (skips moderate/low-value)
    assert len(results["needs_review"]) == 0


@pytest.mark.asyncio
async def test_batch_evaluate_hitl(strong_synonym_candidate, zero_edge_score, high_value_score, low_value_score):
    """Test batch evaluation in HITL mode - everything needs review."""
    strategy = PruningStrategy(mode="hitl")

    synonyms = [(strong_synonym_candidate, high_value_score, low_value_score)]
    low_value_types = [zero_edge_score]

    results = await strategy.batch_evaluate(synonyms, low_value_types)

    # HITL should require review for everything
    assert len(results["needs_review"]) >= 2
    assert len(results["auto_execute"]) == 0


@pytest.mark.asyncio
async def test_batch_evaluate_empty():
    """Test batch evaluation with empty lists."""
    strategy = PruningStrategy(mode="naive")

    results = await strategy.batch_evaluate([], [])

    assert results["auto_execute"] == []
    assert results["needs_review"] == []


# ============================================================================
# Utility Function Tests
# ============================================================================


def test_filter_by_review_level_none():
    """Test filtering by NONE review level (auto-execute)."""
    actions = [
        ActionRecommendation(ActionType.MERGE, "TYPE1", ReviewLevel.NONE, True, False, "TYPE2"),
        ActionRecommendation(ActionType.PRUNE, "TYPE3", ReviewLevel.HUMAN, False, True),
        ActionRecommendation(ActionType.MERGE, "TYPE4", ReviewLevel.NONE, True, False, "TYPE5"),
    ]

    auto = filter_by_review_level(actions, ReviewLevel.NONE)

    assert len(auto) == 2
    assert all(a.review_level == ReviewLevel.NONE for a in auto)


def test_filter_by_review_level_human():
    """Test filtering by HUMAN review level."""
    actions = [
        ActionRecommendation(ActionType.MERGE, "TYPE1", ReviewLevel.NONE, True, False, "TYPE2"),
        ActionRecommendation(ActionType.PRUNE, "TYPE3", ReviewLevel.HUMAN, False, True),
        ActionRecommendation(ActionType.DEPRECATE, "TYPE4", ReviewLevel.HUMAN, False, True),
    ]

    human = filter_by_review_level(actions, ReviewLevel.HUMAN)

    assert len(human) == 2
    assert all(a.review_level == ReviewLevel.HUMAN for a in human)


def test_group_by_action_type():
    """Test grouping recommendations by action type."""
    actions = [
        ActionRecommendation(ActionType.MERGE, "TYPE1", ReviewLevel.NONE, True, False, "TYPE2"),
        ActionRecommendation(ActionType.MERGE, "TYPE3", ReviewLevel.NONE, True, False, "TYPE4"),
        ActionRecommendation(ActionType.PRUNE, "TYPE5", ReviewLevel.NONE, True, False),
        ActionRecommendation(ActionType.SKIP, "TYPE6", ReviewLevel.NONE, False, False),
    ]

    groups = group_by_action_type(actions)

    assert ActionType.MERGE in groups
    assert ActionType.PRUNE in groups
    assert ActionType.SKIP in groups
    assert len(groups[ActionType.MERGE]) == 2
    assert len(groups[ActionType.PRUNE]) == 1
    assert len(groups[ActionType.SKIP]) == 1


def test_group_by_action_type_empty():
    """Test grouping empty list."""
    groups = group_by_action_type([])
    assert len(groups) == 0


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_builtin_never_pruned():
    """Test that builtin types are never pruned regardless of mode."""
    builtin_score = EdgeTypeScore(
        relationship_type="IMPLIES",
        edge_count=0,  # Even with zero edges
        avg_traversal=0.0,
        bridge_count=0,
        trend=0.0,
        value_score=0.0,
        is_builtin=True,  # Protected!
        last_used=None
    )

    for mode in ["naive", "hitl"]:
        strategy = PruningStrategy(mode=mode)
        action = await strategy.evaluate_low_value_type(builtin_score)

        assert action.action_type == ActionType.SKIP
        assert "builtin" in action.reasoning.lower()


@pytest.mark.asyncio
async def test_action_recommendation_repr_merge():
    """Test ActionRecommendation string representation for merge."""
    action = ActionRecommendation(
        action_type=ActionType.MERGE,
        edge_type="VALIDATES",
        target_type="VERIFIES",
        review_level=ReviewLevel.NONE,
        should_execute=True,
        needs_review=False
    )

    repr_str = repr(action)
    assert "MERGE" in repr_str
    assert "VALIDATES" in repr_str
    assert "VERIFIES" in repr_str


@pytest.mark.asyncio
async def test_action_recommendation_repr_prune():
    """Test ActionRecommendation string representation for prune."""
    action = ActionRecommendation(
        action_type=ActionType.PRUNE,
        edge_type="UNUSED",
        review_level=ReviewLevel.NONE,
        should_execute=True,
        needs_review=False
    )

    repr_str = repr(action)
    assert "PRUNE" in repr_str
    assert "UNUSED" in repr_str


@pytest.mark.asyncio
async def test_metadata_preserved():
    """Test that metadata is preserved in recommendations."""
    strategy = PruningStrategy(mode="naive")

    high_score = EdgeTypeScore("TYPE1", 100, 10.0, 5, 2.0, 50.0, False, datetime.now())
    low_score = EdgeTypeScore("TYPE2", 50, 5.0, 2, 1.0, 20.0, False, datetime.now())

    candidate = SynonymCandidate("TYPE1", "TYPE2", 0.95, SynonymStrength.STRONG, True, False, "Test")

    action = await strategy.evaluate_synonym(candidate, high_score, low_score)

    assert action.metadata is not None
    assert "similarity" in action.metadata
    assert action.metadata["similarity"] == 0.95
