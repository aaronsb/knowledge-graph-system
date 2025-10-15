"""
Unit tests for vocabulary_scoring.py module.

Tests value score calculation, bridge detection, and trend analysis for
automatic edge vocabulary expansion (ADR-032).

Test Coverage:
- EdgeTypeScore dataclass
- VocabularyScorer value score calculation
- Bridge detection logic
- Trend calculation
- Low-value type filtering
- Zero-edge type detection
- Score comparison utilities
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.lib.vocabulary_scoring import (
    EdgeTypeScore,
    VocabularyScorer,
    compare_scores,
)


# ============================================================================
# EdgeTypeScore Dataclass Tests
# ============================================================================


class TestEdgeTypeScore:
    """Test suite for EdgeTypeScore dataclass"""

    def test_create_score(self):
        """Test creating an EdgeTypeScore instance"""
        score = EdgeTypeScore(
            relationship_type="IMPLIES",
            edge_count=100,
            avg_traversal=50.5,
            bridge_count=5,
            trend=12.3,
            value_score=125.5,
            is_builtin=True,
            last_used=datetime.now()
        )

        assert score.relationship_type == "IMPLIES"
        assert score.edge_count == 100
        assert score.avg_traversal == 50.5
        assert score.bridge_count == 5
        assert score.trend == 12.3
        assert score.value_score == 125.5
        assert score.is_builtin is True
        assert isinstance(score.last_used, datetime)

    def test_score_with_none_last_used(self):
        """Test EdgeTypeScore with None last_used (never used type)"""
        score = EdgeTypeScore(
            relationship_type="UNUSED_TYPE",
            edge_count=0,
            avg_traversal=0.0,
            bridge_count=0,
            trend=0.0,
            value_score=0.0,
            is_builtin=False,
            last_used=None
        )

        assert score.last_used is None
        assert score.edge_count == 0

    def test_score_repr(self):
        """Test string representation of EdgeTypeScore"""
        score = EdgeTypeScore(
            relationship_type="SUPPORTS",
            edge_count=50,
            avg_traversal=25.0,
            bridge_count=3,
            trend=5.0,
            value_score=62.5,
            is_builtin=False,
            last_used=None
        )

        repr_str = repr(score)
        assert "EdgeTypeScore" in repr_str
        assert "SUPPORTS" in repr_str
        assert "score=62.5" in repr_str or "score=62.50" in repr_str
        assert "edges=50" in repr_str


# ============================================================================
# VocabularyScorer Tests
# ============================================================================


class TestVocabularyScorer:
    """Test suite for VocabularyScorer class"""

    @pytest.fixture
    def mock_db(self):
        """Provide mock database client"""
        db = MagicMock()
        db.execute_query = AsyncMock()
        return db

    @pytest.fixture
    def scorer(self, mock_db):
        """Provide VocabularyScorer instance with mock database"""
        return VocabularyScorer(mock_db)

    def test_scorer_initialization(self, mock_db):
        """Test VocabularyScorer initialization"""
        scorer = VocabularyScorer(mock_db)
        assert scorer.db == mock_db
        assert scorer.BRIDGE_SOURCE_THRESHOLD == 10
        assert scorer.BRIDGE_DEST_THRESHOLD == 100

    def test_calculate_value_score_base(self, scorer):
        """Test value score calculation with base values"""
        score = scorer._calculate_value_score(
            edge_count=100,
            avg_traversal=50.0,
            bridge_count=5,
            trend=10.0
        )

        # Expected: 100×1.0 + (50/100)×0.5 + (5/10)×0.3 + 10×0.2
        # = 100 + 0.25 + 0.15 + 2.0 = 102.4
        assert abs(score - 102.4) < 0.01

    def test_calculate_value_score_zero_values(self, scorer):
        """Test value score with all zero values"""
        score = scorer._calculate_value_score(
            edge_count=0,
            avg_traversal=0.0,
            bridge_count=0,
            trend=0.0
        )

        assert score == 0.0

    def test_calculate_value_score_negative_trend(self, scorer):
        """Test that negative trends are treated as zero"""
        score_negative = scorer._calculate_value_score(
            edge_count=50,
            avg_traversal=10.0,
            bridge_count=2,
            trend=-5.0  # Negative trend
        )

        score_zero = scorer._calculate_value_score(
            edge_count=50,
            avg_traversal=10.0,
            bridge_count=2,
            trend=0.0  # Zero trend
        )

        # Negative trend should be treated as zero
        assert score_negative == score_zero

    def test_calculate_value_score_high_traversal(self, scorer):
        """Test value score with high traversal rate"""
        score = scorer._calculate_value_score(
            edge_count=10,
            avg_traversal=500.0,  # Very high traversal
            bridge_count=1,
            trend=5.0
        )

        # Traversal component: (500/100) × 0.5 = 2.5
        # Total: 10 + 2.5 + 0.03 + 1.0 = 13.53
        assert score > 13.0
        assert score < 14.0

    def test_calculate_value_score_many_bridges(self, scorer):
        """Test value score with many bridge edges"""
        score = scorer._calculate_value_score(
            edge_count=20,
            avg_traversal=10.0,
            bridge_count=50,  # Many bridges
            trend=2.0
        )

        # Bridge component: (50/10) × 0.3 = 1.5
        assert score > 21.0  # Significant bridge contribution

    @pytest.mark.asyncio
    async def test_get_edge_metrics(self, scorer, mock_db):
        """Test querying edge metrics from database"""
        # Mock database response
        mock_db.execute_query.return_value = [
            {
                "relationship_type": "IMPLIES",
                "edge_count": 100,
                "avg_traversal": 50.5,
                "last_used": datetime.now()
            },
            {
                "relationship_type": "SUPPORTS",
                "edge_count": 75,
                "avg_traversal": 25.0,
                "last_used": None
            }
        ]

        metrics = await scorer._get_edge_metrics()

        assert "IMPLIES" in metrics
        assert metrics["IMPLIES"]["edge_count"] == 100
        assert metrics["IMPLIES"]["avg_traversal"] == 50.5

        assert "SUPPORTS" in metrics
        assert metrics["SUPPORTS"]["edge_count"] == 75

    @pytest.mark.asyncio
    async def test_get_edge_metrics_empty_database(self, scorer, mock_db):
        """Test edge metrics with empty database"""
        mock_db.execute_query.return_value = []

        metrics = await scorer._get_edge_metrics()

        assert metrics == {}

    @pytest.mark.asyncio
    async def test_get_edge_metrics_database_error(self, scorer, mock_db):
        """Test edge metrics when database query fails"""
        mock_db.execute_query.side_effect = Exception("Database error")

        metrics = await scorer._get_edge_metrics()

        assert metrics == {}  # Should return empty dict on error

    @pytest.mark.asyncio
    async def test_detect_bridges(self, scorer, mock_db):
        """Test bridge detection logic"""
        # Mock database response
        mock_db.execute_query.return_value = [
            {"relationship_type": "IMPLIES", "bridge_count": 5},
            {"relationship_type": "SUPPORTS", "bridge_count": 3}
        ]

        bridges = await scorer._detect_bridges()

        assert bridges["IMPLIES"] == 5
        assert bridges["SUPPORTS"] == 3

    @pytest.mark.asyncio
    async def test_detect_bridges_none_found(self, scorer, mock_db):
        """Test bridge detection when no bridges exist"""
        mock_db.execute_query.return_value = []

        bridges = await scorer._detect_bridges()

        assert bridges == {}

    @pytest.mark.asyncio
    async def test_calculate_trends(self, scorer, mock_db):
        """Test trend calculation based on usage variation"""
        # Mock database response
        mock_db.execute_query.return_value = [
            {
                "relationship_type": "ACTIVE_TYPE",
                "avg_usage": 100.0,
                "usage_variation": 50.0  # High variation = active
            },
            {
                "relationship_type": "STABLE_TYPE",
                "avg_usage": 50.0,
                "usage_variation": 10.0  # Low variation = stable
            }
        ]

        trends = await scorer._calculate_trends()

        # ACTIVE_TYPE: Higher trend due to high variation
        assert trends["ACTIVE_TYPE"] > trends["STABLE_TYPE"]
        assert trends["ACTIVE_TYPE"] > 0

    @pytest.mark.asyncio
    async def test_calculate_trends_zero_usage(self, scorer, mock_db):
        """Test trend when type has zero usage"""
        mock_db.execute_query.return_value = [
            {
                "relationship_type": "UNUSED_TYPE",
                "avg_usage": 0.0,
                "usage_variation": 0.0
            }
        ]

        trends = await scorer._calculate_trends()

        # Zero usage = zero trend
        assert trends["UNUSED_TYPE"] == 0.0

    @pytest.mark.asyncio
    async def test_get_vocabulary_metadata(self, scorer, mock_db):
        """Test getting vocabulary metadata"""
        mock_db.execute_query.return_value = [
            {"relationship_type": "IMPLIES", "is_builtin": True, "is_active": True},
            {"relationship_type": "CUSTOM_TYPE", "is_builtin": False, "is_active": True}
        ]

        metadata = await scorer._get_vocabulary_metadata()

        assert metadata["IMPLIES"]["is_builtin"] is True
        assert metadata["CUSTOM_TYPE"]["is_builtin"] is False

    @pytest.mark.asyncio
    async def test_get_value_scores_complete(self, scorer, mock_db):
        """Test complete value score calculation workflow"""
        # Mock all database queries
        mock_db.execute_query.side_effect = [
            # Edge metrics
            [{"relationship_type": "IMPLIES", "edge_count": 100, "avg_traversal": 50.0, "last_used": datetime.now()}],
            # Bridges
            [{"relationship_type": "IMPLIES", "bridge_count": 5}],
            # Trends
            [{"relationship_type": "IMPLIES", "avg_usage": 100.0, "usage_variation": 50.0}],
            # Vocabulary metadata
            [{"relationship_type": "IMPLIES", "is_builtin": True, "is_active": True}]
        ]

        scores = await scorer.get_value_scores()

        assert "IMPLIES" in scores
        score = scores["IMPLIES"]

        assert score.relationship_type == "IMPLIES"
        assert score.edge_count == 100
        assert score.avg_traversal == 50.0
        assert score.bridge_count == 5
        assert score.trend > 0  # Should have positive trend from variation
        assert score.is_builtin is True
        assert score.value_score > 0

    @pytest.mark.asyncio
    async def test_get_value_scores_exclude_builtin(self, scorer, mock_db):
        """Test excluding builtin types from results"""
        # Mock database responses
        mock_db.execute_query.side_effect = [
            [
                {"relationship_type": "IMPLIES", "edge_count": 100, "avg_traversal": 50.0, "last_used": None},
                {"relationship_type": "CUSTOM", "edge_count": 50, "avg_traversal": 25.0, "last_used": None}
            ],
            [],  # No bridges
            [{"relationship_type": "IMPLIES", "avg_usage": 100.0, "usage_variation": 50.0}],  # Trends
            [
                {"relationship_type": "IMPLIES", "is_builtin": True, "is_active": True},
                {"relationship_type": "CUSTOM", "is_builtin": False, "is_active": True}
            ]
        ]

        scores = await scorer.get_value_scores(include_builtin=False)

        assert "CUSTOM" in scores
        assert "IMPLIES" not in scores  # Excluded because builtin

    @pytest.mark.asyncio
    async def test_get_low_value_types(self, scorer, mock_db):
        """Test filtering low-value types for pruning"""
        # Mock get_value_scores
        with patch.object(scorer, 'get_value_scores', new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = {
                "HIGH_VALUE": EdgeTypeScore("HIGH_VALUE", 100, 50.0, 5, 10.0, 150.0, False, None),
                "LOW_VALUE": EdgeTypeScore("LOW_VALUE", 5, 1.0, 0, 0.0, 0.5, False, None),
                "BUILTIN_LOW": EdgeTypeScore("BUILTIN_LOW", 3, 0.5, 0, 0.0, 0.3, True, None)
            }

            candidates = await scorer.get_low_value_types(threshold=1.0)

            # Should return low-value types sorted by score
            assert len(candidates) == 1
            assert candidates[0].relationship_type == "LOW_VALUE"
            assert candidates[0].value_score == 0.5

    @pytest.mark.asyncio
    async def test_get_low_value_types_include_builtin(self, scorer, mock_db):
        """Test that builtins can be included if specified"""
        with patch.object(scorer, 'get_value_scores', new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = {
                "LOW_BUILTIN": EdgeTypeScore("LOW_BUILTIN", 3, 0.5, 0, 0.0, 0.3, True, None)
            }

            # With exclude_builtin=True (default)
            candidates_exclude = await scorer.get_low_value_types(threshold=1.0, exclude_builtin=True)
            assert len(candidates_exclude) == 0

            # With exclude_builtin=False
            mock_scores.return_value = {
                "LOW_BUILTIN": EdgeTypeScore("LOW_BUILTIN", 3, 0.5, 0, 0.0, 0.3, True, None)
            }
            candidates_include = await scorer.get_low_value_types(threshold=1.0, exclude_builtin=False)
            assert len(candidates_include) == 1

    @pytest.mark.asyncio
    async def test_get_low_value_types_exclude_nonzero(self, scorer, mock_db):
        """Test excluding types with existing edges"""
        with patch.object(scorer, 'get_value_scores', new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = {
                "ZERO_EDGES": EdgeTypeScore("ZERO_EDGES", 0, 0.0, 0, 0.0, 0.0, False, None),
                "HAS_EDGES": EdgeTypeScore("HAS_EDGES", 5, 1.0, 0, 0.0, 0.5, False, None)
            }

            # With exclude_nonzero_edges=True
            candidates = await scorer.get_low_value_types(threshold=1.0, exclude_nonzero_edges=True)

            assert len(candidates) == 1
            assert candidates[0].relationship_type == "ZERO_EDGES"

    @pytest.mark.asyncio
    async def test_get_zero_edge_types(self, scorer, mock_db):
        """Test getting types with zero edges"""
        mock_db.execute_query.return_value = [
            {"relationship_type": "UNUSED_TYPE_1"},
            {"relationship_type": "UNUSED_TYPE_2"}
        ]

        zero_types = await scorer.get_zero_edge_types()

        assert len(zero_types) == 2
        assert "UNUSED_TYPE_1" in zero_types
        assert "UNUSED_TYPE_2" in zero_types

    @pytest.mark.asyncio
    async def test_get_zero_edge_types_all_used(self, scorer, mock_db):
        """Test when all types have edges"""
        mock_db.execute_query.return_value = []

        zero_types = await scorer.get_zero_edge_types()

        assert zero_types == []

    def test_get_score_breakdown(self, scorer):
        """Test breaking down score into components"""
        score = EdgeTypeScore(
            relationship_type="TEST",
            edge_count=100,
            avg_traversal=50.0,
            bridge_count=5,
            trend=10.0,
            value_score=102.4,
            is_builtin=False,
            last_used=None
        )

        breakdown = scorer.get_score_breakdown(score)

        # Check component calculations
        assert breakdown["edge_component"] == 100.0  # 100 × 1.0
        assert abs(breakdown["traversal_component"] - 0.25) < 0.01  # (50/100) × 0.5
        assert abs(breakdown["bridge_component"] - 0.15) < 0.01  # (5/10) × 0.3
        assert breakdown["trend_component"] == 2.0  # 10 × 0.2
        assert breakdown["total_score"] == 102.4

    def test_get_score_breakdown_zero_score(self, scorer):
        """Test breakdown of zero-value score"""
        score = EdgeTypeScore(
            relationship_type="ZERO",
            edge_count=0,
            avg_traversal=0.0,
            bridge_count=0,
            trend=0.0,
            value_score=0.0,
            is_builtin=False,
            last_used=None
        )

        breakdown = scorer.get_score_breakdown(score)

        assert breakdown["edge_component"] == 0.0
        assert breakdown["traversal_component"] == 0.0
        assert breakdown["bridge_component"] == 0.0
        assert breakdown["trend_component"] == 0.0
        assert breakdown["total_score"] == 0.0


# ============================================================================
# Utility Function Tests
# ============================================================================


class TestUtilityFunctions:
    """Test suite for utility functions"""

    def test_compare_scores(self):
        """Test score comparison utility"""
        score1 = EdgeTypeScore("IMPLIES", 100, 50.0, 5, 10.0, 125.5, True, None)
        score2 = EdgeTypeScore("RELATED_TO", 50, 25.0, 2, 5.0, 62.5, False, None)

        comparison = compare_scores(score1, score2)

        assert comparison["type1"] == "IMPLIES"
        assert comparison["type2"] == "RELATED_TO"
        assert comparison["score_diff"] == 63.0  # 125.5 - 62.5
        assert comparison["edge_diff"] == 50  # 100 - 50
        assert comparison["bridge_diff"] == 3  # 5 - 2
        assert comparison["trend_diff"] == 5.0  # 10 - 5
        assert comparison["more_valuable"] == "IMPLIES"

    def test_compare_scores_equal(self):
        """Test comparing equal scores"""
        score1 = EdgeTypeScore("TYPE_A", 50, 25.0, 2, 5.0, 62.5, False, None)
        score2 = EdgeTypeScore("TYPE_B", 50, 25.0, 2, 5.0, 62.5, False, None)

        comparison = compare_scores(score1, score2)

        assert comparison["score_diff"] == 0.0
        assert comparison["more_valuable"] in ["TYPE_A", "TYPE_B"]

    def test_compare_scores_reverse_order(self):
        """Test that comparison order matters"""
        score1 = EdgeTypeScore("LOW", 10, 5.0, 0, 0.0, 10.0, False, None)
        score2 = EdgeTypeScore("HIGH", 100, 50.0, 5, 10.0, 125.5, False, None)

        comparison = compare_scores(score1, score2)

        assert comparison["score_diff"] < 0  # score1 < score2
        assert comparison["more_valuable"] == "HIGH"


# ============================================================================
# Integration Tests
# ============================================================================


class TestVocabularyScoringIntegration:
    """Integration tests for complete workflows"""

    @pytest.mark.asyncio
    async def test_full_scoring_workflow(self):
        """Test complete scoring workflow with mock database"""
        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock()

        # Simulate database responses
        mock_db.execute_query.side_effect = [
            # Edge metrics
            [
                {"relationship_type": "HIGH_VALUE", "edge_count": 100, "avg_traversal": 50.0, "last_used": datetime.now()},
                {"relationship_type": "LOW_VALUE", "edge_count": 5, "avg_traversal": 1.0, "last_used": None},
                {"relationship_type": "ZERO_EDGES", "edge_count": 0, "avg_traversal": 0.0, "last_used": None}
            ],
            # Bridges
            [{"relationship_type": "HIGH_VALUE", "bridge_count": 5}],
            # Trends
            [
                {"relationship_type": "HIGH_VALUE", "recent_usage": 80, "total_usage": 100},
                {"relationship_type": "LOW_VALUE", "recent_usage": 5, "total_usage": 100}
            ],
            # Metadata
            [
                {"relationship_type": "HIGH_VALUE", "is_builtin": False, "is_active": True},
                {"relationship_type": "LOW_VALUE", "is_builtin": False, "is_active": True},
                {"relationship_type": "ZERO_EDGES", "is_builtin": False, "is_active": True}
            ]
        ]

        scorer = VocabularyScorer(mock_db)
        scores = await scorer.get_value_scores()

        # Verify scores calculated correctly
        assert len(scores) == 3
        assert scores["HIGH_VALUE"].value_score > scores["LOW_VALUE"].value_score
        assert scores["ZERO_EDGES"].value_score == 0.0

    @pytest.mark.asyncio
    async def test_pruning_candidate_selection(self):
        """Test selecting pruning candidates from scores"""
        mock_db = MagicMock()
        scorer = VocabularyScorer(mock_db)

        # Mock get_value_scores
        with patch.object(scorer, 'get_value_scores', new_callable=AsyncMock) as mock_scores:
            mock_scores.return_value = {
                "KEEP_1": EdgeTypeScore("KEEP_1", 100, 50.0, 5, 10.0, 125.0, False, datetime.now()),
                "KEEP_2": EdgeTypeScore("KEEP_2", 75, 35.0, 3, 8.0, 90.0, False, datetime.now()),
                "PRUNE_1": EdgeTypeScore("PRUNE_1", 5, 1.0, 0, 0.0, 0.5, False, None),
                "PRUNE_2": EdgeTypeScore("PRUNE_2", 0, 0.0, 0, 0.0, 0.0, False, None),
                "BUILTIN": EdgeTypeScore("BUILTIN", 10, 5.0, 0, 0.0, 0.8, True, None)
            }

            # Get low-value types for pruning (threshold = 1.0)
            candidates = await scorer.get_low_value_types(threshold=1.0)

            # Should get PRUNE_1 and PRUNE_2 (not BUILTIN)
            assert len(candidates) == 2
            assert candidates[0].relationship_type in ["PRUNE_1", "PRUNE_2"]
            assert candidates[1].relationship_type in ["PRUNE_1", "PRUNE_2"]

            # Verify sorted by value (lowest first)
            assert candidates[0].value_score <= candidates[1].value_score


if __name__ == "__main__":
    # Allow running tests directly: python test_vocabulary_scoring.py
    pytest.main([__file__, "-v"])
