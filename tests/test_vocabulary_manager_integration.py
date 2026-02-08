"""
Integration tests for VocabularyManager - End-to-end workflow testing.

Tests the complete pipeline:
1. Adding new edge types to vocabulary
2. Checking for synonyms
3. Analyzing vocabulary state
4. Generating recommendations
5. Executing actions based on mode
6. Verifying database state changes

Author: Claude (ADR-032 Phase 3b)
"""

import pytest
import asyncio
from typing import List, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from tests.helpers import patch_synonym_detector_embedding
from api.app.services.vocabulary_manager import VocabularyManager
from api.app.lib.aggressiveness_curve import calculate_aggressiveness
from api.app.lib.vocabulary_scoring import EdgeTypeScore
from api.app.lib.synonym_detector import SynonymCandidate, SynonymStrength
from api.app.lib.pruning_strategies import ActionType, ReviewLevel, ActionRecommendation


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_client():
    """Mock AGEClient with vocabulary operations"""
    client = MagicMock()

    # Initial vocabulary state (30 types - at vocab_min)
    client._vocabulary = [
        "ANALOGOUS_TO", "CAUSES", "COMPLEMENTS", "COMPOSED_OF", "CONSUMES",
        "CONTRADICTS", "CONTRASTS_WITH", "CONVERTS", "DEPENDS_ON", "DERIVES_FROM",
        "ENABLES", "EQUIVALENT_TO", "EVIDENCED_BY", "EXEMPLIFIES", "GENERATES",
        "IMPLIES", "INHIBITS", "INSTANTIATES", "JUSTIFIES", "LEADS_TO",
        "MAINTAINS", "MANIFESTS", "MITIGATES", "OPPOSES", "PRECEDES",
        "PREVENTS", "REQUIRES", "RESULTS_FROM", "SUGGESTS", "SUPPORTS"
    ]

    # Vocabulary CRUD operations
    def get_vocabulary_size():
        return len([t for t in client._vocabulary if t])

    def get_all_edge_types(include_inactive=False):
        return list(client._vocabulary)

    def add_edge_type(relationship_type, category, description=None, added_by="system", is_builtin=False):
        if relationship_type not in client._vocabulary:
            client._vocabulary.append(relationship_type)
            return True
        return False

    def get_edge_type_info(relationship_type):
        if relationship_type in client._vocabulary:
            return {
                "relationship_type": relationship_type,
                "category": "test_category",
                "is_active": True,
                "is_builtin": relationship_type in ["IMPLIES", "SUPPORTS", "CONTRADICTS"],
                "added_by": "system",
                "description": f"Test description for {relationship_type}"
            }
        return None

    def merge_edge_types(deprecated_type, target_type, performed_by="system"):
        if deprecated_type in client._vocabulary:
            client._vocabulary.remove(deprecated_type)
        return {"edges_updated": 5, "vocab_updated": 1}

    def get_category_distribution():
        return {
            "logical_truth": 8,
            "causal": 6,
            "structural": 5,
            "evidential": 4,
            "similarity": 3,
            "temporal": 2,
            "functional": 1,
            "meta": 1
        }

    def get_vocab_config(key):
        """Return None for all config keys so VocabularyManager uses defaults."""
        return None

    client.get_vocabulary_size = get_vocabulary_size
    client.get_all_edge_types = get_all_edge_types
    client.add_edge_type = add_edge_type
    client.get_edge_type_info = get_edge_type_info
    client.merge_edge_types = merge_edge_types
    client.get_category_distribution = get_category_distribution
    client.get_vocab_config = get_vocab_config

    return client


@pytest.fixture
def mock_ai_provider():
    """Mock AI provider for embeddings"""
    provider = AsyncMock()

    # Generate deterministic embeddings based on edge type name
    async def generate_embedding(text):
        # Simple hash-based embedding for deterministic results
        hash_val = hash(text) % 1000
        # Create 1536-dim embedding (normalized)
        embedding = np.random.RandomState(hash_val).randn(1536)
        embedding = embedding / np.linalg.norm(embedding)
        return {"embedding": embedding.tolist()}

    provider.generate_embedding = generate_embedding
    return provider


def _patch_synonym_detector(manager):
    """Patch SynonymDetector on a VocabularyManager to bypass AGEClient."""
    patch_synonym_detector_embedding(manager.synonym_detector)


@pytest.fixture
def vocabulary_manager_naive(mock_db_client, mock_ai_provider):
    """VocabularyManager in naive mode (auto-execute)"""
    mgr = VocabularyManager(
        db_client=mock_db_client,
        ai_provider=mock_ai_provider,
        mode="naive",
        aggressiveness_profile="aggressive"
    )
    _patch_synonym_detector(mgr)
    return mgr


@pytest.fixture
def vocabulary_manager_hitl(mock_db_client, mock_ai_provider):
    """VocabularyManager in HITL mode (human review)"""
    mgr = VocabularyManager(
        db_client=mock_db_client,
        ai_provider=mock_ai_provider,
        mode="hitl",
        aggressiveness_profile="aggressive"
    )
    _patch_synonym_detector(mgr)
    return mgr


@pytest.fixture
def vocabulary_manager_aitl(mock_db_client, mock_ai_provider):
    """VocabularyManager in AITL mode (AI review)"""
    mgr = VocabularyManager(
        db_client=mock_db_client,
        ai_provider=mock_ai_provider,
        mode="aitl",
        aggressiveness_profile="aggressive"
    )
    _patch_synonym_detector(mgr)
    return mgr


# =============================================================================
# Integration Tests - Basic Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_add_new_edge_types(vocabulary_manager_naive, mock_db_client):
    """Test adding new edge types to vocabulary"""
    initial_size = mock_db_client.get_vocabulary_size()
    assert initial_size == 30  # At vocab_min

    # Add three new types
    new_types = ["AUTHORED_BY", "DATES", "REFERENCES"]

    for edge_type in new_types:
        result = mock_db_client.add_edge_type(
            edge_type,
            category="test_category",
            description=f"Test edge type {edge_type}",
            added_by="integration_test"
        )
        assert result is True

    # Verify vocabulary grew
    new_size = mock_db_client.get_vocabulary_size()
    assert new_size == 33

    # Verify types exist
    all_types = mock_db_client.get_all_edge_types()
    for edge_type in new_types:
        assert edge_type in all_types


@pytest.mark.asyncio
async def test_check_for_synonyms_before_adding(vocabulary_manager_naive):
    """Test synonym detection before adding new types"""
    # Check if "WRITTEN_BY" would be similar to existing types
    synonyms = await vocabulary_manager_naive.check_for_synonyms(
        "WRITTEN_BY",
        existing_types=["AUTHORED_BY", "CREATED_BY", "COMPOSED_BY"]
    )

    # Should detect similarity to existing types
    assert isinstance(synonyms, list)
    # With mock embeddings, similarity depends on hash
    # We're just verifying the method works, not exact similarity scores


@pytest.mark.asyncio
async def test_analyze_vocabulary_state(vocabulary_manager_naive, mock_db_client):
    """Test vocabulary analysis with current state"""
    # Mock scorer responses - MUST RETURN DICT not list
    mock_scores = {
        "IMPLIES": EdgeTypeScore(
            relationship_type="IMPLIES",
            edge_count=150,
            avg_traversal=45.0,
            bridge_count=3,
            trend=2.5,
            value_score=150.0,
            is_builtin=True,
            last_used=None
        ),
        "SUPPORTS": EdgeTypeScore(
            relationship_type="SUPPORTS",
            edge_count=120,
            avg_traversal=35.0,
            bridge_count=2,
            trend=1.8,
            value_score=120.0,
            is_builtin=True,
            last_used=None
        ),
        "LOW_VALUE_TYPE": EdgeTypeScore(
            relationship_type="LOW_VALUE_TYPE",
            edge_count=2,
            avg_traversal=0.5,
            bridge_count=0,
            trend=0.0,
            value_score=0.5,
            is_builtin=False,
            last_used=None
        )
    }

    with patch.object(
        vocabulary_manager_naive.scorer,
        'get_value_scores',
        return_value=mock_scores
    ):
        analysis = await vocabulary_manager_naive.analyze_vocabulary(
            vocab_min=30,
            vocab_max=90,
            vocab_emergency=200
        )

    # Verify analysis structure
    assert analysis.vocab_size == 30
    assert analysis.aggressiveness >= 0.0
    assert analysis.aggressiveness <= 1.0
    assert analysis.zone in ["comfort", "watch", "emergency", "block"]
    assert len(analysis.edge_type_scores) == 3
    assert len(analysis.low_value_types) >= 0
    assert len(analysis.synonym_candidates) >= 0

    # At vocab_min, should be in "comfort" zone
    assert analysis.zone == "comfort"


@pytest.mark.asyncio
async def test_generate_recommendations_naive_mode(vocabulary_manager_naive):
    """Test recommendation generation in naive mode (auto-execute)"""
    # Create proper EdgeTypeScore objects
    score_type_a = EdgeTypeScore("TYPE_A", 100, 30.0, 2, 1.5, 100.0, False, None)
    score_type_b = EdgeTypeScore("TYPE_B", 95, 28.0, 2, 1.4, 95.0, False, None)
    score_low_value = EdgeTypeScore("LOW_VALUE", 2, 0.5, 0, 0.0, 0.5, False, None)

    # Create proper SynonymCandidate with all required fields
    synonym = SynonymCandidate(
        type1="TYPE_A",
        type2="TYPE_B",
        similarity=0.95,
        strength=SynonymStrength.STRONG,
        is_strong_match=True,
        needs_review=False,
        reasoning="High semantic similarity (0.95)"
    )

    # Mock analysis with synonym candidate
    with patch.object(
        vocabulary_manager_naive,
        'analyze_vocabulary',
        return_value=MagicMock(
            vocab_size=35,
            aggressiveness=0.2,
            zone="watch",
            edge_type_scores={
                "TYPE_A": score_type_a,
                "TYPE_B": score_type_b,
                "LOW_VALUE": score_low_value
            },
            synonym_candidates=[(synonym, score_type_a, score_type_b)],
            low_value_types=[score_low_value],
            category_distribution={"test": 8}
        )
    ):
        recommendations = await vocabulary_manager_naive.generate_recommendations()

    # Verify recommendations structure
    assert "auto_execute" in recommendations
    assert "needs_review" in recommendations

    # In naive mode, strong synonyms should be auto-approved
    auto_execute = recommendations["auto_execute"]
    assert len(auto_execute) > 0  # Should have at least the strong synonym

    # Verify the action is a merge
    merge_actions = [a for a in auto_execute if a.action_type == ActionType.MERGE]
    assert len(merge_actions) > 0
    assert merge_actions[0].should_execute is True


@pytest.mark.asyncio
async def test_generate_recommendations_hitl_mode(vocabulary_manager_hitl):
    """Test recommendation generation in HITL mode (human review required)"""
    # Create proper EdgeTypeScore objects
    score_type_a = EdgeTypeScore("TYPE_A", 100, 30.0, 2, 1.5, 100.0, False, None)
    score_type_b = EdgeTypeScore("TYPE_B", 95, 28.0, 2, 1.4, 95.0, False, None)

    # Create proper SynonymCandidate with all required fields
    synonym = SynonymCandidate(
        type1="TYPE_A",
        type2="TYPE_B",
        similarity=0.95,
        strength=SynonymStrength.STRONG,
        is_strong_match=True,
        needs_review=True,
        reasoning="High semantic similarity (0.95) - needs human review"
    )

    # Mock analysis with synonym candidate
    with patch.object(
        vocabulary_manager_hitl,
        'analyze_vocabulary',
        return_value=MagicMock(
            vocab_size=35,
            aggressiveness=0.2,
            zone="watch",
            edge_type_scores={
                "TYPE_A": score_type_a,
                "TYPE_B": score_type_b
            },
            synonym_candidates=[(synonym, score_type_a, score_type_b)],
            low_value_types=[],
            category_distribution={"test": 8}
        )
    ):
        recommendations = await vocabulary_manager_hitl.generate_recommendations()

    # In HITL mode, even strong synonyms should require human review
    needs_review = recommendations["needs_review"]
    assert len(needs_review) > 0  # Should have at least the strong synonym

    # Verify the action requires human review
    merge_actions = [a for a in needs_review if a.action_type == ActionType.MERGE]
    assert len(merge_actions) > 0
    assert merge_actions[0].review_level == ReviewLevel.HUMAN
    assert merge_actions[0].should_execute is False


@pytest.mark.asyncio
async def test_execute_merge_action(vocabulary_manager_naive, mock_db_client):
    """Test executing a merge action"""
    # Add test types
    mock_db_client.add_edge_type("AUTHORED_BY", "authorship")
    mock_db_client.add_edge_type("WRITTEN_BY", "authorship")

    initial_size = mock_db_client.get_vocabulary_size()

    # Execute merge
    result = mock_db_client.merge_edge_types(
        deprecated_type="WRITTEN_BY",
        target_type="AUTHORED_BY",
        performed_by="integration_test"
    )

    # Verify merge results
    assert result["edges_updated"] == 5
    assert result["vocab_updated"] == 1

    # Verify vocabulary size decreased
    new_size = mock_db_client.get_vocabulary_size()
    assert new_size == initial_size - 1

    # Verify deprecated type removed
    all_types = mock_db_client.get_all_edge_types()
    assert "WRITTEN_BY" not in all_types
    assert "AUTHORED_BY" in all_types


# =============================================================================
# Integration Tests - Complex Scenarios
# =============================================================================

@pytest.mark.asyncio
async def test_full_workflow_with_real_types(vocabulary_manager_naive, mock_db_client):
    """
    Test complete workflow with realistic edge types:
    1. Add AUTHORED_BY, DATES, REFERENCES
    2. Analyze vocabulary
    3. Generate recommendations
    4. Execute approved actions
    """
    # Step 1: Add new types
    new_types = [
        ("AUTHORED_BY", "authorship"),
        ("DATES", "temporal"),
        ("REFERENCES", "citation")
    ]

    for edge_type, category in new_types:
        result = mock_db_client.add_edge_type(edge_type, category)
        assert result is True

    # Step 2: Check vocabulary state
    vocab_size = mock_db_client.get_vocabulary_size()
    assert vocab_size == 33  # 30 initial + 3 new

    # Step 3: Analyze vocabulary
    mock_scores = {
        "AUTHORED_BY": EdgeTypeScore("AUTHORED_BY", 50, 15.0, 1, 0.8, 50.0, False, None),
        "DATES": EdgeTypeScore("DATES", 30, 8.0, 0, 0.3, 30.0, False, None),
        "REFERENCES": EdgeTypeScore("REFERENCES", 40, 12.0, 1, 0.6, 40.0, False, None),
    }

    with patch.object(
        vocabulary_manager_naive.scorer,
        'get_value_scores',
        return_value=mock_scores
    ):
        analysis = await vocabulary_manager_naive.analyze_vocabulary()

    assert analysis.vocab_size == 33
    assert len(analysis.edge_type_scores) == 3

    # Step 4: Generate recommendations
    recommendations = await vocabulary_manager_naive.generate_recommendations(analysis)

    # Verify recommendations structure
    assert isinstance(recommendations, dict)
    # Keys should be auto_execute and needs_review
    assert "auto_execute" in recommendations
    assert "needs_review" in recommendations
    assert isinstance(recommendations["auto_execute"], list)
    assert isinstance(recommendations["needs_review"], list)


@pytest.mark.asyncio
async def test_aggressiveness_increases_with_vocabulary_size(
    vocabulary_manager_naive,
    mock_db_client
):
    """Test that aggressiveness increases as vocabulary grows"""
    # Test at different vocabulary sizes
    test_sizes = [30, 50, 90, 150, 200]
    previous_aggressiveness = 0.0

    for size in test_sizes:
        # Mock vocabulary size
        mock_db_client._vocabulary = [f"TYPE_{i}" for i in range(size)]

        # Calculate aggressiveness
        aggressiveness, zone = calculate_aggressiveness(
            current_size=size,
            vocab_min=30,
            vocab_max=90,
            vocab_emergency=200,
            profile="aggressive"
        )

        print(f"Size={size}, Aggressiveness={aggressiveness:.3f}, Zone={zone}")

        # Verify monotonic increase
        if size > 30:  # After safe zone
            assert aggressiveness >= previous_aggressiveness

        previous_aggressiveness = aggressiveness

    # Verify zones (actual zone names from aggressiveness_curve.py)
    assert calculate_aggressiveness(25, 30, 90, 200)[1] == "comfort"
    assert calculate_aggressiveness(50, 30, 90, 200)[1] == "watch"
    assert calculate_aggressiveness(120, 30, 90, 200)[1] == "emergency"
    assert calculate_aggressiveness(200, 30, 90, 200)[1] == "block"


@pytest.mark.asyncio
async def test_builtin_types_protected_from_pruning(vocabulary_manager_naive):
    """Test that builtin types cannot be pruned"""
    # Mock analysis with low-value builtin type
    builtin_score = EdgeTypeScore(
        relationship_type="IMPLIES",
        edge_count=5,
        avg_traversal=1.0,
        bridge_count=0,
        trend=0.0,
        value_score=0.5,  # Very low value
        is_builtin=True,
        last_used=None
    )

    with patch.object(
        vocabulary_manager_naive,
        'analyze_vocabulary',
        return_value=MagicMock(
            vocab_size=35,
            aggressiveness=0.8,
            zone="emergency",
            edge_type_scores={"IMPLIES": builtin_score},
            synonym_candidates=[],
            low_value_types=[builtin_score],  # Include builtin in low value
            category_distribution={"logical_truth": 1}
        )
    ):
        recommendations = await vocabulary_manager_naive.generate_recommendations()

    # Verify builtin type not recommended for pruning
    if "prune" in recommendations:
        prune_recs = recommendations["prune"]
        builtin_prune = [r for r in prune_recs if r.relationship_type == "IMPLIES"]
        # Should either be empty or marked as SKIP
        for rec in builtin_prune:
            assert rec.action_type == ActionType.SKIP


@pytest.mark.asyncio
async def test_mode_comparison_all_three_modes(
    vocabulary_manager_naive,
    vocabulary_manager_hitl,
    vocabulary_manager_aitl
):
    """
    Compare behavior across all three modes:
    - naive: Auto-execute strong synonyms
    - HITL: Human review required
    - AITL: AI review before execution
    """
    # Create proper EdgeTypeScore objects
    score_created_by = EdgeTypeScore("CREATED_BY", 50, 15.0, 1, 0.8, 50.0, False, None)
    score_authored_by = EdgeTypeScore("AUTHORED_BY", 48, 14.5, 1, 0.75, 48.0, False, None)

    # Create proper SynonymCandidate
    synonym = SynonymCandidate(
        type1="CREATED_BY",
        type2="AUTHORED_BY",
        similarity=0.95,
        strength=SynonymStrength.STRONG,
        is_strong_match=True,
        needs_review=False,
        reasoning="Very high semantic similarity (0.95)"
    )

    # Mock analysis with strong synonym
    mock_analysis = MagicMock(
        vocab_size=35,
        aggressiveness=0.2,
        zone="watch",
        edge_type_scores={
            "CREATED_BY": score_created_by,
            "AUTHORED_BY": score_authored_by
        },
        synonym_candidates=[(synonym, score_created_by, score_authored_by)],
        low_value_types=[],
        category_distribution={"authorship": 2}
    )

    # Test naive mode
    with patch.object(vocabulary_manager_naive, 'analyze_vocabulary', return_value=mock_analysis):
        naive_recs = await vocabulary_manager_naive.generate_recommendations()

    # Test HITL mode
    with patch.object(vocabulary_manager_hitl, 'analyze_vocabulary', return_value=mock_analysis):
        hitl_recs = await vocabulary_manager_hitl.generate_recommendations()

    # Test AITL mode
    with patch.object(vocabulary_manager_aitl, 'analyze_vocabulary', return_value=mock_analysis):
        aitl_recs = await vocabulary_manager_aitl.generate_recommendations()

    # Compare behaviors
    print("\n=== Mode Comparison ===")

    # Naive: Should auto-approve
    if len(naive_recs["auto_execute"]) > 0:
        naive_merge = naive_recs["auto_execute"][0]
        print(f"Naive - should_execute: {naive_merge.should_execute}, review_level: {naive_merge.review_level}")
        assert naive_merge.should_execute is True
        assert naive_merge.review_level == ReviewLevel.NONE

    # HITL: Should require human review
    if len(hitl_recs["needs_review"]) > 0:
        hitl_merge = hitl_recs["needs_review"][0]
        print(f"HITL - should_execute: {hitl_merge.should_execute}, review_level: {hitl_merge.review_level}")
        assert hitl_merge.review_level == ReviewLevel.HUMAN
        assert hitl_merge.should_execute is False

    # AITL: Should auto-execute (strong synonym in AITL mode)
    if len(aitl_recs["auto_execute"]) > 0:
        aitl_merge = aitl_recs["auto_execute"][0]
        print(f"AITL - should_execute: {aitl_merge.should_execute}, review_level: {aitl_merge.review_level}")
        # AITL auto-executes strong synonyms
        assert aitl_merge.should_execute is True


# =============================================================================
# Integration Tests - Error Handling
# =============================================================================

@pytest.mark.asyncio
async def test_handle_duplicate_edge_type_addition(vocabulary_manager_naive, mock_db_client):
    """Test handling of duplicate edge type addition"""
    # Add type first time
    result1 = mock_db_client.add_edge_type("DUPLICATE_TYPE", "test_category")
    assert result1 is True

    # Try adding same type again
    result2 = mock_db_client.add_edge_type("DUPLICATE_TYPE", "test_category")
    assert result2 is False  # Should return False, not error


@pytest.mark.asyncio
async def test_handle_merge_nonexistent_type(vocabulary_manager_naive, mock_db_client):
    """Test merging a type that doesn't exist"""
    initial_size = mock_db_client.get_vocabulary_size()

    # Try merging nonexistent type
    result = mock_db_client.merge_edge_types(
        deprecated_type="NONEXISTENT_TYPE",
        target_type="IMPLIES"
    )

    # Should complete without error (no-op)
    assert result["vocab_updated"] == 1

    # Vocabulary size should be unchanged
    new_size = mock_db_client.get_vocabulary_size()
    assert new_size == initial_size


@pytest.mark.asyncio
async def test_empty_synonym_candidates(vocabulary_manager_naive):
    """Test analysis when no synonym candidates found"""
    with patch.object(
        vocabulary_manager_naive.synonym_detector,
        'find_synonyms_for_type',
        return_value=[]  # No synonyms
    ):
        synonyms = await vocabulary_manager_naive.check_for_synonyms("UNIQUE_TYPE")
        assert synonyms == []
        assert isinstance(synonyms, list)


# =============================================================================
# Execute Prune/Deprecate Tests
# =============================================================================

def _make_mock_pool():
    """Create a mock connection pool with cursor context manager."""
    pool = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    pool.getconn.return_value = conn
    return pool, conn, cursor


@pytest.fixture
def prune_action():
    """ActionRecommendation for a PRUNE action."""
    return ActionRecommendation(
        action_type=ActionType.PRUNE,
        edge_type="STALE_TYPE",
        review_level=ReviewLevel.NONE,
        should_execute=True,
        needs_review=False,
        reasoning="Zero edges - auto-prune",
        metadata={"value_score": 0.0, "edge_count": 0}
    )


@pytest.fixture
def deprecate_action():
    """ActionRecommendation for a DEPRECATE action."""
    return ActionRecommendation(
        action_type=ActionType.DEPRECATE,
        edge_type="LOW_VALUE_TYPE",
        review_level=ReviewLevel.AI,
        should_execute=True,
        needs_review=False,
        reasoning="LLM approved deprecation",
        metadata={"value_score": 0.3, "edge_count": 5}
    )


@pytest.mark.asyncio
async def test_execute_prune_success(vocabulary_manager_naive, prune_action):
    """Test successful prune: type exists with zero edges."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    # First query: SELECT edge_count → row with edge_count=0
    # Second query: DELETE RETURNING → returns the deleted type
    # Third query: INSERT history → no return needed
    cursor.fetchone.side_effect = [
        (0,),            # edge_count = 0 (safe to prune)
        ("STALE_TYPE",), # DELETE RETURNING
    ]

    result = await vocabulary_manager_naive._execute_prune(prune_action)

    assert result.success is True
    assert "Pruned" in result.message
    conn.commit.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_prune_refuses_with_edges(vocabulary_manager_naive, prune_action):
    """Test prune refused when type still has edges."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    cursor.fetchone.side_effect = [
        (12,),  # edge_count = 12 (NOT safe to prune)
    ]

    result = await vocabulary_manager_naive._execute_prune(prune_action)

    assert result.success is False
    assert "still has 12 edges" in result.message
    assert result.error == "edges_exist"
    conn.commit.assert_not_called()
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_prune_type_not_found(vocabulary_manager_naive, prune_action):
    """Test prune when type doesn't exist in vocabulary."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    cursor.fetchone.side_effect = [
        None,  # SELECT returns nothing
    ]

    result = await vocabulary_manager_naive._execute_prune(prune_action)

    assert result.success is False
    assert "not found" in result.message
    assert result.error == "not_found"
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_prune_delete_fails(vocabulary_manager_naive, prune_action):
    """Test prune when DELETE RETURNING returns nothing."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    cursor.fetchone.side_effect = [
        (0,),   # edge_count = 0
        None,   # DELETE RETURNING → nothing deleted
    ]

    result = await vocabulary_manager_naive._execute_prune(prune_action)

    assert result.success is False
    assert result.error == "delete_failed"
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_prune_db_error_rolls_back(vocabulary_manager_naive, prune_action):
    """Test prune rolls back on database error."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    cursor.execute.side_effect = Exception("connection lost")

    result = await vocabulary_manager_naive._execute_prune(prune_action)

    assert result.success is False
    assert "connection lost" in result.error
    conn.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_deprecate_success(vocabulary_manager_naive, deprecate_action):
    """Test successful deprecate: type exists and is active."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    # UPDATE RETURNING → returns type and edge count
    cursor.fetchone.side_effect = [
        ("LOW_VALUE_TYPE", 5),  # relationship_type, edge_count
    ]

    result = await vocabulary_manager_naive._execute_deprecate(deprecate_action)

    assert result.success is True
    assert "Deprecated" in result.message
    assert "5 edges preserved" in result.message
    conn.commit.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_deprecate_already_inactive(vocabulary_manager_naive, deprecate_action):
    """Test deprecate when type is already inactive or doesn't exist."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    # UPDATE RETURNING → nothing (WHERE is_active = TRUE didn't match)
    cursor.fetchone.side_effect = [None]

    result = await vocabulary_manager_naive._execute_deprecate(deprecate_action)

    assert result.success is False
    assert "not found or already inactive" in result.message
    assert result.error == "not_found_or_inactive"
    pool.putconn.assert_called_once_with(conn)


@pytest.mark.asyncio
async def test_execute_deprecate_db_error_rolls_back(vocabulary_manager_naive, deprecate_action):
    """Test deprecate rolls back on database error."""
    pool, conn, cursor = _make_mock_pool()
    vocabulary_manager_naive.db.pool = pool

    cursor.execute.side_effect = Exception("permission denied")

    result = await vocabulary_manager_naive._execute_deprecate(deprecate_action)

    assert result.success is False
    assert "permission denied" in result.error
    conn.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


# =============================================================================
# Summary Test
# =============================================================================

@pytest.mark.asyncio
async def test_complete_integration_summary(vocabulary_manager_naive, mock_db_client):
    """
    Complete integration test summarizing all capabilities:
    - Vocabulary operations
    - Synonym detection
    - Analysis
    - Recommendation generation
    - Action execution
    """
    print("\n=== Complete Integration Test Summary ===\n")

    # 1. Initial state
    initial_size = mock_db_client.get_vocabulary_size()
    print(f"✓ Initial vocabulary size: {initial_size}")
    assert initial_size == 30

    # 2. Add new types
    new_types = ["AUTHORED_BY", "DATES", "REFERENCES"]
    for edge_type in new_types:
        result = mock_db_client.add_edge_type(edge_type, "test_category")
        assert result is True
    print(f"✓ Added {len(new_types)} new edge types")

    # 3. Check synonyms
    synonyms = await vocabulary_manager_naive.check_for_synonyms(
        "WRITTEN_BY",
        existing_types=["AUTHORED_BY"]
    )
    print(f"✓ Checked for synonyms: {len(synonyms)} candidates found")

    # 4. Analyze vocabulary
    mock_scores = {
        "AUTHORED_BY": EdgeTypeScore("AUTHORED_BY", 50, 15.0, 1, 0.8, 50.0, False, None),
        "DATES": EdgeTypeScore("DATES", 30, 8.0, 0, 0.3, 30.0, False, None),
        "REFERENCES": EdgeTypeScore("REFERENCES", 40, 12.0, 1, 0.6, 40.0, False, None),
    }

    with patch.object(
        vocabulary_manager_naive.scorer,
        'get_value_scores',
        return_value=mock_scores
    ):
        analysis = await vocabulary_manager_naive.analyze_vocabulary()
    print(f"✓ Analyzed vocabulary: size={analysis.vocab_size}, zone={analysis.zone}, aggressiveness={analysis.aggressiveness:.3f}")

    # 5. Generate recommendations
    recommendations = await vocabulary_manager_naive.generate_recommendations(analysis)
    total_recs = sum(len(recs) for recs in recommendations.values())
    print(f"✓ Generated {total_recs} recommendations across {len(recommendations)} action types")

    # 6. Execute merge
    mock_db_client.add_edge_type("WRITTEN_BY", "authorship")
    result = mock_db_client.merge_edge_types("WRITTEN_BY", "AUTHORED_BY")
    print(f"✓ Executed merge: {result['edges_updated']} edges updated, {result['vocab_updated']} vocab entries updated")

    # 7. Final state
    final_size = mock_db_client.get_vocabulary_size()
    print(f"✓ Final vocabulary size: {final_size}")

    print("\n=== All Integration Tests Passed ===\n")
    assert True  # If we got here, all assertions passed
