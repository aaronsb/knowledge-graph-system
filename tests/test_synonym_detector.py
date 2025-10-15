"""
Tests for synonym_detector.py

Validates embedding-based synonym detection for edge type merging (ADR-032).
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from src.api.lib.synonym_detector import (
    SynonymDetector,
    SynonymCandidate,
    SynonymStrength,
    MergeRecommendation,
    filter_by_strength,
    get_merge_graph
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ai_provider():
    """Mock AI provider with controlled embeddings."""
    provider = MagicMock()

    # Define mock embeddings for test types
    # Using controlled vectors to produce known cosine similarities
    mock_embeddings = {
        "VALIDATES": np.array([1.0, 0.0, 0.0]),      # Base vector
        "VERIFIES": np.array([0.95, 0.312, 0.0]),    # ~0.95 similarity (very similar)
        "CHECKS": np.array([0.87, 0.494, 0.0]),      # ~0.87 similarity (moderately similar)
        "IMPLIES": np.array([0.0, 1.0, 0.0]),        # ~0.0 similarity (completely different)
        "SUPPORTS": np.array([0.5, 0.866, 0.0]),     # ~0.5 similarity (somewhat different)
        "CONFIRMS": np.array([0.92, 0.391, 0.0]),    # ~0.92 similarity (very similar to VALIDATES)
        "TESTS": np.array([0.85, 0.527, 0.0]),       # ~0.85 similarity (moderately similar)
        "ENABLES": np.array([0.0, 0.0, 1.0]),        # ~0.0 similarity (orthogonal - completely different)
    }

    async def mock_generate_embedding(text: str):
        # Extract edge type from "relationship: <type>" format
        edge_type = text.replace("relationship: ", "").upper()

        if edge_type in mock_embeddings:
            return {"embedding": mock_embeddings[edge_type].tolist()}
        else:
            # Default random embedding for unknown types
            np.random.seed(hash(edge_type) % (2**32))
            return {"embedding": np.random.rand(3).tolist()}

    provider.generate_embedding = AsyncMock(side_effect=mock_generate_embedding)

    return provider


@pytest.fixture
def detector(mock_ai_provider):
    """SynonymDetector instance with mock provider."""
    return SynonymDetector(mock_ai_provider)


# ============================================================================
# Basic Synonym Detection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_find_synonyms_strong_match(detector):
    """Test detection of strong synonym matches (>= 0.90)."""
    edge_types = ["VALIDATES", "VERIFIES", "CONFIRMS"]

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.90)

    # Should find at least 2 strong pairs (VALIDATES-VERIFIES, VALIDATES-CONFIRMS)
    # May find 3 if VERIFIES-CONFIRMS also matches strongly
    assert len(candidates) >= 2

    # Check strongest match
    strongest = candidates[0]
    assert strongest.similarity >= 0.90
    assert strongest.strength == SynonymStrength.STRONG
    assert strongest.is_strong_match is True
    assert strongest.needs_review is False


@pytest.mark.asyncio
async def test_find_synonyms_moderate_match(detector):
    """Test detection of moderate synonym matches (0.70-0.89)."""
    edge_types = ["VALIDATES", "CHECKS", "TESTS"]

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.70)

    # Should find VALIDATES-CHECKS (~0.87) and VALIDATES-TESTS (~0.85)
    assert len(candidates) >= 2

    # Check for moderate matches
    moderate_matches = [c for c in candidates if c.strength == SynonymStrength.MODERATE]
    assert len(moderate_matches) >= 2

    for match in moderate_matches:
        assert 0.70 <= match.similarity < 0.90
        assert match.is_strong_match is False
        assert match.needs_review is True


@pytest.mark.asyncio
async def test_find_synonyms_no_matches(detector):
    """Test with completely different edge types."""
    edge_types = ["VALIDATES", "IMPLIES"]

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.70)

    # Should find no matches (similarity ~0.0)
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_find_synonyms_sorted_by_similarity(detector):
    """Test that results are sorted by similarity (highest first)."""
    edge_types = ["VALIDATES", "VERIFIES", "CHECKS", "CONFIRMS"]

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.70)

    assert len(candidates) > 0

    # Check sorting
    for i in range(len(candidates) - 1):
        assert candidates[i].similarity >= candidates[i + 1].similarity


@pytest.mark.asyncio
async def test_find_synonyms_empty_list(detector):
    """Test with empty edge types list."""
    candidates = await detector.find_synonyms([], min_similarity=0.70)

    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_find_synonyms_single_type(detector):
    """Test with single edge type."""
    candidates = await detector.find_synonyms(["VALIDATES"], min_similarity=0.70)

    assert len(candidates) == 0


# ============================================================================
# Find Synonyms for Single Type Tests
# ============================================================================


@pytest.mark.asyncio
async def test_find_synonyms_for_type_strong_match(detector):
    """Test finding synonyms for a single edge type."""
    edge_type = "VALIDATES"
    existing_types = ["VERIFIES", "CONFIRMS", "CHECKS", "IMPLIES"]

    synonyms = await detector.find_synonyms_for_type(
        edge_type,
        existing_types,
        min_similarity=0.70
    )

    # Should find VERIFIES, CONFIRMS, and CHECKS (all >= 0.70)
    assert len(synonyms) >= 3

    # Check strongest match
    strongest = synonyms[0]
    assert strongest.type1 == edge_type
    assert strongest.type2 in existing_types
    assert strongest.similarity >= 0.90


@pytest.mark.asyncio
async def test_find_synonyms_for_type_no_matches(detector):
    """Test finding synonyms when none exist."""
    edge_type = "VALIDATES"
    existing_types = ["IMPLIES", "ENABLES"]  # Very different

    synonyms = await detector.find_synonyms_for_type(
        edge_type,
        existing_types,
        min_similarity=0.70
    )

    assert len(synonyms) == 0


@pytest.mark.asyncio
async def test_find_synonyms_for_type_sorted(detector):
    """Test that results are sorted by similarity."""
    edge_type = "VALIDATES"
    existing_types = ["VERIFIES", "CHECKS", "CONFIRMS"]

    synonyms = await detector.find_synonyms_for_type(
        edge_type,
        existing_types,
        min_similarity=0.70
    )

    # Check sorting
    for i in range(len(synonyms) - 1):
        assert synonyms[i].similarity >= synonyms[i + 1].similarity


# ============================================================================
# Merge Recommendation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_suggest_merge_by_value_score(detector):
    """Test merge suggestion based on value scores."""
    recommendation = await detector.suggest_merge(
        "VALIDATES", "VERIFIES",
        type1_edge_count=100, type2_edge_count=50,
        type1_value_score=45.0, type2_value_score=20.0
    )

    assert isinstance(recommendation, MergeRecommendation)
    assert recommendation.preserve_type == "VALIDATES"  # Higher value score
    assert recommendation.deprecate_type == "VERIFIES"
    assert recommendation.affected_edges == 150
    assert recommendation.similarity >= 0.90
    assert "value score" in recommendation.reasoning.lower()


@pytest.mark.asyncio
async def test_suggest_merge_by_edge_count(detector):
    """Test merge suggestion based on edge count (no value scores)."""
    recommendation = await detector.suggest_merge(
        "VALIDATES", "VERIFIES",
        type1_edge_count=120, type2_edge_count=30
    )

    assert recommendation.preserve_type == "VALIDATES"  # More edges
    assert recommendation.deprecate_type == "VERIFIES"
    assert recommendation.affected_edges == 150
    assert "more edges" in recommendation.reasoning.lower()


@pytest.mark.asyncio
async def test_suggest_merge_reverse_by_edge_count(detector):
    """Test merge suggestion when type2 has more edges."""
    recommendation = await detector.suggest_merge(
        "VALIDATES", "VERIFIES",
        type1_edge_count=30, type2_edge_count=120
    )

    assert recommendation.preserve_type == "VERIFIES"  # More edges
    assert recommendation.deprecate_type == "VALIDATES"


@pytest.mark.asyncio
async def test_suggest_merge_alphabetical_tiebreaker(detector):
    """Test merge suggestion with alphabetical tiebreaker."""
    recommendation = await detector.suggest_merge(
        "VERIFIES", "VALIDATES",
        type1_edge_count=50, type2_edge_count=50,  # Same count
        type1_value_score=25.0, type2_value_score=25.0  # Same score
    )

    assert recommendation.preserve_type == "VALIDATES"  # Alphabetically first
    assert recommendation.deprecate_type == "VERIFIES"
    assert "alphabetical" in recommendation.reasoning.lower()


@pytest.mark.asyncio
async def test_suggest_merge_value_score_overrides_edge_count(detector):
    """Test that value score takes priority over edge count."""
    recommendation = await detector.suggest_merge(
        "VALIDATES", "VERIFIES",
        type1_edge_count=50, type2_edge_count=200,  # type2 has more edges
        type1_value_score=100.0, type2_value_score=30.0  # But type1 has higher value
    )

    assert recommendation.preserve_type == "VALIDATES"  # Higher value score wins
    assert recommendation.deprecate_type == "VERIFIES"
    assert "value score" in recommendation.reasoning.lower()


# ============================================================================
# Batch Duplicate Detection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batch_detect_duplicates_strong_only(detector):
    """Test batch duplicate detection with strong matches only."""
    edge_types = ["VALIDATES", "VERIFIES", "CONFIRMS", "CHECKS", "IMPLIES"]

    clusters = await detector.batch_detect_duplicates(edge_types, strong_only=True)

    # Should find clusters around VALIDATES (with VERIFIES and CONFIRMS)
    assert len(clusters) > 0

    # VALIDATES should have synonyms
    if "VALIDATES" in clusters:
        assert len(clusters["VALIDATES"]) >= 2
        assert "VERIFIES" in clusters["VALIDATES"]
        assert "CONFIRMS" in clusters["VALIDATES"]


@pytest.mark.asyncio
async def test_batch_detect_duplicates_all_matches(detector):
    """Test batch duplicate detection with moderate and strong matches."""
    edge_types = ["VALIDATES", "VERIFIES", "CHECKS", "IMPLIES"]

    clusters = await detector.batch_detect_duplicates(edge_types, strong_only=False)

    # Should find more clusters with moderate threshold (>= 0.70)
    assert len(clusters) > 0

    # VALIDATES should have multiple synonyms
    if "VALIDATES" in clusters:
        # Should include VERIFIES (strong) and CHECKS (moderate)
        assert len(clusters["VALIDATES"]) >= 2


@pytest.mark.asyncio
async def test_batch_detect_duplicates_no_duplicates(detector):
    """Test batch duplicate detection with completely different types."""
    edge_types = ["IMPLIES", "ENABLES"]

    clusters = await detector.batch_detect_duplicates(edge_types, strong_only=False)

    # Should find no clusters
    assert len(clusters) == 0


@pytest.mark.asyncio
async def test_batch_detect_duplicates_sorted_lists(detector):
    """Test that cluster lists are sorted."""
    edge_types = ["VALIDATES", "VERIFIES", "CONFIRMS", "CHECKS"]

    clusters = await detector.batch_detect_duplicates(edge_types, strong_only=False)

    # Check that all lists are sorted
    for primary, synonyms in clusters.items():
        assert synonyms == sorted(synonyms)


# ============================================================================
# Threshold Tests
# ============================================================================


@pytest.mark.asyncio
async def test_strong_threshold_boundary(detector):
    """Test behavior at strong match threshold boundary (0.90)."""
    edge_types = ["VALIDATES", "VERIFIES"]  # Should be >= 0.90

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.89)

    assert len(candidates) == 1

    candidate = candidates[0]

    # Check threshold classification
    if candidate.similarity >= 0.90:
        assert candidate.strength == SynonymStrength.STRONG
        assert candidate.is_strong_match is True
    else:
        # If just below 0.90 due to floating point
        assert candidate.strength == SynonymStrength.MODERATE
        assert candidate.is_strong_match is False


@pytest.mark.asyncio
async def test_moderate_threshold_boundary(detector):
    """Test behavior at moderate match threshold boundary (0.70)."""
    # Create candidates near 0.70 threshold
    edge_types = ["VALIDATES", "CHECKS"]  # Should be around 0.87

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.69)

    assert len(candidates) >= 1

    for candidate in candidates:
        if candidate.similarity >= 0.90:
            assert candidate.strength == SynonymStrength.STRONG
        elif candidate.similarity >= 0.70:
            assert candidate.strength == SynonymStrength.MODERATE
        else:
            assert candidate.strength == SynonymStrength.WEAK


# ============================================================================
# Cosine Similarity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cosine_similarity_identical_vectors(detector):
    """Test cosine similarity of identical vectors."""
    vec = np.array([1.0, 0.0, 0.0])

    similarity = detector._cosine_similarity(vec, vec)

    assert abs(similarity - 1.0) < 0.001


@pytest.mark.asyncio
async def test_cosine_similarity_orthogonal_vectors(detector):
    """Test cosine similarity of orthogonal vectors."""
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([0.0, 1.0, 0.0])

    similarity = detector._cosine_similarity(vec1, vec2)

    assert abs(similarity - 0.0) < 0.001


@pytest.mark.asyncio
async def test_cosine_similarity_zero_vectors(detector):
    """Test cosine similarity with zero vectors."""
    vec1 = np.array([0.0, 0.0, 0.0])
    vec2 = np.array([1.0, 0.0, 0.0])

    similarity = detector._cosine_similarity(vec1, vec2)

    assert similarity == 0.0


# ============================================================================
# Caching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_embedding_caching(detector):
    """Test that embeddings are cached to reduce API calls."""
    edge_type = "VALIDATES"

    # First call - should hit provider
    embedding1 = await detector._get_edge_type_embedding(edge_type)

    # Second call - should use cache
    embedding2 = await detector._get_edge_type_embedding(edge_type)

    # Should be same object
    assert np.array_equal(embedding1, embedding2)

    # Check cache contains entry
    assert edge_type in detector._embedding_cache


@pytest.mark.asyncio
async def test_clear_cache(detector):
    """Test cache clearing."""
    edge_type = "VALIDATES"

    # Generate embedding
    await detector._get_edge_type_embedding(edge_type)

    assert len(detector._embedding_cache) > 0

    # Clear cache
    detector.clear_cache()

    assert len(detector._embedding_cache) == 0


# ============================================================================
# Utility Function Tests
# ============================================================================


def test_filter_by_strength_strong():
    """Test filtering by STRONG strength."""
    candidates = [
        SynonymCandidate("A", "B", 0.95, SynonymStrength.STRONG, True, False, ""),
        SynonymCandidate("C", "D", 0.75, SynonymStrength.MODERATE, False, True, ""),
        SynonymCandidate("E", "F", 0.92, SynonymStrength.STRONG, True, False, ""),
    ]

    strong = filter_by_strength(candidates, SynonymStrength.STRONG)

    assert len(strong) == 2
    assert all(c.strength == SynonymStrength.STRONG for c in strong)


def test_filter_by_strength_moderate():
    """Test filtering by MODERATE strength."""
    candidates = [
        SynonymCandidate("A", "B", 0.95, SynonymStrength.STRONG, True, False, ""),
        SynonymCandidate("C", "D", 0.75, SynonymStrength.MODERATE, False, True, ""),
        SynonymCandidate("E", "F", 0.80, SynonymStrength.MODERATE, False, True, ""),
    ]

    moderate = filter_by_strength(candidates, SynonymStrength.MODERATE)

    assert len(moderate) == 2
    assert all(c.strength == SynonymStrength.MODERATE for c in moderate)


def test_get_merge_graph():
    """Test building merge graph from candidates."""
    candidates = [
        SynonymCandidate("VALIDATES", "VERIFIES", 0.95, SynonymStrength.STRONG, True, False, ""),
        SynonymCandidate("VALIDATES", "CHECKS", 0.85, SynonymStrength.MODERATE, False, True, ""),
        SynonymCandidate("CONFIRMS", "TESTS", 0.92, SynonymStrength.STRONG, True, False, ""),
    ]

    graph = get_merge_graph(candidates)

    assert "VALIDATES" in graph
    assert "VERIFIES" in graph["VALIDATES"]
    assert "CHECKS" in graph["VALIDATES"]

    assert "VERIFIES" in graph
    assert "VALIDATES" in graph["VERIFIES"]

    assert "CONFIRMS" in graph
    assert "TESTS" in graph["CONFIRMS"]


def test_get_merge_graph_empty():
    """Test building merge graph from empty list."""
    graph = get_merge_graph([])

    assert len(graph) == 0


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_find_synonyms_self_comparison_avoided(detector):
    """Test that types don't compare with themselves."""
    edge_types = ["VALIDATES", "VALIDATES"]  # Duplicate

    candidates = await detector.find_synonyms(edge_types, min_similarity=0.70)

    # Should not create self-comparison
    for candidate in candidates:
        assert candidate.type1 != candidate.type2


@pytest.mark.asyncio
async def test_find_synonyms_for_type_excludes_self(detector):
    """Test that find_synonyms_for_type excludes self-match."""
    edge_type = "VALIDATES"
    existing_types = ["VALIDATES", "VERIFIES", "CHECKS"]

    synonyms = await detector.find_synonyms_for_type(
        edge_type,
        existing_types,
        min_similarity=0.0  # Include all
    )

    # Should not include self-match
    for synonym in synonyms:
        assert synonym.type2 != edge_type


@pytest.mark.asyncio
async def test_synonym_candidate_repr():
    """Test SynonymCandidate string representation."""
    candidate = SynonymCandidate(
        "VALIDATES", "VERIFIES",
        0.95, SynonymStrength.STRONG,
        True, False,
        "Test reasoning"
    )

    repr_str = repr(candidate)

    assert "VALIDATES" in repr_str
    assert "VERIFIES" in repr_str
    assert "0.95" in repr_str or "0.950" in repr_str
    assert "strong" in repr_str


@pytest.mark.asyncio
async def test_merge_recommendation_repr():
    """Test MergeRecommendation string representation."""
    recommendation = MergeRecommendation(
        "VALIDATES", "VERIFIES",
        0.95, 150,
        "Test reasoning"
    )

    repr_str = repr(recommendation)

    assert "VALIDATES" in repr_str
    assert "VERIFIES" in repr_str
    assert "150" in repr_str
