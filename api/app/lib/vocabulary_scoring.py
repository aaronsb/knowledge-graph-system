"""
Grounding-Aware Vocabulary Scoring (Graph-Native Implementation).

Implements ADR-046 (Grounding-Aware Vocabulary Management) by extending ADR-032
with embedding-based synonym detection and grounding contribution metrics.

Key Features:
1. **Embedding-based synonym detection** - Uses semantic similarity instead of string matching
2. **Grounding contribution metrics** - Measures impact on truth convergence (ADR-044)
3. **Dynamic vocabulary curation** - Generates optimized subsets for LLM extraction prompts
4. **Graph-native architecture** - All operations use graph queries + embeddings

Value Score Components:
- **edge_count**: How many edges use this type (usage metric)
- **avg_traversal**: How often queried (access patterns)
- **bridge_count**: Connects disconnected subgraphs (structural importance)
- **trend**: Usage variation (growth/decline indicator)
- **grounding_contribution** (NEW): Impact on grounding strength (truth convergence)
- **supports_concepts** (NEW): Number of concepts this type helps ground

Synonym Detection (ADR-046):
    Uses embedding cosine similarity instead of Porter stemmer:
    - similarity >= 0.90: Strong synonyms (auto-merge candidates)
    - similarity >= 0.85: Moderate synonyms (review recommended)
    - similarity < 0.85: Distinct types (preserve diversity)

Dynamic Vocabulary Curation (ADR-046):
    Prevents LLM cognitive overload by selecting optimal subset:
    - High grounding contribution (truth-critical types)
    - Semantic diversity (avoid redundant synonyms)
    - Usage frequency (proven utility)
    - Maximum 40-50 types for extraction prompts

Usage:
    from api.app.lib.vocabulary_scoring import VocabularyScorer

    scorer = VocabularyScorer(db_client)

    # Basic scoring (ADR-032 metrics)
    scores = await scorer.get_value_scores()

    # With grounding awareness (ADR-046)
    scores = await scorer.get_value_scores(include_grounding=True)

    # Find semantic synonyms
    synonyms = await scorer.find_semantic_synonyms("CAUSES", threshold=0.85)

    # Get curated vocabulary for LLM prompts
    vocab = await scorer.get_extraction_vocabulary(max_types=50)

    # Generate grounding-aware merge recommendations
    recommendations = await scorer.generate_merge_recommendations(min_similarity=0.85)

Replaces:
    - ADR-032 synonym_detector.py (string-based detection)
    - ADR-032 category_classifier.py (table-based classification)
    - Porter stemmer approach (language-specific, brittle)

References:
    - ADR-046: Grounding-Aware Vocabulary Management (this implementation)
    - ADR-044: Probabilistic Truth Convergence (grounding strength calculation)
    - ADR-045: Unified Embedding Generation (provides embeddings)
    - ADR-032: Automatic Edge Vocabulary Expansion (extended by this)
    - ADR-025: Dynamic Relationship Vocabulary
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


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
        avg_grounding_contribution: Average grounding strength contribution (ADR-046)
        supports_concepts: Number of concepts this edge type helps ground (ADR-046)
        embedding: Edge type embedding vector for semantic analysis (ADR-046)
        epistemic_status: Epistemic status classification (ADR-065)
    """
    relationship_type: str
    edge_count: int
    avg_traversal: float
    bridge_count: int
    trend: float
    value_score: float
    is_builtin: bool
    last_used: Optional[datetime]
    avg_grounding_contribution: Optional[float] = None
    supports_concepts: Optional[int] = None
    embedding: Optional[List[float]] = None
    epistemic_status: Optional[str] = None

    def __repr__(self) -> str:
        grounding_info = ""
        if self.avg_grounding_contribution is not None:
            grounding_info = f", grounding={self.avg_grounding_contribution:.3f}"
        return (
            f"EdgeTypeScore({self.relationship_type}, "
            f"score={self.value_score:.2f}, edges={self.edge_count}, "
            f"bridges={self.bridge_count}{grounding_info})"
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
        include_builtin: bool = True,
        include_grounding: bool = False
    ) -> Dict[str, EdgeTypeScore]:
        """
        Calculate value scores for all edge types.

        Args:
            include_builtin: Include protected builtin types in results
            include_grounding: Calculate grounding contributions (ADR-046, slower)

        Returns:
            Dictionary mapping relationship_type to EdgeTypeScore

        Example:
            >>> scorer = VocabularyScorer(db_client)
            >>> scores = await scorer.get_value_scores()
            >>> scores["IMPLIES"]
            EdgeTypeScore(IMPLIES, score=45.23, edges=120, bridges=5)

            >>> # With grounding metrics
            >>> scores = await scorer.get_value_scores(include_grounding=True)
            >>> scores["IMPLIES"]
            EdgeTypeScore(IMPLIES, score=45.23, edges=120, bridges=5, grounding=0.842)
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

            # Optionally calculate grounding contribution (ADR-046)
            avg_grounding_contribution = None
            supports_concepts = None
            embedding = None

            if include_grounding:
                try:
                    avg_grounding_contribution, supports_concepts = await self.calculate_grounding_contribution(rel_type)
                    embedding = vocab_metadata.get(rel_type, {}).get("embedding")
                except Exception as e:
                    logger.warning(f"Failed to calculate grounding for {rel_type}: {e}")

            # Get epistemic status from metadata (ADR-065)
            epistemic_status = vocab_metadata.get(rel_type, {}).get("epistemic_status")

            scores[rel_type] = EdgeTypeScore(
                relationship_type=rel_type,
                edge_count=edge_count,
                avg_traversal=avg_traversal,
                bridge_count=bridge_count,
                trend=trend,
                value_score=value_score,
                is_builtin=is_builtin,
                last_used=last_used,
                avg_grounding_contribution=avg_grounding_contribution,
                supports_concepts=supports_concepts,
                embedding=embedding,
                epistemic_status=epistemic_status
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
            logger.error(f"Error querying edge metrics: {e}")
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
            logger.error(f"Error detecting bridges: {e}")
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
            logger.error(f"Error calculating trends: {e}")
            return {}

    async def _get_vocabulary_metadata(self) -> Dict[str, Dict]:
        """
        Get metadata about edge types from vocabulary table and graph.

        Returns:
            Dict mapping relationship_type to {is_builtin, is_active, embedding, epistemic_status}
        """
        # Get SQL metadata
        query = """
            SELECT
                relationship_type,
                is_builtin,
                is_active,
                embedding
            FROM kg_api.relationship_vocabulary
        """

        try:
            result = await self._execute_query(query)

            metadata = {}
            for row in result:
                rel_type = row["relationship_type"]
                metadata[rel_type] = {
                    "is_builtin": row["is_builtin"],
                    "is_active": row["is_active"],
                    "embedding": row.get("embedding"),
                    "epistemic_status": None  # Will be populated from graph
                }

        except Exception as e:
            logger.error(f"Error getting vocabulary metadata from SQL: {e}")
            metadata = {}

        # Get epistemic_status from graph (ADR-065)
        try:
            epistemic_query = """
                SELECT * FROM cypher('knowledge_graph', $$
                    MATCH (v:VocabType)
                    WHERE v.epistemic_status IS NOT NULL
                    RETURN v.name AS relationship_type, v.epistemic_status AS epistemic_status
                $$) AS (relationship_type agtype, epistemic_status agtype);
            """

            epistemic_result = await self._execute_query(epistemic_query)

            for row in epistemic_result:
                # Values are already unwrapped by psycopg2/age adapter
                rel_type = row["relationship_type"]
                epistemic_status = row["epistemic_status"]

                if rel_type in metadata:
                    metadata[rel_type]["epistemic_status"] = epistemic_status

        except Exception as e:
            logger.warning(f"Could not fetch epistemic_status from graph: {e}")
            # Continue without epistemic status - it's optional

        return metadata

    async def calculate_grounding_contribution(
        self,
        relationship_type: str
    ) -> Tuple[float, int]:
        """
        Calculate grounding strength contribution for an edge type (ADR-046).

        This measures how much an edge type contributes to concept grounding
        across the graph by analyzing its semantic similarity to SUPPORTS/CONTRADICTS.

        Algorithm:
        1. Get SUPPORTS and CONTRADICTS prototype embeddings
        2. Get embedding for the target edge type
        3. Calculate cosine similarity to both prototypes
        4. Classify as supporting (+) or contradicting (-)
        5. Count how many concepts use this edge type
        6. Return (avg_contribution, concept_count)

        Args:
            relationship_type: Edge type to analyze

        Returns:
            Tuple of (avg_grounding_contribution, supports_concepts):
            - avg_grounding_contribution: Float in [-1.0, 1.0] indicating
              support (+) or contradiction (-) semantics
            - supports_concepts: Number of distinct concepts with incoming
              edges of this type

        Example:
            >>> contribution, count = await scorer.calculate_grounding_contribution("IMPLIES")
            >>> print(f"IMPLIES: {contribution:.3f} grounding ({count} concepts)")
            IMPLIES: 0.842 grounding (156 concepts)
        """
        import numpy as np
        import json

        try:
            # Step 1: Get prototype embeddings
            query_prototypes = """
                SELECT relationship_type, embedding
                FROM kg_api.relationship_vocabulary
                WHERE relationship_type IN ('SUPPORTS', 'CONTRADICTS')
                  AND embedding IS NOT NULL
            """
            prototypes = await self._execute_query(query_prototypes)

            if len(prototypes) < 2:
                logger.warning("Missing SUPPORTS or CONTRADICTS embeddings for grounding calculation")
                return (0.0, 0)

            # Parse prototype embeddings
            supports_emb = None
            contradicts_emb = None

            for proto in prototypes:
                emb_json = proto['embedding']
                # Handle various JSONB formats
                if isinstance(emb_json, str):
                    emb_array = np.array(json.loads(emb_json), dtype=float)
                elif isinstance(emb_json, list):
                    emb_array = np.array(emb_json, dtype=float)
                elif isinstance(emb_json, dict):
                    emb_array = np.array(list(emb_json.values()), dtype=float)
                else:
                    emb_array = np.array(list(emb_json), dtype=float)

                if proto['relationship_type'] == 'SUPPORTS':
                    supports_emb = emb_array
                else:
                    contradicts_emb = emb_array

            if supports_emb is None or contradicts_emb is None:
                logger.warning("Failed to parse prototype embeddings")
                return (0.0, 0)

            # Step 2: Get target edge type embedding
            query_target = """
                SELECT embedding
                FROM kg_api.relationship_vocabulary
                WHERE relationship_type = %s
                  AND embedding IS NOT NULL
            """
            # Handle both raw psycopg2 and AGEClient
            if hasattr(self.db, 'pool'):
                # AGEClient with connection pool
                conn = self.db.pool.getconn()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(query_target, (relationship_type,))
                        target_row = cur.fetchone()
                finally:
                    self.db.pool.putconn(conn)
            else:
                # Raw psycopg2 connection
                with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query_target, (relationship_type,))
                    target_row = cur.fetchone()

            if not target_row or not target_row.get('embedding'):
                logger.warning(f"No embedding found for {relationship_type}")
                return (0.0, 0)

            # Parse target embedding
            emb_json = target_row['embedding']
            if isinstance(emb_json, str):
                target_emb = np.array(json.loads(emb_json), dtype=float)
            elif isinstance(emb_json, list):
                target_emb = np.array(emb_json, dtype=float)
            elif isinstance(emb_json, dict):
                target_emb = np.array(list(emb_json.values()), dtype=float)
            else:
                target_emb = np.array(list(emb_json), dtype=float)

            # Step 3: Calculate cosine similarity to prototypes
            def cosine_similarity(a, b):
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

            support_sim = float(cosine_similarity(target_emb, supports_emb))
            contradict_sim = float(cosine_similarity(target_emb, contradicts_emb))

            # Step 4: Calculate grounding contribution
            # Positive if more similar to SUPPORTS, negative if more similar to CONTRADICTS
            # Normalize to [-1, 1] range
            total_sim = abs(support_sim) + abs(contradict_sim)
            if total_sim == 0:
                avg_contribution = 0.0
            else:
                avg_contribution = (support_sim - contradict_sim) / total_sim

            # Step 5: Count distinct concepts with incoming edges of this type
            query_concepts = f"""
                SELECT COUNT(DISTINCT to_concept_id) as concept_count
                FROM kg_api.edge_usage_stats
                WHERE relationship_type = %s
            """

            if hasattr(self.db, 'pool'):
                conn = self.db.pool.getconn()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(query_concepts, (relationship_type,))
                        count_row = cur.fetchone()
                        supports_concepts = count_row['concept_count'] if count_row else 0
                finally:
                    self.db.pool.putconn(conn)
            else:
                with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query_concepts, (relationship_type,))
                    count_row = cur.fetchone()
                    supports_concepts = count_row['concept_count'] if count_row else 0

            return (float(avg_contribution), int(supports_concepts))

        except Exception as e:
            logger.error(f"Error calculating grounding contribution for {relationship_type}: {e}")
            return (0.0, 0)

    async def find_semantic_synonyms(
        self,
        relationship_type: str,
        threshold: float = 0.85,
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find semantic synonyms using embedding similarity (ADR-046).

        Replaces Porter stemmer approach with embedding-based cosine similarity
        for more accurate synonym detection across all vocabulary types.

        Args:
            relationship_type: Edge type to find synonyms for
            threshold: Minimum cosine similarity (0.85 = 85% similar)
            limit: Maximum number of synonyms to return

        Returns:
            List of (synonym_type, similarity_score) tuples sorted by similarity

        Example:
            >>> synonyms = await scorer.find_semantic_synonyms("CAUSES", threshold=0.85)
            >>> for syn, score in synonyms:
            ...     print(f"{syn}: {score:.3f}")
            RESULTS_IN: 0.912
            LEADS_TO: 0.876
            PRODUCES: 0.864
        """
        import numpy as np
        import json

        try:
            # Get target embedding
            query_target = """
                SELECT embedding
                FROM kg_api.relationship_vocabulary
                WHERE relationship_type = %s
                  AND embedding IS NOT NULL
            """

            # Get all other embeddings
            query_all = """
                SELECT relationship_type, embedding
                FROM kg_api.relationship_vocabulary
                WHERE relationship_type != %s
                  AND embedding IS NOT NULL
                  AND is_active = TRUE
            """

            # Handle both raw psycopg2 and AGEClient
            if hasattr(self.db, 'pool'):
                conn = self.db.pool.getconn()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # Get target
                        cur.execute(query_target, (relationship_type,))
                        target_row = cur.fetchone()

                        if not target_row or not target_row.get('embedding'):
                            logger.warning(f"No embedding found for {relationship_type}")
                            return []

                        # Parse target embedding
                        emb_json = target_row['embedding']
                        if isinstance(emb_json, str):
                            target_emb = np.array(json.loads(emb_json), dtype=float)
                        elif isinstance(emb_json, list):
                            target_emb = np.array(emb_json, dtype=float)
                        elif isinstance(emb_json, dict):
                            target_emb = np.array(list(emb_json.values()), dtype=float)
                        else:
                            target_emb = np.array(list(emb_json), dtype=float)

                        # Get all other embeddings
                        cur.execute(query_all, (relationship_type,))
                        candidates = cur.fetchall()
                finally:
                    self.db.pool.putconn(conn)
            else:
                with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get target
                    cur.execute(query_target, (relationship_type,))
                    target_row = cur.fetchone()

                    if not target_row or not target_row.get('embedding'):
                        logger.warning(f"No embedding found for {relationship_type}")
                        return []

                    # Parse target embedding
                    emb_json = target_row['embedding']
                    if isinstance(emb_json, str):
                        target_emb = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        target_emb = np.array(emb_json, dtype=float)
                    elif isinstance(emb_json, dict):
                        target_emb = np.array(list(emb_json.values()), dtype=float)
                    else:
                        target_emb = np.array(list(emb_json), dtype=float)

                    # Get all other embeddings
                    cur.execute(query_all, (relationship_type,))
                    candidates = cur.fetchall()

            # Calculate similarities
            similarities = []

            def cosine_similarity(a, b):
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

            for candidate in candidates:
                # Parse candidate embedding
                emb_json = candidate['embedding']
                if isinstance(emb_json, str):
                    cand_emb = np.array(json.loads(emb_json), dtype=float)
                elif isinstance(emb_json, list):
                    cand_emb = np.array(emb_json, dtype=float)
                elif isinstance(emb_json, dict):
                    cand_emb = np.array(list(emb_json.values()), dtype=float)
                else:
                    cand_emb = np.array(list(emb_json), dtype=float)

                # Calculate similarity
                similarity = float(cosine_similarity(target_emb, cand_emb))

                # Only include if above threshold
                if similarity >= threshold:
                    similarities.append((candidate['relationship_type'], similarity))

            # Sort by similarity (descending) and limit
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:limit]

        except Exception as e:
            logger.error(f"Error finding semantic synonyms for {relationship_type}: {e}")
            return []

    async def get_extraction_vocabulary(
        self,
        max_types: int = 50,
        include_builtin: bool = True,
        min_value_score: float = 0.1,
        grounding_weight: float = 0.3
    ) -> List[str]:
        """
        Get optimal vocabulary subset for LLM extraction prompts (ADR-046).

        Dynamically curates vocabulary based on:
        - Usage metrics (value_score)
        - Grounding contribution (semantic coherence)
        - Semantic diversity (avoid redundant synonyms)

        Algorithm:
        1. Get all edge types with value scores + grounding
        2. Filter by min_value_score threshold
        3. Sort by combined score (value + grounding_weight * grounding)
        4. Deduplicate semantic synonyms (keep highest scoring)
        5. Return top max_types for LLM prompt

        Args:
            max_types: Maximum vocabulary size for LLM prompt
            include_builtin: Include protected builtin types
            min_value_score: Minimum value score to consider
            grounding_weight: How much to weight grounding vs usage (0-1)

        Returns:
            List of relationship type names optimized for extraction

        Example:
            >>> vocab = await scorer.get_extraction_vocabulary(max_types=30)
            >>> print(f"Optimized vocabulary: {len(vocab)} types")
            >>> print(vocab[:5])
            ['IMPLIES', 'CAUSES', 'SUPPORTS', 'ENABLES', 'REQUIRES']
        """
        try:
            # Get all scores with grounding metrics
            scores = await self.get_value_scores(
                include_builtin=include_builtin,
                include_grounding=True
            )

            # Filter by minimum value score
            candidates = [
                score for score in scores.values()
                if score.value_score >= min_value_score
            ]

            # Calculate combined score (value + grounding contribution)
            for score in candidates:
                grounding_contrib = score.avg_grounding_contribution or 0.0
                # Combine value score with grounding contribution
                # Higher grounding_weight = more emphasis on semantic coherence
                score.combined_score = (
                    score.value_score * (1 - grounding_weight) +
                    abs(grounding_contrib) * grounding_weight * 10.0  # Scale grounding to match value range
                )

            # Sort by combined score (descending)
            candidates.sort(key=lambda s: s.combined_score, reverse=True)

            # Deduplicate semantic synonyms (keep highest scoring variant)
            selected = []
            selected_embeddings = []

            import numpy as np
            import json

            def cosine_similarity(a, b):
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

            for candidate in candidates:
                # Check if too similar to already selected types
                is_duplicate = False

                if candidate.embedding:
                    # Parse candidate embedding
                    emb_json = candidate.embedding
                    if isinstance(emb_json, str):
                        cand_emb = np.array(json.loads(emb_json), dtype=float)
                    elif isinstance(emb_json, list):
                        cand_emb = np.array(emb_json, dtype=float)
                    elif isinstance(emb_json, dict):
                        cand_emb = np.array(list(emb_json.values()), dtype=float)
                    else:
                        cand_emb = np.array(list(emb_json), dtype=float)

                    # Check against selected embeddings
                    for sel_emb in selected_embeddings:
                        similarity = cosine_similarity(cand_emb, sel_emb)
                        # If very similar (>90%), consider it a duplicate
                        if similarity > 0.90:
                            is_duplicate = True
                            logger.debug(
                                f"Skipping {candidate.relationship_type} "
                                f"(synonym of existing type, sim={similarity:.3f})"
                            )
                            break

                    if not is_duplicate:
                        selected.append(candidate.relationship_type)
                        selected_embeddings.append(cand_emb)
                else:
                    # No embedding, include it anyway
                    selected.append(candidate.relationship_type)

                # Stop when we have enough
                if len(selected) >= max_types:
                    break

            logger.info(
                f"Curated vocabulary: {len(selected)}/{len(candidates)} types "
                f"(max={max_types}, min_value={min_value_score})"
            )

            return selected

        except Exception as e:
            logger.error(f"Error curating extraction vocabulary: {e}")
            # Fallback to builtin types only
            try:
                query = """
                    SELECT relationship_type
                    FROM kg_api.relationship_vocabulary
                    WHERE is_builtin = TRUE
                      AND is_active = TRUE
                    ORDER BY relationship_type
                """
                result = await self._execute_query(query)
                fallback = [row['relationship_type'] for row in result]
                logger.warning(f"Using fallback vocabulary: {len(fallback)} builtin types")
                return fallback
            except Exception as fallback_error:
                logger.error(f"Fallback vocabulary failed: {fallback_error}")
                return []

    async def generate_merge_recommendations(
        self,
        min_similarity: float = 0.85,
        max_candidates: int = 20,
        consider_grounding: bool = True
    ) -> List[Dict]:
        """
        Generate grounding-aware merge recommendations (ADR-046).

        Replaces ADR-032 synonym_detector + pruning_strategies with graph-native approach.

        Algorithm:
        1. Get all active edge types with scores + grounding
        2. Find semantic synonyms using embedding similarity
        3. For each synonym pair, calculate merge priority:
           - Higher similarity = higher priority
           - Lower grounding difference = safer merge
           - Lower edge count = less disruption
        4. Filter out inverse relationships (TYPE vs TYPE_BY)
        5. Return prioritized merge recommendations

        Args:
            min_similarity: Minimum embedding similarity (default: 0.85)
            max_candidates: Maximum recommendations to return
            consider_grounding: Weight grounding compatibility in priority

        Returns:
            List of merge recommendation dicts with:
            - deprecated_type: Type to deprecate
            - target_type: Type to preserve
            - similarity: Embedding similarity score
            - grounding_delta: Difference in grounding contributions
            - priority_score: Combined priority (higher = better candidate)
            - reasoning: Human-readable explanation

        Example:
            >>> recommendations = await scorer.generate_merge_recommendations(min_similarity=0.85)
            >>> for rec in recommendations[:5]:
            ...     print(f"{rec['deprecated_type']} → {rec['target_type']}: {rec['reasoning']}")
        """
        try:
            # Step 1: Get all edge types with full scoring
            scores = await self.get_value_scores(
                include_builtin=False,  # Don't merge builtin types
                include_grounding=consider_grounding
            )

            if not scores:
                logger.warning("No edge type scores available for merge recommendations")
                return []

            recommendations = []

            # Step 2: Find synonym pairs for each type
            for type_name, score in scores.items():
                synonyms = await self.find_semantic_synonyms(
                    type_name,
                    threshold=min_similarity,
                    limit=5  # Top 5 synonyms per type
                )

                for synonym_type, similarity in synonyms:
                    synonym_score = scores.get(synonym_type)
                    if not synonym_score:
                        continue

                    # Filter: Skip inverse relationships (TYPE vs TYPE_BY)
                    type1_base = type_name.replace('_BY', '').replace('_TO', '')
                    type2_base = synonym_type.replace('_BY', '').replace('_TO', '')
                    if type1_base == type2_base:
                        logger.debug(f"Skipping inverse pair: {type_name} / {synonym_type}")
                        continue

                    # Determine which to deprecate (lower usage = deprecate)
                    if score.edge_count >= synonym_score.edge_count:
                        target = type_name
                        deprecated = synonym_type
                        target_score = score
                        deprecated_score = synonym_score
                    else:
                        target = synonym_type
                        deprecated = type_name
                        target_score = synonym_score
                        deprecated_score = score

                    # Calculate grounding delta (if available)
                    grounding_delta = 0.0
                    if consider_grounding and target_score.avg_grounding_contribution is not None:
                        target_grounding = target_score.avg_grounding_contribution or 0.0
                        deprecated_grounding = deprecated_score.avg_grounding_contribution or 0.0
                        grounding_delta = abs(target_grounding - deprecated_grounding)

                    # Calculate priority score
                    # High similarity + low grounding delta + low edge count = high priority
                    priority_score = (
                        similarity * 2.0 +  # Similarity is most important
                        (1.0 - grounding_delta) * 0.5 +  # Compatible grounding is good
                        (1.0 - min(deprecated_score.edge_count / 100.0, 1.0)) * 0.3  # Low disruption is good
                    )

                    # Generate reasoning
                    reasoning_parts = [
                        f"High similarity ({similarity:.1%})",
                    ]
                    if deprecated_score.edge_count == 0:
                        reasoning_parts.append("zero edges (safe)")
                    else:
                        reasoning_parts.append(f"{deprecated_score.edge_count} edges to update")

                    if consider_grounding and grounding_delta > 0:
                        reasoning_parts.append(f"grounding Δ={grounding_delta:.3f}")

                    reasoning = "; ".join(reasoning_parts)

                    recommendations.append({
                        'deprecated_type': deprecated,
                        'target_type': target,
                        'similarity': float(similarity),
                        'grounding_delta': float(grounding_delta),
                        'priority_score': float(priority_score),
                        'affected_edges': deprecated_score.edge_count,
                        'reasoning': reasoning,
                        'target_grounding': target_score.avg_grounding_contribution,
                        'deprecated_grounding': deprecated_score.avg_grounding_contribution
                    })

            # Step 3: Deduplicate (same pair might appear twice)
            seen_pairs = set()
            unique_recommendations = []

            for rec in recommendations:
                pair_key = frozenset([rec['deprecated_type'], rec['target_type']])
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    unique_recommendations.append(rec)

            # Step 4: Sort by priority and limit
            unique_recommendations.sort(key=lambda r: r['priority_score'], reverse=True)

            logger.info(
                f"Generated {len(unique_recommendations)} merge recommendations "
                f"(min_similarity={min_similarity:.0%})"
            )

            return unique_recommendations[:max_candidates]

        except Exception as e:
            logger.error(f"Error generating merge recommendations: {e}")
            return []

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
            logger.error(f"Error getting zero-edge types: {e}")
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
    print("  from api.app.lib.vocabulary_scoring import VocabularyScorer")
    print("  scorer = VocabularyScorer(db_client)")
    print("  scores = await scorer.get_value_scores()")
    print()
    print("For testing, run: pytest tests/test_vocabulary_scoring.py")
