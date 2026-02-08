"""
Category Classifier for Automatic Edge Vocabulary Expansion.

Classifies edge types into semantic categories using embedding-based similarity.
Implements high bar for new category creation to prevent proliferation (ADR-032).

Classification Logic:
    - confidence >= 0.3: Assign to existing category (good fit)
    - confidence < 0.3 (for ALL categories): Propose new category

Category Limits:
    - MIN: 8 (protected core categories)
    - MERGE_THRESHOLD: 12 (start flagging merge opportunities)
    - MAX: 15 (hard limit, block new categories)

Usage:
    from api.app.lib.category_classifier import CategoryClassifier

    classifier = CategoryClassifier(ai_provider)
    result = await classifier.classify_edge_type("VALIDATES")

    if result.should_create_new:
        print(f"Propose new category: {result.suggested_category}")
    else:
        print(f"Assign to: {result.best_match_category} ({result.confidence:.2f})")

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - ADR-022: Semantic Relationship Taxonomy (30-type system)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from api.app.constants import RELATIONSHIP_CATEGORIES

@dataclass
class CategoryClassification:
    """
    Classification result for an edge type.

    Attributes:
        edge_type: Edge type being classified
        best_match_category: Category with highest similarity
        confidence: Similarity score of best match (0.0-1.0)
        all_scores: Dict mapping category -> confidence score
        should_create_new: True if no good fit found (all < 0.3)
        suggested_category: Suggested name if creating new category
        reasoning: Explanation of classification decision
    """
    edge_type: str
    best_match_category: Optional[str]
    confidence: float
    all_scores: Dict[str, float]
    should_create_new: bool
    suggested_category: Optional[str]
    reasoning: str

    def __repr__(self) -> str:
        if self.should_create_new:
            return f"CategoryClassification({self.edge_type} -> NEW: {self.suggested_category})"
        else:
            return f"CategoryClassification({self.edge_type} -> {self.best_match_category}, conf={self.confidence:.2f})"


class CategoryClassifier:
    """
    Classify edge types into semantic categories using embeddings.

    Uses cosine similarity between edge type and category embeddings
    to determine best fit.
    """

    # Classification thresholds (per ADR-032)
    GOOD_FIT_THRESHOLD = 0.3        # >= 0.3: assign to existing
    NEW_CATEGORY_THRESHOLD = 0.3    # < 0.3 for ALL: propose new

    # Category limits
    CATEGORY_MIN = 8                # Protected core categories
    CATEGORY_MERGE_THRESHOLD = 12   # Flag merge opportunities
    CATEGORY_MAX = 15               # Hard limit

    # Protected core categories (from ADR-022)
    PROTECTED_CATEGORIES = {
        "logical_truth",
        "causal",
        "structural",
        "evidential",
        "similarity",
        "temporal",
        "functional",
        "meta"
    }

    def __init__(self, ai_provider):
        """
        Initialize classifier with AI provider for embeddings.

        Args:
            ai_provider: AI provider instance with generate_embedding() method
        """
        self.ai_provider = ai_provider
        self._category_embeddings_cache = {}

    async def classify_edge_type(
        self,
        edge_type: str,
        existing_categories: Optional[List[str]] = None
    ) -> CategoryClassification:
        """
        Classify an edge type into a category.

        Args:
            edge_type: Edge type to classify (e.g., "VALIDATES", "TRIGGERS")
            existing_categories: List of existing category names
                                (defaults to RELATIONSHIP_CATEGORIES keys)

        Returns:
            CategoryClassification with assignment or new category proposal

        Example:
            >>> classifier = CategoryClassifier(ai_provider)
            >>> result = await classifier.classify_edge_type("VALIDATES")
            >>> if result.confidence >= 0.3:
            ...     print(f"Assign to {result.best_match_category}")
        """
        # Default to built-in categories
        if existing_categories is None:
            existing_categories = list(RELATIONSHIP_CATEGORIES.keys())

        # Generate embedding for edge type
        edge_embedding = await self._get_edge_type_embedding(edge_type)

        # Calculate similarity to each category
        scores = {}
        for category in existing_categories:
            category_embedding = await self._get_category_embedding(category)
            similarity = self._cosine_similarity(edge_embedding, category_embedding)
            scores[category] = similarity

        # Find best match
        best_category = max(scores, key=scores.get)
        best_confidence = scores[best_category]

        # Decision: assign or propose new
        if best_confidence >= self.GOOD_FIT_THRESHOLD:
            # Good fit found - assign to existing category
            return CategoryClassification(
                edge_type=edge_type,
                best_match_category=best_category,
                confidence=best_confidence,
                all_scores=scores,
                should_create_new=False,
                suggested_category=None,
                reasoning=f"Good fit to '{best_category}' (confidence: {best_confidence:.2f})"
            )
        else:
            # No good fit - propose new category
            suggested_name = await self._suggest_category_name(edge_type)

            return CategoryClassification(
                edge_type=edge_type,
                best_match_category=None,
                confidence=best_confidence,
                all_scores=scores,
                should_create_new=True,
                suggested_category=suggested_name,
                reasoning=f"No good fit (best: '{best_category}' at {best_confidence:.2f}). Suggest new category: '{suggested_name}'"
            )

    async def _get_edge_type_embedding(self, edge_type: str) -> np.ndarray:
        """
        Generate embedding for edge type.

        Args:
            edge_type: Edge type name

        Returns:
            Numpy array of embedding vector
        """
        # Convert edge type to descriptive text for better embeddings
        descriptive_text = self._edge_type_to_text(edge_type)

        result = self.ai_provider.generate_embedding(descriptive_text)
        embedding = result["embedding"]

        return np.array(embedding)

    async def _get_category_embedding(self, category: str) -> np.ndarray:
        """
        Get embedding for category (with caching).

        Generates embedding based on category name and example edge types.

        Args:
            category: Category name

        Returns:
            Numpy array of embedding vector
        """
        # Check cache
        if category in self._category_embeddings_cache:
            return self._category_embeddings_cache[category]

        # Generate descriptive text for category
        descriptive_text = self._category_to_text(category)

        result = self.ai_provider.generate_embedding(descriptive_text)
        embedding = np.array(result["embedding"])

        # Cache for reuse
        self._category_embeddings_cache[category] = embedding

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
            "validates verification confirmation checking"
        """
        # Convert uppercase underscore to lowercase words
        words = edge_type.lower().replace("_", " ")

        # Add semantic expansion for better embeddings
        # This helps capture the semantic meaning
        return f"relationship: {words}"

    def _category_to_text(self, category: str) -> str:
        """
        Convert category to descriptive text for embeddings.

        Includes category name and example edge types.

        Args:
            category: Category name

        Returns:
            Descriptive text with examples

        Example:
            >>> _category_to_text("causal")
            "causal relationships: causes, enables, prevents, influences, results from"
        """
        # Get example edge types from this category
        examples = RELATIONSHIP_CATEGORIES.get(category, [])
        example_text = ", ".join([e.lower().replace("_", " ") for e in examples[:5]])

        return f"{category} relationships: {example_text}"

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

    async def _suggest_category_name(self, edge_type: str) -> str:
        """
        Suggest a category name for a new category.

        Uses simple heuristics based on edge type name.

        Args:
            edge_type: Edge type needing new category

        Returns:
            Suggested category name

        Example:
            >>> _suggest_category_name("MONITORS")
            "observational"
        """
        # Simple heuristic: derive from edge type
        # In production, this could use LLM to generate better names

        edge_lower = edge_type.lower()

        # Common patterns
        if any(word in edge_lower for word in ["monitor", "observe", "track", "watch"]):
            return "observational"
        elif any(word in edge_lower for word in ["validate", "verify", "check", "test"]):
            return "validation"
        elif any(word in edge_lower for word in ["restrict", "constrain", "limit", "bound"]):
            return "constraint"
        elif any(word in edge_lower for word in ["enhance", "improve", "optimize", "refine"]):
            return "enhancement"
        elif any(word in edge_lower for word in ["connect", "link", "associate", "relate"]):
            return "associative"
        else:
            # Default: use first word as category base
            first_word = edge_lower.split("_")[0] if "_" in edge_lower else edge_lower
            return f"{first_word}_based"

    async def batch_classify(
        self,
        edge_types: List[str],
        existing_categories: Optional[List[str]] = None
    ) -> Dict[str, CategoryClassification]:
        """
        Classify multiple edge types in batch.

        More efficient than individual calls due to caching.

        Args:
            edge_types: List of edge types to classify
            existing_categories: List of existing category names

        Returns:
            Dict mapping edge_type -> CategoryClassification

        Example:
            >>> results = await classifier.batch_classify(["VALIDATES", "MONITORS"])
            >>> for edge_type, result in results.items():
            ...     print(f"{edge_type}: {result.best_match_category}")
        """
        results = {}

        for edge_type in edge_types:
            result = await self.classify_edge_type(edge_type, existing_categories)
            results[edge_type] = result

        return results

    def check_category_limits(self, current_count: int) -> Dict[str, any]:
        """
        Check if category count is within acceptable limits.

        Args:
            current_count: Current number of categories

        Returns:
            Dict with limit check results

        Example:
            >>> limits = classifier.check_category_limits(13)
            >>> if limits["at_max"]:
            ...     print("Cannot create new categories")
        """
        return {
            "current_count": current_count,
            "min": self.CATEGORY_MIN,
            "merge_threshold": self.CATEGORY_MERGE_THRESHOLD,
            "max": self.CATEGORY_MAX,
            "below_min": current_count < self.CATEGORY_MIN,
            "should_merge": current_count >= self.CATEGORY_MERGE_THRESHOLD,
            "at_max": current_count >= self.CATEGORY_MAX,
            "can_add": current_count < self.CATEGORY_MAX,
            "space_remaining": max(0, self.CATEGORY_MAX - current_count)
        }

    def is_protected_category(self, category: str) -> bool:
        """
        Check if category is protected (cannot be deleted).

        Args:
            category: Category name

        Returns:
            True if protected

        Example:
            >>> classifier.is_protected_category("causal")
            True
            >>> classifier.is_protected_category("custom_category")
            False
        """
        return category in self.PROTECTED_CATEGORIES


# ============================================================================
# Utility Functions
# ============================================================================


def get_category_for_edge_type(edge_type: str) -> Optional[str]:
    """
    Get the category for a known edge type.

    Looks up in RELATIONSHIP_CATEGORIES constant.

    Args:
        edge_type: Edge type name

    Returns:
        Category name if found, None otherwise

    Example:
        >>> get_category_for_edge_type("CAUSES")
        "causal"
        >>> get_category_for_edge_type("UNKNOWN_TYPE")
        None
    """
    for category, types in RELATIONSHIP_CATEGORIES.items():
        if edge_type in types:
            return category
    return None


def get_edge_types_in_category(category: str) -> List[str]:
    """
    Get all edge types in a category.

    Args:
        category: Category name

    Returns:
        List of edge types in category

    Example:
        >>> types = get_edge_types_in_category("causal")
        >>> "CAUSES" in types
        True
    """
    return RELATIONSHIP_CATEGORIES.get(category, [])


if __name__ == "__main__":
    # Quick demonstration
    import asyncio
    import sys

    print("Category Classifier - ADR-032 Implementation")
    print("=" * 60)
    print()
    print("This module classifies edge types into semantic categories using:")
    print("  - Embedding-based similarity (cosine)")
    print("  - High bar for new categories (< 0.3 confidence for ALL)")
    print("  - Category limits (8 min, 15 max, 12 merge threshold)")
    print()
    print("Usage:")
    print("  from api.app.lib.category_classifier import CategoryClassifier")
    print("  classifier = CategoryClassifier(ai_provider)")
    print("  result = await classifier.classify_edge_type('VALIDATES')")
    print()
    print("Protected categories:")
    for cat in sorted(CategoryClassifier.PROTECTED_CATEGORIES):
        print(f"  - {cat}")
    print()
    print("For testing, run: pytest tests/test_category_classifier.py")
