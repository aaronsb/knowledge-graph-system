"""
Unit tests for category_classifier.py module.

Tests embedding-based category classification for automatic edge vocabulary
expansion (ADR-032).

Test Coverage:
- CategoryClassification dataclass
- CategoryClassifier classification logic
- Confidence thresholds (>= 0.3 assign, < 0.3 new)
- Category limit checking (8-15 range)
- Protected category enforcement
- Batch classification
- Utility functions
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from api.app.lib.category_classifier import (
    CategoryClassification,
    CategoryClassifier,
    get_category_for_edge_type,
    get_edge_types_in_category,
)


# ============================================================================
# CategoryClassification Dataclass Tests
# ============================================================================


class TestCategoryClassification:
    """Test suite for CategoryClassification dataclass"""

    def test_create_classification_assign(self):
        """Test creating classification for existing category assignment"""
        result = CategoryClassification(
            edge_type="VALIDATES",
            best_match_category="evidential",
            confidence=0.85,
            all_scores={"evidential": 0.85, "logical_truth": 0.45},
            should_create_new=False,
            suggested_category=None,
            reasoning="Good fit to 'evidential'"
        )

        assert result.edge_type == "VALIDATES"
        assert result.best_match_category == "evidential"
        assert result.confidence == 0.85
        assert result.should_create_new is False
        assert result.suggested_category is None

    def test_create_classification_new_category(self):
        """Test creating classification for new category proposal"""
        result = CategoryClassification(
            edge_type="MONITORS",
            best_match_category=None,
            confidence=0.15,
            all_scores={"causal": 0.15, "functional": 0.12},
            should_create_new=True,
            suggested_category="observational",
            reasoning="No good fit, suggest new"
        )

        assert result.edge_type == "MONITORS"
        assert result.best_match_category is None
        assert result.confidence == 0.15
        assert result.should_create_new is True
        assert result.suggested_category == "observational"

    def test_classification_repr(self):
        """Test string representation"""
        result_assign = CategoryClassification(
            "TEST", "causal", 0.75, {}, False, None, "Good fit"
        )
        repr_str = repr(result_assign)
        assert "TEST" in repr_str
        assert "causal" in repr_str
        assert "0.75" in repr_str

        result_new = CategoryClassification(
            "TEST", None, 0.15, {}, True, "new_cat", "No fit"
        )
        repr_str_new = repr(result_new)
        assert "NEW" in repr_str_new
        assert "new_cat" in repr_str_new


# ============================================================================
# CategoryClassifier Tests
# ============================================================================


class TestCategoryClassifier:
    """Test suite for CategoryClassifier class"""

    @pytest.fixture
    def mock_ai_provider(self):
        """Provide mock AI provider with embedding generation"""
        provider = MagicMock()
        provider.generate_embedding = AsyncMock()
        return provider

    @pytest.fixture
    def classifier(self, mock_ai_provider):
        """Provide CategoryClassifier instance"""
        return CategoryClassifier(mock_ai_provider)

    def test_classifier_initialization(self, mock_ai_provider):
        """Test CategoryClassifier initialization"""
        classifier = CategoryClassifier(mock_ai_provider)
        assert classifier.ai_provider == mock_ai_provider
        assert classifier.GOOD_FIT_THRESHOLD == 0.3
        assert classifier.CATEGORY_MAX == 15
        assert len(classifier.PROTECTED_CATEGORIES) == 8

    def test_cosine_similarity(self, classifier):
        """Test cosine similarity calculation"""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        similarity = classifier._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001  # Identical vectors

        vec3 = np.array([1.0, 0.0, 0.0])
        vec4 = np.array([0.0, 1.0, 0.0])
        similarity2 = classifier._cosine_similarity(vec3, vec4)
        assert abs(similarity2 - 0.0) < 0.001  # Orthogonal vectors

        vec5 = np.array([1.0, 1.0, 0.0])
        vec6 = np.array([1.0, 1.0, 0.0])
        similarity3 = classifier._cosine_similarity(vec5, vec6)
        assert abs(similarity3 - 1.0) < 0.001  # Identical non-unit vectors

    def test_cosine_similarity_zero_vectors(self, classifier):
        """Test cosine similarity with zero vectors"""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        similarity = classifier._cosine_similarity(vec1, vec2)
        assert similarity == 0.0  # Zero vector should give 0

    def test_edge_type_to_text(self, classifier):
        """Test converting edge type to descriptive text"""
        text = classifier._edge_type_to_text("VALIDATES")
        assert "validates" in text.lower()
        assert "relationship" in text.lower()

        text2 = classifier._edge_type_to_text("RESULTS_FROM")
        assert "results from" in text2.lower()

    def test_category_to_text(self, classifier):
        """Test converting category to descriptive text"""
        text = classifier._category_to_text("causal")
        assert "causal" in text.lower()
        assert "relationships" in text.lower()
        # Should include example edge types
        assert any(word in text.lower() for word in ["causes", "enables", "prevents"])

    @pytest.mark.asyncio
    async def test_get_edge_type_embedding(self, classifier, mock_ai_provider):
        """Test generating embedding for edge type"""
        # Mock embedding response
        mock_ai_provider.generate_embedding.return_value = {
            "embedding": [0.1, 0.2, 0.3],
            "tokens": 10
        }

        embedding = await classifier._get_edge_type_embedding("VALIDATES")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 3
        assert embedding[0] == 0.1

        # Verify provider was called with descriptive text
        mock_ai_provider.generate_embedding.assert_called_once()
        call_text = mock_ai_provider.generate_embedding.call_args[0][0]
        assert "validates" in call_text.lower()

    @pytest.mark.asyncio
    async def test_get_category_embedding_with_caching(self, classifier, mock_ai_provider):
        """Test category embedding generation with caching"""
        mock_ai_provider.generate_embedding.return_value = {
            "embedding": [0.5, 0.5, 0.5],
            "tokens": 10
        }

        # First call - should hit provider
        embedding1 = await classifier._get_category_embedding("causal")
        assert mock_ai_provider.generate_embedding.call_count == 1

        # Second call - should use cache
        embedding2 = await classifier._get_category_embedding("causal")
        assert mock_ai_provider.generate_embedding.call_count == 1  # Not called again

        # Verify cached result
        assert np.array_equal(embedding1, embedding2)

    @pytest.mark.asyncio
    async def test_classify_edge_type_good_fit(self, classifier, mock_ai_provider):
        """Test classification when good fit found (>= 0.3)"""
        # Mock embeddings
        edge_embedding = np.array([1.0, 0.0, 0.0])
        category_embedding = np.array([0.9, 0.1, 0.0])  # High similarity

        mock_ai_provider.generate_embedding.side_effect = [
            {"embedding": edge_embedding.tolist(), "tokens": 10},
            {"embedding": category_embedding.tolist(), "tokens": 10},
        ]

        result = await classifier.classify_edge_type("VALIDATES", ["evidential"])

        assert result.edge_type == "VALIDATES"
        assert result.best_match_category == "evidential"
        assert result.confidence > 0.3  # Good fit threshold
        assert result.should_create_new is False
        assert result.suggested_category is None

    @pytest.mark.asyncio
    async def test_classify_edge_type_no_good_fit(self, classifier, mock_ai_provider):
        """Test classification when no good fit (< 0.3 for all)"""
        # Mock embeddings - orthogonal (low similarity)
        edge_embedding = np.array([1.0, 0.0, 0.0])
        category_embedding = np.array([0.0, 1.0, 0.0])  # Orthogonal = 0.0 similarity

        mock_ai_provider.generate_embedding.side_effect = [
            {"embedding": edge_embedding.tolist(), "tokens": 10},
            {"embedding": category_embedding.tolist(), "tokens": 10},
        ]

        result = await classifier.classify_edge_type("MONITORS", ["causal"])

        assert result.edge_type == "MONITORS"
        assert result.best_match_category is None
        assert result.confidence < 0.3  # Below threshold
        assert result.should_create_new is True
        assert result.suggested_category is not None

    @pytest.mark.asyncio
    async def test_classify_edge_type_multiple_categories(self, classifier, mock_ai_provider):
        """Test classification against multiple categories"""
        # Mock embeddings for edge type and multiple categories
        edge_embedding = np.array([1.0, 0.0, 0.0])

        # Category embeddings with varying similarity
        # For cosine similarity: dot(v1, v2) / (||v1|| * ||v2||)
        cat1_embedding = np.array([0.5, 0.866, 0.0])  # ~0.5 similarity (60°)
        cat2_embedding = np.array([0.95, 0.312, 0.0])  # ~0.95 similarity (18°) - HIGHEST
        cat3_embedding = np.array([0.7, 0.714, 0.0])  # ~0.7 similarity (45°)

        mock_ai_provider.generate_embedding.side_effect = [
            {"embedding": edge_embedding.tolist(), "tokens": 10},
            {"embedding": cat1_embedding.tolist(), "tokens": 10},
            {"embedding": cat2_embedding.tolist(), "tokens": 10},
            {"embedding": cat3_embedding.tolist(), "tokens": 10},
        ]

        result = await classifier.classify_edge_type(
            "TEST_TYPE",
            ["category1", "category2", "category3"]
        )

        # Should pick category2 (highest similarity)
        assert result.best_match_category == "category2"
        assert "category1" in result.all_scores
        assert "category2" in result.all_scores
        assert "category3" in result.all_scores
        # Verify category2 has highest score
        assert result.all_scores["category2"] > result.all_scores["category1"]
        assert result.all_scores["category2"] > result.all_scores["category3"]

    @pytest.mark.asyncio
    async def test_classify_edge_type_default_categories(self, classifier, mock_ai_provider):
        """Test classification uses default RELATIONSHIP_CATEGORIES if not specified"""
        # Mock single high-similarity category
        edge_embedding = np.array([1.0, 0.0, 0.0])
        category_embedding = np.array([0.95, 0.0, 0.0])

        # Need to mock multiple calls (one per category in RELATIONSHIP_CATEGORIES)
        mock_ai_provider.generate_embedding.side_effect = [
            {"embedding": edge_embedding.tolist(), "tokens": 10},
        ] + [
            {"embedding": category_embedding.tolist(), "tokens": 10}
        ] * 10  # Enough for all categories

        result = await classifier.classify_edge_type("TEST_TYPE")

        # Should use default categories
        assert result.best_match_category is not None
        assert len(result.all_scores) >= 8  # At least the 8 core categories

    @pytest.mark.asyncio
    async def test_suggest_category_name_patterns(self, classifier):
        """Test category name suggestion based on edge type patterns"""
        # Test observational pattern
        name = await classifier._suggest_category_name("MONITORS")
        assert name == "observational"

        # Test validation pattern
        name2 = await classifier._suggest_category_name("VALIDATES")
        assert name2 == "validation"

        # Test constraint pattern
        name3 = await classifier._suggest_category_name("RESTRICTS")
        assert name3 == "constraint"

        # Test enhancement pattern
        name4 = await classifier._suggest_category_name("ENHANCES")
        assert name4 == "enhancement"

        # Test associative pattern
        name5 = await classifier._suggest_category_name("CONNECTS")
        assert name5 == "associative"

        # Test default pattern
        name6 = await classifier._suggest_category_name("UNKNOWN_TYPE")
        assert "unknown" in name6

    @pytest.mark.asyncio
    async def test_batch_classify(self, classifier, mock_ai_provider):
        """Test batch classification of multiple edge types"""
        # Mock embeddings
        mock_ai_provider.generate_embedding.side_effect = [
            {"embedding": [1.0, 0.0, 0.0], "tokens": 10},  # Edge type 1
            {"embedding": [0.9, 0.1, 0.0], "tokens": 10},  # Category
            {"embedding": [0.0, 1.0, 0.0], "tokens": 10},  # Edge type 2
            {"embedding": [0.1, 0.9, 0.0], "tokens": 10},  # Category
        ]

        results = await classifier.batch_classify(
            ["TYPE1", "TYPE2"],
            ["test_category"]
        )

        assert len(results) == 2
        assert "TYPE1" in results
        assert "TYPE2" in results
        assert isinstance(results["TYPE1"], CategoryClassification)
        assert isinstance(results["TYPE2"], CategoryClassification)

    def test_check_category_limits(self, classifier):
        """Test category limit checking"""
        # Below minimum
        limits = classifier.check_category_limits(5)
        assert limits["below_min"] is True
        assert limits["can_add"] is True
        assert limits["at_max"] is False

        # At merge threshold
        limits2 = classifier.check_category_limits(12)
        assert limits2["should_merge"] is True
        assert limits2["can_add"] is True
        assert limits2["at_max"] is False

        # At maximum
        limits3 = classifier.check_category_limits(15)
        assert limits3["at_max"] is True
        assert limits3["can_add"] is False
        assert limits3["space_remaining"] == 0

        # Above maximum
        limits4 = classifier.check_category_limits(20)
        assert limits4["at_max"] is True
        assert limits4["space_remaining"] == 0

    def test_is_protected_category(self, classifier):
        """Test protected category checking"""
        # Core protected categories
        assert classifier.is_protected_category("logical_truth") is True
        assert classifier.is_protected_category("causal") is True
        assert classifier.is_protected_category("structural") is True
        assert classifier.is_protected_category("evidential") is True
        assert classifier.is_protected_category("similarity") is True
        assert classifier.is_protected_category("temporal") is True
        assert classifier.is_protected_category("functional") is True
        assert classifier.is_protected_category("meta") is True

        # Custom categories
        assert classifier.is_protected_category("custom_category") is False
        assert classifier.is_protected_category("observational") is False


# ============================================================================
# Utility Function Tests
# ============================================================================


class TestUtilityFunctions:
    """Test suite for utility functions"""

    def test_get_category_for_edge_type(self):
        """Test getting category for known edge type"""
        # Known edge types
        assert get_category_for_edge_type("CAUSES") == "causal"
        assert get_category_for_edge_type("IMPLIES") == "logical_truth"
        assert get_category_for_edge_type("SUPPORTS") == "evidential"
        assert get_category_for_edge_type("PART_OF") == "structural"

        # Unknown edge type
        assert get_category_for_edge_type("UNKNOWN_TYPE") is None

    def test_get_edge_types_in_category(self):
        """Test getting all edge types in a category"""
        # Known category
        types = get_edge_types_in_category("causal")
        assert len(types) > 0
        assert "CAUSES" in types
        assert "ENABLES" in types

        # Unknown category
        types2 = get_edge_types_in_category("nonexistent")
        assert types2 == []


# ============================================================================
# Integration Tests
# ============================================================================


class TestCategoryClassifierIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_full_classification_workflow_assign(self):
        """Test complete workflow for assigning to existing category"""
        mock_provider = MagicMock()
        mock_provider.generate_embedding = AsyncMock()

        # Create classifier
        classifier = CategoryClassifier(mock_provider)

        # Mock embeddings with high similarity
        edge_emb = np.array([1.0, 0.5, 0.2])
        cat_emb = np.array([0.95, 0.48, 0.19])  # Very similar

        mock_provider.generate_embedding.side_effect = [
            {"embedding": edge_emb.tolist(), "tokens": 10},
            {"embedding": cat_emb.tolist(), "tokens": 10},
        ]

        # Classify
        result = await classifier.classify_edge_type("NEW_TYPE", ["target_category"])

        # Verify assignment
        assert result.should_create_new is False
        assert result.best_match_category == "target_category"
        assert result.confidence >= 0.3

    @pytest.mark.asyncio
    async def test_full_classification_workflow_new_category(self):
        """Test complete workflow for proposing new category"""
        mock_provider = MagicMock()
        mock_provider.generate_embedding = AsyncMock()

        classifier = CategoryClassifier(mock_provider)

        # Mock embeddings with low similarity (orthogonal)
        edge_emb = np.array([1.0, 0.0, 0.0])
        cat_emb = np.array([0.0, 1.0, 0.0])

        mock_provider.generate_embedding.side_effect = [
            {"embedding": edge_emb.tolist(), "tokens": 10},
            {"embedding": cat_emb.tolist(), "tokens": 10},
        ]

        # Classify
        result = await classifier.classify_edge_type("MONITORS", ["causal"])

        # Verify new category proposal
        assert result.should_create_new is True
        assert result.best_match_category is None
        assert result.suggested_category is not None
        assert result.confidence < 0.3

    @pytest.mark.asyncio
    async def test_category_limit_enforcement(self):
        """Test that category limits are properly checked"""
        mock_provider = MagicMock()
        classifier = CategoryClassifier(mock_provider)

        # Check various scenarios
        limits_ok = classifier.check_category_limits(10)
        assert limits_ok["can_add"] is True

        limits_at_threshold = classifier.check_category_limits(12)
        assert limits_at_threshold["should_merge"] is True
        assert limits_at_threshold["can_add"] is True

        limits_at_max = classifier.check_category_limits(15)
        assert limits_at_max["at_max"] is True
        assert limits_at_max["can_add"] is False

    @pytest.mark.asyncio
    async def test_threshold_boundary_conditions(self):
        """Test classification at exact threshold boundaries"""
        mock_provider = MagicMock()
        mock_provider.generate_embedding = AsyncMock()
        classifier = CategoryClassifier(mock_provider)

        # Test at exact threshold (0.3)
        # For unit vectors: cos(θ) = dot product
        # cos(72.54°) ≈ 0.3
        edge_emb = np.array([1.0, 0.0, 0.0])

        # Create normalized vector with ~0.3 x-component
        # Using normalized [0.3, 0.954, 0] gives cosine similarity of 0.3
        cat_emb_normalized = np.array([0.3, 0.954, 0.0])
        # Normalize to unit vector
        cat_emb = cat_emb_normalized / np.linalg.norm(cat_emb_normalized)

        mock_provider.generate_embedding.side_effect = [
            {"embedding": edge_emb.tolist(), "tokens": 10},
            {"embedding": cat_emb.tolist(), "tokens": 10},
        ]

        result = await classifier.classify_edge_type("BOUNDARY_TYPE", ["test_category"])

        # At ~0.3, should assign (>= 0.3 threshold)
        # Note: Due to floating point precision, we check result not exact value
        if result.confidence >= 0.3:
            assert result.should_create_new is False
        else:
            # If slightly below due to floating point, should propose new
            assert result.should_create_new is True
            assert result.confidence < 0.31  # Close to threshold


if __name__ == "__main__":
    # Allow running tests directly: python test_category_classifier.py
    pytest.main([__file__, "-v"])
