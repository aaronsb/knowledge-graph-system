"""
Epistemic Confidence Analyzer (ADR-063 extension).

Calculates epistemic confidence based on neighborhood richness to determine
how meaningful a grounding score is. A concept with sparse neighborhood
shows "Unexplored" rather than a misleading "0%" grounding.

This implements the two-dimensional epistemic model:
- Grounding: Direction of epistemic alignment (support ↔ contradict)
- Confidence: How much data exists to trust the grounding score

The confidence_score uses a nonlinear (saturation) function that reflects
diminishing returns - early evidence contributes more than later evidence.

Caching (ADR-201 Phase 5f):
    Confidence signals (relationship count, source count, evidence count)
    depend only on a concept's own graph neighborhood — no cross-concept
    dependency. Results are cached per-concept against the graph generation
    counter. When the graph mutates (ingestion, edits, merges), the generation
    bumps and the entire cache evicts. Between mutations, repeated queries
    for the same concept return instantly from cache.

References:
    - ADR-044: Probabilistic Truth Convergence
    - ADR-063: Semantic Diversity as Authenticity Signal
    - .claude/findings-grounding-presentation.md
    - .claude/additional-scoring-findings.md
"""

from typing import Dict, Any, Optional, Set, Tuple
import logging
import threading
import time
import math

logger = logging.getLogger(__name__)

# Per-concept confidence cache, keyed by (concept_id, graph_generation).
# Evicts entirely when graph generation changes.
_confidence_cache_lock = threading.Lock()
_confidence_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}
_confidence_cache_generation: Optional[int] = None


# Confidence level thresholds
# These are initial values - Phase 4 will tune based on real data
CONFIDENT_MIN_RELATIONSHIPS = 5
CONFIDENT_MIN_SOURCES = 3
CONFIDENT_MIN_EVIDENCE = 3

TENTATIVE_MIN_RELATIONSHIPS = 2
TENTATIVE_MIN_SOURCES = 1
TENTATIVE_MIN_EVIDENCE = 1


class ConfidenceAnalyzer:
    """
    Analyzes epistemic confidence based on neighborhood richness.

    Confidence answers: "How much data do we have to judge this concept?"

    Three levels:
    - Confident: Rich neighborhood (≥5 relationships, ≥3 sources, diverse types)
    - Tentative: Some signal (2-4 relationships, 1-2 sources)
    - Insufficient: Sparse (<2 relationships, single source or less)

    The confidence level determines how to present grounding:
    - Confident + Positive grounding → "Well-supported ✓"
    - Insufficient + Any grounding → "Unexplored" (don't show misleading numbers)
    """

    def __init__(self, age_client):
        """
        Initialize confidence analyzer.

        Args:
            age_client: AGEClient instance for graph queries
        """
        self.client = age_client

    def calculate_confidence(
        self,
        concept_id: str,
        grounding_strength: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate epistemic confidence for a concept.

        Results are cached per-concept against the graph generation counter.
        The grounding_display field depends on both the cached signals AND
        the grounding_strength parameter, so it's recomputed from cached
        signals when grounding_strength differs (cheap — no DB queries).

        Args:
            concept_id: Target concept ID
            grounding_strength: Optional grounding score for combined interpretation

        Returns:
            Dictionary with confidence metrics:
            {
                "level": "confident" | "tentative" | "insufficient",
                "signals": {...},
                "interpretation": str,
                "grounding_display": str  # Combined grounding x confidence label
            }
        """
        global _confidence_cache, _confidence_cache_generation

        # Check graph generation for cache validity
        graph_gen = self._get_graph_generation()

        with _confidence_cache_lock:
            if _confidence_cache_generation != graph_gen:
                if _confidence_cache:
                    logger.info(
                        f"Confidence cache invalidated: generation "
                        f"{_confidence_cache_generation} → {graph_gen} "
                        f"({len(_confidence_cache)} entries evicted)"
                    )
                _confidence_cache.clear()
                _confidence_cache_generation = graph_gen

            cache_key = (concept_id, graph_gen)
            cached = _confidence_cache.get(cache_key)

        if cached is not None:
            # Recompute grounding_display (depends on caller's grounding_strength)
            result = dict(cached)
            result['grounding_display'] = self._get_grounding_display(
                grounding_strength, result['level']
            )
            return result

        start_time = time.time()

        try:
            # Gather signals from graph
            signals = self._gather_signals(concept_id)

            # Determine confidence level
            level = self._calculate_level(signals)

            # Generate interpretation
            interpretation = self._interpret(level, signals)

            # Generate combined grounding x confidence display label
            grounding_display = self._get_grounding_display(
                grounding_strength, level
            )

            calculation_time_ms = int((time.time() - start_time) * 1000)

            logger.debug(
                f"Confidence calculated for {concept_id}: "
                f"level={level}, rels={signals['relationship_count']}, "
                f"sources={signals['source_count']}, time={calculation_time_ms}ms"
            )

            # Calculate numeric confidence score (0-1, nonlinear)
            confidence_score = self._calculate_score(signals)

            result = {
                "level": level,
                "confidence_score": confidence_score,
                "signals": signals,
                "interpretation": interpretation,
                "grounding_display": grounding_display,
                "calculation_time_ms": calculation_time_ms
            }

            with _confidence_cache_lock:
                _confidence_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Confidence calculation failed for {concept_id}: {e}")
            raise

    def _get_graph_generation(self) -> int:
        """Read graph generation for cache invalidation.

        Same two-tier probe as query.py: tries graph_accel.generation first,
        falls back to vocabulary_change_counter.
        """
        from psycopg2 import extras
        conn = self.client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                try:
                    cur.execute("SAVEPOINT conf_gen_check")
                    cur.execute(
                        "SELECT current_generation FROM graph_accel.generation "
                        "WHERE graph_name = 'knowledge_graph'"
                    )
                    row = cur.fetchone()
                    cur.execute("RELEASE SAVEPOINT conf_gen_check")
                    if row:
                        return int(row['current_generation'])
                except Exception:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT conf_gen_check")
                    except Exception:
                        pass
                # Fallback
                try:
                    cur.execute(
                        "SELECT counter FROM graph_metrics "
                        "WHERE metric_name = 'vocabulary_change_counter'"
                    )
                    row = cur.fetchone()
                    return int(row['counter']) if row else 0
                except Exception:
                    return 0
        finally:
            self.client.pool.putconn(conn)

    def _gather_signals(self, concept_id: str) -> Dict[str, Any]:
        """
        Gather confidence signals from graph.

        Counts:
        - Incoming + outgoing relationships (close neighbors)
        - Unique source documents
        - Evidence instances
        - Relationship type diversity
        """
        # Count relationships (both directions)
        rel_query = """
        MATCH (c:Concept {concept_id: $concept_id})-[r]-(other:Concept)
        RETURN count(r) as rel_count, count(DISTINCT type(r)) as type_count
        """
        rel_result = self.client._execute_cypher(
            rel_query,
            params={'concept_id': concept_id}
        )

        relationship_count = 0
        relationship_types = 0
        if rel_result and len(rel_result) > 0:
            relationship_count = rel_result[0].get('rel_count', 0) or 0
            relationship_types = rel_result[0].get('type_count', 0) or 0

        # Count unique sources and evidence instances
        source_query = """
        MATCH (c:Concept {concept_id: $concept_id})-[:APPEARS_IN]->(s:Source)
        RETURN count(DISTINCT s.document) as source_count
        """
        source_result = self.client._execute_cypher(
            source_query,
            params={'concept_id': concept_id}
        )

        source_count = 0
        if source_result and len(source_result) > 0:
            source_count = source_result[0].get('source_count', 0) or 0

        # Count evidence instances
        evidence_query = """
        MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
        RETURN count(i) as evidence_count
        """
        evidence_result = self.client._execute_cypher(
            evidence_query,
            params={'concept_id': concept_id}
        )

        evidence_count = 0
        if evidence_result and len(evidence_result) > 0:
            evidence_count = evidence_result[0].get('evidence_count', 0) or 0

        # Calculate relationship type diversity (0-1)
        # Using simple ratio: unique_types / relationship_count
        # Capped at 1.0 for edge cases
        type_diversity = 0.0
        if relationship_count > 0:
            type_diversity = min(1.0, relationship_types / relationship_count)

        return {
            "relationship_count": relationship_count,
            "source_count": source_count,
            "evidence_count": evidence_count,
            "relationship_types": relationship_types,
            "relationship_type_diversity": round(type_diversity, 3)
        }

    def _calculate_score(self, signals: Dict[str, Any]) -> float:
        """
        Calculate numeric confidence score (0-1) using nonlinear saturation.

        Uses a saturation function: score = composite / (composite + k)
        This reflects diminishing returns - early evidence contributes more
        than later evidence, asymptotically approaching 1.0.

        The composite metric combines:
        - Relationship count (normalized by 10)
        - Source count (normalized by 5)
        - Evidence count (normalized by 10)
        - Relationship type diversity (0-1)

        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        rel_count = signals.get('relationship_count', 0)
        source_count = signals.get('source_count', 0)
        evidence_count = signals.get('evidence_count', 0)
        type_diversity = signals.get('relationship_type_diversity', 0.0)

        # Composite metric with weighted contributions
        # Each component normalized to roughly 0-1 range for typical values
        composite = (
            rel_count / 10.0 +      # 10 relationships → 1.0 contribution
            source_count / 5.0 +    # 5 sources → 1.0 contribution
            evidence_count / 10.0 + # 10 evidence → 1.0 contribution
            type_diversity          # Already 0-1
        )

        # Half-saturation constant: when composite = k, score = 0.5
        # k=2.0 means: 10 rels + 5 sources + 10 evidence + full diversity → ~67% confidence
        k = 2.0

        # Saturation function with diminishing returns
        score = composite / (composite + k)

        return round(score, 3)

    def _calculate_level(self, signals: Dict[str, Any]) -> str:
        """
        Determine confidence level from signals.

        Levels:
        - confident: Rich on most signals
        - tentative: Some signal but gaps
        - insufficient: Sparse across the board
        """
        rel_count = signals.get('relationship_count', 0)
        source_count = signals.get('source_count', 0)
        evidence_count = signals.get('evidence_count', 0)

        # Confident: Rich neighborhood
        if (rel_count >= CONFIDENT_MIN_RELATIONSHIPS and
            source_count >= CONFIDENT_MIN_SOURCES and
            evidence_count >= CONFIDENT_MIN_EVIDENCE):
            return "confident"

        # Tentative: Some signal
        if (rel_count >= TENTATIVE_MIN_RELATIONSHIPS or
            source_count >= TENTATIVE_MIN_SOURCES or
            evidence_count >= TENTATIVE_MIN_EVIDENCE):
            return "tentative"

        # Insufficient: Sparse
        return "insufficient"

    def _interpret(self, level: str, signals: Dict[str, Any]) -> str:
        """Generate human-readable interpretation."""
        rel_count = signals.get('relationship_count', 0)
        source_count = signals.get('source_count', 0)

        if level == "confident":
            return (
                f"Rich epistemic neighborhood: {rel_count} relationships, "
                f"{source_count} sources. Grounding score is meaningful."
            )
        elif level == "tentative":
            return (
                f"Limited data: {rel_count} relationships, {source_count} sources. "
                f"Grounding score should be interpreted with caution."
            )
        else:
            return (
                f"Sparse neighborhood: {rel_count} relationships, {source_count} sources. "
                f"Insufficient data to assess grounding."
            )

    def _get_grounding_display(
        self,
        grounding: Optional[float],
        confidence: str
    ) -> str:
        """
        Get combined grounding × confidence display label.

        This is the 3×3 matrix from findings-grounding-presentation.md:

        | Grounding × Confidence | Display |
        |------------------------|---------|
        | Positive + Confident | "Well-supported" |
        | Positive + Tentative | "Some support (limited data)" |
        | Positive + Insufficient | "Possibly supported (needs exploration)" |
        | Neutral + Confident | "Balanced perspectives" |
        | Neutral + Tentative | "Unclear" |
        | Neutral + Insufficient | "Unexplored" |
        | Negative + Confident | "Contested" |
        | Negative + Tentative | "Possibly contested" |
        | Negative + Insufficient | "Unknown (needs exploration)" |
        """
        if grounding is None:
            if confidence == "insufficient":
                return "Unexplored"
            return "Unknown"

        # Determine grounding category
        if grounding >= 0.2:
            grounding_cat = "positive"
        elif grounding <= -0.2:
            grounding_cat = "negative"
        else:
            grounding_cat = "neutral"

        # 3×3 matrix lookup
        display_matrix = {
            ("positive", "confident"): "Well-supported",
            ("positive", "tentative"): "Some support (limited data)",
            ("positive", "insufficient"): "Possibly supported (needs exploration)",
            ("neutral", "confident"): "Balanced perspectives",
            ("neutral", "tentative"): "Unclear",
            ("neutral", "insufficient"): "Unexplored",
            ("negative", "confident"): "Contested",
            ("negative", "tentative"): "Possibly contested",
            ("negative", "insufficient"): "Unknown (needs exploration)",
        }

        return display_matrix.get((grounding_cat, confidence), "Unknown")
