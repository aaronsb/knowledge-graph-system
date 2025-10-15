"""
Synonym Detector for Automatic Edge Vocabulary Expansion.

Detects potential synonyms among edge types using embedding-based similarity
to identify merge candidates and reduce vocabulary duplication (ADR-032).

Similarity Thresholds:
    - similarity >= 0.90: Strong merge candidate (auto-suggest)
    - similarity >= 0.70: Review needed (human decision)
    - similarity < 0.70: Not synonyms (distinct types)

Merge Strategy:
    - Preserve higher-value type (based on VocabularyScorer)
    - Combine usage statistics
    - Update all edges to use preserved type
    - Mark deprecated type as inactive

Usage:
    from src.api.lib.synonym_detector import SynonymDetector

    detector = SynonymDetector(ai_provider)
    candidates = await detector.find_synonyms(["VALIDATES", "VERIFIES"])

    for candidate in candidates:
        if candidate.is_strong_match:
            print(f"Auto-merge: {candidate.type1} ≈ {candidate.type2}")
        else:
            print(f"Review: {candidate.type1} ≈ {candidate.type2}")

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - ADR-025: Dynamic Relationship Vocabulary
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import numpy as np


class SynonymStrength(Enum):
    """Synonym match strength categories."""
    STRONG = "strong"          # >= 0.90: auto-suggest merge
    MODERATE = "moderate"      # >= 0.70: review needed
    WEAK = "weak"              # < 0.70: not synonyms


@dataclass
class SynonymCandidate:
    """
    Potential synonym pair with similarity metrics.

    Attributes:
        type1: First edge type
        type2: Second edge type
        similarity: Cosine similarity score (0.0-1.0)
        strength: Match strength category (STRONG/MODERATE/WEAK)
        is_strong_match: True if >= 0.90 (auto-merge candidate)
        needs_review: True if 0.70-0.89 (human decision needed)
        reasoning: Explanation of similarity assessment
    """
    type1: str
    type2: str
    similarity: float
    strength: SynonymStrength
    is_strong_match: bool
    needs_review: bool
    reasoning: str

    def __repr__(self) -> str:
        return (
            f"SynonymCandidate({self.type1} ≈ {self.type2}, "
            f"sim={self.similarity:.3f}, {self.strength.value})"
        )


@dataclass
class MergeRecommendation:
    """
    Recommendation for merging synonym pair.

    Attributes:
        preserve_type: Type to keep (higher value)
        deprecate_type: Type to mark inactive
        similarity: Similarity score
        affected_edges: Number of edges that will be updated
        reasoning: Why this merge is recommended
    """
    preserve_type: str
    deprecate_type: str
    similarity: float
    affected_edges: int
    reasoning: str

    def __repr__(self) -> str:
        return (
            f"MergeRecommendation({self.deprecate_type} → {self.preserve_type}, "
            f"{self.affected_edges} edges)"
        )


class SynonymDetector:
    """
    Detect synonym edge types using embedding similarity.

    Uses cosine similarity between edge type embeddings to identify
    potential synonyms for vocabulary consolidation.
    """

    # Similarity thresholds (per ADR-032)
    STRONG_MATCH_THRESHOLD = 0.90      # Auto-suggest merge
    MODERATE_MATCH_THRESHOLD = 0.70    # Review needed

    def __init__(self, ai_provider):
        """
        Initialize detector with AI provider for embeddings.

        Args:
            ai_provider: AI provider instance with generate_embedding() method
        """
        self.ai_provider = ai_provider
        self._embedding_cache: Dict[str, np.ndarray] = {}

    async def find_synonyms(
        self,
        edge_types: List[str],
        min_similarity: float = MODERATE_MATCH_THRESHOLD
    ) -> List[SynonymCandidate]:
        """
        Find potential synonyms among edge types.

        Args:
            edge_types: List of edge types to compare
            min_similarity: Minimum similarity to include (default: 0.70)

        Returns:
            List of SynonymCandidate objects sorted by similarity (highest first)

        Example:
            >>> detector = SynonymDetector(ai_provider)
            >>> candidates = await detector.find_synonyms(["VALIDATES", "VERIFIES", "CHECKS"])
            >>> for c in candidates:
            ...     if c.is_strong_match:
            ...         print(f"Merge {c.type1} with {c.type2}")
        """
        candidates = []

        # Generate embeddings for all types
        embeddings = {}
        for edge_type in edge_types:
            embeddings[edge_type] = await self._get_edge_type_embedding(edge_type)

        # Compare all pairs
        compared_pairs: Set[Tuple[str, str]] = set()

        for i, type1 in enumerate(edge_types):
            for type2 in edge_types[i + 1:]:
                # Skip self-comparison (same type name)
                if type1 == type2:
                    continue

                # Avoid duplicate comparisons
                pair = tuple(sorted([type1, type2]))
                if pair in compared_pairs:
                    continue
                compared_pairs.add(pair)

                # Calculate similarity
                similarity = self._cosine_similarity(
                    embeddings[type1],
                    embeddings[type2]
                )

                # Only include if above minimum threshold
                if similarity >= min_similarity:
                    # Determine strength category
                    if similarity >= self.STRONG_MATCH_THRESHOLD:
                        strength = SynonymStrength.STRONG
                        is_strong = True
                        needs_review = False
                        reasoning = f"Very high similarity ({similarity:.3f}) - strong merge candidate"
                    elif similarity >= self.MODERATE_MATCH_THRESHOLD:
                        strength = SynonymStrength.MODERATE
                        is_strong = False
                        needs_review = True
                        reasoning = f"Moderate similarity ({similarity:.3f}) - review recommended"
                    else:
                        strength = SynonymStrength.WEAK
                        is_strong = False
                        needs_review = False
                        reasoning = f"Low similarity ({similarity:.3f}) - likely distinct types"

                    candidates.append(SynonymCandidate(
                        type1=type1,
                        type2=type2,
                        similarity=similarity,
                        strength=strength,
                        is_strong_match=is_strong,
                        needs_review=needs_review,
                        reasoning=reasoning
                    ))

        # Sort by similarity (highest first)
        candidates.sort(key=lambda c: c.similarity, reverse=True)

        return candidates

    async def find_synonyms_for_type(
        self,
        edge_type: str,
        existing_types: List[str],
        min_similarity: float = MODERATE_MATCH_THRESHOLD
    ) -> List[SynonymCandidate]:
        """
        Find potential synonyms for a single edge type.

        Useful for checking new types during auto-expansion.

        Args:
            edge_type: Edge type to find synonyms for
            existing_types: List of existing types to compare against
            min_similarity: Minimum similarity to include (default: 0.70)

        Returns:
            List of SynonymCandidate objects sorted by similarity

        Example:
            >>> detector = SynonymDetector(ai_provider)
            >>> synonyms = await detector.find_synonyms_for_type(
            ...     "VERIFIES",
            ...     ["VALIDATES", "CHECKS", "CONFIRMS"]
            ... )
            >>> if synonyms and synonyms[0].is_strong_match:
            ...     print(f"Don't add VERIFIES - use {synonyms[0].type2} instead")
        """
        # Get embedding for target type
        target_embedding = await self._get_edge_type_embedding(edge_type)

        candidates = []

        for existing_type in existing_types:
            # Skip self-comparison
            if existing_type == edge_type:
                continue

            # Get embedding for existing type
            existing_embedding = await self._get_edge_type_embedding(existing_type)

            # Calculate similarity
            similarity = self._cosine_similarity(target_embedding, existing_embedding)

            # Only include if above threshold
            if similarity >= min_similarity:
                # Determine strength
                if similarity >= self.STRONG_MATCH_THRESHOLD:
                    strength = SynonymStrength.STRONG
                    is_strong = True
                    needs_review = False
                    reasoning = f"Very high similarity ({similarity:.3f}) - use existing type instead"
                elif similarity >= self.MODERATE_MATCH_THRESHOLD:
                    strength = SynonymStrength.MODERATE
                    is_strong = False
                    needs_review = True
                    reasoning = f"Moderate similarity ({similarity:.3f}) - consider reusing existing type"
                else:
                    strength = SynonymStrength.WEAK
                    is_strong = False
                    needs_review = False
                    reasoning = f"Low similarity ({similarity:.3f}) - distinct types"

                candidates.append(SynonymCandidate(
                    type1=edge_type,
                    type2=existing_type,
                    similarity=similarity,
                    strength=strength,
                    is_strong_match=is_strong,
                    needs_review=needs_review,
                    reasoning=reasoning
                ))

        # Sort by similarity (highest first)
        candidates.sort(key=lambda c: c.similarity, reverse=True)

        return candidates

    async def suggest_merge(
        self,
        type1: str,
        type2: str,
        type1_edge_count: int,
        type2_edge_count: int,
        type1_value_score: Optional[float] = None,
        type2_value_score: Optional[float] = None
    ) -> MergeRecommendation:
        """
        Suggest merge strategy for synonym pair.

        Determines which type to preserve based on:
        1. Value score (if provided)
        2. Edge count (fallback)
        3. Alphabetical order (tiebreaker)

        Args:
            type1: First edge type
            type2: Second edge type
            type1_edge_count: Number of edges using type1
            type2_edge_count: Number of edges using type2
            type1_value_score: Optional value score for type1
            type2_value_score: Optional value score for type2

        Returns:
            MergeRecommendation with preserve/deprecate decision

        Example:
            >>> recommendation = await detector.suggest_merge(
            ...     "VALIDATES", "VERIFIES",
            ...     type1_edge_count=120, type2_edge_count=45,
            ...     type1_value_score=45.2, type2_value_score=12.3
            ... )
            >>> print(f"Preserve: {recommendation.preserve_type}")
            >>> print(f"Deprecate: {recommendation.deprecate_type}")
        """
        # Calculate similarity
        emb1 = await self._get_edge_type_embedding(type1)
        emb2 = await self._get_edge_type_embedding(type2)
        similarity = self._cosine_similarity(emb1, emb2)

        # Determine which to preserve
        preserve_type = None
        deprecate_type = None
        reasoning_parts = []

        # Decision 1: Use value scores if both provided
        if type1_value_score is not None and type2_value_score is not None:
            if type1_value_score > type2_value_score:
                preserve_type = type1
                deprecate_type = type2
                reasoning_parts.append(
                    f"'{type1}' has higher value score ({type1_value_score:.2f} vs {type2_value_score:.2f})"
                )
            elif type2_value_score > type1_value_score:
                preserve_type = type2
                deprecate_type = type1
                reasoning_parts.append(
                    f"'{type2}' has higher value score ({type2_value_score:.2f} vs {type1_value_score:.2f})"
                )

        # Decision 2: Use edge counts if no value scores or tie
        if preserve_type is None:
            if type1_edge_count > type2_edge_count:
                preserve_type = type1
                deprecate_type = type2
                reasoning_parts.append(
                    f"'{type1}' has more edges ({type1_edge_count} vs {type2_edge_count})"
                )
            elif type2_edge_count > type1_edge_count:
                preserve_type = type2
                deprecate_type = type1
                reasoning_parts.append(
                    f"'{type2}' has more edges ({type2_edge_count} vs {type1_edge_count})"
                )

        # Decision 3: Alphabetical tiebreaker
        if preserve_type is None:
            if type1 < type2:
                preserve_type = type1
                deprecate_type = type2
                reasoning_parts.append("alphabetical tiebreaker")
            else:
                preserve_type = type2
                deprecate_type = type1
                reasoning_parts.append("alphabetical tiebreaker")

        # Calculate total affected edges
        affected_edges = type1_edge_count + type2_edge_count

        reasoning = (
            f"Merge '{deprecate_type}' into '{preserve_type}' "
            f"(similarity: {similarity:.3f}). "
            f"Reason: {' and '.join(reasoning_parts)}. "
            f"Will update {affected_edges} total edges."
        )

        return MergeRecommendation(
            preserve_type=preserve_type,
            deprecate_type=deprecate_type,
            similarity=similarity,
            affected_edges=affected_edges,
            reasoning=reasoning
        )

    async def batch_detect_duplicates(
        self,
        edge_types: List[str],
        strong_only: bool = False
    ) -> Dict[str, List[str]]:
        """
        Detect duplicate clusters in vocabulary.

        Groups edge types into synonym clusters for bulk review.

        Args:
            edge_types: List of all edge types to analyze
            strong_only: Only include strong matches (>= 0.90)

        Returns:
            Dict mapping primary type -> list of similar types

        Example:
            >>> clusters = await detector.batch_detect_duplicates(all_types)
            >>> for primary, similars in clusters.items():
            ...     print(f"{primary}: {', '.join(similars)}")
        """
        min_sim = self.STRONG_MATCH_THRESHOLD if strong_only else self.MODERATE_MATCH_THRESHOLD

        # Find all synonym candidates
        candidates = await self.find_synonyms(edge_types, min_similarity=min_sim)

        # Build clusters
        clusters: Dict[str, Set[str]] = {}

        for candidate in candidates:
            # Add type1 cluster
            if candidate.type1 not in clusters:
                clusters[candidate.type1] = set()
            clusters[candidate.type1].add(candidate.type2)

            # Add type2 cluster
            if candidate.type2 not in clusters:
                clusters[candidate.type2] = set()
            clusters[candidate.type2].add(candidate.type1)

        # Convert sets to sorted lists
        result = {
            primary: sorted(list(similars))
            for primary, similars in clusters.items()
            if similars  # Only include types with synonyms
        }

        return result

    async def _get_edge_type_embedding(self, edge_type: str) -> np.ndarray:
        """
        Get embedding for edge type (with caching).

        First checks in-memory cache, then database, then generates via API.

        Args:
            edge_type: Edge type name

        Returns:
            Numpy array of embedding vector
        """
        # Check in-memory cache first
        if edge_type in self._embedding_cache:
            return self._embedding_cache[edge_type]

        # Check database for pre-generated embedding
        # Import here to avoid circular dependency
        from .age_client import AGEClient

        db = AGEClient()
        try:
            embedding_data = db.get_vocabulary_embedding(edge_type)

            if embedding_data and embedding_data.get('embedding'):
                # Use database embedding
                embedding = np.array(embedding_data['embedding'])

                # Cache for reuse
                self._embedding_cache[edge_type] = embedding

                return embedding
        finally:
            db.close()

        # Fallback: Generate new embedding via API
        # Convert edge type to descriptive text
        descriptive_text = self._edge_type_to_text(edge_type)

        # Generate embedding
        result = await self.ai_provider.generate_embedding(descriptive_text)
        embedding = np.array(result["embedding"])

        # Cache for reuse
        self._embedding_cache[edge_type] = embedding

        # Store in database for future use
        try:
            db = AGEClient()
            try:
                db.update_vocabulary_embedding(
                    edge_type,
                    embedding.tolist(),
                    self.ai_provider.get_embedding_model()
                )
            finally:
                db.close()
        except Exception as e:
            # Don't fail if database update fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to store embedding for {edge_type}: {e}")

        return embedding

    def _edge_type_to_text(self, edge_type: str) -> str:
        """
        Convert edge type to descriptive text for embeddings.

        Args:
            edge_type: Edge type name (e.g., "VALIDATES")

        Returns:
            Descriptive text

        Example:
            >>> _edge_type_to_text("VALIDATES")
            "relationship: validates"
        """
        # Convert uppercase underscore to lowercase words
        words = edge_type.lower().replace("_", " ")

        # Add semantic context
        return f"relationship: {words}"

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Clamp to [0, 1] range
        return max(0.0, min(1.0, similarity))

    def clear_cache(self):
        """Clear embedding cache (useful for testing)."""
        self._embedding_cache.clear()


# ============================================================================
# Utility Functions
# ============================================================================


def filter_by_strength(
    candidates: List[SynonymCandidate],
    strength: SynonymStrength
) -> List[SynonymCandidate]:
    """
    Filter synonym candidates by strength.

    Args:
        candidates: List of synonym candidates
        strength: Target strength level

    Returns:
        Filtered list

    Example:
        >>> strong_matches = filter_by_strength(candidates, SynonymStrength.STRONG)
        >>> for match in strong_matches:
        ...     print(f"Auto-merge: {match.type1} with {match.type2}")
    """
    return [c for c in candidates if c.strength == strength]


def get_merge_graph(candidates: List[SynonymCandidate]) -> Dict[str, List[str]]:
    """
    Build merge graph from synonym candidates.

    Creates adjacency list for merge planning.

    Args:
        candidates: List of synonym candidates

    Returns:
        Dict mapping edge type -> list of synonym types

    Example:
        >>> graph = get_merge_graph(candidates)
        >>> print(graph)
        {'VALIDATES': ['VERIFIES', 'CHECKS'], 'VERIFIES': ['VALIDATES']}
    """
    graph: Dict[str, List[str]] = {}

    for candidate in candidates:
        # Add type1 -> type2
        if candidate.type1 not in graph:
            graph[candidate.type1] = []
        graph[candidate.type1].append(candidate.type2)

        # Add type2 -> type1
        if candidate.type2 not in graph:
            graph[candidate.type2] = []
        graph[candidate.type2].append(candidate.type1)

    return graph


if __name__ == "__main__":
    # Quick demonstration
    import asyncio
    import sys

    print("Synonym Detector - ADR-032 Implementation")
    print("=" * 60)
    print()
    print("This module detects synonym edge types using:")
    print("  - Embedding-based similarity (cosine)")
    print("  - Strong match threshold: >= 0.90 (auto-merge)")
    print("  - Moderate match threshold: >= 0.70 (review needed)")
    print()
    print("Usage:")
    print("  from src.api.lib.synonym_detector import SynonymDetector")
    print("  detector = SynonymDetector(ai_provider)")
    print("  candidates = await detector.find_synonyms(edge_types)")
    print()
    print("For testing, run: pytest tests/test_synonym_detector.py")
