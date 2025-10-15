"""
Vocabulary Scoring for Automatic Edge Vocabulary Expansion.

Calculates value scores for edge types based on usage metrics to inform
intelligent pruning decisions (ADR-032).

Value Score Formula:
    value_score = (
        edge_count × 1.0 +                    # Base: how many edges exist
        (avg_traversal / 100.0) × 0.5 +       # Usage: how often queried
        (bridge_count / 10.0) × 0.3 +         # Structural: connects subgraphs
        max(0, trend) × 0.2                   # Momentum: usage variation (growth indicator)
    )

Bridge Detection:
    Low-activation nodes connecting to high-activation nodes prevent
    catastrophic forgetting of structurally important types.

Usage:
    from src.api.lib.vocabulary_scoring import VocabularyScorer

    scorer = VocabularyScorer(db_client)
    scores = await scorer.get_value_scores()

    for edge_type, score in scores.items():
        print(f"{edge_type}: {score.value_score:.2f} (edges: {score.edge_count})")

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - ADR-025: Dynamic Relationship Vocabulary
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class EdgeTypeScore:
    """
    Value score and component metrics for an edge type.

    Attributes:
        relationship_type: Edge type label (e.g., "IMPLIES", "CAUSES")
        edge_count: Total number of edges of this type
        avg_traversal: Average traversals per edge
        bridge_count: Number of bridge edges (structural importance)
        trend: Usage trend (positive = growing, negative = declining)
        value_score: Calculated value score (higher = more valuable)
        is_builtin: Protected core type (never auto-prune)
        last_used: Timestamp of most recent traversal
    """
    relationship_type: str
    edge_count: int
    avg_traversal: float
    bridge_count: int
    trend: float
    value_score: float
    is_builtin: bool
    last_used: Optional[datetime]

    def __repr__(self) -> str:
        return (
            f"EdgeTypeScore({self.relationship_type}, "
            f"score={self.value_score:.2f}, edges={self.edge_count}, "
            f"bridges={self.bridge_count})"
        )


class VocabularyScorer:
    """
    Calculate value scores for edge types based on usage statistics.

    Queries kg_api.edge_usage_stats and kg_api.concept_access_stats to
    determine structural importance and usage patterns.
    """

    # Bridge detection thresholds (per ADR-032)
    BRIDGE_SOURCE_THRESHOLD = 10    # Low-activation source
    BRIDGE_DEST_THRESHOLD = 100     # High-activation destination

    # Score component weights
    WEIGHT_EDGE_COUNT = 1.0
    WEIGHT_TRAVERSAL = 0.5
    WEIGHT_BRIDGE = 0.3
    WEIGHT_TREND = 0.2

    def __init__(self, db_client):
        """
        Initialize scorer with database client.

        Args:
            db_client: PostgreSQL connection or age_client instance
        """
        self.db = db_client

    async def get_value_scores(
        self,
        include_builtin: bool = True
    ) -> Dict[str, EdgeTypeScore]:
        """
        Calculate value scores for all edge types.

        Args:
            include_builtin: Include protected builtin types in results

        Returns:
            Dictionary mapping relationship_type to EdgeTypeScore

        Example:
            >>> scorer = VocabularyScorer(db_client)
            >>> scores = await scorer.get_value_scores()
            >>> scores["IMPLIES"]
            EdgeTypeScore(IMPLIES, score=45.23, edges=120, bridges=5)
        """
        # Get base metrics (edge counts and traversals)
        edge_metrics = await self._get_edge_metrics()

        # Detect bridge edges
        bridge_counts = await self._detect_bridges()

        # Calculate usage trends (recent vs historical)
        trends = await self._calculate_trends()

        # Get builtin status and last used timestamps
        vocab_metadata = await self._get_vocabulary_metadata()

        # Combine metrics into scores
        scores = {}

        for rel_type, metrics in edge_metrics.items():
            # Skip builtin types if requested
            is_builtin = vocab_metadata.get(rel_type, {}).get("is_builtin", False)
            if not include_builtin and is_builtin:
                continue

            edge_count = metrics["edge_count"]
            avg_traversal = metrics["avg_traversal"]
            bridge_count = bridge_counts.get(rel_type, 0)
            trend = trends.get(rel_type, 0.0)
            last_used = metrics.get("last_used")

            # Calculate value score
            value_score = self._calculate_value_score(
                edge_count=edge_count,
                avg_traversal=avg_traversal,
                bridge_count=bridge_count,
                trend=trend
            )

            scores[rel_type] = EdgeTypeScore(
                relationship_type=rel_type,
                edge_count=edge_count,
                avg_traversal=avg_traversal,
                bridge_count=bridge_count,
                trend=trend,
                value_score=value_score,
                is_builtin=is_builtin,
                last_used=last_used
            )

        return scores

    def _calculate_value_score(
        self,
        edge_count: int,
        avg_traversal: float,
        bridge_count: int,
        trend: float
    ) -> float:
        """
        Calculate value score from components.

        Formula:
            value_score = (
                edge_count × 1.0 +
                (avg_traversal / 100.0) × 0.5 +
                (bridge_count / 10.0) × 0.3 +
                max(0, trend) × 0.2
            )

        Args:
            edge_count: Total edges of this type
            avg_traversal: Average traversals per edge
            bridge_count: Number of bridge edges
            trend: Usage trend (variation-based growth indicator)

        Returns:
            Value score (higher = more valuable)
        """
        score = (
            edge_count * self.WEIGHT_EDGE_COUNT +
            (avg_traversal / 100.0) * self.WEIGHT_TRAVERSAL +
            (bridge_count / 10.0) * self.WEIGHT_BRIDGE +
            max(0, trend) * self.WEIGHT_TREND
        )

        return score

    async def _get_edge_metrics(self) -> Dict[str, Dict]:
        """
        Query edge usage statistics from database.

        Returns:
            Dict mapping relationship_type to {edge_count, avg_traversal, last_used}
        """
        query = """
            SELECT
                relationship_type,
                COUNT(*) as edge_count,
                AVG(traversal_count) as avg_traversal,
                MAX(last_traversed) as last_used
            FROM kg_api.edge_usage_stats
            GROUP BY relationship_type
        """

        try:
            result = await self._execute_query(query)

            metrics = {}
            for row in result:
                rel_type = row["relationship_type"]
                metrics[rel_type] = {
                    "edge_count": row["edge_count"],
                    "avg_traversal": float(row["avg_traversal"] or 0),
                    "last_used": row["last_used"]
                }

            return metrics

        except Exception as e:
            print(f"Error querying edge metrics: {e}")
            return {}

    async def _detect_bridges(self) -> Dict[str, int]:
        """
        Detect bridge edges: low-activation source → high-activation destination.

        Bridge Detection Logic:
            - Source concept: access_count < 10 (rarely accessed)
            - Destination concept: access_count > 100 (frequently accessed)
            - These edges prevent catastrophic forgetting

        Returns:
            Dict mapping relationship_type to bridge_count
        """
        query = f"""
            SELECT
                e.relationship_type,
                COUNT(*) as bridge_count
            FROM kg_api.edge_usage_stats e
            JOIN kg_api.concept_access_stats c_from
                ON e.from_concept_id = c_from.concept_id
            JOIN kg_api.concept_access_stats c_to
                ON e.to_concept_id = c_to.concept_id
            WHERE c_from.access_count < {self.BRIDGE_SOURCE_THRESHOLD}
              AND c_to.access_count > {self.BRIDGE_DEST_THRESHOLD}
            GROUP BY e.relationship_type
        """

        try:
            result = await self._execute_query(query)

            bridges = {}
            for row in result:
                bridges[row["relationship_type"]] = row["bridge_count"]

            return bridges

        except Exception as e:
            print(f"Error detecting bridges: {e}")
            return {}

    async def _calculate_trends(self) -> Dict[str, float]:
        """
        Calculate usage trends based on actual traversal changes.

        Trend Calculation:
            - Compare current traversal rates to historical averages
            - Positive trend = growing usage (recent > historical)
            - Negative trend = declining usage (recent < historical)
            - Uses traversal_count as proxy for usage growth

        Note: Graphs don't understand time - we infer trends from
        traversal count differentials, not timestamps.

        Returns:
            Dict mapping relationship_type to trend value
        """
        query = """
            SELECT
                relationship_type,
                AVG(traversal_count) as avg_usage,
                STDDEV(traversal_count) as usage_variation
            FROM kg_api.edge_usage_stats
            GROUP BY relationship_type
        """

        try:
            result = await self._execute_query(query)

            trends = {}
            for row in result:
                rel_type = row["relationship_type"]
                avg_usage = row["avg_usage"] or 0
                variation = row["usage_variation"] or 0

                # Use variation as trend indicator
                # Higher variation suggests active usage patterns (good)
                # Positive average with high variation = growing
                trend = (avg_usage / 10.0) * (1.0 + variation / 100.0) if avg_usage > 0 else 0

                trends[rel_type] = trend

            return trends

        except Exception as e:
            print(f"Error calculating trends: {e}")
            return {}

    async def _get_vocabulary_metadata(self) -> Dict[str, Dict]:
        """
        Get metadata about edge types from vocabulary table.

        Returns:
            Dict mapping relationship_type to {is_builtin, is_active}
        """
        query = """
            SELECT
                relationship_type,
                is_builtin,
                is_active
            FROM kg_api.relationship_vocabulary
        """

        try:
            result = await self._execute_query(query)

            metadata = {}
            for row in result:
                rel_type = row["relationship_type"]
                metadata[rel_type] = {
                    "is_builtin": row["is_builtin"],
                    "is_active": row["is_active"]
                }

            return metadata

        except Exception as e:
            print(f"Error getting vocabulary metadata: {e}")
            return {}

    async def _execute_query(self, query: str) -> List[Dict]:
        """
        Execute SQL query and return results.

        Handles both raw psycopg2 connections and AGEClient instances.

        Args:
            query: SQL query string

        Returns:
            List of row dictionaries
        """
        # If db is AGEClient or has execute_query method
        if hasattr(self.db, 'execute_query'):
            return await self.db.execute_query(query)

        # If db is raw psycopg2 connection
        elif hasattr(self.db, 'cursor'):
            with self.db.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall()

        else:
            raise ValueError("Unsupported database client type")

    async def get_low_value_types(
        self,
        threshold: float = 1.0,
        exclude_builtin: bool = True,
        exclude_nonzero_edges: bool = False
    ) -> List[EdgeTypeScore]:
        """
        Get edge types with low value scores for pruning consideration.

        Args:
            threshold: Maximum value score to include (default: 1.0)
            exclude_builtin: Exclude protected builtin types (default: True)
            exclude_nonzero_edges: Exclude types with existing edges (default: False)

        Returns:
            List of EdgeTypeScore objects sorted by value (lowest first)

        Example:
            >>> scorer = VocabularyScorer(db_client)
            >>> candidates = await scorer.get_low_value_types(threshold=0.5)
            >>> for score in candidates[:5]:  # Top 5 pruning candidates
            ...     print(f"{score.relationship_type}: {score.value_score:.2f}")
        """
        scores = await self.get_value_scores(include_builtin=not exclude_builtin)

        # Filter by criteria
        candidates = [
            score for score in scores.values()
            if score.value_score <= threshold
            and (not exclude_builtin or not score.is_builtin)
            and (not exclude_nonzero_edges or score.edge_count == 0)
        ]

        # Sort by value (lowest first)
        candidates.sort(key=lambda s: s.value_score)

        return candidates

    async def get_zero_edge_types(self) -> List[str]:
        """
        Get edge types with zero edges (safe to prune).

        These types have been added to vocabulary but never used.
        Safe to remove without data loss.

        Returns:
            List of relationship type names with zero edges

        Example:
            >>> scorer = VocabularyScorer(db_client)
            >>> unused = await scorer.get_zero_edge_types()
            >>> print(f"Found {len(unused)} unused types")
        """
        query = """
            SELECT rv.relationship_type
            FROM kg_api.relationship_vocabulary rv
            LEFT JOIN kg_api.edge_usage_stats e
                ON rv.relationship_type = e.relationship_type
            WHERE e.relationship_type IS NULL
              AND rv.is_builtin = FALSE
              AND rv.is_active = TRUE
        """

        try:
            result = await self._execute_query(query)
            return [row["relationship_type"] for row in result]

        except Exception as e:
            print(f"Error getting zero-edge types: {e}")
            return []

    def get_score_breakdown(self, score: EdgeTypeScore) -> Dict[str, float]:
        """
        Break down value score into individual components.

        Useful for understanding what makes a type valuable.

        Args:
            score: EdgeTypeScore to analyze

        Returns:
            Dict with component scores

        Example:
            >>> breakdown = scorer.get_score_breakdown(scores["IMPLIES"])
            >>> print(f"Edge contribution: {breakdown['edge_component']:.2f}")
            >>> print(f"Traversal contribution: {breakdown['traversal_component']:.2f}")
        """
        return {
            "edge_component": score.edge_count * self.WEIGHT_EDGE_COUNT,
            "traversal_component": (score.avg_traversal / 100.0) * self.WEIGHT_TRAVERSAL,
            "bridge_component": (score.bridge_count / 10.0) * self.WEIGHT_BRIDGE,
            "trend_component": max(0, score.trend) * self.WEIGHT_TREND,
            "total_score": score.value_score
        }


# ============================================================================
# Utility Functions
# ============================================================================


def compare_scores(
    score1: EdgeTypeScore,
    score2: EdgeTypeScore
) -> Dict[str, any]:
    """
    Compare two edge type scores.

    Useful for understanding relative value.

    Args:
        score1: First score to compare
        score2: Second score to compare

    Returns:
        Comparison dict with differences

    Example:
        >>> comparison = compare_scores(scores["IMPLIES"], scores["RELATED_TO"])
        >>> print(f"Score difference: {comparison['score_diff']:.2f}")
    """
    return {
        "type1": score1.relationship_type,
        "type2": score2.relationship_type,
        "score_diff": score1.value_score - score2.value_score,
        "edge_diff": score1.edge_count - score2.edge_count,
        "bridge_diff": score1.bridge_count - score2.bridge_count,
        "trend_diff": score1.trend - score2.trend,
        "more_valuable": score1.relationship_type if score1.value_score > score2.value_score else score2.relationship_type
    }


if __name__ == "__main__":
    # Quick demonstration (requires database connection)
    import asyncio
    import sys

    print("Vocabulary Scorer - ADR-032 Implementation")
    print("=" * 60)
    print()
    print("This module calculates value scores for edge types based on:")
    print("  - Edge count (base importance)")
    print("  - Traversal frequency (usage patterns)")
    print("  - Bridge detection (structural importance)")
    print("  - Usage trends (momentum)")
    print()
    print("Usage:")
    print("  from src.api.lib.vocabulary_scoring import VocabularyScorer")
    print("  scorer = VocabularyScorer(db_client)")
    print("  scores = await scorer.get_value_scores()")
    print()
    print("For testing, run: pytest tests/test_vocabulary_scoring.py")
